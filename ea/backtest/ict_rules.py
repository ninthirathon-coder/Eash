"""ทดสอบกฎตามหลัก ICT ทีละข้อกับระบบ Order Block ของ EA (v1.22) แล้วเขียนตารางลง ea/results/ict_rules.csv

ข้อมูล: แท่ง M1 ของ XAUUSD จาก branch claude/intelligent-pasteur-f8c6jd (data/xauusd/XAUUSD_M1_YYYY.zip)
  python3 ea/backtest/convert_mt5_zip.py <โฟลเดอร์ zip> ea/data/XAUUSD_M1.csv.gz 2019 2026
  python3 ea/backtest/ict_rules.py [ea/data/XAUUSD_M1.csv.gz]

ข้อจำกัด: HistData ไม่มี tick volume จึงจำลองตัวกรอง volume ของ EA (InpObVolMult) ไม่ได้ ทุกชุดในไฟล์นี้ไม่มีตัวกรองนั้น
"""
import pickle
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from engine import Params, load, run, stats  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "XAUUSD_M1.csv.gz"
CACHE = DATA.with_suffix(".m5.pkl")
SPLIT = "2023-01-01"

OFF = dict(use_model_2022=False, use_wyckoff=False, use_silver_bullet=False, use_ict_levels=False)
# ระบบ Order Block ตามค่าเริ่มต้นของ EA v1.22 (ยกเว้นตัวกรอง volume)
OB = Params(**OFF, ob_model=True, ob_window=(900, 1080), ob_steps=2, ob_step_strength=2, ob_retest_step=1,
            ob_sl_mode="hl", ob_sl_struct_buf=0.2, ob_sl_buf=0.2, ob_min_risk=2.0, ob_tp_hidden=True,
            ob_hz_tfs=(240, 60), ob_hz_bars=3, ob_hz_min_rr=2.0, ob_rr=3.0, ob_sw_min=3, ob_sw_tfs=(1, 3, 15, 30),
            ob_sw_bars=20, ob_sw_er=0.3, order_grace=120, max_trades_day=5, max_losses_day=3, ob_hold_overnight=True)
# ICT Order Block เต็มรูปแบบ (เข้าด้วย MSS + FVG บน TF เล็ก)
ICT = Params(**OFF, ict_ob=True)
KZ = ((540, 720), (840, 1080))      # London 02-05, NY AM + Silver Bullet 07-11 (นาทีนับจาก 17:00 NY)
NY = ((840, 1080),)

RUNS = [
    # กลุ่ม, ชื่อ, Params
    ("ICT OB เต็มรูปแบบ", "ครบทุกข้อใน checklist", ICT),
    ("ICT OB เต็มรูปแบบ", "ไม่บังคับ Discount ของขา MSS", replace(ICT, ict_ob_discount=False)),
    ("ICT OB เต็มรูปแบบ", "+ ไม่บังคับ Premium/Discount H1", replace(ICT, ict_ob_discount=False, ict_ob_pd_bars=0)),
    ("ICT OB เต็มรูปแบบ", "+ ไม่ใช้ bias รายวัน", replace(ICT, ict_ob_discount=False, ict_ob_pd_bars=0, ict_ob_bias=False)),
    ("ICT OB เต็มรูปแบบ", "+ นิยาม OB หลวม (ไม่ต้อง BOS/FVG)",
     replace(ICT, ict_ob_discount=False, ict_ob_pd_bars=0, ict_ob_bias=False, ict_ob_need_fvg=False, ict_ob_need_bos=False)),
    ("กฎ ICT ทีละข้อกับระบบ OB", "ระบบ OB v1.22 (ฐาน)", OB),
    ("กฎ ICT ทีละข้อกับระบบ OB", "+ นิยาม OB แบบ ICT (BOS + FVG)", replace(OB, ob_ict_zones=True)),
    ("กฎ ICT ทีละข้อกับระบบ OB", "+ ปิดหลุด Mean Threshold = โซนใช้ไม่ได้", replace(OB, ob_mt_invalid=True)),
    ("กฎ ICT ทีละข้อกับระบบ OB", "+ Kill Zone London 02-05 + NY 07-11", replace(OB, ob_windows=KZ)),
    ("กฎ ICT ทีละข้อกับระบบ OB", "+ NY AM Kill Zone + Silver Bullet 07-11", replace(OB, ob_windows=NY)),
    ("กฎ ICT ทีละข้อกับระบบ OB", "+ bias รายวัน", replace(OB, ob_bias=True)),
    ("กฎ ICT ทีละข้อกับระบบ OB", "+ Premium/Discount (กรอบ H1 120 แท่ง)", replace(OB, ob_pd_bars=120)),
    ("กฎ ICT ทีละข้อกับระบบ OB", "+ TP ที่สภาพคล่อง (แทน hidden zone)", replace(OB, ob_tp_liq=True, ob_tp_hidden=False)),
    ("กฎ ICT ทีละข้อกับระบบ OB", "+ ปิดไม้ 16:00 ไม่ถือข้ามวัน", replace(OB, ob_hold_overnight=False)),
    ("กฎ ICT ทีละข้อกับระบบ OB", "+ ไม่ใช้ตัวกรอง sideway (ไม่ใช่กฎ ICT)", replace(OB, ob_sw_min=0)),
    ("รวมกฎที่ช่วย", "bias + Mean Threshold", replace(OB, ob_bias=True, ob_mt_invalid=True)),
    ("รวมกฎที่ช่วย", "bias + Premium/Discount", replace(OB, ob_bias=True, ob_pd_bars=120)),
    ("รวมกฎที่ช่วย", "bias + TP ที่สภาพคล่อง", replace(OB, ob_bias=True, ob_tp_liq=True, ob_tp_hidden=False)),
    ("v1.30", "v1.30 ค่าเริ่มต้น: bias + เวลา 07-11", replace(OB, ob_bias=True, ob_windows=NY)),
    ("v1.30", "v1.30 + แบ่งปิด 50% ที่ 1R", replace(OB, ob_bias=True, ob_windows=NY, partial_r=1.0)),
    ("v1.30", "v1.22 + แบ่งปิด 50% ที่ 1R", replace(OB, partial_r=1.0)),
]


def main():
    if CACHE.exists():
        data = pickle.load(open(CACHE, "rb"))
    else:
        data = load(DATA, start="2019-01-01", tf=5)
        pickle.dump(data, open(CACHE, "wb"))
    rows = []
    for group, name, p in RUNS:
        tr, _ = run(data, p)
        st = stats(tr, p)
        row = dict(กลุ่ม=group, ชุด=name, ไม้=st.get("trades", 0), ชนะ=st.get("win_rate", 0), PF=st.get("pf", 0),
                   ผลตอบแทน=st.get("ret_pct", 0), DD=st.get("max_dd_pct", 0), R_ต่อไม้=st.get("expectancy_R", 0))
        if len(tr):
            t = pd.to_datetime(tr.open_time)
            a, b = tr[t < SPLIT], tr[t >= SPLIT]
            row["R_ต่อไม้_2019_22"] = round(a.R.mean(), 2) if len(a) else np.nan
            row["R_ต่อไม้_2023_26"] = round(b.R.mean(), 2) if len(b) else np.nan
            for y, v in tr.groupby(t.dt.year).R.sum().items():
                row[f"R_{y}"] = round(v, 1)
        rows.append(row)
        print(f"{group:26s} {name:42s} n={row['ไม้']:4d} PF={row['PF']:5.2f} ret={row['ผลตอบแทน']:7.2f}% DD={row['DD']:5.1f}%",
              flush=True)
    out = ROOT / "results" / "ict_rules.csv"
    pd.DataFrame(rows).to_csv(out, index=False)
    print("->", out)


if __name__ == "__main__":
    main()
