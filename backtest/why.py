"""ค้นหาว่าทำไม EA (ICT_TopDown_EA v1.20) ไม่เข้า/เข้าออเดอร์ ณ เวลาที่เห็นบนกราฟ
ใช้: python3 why.py "2026-10-16 20:30"            (เวลาไทย, ดู ±3 ชม.)
     python3 why.py "2026-10-16 20:30" 6          (ดู ±6 ชม.)
     python3 why.py "2026-10-16 07:30" 3 ny       (ระบุเป็นเวลานิวยอร์ก)
ข้อมูล: setups_log_v120.csv (ทองคำ HistData 2009-03 ถึง 2026-11-06)"""
import sys, os, pandas as pd
D = os.path.dirname(os.path.abspath(__file__))
L = pd.read_csv(os.path.join(D, 'setups_log_v120.csv'), encoding='utf-8-sig')
when = pd.Timestamp(sys.argv[1]); win = float(sys.argv[2]) if len(sys.argv) > 2 else 3
col = 'เวลาNY_sweep' if len(sys.argv) > 3 and sys.argv[3].lower() == 'ny' else 'เวลาไทย_sweep'
t = pd.to_datetime(L[col])
M = L[(t >= when - pd.Timedelta(hours=win)) & (t <= when + pd.Timedelta(hours=win))]
if M.empty:
    print('ไม่มีโซน TF ใหญ่ (swing H1/H4, PDH/PDL) ถูกแทงในช่วงนี้ -> EA ไม่มี setup ให้พิจารณาเลย')
    print('(EA ไม่ได้ใช้ swing M5/M15, Asian range, Equal highs/lows เล็กๆ เป็นโซน)')
else:
    pd.set_option('display.width', 220); pd.set_option('display.max_colwidth', 60)
    print(M[['เวลาไทย_sweep', 'เวลาNY_sweep', 'ฝั่ง', 'โซน', 'ระดับ', 'ผล']].to_string(index=False))
