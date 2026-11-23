# Surge Scanner – ผลสแกน

เก็บผลสแกนแต่ละครั้งเป็นไฟล์แยก ตั้งชื่อตามวันเวลา:

```
scans/surge/YYYY-MM-DD_HHMM.md
```

- `LATEST.md` – สำเนาของผลล่าสุดเสมอ
- `INDEX.md` – รายการผลทั้งหมด (ใหม่สุดอยู่บน)

## บันทึกผลใหม่

```bash
# จากไฟล์
python3 scripts/save_scan.py path/to/result.txt --note "รอบเช้า"

# จาก clipboard / pipe
pbpaste | python3 scripts/save_scan.py - --note "รอบเช้า"
```

แล้ว commit:

```bash
git add scans/surge && git commit -m "Surge scan YYYY-MM-DD" && git push
```

## ดูผลล่าสุด

```bash
cat scans/surge/LATEST.md
```
