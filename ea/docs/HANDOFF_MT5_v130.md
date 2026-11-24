# ทดสอบ EA v1.30 ใน MT5 บนเครื่องผู้ใช้

เปิด Claude Code แบบรันในเครื่อง (local) ที่โฟลเดอร์ repo Eash ที่ใช้รัน `tools\run_mt5_tests.ps1` อยู่แล้ว แล้ววางข้อความด้านล่างทั้งหมด

---

งาน: compile และทดสอบ ICT_Wyckoff_Gold_EA v1.30 ใน Strategy Tester เทียบกับ v1.22 (รอบ G/H 5 ปีเดิม)

1. อยู่ที่ branch `claude/friendly-franklin-wvv9a6` (`git pull` ก่อน) แล้วดึงซอร์ส v1.30 มาแทนไฟล์เดิม:
   `git fetch origin claude/happy-mccarthy-7r2mhp`
   `cmd /c "git show origin/claude/happy-mccarthy-7r2mhp:ea/mql5/ICT_Wyckoff_Gold_EA.mq5 > mql5\ICT_Wyckoff_Gold_EA.mq5"`
   (ใช้ `cmd /c` เพราะการ redirect ของ PowerShell 5.1 จะแปลงไฟล์เป็น UTF-16 และภาษาไทยเพี้ยน)
   ตรวจว่าไฟล์เป็น `#property version "1.30"` และภาษาไทยในคอมเมนต์อ่านออก
2. เพิ่มรอบในตาราง `$runs` ของ `tools\run_mt5_tests.ps1` (ห้ามแก้รอบเดิม):
   - `I_v130_ict_nostop`: `InpSkipFomc=false; InpTotalDDPct=0`
   - `J_v130_ict_part1R_nostop`: `InpSkipFomc=false; InpObPartialR=1.0; InpTotalDDPct=0`
   - `K_v130_ict_novol_nostop`: `InpSkipFomc=false; InpObVolMult=0; InpTotalDDPct=0` (ไม่มีตัวกรอง volume เหมือนที่ทดสอบใน Python)
   - `L_v130_as_v122_nostop`: `InpSkipFomc=false; InpObUseBias=false; InpObStart=800; InpTotalDDPct=0` (ต้องได้ผลเท่ารอบ G เป๊ะ ถ้าไม่เท่าให้รายงาน)
3. ขอให้ผู้ใช้ปิด MT5 ก่อน ห้ามปิดเองโดยไม่ถาม ห้ามรันบนบัญชีจริง ใช้ Strategy Tester อย่างเดียว
4. รัน 5 ปี (2021.11.22 ถึง 2026.11.22) ด้วย `-Only I,J,K,L -Suffix _5y`:
   - XM แบบ real ticks (Model 4)
   - FxPro แบบ Every tick (Model 0) เพราะ real ticks ของ FxPro เริ่มกลางปี 2024
   ถ้า compile ไม่ผ่าน ให้แก้เฉพาะ error ของการ compile ห้ามเปลี่ยนตรรกะการเทรด แล้วรายงานว่าแก้อะไร
5. สรุปเป็นตารางเทียบกับรอบ G/H 5 ปีเดิม: กำไรสุทธิ, PF, จำนวนไม้, Balance DD, Equity DD, แพ้ติดกันสูงสุด และกำไรรายปี
   - ต่อท้ายไฟล์ `results/MT5_ORDER_BLOCK.md` และ `results/mt5_reports/summary.csv`
   - commit แล้ว push

ผลที่คาดจาก Python (`ea/results/ICT_RULES.md` ใน branch `claude/happy-mccarthy-7r2mhp`): v1.30 มีไม้น้อยกว่า v1.22 ราวครึ่งหนึ่ง PF สูงขึ้น และ DD ต่ำลง
