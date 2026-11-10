import os, numpy as np, pandas as pd, warnings
warnings.filterwarnings('ignore')
from sim import htf_trend
from sim_m1 import run_m1

D = os.path.dirname(os.path.abspath(__file__))
z = np.load(os.environ.get('DATA_DIR', D) + '/data.npz')
t1, o, h, l, c = (z['m1' + k] for k in 'tohlc')
n = len(c)


def atr_sma(h, l, c, p=14):
    pc = np.r_[c[0], c[:-1]]
    tr = np.maximum(h - l, np.maximum(abs(h - pc), abs(l - pc)))
    return pd.Series(tr).rolling(p).mean().fillna(0).to_numpy()


def agg(P):
    key = t1 // P
    st = np.flatnonzero(np.r_[True, key[1:] != key[:-1]]); en = np.r_[st[1:], n] - 1
    return dict(o=o[st], h=np.maximum.reduceat(h, st), l=np.minimum.reduceat(l, st), c=c[en], st=st, en=en,
                gid=np.cumsum(np.r_[True, key[1:] != key[:-1]]) - 1)


atr1 = atr_sma(h, l, c)
M5 = agg(5); a5 = atr_sma(M5['h'], M5['l'], M5['c'])
# ATR of the last CLOSED M5 bar at each M1 index
g5 = M5['gid']; closed5 = np.where(M5['en'][g5] == np.arange(n), g5, g5 - 1)
atr5 = np.where(closed5 >= 0, a5[np.clip(closed5, 0, None)], 0)

H1 = agg(60); H4 = agg(240)
h1c_at = np.full(n, -1, np.int64); h1c_at[H1['en']] = np.arange(len(H1['en']))
h4c_at = np.full(n, -1, np.int64); h4c_at[H4['en']] = np.arange(len(H4['en']))
tr1 = htf_trend(H1['o'], H1['h'], H1['l'], H1['c'], 3); tr4 = htf_trend(H4['o'], H4['h'], H4['l'], H4['c'], 3)


def last_closed_trend(G, tr):
    g = G['gid']; cl = np.where(G['en'][g] == np.arange(n), g, g - 1)
    return np.where(cl >= 0, tr[np.clip(cl, 0, None)], 0)


b1 = last_closed_trend(H1, tr1); b4 = last_closed_trend(H4, tr4)


def last_closed_atr(G):
    a = atr_sma(G['h'], G['l'], G['c']); g = G['gid']; cl = np.where(G['en'][g] == np.arange(n), g, g - 1)
    return np.where(cl >= 0, a[np.clip(cl, 0, None)], 0)


aH1 = last_closed_atr(H1); aH4 = last_closed_atr(H4)
DY = agg(1440)
dayStart = DY['st'][DY['gid']]
prevDS = np.where(DY['gid'] > 0, DY['st'][np.clip(DY['gid'] - 1, 0, None)], 0)
pdh = np.where(DY['gid'] > 0, DY['h'][np.clip(DY['gid'] - 1, 0, None)], 0.0)
pdl = np.where(DY['gid'] > 0, DY['l'][np.clip(DY['gid'] - 1, 0, None)], 0.0)

# --- extra arrays for PDF-derived ideas
prevDE = np.where(DY['gid'] > 0, DY['en'][np.clip(DY['gid'] - 1, 0, None)], 0)
dd_ = t1 // 1440; wk = (dd_ + 3) // 7
wst = np.flatnonzero(np.r_[True, wk[1:] != wk[:-1]]); wen = np.r_[wst[1:], n] - 1
wgid = np.cumsum(np.r_[True, wk[1:] != wk[:-1]]) - 1
WH = np.maximum.reduceat(h, wst); WL = np.minimum.reduceat(l, wst)
wStart = wst[wgid]
pwh = np.where(wgid > 0, WH[np.clip(wgid - 1, 0, None)], 0.0); pwl = np.where(wgid > 0, WL[np.clip(wgid - 1, 0, None)], 0.0)
prevWS = np.where(wgid > 0, wst[np.clip(wgid - 1, 0, None)], 0); prevWE = np.where(wgid > 0, wen[np.clip(wgid - 1, 0, None)], 0)
nyd = (t1 - 420) // 1440
nst = np.flatnonzero(np.r_[True, nyd[1:] != nyd[:-1]]); ngid = np.cumsum(np.r_[True, nyd[1:] != nyd[:-1]]) - 1
mOpen = o[nst][ngid]
# daily bias from the previous two server days
G = DY['gid']; nD = len(DY['st']); db = np.zeros(nD, np.int64)
for D_ in range(2, nD):
    h1_, l1_, c1_ = DY['h'][D_ - 1], DY['l'][D_ - 1], DY['c'][D_ - 1]; h2_, l2_ = DY['h'][D_ - 2], DY['l'][D_ - 2]
    if h1_ > h2_ and c1_ < h2_: db[D_] = -1        # swept prior high, closed back inside -> look for lows
    elif l1_ < l2_ and c1_ > l2_: db[D_] = 1       # swept prior low, closed back inside -> look for highs
    elif c1_ > h2_: db[D_] = 1
    elif c1_ < l2_: db[D_] = -1
dBias = db[G]
# silver aligned to gold minutes
_ag = np.load(os.environ.get('AG_DIR', D + '/../d_xagusd') + '/data.npz')
_i = np.clip(np.searchsorted(_ag['m1t'], t1), 0, len(_ag['m1t']) - 1); _m = _ag['m1t'][_i] == t1
agL = np.where(_m, _ag['m1l'][_i], np.nan); agH = np.where(_m, _ag['m1h'][_i], np.nan)

BASE = dict(risk=1.0, RR=2.0, slBuf=0.5, maxDepth=3.0, maxTrades=2, BE=1.0, BEplus=0.10, partial=50, setupExp=30,
            mssS=2, disp=1.0, minFVG=0.3, fvgWait=5, paWait=15, entry=0, spread=0.30, bal=10000, bias=0,
            lon=1, nyk=1, useH1=1, useH4=1, usePD=1, maxSpR=0.2, maxSL=3.0, sweepPA=3,
            pin=1, pinR=2.0, eng=1, star=1, slMode=0, slK=0.5, maxSLz=3.0, filtM1=0, tpMode=0, minRR=1.0, tpBuf=0.0, tpS=2, spreadRel=0.0, lonS=2.0, lonE=5.0, nyS=7.0, nyE=10.0, dowMask=31, pdF=0, trail=0, eqOnly=0, eqTol=0.1, usePW=0, ote=0.0, po3=0, dbias=0, tp2=0, smt=0, tp2Pct=50)
ORDER = ['risk', 'RR', 'slBuf', 'maxDepth', 'maxTrades', 'BE', 'BEplus', 'partial', 'setupExp', 'mssS', 'disp',
         'minFVG', 'fvgWait', 'paWait', 'entry', 'spread', 'bal', 'bias', 'lon', 'nyk', 'useH1', 'useH4', 'usePD',
         'maxSpR', 'maxSL', 'sweepPA', 'slMode', 'slK', 'maxSLz', 'filtM1', 'tpMode', 'minRR', 'tpBuf', 'tpS', 'spreadRel', 'lonS', 'lonE', 'nyS', 'nyE', 'dowMask', 'pdF', 'trail', 'eqOnly', 'eqTol', 'usePW', 'ote', 'po3', 'dbias', 'tp2', 'smt', 'tp2Pct']
TFN = {1: 'H1', 2: 'H4', 3: 'PDH/PDL', 5: 'PWH/PWL'}


def go(**kw):
    p = dict(BASE, **kw)
    cfg = np.array([p[k] for k in ORDER], float)
    Pc = np.array([p['pin'], p['pinR'], p['eng'], p['star']], float)
    r = run_m1(t1, o, h, l, c, atr1, atr5, h1c_at, h4c_at, dayStart, pdh, pdl,
               H1['h'], H1['l'], H4['h'], H4['l'], b1, b4, cfg, Pc, aH1, aH4, H1['st'], H4['st'], prevDS, H1['gid'], H4['gid'],
               H1['en'], H4['en'], prevDE, wStart, pwh, pwl, prevWS, prevWE, mOpen, dBias, agL, agH)
    cols = ['tin', 'tout', 'dir', 'tf', 'R', 'pnl', 'kz', 'risk', 'entry', 'sl', 'tp', 'lvl', 'sw', 'mi', 'zt', 'zb']
    T = pd.DataFrame({k: v for k, v in zip(cols, r)})
    T['date'] = pd.to_datetime(T.tin * 60, unit='s')
    return T


def stats(T, bal0=10000.0):
    if len(T) == 0:
        return dict(n=0, avgR=float('nan'))
    R = T.R; eq = bal0 + T.pnl.cumsum()
    dd = (eq / eq.cummax().clip(lower=bal0) - 1).min()
    gw = T.pnl[T.pnl > 0].sum(); gl = -T.pnl[T.pnl < 0].sum()
    return dict(n=len(T), win=round((R > 0.05).mean() * 100, 1), avgR=round(R.mean(), 3),
                PF=round(gw / gl, 2) if gl > 0 else np.inf, ret=round((eq.iloc[-1] / bal0 - 1) * 100, 1),
                maxDD=round(dd * 100, 1), tstat=round(R.mean() / R.std() * np.sqrt(len(R)), 2) if len(R) > 1 else 0)
