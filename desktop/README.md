# โปรแกรมติดตั้ง ThaiCustoms (Windows + Mac)

โปรแกรมนี้เป็น **ไอคอนบนเครื่อง** — กดแล้วเปิดเว็บ
<https://gateway-1008099094873.asia-southeast1.run.app>
ในเบราว์เซอร์ของผู้ใช้ ตัวเว็บ/ระบบเครดิต/จ่ายเงินทำงานเหมือนเดิมทุกอย่าง

## ไฟล์ในโฟลเดอร์นี้

| ไฟล์ | ใช้ทำอะไร |
|---|---|
| `assets/logo-1024.png` + `logo.ico` | ไอคอนโปรแกรม (เรนเดอร์จาก `gateway/static/logo.svg`) |
| `assets/make-icons.py` | สคริปต์สร้างไอคอนใหม่ถ้าเปลี่ยนโลโก้ |
| `windows/installer.iss` | สคริปต์ Inno Setup → ได้ไฟล์ `ThaiCustoms-Setup-<ver>-win64.exe` |
| `macos/build-dmg.sh` | สคริปต์สร้าง `ThaiCustoms.app` + `ThaiCustoms-<ver>-mac.dmg` |
| `../.github/workflows/desktop.yml` | GitHub Actions สร้างไฟล์ติดตั้ง 2 ระบบอัตโนมัติ |

ถ้า URL เว็บเปลี่ยน ต้องแก้ 2 ที่: `windows/installer.iss` (`AppURL`)
กับ `macos/build-dmg.sh` (`APP_URL`)

## วิธีสั่งสร้างไฟล์ติดตั้ง

**แบบที่ 1 — ติด tag (ได้ Release พร้อมไฟล์แนบ):**

```powershell
git tag desktop-v1.0.0
git push origin desktop-v1.0.0
```

แล้วโหลดไฟล์ได้ที่หน้า GitHub → Releases

**แบบที่ 2 — กดปุ่ม (ไม่สร้าง Release):**
เข้า GitHub → Actions → `desktop-installers` → Run workflow → ใส่เลขเวอร์ชัน
แล้วโหลดจาก Artifacts

## วิธีติดตั้ง (สำหรับคนรับไฟล์)

**Windows:** ดับเบิลคลิกไฟล์ `ThaiCustoms-Setup-*.exe` → ติดตั้งแบบไม่ต้องเป็นแอดมิน
→ ได้ไอคอนใน Start Menu (+ Desktop ถ้าติ๊กไว้)

**Mac:** เปิดไฟล์ `.dmg` → ลากแอปลงโฟลเดอร์ Applications → เปิดจาก Launchpad

## หน้าจอเตือนครั้งแรก (ปกติ เพราะยังไม่เซ็นลายเซ็น)

- **Windows SmartScreen:** ขึ้น "Unknown publisher" → กด `More info` → `Run anyway`
- **Mac Gatekeeper:** ขึ้นว่าไม่สามารถยืนยันผู้พัฒนาได้ → **คลิกขวาที่แอป → Open**
  → กด Open อีกครั้ง (ทำครั้งเดียว ครั้งต่อไปเปิดปกติ)

ถ้าวันหลังอยากให้ไม่มีจอนี้เลย ต้องซื้อใบรับรอง (Code Signing) ทั้ง 2 ฝั่ง
