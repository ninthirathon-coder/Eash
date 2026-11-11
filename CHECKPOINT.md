# Checkpoint: ก่อนเริ่ม EA แบบ Top-down (2026-11-10)

Commit checkpoint: `fc492b3` บน branch `claude/intelligent-pasteur-f8c6jd`
ย้อนกลับมาจุดนี้: `git checkout fc492b3` (หรือดูไฟล์ ณ จุดนี้: `git show fc492b3:<path>`)

## สิ่งที่มีแล้ว
| ส่วน | ไฟล์ |
|---|---|
| EA ตัวเดิม (ตัดสินใจบน M5) | `MQL5/Experts/ICT_Candle_EA.mq5` + `README_ICT_Candle_EA.md` |
| ข้อมูล XAUUSD M1 2009-2026 (HistData, เวลา NY+7) | `data/xauusd/` |
| Backtest EA ตัวเดิม (M5) | `backtest/sim.py`, `backtest/run.py` |
| Backtest แบบ Top-down (M1) | `backtest/sim_m1.py`, `backtest/run_m1.py` |
| วิเคราะห์จุดผิดพลาด + รูป | `backtest/ana.py`, `backtest/plots.py`, `backtest/errors/` |

## ผลทุกแนวทาง (XAUUSD 2009-2026, spread $0.30, เสี่ยง 1%/ไม้)
| แนวทาง | ไม้ | เฉลี่ย/ไม้ | t |
|---|---|---|---|
| EA เดิม: Limit ที่ FVG | 544 | -0.155R | -3.4 |
| + รอ PA ที่ sweep และใน FVG | 135 | -0.073R | -0.8 |
| + Multi-TF sweep M5→M15→M30→H1→H4 (ค่าเริ่มต้นของ EA เดิมตอนนี้) | 172 | +0.022R | 0.3 |
| + เพิ่มขั้น M1 | 392 | -0.177R | -3.3 |
| Top-down: โซน H1/H4/PDH/PDL → ยืนยันบน M1, SL ไส้ M1, TP 2R | 170 | -0.061R | -0.7 |
| Top-down + SL พ้นโซน 1.5 ATR, TP 2R | 167 | +0.099R | 1.2 |
| **Top-down + SL พ้นโซน 1.5 ATR, TP swing ก่อนกลับตัว (RR ≥ 0.8)** | 94 | **+0.139R** | 1.3 |

## สิ่งที่เรียนรู้
1. Liquidity เล็ก (swing M5/M1) = noise ยิ่งเล็กยิ่งแพ้
2. ต้องรอ PA ก่อนเข้า Limit ล้วนโดนราคาพุ่งทะลุ
3. SL ที่ไส้ M1 แคบเกินไป วาง SL พ้นโซน TF ใหญ่ ~1.25-2 ATR ดีขึ้นต่อเนื่อง
4. TP แบบ ICT (swing ก่อนจุดกลับตัว) ทำให้ RR ต่ำ (~1.2-1.5) แต่ win rate สูงขึ้น
5. ยังไม่มีชุดไหนมีนัยสำคัญทางสถิติ (t < 2) และค่าที่ดีที่สุดถูกเลือกหลังเห็นผล

## ขั้นต่อไป
- [x] เขียน EA ตัวใหม่ `MQL5/Experts/ICT_TopDown_EA.mq5` ตามแนวทาง Top-down (ค่าตามแถวตัวหนา) — ดู `MQL5/Experts/README_ICT_TopDown_EA.md`
- [ ] Compile + Strategy Tester ด้วยข้อมูลโบรก (ยังไม่ได้: รันตัวติดตั้ง MT5 ใน Wine ไม่ได้รับอนุญาตในเครื่องคลาวด์)
- [x] Walk-forward + ทดสอบตลาดอื่น (ดูหัวข้อด้านล่าง)
- [ ] Forward test บนเดโม

## Walk-forward และตลาดอื่น (`backtest/wf.py`)
15 ชุดค่า (SL: ไส้ M1 / พ้นโซน 1.0-2.0 ATR × TP: 2R / swing RR≥0.8 / swing RR≥1.0)
in-sample = ถึงปี 2017, out-of-sample = 2018 ขึ้นไป, spread เป็น % ของราคา

| ตลาด | ชุดที่ดีสุดช่วงแรก → ผลช่วงหลัง | OOS เป็นบวก | ค่า EA (SL 1.5, swing RR≥0.8) ทั้งช่วง |
|---|---|---|---|
| XAUUSD 2009-2026 | +0.167R → +0.012R | 9/15 | 94 ไม้, +0.139R |
| EURUSD 2010-2025 | +0.175R → -0.221R | 0/15 | 120 ไม้, -0.095R |
| NAS100 2010-2025 | +0.271R → +0.482R (14 ไม้) | 10/15 | 58 ไม้, +0.083R |

สรุป: SL พ้นโซนดีกว่า SL ไส้ M1 บนทองและ NAS100 แต่ใช้ไม่ได้กับ EURUSD; ค่าที่ดีสุดในช่วงแรกไม่การันตีช่วงหลัง; ไม้น้อยเกินจะสรุปว่ามี edge

## ตัดสินใจ: เทรดเฉพาะทองคำ
EA ทั้งสองตัวล็อกให้ทำงานเฉพาะสัญลักษณ์ทอง (ชื่อมี XAU หรือ GOLD) ไม่เทรดสินทรัพย์อื่น

## ICT_TopDown_EA v1.10
ไม่เทรดวันจันทร์ + รอ PA ใน FVG ≤ 10 แท่ง (ผ่านเกณฑ์ดีขึ้นทั้งปีคี่/ปีคู่) → 69 ไม้ +0.234R t=1.8 (v1.00: 94 ไม้ +0.139R)

## ICT_TopDown_EA v1.20 (ไอเดียจาก PDF)
ทดสอบ 8 ไอเดียจาก PDF ผ่าน 1 ข้อ: TP1 = swing (ปิด 50% + กันทุน), TP2 = ขอบ dealing range → 69 ไม้ +0.276R t=1.9

## ICT_TopDown_EA v1.30
เพิ่มตามที่ผู้ใช้กำหนด: แท่ง MSS ต้องมี tick volume > ค่าเฉลี่ย 50 แท่ง — ยังไม่ได้ backtest (HistData ไม่มี volume) ต้องใช้ข้อมูล M1 จากโบรกที่มี tick volume

## ICT_TopDown_EA v1.31
เพดาน SL = 2.5 ATR ของ TF โซน (ผู้ใช้เลือก) → backtest (ไม่รวมตัวกรอง volume) 66 ไม้ +0.246R +15.1% DD -3.9%

## สถานะล่าสุด (ก่อนปิดเครื่อง)
- EA ตัวหลัก: `MQL5/Experts/ICT_TopDown_EA.mq5` v1.31 (ยังไม่ได้ compile)
- Visual trade: https://claude.ai/artifact/QyN9pidGgvx8KJPESGUHtE
- **หน้าวงจุดที่ต้องแก้: https://claude.ai/artifact/DtyuUWFtK6mYLNvW3LaQZb** — วง/โน้ตเก็บใน db ของหน้า (collection `marks`, `notes`)
  เซสชันใหม่อ่านได้ด้วย ArtifactData `list` collection `marks` และ `notes` ที่ URL นี้
- งานถัดไป: อ่านวง/โน้ต → backtest กฎที่ผู้ใช้ต้องการ → แก้ EA → ส่งไฟล์ .mq5

## เริ่มต่อในเครื่องใหม่
```bash
pip install numpy pandas numba matplotlib
cd backtest && mkdir -p raw csv && bash download/dl_xauusd.sh    # (แก้ปีในสคริปต์: 2009-2025 + เดือนของปีปัจจุบัน)
for z in raw/*.zip; do unzip -oq $z -d csv/; done
python3 prep.py .                    # -> data.npz
python3 -c "from run_m1 import *; print(stats(go(slMode=1,slK=1.5,filtM1=1,tpMode=2,minRR=0.8,tpS=2,dowMask=30,paWait=10,tp2=1,maxSLzone=2.5)))"
# ควรได้ 66 ไม้ avgR +0.246 (v1.31)
```
`run_m1.py` ต้องมีข้อมูลโลหะเงินด้วย (`AG_DIR`, ใช้กับ SMT): โหลดด้วย `download/dl_xagusd.sh` แล้ว `prep.py` ในโฟลเดอร์นั้น

## ICT_TopDown_EA v1.40
เพิ่มตัวเลือก SL ชิดไส้ (TD_SL_WICK) และ TP แบบ swing H1 แรกที่ RR ถึง / liquidity ฝั่งตรงข้าม ค่าเริ่มต้นยังเป็น v1.31
SL ไส้ 1 ATR M1 + RR3: 117 ไม้ +0.254R +31% DD -12.8% (ปี 2021-23 ติดลบ) เทียบ v1.31 66 ไม้ +0.246R +15% DD -3.9%
