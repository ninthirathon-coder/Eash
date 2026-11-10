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
เขียน EA ตัวใหม่ `MQL5/Experts/ICT_TopDown_EA.mq5` ตามแนวทาง Top-down (ค่าตามแถวตัวหนา) แล้ว forward test บนเดโม
