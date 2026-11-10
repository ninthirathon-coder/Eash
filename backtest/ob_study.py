"""Event study: first touch of a fresh (unmitigated, never-wicked) order block -> does price reach the nearest swing?
Bullish OB = last bearish candle (within 5 bars) before a displacement candle (body >= dispATR*ATR) that closes above the
latest confirmed swing high (BOS). Zone = OB candle high..low. Bearish mirrored.
Trade model: limit at the zone edge (OB high for buys), SL = OB low - 0.1 ATR, TP = nearest confirmed swing high above
entry at touch time. Resolved on the same TF bars; a bar that hits both SL and TP counts as SL. Spread charged."""
import sys, numpy as np, pandas as pd, numba as nb
from sim import swing_hi, swing_lo


@nb.njit(cache=True)
def study(t, o, h, l, c, atr, s, disp, maxAge, spread, touchNo, closeInv=0):
    n = len(c)
    out = np.zeros((200000, 9)); k = 0     # time, dir, R, hitTP, risk, rr, formIdx, touchIdx, kz-hour(NY)
    lastSH = 0.0; lastSL = 0.0
    for i in range(2 * s + 2, n - 1):
        # confirmed swings (bar i-s confirmed at bar i)
        if swing_hi(h, i - s, s, i): lastSH = h[i - s]
        if swing_lo(l, i - s, s, i): lastSL = l[i - s]
        a = atr[i]
        if a <= 0: continue
        for d in (1, -1):
            body = d * (c[i] - o[i])
            if body < disp * a: continue
            if d > 0 and not (lastSH > 0 and c[i] > lastSH and o[i] <= lastSH): continue
            if d < 0 and not (lastSL > 0 and c[i] < lastSL and o[i] >= lastSL): continue
            j = -1
            for q in range(i - 1, max(i - 6, 0), -1):
                if d * (c[q] - o[q]) < 0: j = q; break
            if j < 0: continue
            zT = h[j]; zB = l[j]
            # price must have left the zone completely after the OB candle
            ok = True
            for q in range(j + 1, i + 1):
                if (d > 0 and l[q] <= zT and q > j + 1) or (d < 0 and h[q] >= zB and q > j + 1): ok = False; break
            if not ok: continue
            # walk forward: find the touchNo-th touch of the zone
            touches = 0; inside = False
            for q in range(i + 1, min(i + 1 + maxAge, n - 1)):
                hit = (l[q] <= zT) if d > 0 else (h[q] + spread >= zB)
                broke = (c[q] < zB) if d > 0 else (c[q] > zT)
                if hit and not inside:
                    touches += 1; inside = True
                    if touches == touchNo:
                        entry = zT + (spread if d > 0 else 0.0) if d > 0 else zB
                        sl = zB - 0.1 * a if d > 0 else zT + 0.1 * a + spread
                        risk = d * (entry - sl)
                        if risk <= 0: break
                        # nearest confirmed swing (at touch time) beyond entry
                        tp = 0.0
                        for r in range(q - s, max(q - 400, s), -1):
                            if d > 0 and swing_hi(h, r, s, q) and h[r] > entry + 0.1 * a: tp = h[r]; break
                            if d < 0 and swing_lo(l, r, s, q) and l[r] + spread < entry - 0.1 * a: tp = l[r] + spread; break
                        if tp == 0.0: break
                        # resolve: the touch bar itself only checks SL (conservative)
                        res = 0.0; got = -1
                        if closeInv == 0 and ((d > 0 and l[q] <= sl) or (d < 0 and h[q] + spread >= sl)):
                            res = -1.0; got = 0
                        else:
                            for u in range(q + 1, min(q + 2000, n)):
                                if closeInv == 1: sh_ = (c[u] < zB) if d > 0 else (c[u] > zT)
                                else: sh_ = (l[u] <= sl) if d > 0 else (h[u] + spread >= sl)
                                tp_ = (h[u] >= tp) if d > 0 else (l[u] + spread <= tp)
                                if sh_: res = -1.0; got = 0; break
                                if tp_: res = d * (tp - entry) / risk; got = 1; break
                        if got >= 0 and k < 200000:
                            out[k, 0] = t[q]; out[k, 1] = d; out[k, 2] = res; out[k, 3] = got; out[k, 4] = risk
                            out[k, 5] = d * (tp - entry) / risk; out[k, 6] = j; out[k, 7] = q
                            out[k, 8] = ((t[q] - 420) % 1440) / 60.0
                            k += 1
                        break
                if not hit: inside = False
                if broke: break
    return out[:k]


def agg(z, P):
    t = z['m1t']; key = t // P
    st = np.flatnonzero(np.r_[True, key[1:] != key[:-1]]); en = np.r_[st[1:], len(t)] - 1
    return key[st] * P, z['m1o'][st], np.maximum.reduceat(z['m1h'], st), np.minimum.reduceat(z['m1l'], st), z['m1c'][en]


def atr_sma(h, l, c, p=14):
    pc = np.r_[c[0], c[:-1]]
    tr = np.maximum(h - l, np.maximum(abs(h - pc), abs(l - pc)))
    return pd.Series(tr).rolling(p).mean().fillna(0).to_numpy()


if __name__ == '__main__':
    z = np.load('data.npz')
    rows = []
    for name, P in [('M5', 5), ('M15', 15), ('H1', 60)]:
        t, o, h, l, c = agg(z, P); a = atr_sma(h, l, c)
        for tn in (1, 2):
            E = study(t, o, h, l, c, a, 3, 1.0, 500, 0.30, tn)
            D = pd.DataFrame(E, columns=['t', 'dir', 'R', 'tp', 'risk', 'rr', 'j', 'q', 'hr'])
            D['year'] = pd.to_datetime(D.t * 60, unit='s').dt.year
            kz = ((D.hr >= 2) & (D.hr < 5)) | ((D.hr >= 7) & (D.hr < 10))
            def s_(x): return (len(x), round(100 * x.tp.mean(), 1) if len(x) else 0, round(x.R.mean(), 3) if len(x) else 0)
            rows.append(dict(TF=name, แตะครั้งที่=tn, n=len(D), ถึงswing=f'{100 * D.tp.mean():.1f}%', RRแผนกลาง=round(D.rr.median(), 2),
                             เฉลี่ยR=round(D.R.mean(), 3), t=round(D.R.mean() / D.R.std() * np.sqrt(len(D)), 1),
                             ปีคี่=round(D[D.year % 2 == 1].R.mean(), 3), ปีคู่=round(D[D.year % 2 == 0].R.mean(), 3),
                             ในKZ=s_(D[kz]), นอกKZ=s_(D[~kz])))
    pd.set_option('display.width', 250); print(pd.DataFrame(rows).to_string(index=False))


from sim import candle


@nb.njit(cache=True)
def study_pa(t, o, h, l, c, atr, s, disp, maxAge, spread, Pc, paWin, slMode):
    """First touch of a fresh OB, then wait up to paWin bars for a PA candle that wicks into the OB and closes back
    outside it (not through). Enter at the next bar's open. slMode 0: beyond the OB, 1: beyond the PA candle wick."""
    n = len(c)
    out = np.zeros((200000, 7)); k = 0
    lastSH = 0.0; lastSL = 0.0
    for i in range(2 * s + 2, n - 2):
        if swing_hi(h, i - s, s, i): lastSH = h[i - s]
        if swing_lo(l, i - s, s, i): lastSL = l[i - s]
        a = atr[i]
        if a <= 0: continue
        for d in (1, -1):
            if d * (c[i] - o[i]) < disp * a: continue
            if d > 0 and not (lastSH > 0 and c[i] > lastSH and o[i] <= lastSH): continue
            if d < 0 and not (lastSL > 0 and c[i] < lastSL and o[i] >= lastSL): continue
            j = -1
            for q in range(i - 1, max(i - 6, 0), -1):
                if d * (c[q] - o[q]) < 0: j = q; break
            if j < 0: continue
            zT = h[j]; zB = l[j]
            ok = True
            for q in range(j + 2, i + 1):
                if (d > 0 and l[q] <= zT) or (d < 0 and h[q] >= zB): ok = False; break
            if not ok: continue
            q0 = -1
            for q in range(i + 1, min(i + 1 + maxAge, n - 2)):
                if (d > 0 and l[q] <= zT) or (d < 0 and h[q] >= zB): q0 = q; break
            if q0 < 0: continue
            # wait for PA confirmation at the OB
            u0 = -1
            for u in range(q0, min(q0 + paWin, n - 2)):
                if (d > 0 and c[u] < zB) or (d < 0 and c[u] > zT): break          # closed through: zone failed
                inz = (l[u] <= zT) if d > 0 else (h[u] >= zB)
                if inz and candle(o, h, l, c, u, d, Pc): u0 = u; break
            if u0 < 0: continue
            entry = o[u0 + 1] + (spread if d > 0 else 0.0)
            if slMode == 0: sl = zB - 0.1 * a if d > 0 else zT + 0.1 * a + spread
            else: sl = l[u0] - 0.1 * a if d > 0 else h[u0] + 0.1 * a + spread
            risk = d * (entry - sl)
            if risk <= 0: continue
            tp = 0.0
            for r in range(u0 - s, max(u0 - 400, s), -1):
                if d > 0 and swing_hi(h, r, s, u0) and h[r] > entry + 0.1 * a: tp = h[r]; break
                if d < 0 and swing_lo(l, r, s, u0) and l[r] + spread < entry - 0.1 * a: tp = l[r] + spread; break
            if tp == 0.0: continue
            res = 0.0; got = -1
            for v in range(u0 + 1, min(u0 + 2000, n)):
                hs = (l[v] <= sl) if d > 0 else (h[v] + spread >= sl)
                ht = (h[v] >= tp) if d > 0 else (l[v] + spread <= tp)
                if v == u0 + 1: ht = False                                         # no TP on the fill bar
                if hs: res = -1.0; got = 0; break
                if ht: res = d * (tp - entry) / risk; got = 1; break
            if got >= 0 and k < 200000:
                out[k, 0] = t[u0 + 1]; out[k, 1] = d; out[k, 2] = res; out[k, 3] = got; out[k, 4] = risk
                out[k, 5] = d * (tp - entry) / risk; out[k, 6] = ((t[u0 + 1] - 420) % 1440) / 60.0
                k += 1
    return out[:k]
