"""Backtest ระบบ ICT ของ indicator "ICT v14 + Mean Reversion" (เฉพาะส่วน Setup ICT 2022 Model)

แปลงตรรกะจาก Pine Script ทีละขั้น (ประเมินตอนแท่งปิด) แล้วเทรดตามสัญญาณ:
  mode="market"  เข้าที่ราคาปิดของแท่งที่ขึ้นสัญญาณ (ทำตาม alert จริง)
  mode="limit"   เข้าที่ราคา Entry ของ setup (ตั้ง Limit รอไว้)
SL = suSL ของ indicator, ถึง TP1 ปิดครึ่งแล้วเลื่อน SL เท่าทุน, ที่เหลือไป TP2 (ไม่มี TP2 = ปิดหมดที่ TP1)

ไม่ได้แปลง: Mean Reversion, RSI/Stoch/Volume, bias แบบ EMA M15 (ใช้ Daily ซึ่งเป็นค่าเริ่มต้น)
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from engine import OZ_PER_LOT, Data


@dataclass
class IndParams:
    # ค่าเริ่มต้นตรงกับ input ของ indicator
    swing_len: int = 3
    disp_atr: float = 1.2
    disp_body: float = 0.6
    disp_win: int = 5
    sweep_win: int = 20
    fvg_min_atr: float = 0.2
    fvg_need_disp: bool = True
    fvg_max: int = 5
    fvg_expiry: int = 200
    ob_lookback: int = 10
    ob_max_atr: float = 2.0
    liq_max: int = 10
    eq_len: int = 5
    eq_tol: float = 0.1
    eq_max_pivots: int = 3
    setup_on_bos: bool = False
    entry_mid: bool = False
    setup_expiry: int = 30
    sl_buf_atr: float = 0.1
    min_rr: float = 2.0
    use_bias: bool = True
    min_grade: str = "C"
    # ตัวกรองแบบบังคับ (ยืมจาก EA): ไม่ผ่าน = ไม่เข้า แทนที่จะเป็นแค่คะแนนเกรด
    require_kz: bool = False        # ต้องอยู่ใน Kill Zone / Silver Bullet ตอนเข้า
    require_bias: bool = False      # ต้องตรงกับ bias รายวัน
    require_sweep: bool = False     # ต้องมีการกวาดสภาพคล่องก่อน MSS
    require_disp: bool = False      # ต้องมี Displacement
    require_pd: bool = False        # จุดเข้าต้องอยู่ฝั่ง Discount / Premium
    fvg_only: bool = False          # ใช้เฉพาะ FVG ไม่ใช้ Order Block สำรอง
    news_block: tuple = (0, 0)      # งดเข้าช่วงนาทีนี้ (915, 945) = 08:15-08:45 นิวยอร์ก
    skip_nfp_day: bool = False      # งดศุกร์แรกของเดือน
    max_trades_day: int = 0         # 0 = ไม่จำกัด
    max_losses_day: int = 0
    # การเทรด
    mode: str = "market"
    partial_at_tp1: bool = True
    eod_exit: int = 1380            # 16:00 นิวยอร์ก (นาทีนับจาก 17:00), 0 = ถือข้ามวัน
    balance: float = 6000.0
    risk_pct: float = 1.0
    fixed_risk: bool = True         # True = เสี่ยงเป็น % ของทุนเริ่มต้น (ไม่ทบต้น) เพื่อให้เทียบชุดค่าได้
    spread: float = 0.30
    commission: float = 7.0


ASIA, LON, NY = (180, 420), (540, 720), (840, 1020)
SB = ((600, 660), (1020, 1080), (1260, 1320))


def _rma(x, n):
    out = np.full(len(x), np.nan)
    if len(x) < n:
        return out
    out[n - 1] = x[:n].mean()
    a = 1.0 / n
    for i in range(n, len(x)):
        out[i] = out[i - 1] + a * (x[i] - out[i - 1])
    return out


def _pivots(v, n, sign):
    """pivot high (sign=1) / low (sign=-1) ยืนยันที่แท่ง i สำหรับจุด i-n คืน array ค่า pivot หรือ nan"""
    x = v * sign
    out = np.full(len(x), np.nan)
    w = np.lib.stride_tricks.sliding_window_view(x, 2 * n + 1)
    c = w[:, n]
    ok = (w[:, :n].max(axis=1) < c) & (w[:, n + 1:].max(axis=1) < c)
    out[2 * n:][ok] = v[n:len(x) - n][ok]
    return out


def run_indicator(data: Data, p: IndParams):
    m5, m1 = data.m5, data.m1
    O, H, L, C = (m5[k].tolist() for k in ("open", "high", "low", "close"))
    Hn, Ln, Cn, On = m5["high"], m5["low"], m5["close"], m5["open"]
    MOD = m5["mod"].tolist()
    DAY = m5["day"].astype("datetime64[D]")
    T5 = m5["time"]
    n = len(C)
    tf = data.tf

    tr = np.maximum(Hn - Ln, np.maximum(np.abs(Hn - np.roll(Cn, 1)), np.abs(Ln - np.roll(Cn, 1))))
    tr[0] = Hn[0] - Ln[0]
    atr = _rma(tr, 14)
    atr_prev = np.roll(atr, 1)
    atr_prev[0] = np.nan
    body, rng = np.abs(Cn - On), Hn - Ln
    big = (~np.isnan(atr_prev)) & (rng > 0) & (body >= p.disp_atr * atr_prev) & (body / np.where(rng > 0, rng, 1) >= p.disp_body)
    disp_up = (big & (Cn > On)).tolist()
    disp_dn = (big & (Cn < On)).tolist()
    sw_ph = _pivots(Hn, p.swing_len, 1).tolist()
    sw_pl = _pivots(Ln, p.swing_len, -1).tolist()
    eq_ph = _pivots(Hn, p.eq_len, 1).tolist()
    eq_pl = _pivots(Ln, p.eq_len, -1).tolist()
    atr_l, atrp_l = atr.tolist(), atr_prev.tolist()

    # ระดับรายวัน / รายสัปดาห์ของแท่งที่ปิดแล้ว
    dfd = pd.DataFrame({"day": DAY, "high": Hn, "low": Ln, "close": Cn})
    dd = dfd.groupby("day").agg(high=("high", "max"), low=("low", "min"), close=("close", "last"))
    wk = dd.groupby(dd.index.to_period("W")).agg(high=("high", "max"), low=("low", "min"))
    dmap, wmap = {}, {}
    days = dd.index.to_list()
    for k, d in enumerate(days):
        y = dd.iloc[k - 1] if k >= 1 else None
        yy = dd.iloc[k - 2] if k >= 2 else None
        dmap[np.datetime64(d, "D")] = (y.high if y is not None else np.nan, y.low if y is not None else np.nan,
                                       y.close if y is not None else np.nan,
                                       yy.high if yy is not None else np.nan, yy.low if yy is not None else np.nan)
    wks = wk.index.to_list()
    for k, w in enumerate(wks):
        wmap[w] = (wk.iloc[k - 1].high, wk.iloc[k - 1].low) if k >= 1 else (np.nan, np.nan)
    day_week = {np.datetime64(d, "D"): d.to_period("W") for d in days}

    m1o, m1h, m1l, m1c, m1t = m1["open"], m1["high"], m1["low"], m1["close"], m1["time"]
    m1mod = (pd.DatetimeIndex(m1t).hour * 60 + pd.DatetimeIndex(m1t).minute).to_numpy()
    nm1 = len(m1c)

    def sim(k0, d, entry, sl, tp1, tp2, lot, limit):
        """จำลองไม้ตั้งแต่แท่ง M1 ที่ k0 คืน (pnl, k_exit, reason) ราคาทั้งหมดเป็นราคาจริง"""
        xa = 0.0 if d == 1 else p.spread    # ฝั่ง Sell ออกที่ ask
        pnl, left, be, sl_now = 0.0, lot, False, sl
        k = k0
        first = True
        while k < nm1:
            o, h, l, c = m1o[k], m1h[k], m1l[k], m1c[k]
            if d == -1:
                o, h, l, c = -o, -l, -h, -c
            e_, s_, t1, t2 = d * entry, d * sl_now, d * tp1, d * tp2
            if p.eod_exit and not first and m1mod[k] >= p.eod_exit > m1mod[k - 1]:
                pnl += (o - xa - e_) * OZ_PER_LOT * left
                return pnl, k, "EOD"
            if not (first and limit) and o - xa <= s_:
                pnl += (o - xa - e_) * OZ_PER_LOT * left
                return pnl, k, "BE" if be else "SL"
            if l - xa <= s_:
                pnl += (s_ - e_) * OZ_PER_LOT * left
                return pnl, k, "BE" if be else "SL"
            if not (first and limit):
                if not be and h - xa >= t1:
                    be, sl_now = True, entry
                    half = np.floor(left / 2 * 100 + 1e-9) / 100
                    if tp1 == tp2:
                        pnl += (t1 - e_) * OZ_PER_LOT * left
                        return pnl, k, "TP"
                    if p.partial_at_tp1 and half >= 0.01:
                        pnl += (t1 - e_) * OZ_PER_LOT * half
                        left = round(left - half, 2)
                if be and h - xa >= t2:
                    pnl += (t2 - e_) * OZ_PER_LOT * left
                    return pnl, k, "TP2"
            first = False
            k += 1
        pnl += (d * m1c[-1] - xa - d * entry) * OZ_PER_LOT * left
        return pnl, nm1 - 1, "END"

    # ---------- สถานะ ----------
    bsl, ssl = [], []
    fvgs = []                       # [top, bot, mid, dir, flipped, created]
    eqh, eql = [], []
    phP, phX, plP, plX = [], [], [], []
    swHi = swLo = None
    swHiX = swLoX = 0
    swHiOpen = swLoOpen = False
    trend = 0
    legDir, legX, legHi, legLo = 0, 0, np.nan, np.nan
    lastSwHi = lastSwLo = None
    pdhT = pdlT = pwhT = pwlT = False
    asHi = asLo = None
    asHiT = asLoT = False
    suDir, suBar, suEntry, suSL, suSwept, suDisp, suPoi = 0, 0, 0.0, 0.0, False, False, ""
    equity = p.balance
    trades = []
    cnt_day, day_tr, day_ls = None, 0, 0
    busy_until = -1                 # index แท่ง M1 ที่ไม้ปัจจุบันปิด
    grade_rank = {"A": 0, "B": 1, "C": 2}
    prev_day = prev_week = None
    in_asia_prev = False
    start = p.swing_len * 2 + 3

    for i in range(n):
        mod = MOD[i]
        day = DAY[i]
        newD = day != prev_day
        week = day_week[day]
        newW = week != prev_week
        prev_day, prev_week = day, week
        dH1, dL1, dC1, dH2, dL2 = dmap[day]
        wH1, wL1 = wmap[week]
        hi, lo, cl = H[i], L[i], C[i]
        inAsia = ASIA[0] <= mod < ASIA[1]
        if inAsia and not in_asia_prev:
            asHi, asLo, asHiT, asLoT = hi, lo, False, False
        elif inAsia and asHi is not None:
            asHi, asLo = max(asHi, hi), min(asLo, lo)
        in_asia_prev = inAsia
        if i <= start:
            continue
        if newD:
            pdhT = pdlT = False
        if newW:
            pwhT = pwlT = False
        a_prev = atrp_l[i]
        a_prev0 = 0.0 if a_prev != a_prev else a_prev

        # 1. สภาพคล่อง: Sweep (ไส้ทะลุแล้วปิดกลับ) / Run (ปิดทะลุ)
        swH = swL = False
        for k in range(len(bsl) - 1, -1, -1):
            if hi > bsl[k]:
                if cl <= bsl[k]:
                    swH = True
                del bsl[k]
        for k in range(len(ssl) - 1, -1, -1):
            if lo < ssl[k]:
                if cl >= ssl[k]:
                    swL = True
                del ssl[k]
        if not pdhT and dH1 == dH1 and hi > dH1:
            pdhT = True
            swH |= cl <= dH1
        if not pdlT and dL1 == dL1 and lo < dL1:
            pdlT = True
            swL |= cl >= dL1
        if not pwhT and wH1 == wH1 and hi > wH1:
            pwhT = True
            swH |= cl <= wH1
        if not pwlT and wL1 == wL1 and lo < wL1:
            pwlT = True
            swL |= cl >= wL1
        if not inAsia and asHi is not None:
            if not asHiT and hi > asHi:
                asHiT = True
                swH |= cl <= asHi
            if not asLoT and lo < asLo:
                asLoT = True
                swL |= cl >= asLo
        for k in range(len(eqh) - 1, -1, -1):
            if hi > eqh[k]:
                if cl <= eqh[k]:
                    swH = True
                del eqh[k]
        for k in range(len(eql) - 1, -1, -1):
            if lo < eql[k]:
                if cl >= eql[k]:
                    swL = True
                del eql[k]
        if swH:
            lastSwHi = i
        if swL:
            lastSwLo = i

        # 2. ขาล่าสุด
        if legDir == 1:
            legHi = max(legHi, hi)
        elif legDir == -1:
            legLo = min(legLo, lo)

        # 3. FVG: อัปเดตของเดิม แล้วตรวจช่องใหม่
        for k in range(len(fvgs) - 1, -1, -1):
            z = fvgs[k]
            kill = i - z[5] > p.fvg_expiry
            if not kill:
                broken = cl < z[1] if z[3] == 1 else cl > z[0]
                if broken:
                    if not z[4]:
                        z[3], z[4], z[5] = -z[3], True, i   # กลายเป็น IFVG
                    else:
                        kill = True
                elif (lo <= z[1]) if z[3] == 1 else (hi >= z[0]):
                    kill = True
            if kill:
                del fvgs[k]
        gap_min = p.fvg_min_atr * a_prev0
        mid_up = disp_up[i - 1] if p.fvg_need_disp else C[i - 1] > O[i - 1]
        mid_dn = disp_dn[i - 1] if p.fvg_need_disp else C[i - 1] < O[i - 1]
        new_dirs = []
        if mid_up and lo > H[i - 2] and lo - H[i - 2] >= gap_min:
            fvgs.append([lo, H[i - 2], (lo + H[i - 2]) / 2, 1, False, i])
            new_dirs.append(1)
        if mid_dn and hi < L[i - 2] and L[i - 2] - hi >= gap_min:
            fvgs.append([L[i - 2], hi, (L[i - 2] + hi) / 2, -1, False, i])
            new_dirs.append(-1)
        for dz in new_dirs:
            cnt = 0
            for k in range(len(fvgs) - 1, -1, -1):
                if fvgs[k][3] == dz:
                    cnt += 1
                    if cnt > p.fvg_max:
                        del fvgs[k]

        # 5. Setup ที่รออยู่: ราคาย่อถึงจุดเข้า -> สัญญาณ
        if suDir != 0:
            d = suDir
            expired = i - suBar > p.setup_expiry
            hit = lo <= suEntry if d == 1 else hi >= suEntry
            if hit and not expired:
                tp1 = legHi if d == 1 else legLo
                cands = list(bsl if d == 1 else ssl) + list(eqh if d == 1 else eql)
                if d == 1:
                    cands += [np.nan if pdhT else dH1, np.nan if pwhT else wH1,
                              np.nan if (asHiT or asHi is None) else asHi]
                else:
                    cands += [np.nan if pdlT else dL1, np.nan if pwlT else wL1,
                              np.nan if (asLoT or asLo is None) else asLo]
                tp2 = None
                for c_ in cands:
                    if c_ == c_ and (c_ - tp1) * d > 0 and (tp2 is None or (c_ - tp2) * d < 0):
                        tp2 = c_
                dol = tp1 if tp2 is None else tp2
                risk = abs(suEntry - suSL)
                rr = max(0.0, (dol - suEntry) * d) / risk if risk > 0 else 0.0
                eq_lvl = (legHi + legLo) / 2
                pd_ok = suEntry <= eq_lvl if d == 1 else suEntry >= eq_lvl
                in_sb = any(a <= mod < b for a, b in SB)
                kz_pass = LON[0] <= mod < LON[1] or NY[0] <= mod < NY[1] or in_sb
                bias = 0
                if dC1 == dC1 and dH2 == dH2:
                    bias = 1 if dC1 > dH2 else -1 if dC1 < dL2 else 0 if (dH1 > dH2 and dL1 < dL2) else \
                        -1 if dH1 > dH2 else 1 if dL1 < dL2 else 0
                bias_ok = p.use_bias and bias == d
                score = suSwept + suDisp + pd_ok + kz_pass + bias_ok
                max_s = 4 + (1 if p.use_bias else 0)
                g = "A" if score >= max_s else "B" if score == max_s - 1 else "C"
                hard = ((kz_pass or not p.require_kz) and (bias == d or not p.require_bias)
                        and (suSwept or not p.require_sweep) and (suDisp or not p.require_disp)
                        and (pd_ok or not p.require_pd) and not (p.news_block[0] <= mod < p.news_block[1]))
                if p.skip_nfp_day:
                    ts = pd.Timestamp(day)
                    hard = hard and not (ts.weekday() == 4 and ts.day <= 7)
                if day != cnt_day:
                    cnt_day, day_tr, day_ls = day, 0, 0
                if (p.max_trades_day and day_tr >= p.max_trades_day) or (p.max_losses_day and day_ls >= p.max_losses_day):
                    hard = False
                if hard and (p.min_rr <= 0 or rr >= p.min_rr) and grade_rank[g] <= grade_rank[p.min_grade]:
                    # ---------- เทรดตามสัญญาณ ----------
                    k0 = None
                    if p.mode == "market":
                        k0 = int(data.m5_m1_end[i])
                        entry = cl + (p.spread if d == 1 else 0.0)
                        ok = k0 < nm1 and (entry - suSL) * d > 0 and (dol - entry) * d > 0 and (tp1 - entry) * d > 0
                    else:
                        entry = suEntry
                        ok = False
                        for k in range(int(data.m5_m1_start[i]), int(data.m5_m1_end[i])):
                            if (d == 1 and m1l[k] + p.spread <= entry) or (d == -1 and m1h[k] >= entry):
                                k0, ok = k, True
                                break
                        ok = ok and (tp1 - entry) * d > 0
                    if ok and k0 > busy_until and not (p.eod_exit and m1mod[min(k0, nm1 - 1)] >= p.eod_exit):
                        r_dist = abs(entry - suSL)
                        lot = np.floor((p.balance if p.fixed_risk else equity) * p.risk_pct / 100 / (r_dist * OZ_PER_LOT) * 100 + 1e-9) / 100
                        if lot >= 0.01:
                            pnl, kx, why = sim(k0, d, entry, suSL, tp1, dol, lot, p.mode == "limit")
                            pnl -= p.commission * lot
                            equity += pnl
                            day_tr += 1
                            day_ls += pnl < 0
                            busy_until = kx
                            trades.append(dict(open_time=m1t[k0], close_time=m1t[kx], dir=d, grade=g, poi=suPoi,
                                               kz=kz_pass, entry=entry, sl=suSL, tp1=tp1, tp2=dol, lot=lot, pnl=pnl,
                                               R=pnl / (r_dist * OZ_PER_LOT * lot + p.commission * lot), exit=why,
                                               equity=equity))
                suDir = 0
            elif expired:
                suDir = 0

        # 6. โครงสร้าง: แท่งปิดทะลุ swing -> BOS / MSS
        brk = 0
        if swHiOpen and cl > swHi:
            brk = 1
        elif swLoOpen and cl < swLo:
            brk = -1
        if brk != 0:
            isMSS = trend == -brk
            fromX = swHiX if brk == 1 else swLoX
            trend = brk
            if brk == 1:
                swHiOpen = False
            else:
                swLoOpen = False
            nn = max(1, min(i - fromX, 300))
            ext = 0
            for j in range(1, nn + 1):
                if (L[i - j] < L[i - ext]) if brk == 1 else (H[i - j] > H[i - ext]):
                    ext = j
            legDir, legX = brk, i - ext
            legHi, legLo = max(H[i - ext:i + 1]), min(L[i - ext:i + 1])
            dsp = disp_up if brk == 1 else disp_dn
            disp = any(dsp[i - k] for k in range(p.disp_win) if i - k >= 0)
            sb_ = lastSwLo if brk == 1 else lastSwHi
            swept = sb_ is not None and i - sb_ <= p.sweep_win
            # Order Block (ใช้เป็น POI สำรองเมื่อไม่มี FVG)
            dPos = 0
            for k in range(0, ext + 1):
                if dsp[i - k]:
                    dPos = k
            ob = None
            for j in range(dPos + 1, dPos + p.ob_lookback + 1):
                if i - j < 0:
                    break
                if (C[i - j] < O[i - j]) if brk == 1 else (C[i - j] > O[i - j]):
                    if H[i - j] > L[i - j]:
                        zt, zb = H[i - j], L[i - j]
                        cap = p.ob_max_atr * a_prev0
                        if p.ob_max_atr > 0 and cap > 0 and zt - zb > cap:
                            if brk == 1:
                                zt = zb + cap
                            else:
                                zb = zt - cap
                        ob = (zt, zb, max(zb, min(zt, (O[i - j] + C[i - j]) / 2)))
                    break
            if isMSS or p.setup_on_bos:
                poi = None
                for k in range(len(fvgs) - 1, -1, -1):
                    f = fvgs[k]
                    if f[3] == brk and not f[4] and f[5] >= legX:
                        poi, suPoi = (f[0], f[1], f[2]), "FVG"
                        break
                if poi is None and ob is not None and not p.fvg_only:
                    poi, suPoi = ob, "OB"
                if poi is not None:
                    suDir, suBar = brk, i
                    suEntry = poi[2] if p.entry_mid else (poi[0] if brk == 1 else poi[1])
                    suSL = legLo - p.sl_buf_atr * a_prev0 if brk == 1 else legHi + p.sl_buf_atr * a_prev0
                    suSwept, suDisp = swept, disp
                else:
                    suDir = 0
            elif suDir == -brk:
                suDir = 0

        # 7. swing ใหม่ที่ยืนยันแล้ว
        v = sw_ph[i]
        if v == v:
            swHi, swHiX, swHiOpen = v, i - p.swing_len, True
            bsl.append(v)
            if len(bsl) > p.liq_max:
                del bsl[0]
        v = sw_pl[i]
        if v == v:
            swLo, swLoX, swLoOpen = v, i - p.swing_len, True
            ssl.append(v)
            if len(ssl) > p.liq_max:
                del ssl[0]

        # 8. EQH / EQL
        tol = atr_l[i] * p.eq_tol if atr_l[i] == atr_l[i] else 0.0
        for piv, P_, X_, lines, sgn in ((eq_ph[i], phP, phX, eqh, 1), (eq_pl[i], plP, plX, eql, -1)):
            if piv != piv:
                continue
            x1 = i - p.eq_len
            m = len(P_)
            for k in range(m - 1, max(0, m - p.eq_max_pivots) - 1, -1):
                p0, x0 = P_[k], X_[k]
                if abs(piv - p0) <= tol and x1 - x0 <= 300:
                    lv = max(piv, p0) if sgn == 1 else min(piv, p0)
                    seg_a, seg_b = x0 + 1, i - p.eq_len - 1   # แท่งระหว่างสองจุด
                    clean = True
                    if seg_b >= seg_a:
                        clean = (max(H[seg_a:seg_b + 1]) <= lv) if sgn == 1 else (min(L[seg_a:seg_b + 1]) >= lv)
                    if clean:
                        lines.append(lv)
                        if len(lines) > 30:
                            del lines[0]
                        break
            P_.append(piv)
            X_.append(x1)
            if len(P_) > 20:
                del P_[0]
                del X_[0]

    return pd.DataFrame(trades)


def summarize(tr: pd.DataFrame, p: IndParams, split="2025-07-01") -> dict:
    if len(tr) == 0:
        return dict(ไม้=0)
    eq = np.concatenate([[p.balance], tr.equity.to_numpy()])
    peak = np.maximum.accumulate(eq)
    wins, loss = tr[tr.pnl > 0], tr[tr.pnl <= 0]
    gl = -loss.pnl.sum()
    a, b = tr[tr.open_time < split], tr[tr.open_time >= split]
    return {"ไม้": len(tr), "ชนะ%": round(len(wins) / len(tr) * 100, 1),
            "ผลตอบแทน%": round((eq[-1] / p.balance - 1) * 100, 1),
            "PF": round(wins.pnl.sum() / gl, 2) if gl > 0 else float("inf"),
            "R/ไม้": round(tr.R.mean(), 3), "MaxDD%": round(((peak - eq) / peak).max() * 100, 1),
            "ไม้ IS": len(a), "R รวม IS": round(a.R.sum(), 1), "ไม้ OOS": len(b), "R รวม OOS": round(b.R.sum(), 1)}
