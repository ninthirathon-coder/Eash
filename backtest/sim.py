"""Python/numba port of MQL5/Experts/ICT_Candle_EA.mq5 (default inputs) for XAUUSD.
Decisions on M5 close; fills/SL/TP/BE simulated on M1 bars (like MT5 '1 minute OHLC').
Conservative intrabar rules: SL before TP; no TP on the M1 bar an order fills; BE applies from next M1 bar.
Times are 'server' minutes = New York time + 7h (DST aware).
"""
import numpy as np, numba as nb

LVL_PD, LVL_ASIA, LVL_SWING = 0, 1, 2


@nb.njit(cache=True)
def swing_hi(h, j, s, newest):
    # abs index j (ascending time); newer bars must be strictly lower, older bars not higher
    if j - s < 0 or j + s > newest:
        return False
    for k in range(1, s + 1):
        if h[j + k] >= h[j] or h[j - k] > h[j]:
            return False
    return True


@nb.njit(cache=True)
def swing_lo(l, j, s, newest):
    if j - s < 0 or j + s > newest:
        return False
    for k in range(1, s + 1):
        if l[j + k] <= l[j] or l[j - k] < l[j]:
            return False
    return True


@nb.njit(cache=True)
def htf_trend(o, h, l, c, s):
    n = len(c)
    out = np.zeros(n, np.int64)          # trend after bar j closed
    trend = 0; lastSH = 0.0; lastSL = 0.0; shB = True; slB = True
    for j in range(n):
        k = j - s
        if k - s >= 0:
            if swing_hi(h, k, s, j):
                lastSH = h[k]; shB = False
            if swing_lo(l, k, s, j):
                lastSL = l[k]; slB = False
        if not shB and c[j] > lastSH:
            trend = 1; shB = True
        if not slB and c[j] < lastSL:
            trend = -1; slB = True
        out[j] = trend
    return out


@nb.njit(cache=True)
def is_pin(o, h, l, c, i, d, ratio):
    rng = h[i] - l[i]
    if rng <= 0: return False
    body = abs(c[i] - o[i])
    up = h[i] - max(o[i], c[i]); dn = min(o[i], c[i]) - l[i]
    wick = dn if d > 0 else up
    opp = up if d > 0 else dn
    return wick >= ratio * max(body, rng * 0.1) and wick >= 0.55 * rng and opp <= 0.25 * rng


@nb.njit(cache=True)
def is_engulf(o, c, i, d):
    p = i - 1
    cb = d * (c[i] - o[i]); pb = d * (o[p] - c[p])
    if cb <= 0 or pb <= 0: return False
    if d > 0: return c[i] > o[p] and o[i] <= c[p]
    return c[i] < o[p] and o[i] >= c[p]


@nb.njit(cache=True)
def is_star(o, h, l, c, i, d):
    a = i - 2; b = i - 1
    r1 = h[a] - l[a]; b1 = d * (o[a] - c[a])
    if r1 <= 0 or b1 < 0.5 * r1: return False
    if abs(c[b] - o[b]) > 0.3 * b1: return False
    if d * (c[i] - o[i]) <= 0: return False
    mid = (o[a] + c[a]) / 2.0
    return c[i] > mid if d > 0 else c[i] < mid


@nb.njit(cache=True)
def candle(o, h, l, c, i, d, P):
    if i < 2: return False
    if P[0] > 0 and is_pin(o, h, l, c, i, d, P[1]): return True
    if P[2] > 0 and is_engulf(o, c, i, d): return True
    if P[3] > 0 and is_star(o, h, l, c, i, d): return True
    return False


@nb.njit(cache=True)
def run(m1t, m1o, m1h, m1l, m5t, o, h, l, c, m5s, m5e, atr, bias, dayFirst, pdh, pdl,
        asHi, asLo, asLast, asD0, cfg, Pc):
    # cfg: 0 risk%,1 RR,2 minRR,3 slBufATR,4 maxSLATR,5 maxTrades/day,6 maxDailyLoss%,7 BE_R,8 BEplus$,
    #      9 partial%,10 trail(0/1),11 pendExpBars,12 swingS,13 lookback,14 setupExp,15 mssS,16 dispATR,
    #      17 minFVGATR,18 fvgWait,19 entryMode(0 edge,1 CE,2 mkt),20 pdMode(0 off,1 leg),21 reqCandle,
    #      22 spread$,23 startBal,24 useBias,25 londonKZ,26 nyKZ,27 commission$/lot round turn,
    #      28 usePDHL,29 useAsia,30 useSwing
    n = len(c)
    spread = cfg[22]; contract = 100.0
    bal = cfg[23]
    # trade log
    MAXT = 200000
    L_t = np.zeros(MAXT, np.int64); L_x = np.zeros(MAXT, np.int64); L_d = np.zeros(MAXT, np.int64)
    L_lv = np.zeros(MAXT, np.int64); L_R = np.zeros(MAXT); L_pnl = np.zeros(MAXT); L_kz = np.zeros(MAXT, np.int64)
    L_mkt = np.zeros(MAXT, np.int64)
    LI = np.zeros((MAXT, 4), np.int64)   # sweepIdx, mssIdx, placeIdx, reason(0 SL,1 TP,2 SL after BE)
    LF = np.zeros((MAXT, 9))             # entry, sl0, tp, fvgTop, fvgBot, extreme, levelPx, mssPx, exitPx
    nt = 0
    eq_t = np.zeros(n, np.int64); eq_v = np.zeros(n); ne = 0
    # setups [0]=buy [1]=sell
    sAct = np.zeros(2, np.int64); sLvl = np.zeros(2); sLt = np.zeros(2, np.int64); sExt = np.zeros(2)
    sMss = np.zeros(2); sMssDone = np.zeros(2, np.int64); sCand = np.zeros(2, np.int64)
    sIdx = np.zeros(2, np.int64); sAge = np.zeros(2, np.int64); sMAge = np.zeros(2, np.int64); sLeg = np.zeros(2)
    sMI = np.zeros(2, np.int64)
    # order state: 0 none, 1 pending, 2 position
    st = 0; od = 0; oEntry = 0.0; oSL = 0.0; oTP = 0.0; oLots = 0.0; oLots0 = 0.0; oSet = 0; oRisk = 0.0
    oPnl = 0.0; oBE = False; oLvl = 0; oKZ = 0; oFillT = 0; oMkt = 0
    oSw = 0; oMI = 0; oPl = 0; oRsn = 0; oE0 = 0.0; oSL0 = 0.0; oTop = 0.0; oBot = 0.0; oExt = 0.0; oLp = 0.0; oMp = 0.0; oX = 0.0
    curDay = -1; dayTrades = 0; dayPL = 0.0
    swS = int(cfg[12]); look = int(cfg[13]); mssS = int(cfg[15])

    for t in range(30, n - 1):
        # ---------------- 1) intrabar execution on M1 of bar t ----------------
        if st != 0:
            for q in range(m5s[t], m5e[t]):
                bo = m1o[q]; bh = m1h[q]; bl = m1l[q]; tm = m1t[q]
                if st == 1:
                    filled = (bl + spread <= oEntry) if od > 0 else (bh >= oEntry)
                    if not filled:
                        continue
                    st = 2; oFillT = tm
                    dday = tm // 1440
                    if dday != curDay:
                        curDay = dday; dayTrades = 0; dayPL = 0.0
                    dayTrades += 1
                    com = cfg[27] * oLots / 2.0
                    bal -= com; oPnl -= com; dayPL -= com
                    # same-bar SL only (conservative)
                    hitSL = (bl <= oSL) if od > 0 else (bh + spread >= oSL)
                    if hitSL:
                        px = oSL
                        oX = px; oRsn = 0
                        pnl = od * (px - oEntry) * contract * oLots - cfg[27] * oLots / 2.0
                        bal += pnl; oPnl += pnl; dayPL += pnl
                        st = 3
                    else:
                        continue
                if st == 2:
                    if od > 0:
                        hitSL = bl <= oSL; hitTP = bh >= oTP
                        slpx = min(bo, oSL) if bo < oSL else oSL
                    else:
                        hitSL = bh + spread >= oSL; hitTP = bl + spread <= oTP
                        slpx = max(bo + spread, oSL) if bo + spread > oSL else oSL
                    if hitSL or hitTP:
                        px = slpx if hitSL else oTP
                        oX = px
                        oRsn = (2 if oBE else 0) if hitSL else 1
                        pnl = od * (px - oEntry) * contract * oLots - cfg[27] * oLots / 2.0
                        bal += pnl; oPnl += pnl
                        dday = tm // 1440
                        if dday != curDay:
                            curDay = dday; dayTrades = 0; dayPL = 0.0
                        dayPL += pnl
                        st = 3
                    elif (not oBE) and cfg[7] > 0 and tm != oFillT:
                        fav = (bh - oEntry) if od > 0 else (oEntry - (bl + spread))
                        if fav >= cfg[7] * oRisk:
                            oBE = True
                            if cfg[9] > 0:
                                cv = np.floor(oLots * cfg[9] / 100.0 / 0.01 + 1e-9) * 0.01
                                if cv >= 0.01 and oLots - cv >= 0.01 - 1e-9:
                                    px = oEntry + od * cfg[7] * oRisk
                                    pnl = od * (px - oEntry) * contract * cv - cfg[27] * cv / 2.0
                                    bal += pnl; oPnl += pnl
                                    dday = tm // 1440
                                    if dday != curDay:
                                        curDay = dday; dayTrades = 0; dayPL = 0.0
                                    dayPL += pnl
                                    oLots -= cv
                            oSL = oEntry + od * cfg[8]
                if st == 3:
                    L_t[nt] = oFillT; L_x[nt] = tm; L_d[nt] = od; L_lv[nt] = oLvl; L_kz[nt] = oKZ
                    L_pnl[nt] = oPnl; L_R[nt] = oPnl / (oRisk * contract * oLots0); L_mkt[nt] = oMkt
                    LI[nt, 0] = oSw; LI[nt, 1] = oMI; LI[nt, 2] = oPl; LI[nt, 3] = oRsn
                    LF[nt, 0] = oE0; LF[nt, 1] = oSL0; LF[nt, 2] = oTP; LF[nt, 3] = oTop; LF[nt, 4] = oBot
                    LF[nt, 5] = oExt; LF[nt, 6] = oLp; LF[nt, 7] = oMp; LF[nt, 8] = oX
                    nt += 1
                    eq_t[ne] = tm; eq_v[ne] = bal; ne += 1
                    st = 0
                    break

        # ---------------- 2) new bar decision (now = open of bar t+1) ----------------
        now = m5t[t + 1]
        bid = o[t + 1]; ask = bid + spread
        a = atr[t]
        if a <= 0:
            continue
        today = now // 1440
        if today != curDay:
            curDay = today; dayTrades = 0; dayPL = 0.0

        # ManagePendingOrders
        if st == 1:
            exp = cfg[11] > 0 and (now - oSet) > cfg[11] * 5
            ran = (od > 0 and bid >= oTP) or (od < 0 and ask <= oTP)
            if exp or ran:
                st = 0
        # TrailByStructure
        if st == 2 and cfg[10] > 0 and od * (oSL - oEntry) >= 0:
            newSL = 0.0
            for k in range(2, look):
                j = t + 1 - k
                if od > 0 and swing_lo(l, j, swS, t):
                    newSL = l[j] - cfg[3] * a; break
                if od < 0 and swing_hi(h, j, swS, t):
                    newSL = h[j] + cfg[3] * a; break
            if newSL > 0:
                newSL = np.round(newSL, 2)
                px = bid if od > 0 else ask
                if od * (newSL - oSL) > 0.01 and od * (px - newSL) > 0:
                    oSL = newSL

        g_bias = bias[t]

        for d in (1, -1):
            si = 0 if d > 0 else 1
            # ---------------- UpdateSetup ----------------
            for _o in range(1):
                if sAct[si] == 1:
                    sAge[si] += 1
                    if sAge[si] > cfg[14]:
                        sAct[si] = 0
                        break
                    if sMssDone[si] == 0:
                        if (d > 0 and c[t] < sLvl[si]) or (d < 0 and c[t] > sLvl[si]):
                            sAct[si] = 0; break
                        if d > 0 and l[t] < sExt[si]: sExt[si] = l[t]
                        if d < 0 and h[t] > sExt[si]: sExt[si] = h[t]
                        if candle(o, h, l, c, t, d, Pc): sCand[si] = 1
                        broke = c[t] > sMss[si] if d > 0 else c[t] < sMss[si]
                        disp = False
                        if broke:
                            for i in range(3):
                                jj = t - i
                                if jj < sIdx[si]: break
                                body = d * (c[jj] - o[jj]); rng = h[jj] - l[jj]
                                if rng > 0 and body >= cfg[16] * a and body / rng >= 0.5:
                                    disp = True; break
                        if broke and disp:
                            if cfg[21] > 0 and sCand[si] == 0:
                                sAct[si] = 0; break
                            sMssDone[si] = 1; sMAge[si] = 0; sMI[si] = t
                    else:
                        sMAge[si] += 1
                        if (d > 0 and l[t] < sExt[si]) or (d < 0 and h[t] > sExt[si]):
                            sAct[si] = 0; break
                    if d > 0: sLeg[si] = max(sLeg[si], h[t])
                    else: sLeg[si] = min(sLeg[si], l[t])

                    if sMssDone[si] == 1:
                        if sMAge[si] > cfg[18]:
                            sAct[si] = 0; break
                        # ---------------- TryEntry ----------------
                        nyMin = (now - 420) % 1440
                        hr = nyMin / 60.0
                        kz = 0
                        if cfg[25] > 0 and hr >= 2.0 and hr < 5.0: kz = 1
                        if cfg[26] > 0 and hr >= 7.0 and hr < 10.0: kz = 2
                        if cfg[25] == 0 and cfg[26] == 0: kz = 3
                        if kz == 0: break
                        if st != 0: break
                        if cfg[5] > 0 and dayTrades >= cfg[5]: break
                        if cfg[6] > 0:
                            flt = 0.0
                            startBal = bal - dayPL
                            if startBal > 0 and dayPL + flt <= -cfg[6] / 100.0 * startBal: break
                        # FindFVG
                        has = False; top = 0.0; bot = 0.0
                        for i in range(1, 7):
                            mid = t - i            # shift i+1
                            if mid < sIdx[si]: break
                            a1 = t + 1 - i; a3 = t - 1 - i
                            if d > 0:
                                if l[a1] <= h[a3]: continue
                                gT = l[a1]; gB = h[a3]
                            else:
                                if h[a1] >= l[a3]: continue
                                gT = l[a3]; gB = h[a1]
                            if gT - gB < cfg[17] * a: continue
                            if d > 0 and gB <= sExt[si]: continue
                            if d < 0 and gT >= sExt[si]: continue
                            filled = False
                            for k in range(1, i):
                                jj = t + 1 - k
                                if d > 0 and l[jj] <= gB: filled = True
                                if d < 0 and h[jj] >= gT: filled = True
                            if filled: continue
                            has = True; top = gT; bot = gB; break
                        mkt = ask if d > 0 else bid
                        em = int(cfg[19])
                        if em == 2:
                            entry = mkt
                        else:
                            if not has: break
                            entry = (top if d > 0 else bot) if em == 0 else (top + bot) / 2.0
                        if cfg[20] == 1 and em != 2:
                            eqp = (sExt[si] + sLeg[si]) / 2.0
                            if d > 0:
                                if bot > eqp: break
                                entry = min(entry, eqp)
                            else:
                                if top < eqp: break
                                entry = max(entry, eqp)
                        sl = sExt[si] - d * cfg[3] * a
                        isM = em == 2 or (ask <= entry if d > 0 else bid >= entry)
                        if isM: entry = mkt
                        entry = np.round(entry, 2); sl = np.round(sl, 2)
                        risk = d * (entry - sl)
                        if risk <= 0:
                            sAct[si] = 0; break
                        if risk > cfg[4] * a:
                            sAct[si] = 0; break
                        tp = entry + d * cfg[1] * risk
                        if d * (tp - entry) / risk < cfg[2] - 1e-9: break
                        tp = np.round(tp, 2)
                        lots = np.floor(bal * cfg[0] / 100.0 / (risk * contract) / 0.01 + 1e-9) * 0.01
                        if lots < 0.01:
                            sAct[si] = 0; break
                        if not isM and d * (mkt - entry) <= 0: break
                        od = d; oEntry = entry; oSL = sl; oTP = tp; oLots = lots; oLots0 = lots; oSet = now
                        oRisk = risk; oPnl = 0.0; oBE = False; oLvl = sLt[si]; oKZ = kz; oMkt = 1 if isM else 0
                        oSw = sIdx[si]; oMI = sMI[si]; oPl = t + 1; oE0 = entry; oSL0 = sl; oTop = top; oBot = bot; oExt = sExt[si]; oLp = sLvl[si]; oMp = sMss[si]
                        if isM:
                            st = 2; oFillT = now
                            dayTrades += 1
                            com = cfg[27] * oLots / 2.0
                            bal -= com; oPnl -= com; dayPL -= com
                        else:
                            st = 1
                        sAct[si] = 0
                    break

            if sAct[si] == 1:
                continue
            # ---------------- DetectSweep ----------------
            if cfg[24] > 0 and g_bias != d:
                continue
            found = False; best = 0.0; bestT = 0
            # PDH/PDL
            if cfg[28] > 0:
                f0 = dayFirst[t + 1]          # first M5 index of today
                if f0 >= 0 and f0 <= t and pdh[t + 1] > 0:
                    L = pdl[t + 1] if d > 0 else pdh[t + 1]
                    sw = (l[t] < L and c[t] > L) if d > 0 else (h[t] > L and c[t] < L)
                    if sw:
                        fresh = True
                        for jj in range(f0, t):
                            if (d > 0 and l[jj] < L) or (d < 0 and h[jj] > L):
                                fresh = False; break
                        if fresh:
                            found = True; best = L; bestT = LVL_PD
            # Asian range
            if cfg[29] > 0:
                Dn = (now - 420) // 1440 - asD0
                if Dn >= 0 and Dn < len(asLast) and asLast[Dn] >= 0 and asLast[Dn] <= t and t + 1 - asLast[Dn] < 400:
                    L = asLo[Dn] if d > 0 else asHi[Dn]
                    sw = (l[t] < L and c[t] > L) if d > 0 else (h[t] > L and c[t] < L)
                    if sw:
                        fresh = True
                        for jj in range(asLast[Dn] + 1, t):
                            if (d > 0 and l[jj] < L) or (d < 0 and h[jj] > L):
                                fresh = False; break
                        if fresh and ((not found) or (d > 0 and L < best) or (d < 0 and L > best)):
                            found = True; best = L; bestT = LVL_ASIA
            # swings
            if cfg[30] > 0:
                for k in range(swS + 2, look + 1):
                    j = t + 1 - k
                    if d > 0:
                        if not swing_lo(l, j, swS, t): continue
                        L = l[j]
                        if not (l[t] < L and c[t] > L): continue
                    else:
                        if not swing_hi(h, j, swS, t): continue
                        L = h[j]
                        if not (h[t] > L and c[t] < L): continue
                    fresh = True
                    for jj in range(j + 1, t):
                        if (d > 0 and l[jj] < L) or (d < 0 and h[jj] > L):
                            fresh = False; break
                    if fresh and ((not found) or (d > 0 and L < best) or (d < 0 and L > best)):
                        found = True; best = L; bestT = LVL_SWING
            if not found:
                continue
            # FindMSSLevel
            mss = 0.0
            for k in range(2, look + 1):
                j = t + 1 - k
                if d > 0 and swing_hi(h, j, mssS, t) and h[j] > c[t]:
                    mss = h[j]; break
                if d < 0 and swing_lo(l, j, mssS, t) and l[j] < c[t]:
                    mss = l[j]; break
            if mss == 0.0:
                v = -1e18 if d > 0 else 1e18
                for k in range(2, 7):
                    j = t + 1 - k
                    v = max(v, h[j]) if d > 0 else min(v, l[j])
                if (d > 0 and v > c[t]) or (d < 0 and v < c[t]): mss = v
            if mss == 0.0:
                continue
            sAct[si] = 1; sLvl[si] = best; sLt[si] = bestT
            sExt[si] = l[t] if d > 0 else h[t]
            sMss[si] = mss; sMssDone[si] = 0; sIdx[si] = t; sAge[si] = 0; sMAge[si] = 0
            sLeg[si] = h[t] if d > 0 else l[t]
            sCand[si] = 1 if candle(o, h, l, c, t, d, Pc) else 0

    return (L_t[:nt], L_x[:nt], L_d[:nt], L_lv[:nt], L_R[:nt], L_pnl[:nt], L_kz[:nt], L_mkt[:nt],
            eq_t[:ne], eq_v[:ne], bal, LI[:nt], LF[:nt])
