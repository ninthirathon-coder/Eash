# Backtest ICT Candle EA (Python port)

พอร์ตตรรกะของ `MQL5/Experts/ICT_Candle_EA.mq5` มาเป็น Python/numba เพื่อเทสกับข้อมูลยาว

- ตัดสินใจตอนแท่ง M5 ปิด (เหมือน EA), จำลองการเข้า/SL/TP/กันทุน/ปิดบางส่วนบนแท่ง M1
- กติกาแบบระวัง: แท่ง M1 เดียวโดนทั้ง SL และ TP = นับ SL, ไม่ให้ TP ในแท่งที่ Limit เพิ่ง fill
- เวลา "เซิร์ฟเวอร์" = เวลานิวยอร์ก + 7 ชม. (ตรงกับ `InpServerMinusNY = 7`)
- ทองคำ: 1 lot = 100 oz, spread คงที่ $0.30 (ปรับได้)

## ข้อมูล
XAUUSD M1 จาก HistData.com (เวลา EST คงที่ UTC-5) ม.ค. 2016 - พ.ย. 2026
ไฟล์ข้อมูลไม่ได้ commit (ใหญ่) ให้โหลด zip รายปีจาก histdata.com แล้วแตกไว้ที่ `backtest/csv/`

```bash
pip install numpy pandas numba
python3 prep.py backtest        # csv/ -> data.npz
python3 run.py                  # ผลค่าเริ่มต้น + trades_base.csv
```
ใน Python: `from run import go, stats; T,*_ = go(disp=1.5); print(stats(T))`

## ผลค่าเริ่มต้น (XAUUSD M5/H1, ทุน $10,000, เสี่ยง 1%/ไม้)
| ไม้ | Win% | เฉลี่ย R | PF | ผลรวม | Max DD |
|---|---|---|---|---|---|
| 348 | 42.5 | -0.135 | 0.74 | -37.9% | -43.5% |

![equity](equity.png)

## EA แพ้ตรงไหน (`errors/`)
`python3 ana.py` (สร้าง trades_full.pkl) แล้ว `python3 plots.py errors` (ต้องมีฟอนต์ Sarabun ใน `backtest/fonts/` หรือตั้ง `THAI_FONT_DIR`)

| ภาพ | เนื้อหา |
|---|---|
| `0_summary.png` | สรุป 5 จุดผิดพลาด พร้อมตัวเลข |
| `1_fake_sweep_breakout.png` | "Sweep" ที่จริงคือเบรคทะลุ + สวนเทรนด์ H4 |
| `2_instant_fill.png` | ราคาพุ่งทะลุ FVG ทันทีที่ตั้ง Limit |
| `3_slow_mss.png` | MSS เกิดช้าหลัง sweep หลายแท่ง |
| `4_stop_hunt.png` | เคสส่วนน้อย: โดนกวาด SL แล้วกลับไป TP |

## Top-down: โซน TF ใหญ่ → ยืนยันบน M1 (`sim_m1.py`, `run_m1.py`)
โซน = swing H1/H4 ที่ยังไม่ถูกแตะ + PDH/PDL; เมื่อราคาแทงผ่านโซน ไปดู M1: ปิดกลับ, MSS + displacement, FVG, PA ใน FVG แล้วเข้า
`from run_m1 import go, stats; print(stats(go(bias=1)))`

| ชุด | ไม้ | Win% | เฉลี่ย/ไม้ | t |
|---|---|---|---|---|
| A. ไม่ดู M1 (เข้าเมื่อปิดกลับเข้าโซน) | 2128 | 45.1 | -0.083R | -3.6 |
| B. M1 sweep + MSS | 544 | 46.5 | -0.076R | -1.7 |
| C. M1 sweep + MSS + FVG + PA | 170 | 44.7 | -0.061R | -0.7 |

### SL พ้นโซน TF ใหญ่ (`slMode=1, slK=k, filtM1=1`)
setup เดิมทุกไม้ (คัดด้วยโครงสร้าง M1) แต่วาง SL = ระดับโซน ± k × ATR ของ TF โซน (H1 หรือ H4)

| k | ไม้ | Win% | เฉลี่ย/ไม้ | t | SL กลาง |
|---|---|---|---|---|---|
| SL หลังไส้ M1 | 170 | 44.7 | -0.061R | -0.7 | $3.0 |
| 0.5 | 169 | 45.6 | -0.067R | -0.8 | $4.1 |
| 1.0 | 169 | 50.9 | +0.028R | 0.3 | $6.2 |
| 1.5 | 167 | 53.3 | +0.099R | 1.2 | $8.4 |
| 2.0 | 162 | 51.2 | +0.072R | 0.8 | $10.3 |
| 3.0 | 151 | 45.7 | -0.069R | -0.8 | $14.4 |

### TP แบบ ICT: swing ก่อนจุดกลับตัว (`tpMode=2`)
TP = swing high/low ล่าสุดบน TF ของโซน (PDH/PDL ใช้ H1) ก่อนแท่งที่เป็นจุด sweep = ต้นขาที่ลงมากวาดโซน

| ชุด | ไม้ | Win% | เฉลี่ย/ไม้ | t | RR แผน (กลาง) |
|---|---|---|---|---|---|
| SL ไส้ M1, TP 2R | 170 | 44.7 | -0.061R | -0.7 | 2.0 |
| SL ไส้ M1, TP swing | 157 | 44.6 | -0.105R | -1.2 | 2.6 |
| SL พ้นโซน 1.5, TP 2R | 167 | 53.3 | +0.099R | 1.2 | 2.0 |
| SL พ้นโซน 1.5, TP swing (RR ≥ 1) | 69 | 52.2 | +0.090R | 0.7 | 1.5 |
| SL พ้นโซน 1.5, TP swing (RR ≥ 0.8) | 94 | 56.4 | +0.139R | 1.3 | 1.2 |

## ทำไมได้ไม้น้อย (`funnel_v120.png`, `setups_log_v120.csv`, `why.py`)
ทุก setup ที่เคยเกิด (19,338 ครั้งใน 17.6 ปี) ถูกบันทึกพร้อมเหตุผลที่ไม่เข้า ใน `setups_log_v120.csv`
ค้นหาตามเวลาที่เห็นบนกราฟ: `python3 backtest/why.py "2026-10-16 20:30"` (เวลาไทย, ±3 ชม.)
