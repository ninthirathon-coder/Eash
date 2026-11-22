งานนี้ทำต่อจาก session บนคลาวด์ ให้ทำบนเครื่อง Windows นี้ที่มี MT5 ของ XM ติดตั้งอยู่

## บริบท

- repo: `ninthirathon-coder/eash` branch `claude/friendly-franklin-wvv9a6`
- EA ทองคำ (XAUUSD / GOLD#) ระบบ Order Block H1 อยู่ที่ `mql5/ICT_Wyckoff_Gold_EA.mq5` (v1.21)
- `mql5/ICT_Wyckoff_Gold_EA_v111.mq5` คือรุ่น v1.11 ที่ผู้ใช้เรียกว่าไฟล์ "Profit" ระบบเทรดเหมือน v1.21 ต่างกันที่ v1.21 เพิ่ม: เวลานิวยอร์กอัตโนมัติ, หยุดขาดทุนรวม 8%, หยุดขาดทุนรายวัน 3%, งดวัน FOMC, ตัวเลือกปิดวันศุกร์ (ปิดอยู่)
- ผลที่มีแล้วอยู่ใน `results/MT5_ORDER_BLOCK.md` ล่าสุดบน XM (GOLD#, M5, real ticks, 2024.01.01–2026.11.22, ทุน 10,000, 1:500): v1.21 ได้ +2,619.71, 64 ไม้, PF 1.48, Equity DD 10.75%
- สคริปต์รันทดสอบ: `tools/run_mt5_tests.ps1` (compile ทั้งสองรุ่น แล้วรัน Strategy Tester 4 รอบแบบไม่ต้องกด: A = v1.11, B = v1.21 ค่าเริ่มต้น, C = v1.21 ไม่งด FOMC, D = v1.21 เสี่ยง 0.5%) ยังไม่เคยรันบน Windows จริง

## สิ่งที่ต้องทำ

1. clone หรือ pull branch ข้างบน
2. หา path ของ `terminal64.exe` ของ XM และโฟลเดอร์ข้อมูล MT5 (ที่มีโฟลเดอร์ `MQL5` อยู่ข้างใน ปกติใต้ `%APPDATA%\MetaQuotes\Terminal\<รหัส>`) ถ้ามีหลายโฟลเดอร์ เลือกอันที่ `origin.txt` ชี้ไปที่โฟลเดอร์ติดตั้งของ XM
3. ถ้า MT5 เปิดอยู่ ให้ขอผู้ใช้ปิดก่อน ห้ามปิดเองโดยไม่ถาม
4. รัน
   `powershell -ExecutionPolicy Bypass -File tools\run_mt5_tests.ps1 -Terminal "<terminal64.exe>" -DataDir "<โฟลเดอร์ข้อมูล>"`
   ถ้าสคริปต์ error ให้แก้สคริปต์ให้ทำงานได้ (เช่น การอ่านผล compile หรือรายงาน) แล้วรันใหม่
5. ตรวจว่ารอบ C ได้ผลเท่ากับรอบ A ถ้าไม่เท่า หาสาเหตุจาก log ของ Strategy Tester (`<โฟลเดอร์ข้อมูล>\Tester\...\logs` หรือ `Tester\logs`)
6. สรุปผลทั้ง 4 รอบเป็นตาราง (กำไรสุทธิ, PF, จำนวนไม้, Balance DD, Equity DD) เทียบกับผลล่าสุดข้างบน แล้วบันทึกต่อท้าย `results/MT5_ORDER_BLOCK.md` พร้อมไฟล์ `results/mt5_reports/summary.csv`
7. commit และ push ไปที่ branch เดิม

## ข้อห้าม

- ห้ามแก้ตรรกะการเทรดใน EA ในงานนี้ ให้รายงานผลเท่านั้น
- ห้ามรันบนบัญชีจริง ใช้ Strategy Tester อย่างเดียว
