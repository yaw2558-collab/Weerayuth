# Tariff data provenance

- File: `tariff_slim.json` (11,414 lines, ~4.5 MB) — slim extract built
  2026-10-12 from Soe-Moe/thai-customs-tariff-json build outputs
  (HS catalog + WTO + FTA + Section 12 + electronic permits).
- Upstream: https://github.com/Soe-Moe/thai-customs-tariff-json (ISC License,
  Copyright (c) 2026 Soe-Moe). ISC permits use/copy/modify/distribute with
  the copyright notice preserved — this file is that notice.
- Underlying data: Thai Customs Department ITD tariff master files
  (REFDRT/REFTRC/REFPRV/REFPMG), HS2022/AHTN2022 base effective 2022-01-01.
- Fields per line: `c` (AHTN 8-digit), `raw`, `th`/`en` descriptions,
  `mfn` (applied general rate %), `mfn_text` (`exempt`/specific-rate note),
  `wto` (WTO bound %), `fta` ({privilege_code: %} — China: ACN=ACFTA/Form E,
  R1C/R1D/R2C/R2D/R3C/R3D=RCEP, TCN=TH-CN), `sec12` (Section 12 reduction %),
  `permit` (controlling agencies).
- Caveats: base year 2022 — rates can change by later notifications; always
  quote as "ตามฐานพิกัดทางการ (ITD) ฉบับ HS2022" and advise Advance Ruling
  for binding results.
