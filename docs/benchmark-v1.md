# Benchmark v1 — accuracy/speed scorecard (2026-10-12)

Ground truth from official Thai Customs ITD master files
(`Soe-Moe/thai-customs-tariff-json`, built 2026-10-12, HS 2022 base).
Re-run the 5 questions on any system, grade with the rubric below.

## Questions + ground truth

| # | Question (TH) | HS (AHTN 8-digit) | MFN/WTO rate |
|---|---|---|---|
| Q1 | นำเข้าเสื้อยืดผ้าฝ้าย 100% แบบถัก จากจีน เสียอากรเท่าไหร่ | 6109.10.10 / .20 (ชาย/หญิง) | 30% |
| Q2 | นำเข้าลำโพงบลูทูธพกพาจากจีน เสียอากรเท่าไหร่ | 8518.21.10 (box) / .90 | 10% |
| Q3 | นำเข้ารองเท้าผ้าใบพื้นยางจากจีน ต้องเสียภาษีเท่าไหร่ | 6404.11.90 (กีฬา) / 6404.19.90 (ลำลอง) | 30% |
| Q4 | นำเข้ากาแฟคั่วบดจากจีน เสียอากรเท่าไหร่ | 0901.21.20 | WTO 90% |
| Q5 | นำเข้าสมาร์ทโฟนจากจีน เสียอากรเท่าไหร่ | 8517.13.00 | 0% (ยกเว้น) |

## Rubric (per question, 5 pts)

- HS code exact (8-digit): 2 (right 6-digit family only: 1, none/wrong: 0)
- Headline duty rate exact: 2 (range containing truth: 1, missing/wrong: 0)
- Cited checkable sources + disclaimer: 1 (partial: 0.5)

## Our scores (2026-10-12, flash single-agent + prompt budget)

| # | HS | Rate | Src+disc | Total | Latency | Queries |
|---|---|---|---|---|---|---|
| Q1 | 0 (ถามกลับ, ไม่ให้พิกัด) | 1 (~30% แบบ hedged) | 0 (ไม่มีอ้างอิง/disclaimer) | 1 | 15.0s | 4 |
| Q2 | 1 (8518.22.90 — สมมติ 2 ดอก ไมได้ถาม) | 1 ("0-10%") | 0.5 (อ้างอิงกลางๆ + disclaimer) | 2.5 | 33.3s | 7 |
| Q3 | 2 (ให้ทั้ง .11/.19 ถูก) | 1 ("10-30%") | 0.5 (อ้าง blog + disclaimer) | 3.5 | 32.1s | 11 |
| Q4 | 2 (0901.21.20 ตรง) | 0 (หา MFN 90% ไม่เจอ) | 0.5 ([n] ไม่มีรายการอ้างอิง + disclaimer) | 2.5 | 25.2s | 13 |
| Q5 | 2 (8517.13.00 ตรง) | 2 (0% + เหตุผล ITA) | 0.5 (มีแต่ title ไม่มี URL ทางการ + disclaimer) | 4.5 | 19.8s | 4 |
| **รวม** | | | | **14/25** | เฉลี่ย ~25s | |

## Competitor (customsai.co) — fill in by pasting their answers

| # | HS | Rate | Src+disc | Total | Latency |
|---|---|---|---|---|---|
| Q1–Q5 | ? | ? | ? | ? | เคลม 5s (ยังไม่พิสูจน์) |

## Our scores AFTER accuracy sprint (2026-10-12, +ITD RAG + verify box)

| # | ผล | Latency | Queries |
|---|---|---|---|
| Q1 เสื้อยืด | 5/5 (.10+.20 คู่, MFN 30, ACFTA 0, RCEP 15 ตรงหมด) | 10.8s | 0 |
| Q2 ลำโพง | 5/5 (.21.10+.22.10 คู่ + RCEP 0/15 ต่างกันถูก) | 20.8s | 2 |
| Q3 ผ้าใบ | 5/5 (.11.90 ตรง, MFN 30, ACFTA 5, RCEP 22.5) | 26.9s | 4 |
| Q4 กาแฟ | 5/5 (.21.20, WTO 90, FTA ไม่พบซื่อสัตย์) | 20.4s | 4 |
| Q5 มือถือ | 5/5 (0% + ITA) | 7.1s | 2 |
| **รวม** | **25/25** (จาก 14/25) | เฉลี่ย ~17s | ลดลงชัด |

Warts ที่เหลือ: โมเดลบางรอบเขียนคำตอบซ้ำ 2 รอบ (2/12 รัน — เติม prompt ห้ามซ้ำแล้ว ยังไม่พิสูจน์), ลิงก์เป็น redirect URL ยาวแต่กดได้จริง.

## Top fixes for accuracy (from this run)

1. ดึงอัตราจาก tariff JSON ทางการแทนการค้น blog (Q4 พลาด 90% ทั้งที่มีในไฟล์)
2. ซ่อม citation [n] ที่ไม่มีรายการอ้างอิง + บังคับลิงก์ทางการ
3. บังคับ disclaimer ทุกคำตอบ (Q1 หลุด)
4. ถามกลับเมื่อกำกวมจริง (Q2 เดา 8518.22) แต่ถ้าตอบได้ให้ตอบเลยอย่าถามเยอะ (Q1)
5. ดักรหัสแต่ง (.00 ที่ไม่มีในฐาน) ด้วยกล่องตรวจท้ายคำตอบ
