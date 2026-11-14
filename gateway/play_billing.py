"""Google Play Billing verification for VisionAssist credit top-ups.

The Android app sells consumable credit packs via Play Billing, then posts
the purchase token here. We verify it with the Play Developer API and grant
credits (idempotent on orderId, ledger reason "topup:play:<order_id>").

Play product IDs (create these exact IDs in Play Console, one-time products):
  credits_100 / credits_500 / credits_1000  (mirror of the web packs)

JSON in/out:
  GET  /billing/play/products  -> [{product_id, credits, thb}]
  POST /billing/play/verify    {"product_id","purchase_token"} -> {ok, credits, balance}

The app MUST finishTransaction (consume) only after this endpoint answers
ok — an un-acked Play purchase is auto-refunded after 3 days.

Config: PLAY_SERVICE_ACCOUNT_JSON env (service-account key JSON with the
Play Developer API "View financial data" permission). Tests patch
_fetch_play_purchase, so no Google libraries are needed to run them.
"""

import json
import os

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

PLAY_PACKAGE = "com.visionassist.app"
PLAY_PRODUCTS = {
  "credits_100": {"credits": 100, "thb": 100},
  "credits_500": {"credits": 500, "thb": 450},
  "credits_1000": {"credits": 1000, "thb": 800},
}

router = APIRouter(prefix="/billing/play")

_main = None  # gateway.main, set by mount()


class VerifyIn(BaseModel):
  product_id: str
  purchase_token: str


def mount(app) -> None:
  """Attach the play-billing router (call once, from gateway.main)."""
  global _main
  if _main is not None:
    return
  from gateway import main as main_mod
  _main = main_mod
  app.include_router(router)


def _fetch_play_purchase(product_id: str, token: str) -> dict:
  """Query the Play Developer API. Tests patch this seam."""
  raw = os.environ.get("PLAY_SERVICE_ACCOUNT_JSON", "")
  if not raw:
    raise HTTPException(500, "play billing not configured")
  try:
    info = json.loads(raw)
  except ValueError:
    raise HTTPException(500, "play billing misconfigured")
  from google.oauth2 import service_account
  from googleapiclient.discovery import build
  creds = service_account.Credentials.from_service_account_info(
    info, scopes=["https://www.googleapis.com/auth/androidpublisher"]
  )
  svc = build("androidpublisher", "v3", credentials=creds, cache_discovery=False)
  try:
    return (
      svc.purchases()
      .products()
      .get(packageName=PLAY_PACKAGE, productId=product_id, token=token)
      .execute()
    )
  except Exception as e:
    raise HTTPException(502, f"play verify error: {e}")


@router.get("/products")
def play_products():
  return {
    "products": [
      {"product_id": pid, **info} for pid, info in PLAY_PRODUCTS.items()
    ]
  }


@router.post("/verify")
def play_verify(body: VerifyIn, authorization: str | None = Header(default=None)):
  claims = _main._verify(authorization)
  uid = claims["uid"]
  info = PLAY_PRODUCTS.get(body.product_id)
  if info is None:
    raise HTTPException(400, "unknown product_id")
  if not body.purchase_token:
    raise HTTPException(400, "missing purchase_token")
  p = _fetch_play_purchase(body.product_id, body.purchase_token)
  order_id = p.get("orderId")
  if p.get("purchaseState") != 0 or not order_id:
    raise HTTPException(400, "purchase not completed")
  if p.get("productId") and p["productId"] != body.product_id:
    raise HTTPException(400, "product mismatch")
  if _main._payment_exists(order_id):
    user = _main._get_or_create_user(uid, claims.get("email"))
    return {"ok": True, "duplicate": True, "balance": user.get("credits", 0)}
  # purchaseType 0 = license-tester sandbox purchase (kept out of live revenue);
  # absent on real purchases -> counts as live.
  live = p.get("purchaseType", 1) != 0
  balance = _main._grant_credits(uid, info["credits"], f"topup:play:{order_id}")
  _main._record_payment(
    order_id,
    {
      "user_id": uid,
      "provider": "play",
      "livemode": live,
      "amount_thb": info["thb"],
      "credits": info["credits"],
      "status": "succeeded",
    },
  )
  return {"ok": True, "credits": info["credits"], "balance": balance}
