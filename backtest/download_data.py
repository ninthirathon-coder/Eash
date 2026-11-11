"""ดาวน์โหลดแท่ง M1 ของ XAUUSD จาก HistData.com แล้วรวมเป็น data/XAUUSD_M1.csv.gz (เวลานิวยอร์ก)

ใช้:  python3 backtest/download_data.py 2023 2026
ปีที่จบแล้วโหลดเป็นไฟล์รายปี ปีปัจจุบันโหลดรายเดือน
หมายเหตุ: ข้อมูล HistData เป็นราคา BID และไม่มี volume
เวลาในไฟล์ตรวจแล้วว่าตรงกับเวลานิวยอร์กตามนาฬิกาจริงทั้งปี (ข่าว 08:30 และช่วงพัก 17:00-18:00 ตรงทุกฤดู)
ข้อมูลช่วง ก.พ.-ก.ค. 2023 มีช่องโหว่รายชั่วโมง ไม่ควรใช้ทดสอบ
"""
import io
import re
import sys
import zipfile
from datetime import date
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent / "data"
BASE = "https://www.histdata.com/download-free-forex-historical-data/?/ascii/1-minute-bar-quotes/xauusd/"
UA = {"User-Agent": "Mozilla/5.0"}


def fetch(year: int, month: int | None = None) -> pd.DataFrame | None:
    url = BASE + str(year) + (f"/{month}" if month else "")
    s = requests.Session()
    page = s.get(url, headers=UA, timeout=60).text
    tk = re.search(r'id="tk" value="([^"]+)"', page)
    dm = re.search(r'id="datemonth" value="([^"]+)"', page)
    if not tk:
        return None
    r = s.post("https://www.histdata.com/get.php", headers={**UA, "Referer": url}, timeout=300,
               data=dict(tk=tk.group(1), date=str(year), datemonth=dm.group(1), platform="ASCII",
                         timeframe="M1", fxpair="XAUUSD"))
    if r.status_code != 200 or r.content[:2] != b"PK":
        return None
    z = zipfile.ZipFile(io.BytesIO(r.content))
    name = next(n for n in z.namelist() if n.endswith(".csv"))
    df = pd.read_csv(z.open(name), sep=";", header=None,
                     names=["time", "open", "high", "low", "close", "volume"])
    df["time"] = pd.to_datetime(df["time"], format="%Y%m%d %H%M%S")
    return df


def main():
    y0, y1 = int(sys.argv[1]), int(sys.argv[2])
    frames = []
    for y in range(y0, y1 + 1):
        if y < date.today().year:
            parts = [fetch(y)]
        else:
            parts = [fetch(y, m) for m in range(1, date.today().month + 1)]
        for f in parts:
            if f is not None:
                frames.append(f)
        print(y, sum(len(f) for f in parts if f is not None), "bars")
    df = pd.concat(frames).drop_duplicates("time").sort_values("time").reset_index(drop=True)
    ROOT.mkdir(exist_ok=True)
    out = ROOT / "XAUUSD_M1.csv.gz"
    df.to_csv(out, index=False, float_format="%.3f")
    print(f"{len(df):,} bars  {df.time.iloc[0]} -> {df.time.iloc[-1]}  saved {out}")


if __name__ == "__main__":
    main()
