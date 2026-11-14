"""VisionAssist endpoints, served from the thai-customs gateway.

Separate product, shared auth/billing: Firebase ID token auth, the PDPA
consent gate, flat-rate credits, and usage_logs rows tagged
feature="vision" (ledger reason "vision:<log_id>") so customs spend stays
separable by query.

JSON in/out (the shape the mobile app speaks):
  POST /vision/describe  {"image": "<base64>"}  -> Thai scene description
  POST /vision/ask       {"question": "..."}    -> Thai answer
  POST /vision/scan      {"image": "<base64>"}  -> {hazard, alert, confidence}

Mounted via mount(app) from the bottom of gateway.main — the deferred
import inside mount() keeps module import order irrelevant.
"""

import base64
import binascii
import json
import time
import uuid

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from google.genai import Client
from google.genai import types as genai_types

VISION_MODEL = "gemini-2.5-flash"  # same model/quota pool as the customs agent
VISION_CREDITS_PER_QUERY = 10  # describe/ask flat rate, same as chat
VISION_SCAN_CREDITS = 1  # scan fires every ~2.5s; 1 credit since 2026-11-14 (was 2)
VISION_RATE_LIMIT_S = 2  # scan cadence (~2.5s) can't survive the 20s chat limit
VISION_MAX_IMAGE_MB = 5
VISION_MAX_QUESTION_CHARS = 2000
VISION_MAX_ALERT_CHARS = 500

router = APIRouter(prefix="/vision")

_vision_last_call: dict[str, float] = {}
_client: Client | None = None
_main = None  # gateway.main, set by mount(); endpoints touch it at request time


class DescribeIn(BaseModel):
  image: str


class AskIn(BaseModel):
  question: str


class ScanIn(BaseModel):
  image: str


def mount(app) -> None:
  """Attach the vision router (call once, from gateway.main)."""
  global _main
  if _main is not None:
    return  # already mounted (import-order independent)
  from gateway import main as main_mod
  _main = main_mod
  app.include_router(router)


def _genai_client() -> Client:
  global _client
  if _client is None:
    _client = Client(vertexai=True, location="global")
  return _client


def _call_model(contents: list, max_output_tokens: int) -> tuple[str, dict]:
  """Single-shot model call. Returns (text, usage). Tests patch this seam."""
  t0 = time.time()
  resp = _genai_client().models.generate_content(
    model=VISION_MODEL,
    contents=contents,
    config=genai_types.GenerateContentConfig(
      max_output_tokens=max_output_tokens
    ),
  )
  text = (resp.text or "").strip()
  if not text:
    raise RuntimeError("empty model response")
  um = resp.usage_metadata
  acc = {
    "prompt": (getattr(um, "prompt_token_count", 0) or 0) if um else 0,
    "cand": (getattr(um, "candidates_token_count", 0) or 0) if um else 0,
    "think": (getattr(um, "thoughts_token_count", 0) or 0) if um else 0,
    "seen": set(),
    "sources": [],
  }
  return text, _main._usage_dict(acc, time.time() - t0)


def _check_vision_rate(uid: str) -> None:
  now = time.time()
  if now - _vision_last_call.get(uid, 0) < VISION_RATE_LIMIT_S:
    raise HTTPException(429, "too fast, wait a moment")
  _vision_last_call[uid] = now


def _preamble(
  authorization: str | None,
  credits: int = VISION_CREDITS_PER_QUERY,
) -> str:
  claims = _main._verify(authorization)
  uid = claims["uid"]
  user = _main._get_or_create_user(uid, claims.get("email"))
  if not user.get("consent_ts"):
    raise HTTPException(403, "consent_required")
  _check_vision_rate(uid)
  if user.get("credits", 0) < credits:
    raise HTTPException(402, "insufficient_credits")
  return uid


def _sniff_mime(data: bytes) -> str | None:
  if data[:3] == b"\xff\xd8\xff":
    return "image/jpeg"
  if data[:4] == b"\x89PNG":
    return "image/png"
  if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
    return "image/webp"
  return None


_MIME_EXT = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}


def _decode_image(image_b64: str) -> tuple[bytes, str]:
  """Base64 (data-URL tolerant) -> (bytes, mime). Raises 400 on any defect."""
  s = (image_b64 or "").strip()
  if s.startswith("data:") and ";base64," in s:
    s = s.split(";base64,", 1)[1]
  try:
    data = base64.b64decode(s, validate=True)
  except (binascii.Error, ValueError):
    raise HTTPException(400, "invalid base64 image")
  if not data:
    raise HTTPException(400, "empty image")
  if len(data) > VISION_MAX_IMAGE_MB * 1024 * 1024:
    raise HTTPException(400, f"image too large (max {VISION_MAX_IMAGE_MB}MB)")
  mime = _sniff_mime(data)
  if mime is None:
    raise HTTPException(400, "unsupported image (use JPEG, PNG or WebP)")
  return data, mime


_DESCRIBE_PROMPT = (
  "Describe what is in front of the camera in Thai, 1-2 short sentences "
  "for a blind pedestrian listening via text-to-speech. Mention obstacles, "
  "stairs, doors, and people in the way first. Plain text only, no markdown."
)

_ASK_DIRECTIVE = "[Answer in Thai, 1-3 short sentences, plain text, no markdown.]"

_SCAN_PROMPT = (
  "You are an obstacle detector for a blind pedestrian. Look at this image "
  "and reply with JSON only, no other text: "
  '{"hazard": true/false, "alert": "short Thai warning or null", '
  '"confidence": 0.0-1.0}. hazard is true only when something blocks the '
  "walking path or is dangerous within a few meters (stairs, drop, vehicle, "
  "person or object in the way, closed door ahead). Otherwise hazard is "
  "false and alert is null."
)


def _parse_scan_json(text: str) -> dict:
  """Strict shape, lenient wrapping (fences tolerated). Raises 502."""
  s = text.strip()
  if s.startswith("```"):
    s = s.strip("`").strip()
    if s[:4].lower() == "json":
      s = s[4:].strip()
  try:
    obj = json.loads(s)
  except (json.JSONDecodeError, ValueError):
    raise HTTPException(502, "scan parse failed")
  if not isinstance(obj, dict):
    raise HTTPException(502, "scan parse failed")
  hazard = obj.get("hazard")
  alert = obj.get("alert")
  conf = obj.get("confidence")
  if not isinstance(hazard, bool):
    raise HTTPException(502, "scan parse failed")
  if alert is not None and not isinstance(alert, str):
    raise HTTPException(502, "scan parse failed")
  if isinstance(conf, bool) or not isinstance(conf, (int, float)):
    raise HTTPException(502, "scan parse failed")
  clean_alert = (alert or "").strip() or None
  if clean_alert:
    clean_alert = clean_alert[:VISION_MAX_ALERT_CHARS]
  return {
    "hazard": hazard,
    "alert": clean_alert,
    "confidence": min(1.0, max(0.0, float(conf))),
  }


def _charge(
  uid: str,
  label: str,
  result: str,
  usage: dict,
  attachment,
  credits: int = VISION_CREDITS_PER_QUERY,
):
  sid = f"vision-{uuid.uuid4().hex[:12]}"
  charged = _main._charge_and_log(
    uid,
    sid,
    label,
    result,
    usage,
    attachment,
    credits=credits,
    reason_prefix="vision",
    extra={"feature": "vision"},
  )
  if charged is None:
    raise HTTPException(402, "insufficient_credits")
  return charged


def _image_attachment(data: bytes, mime: str) -> dict:
  return {
    "name": f"camera.{_MIME_EXT[mime]}",
    "size": len(data),
    "kind": "image",
  }


@router.post("/describe")
def describe(
  body: DescribeIn, authorization: str | None = Header(default=None)
):
  uid = _preamble(authorization, VISION_CREDITS_PER_QUERY)
  data, mime = _decode_image(body.image)
  contents = [
    genai_types.Part.from_bytes(data=data, mime_type=mime),
    genai_types.Part(text=_DESCRIBE_PROMPT),
  ]
  try:
    text, usage = _call_model(contents, 256)
  except HTTPException:
    raise
  except Exception:
    raise HTTPException(502, "model unavailable")
  remaining, log_id = _charge(
    uid,
    "[vision describe]",
    text,
    usage,
    _image_attachment(data, mime),
    VISION_CREDITS_PER_QUERY,
  )
  return {
    "description": text,
    "credits_left": remaining,
    "log_id": log_id,
    "usage": usage,
  }


@router.post("/ask")
def ask(body: AskIn, authorization: str | None = Header(default=None)):
  uid = _preamble(authorization, VISION_CREDITS_PER_QUERY)
  question = (body.question or "").strip()
  if not question:
    raise HTTPException(400, "question required")
  if len(question) > VISION_MAX_QUESTION_CHARS:
    raise HTTPException(
      400, f"question too long (max {VISION_MAX_QUESTION_CHARS} chars)"
    )
  try:
    text, usage = _call_model(
      [genai_types.Part(text=f"{_ASK_DIRECTIVE}\n\n{question}")], 512
    )
  except HTTPException:
    raise
  except Exception:
    raise HTTPException(502, "model unavailable")
  remaining, log_id = _charge(
    uid, question, text, usage, None, VISION_CREDITS_PER_QUERY
  )
  return {
    "answer": text,
    "credits_left": remaining,
    "log_id": log_id,
    "usage": usage,
  }


@router.post("/scan")
def scan(body: ScanIn, authorization: str | None = Header(default=None)):
  uid = _preamble(authorization, VISION_SCAN_CREDITS)
  data, mime = _decode_image(body.image)
  contents = [
    genai_types.Part.from_bytes(data=data, mime_type=mime),
    genai_types.Part(text=_SCAN_PROMPT),
  ]
  try:
    text, usage = _call_model(contents, 128)
  except HTTPException:
    raise
  except Exception:
    raise HTTPException(502, "model unavailable")
  parsed = _parse_scan_json(text)
  remaining, log_id = _charge(
    uid,
    "[vision scan]",
    json.dumps(parsed, ensure_ascii=False),
    usage,
    _image_attachment(data, mime),
    VISION_SCAN_CREDITS,
  )
  return {
    **parsed,
    "credits_left": remaining,
    "log_id": log_id,
    "usage": usage,
  }