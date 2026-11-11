import sys, json, numpy as np, pandas as pd
from sim import run, htf_trend

import os
D = os.path.dirname(os.path.abspath(__file__))
z = np.load(D + '/data.npz')
t5, o, h, l, c, s5, e5 = (z['m5' + k] for k in ('t', 'o', 'h', 'l', 'c', 's', 'e'))
n = len(t5)

# ATR(14) SMA of TR, value at bar t
pc = np.r_[c[0], c[:-1]]
tr = np.maximum(h - l, np.maximum(abs(h - pc), abs(l - pc)))
atr = pd.Series(tr).rolling(14).mean().fillna(0).to_numpy()

# HTF bias (H1 structure, strength 3): trend after last CLOSED H1 bar at decision time (open of t+1)
H = {k: z['h1' + k] for k in ('t', 'o', 'h', 'l', 'c')}
tr_h1 = htf_trend(H['o'], H['h'], H['l'], H['c'], 3)
now = np.r_[t5[1:], t5[-1] + 5]
lastClosed = np.searchsorted(H['t'], (now // 60) * 60, 'left') - 1
bias = np.where(lastClosed >= 0, tr_h1[np.clip(lastClosed, 0, None)], 0)

# Server-day (NY+7) D1: first M5 idx of day, previous day high/low
day = t5 // 1440
st = np.flatnonzero(np.r_[True, day[1:] != day[:-1]])
dh = np.maximum.reduceat(h, st); dl = np.minimum.reduceat(l, st)
gid = np.cumsum(np.r_[True, day[1:] != day[:-1]]) - 1
dayFirst = st[gid]
pdh = np.where(gid > 0, dh[np.clip(gid - 1, 0, None)], 0.0)
pdl = np.where(gid > 0, dl[np.clip(gid - 1, 0, None)], 0.0)

# Asian range 20:00-24:00 NY (belongs to next NY day)
ny = t5 - 420
nyd = ny // 1440; nym = ny % 1440
inA = nym >= 1200
Dn = nyd + 1
asD0 = int(Dn.min())
nD = int(Dn.max() - asD0 + 2)
asHi = np.full(nD, -1e18); asLo = np.full(nD, 1e18); asLast = np.full(nD, -1, np.int64)
idx = np.flatnonzero(inA)
np.maximum.at(asHi, Dn[idx] - asD0, h[idx]); np.minimum.at(asLo, Dn[idx] - asD0, l[idx])
np.maximum.at(asLast, Dn[idx] - asD0, idx)

# multi-TF arrays built from M5: 0=M5 1=M15 2=M30 3=H1 4=H4
TFo = np.zeros((5, n)); TFh = np.zeros((5, n)); TFl = np.zeros((5, n)); TFc = np.zeros((5, n))
TFs = np.zeros((5, n), np.int64); TFe = np.zeros((5, n), np.int64); tfIdx = np.zeros((5, n), np.int64)
for k, P in enumerate((5, 15, 30, 60, 240)):
    key = t5 // P
    stt = np.flatnonzero(np.r_[True, key[1:] != key[:-1]]); enn = np.r_[stt[1:], n] - 1
    m = len(stt)
    TFo[k, :m] = o[stt]; TFh[k, :m] = np.maximum.reduceat(h, stt); TFl[k, :m] = np.minimum.reduceat(l, stt)
    TFc[k, :m] = c[enn]; TFs[k, :m] = stt; TFe[k, :m] = enn
    TFh[k, m:] = 1e18; TFl[k, m:] = -1e18
    tfIdx[k] = np.cumsum(np.r_[True, key[1:] != key[:-1]]) - 1

BASE = dict(risk=1.0, RR=2.0, minRR=1.5, slBuf=0.1, maxSL=3.0, maxTrades=2, maxDL=3.0, BE=1.0, BEplus=0.10,
            partial=50, trail=1, pendExp=12, swS=3, look=80, setupExp=20, mssS=2, disp=1.0, minFVG=0.15,
            fvgWait=3, entry=1, pd=1, reqCandle=1, spread=0.30, bal=10000, useBias=1, lon=1, nyk=1, comm=0.0,
            pdhl=1, asia=1, swing=1, pin=1, pinR=2.0, eng=1, star=1, sweepPA=0, paWait=12, mtf=0, mtfMin=0, mtfMax=3, useM1=0)
ORDER = ['risk', 'RR', 'minRR', 'slBuf', 'maxSL', 'maxTrades', 'maxDL', 'BE', 'BEplus', 'partial', 'trail',
         'pendExp', 'swS', 'look', 'setupExp', 'mssS', 'disp', 'minFVG', 'fvgWait', 'entry', 'pd', 'reqCandle',
         'spread', 'bal', 'useBias', 'lon', 'nyk', 'comm', 'pdhl', 'asia', 'swing', 'sweepPA', 'paWait', 'mtf', 'mtfMin', 'mtfMax', 'useM1']


def go(**kw):
    p = dict(BASE, **kw)
    cfg = np.array([p[k] for k in ORDER], float)
    Pc = np.array([p['pin'], p['pinR'], p['eng'], p['star']], float)
    r = run(z['m1t'], z['m1o'], z['m1h'], z['m1l'], t5, o, h, l, c, s5, e5, atr, bias, dayFirst, pdh, pdl,
            asHi, asLo, asLast, asD0, cfg, Pc, TFo, TFh, TFl, TFc, TFs, TFe, tfIdx)
    T = pd.DataFrame(dict(tin=r[0], tout=r[1], dir=r[2], lvl=r[3], R=r[4], pnl=r[5], kz=r[6], mkt=r[7]))
    for k,nm in enumerate(['sw','mi','pl','rsn']): T[nm]=r[11][:,k]
    for k,nm in enumerate(['entry','sl0','tp','top','bot','ext','lvlpx','msspx','xpx']): T[nm]=r[12][:,k]
    T['date'] = pd.to_datetime(T.tin * 60, unit='s')
    return T, r[8], r[9], r[10]


def stats(T, bal0=10000.0):
    if len(T) == 0:
        return dict(n=0)
    R = T.R
    eq = bal0 + T.pnl.cumsum()
    dd = (eq / eq.cummax().clip(lower=bal0) - 1).min()
    gw = T.pnl[T.pnl > 0].sum(); gl = -T.pnl[T.pnl < 0].sum()
    return dict(n=len(T), win=round((R > 0.05).mean() * 100, 1), be=round((R.abs() <= 0.05).mean() * 100, 1),
                avgR=round(R.mean(), 3), sumR=round(R.sum(), 1), PF=round(gw / gl, 2) if gl > 0 else np.inf,
                ret=round((eq.iloc[-1] / bal0 - 1) * 100, 1), maxDD=round(dd * 100, 1),
                tstat=round(R.mean() / R.std() * np.sqrt(len(R)), 2))


if __name__ == '__main__':
    import time
    t0 = time.time()
    T, et, ev, bal = go()
    print('time %.1fs' % (time.time() - t0))
    print(stats(T))
    T.to_csv(D + '/trades_base.csv', index=False)
