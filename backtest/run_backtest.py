"""รัน backtest แล้วเขียนรายงานลง results/

ใช้:  python3 backtest/run_backtest.py            # ชุดมาตรฐาน (M1/M3/M5 + ตัวแปรหลัก)
      python3 backtest/run_backtest.py --grid     # เพิ่มตาราง grid 96 ชุด (ช้า ~2 นาที)
"""
import itertools
import sys
from pathlib import Path

import pandas as pd

from engine import Params, load, run, stats

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "XAUUSD_M1.csv.gz"
OUT = ROOT / "results"
START = "2024-01-01"     # ข้อมูลก่อนหน้านี้มีช่องโหว่
SPLIT = "2025-07-01"     # ก่อน = in-sample, หลัง = out-of-sample

VARIANTS = [
    ("ค่าเริ่มต้นของ EA", {}),
    ("เข้าเฉพาะโซน Discount/Premium", dict(require_discount=True)),
    ("ไม่ใช้ bias รายวัน", dict(use_bias=False)),
    ("ไม่ปิดเมื่อแท่งปิดทะลุ FVG", dict(exit_on_fvg_fail=False)),
    ("ไม่แบ่งปิดที่ TP1", dict(partial_at_tp1=False)),
    ("เฉพาะ Wyckoff Spring/UTAD", dict(use_ict_levels=False, use_swing_levels=False)),
    ("เฉพาะ London Kill Zone", dict(trade_nyam=False)),
    ("เฉพาะ New York AM Kill Zone", dict(trade_london=False)),
    ("Silver Bullet อย่างเดียว", dict(use_model_2022=False, use_silver_bullet=True)),
    ("Silver Bullet ไม่ใช้ bias", dict(use_model_2022=False, use_silver_bullet=True, use_bias=False)),
    ("Silver Bullet ไม่ปิดเมื่อทะลุ FVG", dict(use_model_2022=False, use_silver_bullet=True, exit_on_fvg_fail=False)),
    ("2022 Model + Silver Bullet", dict(use_silver_bullet=True)),
]


def row(name, tf, tr, p):
    st = stats(tr, p)
    if st["trades"] == 0:
        return dict(TF=f"M{tf}", ชุดค่า=name, ไม้=0)
    a, b = tr[tr.open_time < SPLIT], tr[tr.open_time >= SPLIT]
    return {"TF": f"M{tf}", "ชุดค่า": name, "ไม้": st["trades"], "ชนะ%": st["win_rate"],
            "กำไรสุทธิ$": st["net"], "ผลตอบแทน%": st["ret_pct"], "PF": st["pf"],
            "R/ไม้": st["expectancy_R"], "MaxDD%": st["max_dd_pct"],
            "ไม้ IS": len(a), "R รวม IS": round(a.R.sum(), 1), "ไม้ OOS": len(b), "R รวม OOS": round(b.R.sum(), 1)}


def fmt(col, v):
    if isinstance(v, float):
        return str(int(v)) if str(col).startswith("ไม้") else f"{v:.2f}"
    return str(v)


def table(df):
    df = df.fillna("")
    head = "| " + " | ".join(map(str, df.columns)) + " |"
    sep = "|" + "|".join("---" for _ in df.columns) + "|"
    body = ["| " + " | ".join(fmt(c, v) for c, v in zip(df.columns, r)) + " |"
            for r in df.itertuples(index=False)]
    return "\n".join([head, sep] + body)


def main():
    OUT.mkdir(exist_ok=True)
    rows, grid = [], []
    detail = {}
    for tf in (5, 3, 1):
        d = load(DATA, start=START, tf=tf)
        span = (pd.Timestamp(d.m5["time"][0]).date(), pd.Timestamp(d.m5["time"][-1]).date())
        for name, kw in VARIANTS:
            p = Params(**kw)
            tr, eq = run(d, p)
            rows.append(row(name, tf, tr, p))
            if not kw:
                tr.to_csv(OUT / f"trades_M{tf}.csv", index=False, float_format="%.3f")
                eq.to_csv(OUT / f"equity_M{tf}.csv", index=False, float_format="%.2f")
                detail[tf] = tr
        if "--grid" in sys.argv:
            for bias, ff, part, disc, rr in itertools.product([True, False], [True, False], [True, False],
                                                              [True, False], [2.0, 3.0]):
                p = Params(use_bias=bias, exit_on_fvg_fail=ff, partial_at_tp1=part, require_discount=disc, min_rr=rr)
                tr, _ = run(d, p)
                if len(tr) == 0:
                    continue
                a, b = tr[tr.open_time < SPLIT], tr[tr.open_time >= SPLIT]
                grid.append({"TF": f"M{tf}", "bias": bias, "fvg_fail": ff, "partial": part, "discount": disc,
                             "min_rr": rr, "ไม้ IS": len(a), "R/ไม้ IS": round(a.R.mean(), 3) if len(a) else 0,
                             "ไม้ OOS": len(b), "R/ไม้ OOS": round(b.R.mean(), 3) if len(b) else 0})
    p = Params()
    L = [f"# ผล Backtest — ICT + Wyckoff Gold EA", "",
         f"- ข้อมูล: XAUUSD M1 (BID) จาก HistData.com ช่วง {span[0]} ถึง {span[1]}",
         f"- ทุนเริ่มต้น {p.balance:,.0f} ดอลลาร์ เสี่ยง {p.risk_pct}% ต่อไม้ spread {p.spread} ดอลลาร์ "
         f"ค่าคอมมิชชัน {p.commission} ดอลลาร์ต่อ lot ไป-กลับ",
         f"- IS (in-sample) = ก่อน {SPLIT}, OOS (out-of-sample) = ตั้งแต่ {SPLIT}",
         "- R = กำไร/ขาดทุนเทียบกับความเสี่ยงของไม้นั้น", "",
         "## ผลตามชุดค่าและ timeframe สัญญาณ", "", table(pd.DataFrame(rows)), ""]
    for tf, tr in detail.items():
        if len(tr) == 0:
            continue
        L += [f"## รายละเอียดค่าเริ่มต้นบน M{tf}", ""]
        for col, title in [("tag", "ตามสภาพคล่องที่ถูกกวาด"), ("kz", "ตาม Kill Zone"), ("dir", "ตามทิศ (1=Buy, -1=Sell)"),
                           ("exit", "ตามวิธีออก")]:
            g = tr.groupby(col).agg(ไม้=("R", "size"), ชนะ=("pnl", lambda s: round((s > 0).mean() * 100, 1)),
                                    R_รวม=("R", "sum"), R_ต่อไม้=("R", "mean")).round(2).reset_index()
            g.columns = [title, "ไม้", "ชนะ%", "R รวม", "R/ไม้"]
            L += [table(g), ""]
        y = tr.groupby(tr.open_time.dt.year).agg(ไม้=("R", "size"), R_รวม=("R", "sum"), กำไร=("pnl", "sum")).round(2)
        y = y.reset_index()
        y.columns = ["ปี", "ไม้", "R รวม", "กำไรสุทธิ$"]
        L += [table(y), ""]
    if grid:
        g = pd.DataFrame(grid).sort_values("R/ไม้ IS", ascending=False)
        g.to_csv(OUT / "grid.csv", index=False)
        ok = g[g["ไม้ IS"] >= 30]
        L += ["## Grid 96 ชุดค่า (เรียงตาม R/ไม้ ช่วง IS, เฉพาะชุดที่มี IS >= 30 ไม้, 15 อันดับแรก)", "",
              table(ok.head(15)), "",
              f"- ชุดที่มี IS >= 30 ไม้: {len(ok)} ชุด, ชุดที่ R/ไม้ เป็นบวกทั้ง IS และ OOS: "
              f"{int(((ok['R/ไม้ IS'] > 0) & (ok['R/ไม้ OOS'] > 0)).sum())} ชุด",
              f"- ทั้ง grid: {len(g)} ชุด, บวกทั้ง IS และ OOS: "
              f"{int(((g['R/ไม้ IS'] > 0) & (g['R/ไม้ OOS'] > 0)).sum())} ชุด", ""]
    (OUT / "REPORT.md").write_text("\n".join(L), encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
