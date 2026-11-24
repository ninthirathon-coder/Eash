"""Convert intelligent-pasteur MT5-format zips (server time = NY+7) to the engine's csv.gz (NY time)."""
import sys, zipfile, pandas as pd
from pathlib import Path
raw, out = Path(sys.argv[1]), Path(sys.argv[2])
frames = []
for y in range(int(sys.argv[3]), int(sys.argv[4]) + 1):
    z = zipfile.ZipFile(raw / f"XAUUSD_M1_{y}.zip")
    df = pd.read_csv(z.open(z.namelist()[0]), sep="\t")
    df.columns = [c.strip("<>").lower() for c in df.columns]
    t = pd.to_datetime(df["date"] + " " + df["time"], format="%Y.%m.%d %H:%M:%S") - pd.Timedelta(hours=7)
    frames.append(pd.DataFrame({"time": t, "open": df.open, "high": df.high, "low": df.low, "close": df.close, "volume": df.tickvol}))
    print(y, len(df))
d = pd.concat(frames).drop_duplicates("time").sort_values("time").reset_index(drop=True)
d.to_csv(out, index=False, float_format="%.3f")
print("rows", len(d), d.time.min(), d.time.max())
