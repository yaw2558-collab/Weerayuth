"""VisionAssist endpoint tests: describe/ask/scan + image + scan parsing.

Seams faked at the boundary: _verify, _get_or_create_user, _call_model,
_charge_and_log. The vision rate bucket resets on every _post (except the
rate test itself, which posts twice on purpose).
Run from thai-customs/: ..\\.venv\\Scripts\\python -m pytest gateway/test_vision.py
"""

import base64
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

import gateway.main as main
import gateway.vision as vision

client = TestClient(main.app)
AUTH = {"Authorization": "Bearer [REDACTED]"}

PNG_1PX = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
JPG_MIN = base64.b64encode(b"\xff\xd8\xff\x00mini").decode()
WEBP_MIN = base64.b64encode(b"RIFF\x00\x00\x00\x00WEBPmini").decode()
GIF_MIN = base64.b64encode(b"GIF89amini").decode()
NOT_IMAGE = base64.b64encode(b"hello world, not an image").decode()

USAGE = {
  "prompt_tokens": 10,
  "candidates_tokens": 5,
  "thoughts_tokens": 0,
  "grounding_calls": 0,
  "latency_s": 0.1,
  "est_cost_usd": 0.0001,
  "capped": False,
  "free": False,
}


def _auth(monkeypatch, credits=30, consent=True):
  monkeypatch.setattr(
    main, "_verify", lambda auth: {"uid": "user1", "email": "u@x.co"}
  )
  user = {"credits": credits}
  if consent:
    user["consent_ts"] = "yes"
  monkeypatch.setattr(main, "_get_or_create_user", lambda uid, email: user)
  vision._vision_last_call.clear()


def _model(monkeypatch, text):
  monkeypatch.setattr(
    vision, "_call_model", lambda contents, maxtok: (text, USAGE)
  )


def _charge_ok(monkeypatch, calls):
  def fake(uid, sid, message, answer, usage, attachment, **kw):
    calls.append(
      {
        "uid": uid,
        "sid": sid,
        "message": message,
        "answer": answer,
        "usage": usage,
        "attachment": attachment,
        "kw": kw,
      }
    )
    return (20, "log1")

  monkeypatch.setattr(main, "_charge_and_log", fake)


def _post(path, payload):
  vision._vision_last_call.clear()
  return client.post(path, json=payload, headers=AUTH)


def test_describe_returns_description_and_charges_vision(monkeypatch):
  _auth(monkeypatch)
  _model(monkeypatch, "ข้างหน้ามีบันได 3 ขั้น")
  calls = []
  _charge_ok(monkeypatch, calls)
  r = _post("/vision/describe", {"image": PNG_1PX})
  assert r.status_code == 200
  d = r.json()
  assert d["description"] == "ข้างหน้ามีบันได 3 ขั้น"
  assert d["credits_left"] == 20
  assert d["log_id"] == "log1"
  assert d["usage"] == USAGE
  assert len(calls) == 1
  c = calls[0]
  assert c["uid"] == "user1"
  assert c["sid"].startswith("vision-")
  assert c["message"] == "[vision describe]"
  assert c["attachment"]["kind"] == "image"
  assert c["attachment"]["name"] == "camera.png"
  assert c["kw"]["credits"] == vision.VISION_CREDITS_PER_QUERY
  assert c["kw"]["reason_prefix"] == "vision"
  assert c["kw"]["extra"] == {"feature": "vision"}


def test_describe_accepts_jpeg_webp_and_data_url(monkeypatch):
  _auth(monkeypatch)
  _model(monkeypatch, "ok")
  calls = []
  _charge_ok(monkeypatch, calls)
  assert _post("/vision/describe", {"image": JPG_MIN}).status_code == 200
  assert _post("/vision/describe", {"image": WEBP_MIN}).status_code == 200
  r = _post(
    "/vision/describe", {"image": "data:image/png;base64," + PNG_1PX}
  )
  assert r.status_code == 200
  assert [c["attachment"]["name"] for c in calls] == [
    "camera.jpg",
    "camera.webp",
    "camera.png",
  ]


def test_describe_rejects_bad_images(monkeypatch):
  _auth(monkeypatch)
  _model(monkeypatch, "unreachable")
  calls = []
  _charge_ok(monkeypatch, calls)
  assert _post("/vision/describe", {"image": "!!!not-base64!!!"}).status_code == 400
  assert _post("/vision/describe", {"image": NOT_IMAGE}).status_code == 400
  assert _post("/vision/describe", {"image": GIF_MIN}).status_code == 400
  assert _post("/vision/describe", {"image": ""}).status_code == 400
  assert _post("/vision/describe", {}).status_code == 422
  assert calls == []  # rejected before any model call or charge


def test_describe_rejects_oversized_image(monkeypatch):
  _auth(monkeypatch)
  _model(monkeypatch, "unreachable")
  monkeypatch.setattr(vision, "VISION_MAX_IMAGE_MB", 0)
  r = _post("/vision/describe", {"image": PNG_1PX})
  assert r.status_code == 400


def test_ask_returns_answer(monkeypatch):
  _auth(monkeypatch)
  _model(monkeypatch, "เป็นป้ายบอกทางออก")
  calls = []
  _charge_ok(monkeypatch, calls)
  r = _post("/vision/ask", {"question": "ป้ายข้างหน้าว่าอะไร"})
  assert r.status_code == 200
  d = r.json()
  assert d["answer"] == "เป็นป้ายบอกทางออก"
  assert d["credits_left"] == 20
  assert calls[0]["message"] == "ป้ายข้างหน้าว่าอะไร"
  assert calls[0]["attachment"] is None


def test_ask_validates_question(monkeypatch):
  _auth(monkeypatch)
  _model(monkeypatch, "unreachable")
  calls = []
  _charge_ok(monkeypatch, calls)
  assert _post("/vision/ask", {"question": ""}).status_code == 400
  assert _post("/vision/ask", {"question": "  "}).status_code == 400
  assert _post("/vision/ask", {"question": "x" * 2001}).status_code == 400
  assert _post("/vision/ask", {}).status_code == 422
  assert calls == []


def test_scan_parses_hazard_json(monkeypatch):
  _auth(monkeypatch)
  _model(
    monkeypatch,
    '{"hazard": true, "alert": "ข้างหน้ามีบันได", "confidence": 0.9}',
  )
  calls = []
  _charge_ok(monkeypatch, calls)
  r = _post("/vision/scan", {"image": PNG_1PX})
  assert r.status_code == 200
  d = r.json()
  assert d["hazard"] is True
  assert d["alert"] == "ข้างหน้ามีบันได"
  assert d["confidence"] == 0.9
  assert d["credits_left"] == 20
  assert json.loads(calls[0]["answer"])["hazard"] is True


def test_scan_tolerates_fences_and_clamps_confidence(monkeypatch):
  _auth(monkeypatch)
  _model(
    monkeypatch,
    '```json\n{"hazard": false, "alert": null, "confidence": 2.5}\n```',
  )
  calls = []
  _charge_ok(monkeypatch, calls)
  r = _post("/vision/scan", {"image": PNG_1PX})
  assert r.status_code == 200
  d = r.json()
  assert d["hazard"] is False
  assert d["alert"] is None
  assert d["confidence"] == 1.0


def test_scan_rejects_malformed_model_output(monkeypatch):
  _auth(monkeypatch)
  calls = []
  _charge_ok(monkeypatch, calls)
  bad = [
    "not json at all",
    "[]",
    '{"hazard": "yes", "alert": null, "confidence": 0.5}',
    '{"hazard": true}',
    '{"hazard": true, "alert": 5, "confidence": 0.5}',
    '{"hazard": false, "alert": null, "confidence": true}',
  ]
  for text in bad:
    _model(monkeypatch, text)
    assert _post("/vision/scan", {"image": PNG_1PX}).status_code == 502
  assert calls == []  # parse failure charges nothing


def test_vision_requires_auth_consent_credits(monkeypatch):
  # no header at all hits the real verifier -> 401 (no Firebase involved)
  assert client.post("/vision/ask", json={"question": "q"}).status_code == 401
  _auth(monkeypatch)

  def _boom(contents, maxtok):
    raise AssertionError("model must not run past a rejected preamble")

  monkeypatch.setattr(vision, "_call_model", _boom)
  _auth(monkeypatch, consent=False)
  assert _post("/vision/ask", {"question": "q"}).status_code == 403
  _auth(monkeypatch, credits=5)
  assert _post("/vision/ask", {"question": "q"}).status_code == 402


def test_vision_rate_limits_per_user(monkeypatch):
  _auth(monkeypatch)
  _model(monkeypatch, "ok")
  calls = []
  _charge_ok(monkeypatch, calls)
  first = client.post("/vision/ask", json={"question": "q1"}, headers=AUTH)
  assert first.status_code == 200
  second = client.post("/vision/ask", json={"question": "q2"}, headers=AUTH)
  assert second.status_code == 429
  assert len(calls) == 1


def test_charge_failure_returns_402(monkeypatch):
  _auth(monkeypatch)
  _model(monkeypatch, "ok")
  monkeypatch.setattr(main, "_charge_and_log", lambda *a, **k: None)
  assert _post("/vision/ask", {"question": "q"}).status_code == 402


def test_model_error_returns_502(monkeypatch):
  _auth(monkeypatch)

  def _fail(contents, maxtok):
    raise RuntimeError("vertex down")

  monkeypatch.setattr(vision, "_call_model", _fail)
  calls = []
  _charge_ok(monkeypatch, calls)
  assert _post("/vision/ask", {"question": "q"}).status_code == 502
  assert calls == []


SCAN_OK = '{"hazard": false, "alert": null, "confidence": 0.8}'


def test_scan_charges_scan_price_not_full_price(monkeypatch):
  _auth(monkeypatch)
  _model(monkeypatch, SCAN_OK)
  calls = []
  _charge_ok(monkeypatch, calls)
  r = _post("/vision/scan", {"image": PNG_1PX})
  assert r.status_code == 200
  assert vision.VISION_SCAN_CREDITS == 1  # decided 2026-11-14: 2/scan drained bonus in ~40s
  assert calls[0]["kw"]["credits"] == vision.VISION_SCAN_CREDITS


def test_ask_keeps_full_price(monkeypatch):
  _auth(monkeypatch)
  _model(monkeypatch, "ok")
  calls = []
  _charge_ok(monkeypatch, calls)
  assert _post("/vision/ask", {"question": "q"}).status_code == 200
  assert calls[0]["kw"]["credits"] == vision.VISION_CREDITS_PER_QUERY
  # describe's full-price assertion lives in
  # test_describe_returns_description_and_charges_vision


def test_scan_preamble_uses_scan_price_threshold(monkeypatch):
  # 5 credits: enough for a 1-credit scan, not for a 10-credit ask
  _auth(monkeypatch, credits=5)
  _model(monkeypatch, SCAN_OK)
  calls = []
  _charge_ok(monkeypatch, calls)
  assert _post("/vision/scan", {"image": PNG_1PX}).status_code == 200
  assert _post("/vision/ask", {"question": "q"}).status_code == 402