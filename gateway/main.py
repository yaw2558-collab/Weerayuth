"""thai-customs product gateway (Phase 2).

- Firebase ID token auth (all endpoints except /healthz, /, /billing/packages, /billing/webhook)
- Flat-rate credits: 10 credits/query, 1 credit = 1 THB
- New users get 30 bonus credits (3 trial queries)
- Consent required before first chat (POST /consent)
- File attachments: images (vision) + xlsx/pdf/docx/csv/txt (text extract)
- Stripe top-up: GET /billing/packages, POST /billing/checkout, POST /billing/webhook
  (card + PromptPay; webhook also handles async payment events)
- POST /chat streams SSE when Accept: text/event-stream, else returns JSON
- Text-only answers are cached in answer_cache (30d TTL) for instant repeats
- Serves minimal chat frontend at /

Run locally from thai-customs/ (reads gateway/.env if present):
    ..\\.venv\\Scripts\\uvicorn gateway.main:app --port 8001
"""

import hashlib
import io
import json
import os
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

import firebase_admin
from firebase_admin import auth as fb_auth
from firebase_admin import firestore

import stripe

from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types as genai_types

from thai_customs_agent.agent import root_agent

APP_NAME = "thai_customs_agent"
PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "glowing-magnet-330507")
ADMIN_KEY = os.environ.get("ADMIN_KEY", "dev-admin-key")
APP_URL = os.environ.get("APP_URL", "http://127.0.0.1:8001").rstrip("/")

STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
# Test-mode price IDs (created 2026-10-08). Override with STRIPE_PRICES_JSON
# ({"price_...": {"credits": N, "thb": N, "label": "..."}}) for live prices.
STRIPE_PRICES = {
  "price_1UO6WNBJq5csWDqWBVufHz2a": {"credits": 100, "thb": 100, "label": "100 เครดิต"},
  "price_1UO6WNBJq5csWDqW7DJFvWkp": {"credits": 500, "thb": 450, "label": "500 เครดิต"},
  "price_1UO6WOBJq5csWDqWNSk9iBup": {"credits": 1000, "thb": 800, "label": "1000 เครดิต"},
}
if os.environ.get("STRIPE_PRICES_JSON"):
  STRIPE_PRICES = json.loads(os.environ["STRIPE_PRICES_JSON"])

CREDITS_PER_QUERY = 10  # flat rate; true cost ~2 THB avg (Phase 0 measured)
NEW_USER_BONUS = 30  # 3 free trial queries
RATE_LIMIT_S = 20
MAX_FILE_MB = 20
MAX_TEXT_CHARS = 100_000
CACHE_VERSION = "v1"  # bump to invalidate answer_cache (e.g. model change)
CACHE_TTL_S = 30 * 24 * 3600  # cached answers stay servable for 30 days

FOOTER = (
  "\n\n---\nสนใจใช้บริการนำเข้า/ปรึกษาพิกัดเพิ่มเติม ติดต่อเรา: "
  "[LINE OA](https://lin.ee/Z55Jn7C) | "
  "[Facebook](https://www.facebook.com/weerayuth.sangkamanee.2025) | "
  "[yaw2558@gmail.com](mailto:yaw2558@gmail.com)"
)

# Pricing in USD (published Gemini pricing) - telemetry estimate only.
IN_PER_1M = 1.25
OUT_PER_1M = 10.00
GROUND_PER_1K = 35.00

firebase_admin.initialize_app(options={"projectId": PROJECT})
db = firestore.client()
session_service = InMemorySessionService()
runner = Runner(agent=root_agent, app_name=APP_NAME, session_service=session_service)
# SSE mode yields partial text chunks (typewriter) + final aggregated events.
_STREAM_CONFIG = RunConfig(streaming_mode=StreamingMode.SSE)

app = FastAPI(title="thai-customs gateway")
_last_call: dict[str, float] = {}


class GrantIn(BaseModel):
  uid: str
  credits: int


def _verify(authorization: str | None) -> dict:
  if not authorization or not authorization.startswith("Bearer "):
    raise HTTPException(401, "missing bearer token")
  try:
    return fb_auth.verify_id_token(authorization[7:])
  except Exception:
    raise HTTPException(401, "invalid token")


def _user_ref(uid: str):
  return db.collection("users").document(uid)


def _get_or_create_user(uid: str, email: str | None) -> dict:
  ref = _user_ref(uid)
  snap = ref.get()
  if snap.exists:
    return snap.to_dict()
  data = {
    "email": email,
    "credits": NEW_USER_BONUS,
    "created": firestore.SERVER_TIMESTAMP,
    "consent_ts": None,
  }
  ref.set(data)
  db.collection("credits_ledger").add(
    {
      "user_id": uid,
      "ts": firestore.SERVER_TIMESTAMP,
      "delta": NEW_USER_BONUS,
      "reason": "bonus:new_user",
    }
  )
  data["credits"] = NEW_USER_BONUS
  return data


def _check_rate(uid: str) -> None:
  now = time.time()
  if now - _last_call.get(uid, 0) < RATE_LIMIT_S:
    raise HTTPException(429, "too fast, wait a moment")
  _last_call[uid] = now


def _extract_text(filename: str, data: bytes) -> tuple[str, str]:
  name = filename.lower()
  if name.endswith((".xlsx", ".xls")):
    import openpyxl

    wb = openpyxl.load_workbook(
      io.BytesIO(data), read_only=True, data_only=True
    )
    parts = []
    for ws in wb.worksheets:
      parts.append(f"[sheet: {ws.title}]")
      for row in ws.iter_rows(values_only=True):
        parts.append(
          " | ".join("" if c is None else str(c) for c in row).rstrip(" |")
        )
    return "\n".join(parts)[:MAX_TEXT_CHARS], "xlsx"
  if name.endswith(".pdf"):
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    text = "\n".join((p.extract_text() or "") for p in reader.pages)
    return text[:MAX_TEXT_CHARS], "pdf"
  if name.endswith(".docx"):
    import docx

    doc = docx.Document(io.BytesIO(data))
    return "\n".join(p.text for p in doc.paragraphs)[:MAX_TEXT_CHARS], "docx"
  if name.endswith((".csv", ".txt", ".md")):
    return data.decode("utf-8-sig", errors="replace")[:MAX_TEXT_CHARS], "text"
  raise HTTPException(400, f"unsupported file type: {filename}")


@app.get("/healthz")
def healthz():
  return {"ok": True}


@app.get("/")
def index():
  return FileResponse(Path(__file__).parent / "static" / "index.html")


@app.get("/admin")
def admin_page():
  return FileResponse(Path(__file__).parent / "static" / "admin.html")


@app.get("/logo.svg")
def logo():
  return FileResponse(
    Path(__file__).parent / "static" / "logo.svg", media_type="image/svg+xml"
  )


@app.get("/me")
def me(authorization: str | None = Header(default=None)):
  claims = _verify(authorization)
  user = _get_or_create_user(claims["uid"], claims.get("email"))
  return {
    "uid": claims["uid"],
    "email": claims.get("email"),
    "credits": user.get("credits", 0),
    "consent_ts": user.get("consent_ts"),
  }


@app.post("/consent")
def consent(authorization: str | None = Header(default=None)):
  claims = _verify(authorization)
  _get_or_create_user(claims["uid"], claims.get("email"))
  _user_ref(claims["uid"]).update({"consent_ts": firestore.SERVER_TIMESTAMP})
  return {"ok": True}


def _grant_credits(uid: str, credits: int, reason: str) -> int:
  """Add credits to a user (transactional) + ledger entry. Returns new balance."""

  @firestore.transactional
  def _txn(txn):
    ref = _user_ref(uid)
    snap = ref.get(transaction=txn)
    bal = (snap.to_dict() or {}).get("credits", 0) if snap.exists else 0
    txn.set(
      ref,
      {"credits": bal + credits, "consent_ts": None}
      if not snap.exists
      else {"credits": bal + credits},
      merge=True,
    )
    txn.set(
      db.collection("credits_ledger").document(),
      {
        "user_id": uid,
        "ts": firestore.SERVER_TIMESTAMP,
        "delta": credits,
        "reason": reason,
      },
    )
    return bal + credits

  return _txn(db.transaction())


def _payment_exists(session_id: str) -> bool:
  return db.collection("payments").document(session_id).get().exists


def _record_payment(session_id: str, data: dict) -> None:
  data = dict(data)
  data["ts"] = firestore.SERVER_TIMESTAMP
  db.collection("payments").document(session_id).set(data)


def _collection_docs(name: str) -> list[dict]:
  return [d.to_dict() or {} for d in db.collection(name).stream()]


@app.get("/admin/stats")
def stats(x_admin_key: str = Header(default="")):
  if x_admin_key != ADMIN_KEY:
    raise HTTPException(403, "bad admin key")
  users = _collection_docs("users")
  payments = _collection_docs("payments")
  # Exclude P0 cost-measurement probes (user_id "measure-*") from prod stats.
  usage = [
    u
    for u in _collection_docs("usage_logs")
    if not str(u.get("user_id", "")).startswith("measure-")
  ]
  ok = [p for p in payments if p.get("status") == "succeeded"]
  live = [p for p in ok if p.get("livemode")]
  return {
    "users": len(users),
    "credits_outstanding": sum(u.get("credits", 0) for u in users),
    "payments_succeeded": len(ok),
    "payments_failed": len(payments) - len(ok),
    "revenue_thb": round(sum(p.get("amount_thb", 0) for p in ok), 2),
    "revenue_live_thb": round(sum(p.get("amount_thb", 0) for p in live), 2),
    "credits_sold": sum(p.get("credits", 0) for p in ok),
    "queries": len(usage),
    "est_cost_usd": round(sum(u.get("est_cost_usd", 0) for u in usage), 4),
    "grounding_calls": sum(u.get("grounding_calls", 0) for u in usage),
  }


@app.post("/admin/grant")
def grant(body: GrantIn, x_admin_key: str = Header(default="")):
  if x_admin_key != ADMIN_KEY:
    raise HTTPException(403, "bad admin key")
  if body.credits <= 0:
    raise HTTPException(400, "credits must be positive")
  return {"uid": body.uid, "credits": _grant_credits(body.uid, body.credits, "topup:admin")}


class CheckoutIn(BaseModel):
  price_id: str


@app.get("/billing/packages")
def packages():
  return {
    "packages": [
      {"price_id": pid, **info} for pid, info in STRIPE_PRICES.items()
    ]
  }


@app.post("/billing/checkout")
def checkout(body: CheckoutIn, authorization: str | None = Header(default=None)):
  claims = _verify(authorization)
  uid = claims["uid"]
  if body.price_id not in STRIPE_PRICES:
    raise HTTPException(400, "unknown price_id")
  if not STRIPE_SECRET_KEY:
    raise HTTPException(500, "stripe not configured")
  stripe.api_key = STRIPE_SECRET_KEY
  info = STRIPE_PRICES[body.price_id]
  try:
    session = stripe.checkout.Session.create(
      mode="payment",
      payment_method_types=["card", "promptpay"],
      line_items=[{"price": body.price_id, "quantity": 1}],
      metadata={"uid": uid, "credits": info["credits"], "price_id": body.price_id},
      success_url=f"{APP_URL}/?topup=success&thb={info['thb']}",
      cancel_url=f"{APP_URL}/?topup=cancel",
    )
  except Exception as e:
    raise HTTPException(502, f"stripe error: {e}")
  return {"url": session.url}


def _handle_completed_session(sess) -> dict:
  """Grant credits for a checkout.session.completed object (idempotent)."""
  if hasattr(sess, "to_dict"):  # stripe-python resource -> plain dict
    sess = sess.to_dict()
  session_id = sess["id"]
  if _payment_exists(session_id):
    return {"duplicate": True}
  meta = sess.get("metadata") or {}
  uid = meta.get("uid")
  try:
    credits = int(meta.get("credits", 0))
  except (TypeError, ValueError):
    credits = 0
  live = bool(sess.get("livemode", False))
  if sess.get("payment_status") != "paid" or not uid or credits <= 0:
    _record_payment(
      session_id,
      {
        "user_id": uid,
        "provider": "stripe",
        "livemode": live,
        "amount_thb": (sess.get("amount_total") or 0) / 100,
        "credits": 0,
        "status": "failed",
        "reason": "unpaid_or_missing_metadata",
      },
    )
    return {"granted": False}
  balance = _grant_credits(uid, credits, f"topup:stripe:{session_id}")
  _record_payment(
    session_id,
    {
      "user_id": uid,
      "provider": "stripe",
      "livemode": live,
      "amount_thb": (sess.get("amount_total") or 0) / 100,
      "credits": credits,
      "status": "succeeded",
    },
  )
  return {"granted": True, "uid": uid, "credits": credits, "balance": balance}


@app.post("/billing/webhook")
async def billing_webhook(request: Request):
  payload = await request.body()
  sig = request.headers.get("stripe-signature", "")
  if not STRIPE_WEBHOOK_SECRET:
    raise HTTPException(500, "webhook not configured")
  try:
    event = stripe.Webhook.construct_event(payload, sig, STRIPE_WEBHOOK_SECRET)
  except Exception:
    raise HTTPException(400, "bad signature")
  # PromptPay pays asynchronously: succeeded arrives via async_payment_succeeded,
  # failed via async_payment_failed (payment_status != paid -> recorded failed).
  if event["type"] in (
    "checkout.session.completed",
    "checkout.session.async_payment_succeeded",
    "checkout.session.async_payment_failed",
  ):
    _handle_completed_session(event["data"]["object"])
  return {"received": True}


def _normalize_question(text: str) -> str:
  return " ".join(text.strip().lower().split())


def _cache_key(normalized: str) -> str:
  raw = f"{CACHE_VERSION}:{normalized}".encode("utf-8")
  return hashlib.sha256(raw).hexdigest()


def _cache_get(key: str) -> dict | None:
  """Return cached {"answer", "usage"} if fresh, else None. Fails open."""
  try:
    snap = db.collection("answer_cache").document(key).get()
  except Exception:
    return None
  if not snap.exists:
    return None
  data = snap.to_dict() or {}
  if not data.get("answer"):
    return None
  if time.time() - data.get("ts", 0) > CACHE_TTL_S:
    return None
  return data


def _cache_put(key: str, answer: str, usage: dict) -> None:
  try:
    db.collection("answer_cache").document(key).set(
      {"answer": answer, "usage": usage, "ts": time.time()}
    )
  except Exception:
    pass


def _accumulate_usage(event, acc: dict) -> None:
  um = getattr(event, "usage_metadata", None)
  if um is not None:
    acc["prompt"] += getattr(um, "prompt_token_count", 0) or 0
    acc["cand"] += getattr(um, "candidates_token_count", 0) or 0
    acc["think"] += getattr(um, "thoughts_token_count", 0) or 0
  if getattr(event, "grounding_metadata", None) is not None:
    acc["grounding"] += 1


def _event_texts(event) -> list[str]:
  out: list[str] = []
  content = getattr(event, "content", None)
  if content is not None:
    for part in getattr(content, "parts", []) or []:
      if getattr(part, "text", None):
        out.append(part.text)
  return out


def _usage_dict(acc: dict, latency: float) -> dict:
  est_cost = (
    acc["prompt"] / 1e6 * IN_PER_1M
    + (acc["cand"] + acc["think"]) / 1e6 * OUT_PER_1M
    + acc["grounding"] / 1000 * GROUND_PER_1K
  )
  return {
    "prompt_tokens": acc["prompt"],
    "candidates_tokens": acc["cand"],
    "thoughts_tokens": acc["think"],
    "grounding_calls": acc["grounding"],
    "latency_s": round(latency, 1),
    "est_cost_usd": round(est_cost, 4),
  }


def _charge_and_log(uid, sid, message, answer, usage, attachment, cached=False):
  """Deduct flat-rate credits + write ledger/usage rows. Returns balance/None."""
  usage_ref = db.collection("usage_logs").document()
  ledger_ref = db.collection("credits_ledger").document()

  @firestore.transactional
  def _txn(txn):
    ref = _user_ref(uid)
    snap = ref.get(transaction=txn)
    bal = (snap.to_dict() or {}).get("credits", 0)
    if bal < CREDITS_PER_QUERY:
      return None
    txn.update(ref, {"credits": bal - CREDITS_PER_QUERY})
    txn.set(
      ledger_ref,
      {
        "user_id": uid,
        "ts": firestore.SERVER_TIMESTAMP,
        "delta": -CREDITS_PER_QUERY,
        "reason": f"chat:{usage_ref.id}",
      },
    )
    txn.set(
      usage_ref,
      {
        "user_id": uid,
        "ts": firestore.SERVER_TIMESTAMP,
        "session_id": sid,
        "question": message,
        "answer_chars": len(answer),
        "prompt_tokens": usage["prompt_tokens"],
        "candidates_tokens": usage["candidates_tokens"],
        "thoughts_tokens": usage["thoughts_tokens"],
        "grounding_calls": usage["grounding_calls"],
        "latency_s": usage["latency_s"],
        "est_cost_usd": usage["est_cost_usd"],
        "cached": cached,
        "attachment": attachment,
      },
    )
    return bal - CREDITS_PER_QUERY

  return _txn(db.transaction())


def _sse(payload_event: str, payload: dict) -> str:
  return f"event: {payload_event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def _chat_once_payload(uid, sid, msg, cache_key):
  """Run the agent to completion; returns (raw_answer, usage)."""
  t0 = time.time()
  acc = {"prompt": 0, "cand": 0, "think": 0, "grounding": 0}
  texts: list[str] = []
  async for event in runner.run_async(
    user_id=uid, session_id=sid, new_message=msg, run_config=_STREAM_CONFIG
  ):
    _accumulate_usage(event, acc)
    if not getattr(event, "partial", False):
      texts.extend(_event_texts(event))
  latency = time.time() - t0
  answer = "".join(texts)
  usage = _usage_dict(acc, latency)
  if cache_key:
    _cache_put(cache_key, answer, usage)
  return answer, usage


async def _chat_sse_gen(uid, sid, message, msg, attachment, cache_key):
  # Immediate sign of life: the model searches official sources before
  # the first token arrives, so tell the client what is happening.
  yield _sse("stage", {"text": "กำลังค้นข้อมูลจากแหล่งทางการ…"})
  t0 = time.time()
  acc = {"prompt": 0, "cand": 0, "think": 0, "grounding": 0}
  texts: list[str] = []
  try:
    async for event in runner.run_async(
      user_id=uid, session_id=sid, new_message=msg, run_config=_STREAM_CONFIG
    ):
      _accumulate_usage(event, acc)
      for text in _event_texts(event):
        if getattr(event, "partial", False):
          yield _sse("token", {"text": text})
        else:
          texts.append(text)
  except Exception as e:
    yield _sse("error", {"error": str(e)[:200]})
    return
  latency = time.time() - t0
  answer = "".join(texts)
  usage = _usage_dict(acc, latency)
  if cache_key:
    _cache_put(cache_key, answer, usage)
  full = answer + FOOTER
  remaining = _charge_and_log(uid, sid, message, full, usage, attachment)
  if remaining is None:
    yield _sse("error", {"error": "insufficient_credits"})
    return
  yield _sse(
    "done",
    {
      "answer": full,
      "session_id": sid,
      "credits_left": remaining,
      "usage": usage,
    },
  )


@app.post("/chat")
async def chat(
  message: str = Form(...),
  session_id: str | None = Form(default=None),
  file: UploadFile | None = File(default=None),
  authorization: str | None = Header(default=None),
  accept: str | None = Header(default=None),
):
  claims = _verify(authorization)
  uid = claims["uid"]
  user = _get_or_create_user(uid, claims.get("email"))
  if not user.get("consent_ts"):
    raise HTTPException(403, "consent_required")
  _check_rate(uid)
  if user.get("credits", 0) < CREDITS_PER_QUERY:
    raise HTTPException(402, "insufficient_credits")

  parts: list = []
  attachment = None
  text = message
  if file is not None and file.filename:
    data = await file.read()
    if len(data) > MAX_FILE_MB * 1024 * 1024:
      raise HTTPException(400, f"file too large (max {MAX_FILE_MB}MB)")
    mime = file.content_type or ""
    if mime.startswith("image/"):
      parts.append(genai_types.Part.from_bytes(data=data, mime_type=mime))
      attachment = {
        "name": file.filename,
        "size": len(data),
        "kind": "image",
      }
    else:
      extracted, kind = _extract_text(file.filename, data)
      text = (
        f"[ไฟล์แนบ {file.filename}]\n{extracted}\n\n[คำถาม]\n{message}"
      )
      attachment = {
        "name": file.filename,
        "size": len(data),
        "kind": kind,
      }
  parts.append(genai_types.Part(text=text))

  sid = session_id or f"web-{uuid.uuid4().hex[:12]}"
  try:
    sess = await session_service.get_session(
      app_name=APP_NAME, user_id=uid, session_id=sid
    )
  except Exception:
    sess = None
  if sess is None:
    await session_service.create_session(
      app_name=APP_NAME, user_id=uid, session_id=sid
    )

  msg = genai_types.Content(role="user", parts=parts)
  wants_sse = bool(accept and "text/event-stream" in accept)

  # Instant path: text-only repeats are served from cache (still charged).
  cache_key = _cache_key(_normalize_question(text)) if attachment is None else None
  if cache_key:
    hit = _cache_get(cache_key)
    if hit is not None:
      full = hit["answer"] + FOOTER
      usage = {
        "prompt_tokens": 0,
        "candidates_tokens": 0,
        "thoughts_tokens": 0,
        "grounding_calls": 0,
        "latency_s": 0.0,
        "est_cost_usd": 0.0,
        "cached": True,
      }
      remaining = _charge_and_log(
        uid, sid, message, full, usage, attachment, cached=True
      )
      if remaining is None:
        raise HTTPException(402, "insufficient_credits")
      payload = {
        "answer": full,
        "session_id": sid,
        "credits_left": remaining,
        "usage": usage,
      }
      if wants_sse:

        async def _done_only():
          yield _sse("done", payload)

        return StreamingResponse(_done_only(), media_type="text/event-stream")
      return payload

  if wants_sse:
    return StreamingResponse(
      _chat_sse_gen(uid, sid, message, msg, attachment, cache_key),
      media_type="text/event-stream",
      headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

  raw, usage = await _chat_once_payload(uid, sid, msg, cache_key)
  full = raw + FOOTER
  remaining = _charge_and_log(uid, sid, message, full, usage, attachment)
  if remaining is None:
    raise HTTPException(402, "insufficient_credits")

  return {
    "answer": full,
    "session_id": sid,
    "credits_left": remaining,
    "usage": usage,
  }
