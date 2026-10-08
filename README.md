# ผู้ช่วยพิกัดศุลกากรไทย (ADK Agent)

Agent ช่วยหาพิกัดอัตราศุลกากรไทย (HS/AHTN) รันด้วย Google ADK + Vertex AI
โมเดล `gemini-3.1-pro-preview` ผ่าน global endpoint

## โครงไฟล์

```
thai-customs/
├── requirements.txt
└── thai_customs_agent/
    ├── __init__.py
    ├── agent.py   # โค้ด agent ทั้งหมด
    └── .env       # project glowing-magnet-330507
```

## วิธีรัน (ครั้งแรก)

```powershell
cd thai-customs
gcloud auth application-default login
gcloud config set project glowing-magnet-330507
.venv\Scripts\adk web
```

(เรียก `adk` ใน venv ตรงๆ ไม่ต้อง activate — ถ้าอยาก activate
แล้วเจอ execution policy ให้รันครั้งเดียว:
`Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`)

แล้วเปิดเบราว์เซอร์ตาม URL ที่ `adk web` แสดง (ปกติ http://localhost:8000)
เลือก agent `thai_customs_agent` แล้วเริ่มแชทได้เลย

(ติดตั้งครั้งแรก: `python -m venv .venv` แล้ว `pip install -r requirements.txt`
ใน venv — ในเครื่องนี้ทำไว้ให้แล้ว)

## วิธีรันแบบ command line

```powershell
cd thai-customs
.venv\Scripts\adk run thai_customs_agent
```

## หมายเหตุ

- ต้องเปิด Vertex AI API ใน project ก่อน
  (`gcloud services enable aiplatform.googleapis.com`)
- ถ้าโมเดล `gemini-3.1-pro-preview` ยังไม่เปิดให้ project นี้
  แล้วเจอ model-not-found ให้เปลี่ยนชื่อโมเดลใน `agent.py`
  เป็นรุ่นที่ project เข้าถึงได้ เช่น `gemini-2.5-pro`
- ถ้า `from google.adk.tools import url_context` import ไม่ผ่าน
  (ขึ้นกับเวอร์ชัน ADK) ให้เปลี่ยนเป็น
  `from google.adk.tools.url_context_tool import UrlContextTool`
  แล้วใช้ `UrlContextTool()` แทน `url_context`
- โมเดล preview อาจคืน 500 INTERNAL เป็นบางคำถาม (เช่น คำถาม
  เครื่องฟอกอากาศ+อากรนำเข้า) ทั้งที่คำถามอื่นทรงเดียวกันผ่าน —
  เป็นบั๊กฝั่ง server ของโมเดล preview ไม่ใช่บั๊กของโค้ดนี้
  ถ้าเจอให้ลองถามใหม่หรือเปลี่ยนสำนวนคำถาม
