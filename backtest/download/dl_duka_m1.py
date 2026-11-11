"""Download Dukascopy XAUUSD M1 BID candles WITH volume (one file per UTC day), resumable.
usage: python3 dl_duka_m1.py OUTDIR 2015-01-01 2026-11-10
Dukascopy rate-limits (HTTP 429) -> retry with backoff. Months in the URL are 0-based."""
import sys, os, time, datetime as dt, urllib.request, urllib.error
out, a, b = sys.argv[1], dt.date.fromisoformat(sys.argv[2]), dt.date.fromisoformat(sys.argv[3])
os.makedirs(out, exist_ok=True)
d = a; ok = 0; t0 = time.time()
while d <= b:
    f = f'{out}/{d:%Y%m%d}.bi5'
    if d.weekday() == 5 or os.path.exists(f):          # Saturday: market closed
        d += dt.timedelta(1); continue
    url = f'https://datafeed.dukascopy.com/datafeed/XAUUSD/{d.year}/{d.month-1:02d}/{d.day:02d}/BID_candles_min_1.bi5'
    wait = 2
    while True:
        try:
            data = urllib.request.urlopen(url, timeout=30).read()
            open(f + '.tmp', 'wb').write(data); os.replace(f + '.tmp', f); ok += 1; break
        except urllib.error.HTTPError as e:
            if e.code == 404: open(f, 'wb').close(); break
            time.sleep(wait); wait = min(wait * 2, 60)
        except Exception:
            time.sleep(wait); wait = min(wait * 2, 60)
    if ok % 50 == 0: print(d, ok, f'{time.time()-t0:.0f}s', flush=True)
    time.sleep(0.5)
    d += dt.timedelta(1)
print('done', ok)
