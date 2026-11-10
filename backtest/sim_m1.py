"""Top-down model: HTF (H1/H4 swings, PDH/PDL) defines the zones; M1 decides whether the zone reacts.
Every decision on M1 close; execution on following M1 bars (SL before TP, BE from next bar).
Times: server minutes (NY + 7h)."""
import numpy as np, numba as nb
from sim import swing_hi, swing_lo, candle, htf_trend



@nb.njit(cache=True)
def logev(E, ne, t_sweep, t_end, code, d, lvl, tf):
    if ne < E.shape[0]:
        E[ne, 0] = t_sweep; E[ne, 1] = t_end; E[ne, 2] = code; E[ne, 3] = d; E[ne, 4] = lvl; E[ne, 5] = tf
    return ne + 1

@nb.njit(cache=True)
def run_m1(t1, o, h, l, c, atr1, atr5, h1c_at, h4c_at, dayStart, pdh, pdl,
           H1h, H1l, H4h, H4l, b1, b4, cfg, Pc, aH1, aH4, H1st, H4st, prevDS, h1gid, h4gid,
           H1en, H4en, prevDE, wStart, pwh, pwl, prevWS, prevWE, mOpen, dBias, agL, agH):
    # cfg: 0 risk%,1 RR,2 slBufATR1,3 maxDepthATR5,4 maxTrades/day,5 BE_R,6 BEplus,7 partial%,8 setupExp(M1 bars),
    # 9 mssS,10 dispATR1,11 minFVGATR1,12 fvgWait,13 paWait,14 entryMode(0 FVG+PA, 1 market at MSS),
    # 15 spread,16 startBal,17 biasMode(0 none,1 H1,2 H4,3 both),18 lon,19 ny,20 useH1,21 useH4,22 usePD,
    # 23 maxSpreadRatio (spread/risk), 24 maxSLATR5, 25 sweepPAbars(M1, 0=off)
    n = len(c)
    spread = cfg[15]; contract = 100.0; bal = cfg[16]
    MAXT = 100000
    L_t = np.zeros(MAXT, np.int64); L_x = np.zeros(MAXT, np.int64); L_d = np.zeros(MAXT, np.int64)
    L_tf = np.zeros(MAXT, np.int64); L_R = np.zeros(MAXT); L_pnl = np.zeros(MAXT); L_kz = np.zeros(MAXT, np.int64)
    L_risk = np.zeros(MAXT); L_ent = np.zeros(MAXT); L_sl = np.zeros(MAXT); L_tp = np.zeros(MAXT); L_lvl = np.zeros(MAXT)
    L_tp1 = np.zeros(MAXT); L_mss = np.zeros(MAXT); oMssP = 0.0
    L_kind = np.zeros(MAXT, np.int64); oKind = 0
    cA = np.zeros(2, np.int64); cExt = np.zeros(2); cL = np.zeros(2); cTF = np.zeros(2, np.int64); cF = np.zeros(2, np.int64)
    cEI = np.zeros(2, np.int64); cLeg = np.zeros(2); cPL = np.zeros(2); cAge = np.zeros(2, np.int64); cPh = np.zeros(2, np.int64)
    cBI = np.zeros(2, np.int64); cMA = np.zeros(2, np.int64); cZT = np.zeros(2); cZB = np.zeros(2); cZA = np.zeros(2, np.int64)
    cSw = np.zeros(2, np.int64); cHi = np.zeros(2)
    L_sw = np.zeros(MAXT, np.int64); L_mi = np.zeros(MAXT, np.int64); L_zt = np.zeros(MAXT); L_zb = np.zeros(MAXT)
    nt = 0
    # active HTF levels: side 0 = lows (sell-side liquidity), 1 = highs
    CAP = 64
    lvP = np.zeros((2, CAP)); lvT = np.zeros((2, CAP), np.int64); nl = np.zeros(2, np.int64)
    lvF = np.zeros((2, CAP), np.int64)   # M1 index where the level was formed
    lvE = np.zeros((2, CAP), np.int64); lvQ = np.zeros((2, CAP), np.int64)
    sF = np.zeros(2, np.int64); sFE = np.zeros(2, np.int64); sLg = np.zeros(2)
    oTP1 = 0.0; oT1 = False
    # setups
    sA = np.zeros(2, np.int64); sL = np.zeros(2); sTF = np.zeros(2, np.int64); sExt = np.zeros(2); sEI = np.zeros(2, np.int64)
    sAge = np.zeros(2, np.int64); sPh = np.zeros(2, np.int64); sMss = np.zeros(2); sMA = np.zeros(2, np.int64)
    sZT = np.zeros(2); sZB = np.zeros(2); sZA = np.zeros(2, np.int64); sCand = np.zeros(2, np.int64); sSw = np.zeros(2, np.int64)
    sMI = np.zeros(2, np.int64)
    rej = np.zeros(30, np.int64); sBlk = np.zeros(2, np.int64)
    EV = np.zeros((60000, 6)); ne2 = 0
    # position
    st = 0; od = 0; oE = 0.0; oSL = 0.0; oTP = 0.0; oLots = 0.0; oLots0 = 0.0; oRisk = 0.0; oPnl = 0.0; oBE = False
    oFill = 0; oTF = 0; oKZ = 0; oL = 0.0; oSw = 0; oMI = 0; oZT = 0.0; oZB = 0.0
    curDay = -1; dayTrades = 0; dayPL = 0.0
    mssS = int(cfg[9])

    for t in range(300, n - 1):
        if cfg[34] > 0:
            spread = cfg[34] * c[t]          # spread as a fraction of price
        # ---------------- execution on bar t ----------------
        if st == 2 and t > oFill:
            bo = o[t]; bh = h[t]; bl = l[t]
            if od > 0:
                hitSL = bl <= oSL; hitTP = bh >= oTP
                slpx = bo if bo < oSL else oSL
            else:
                hitSL = bh + spread >= oSL; hitTP = bl + spread <= oTP
                slpx = bo + spread if bo + spread > oSL else oSL
            closed = False
            if hitSL or hitTP:
                px = slpx if hitSL else oTP
                pnl = od * (px - oE) * contract * oLots
                bal += pnl; oPnl += pnl; dayPL += pnl; closed = True
            elif (not oT1) and ((od > 0 and bh >= oTP1) or (od < 0 and bl + spread <= oTP1)):
                oT1 = True; oBE = True
                cv = np.floor(oLots * cfg[50] / 100.0 / 0.01 + 1e-9) * 0.01
                if cv >= 0.01 and oLots - cv >= 0.01 - 1e-9:
                    pnl = od * (oTP1 - oE) * contract * cv
                    bal += pnl; oPnl += pnl; dayPL += pnl; oLots -= cv
                oSL = oE + od * cfg[6]
            elif oBE and cfg[41] > 0:
                # trail behind the latest confirmed M1 swing after break-even
                ts2 = int(cfg[41])
                for j in range(t - ts2, t - 200, -1):
                    if od > 0 and swing_lo(l, j, ts2, t):
                        nsl = l[j] - 0.5 * atr1[t]
                        if nsl > oSL: oSL = nsl
                        break
                    if od < 0 and swing_hi(h, j, ts2, t):
                        nsl = h[j] + 0.5 * atr1[t] + spread
                        if nsl < oSL: oSL = nsl
                        break
            elif (not oBE) and cfg[5] > 0 and cfg[48] == 0 and t > oFill + 0:
                fav = (bh - oE) if od > 0 else (oE - (bl + spread))
                if fav >= cfg[5] * oRisk:
                    oBE = True
                    if cfg[7] > 0:
                        cv = np.floor(oLots * cfg[7] / 100.0 / 0.01 + 1e-9) * 0.01
                        if cv >= 0.01 and oLots - cv >= 0.01 - 1e-9:
                            pnl = cfg[5] * oRisk * contract * cv
                            bal += pnl; oPnl += pnl; dayPL += pnl; oLots -= cv
                    oSL = oE + od * cfg[6]
            if closed:
                L_t[nt] = t1[oFill]; L_x[nt] = t1[t]; L_d[nt] = od; L_tf[nt] = oTF; L_kz[nt] = oKZ
                L_pnl[nt] = oPnl; L_R[nt] = oPnl / (oRisk * contract * oLots0); L_risk[nt] = oRisk
                L_ent[nt] = oE; L_sl[nt] = oSL if not oBE else oE - od * oRisk; L_tp[nt] = oTP; L_lvl[nt] = oL
                L_tp1[nt] = oTP1; L_mss[nt] = oMssP; L_kind[nt] = oKind; L_sw[nt] = oSw; L_mi[nt] = oMI; L_zt[nt] = oZT; L_zb[nt] = oZB
                nt += 1; st = 0

        now = t1[t + 1]
        today = now // 1440
        if today != curDay:
            curDay = today; dayTrades = 0; dayPL = 0.0
        a1 = atr1[t]; a5 = atr5[t]
        if a1 <= 0 or a5 <= 0:
            continue

        # ---------------- update HTF levels ----------------
        if cfg[22] > 0 and dayStart[t + 1] == t + 1 and pdh[t + 1] > 0:
            for sd in range(2):
                if nl[sd] == CAP:
                    for q in range(CAP - 1): lvP[sd, q] = lvP[sd, q + 1]; lvT[sd, q] = lvT[sd, q + 1]; lvF[sd, q] = lvF[sd, q + 1]; lvE[sd, q] = lvE[sd, q + 1]; lvQ[sd, q] = lvQ[sd, q + 1]
                    nl[sd] -= 1
                lvP[sd, nl[sd]] = pdl[t + 1] if sd == 0 else pdh[t + 1]; lvT[sd, nl[sd]] = 3; lvF[sd, nl[sd]] = prevDS[t + 1]; lvE[sd, nl[sd]] = prevDE[t + 1]; lvQ[sd, nl[sd]] = 0; nl[sd] += 1
        if cfg[44] > 0 and wStart[t + 1] == t + 1 and pwh[t + 1] > 0:
            for sd in range(2):
                if nl[sd] == CAP:
                    for q in range(CAP - 1): lvP[sd, q] = lvP[sd, q + 1]; lvT[sd, q] = lvT[sd, q + 1]; lvF[sd, q] = lvF[sd, q + 1]; lvE[sd, q] = lvE[sd, q + 1]; lvQ[sd, q] = lvQ[sd, q + 1]
                    nl[sd] -= 1
                lvP[sd, nl[sd]] = pwl[t + 1] if sd == 0 else pwh[t + 1]; lvT[sd, nl[sd]] = 5
                lvF[sd, nl[sd]] = prevWS[t + 1]; lvE[sd, nl[sd]] = prevWE[t + 1]; lvQ[sd, nl[sd]] = 0; nl[sd] += 1
        for tf in range(2):
            use = cfg[20] if tf == 0 else cfg[21]
            g = h1c_at[t] if tf == 0 else h4c_at[t]
            if use <= 0 or g < 0: continue
            k = g - 3
            if k < 3: continue
            HH = H1h if tf == 0 else H4h
            LL = H1l if tf == 0 else H4l
            for sd in range(2):
                ok = swing_lo(LL, k, 3, g) if sd == 0 else swing_hi(HH, k, 3, g)
                if not ok: continue
                P = LL[k] if sd == 0 else HH[k]
                # still untouched by the current M1 bar?
                if (sd == 0 and l[t] < P) or (sd == 1 and h[t] > P): continue
                if nl[sd] == CAP:
                    for q in range(CAP - 1): lvP[sd, q] = lvP[sd, q + 1]; lvT[sd, q] = lvT[sd, q + 1]; lvF[sd, q] = lvF[sd, q + 1]; lvE[sd, q] = lvE[sd, q + 1]; lvQ[sd, q] = lvQ[sd, q + 1]
                    nl[sd] -= 1
                eq = 0
                tol = cfg[43] * (aH1[t] if tf == 0 else aH4[t])
                for q in range(nl[sd]):
                    if lvT[sd, q] == 1 + tf and abs(lvP[sd, q] - P) <= tol:
                        eq = 1; lvQ[sd, q] = 1
                lvP[sd, nl[sd]] = P; lvT[sd, nl[sd]] = 1 + tf; lvF[sd, nl[sd]] = H1st[k] if tf == 0 else H4st[k]
                lvE[sd, nl[sd]] = H1en[k] if tf == 0 else H4en[k]; lvQ[sd, nl[sd]] = eq; nl[sd] += 1

        # ---------------- zones taken this bar -> new setups ----------------
        for sd in range(2):
            d = 1 if sd == 0 else -1          # lows swept -> buy setup
            best = 0.0; bt = 0; fnd = False; bf = 0; be = 0; bq = 0
            q = 0
            while q < nl[sd]:
                P = lvP[sd, q]
                if (sd == 0 and l[t] < P) or (sd == 1 and h[t] > P):
                    if (not fnd) or (d > 0 and P < best) or (d < 0 and P > best) or (P == best and lvT[sd, q] > bt):
                        best = P; bt = lvT[sd, q]; fnd = True; bf = lvF[sd, q]; be = lvE[sd, q]; bq = lvQ[sd, q]
                    for r in range(q, nl[sd] - 1):
                        lvP[sd, r] = lvP[sd, r + 1]; lvT[sd, r] = lvT[sd, r + 1]; lvF[sd, r] = lvF[sd, r + 1]; lvE[sd, r] = lvE[sd, r + 1]; lvQ[sd, r] = lvQ[sd, r + 1]
                    nl[sd] -= 1
                else:
                    q += 1
            if fnd: rej[0] += 1
            if fnd and sA[sd] == 1:
                rej[1] += 1; ne2 = logev(EV, ne2, t1[t], t1[t], 1, 1 if sd == 0 else -1, best, bt)
            if not fnd or sA[sd] == 1:
                continue
            bm = int(cfg[17])
            if bm == 1 or bm == 3:
                if b1[t] != d: continue
            if bm == 2 or bm == 3:
                if b4[t] != d: continue
            if cfg[42] > 0 and bt == 1 and bq == 0: continue          # H1 zone must be equal highs/lows
            if cfg[47] == 1 and dBias[t] != d: continue               # daily bias strict
            if cfg[47] == 2 and dBias[t] == -d: continue              # daily bias loose
            sFE[sd] = be; sBlk[sd] = 0
            sA[sd] = 1; sF[sd] = bf; sL[sd] = best; sTF[sd] = bt; sExt[sd] = l[t] if d > 0 else h[t]; sEI[sd] = t
            sAge[sd] = -1; sPh[sd] = 0; sMss[sd] = 0.0; sCand[sd] = 0; sSw[sd] = t

        # ---------------- progress setups on M1 ----------------
        for sd in range(2):
            if sA[sd] == 0: continue
            d = 1 if sd == 0 else -1
            sAge[sd] += 1
            if sAge[sd] == 0: sLg[sd] = h[t] if d > 0 else l[t]
            if (d > 0 and l[t] < sExt[sd]) or (d < 0 and h[t] > sExt[sd]):
                sLg[sd] = h[t] if d > 0 else l[t]
            sLg[sd] = max(sLg[sd], h[t]) if d > 0 else min(sLg[sd], l[t])
            if sPh[sd] == 0:
                if sAge[sd] > cfg[8]:
                    sA[sd] = 0; rej[3] += 1; ne2 = logev(EV, ne2, t1[sSw[sd]], t1[t], 3, d, sL[sd], sTF[sd]); continue
                if (d > 0 and l[t] < sExt[sd]) or (d < 0 and h[t] > sExt[sd]):
                    sExt[sd] = l[t] if d > 0 else h[t]; sEI[sd] = t; sMss[sd] = 0.0
                if d * (sL[sd] - sExt[sd]) > cfg[3] * a5:
                    sA[sd] = 0; rej[4] += 1; ne2 = logev(EV, ne2, t1[sSw[sd]], t1[t], 4, d, sL[sd], sTF[sd]); continue                   # too deep = real breakout, not a sweep
                if candle(o, h, l, c, t, d, Pc) and (cfg[25] <= 0 or t - sEI[sd] <= cfg[25]):
                    sCand[sd] = 1
                if sMss[sd] == 0.0:
                    for j in range(sEI[sd] - 1, sEI[sd] - 120, -1):
                        if d > 0 and swing_hi(h, j, mssS, t) and h[j] > sL[sd]:
                            sMss[sd] = h[j]; break
                        if d < 0 and swing_lo(l, j, mssS, t) and l[j] < sL[sd]:
                            sMss[sd] = l[j]; break
                    if sMss[sd] == 0.0 and cfg[14] != 2: continue
                reclaimed = c[t] > sL[sd] if d > 0 else c[t] < sL[sd]
                if cfg[14] == 2:
                    if not reclaimed: continue
                    sPh[sd] = 1; sMA[sd] = 0; sMI[sd] = t       # no M1 confirmation: enter on reclaim
                else:
                    broke = c[t] > sMss[sd] if d > 0 else c[t] < sMss[sd]
                    if not (reclaimed and broke): continue
                disp = False
                for i in range(3):
                    jj = t - i
                    if jj < sEI[sd]: break
                    body = d * (c[jj] - o[jj]); rng = h[jj] - l[jj]
                    if rng > 0 and body >= cfg[10] * a1 and body / rng >= 0.5:
                        disp = True; break
                if not disp and cfg[14] != 2: continue
                if cfg[25] > 0 and sCand[sd] == 0 and cfg[14] != 2:
                    sA[sd] = 0; rej[5] += 1; ne2 = logev(EV, ne2, t1[sSw[sd]], t1[t], 5, d, sL[sd], sTF[sd]); continue
                sPh[sd] = 1; sMA[sd] = 0; sMI[sd] = t
                if cfg[14] == 0: continue
            elif sPh[sd] == 1:
                sMA[sd] += 1
                if sMA[sd] > cfg[12]:
                    if cfg[52] > 0 and cA[sd] == 0: cA[sd] = 1; cExt[sd] = sExt[sd]; cL[sd] = sL[sd]; cTF[sd] = sTF[sd]; cF[sd] = sF[sd]; cEI[sd] = sEI[sd]; cLeg[sd] = sLg[sd]; cPL[sd] = 1e18 if d > 0 else -1e18; cAge[sd] = 0; cPh[sd] = 0; cSw[sd] = sSw[sd]
                    sA[sd] = 0; rej[6] += 1; ne2 = logev(EV, ne2, t1[sSw[sd]], t1[t], 6, d, sL[sd], sTF[sd]); continue
                if (d > 0 and l[t] < sExt[sd]) or (d < 0 and h[t] > sExt[sd]):
                    sA[sd] = 0; rej[7] += 1; ne2 = logev(EV, ne2, t1[sSw[sd]], t1[t], 7, d, sL[sd], sTF[sd]); continue
            elif sPh[sd] == 2:
                sZA[sd] += 1
                if sZA[sd] > cfg[13]:
                    if cfg[52] > 0 and cA[sd] == 0: cA[sd] = 1; cExt[sd] = sExt[sd]; cL[sd] = sL[sd]; cTF[sd] = sTF[sd]; cF[sd] = sF[sd]; cEI[sd] = sEI[sd]; cLeg[sd] = sLg[sd]; cPL[sd] = 1e18 if d > 0 else -1e18; cAge[sd] = 0; cPh[sd] = 0; cSw[sd] = sSw[sd]
                    cdx = sBlk[sd] if sBlk[sd] > 0 else 8; rej[cdx] += 1; ne2 = logev(EV, ne2, t1[sSw[sd]], t1[t], cdx, d, sL[sd], sTF[sd]); sA[sd] = 0; continue
                if (d > 0 and (c[t] < sZB[sd] or l[t] < sExt[sd])) or (d < 0 and (c[t] > sZT[sd] or h[t] > sExt[sd])):
                    sA[sd] = 0; rej[9] += 1; ne2 = logev(EV, ne2, t1[sSw[sd]], t1[t], 9, d, sL[sd], sTF[sd]); continue
                touched = l[t] <= sZT[sd] if d > 0 else h[t] >= sZB[sd]
                if not (touched and candle(o, h, l, c, t, d, Pc)): continue

            if sPh[sd] == 1 and cfg[14] == 0:
                # find M1 FVG after the sweep extreme and arm the zone
                for i in range(1, 7):
                    if t - i < sEI[sd]: break
                    a_ = t + 1 - i; b_ = t - 1 - i
                    if d > 0:
                        if l[a_] <= h[b_]: continue
                        gT = l[a_]; gB = h[b_]
                    else:
                        if h[a_] >= l[b_]: continue
                        gT = l[b_]; gB = h[a_]
                    if gT - gB < cfg[11] * a1: continue
                    if (d > 0 and gB <= sExt[sd]) or (d < 0 and gT >= sExt[sd]): continue
                    fl = False
                    for k2 in range(1, i):
                        jj = t + 1 - k2
                        if (d > 0 and l[jj] <= gB) or (d < 0 and h[jj] >= gT): fl = True
                    if fl: continue
                    sPh[sd] = 2; sZT[sd] = gT; sZB[sd] = gB; sZA[sd] = 0
                    break
                continue

            # ---------------- entry ----------------
            hr = ((now - 420) % 1440) / 60.0
            kz = 0
            if cfg[18] > 0 and hr >= cfg[35] and hr < cfg[36]: kz = 1
            if cfg[19] > 0 and hr >= cfg[37] and hr < cfg[38]: kz = 2
            if cfg[18] == 0 and cfg[19] == 0: kz = 3
            if kz == 0: sBlk[sd] = 10; continue
            if st != 0: sBlk[sd] = 11; continue
            dow = ((now - 420) // 1440 + 3) % 7          # NY weekday, Monday = 0
            if dow < 5 and ((int(cfg[39]) >> dow) & 1) == 0: sA[sd] = 0; rej[13] += 1; ne2 = logev(EV, ne2, t1[sSw[sd]], t1[t], 13, d, sL[sd], sTF[sd]); continue
            if cfg[4] > 0 and dayTrades >= cfg[4]: sBlk[sd] = 12; continue
            entry = o[t + 1] + (spread if d > 0 else 0.0)
            if cfg[46] > 0 and mOpen[t + 1] > 0:                       # Power of 3: buy below / sell above NY midnight open
                if (d > 0 and entry > mOpen[t + 1]) or (d < 0 and entry < mOpen[t + 1]): sA[sd] = 0; continue
            if cfg[45] > 0:                                             # OTE: retracement of the displacement leg
                rg = d * (sLg[sd] - sExt[sd])
                if rg <= 0 or d * (sLg[sd] - entry) / rg < cfg[45]: sA[sd] = 0; continue
            if cfg[49] > 0:                                             # SMT gold vs silver
                ps = np.nan
                for jj in range(max(sF[sd], 0), sFE[sd] + 1):
                    v = agL[jj] if d > 0 else agH[jj]
                    if v == v:
                        if ps != ps: ps = v
                        elif (d > 0 and v < ps) or (d < 0 and v > ps): ps = v
                if ps != ps: sA[sd] = 0; continue
                broke2 = False
                for jj in range(sFE[sd] + 1, sEI[sd] + 1):
                    v = agL[jj] if d > 0 else agH[jj]
                    if v == v and ((d > 0 and v < ps) or (d < 0 and v > ps)): broke2 = True; break
                if broke2: sA[sd] = 0; continue                          # silver confirmed the sweep -> no divergence
            # premium / discount
            if cfg[40] == 1 and pdh[t + 1] > 0:
                mid = (pdh[t + 1] + pdl[t + 1]) / 2.0          # previous day range
                if (d > 0 and entry > mid) or (d < 0 and entry < mid): sA[sd] = 0; continue
            elif cfg[40] == 2:
                ex2 = sExt[sd]                                  # dealing range: zone formation -> sweep
                for jj in range(max(sF[sd], 0), sEI[sd] + 1):
                    ex2 = max(ex2, h[jj]) if d > 0 else min(ex2, l[jj])
                mid = (ex2 + sExt[sd]) / 2.0
                if (d > 0 and entry > mid) or (d < 0 and entry < mid): sA[sd] = 0; continue
            sl = sExt[sd] - d * cfg[2] * a1
            if cfg[26] == 1 or cfg[26] == 2:
                az = aH1[t] if sTF[sd] == 1 else aH4[t]
                anchor = sL[sd] if cfg[26] == 1 else sExt[sd]   # 1 = from the zone level, 2 = from the sweep wick
                sl2 = anchor - d * cfg[27] * az
                if d * (sl - sl2) > 0: sl = sl2
            risk = d * (entry - sl)
            if risk <= 0: sA[sd] = 0; continue
            if cfg[51] > 0 and cfg[26] >= 1:
                if risk > cfg[51] * (aH1[t] if sTF[sd] == 1 else aH4[t]): sA[sd] = 0; rej[19] += 1; ne2 = logev(EV, ne2, t1[sSw[sd]], t1[t], 19, d, sL[sd], sTF[sd]); continue
            if cfg[29] > 0:
                # filters judged on the M1-structure SL (selects the same setups), SL actually placed beyond the zone
                r1 = d * (entry - (sExt[sd] - d * cfg[2] * a1))
                if r1 <= 0 or r1 > cfg[24] * a5: sA[sd] = 0; rej[14] += 1; ne2 = logev(EV, ne2, t1[sSw[sd]], t1[t], 14, d, sL[sd], sTF[sd]); continue
                if spread / r1 > cfg[23]: sA[sd] = 0; rej[15] += 1; ne2 = logev(EV, ne2, t1[sSw[sd]], t1[t], 15, d, sL[sd], sTF[sd]); continue
            elif cfg[26] == 1:
                if risk > cfg[28] * (aH1[t] if sTF[sd] == 1 else aH4[t]): sA[sd] = 0; continue
            elif risk > cfg[24] * a5: sA[sd] = 0; continue
            if cfg[29] == 0 and spread / risk > cfg[23]: sA[sd] = 0; continue
            tp = entry + d * cfg[1] * risk
            if cfg[30] == 1:
                # ICT target: opposite edge of the dealing range = extreme between level formation and the sweep
                ex = -1e18 if d > 0 else 1e18
                for jj in range(max(sF[sd], 0), sEI[sd] + 1):
                    ex = max(ex, h[jj]) if d > 0 else min(ex, l[jj] + spread)
                tp = ex - d * cfg[32]
                if d * (tp - entry) / risk < cfg[31]: sA[sd] = 0; rej[16] += 1; ne2 = logev(EV, ne2, t1[sSw[sd]], t1[t], 16, d, sL[sd], sTF[sd]); continue
            elif cfg[30] == 2:
                # ICT target: the last swing (zone TF; PDH/PDL use H1) BEFORE the reversal = origin of the leg into the sweep
                use4 = sTF[sd] == 2
                HH = H4h if use4 else H1h
                LL = H4l if use4 else H1l
                gS = h4gid[sEI[sd]] if use4 else h1gid[sEI[sd]]     # HTF bar holding the sweep extreme
                ts = int(cfg[33]); tp = 0.0
                for k in range(gS - 1, max(gS - 300, ts) - 1, -1):
                    if d > 0 and swing_hi(HH, k, ts, gS) and HH[k] > entry:
                        tp = HH[k]; break
                    if d < 0 and swing_lo(LL, k, ts, gS) and LL[k] + spread < entry:
                        tp = LL[k] + spread; break
                if tp == 0.0: sA[sd] = 0; rej[16] += 1; ne2 = logev(EV, ne2, t1[sSw[sd]], t1[t], 16, d, sL[sd], sTF[sd]); continue
                tp = tp - d * cfg[32]
                if d * (tp - entry) / risk < cfg[31]: sA[sd] = 0; rej[16] += 1; ne2 = logev(EV, ne2, t1[sSw[sd]], t1[t], 16, d, sL[sd], sTF[sd]); continue
            tp1 = tp
            if cfg[48] > 0:                                             # TP1 = swing, TP2 = dealing-range edge
                ex = -1e18 if d > 0 else 1e18
                for jj in range(max(sF[sd], 0), sEI[sd] + 1):
                    ex = max(ex, h[jj]) if d > 0 else min(ex, l[jj] + spread)
                if d * (ex - tp1) > 0: tp = ex
            lots = np.floor(bal * cfg[0] / 100.0 / (risk * contract) / 0.01 + 1e-9) * 0.01
            if lots < 0.01: sA[sd] = 0; rej[17] += 1; ne2 = logev(EV, ne2, t1[sSw[sd]], t1[t], 17, d, sL[sd], sTF[sd]); continue
            oTP1 = tp1; oT1 = not (cfg[48] > 0 and d * (tp - tp1) > 0)
            st = 2; od = d; oE = entry; oSL = sl; oTP = tp; oLots = lots; oLots0 = lots
            oRisk = risk; oPnl = 0.0; oBE = False; oFill = t + 1; oTF = sTF[sd]; oKZ = kz; oL = sL[sd]
            oSw = sSw[sd]; oMI = sMI[sd]; oZT = sZT[sd]; oZB = sZB[sd]; oMssP = sMss[sd]; oKind = 0
            dayTrades += 1
            sA[sd] = 0; rej[18] += 1; ne2 = logev(EV, ne2, t1[sSw[sd]], t1[t], 18, d, sL[sd], sTF[sd])
            # fill bar: conservative SL check on the fill bar itself
            if (d > 0 and l[t + 1] <= sl) or (d < 0 and h[t + 1] + spread >= sl):
                pnl = -risk * contract * lots
                bal += pnl; oPnl += pnl; dayPL += pnl
                L_t[nt] = t1[t + 1]; L_x[nt] = t1[t + 1]; L_d[nt] = od; L_tf[nt] = oTF; L_kz[nt] = oKZ
                L_pnl[nt] = oPnl; L_R[nt] = -1.0; L_risk[nt] = risk; L_ent[nt] = oE; L_sl[nt] = sl; L_tp[nt] = oTP
                L_lvl[nt] = oL; L_tp1[nt] = oTP1; L_mss[nt] = oMssP; L_kind[nt] = oKind; L_sw[nt] = oSw; L_mi[nt] = oMI; L_zt[nt] = oZT; L_zb[nt] = oZB
                nt += 1; st = 0

        # ================= continuation (trend-follow) after a missed reversal =================
        if cfg[52] > 0:
            for sd in range(2):
                if cA[sd] == 0: continue
                d = 1 if sd == 0 else -1
                cAge[sd] += 1
                if cAge[sd] > cfg[53]: cA[sd] = 0; continue
                if (d > 0 and c[t] < cExt[sd]) or (d < 0 and c[t] > cExt[sd]): cA[sd] = 0; continue   # reversal failed
                if cPh[sd] == 0:
                    if d > 0: cPL[sd] = min(cPL[sd], l[t])
                    else: cPL[sd] = max(cPL[sd], h[t])
                    brk = c[t] > cLeg[sd] if d > 0 else c[t] < cLeg[sd]
                    dsp = False
                    for i in range(3):
                        jj = t - i
                        body = d * (c[jj] - o[jj]); rng = h[jj] - l[jj]
                        if rng > 0 and body >= cfg[10] * a1 and body / rng >= 0.5: dsp = True; break
                    if brk and dsp:
                        cPh[sd] = 1; cBI[sd] = t; cMA[sd] = 0; cHi[sd] = h[t] if d > 0 else l[t]
                    elif (d > 0 and h[t] > cLeg[sd]) or (d < 0 and l[t] < cLeg[sd]):
                        cLeg[sd] = h[t] if d > 0 else l[t]          # new extreme without a clean BOS -> raise the bar
                        cPL[sd] = l[t] if d > 0 else h[t]
                    continue
                if cPh[sd] >= 1:
                    cHi[sd] = max(cHi[sd], h[t]) if d > 0 else min(cHi[sd], l[t])     # extreme of the BOS leg
                if cPh[sd] == 1:
                    cMA[sd] += 1
                    if cMA[sd] > cfg[12]: cA[sd] = 0; continue
                    for i in range(1, 7):
                        a_ = t + 1 - i; b_ = t - 1 - i
                        if d > 0:
                            if l[a_] <= h[b_]: continue
                            gT = l[a_]; gB = h[b_]
                        else:
                            if h[a_] >= l[b_]: continue
                            gT = l[b_]; gB = h[a_]
                        if gT - gB < cfg[11] * a1: continue
                        if (d > 0 and gB <= cPL[sd]) or (d < 0 and gT >= cPL[sd]): continue
                        fl = False
                        for k2 in range(1, i):
                            jj = t + 1 - k2
                            if (d > 0 and l[jj] <= gB) or (d < 0 and h[jj] >= gT): fl = True
                        if fl: continue
                        cPh[sd] = 2; cZT[sd] = gT; cZB[sd] = gB; cZA[sd] = 0
                        break
                    continue
                # phase 2: pullback into the BOS FVG + PA
                cZA[sd] += 1
                if cZA[sd] > cfg[13]: cA[sd] = 0; continue
                if (d > 0 and c[t] < cZB[sd]) or (d < 0 and c[t] > cZT[sd]): cA[sd] = 0; continue
                touched = l[t] <= cZT[sd] if d > 0 else h[t] >= cZB[sd]
                if not (touched and candle(o, h, l, c, t, d, Pc)): continue
                hr = ((now - 420) % 1440) / 60.0
                kz = 0
                if cfg[18] > 0 and hr >= cfg[35] and hr < cfg[36]: kz = 1
                if cfg[19] > 0 and hr >= cfg[37] and hr < cfg[38]: kz = 2
                if cfg[18] == 0 and cfg[19] == 0: kz = 3
                if kz == 0 or st != 0: continue
                dow = ((now - 420) // 1440 + 3) % 7
                if dow < 5 and ((int(cfg[39]) >> dow) & 1) == 0: cA[sd] = 0; continue
                if cfg[4] > 0 and dayTrades >= cfg[4]: continue
                entry = o[t + 1] + (spread if d > 0 else 0.0)
                az = aH1[t] if cTF[sd] == 1 else aH4[t]
                if cfg[54] == 0: sl = cL[sd] - d * cfg[27] * az            # same structural SL as the reversal
                elif cfg[54] == 1: sl = cPL[sd] - d * cfg[55] * az        # below the pullback (higher low), zone ATR
                elif cfg[54] == 2: sl = cPL[sd] - d * cfg[55] * a1        # tight: below the pullback, M1 ATR
                else: sl = (cZB[sd] if d > 0 else cZT[sd]) - d * cfg[55] * a1   # tight: beyond the FVG, M1 ATR
                risk = d * (entry - sl)
                if risk <= 0: cA[sd] = 0; continue
                if cfg[51] > 0 and risk > cfg[51] * az: cA[sd] = 0; continue
                if spread / risk > cfg[23]: cA[sd] = 0; continue
                # targets: swing before the reversal (TF of the zone), else dealing-range edge
                use4 = cTF[sd] == 2
                HH = H4h if use4 else H1h
                LL = H4l if use4 else H1l
                gS = h4gid[cEI[sd]] if use4 else h1gid[cEI[sd]]
                ts = int(cfg[33]); tsw = 0.0
                for k in range(gS - 1, max(gS - 300, ts) - 1, -1):
                    if d > 0 and swing_hi(HH, k, ts, gS) and HH[k] > entry: tsw = HH[k]; break
                    if d < 0 and swing_lo(LL, k, ts, gS) and LL[k] + spread < entry: tsw = LL[k] + spread; break
                ex = -1e18 if d > 0 else 1e18
                for jj in range(max(cF[sd], 0), cEI[sd] + 1):
                    ex = max(ex, h[jj]) if d > 0 else min(ex, l[jj] + spread)
                tp1 = tsw if (tsw != 0.0 and d * (tsw - entry) / risk >= cfg[31]) else ex
                tp = ex if d * (ex - tp1) > 0 else tp1
                if cfg[56] == 1:                                           # tight: fixed RR, single target
                    tp1 = entry + d * cfg[57] * risk; tp = tp1
                elif cfg[56] == 2:                                         # tight: the BOS-leg extreme (nearest liquidity)
                    tp1 = cHi[sd] if d > 0 else cHi[sd] + spread; tp = tp1
                    if d * (tp1 - entry) / risk < cfg[58]: cA[sd] = 0; continue
                if cfg[56] == 0 and d * (tp1 - entry) / risk < cfg[31]: cA[sd] = 0; continue
                lots = np.floor(bal * cfg[0] / 100.0 / (risk * contract) / 0.01 + 1e-9) * 0.01
                if lots < 0.01: cA[sd] = 0; continue
                oTP1 = tp1; oT1 = not (d * (tp - tp1) > 0)
                st = 2; od = d; oE = entry; oSL = sl; oTP = tp; oLots = lots; oLots0 = lots
                oRisk = risk; oPnl = 0.0; oBE = False; oFill = t + 1; oTF = cTF[sd]; oKZ = kz; oL = cL[sd]
                oSw = cSw[sd]; oMI = cBI[sd]; oZT = cZT[sd]; oZB = cZB[sd]; oMssP = cLeg[sd]; oKind = 1
                dayTrades += 1
                cA[sd] = 0
                if (d > 0 and l[t + 1] <= sl) or (d < 0 and h[t + 1] + spread >= sl):
                    pnl = -risk * contract * lots
                    bal += pnl; oPnl += pnl; dayPL += pnl
                    L_t[nt] = t1[t + 1]; L_x[nt] = t1[t + 1]; L_d[nt] = od; L_tf[nt] = oTF; L_kz[nt] = oKZ
                    L_pnl[nt] = oPnl; L_R[nt] = -1.0; L_risk[nt] = risk; L_ent[nt] = oE; L_sl[nt] = sl; L_tp[nt] = oTP
                    L_lvl[nt] = oL; L_tp1[nt] = oTP1; L_mss[nt] = oMssP; L_kind[nt] = oKind; L_sw[nt] = oSw; L_mi[nt] = oMI; L_zt[nt] = oZT; L_zb[nt] = oZB
                    nt += 1; st = 0

    return (L_t[:nt], L_x[:nt], L_d[:nt], L_tf[:nt], L_R[:nt], L_pnl[:nt], L_kz[:nt], L_risk[:nt],
            L_ent[:nt], L_sl[:nt], L_tp[:nt], L_lvl[:nt], L_sw[:nt], L_mi[:nt], L_zt[:nt], L_zb[:nt], rej, EV[:min(ne2, 60000)], L_tp1[:nt], L_mss[:nt], L_kind[:nt])
