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
