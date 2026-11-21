"""สร้างข้อมูลให้หน้ากราฟแบบ TradingView (chart/index.html)

ใช้:
  python3 chart/build_chart.py                                   # 6 เดือนล่าสุด M5 + ไม้จาก results/mt5_order_block_trades.csv
  python3 chart/build_chart.py --start 2026-01-01 --tf 15
  python3 chart/build_chart.py --trades results/hybrid_M15_trades.csv
  python3 chart/build_chart.py --no-volume                       # ไม่ดึง volume ทองคำล่วงหน้า (GC=F)

ผลลัพธ์อยู่ที่ chart/out/  (index.html, bars.json, trades.json)
เปิดดูในเครื่อง:  cd chart/out && python3 -m http.server 8000  แล้วเข้า http://localhost:8000

เรื่อง volume: ข้อมูลราคา HistData ไม่มี volume เลยยืม volume จริงของทองคำล่วงหน้า COMEX (GC=F) จาก Yahoo
มาใส่ตามเวลาแท่ง (ราคาใช้ spot เหมือนเดิม) Yahoo ให้แท่ง 5 นาทีย้อนหลัง ~60 วัน และแท่ง 1 ชั่วโมงย้อนหลัง ~2 ปี
ช่วงที่มีแค่ 1 ชั่วโมงจะเฉลี่ย volume ลงแท่งย่อยเท่าๆ กัน ถ้าดึงไม่ได้ หน้ากราฟจะใช้ profile แบบนับเวลา (TPO) แทน
"""
import argparse
import json
import sys
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "XAUUSD_M1.csv.gz"
OUT = Path(__file__).resolve().parent / "out"
YAHOO = "https://query1.finance.yahoo.com/v8/finance/chart/GC=F"

# ชื่อคอลัมน์ที่เจอในไฟล์ไม้ของ backtest/MT5 -> ชื่อกลาง
ALIASES = {
    "open_time": "open", "close_time": "close", "entry": "entry", "exit_price": "exit",
    "pnl": "pnl", "dir": "dir", "sl": "sl", "tp1": "tp1", "tp2": "tp2", "R": "R", "lot": "lot",
}


def load_bars(path: Path, start, end, tf: int) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["time"])
    if start:
        df = df[df.time >= start]
    if end:
        df = df[df.time < end]
    df = df.set_index("time")
    if tf > 1:
        df = df.resample(f"{tf}min", label="left", closed="left").agg(
            {"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    return df[["open", "high", "low", "close"]]


def yahoo(interval: str, rng: str) -> pd.Series | None:
    try:
        r = requests.get(YAHOO, params=dict(interval=interval, range=rng),
                         headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
        res = r.json()["chart"]["result"][0]
    except Exception as e:  # noqa: BLE001
        print(f"  ดึง GC=F {interval} ไม่ได้: {e}", file=sys.stderr)
        return None
    t = pd.to_datetime(res["timestamp"], unit="s", utc=True).tz_convert("America/New_York").tz_localize(None)
    v = pd.Series(res["indicators"]["quote"][0]["volume"], index=t, dtype="float").fillna(0)
    return v[~v.index.duplicated()]


def attach_volume(bars: pd.DataFrame, tf: int) -> tuple[pd.Series, str]:
    """volume ของ GC=F ต่อแท่ง (เวลานิวยอร์ก) ใช้ 5m ก่อน ส่วนที่เก่ากว่าเฉลี่ยจาก 1h"""
    vol = pd.Series(0.0, index=bars.index)
    src = []
    h1 = yahoo("60m", "730d")
    if h1 is not None:
        # กระจาย volume รายชั่วโมงให้แท่งที่มีอยู่จริงในชั่วโมงนั้นเท่าๆ กัน
        hour = bars.index.floor("h")
        n = pd.Series(1, index=bars.index).groupby(hour).transform("count")
        vol = (h1.reindex(hour).fillna(0).to_numpy() / n.to_numpy())
        vol = pd.Series(vol, index=bars.index)
        src.append("1h")
    if tf % 5 == 0:
        m5 = yahoo("5m", "60d")
        if m5 is not None and len(m5):
            fine = m5.resample(f"{tf}min", label="left", closed="left").sum()
            mask = bars.index >= m5.index[0]
            vol[mask] = fine.reindex(bars.index[mask]).fillna(0).to_numpy()
            src.append(f"{tf}m")
    return vol.round(0), "+".join(src)


def load_trades(path: Path, bars: pd.DataFrame) -> list[dict]:
    df = pd.read_csv(path)
    df = df.rename(columns={k: v for k, v in ALIASES.items() if k in df.columns})
    if "exit" in df.columns and not pd.api.types.is_numeric_dtype(df["exit"]):
        df = df.rename(columns={"exit": "reason"})  # ไฟล์ backtest ใช้ exit เป็นเหตุผลการปิด
    need = {"open", "dir", "entry"}
    if not need <= set(df.columns):
        sys.exit(f"ไฟล์ไม้ต้องมีคอลัมน์ {need} (เจอ {list(df.columns)})")
    df["open"] = pd.to_datetime(df["open"])
    if "close" in df.columns:
        df["close"] = pd.to_datetime(df["close"])
    if "ny_hour" in df.columns:
        # ไฟล์จาก MT5 เป็นเวลาเซิร์ฟเวอร์โบรก ใช้ ny_hour แปลงกลับเป็นเวลานิวยอร์ก (ส่วนต่างเปลี่ยนตาม DST)
        off = pd.to_timedelta((df["open"].dt.hour - df["ny_hour"]) % 24, unit="h")
        df["open"] = df["open"] - off
        if "close" in df.columns:
            df["close"] = df["close"] - off
    t0, t1 = bars.index[0], bars.index[-1]
    df = df[(df["open"] >= t0) & (df["open"] <= t1)]
    out = []
    for r in df.to_dict("records"):
        tr = {"t0": int(r["open"].timestamp()), "dir": int(r["dir"]), "entry": round(float(r["entry"]), 3)}
        if pd.notna(r.get("close")):
            tr["t1"] = int(r["close"].timestamp())
        for k in ("exit", "sl", "tp1", "tp2", "pnl", "R", "lot"):
            if k in r and pd.notna(r[k]) and isinstance(r[k], (int, float)):
                tr[k] = round(float(r[k]), 3)
        if "reason" in r and pd.notna(r["reason"]):
            tr["reason"] = str(r["reason"])
        # ไฟล์ backtest ไม่มีราคาปิด: ประมาณจาก pnl/lot (ทอง 1 lot = 100 oz)
        if "exit" not in tr and {"pnl", "lot"} <= tr.keys() and tr["lot"]:
            tr["exit"] = round(tr["entry"] + tr["pnl"] / (tr["lot"] * 100) * tr["dir"], 3)
        out.append(tr)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(DATA))
    ap.add_argument("--start", help="YYYY-MM-DD (ค่าเริ่มต้น: 6 เดือนก่อนแท่งสุดท้าย)")
    ap.add_argument("--end")
    ap.add_argument("--tf", type=int, default=5, help="นาทีต่อแท่งพื้นฐาน (1, 5, 15...) หน้ากราฟรวมเป็น TF ใหญ่ขึ้นได้เอง")
    ap.add_argument("--trades", default=str(ROOT / "results" / "mt5_order_block_trades.csv"))
    ap.add_argument("--no-volume", action="store_true")
    a = ap.parse_args()

    path = Path(a.data)
    if not path.exists():
        sys.exit(f"ไม่เจอ {path} ให้รัน  python3 backtest/download_data.py 2025 2026  ก่อน")
    start = a.start
    if not start:
        last = pd.read_csv(path, usecols=["time"]).time.iloc[-1]
        start = (pd.Timestamp(last) - pd.DateOffset(months=6)).strftime("%Y-%m-%d")
    if a.tf == 1 and pd.Timestamp(a.end or pd.Timestamp.now()) - pd.Timestamp(start) > pd.Timedelta(days=62):
        print("เตือน: M1 เกิน 2 เดือนไฟล์จะใหญ่และกราฟช้าบนมือถือ", file=sys.stderr)

    bars = load_bars(path, start, a.end, a.tf)
    print(f"แท่ง M{a.tf}: {len(bars):,}  {bars.index[0]} -> {bars.index[-1]}")
    vol, vsrc = (pd.Series(0.0, index=bars.index), "") if a.no_volume else attach_volume(bars, a.tf)
    print(f"volume: {vsrc or 'ไม่มี (ใช้ TPO)'}")

    OUT.mkdir(exist_ok=True)
    # เวลานิวยอร์กแบบไม่มีโซน -> epoch แบบ UTC เพื่อให้กราฟแสดงเวลานิวยอร์กตรงๆ
    t = ((bars.index - pd.Timestamp(0)) // pd.Timedelta(seconds=1)).tolist()
    rows = [[ti, round(o, 3), round(h, 3), round(lo, 3), round(c, 3), int(v)]
            for ti, o, h, lo, c, v in zip(t, bars.open, bars.high, bars.low, bars.close, vol)]
    meta = {"symbol": "XAUUSD", "tf": a.tf, "tz": "America/New_York", "volume": vsrc,
            "source": "HistData (BID)" + (f" + volume GC=F {vsrc}" if vsrc else "")}
    with open(OUT / "bars.json", "w") as f:
        f.write('{"meta":' + json.dumps(meta, ensure_ascii=False) + ',"bars":[\n')
        f.write(",\n".join(json.dumps(r, separators=(",", ":")) for r in rows))
        f.write("\n]}\n")

    trades = []
    if a.trades and Path(a.trades).exists():
        trades = load_trades(Path(a.trades), bars)
    (OUT / "trades.json").write_text(json.dumps(
        {"file": Path(a.trades).name if a.trades else "", "trades": trades}, ensure_ascii=False, indent=0))
    print(f"ไม้ในช่วงกราฟ: {len(trades)}")
    page = (Path(__file__).resolve().parent / "index.html").read_text()
    (OUT / "index.html").write_text(
        '<!doctype html>\n<html lang="th"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n'
        + page + "\n</html>\n")
    print(f"เขียนไว้ที่ {OUT}")


if __name__ == "__main__":
    main()
