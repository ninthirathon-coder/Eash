"""Top-down model: HTF (H1/H4 swings, PDH/PDL) defines the zones; M1 decides whether the zone reacts.
Every decision on M1 close; execution on following M1 bars (SL before TP, BE from next bar).
Times: server minutes (NY + 7h)."""
import numpy as np, numba as nb
from sim import swing_hi, swing_lo, candle, htf_trend


@nb.njit(cache=True)
def run_m1(t1, o, h, l, c, atr1, atr5, h1c_at, h4c_at, dayStart, pdh, pdl,
           H1h, H1l, H4h, H4l, b1, b4, cfg, Pc):
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
    L_sw = np.zeros(MAXT, np.int64); L_mi = np.zeros(MAXT, np.int64); L_zt = np.zeros(MAXT); L_zb = np.zeros(MAXT)
    nt = 0
    # active HTF levels: side 0 = lows (sell-side liquidity), 1 = highs
    CAP = 64
    lvP = np.zeros((2, CAP)); lvT = np.zeros((2, CAP), np.int64); nl = np.zeros(2, np.int64)
    # setups
    sA = np.zeros(2, np.int64); sL = np.zeros(2); sTF = np.zeros(2, np.int64); sExt = np.zeros(2); sEI = np.zeros(2, np.int64)
    sAge = np.zeros(2, np.int64); sPh = np.zeros(2, np.int64); sMss = np.zeros(2); sMA = np.zeros(2, np.int64)
    sZT = np.zeros(2); sZB = np.zeros(2); sZA = np.zeros(2, np.int64); sCand = np.zeros(2, np.int64); sSw = np.zeros(2, np.int64)
    sMI = np.zeros(2, np.int64)
    # position
    st = 0; od = 0; oE = 0.0; oSL = 0.0; oTP = 0.0; oLots = 0.0; oLots0 = 0.0; oRisk = 0.0; oPnl = 0.0; oBE = False
    oFill = 0; oTF = 0; oKZ = 0; oL = 0.0; oSw = 0; oMI = 0; oZT = 0.0; oZB = 0.0
    curDay = -1; dayTrades = 0; dayPL = 0.0
    mssS = int(cfg[9])

    for t in range(300, n - 1):
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
            elif (not oBE) and cfg[5] > 0 and t > oFill + 0:
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
                L_sw[nt] = oSw; L_mi[nt] = oMI; L_zt[nt] = oZT; L_zb[nt] = oZB
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
                    for q in range(CAP - 1): lvP[sd, q] = lvP[sd, q + 1]; lvT[sd, q] = lvT[sd, q + 1]
                    nl[sd] -= 1
                lvP[sd, nl[sd]] = pdl[t + 1] if sd == 0 else pdh[t + 1]; lvT[sd, nl[sd]] = 3; nl[sd] += 1
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
                    for q in range(CAP - 1): lvP[sd, q] = lvP[sd, q + 1]; lvT[sd, q] = lvT[sd, q + 1]
                    nl[sd] -= 1
                lvP[sd, nl[sd]] = P; lvT[sd, nl[sd]] = 1 + tf; nl[sd] += 1

        # ---------------- zones taken this bar -> new setups ----------------
        for sd in range(2):
            d = 1 if sd == 0 else -1          # lows swept -> buy setup
            best = 0.0; bt = 0; fnd = False
            q = 0
            while q < nl[sd]:
                P = lvP[sd, q]
                if (sd == 0 and l[t] < P) or (sd == 1 and h[t] > P):
                    if (not fnd) or (d > 0 and P < best) or (d < 0 and P > best) or (P == best and lvT[sd, q] > bt):
                        best = P; bt = lvT[sd, q]; fnd = True
                    for r in range(q, nl[sd] - 1):
                        lvP[sd, r] = lvP[sd, r + 1]; lvT[sd, r] = lvT[sd, r + 1]
                    nl[sd] -= 1
                else:
                    q += 1
            if not fnd or sA[sd] == 1:
                continue
            bm = int(cfg[17])
            if bm == 1 or bm == 3:
                if b1[t] != d: continue
            if bm == 2 or bm == 3:
                if b4[t] != d: continue
            sA[sd] = 1; sL[sd] = best; sTF[sd] = bt; sExt[sd] = l[t] if d > 0 else h[t]; sEI[sd] = t
            sAge[sd] = -1; sPh[sd] = 0; sMss[sd] = 0.0; sCand[sd] = 0; sSw[sd] = t

        # ---------------- progress setups on M1 ----------------
        for sd in range(2):
            if sA[sd] == 0: continue
            d = 1 if sd == 0 else -1
            sAge[sd] += 1
            if sPh[sd] == 0:
                if sAge[sd] > cfg[8]:
                    sA[sd] = 0; continue
                if (d > 0 and l[t] < sExt[sd]) or (d < 0 and h[t] > sExt[sd]):
                    sExt[sd] = l[t] if d > 0 else h[t]; sEI[sd] = t; sMss[sd] = 0.0
                if d * (sL[sd] - sExt[sd]) > cfg[3] * a5:
                    sA[sd] = 0; continue                   # too deep = real breakout, not a sweep
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
                    sA[sd] = 0; continue
                sPh[sd] = 1; sMA[sd] = 0; sMI[sd] = t
                if cfg[14] == 0: continue
            elif sPh[sd] == 1:
                sMA[sd] += 1
                if sMA[sd] > cfg[12]:
                    sA[sd] = 0; continue
                if (d > 0 and l[t] < sExt[sd]) or (d < 0 and h[t] > sExt[sd]):
                    sA[sd] = 0; continue
            elif sPh[sd] == 2:
                sZA[sd] += 1
                if sZA[sd] > cfg[13]:
                    sA[sd] = 0; continue
                if (d > 0 and (c[t] < sZB[sd] or l[t] < sExt[sd])) or (d < 0 and (c[t] > sZT[sd] or h[t] > sExt[sd])):
                    sA[sd] = 0; continue
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
            if cfg[18] > 0 and hr >= 2.0 and hr < 5.0: kz = 1
            if cfg[19] > 0 and hr >= 7.0 and hr < 10.0: kz = 2
            if cfg[18] == 0 and cfg[19] == 0: kz = 3
            if kz == 0 or st != 0: continue
            if cfg[4] > 0 and dayTrades >= cfg[4]: continue
            entry = o[t + 1] + (spread if d > 0 else 0.0)
            sl = sExt[sd] - d * cfg[2] * a1
            risk = d * (entry - sl)
            if risk <= 0: sA[sd] = 0; continue
            if risk > cfg[24] * a5: sA[sd] = 0; continue
            if spread / risk > cfg[23]: sA[sd] = 0; continue
            lots = np.floor(bal * cfg[0] / 100.0 / (risk * contract) / 0.01 + 1e-9) * 0.01
            if lots < 0.01: sA[sd] = 0; continue
            st = 2; od = d; oE = entry; oSL = sl; oTP = entry + d * cfg[1] * risk; oLots = lots; oLots0 = lots
            oRisk = risk; oPnl = 0.0; oBE = False; oFill = t + 1; oTF = sTF[sd]; oKZ = kz; oL = sL[sd]
            oSw = sSw[sd]; oMI = sMI[sd]; oZT = sZT[sd]; oZB = sZB[sd]
            dayTrades += 1
            sA[sd] = 0
            # fill bar: conservative SL check on the fill bar itself
            if (d > 0 and l[t + 1] <= sl) or (d < 0 and h[t + 1] + spread >= sl):
                pnl = -risk * contract * lots
                bal += pnl; oPnl += pnl; dayPL += pnl
                L_t[nt] = t1[t + 1]; L_x[nt] = t1[t + 1]; L_d[nt] = od; L_tf[nt] = oTF; L_kz[nt] = oKZ
                L_pnl[nt] = oPnl; L_R[nt] = -1.0; L_risk[nt] = risk; L_ent[nt] = oE; L_sl[nt] = sl; L_tp[nt] = oTP
                L_lvl[nt] = oL; L_sw[nt] = oSw; L_mi[nt] = oMI; L_zt[nt] = oZT; L_zb[nt] = oZB
                nt += 1; st = 0

    return (L_t[:nt], L_x[:nt], L_d[:nt], L_tf[:nt], L_R[:nt], L_pnl[:nt], L_kz[:nt], L_risk[:nt],
            L_ent[:nt], L_sl[:nt], L_tp[:nt], L_lvl[:nt], L_sw[:nt], L_mi[:nt], L_zt[:nt], L_zb[:nt])
