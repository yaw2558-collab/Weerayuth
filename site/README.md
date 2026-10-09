# เว็บโชว์สินค้า ซอฟแวร์ดีดี (site/)

เว็บ static หน้าเดียว แนะนำโปรแกรม ThaiCustoms + ลิงก์ไปเว็บแอป ไฟล์ติดตั้ง
คู่มือ และช่องทางติดต่อ แยกจากระบบแชทเพื่อให้แก้เร็วและโฮสต์ฟรีบน GitHub Pages

## ดูตัวอย่างบนเครื่อง

```powershell
cd site
python -m http.server 8080
```

แล้วเปิด http://127.0.0.1:8080 ในเบราว์เซอร์

## Deploy (อัตโนมัติ)

- ตั้งค่าครั้งเดียว: เปิด repo บน GitHub → Settings → Pages → Source เลือก
  **GitHub Actions**
- ทุก push ขึ้นสาขา `gateway` ที่แตะไฟล์ใน `site/` จะ deploy ใหม่เอง
  (workflow `.github/workflows/pages.yml`)
- สั่งเอง: Actions → `deploy-site` → Run workflow

## แก้ไขเมื่อมีของใหม่

| กรณี | แก้ที่ |
|---|---|
| ออกโปรแกรมรุ่นใหม่ | `index.html` ส่วน `#download` (เลขรุ่น + ลิงก์ tag) |
| เปลี่ยนราคา/แพ็กเกจ | `index.html` ส่วน `#pricing` |
| เพิ่มสินค้าตัวที่ 2 | คัดลอก `<article class="product">` ใน `#product` แล้วแก้เนื้อหา |
| เปลี่ยนคู่มือ PDF | ทับไฟล์ใน `site/assets/` (ต้นฉบับอยู่ที่ `docs/`) |
| เปลี่ยน URL เว็บแอป | ค้น `gateway-1008099094873` ใน `index.html` แล้วแทนที่ทั้งหมด |

## หลัง deploy ครั้งแรก

- จด URL จริงของเว็บ (เช่น `https://<owner>.github.io/<repo>/`) แล้วเติม
  Open Graph tags (`og:url`/`og:image` ชี้ `assets/og-logo.png`) ใน `<head>`
  เพื่อให้แชร์ลง LINE/Facebook แล้วมีรูปพรีวิวสวยๆ
