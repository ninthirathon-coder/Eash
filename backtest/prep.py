"""Load HistData XAUUSD M1 (EST, UTC-5 fixed) -> server time (NY+7, DST-aware) -> M1/M5/H1 arrays."""
import glob, sys, numpy as np, pandas as pd

D = sys.argv[1]
files = sorted(glob.glob(D + '/csv/*.csv'))
df = pd.concat([pd.read_csv(f, sep=';', header=None, names=['dt', 'o', 'h', 'l', 'c', 'v']) for f in files])
est = pd.to_datetime(df.dt, format='%Y%m%d %H%M%S')
utc = (est + pd.Timedelta(hours=5)).dt.tz_localize('UTC')
ny = utc.dt.tz_convert('America/New_York').dt.tz_localize(None)
server = ny + pd.Timedelta(hours=7)
m = server.to_numpy().astype('datetime64[m]').astype(np.int64)
o, h, l, c = (df[k].to_numpy(float) for k in 'ohlc')
idx = np.argsort(m, kind='stable')
m, o, h, l, c = m[idx], o[idx], h[idx], l[idx], c[idx]
keep = np.r_[True, m[1:] != m[:-1]]
m, o, h, l, c = m[keep], o[keep], h[keep], l[keep], c[keep]
print('M1 bars', len(m), pd.to_datetime(m[0] * 60, unit='s'), '->', pd.to_datetime(m[-1] * 60, unit='s'))


def agg(period):
    key = m // period
    st = np.flatnonzero(np.r_[True, key[1:] != key[:-1]])
    en = np.r_[st[1:], len(m)]
    return dict(t=key[st] * period, o=o[st], h=np.maximum.reduceat(h, st), l=np.minimum.reduceat(l, st),
                c=c[en - 1], s=st, e=en)

m5 = agg(5)
h1 = agg(60)
np.savez(D + '/data.npz', m1t=m, m1o=o, m1h=h, m1l=l, m1c=c,
         **{'m5' + k: v for k, v in m5.items()}, **{'h1' + k: v for k, v in h1.items()})
print('M5', len(m5['t']), 'H1', len(h1['t']))
