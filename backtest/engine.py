"""Backtest engine สำหรับ EA "ICT 2022 Model + Wyckoff Spring/UTAD" บน XAUUSD

ตรรกะตรงกับ mql5/ICT_Wyckoff_Gold_EA.mq5 (สัญญาณคิดตอนแท่ง M5 ปิด, จำลองการ fill ด้วยแท่ง M1)

เวลา: ใช้ "server time" = เวลานิวยอร์ก + 7 ชม. (เท่ากับโบรกเกอร์ GMT+2/+3 ส่วนใหญ่)
ทำให้วันเทรดเริ่ม 00:00 server = 17:00 นิวยอร์ก

ทิศทาง: โค้ดเขียนฝั่ง Buy อย่างเดียว ฝั่ง Sell ใช้ราคากลับเครื่องหมาย (p' = -p)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

OZ_PER_LOT = 100.0


@dataclass
class Params:
    # --- เวลา (นาทีนับจาก 00:00 server = 17:00 NY) ---
    asia: tuple = (180, 420)        # 20:00-00:00 NY
    london: tuple = (540, 720)      # 02:00-05:00 NY
    nyam: tuple = (840, 1020)       # 07:00-10:00 NY
    trade_london: bool = True
    trade_nyam: bool = True
    news_block: tuple = (915, 945)  # 08:15-08:45 NY (ข่าว 08:30)
    eod_exit: int = 1380            # 16:00 NY ปิดทุกไม้
    skip_nfp_day: bool = True       # ศุกร์แรกของเดือน
    # --- สัญญาณ ---
    use_bias: bool = True           # ICT: เทรดตาม bias รายวันเท่านั้น
    use_ict_levels: bool = True     # กวาด Asia / PDH-PDL / London
    use_wyckoff: bool = True        # กวาดขอบกรอบ H1 (Spring / UTAD)
    use_swing_levels: bool = True   # จุดสูง/ต่ำเก่าบน H1 ที่ยังไม่ถูกกวาด
    swing_lookback: int = 48
    swing_max: int = 2
    max_mss_min: int = 120          # MSS ต้องเกิดภายในกี่นาทีหลังจุดกวาด
    disp_mult: float = 1.5          # ตัวแท่ง displacement >= กี่เท่าของค่าเฉลี่ย 20 แท่ง
    min_fvg: float = 0.2            # ขนาด FVG ขั้นต่ำ (เท่าของ A = ค่าเฉลี่ย high-low 20 แท่ง M5)
    require_discount: bool = False  # จุดเข้าต้องต่ำกว่า 50% ของขา displacement
    entry_ce: bool = False          # True = เข้าที่ CE 50% ของ FVG, False = ขอบช่อง
    vol_mult: float = 0.0           # Wyckoff effort: volume ขา displacement >= กี่เท่า (0 = ปิด)
    # --- กรอบ Wyckoff บน H1 ---
    wy_bars: int = 72
    wy_min_width: float = 3.0       # ความกว้างกรอบขั้นต่ำ (เท่าของค่าเฉลี่ย high-low H1 ในกรอบ)
    wy_max_drift: float = 0.5       # |close สุดท้าย - close แรก| / ความกว้างกรอบ
    wy_min_touches: int = 2
    # --- ออเดอร์ ---
    sl_buffer: float = 0.5          # เผื่อ SL เลยจุดกวาด (เท่าของ A)
    min_risk: float = 2.0           # ระยะ SL สั้นกว่านี้ข้าม (เท่าของ A)
    max_risk: float = 12.0          # ระยะ SL กว้างกว่านี้ข้าม (เท่าของ A)
    min_rr: float = 2.0
    order_grace: int = 60           # นาทีที่ออเดอร์รอได้หลังหมด Kill Zone
    fallback_rr: float = 0.0        # ถ้าไม่มีเป้าสภาพคล่อง ใช้ RR คงที่ (0 = ไม่เข้า)
    partial_at_tp1: bool = True
    exit_on_fvg_fail: bool = True   # แท่ง M5 ปิดทะลุ FVG สวนทาง -> ปิดเอง
    # --- ความเสี่ยง ---
    balance: float = 6000.0
    risk_pct: float = 1.0
    max_trades_day: int = 2
    max_losses_day: int = 2
    # --- ต้นทุน ---
    spread: float = 0.30
    commission: float = 7.0         # ดอลลาร์ต่อ lot ไป-กลับ
    no_trade_dates: tuple = ()      # 'YYYY-MM-DD' (วันเทรดแบบ server)


@dataclass
class Data:
    m1: dict
    m5: dict
    m5_m1_start: np.ndarray
    m5_m1_end: np.ndarray
    tf: int = 5


def load(path: str | Path, start=None, end=None, tf: int = 5) -> Data:
    df = pd.read_csv(path, parse_dates=["time"])
    df["srv"] = df["time"] + pd.Timedelta(hours=7)  # ไฟล์เป็นเวลานิวยอร์ก
    if start:
        df = df[df.srv >= start]
    if end:
        df = df[df.srv < end]
    df = df.reset_index(drop=True)
    df["b5"] = df.srv.dt.floor(f"{tf}min")
    g = df.groupby("b5", sort=True)
    m5 = g.agg(open=("open", "first"), high=("high", "max"), low=("low", "min"),
               close=("close", "last"), volume=("volume", "sum")).reset_index()
    first = g["open"].apply(lambda s: s.index[0]).to_numpy()
    last = g["open"].apply(lambda s: s.index[-1]).to_numpy() + 1
    m5["day"] = m5.b5.dt.normalize()
    m5["mod"] = m5.b5.dt.hour * 60 + m5.b5.dt.minute
    m5d = {c: m5[c].to_numpy() for c in ["open", "high", "low", "close", "volume", "mod"]}
    m5d["time"] = m5.b5.to_numpy()
    m5d["day"] = m5.day.to_numpy()
    m1d = {c: df[c].to_numpy() for c in ["open", "high", "low", "close"]}
    m1d["time"] = df.srv.to_numpy()
    return Data(m1=m1d, m5=m5d, m5_m1_start=first, m5_m1_end=last, tf=tf)


def daily_bias(days: pd.DataFrame) -> dict:
    """กฎจากตาราง bias รายวันในเอกสาร (ปิดทะลุ = ไปต่อ, ไส้ทะลุแล้วปิดกลับ = กลับตัว, inside = ไม่มี)"""
    out = {}
    d = days.reset_index()
    for k in range(2, len(d)):
        y, yy = d.iloc[k - 1], d.iloc[k - 2]
        up, dn = y.high > yy.high, y.low < yy.low
        if up and not dn:
            b = 1 if y.close > yy.high else -1
        elif dn and not up:
            b = -1 if y.close < yy.low else 1
        elif up and dn:
            b = 1 if y.close > yy.high else (-1 if y.close < yy.low else 0)
        else:
            b = 0
        out[np.datetime64(d.iloc[k].day, "ns")] = (b, y.high, y.low)
    return out


def wyckoff_range(h1h, h1l, h1c, p: Params):
    """หากรอบไซด์เวย์จากแท่ง H1 ล่าสุด คืน (low, high) หรือ None"""
    if len(h1h) < p.wy_bars:
        return None
    h, l, c = h1h[-p.wy_bars:], h1l[-p.wy_bars:], h1c[-p.wy_bars:]
    rh, rl = h.max(), l.min()
    w = rh - rl
    if w < p.wy_min_width * (h - l).mean():
        return None
    if abs(c[-1] - c[0]) > p.wy_max_drift * w:
        return None
    up_zone, dn_zone = rh - 0.25 * w, rl + 0.25 * w
    ups = dns = 0
    state = 0
    for k in range(len(h)):
        if h[k] >= up_zone and state != 1:
            ups += 1
            state = 1
        elif l[k] <= dn_zone and state != -1:
            dns += 1
            state = -1
    if ups < p.wy_min_touches or dns < p.wy_min_touches:
        return None
    return rl, rh


class Side:
    def __init__(self, d):
        self.d = d
        self.reset()

    def reset(self):
        self.levels = []   # [price', tag, tp1', tp2', swept]
        self.targets = []  # ราคา' ของสภาพคล่องฝั่งตรงข้าม
        self.ext = None
        self.ext_i = -1
        self.mss = None
        self.tag = None
        self.lvl = None
        self.fired = False


def run(data: Data, p: Params):
    m5, m1, tf = data.m5, data.m1, data.tf
    O, H, L, C, V, MOD = m5["open"], m5["high"], m5["low"], m5["close"], m5["volume"], m5["mod"]
    DAY, T5 = m5["day"].astype("datetime64[ns]"), m5["time"]
    n = len(C)
    body = np.abs(C - O)
    rng5 = H - L
    # แท่งรายวัน (วันเทรด server)
    dfd = pd.DataFrame({"day": DAY, "high": H, "low": L, "close": C})
    days = dfd.groupby("day").agg(high=("high", "max"), low=("low", "min"), close=("close", "last"))
    bias = daily_bias(days)
    # H1
    hkey = T5.astype("datetime64[h]")
    dfh = pd.DataFrame({"h": hkey, "high": H, "low": L, "close": C})
    h1 = dfh.groupby("h").agg(high=("high", "max"), low=("low", "min"), close=("close", "last"))
    h1t = h1.index.to_numpy()
    h1h, h1l, h1c = h1.high.to_numpy(), h1.low.to_numpy(), h1.close.to_numpy()

    X = {1: (H, L, C, O), -1: (-L, -H, -C, -O)}
    sides = {1: Side(1), -1: Side(-1)}
    equity = p.balance
    trades = []
    eq_curve = []
    funnel = {}

    def cnt(k):
        funnel[k] = funnel.get(k, 0) + 1
    pending = None
    pos = None
    cur_day = None
    day_trades = day_losses = 0
    day_ok = False
    kz = None
    kz_end = 0
    day_start_i = 0
    m1o, m1h, m1l, m1c, m1t = m1["open"], m1["high"], m1["low"], m1["close"], m1["time"]

    def close_pos(price_t, when, reason, frac_lot=None):
        nonlocal equity, pos, day_losses
        lot = pos["lot"] if frac_lot is None else frac_lot
        pnl = (price_t - pos["entry"]) * OZ_PER_LOT * lot - p.commission * lot
        equity += pnl
        pos["pnl"] += pnl
        pos["lot"] = round(pos["lot"] - lot, 2)
        if pos["lot"] <= 1e-9:
            r = pos["pnl"] / pos["risk_usd"]
            trades.append(dict(open_time=pos["t_open"], close_time=when, dir=pos["d"], tag=pos["tag"], kz=pos["kz"],
                               entry=pos["d"] * pos["entry"], sl=pos["d"] * pos["sl0"], tp1=pos["d"] * pos["tp1"],
                               tp2=pos["d"] * pos["tp2"], lot=pos["lot0"], pnl=pos["pnl"], R=r, exit=reason,
                               equity=equity))
            if pos["pnl"] < 0:
                day_losses += 1
            pos = None

    for i in range(n):
        mod = MOD[i]
        # ---------- วันใหม่ ----------
        if DAY[i] != cur_day:
            cur_day = DAY[i]
            day_trades = day_losses = 0
            day_start_i = i
            kz = None
            pending = None
            ts = pd.Timestamp(cur_day)
            day_ok = cur_day in bias and str(ts.date()) not in p.no_trade_dates
            if p.skip_nfp_day and ts.weekday() == 4 and ts.day <= 7:
                day_ok = False
            eq_curve.append((ts, equity))

        # ---------- จำลอง M1 ของแท่งนี้ ----------
        if pending is not None or pos is not None:
            for k in range(data.m5_m1_start[i], data.m5_m1_end[i]):
                if pos is None and pending is None:
                    break
                d = pending["d"] if pending is not None else pos["d"]
                if d == 1:
                    o, h, l, c = m1o[k], m1h[k], m1l[k], m1c[k]
                    ea, xa = p.spread, 0.0
                else:
                    o, h, l, c = -m1o[k], -m1l[k], -m1h[k], -m1c[k]
                    ea, xa = 0.0, p.spread
                if pending is not None:
                    if l + ea <= pending["entry"]:
                        pos = dict(pending, t_open=m1t[k], pnl=0.0, be=False, sl0=pending["sl"], lot0=pending["lot"])
                        pending = None
                        day_trades += 1
                        if l - xa <= pos["sl"]:
                            close_pos(pos["sl"], m1t[k], "SL")
                        continue
                    if h - xa >= pending["tp1"]:
                        pending = None  # ราคาไปถึงเป้าก่อนย่อมาเข้า
                    continue
                # มีสถานะ
                if o - xa <= pos["sl"]:
                    close_pos(o - xa, m1t[k], "BE" if pos["be"] else "SL")
                    continue
                if l - xa <= pos["sl"]:
                    close_pos(pos["sl"], m1t[k], "BE" if pos["be"] else "SL")
                    continue
                if not pos["be"] and h - xa >= pos["tp1"]:
                    pos["be"] = True
                    pos["sl"] = pos["entry"]
                    if p.partial_at_tp1 and pos["tp1"] < pos["tp2"]:
                        half = np.floor(pos["lot"] / 2 * 100 + 1e-9) / 100
                        if half >= 0.01:
                            close_pos(pos["tp1"], m1t[k], "TP1", half)
                if pos is not None and h - xa >= pos["tp2"]:
                    close_pos(pos["tp2"], m1t[k], "TP2")

        # ---------- ตอนแท่ง M5 ปิด ----------
        if pos is not None:
            Hd, Ld, Cd, Od = X[pos["d"]]
            xa = 0.0 if pos["d"] == 1 else p.spread
            if mod + tf >= p.eod_exit:
                close_pos(Cd[i] - xa, T5[i], "EOD")
            elif p.exit_on_fvg_fail and not pos["be"] and Cd[i] < pos["fvg_lo"]:
                close_pos(Cd[i] - xa, T5[i], "FVGFAIL")
        if pending is not None:
            Hd, Ld, Cd, Od = X[pending["d"]]
            if Cd[i] < pending["fvg_lo"] or mod + tf >= pending["expire"] or p.news_block[0] <= mod + tf < p.news_block[1]:
                pending = None

        if not day_ok:
            continue
        endm = mod + tf  # เวลาปิดแท่ง
        # ---------- เข้า Kill Zone: เตรียมระดับสภาพคล่อง ----------
        new_kz = None
        if p.trade_london and p.london[0] <= mod < p.london[1]:
            new_kz = "LON"
        elif p.trade_nyam and p.nyam[0] <= mod < p.nyam[1]:
            new_kz = "NY"
        if new_kz != kz:
            kz = new_kz
            for s in sides.values():
                s.reset()
            if kz is not None:
                kz_start, kz_end = (p.london if kz == "LON" else p.nyam)
                b, pdh, pdl = bias[cur_day]
                sl_ = slice(day_start_i, i)  # แท่งของวันนี้ก่อนเข้า KZ
                dm = MOD[sl_]

                def rng(a, b_):
                    m = (dm >= a) & (dm < b_)
                    if not m.any():
                        return None
                    return H[sl_][m].max(), L[sl_][m].min()

                def after(a):
                    m = dm >= a
                    if not m.any():
                        return -np.inf, np.inf
                    return H[sl_][m].max(), L[sl_][m].min()

                highs, lows = [], []  # (price, tag) ที่ยังไม่ถูกกวาด
                r = rng(*p.asia)
                if r:
                    ah, al = after(p.asia[1])
                    if r[0] > ah:
                        highs.append((r[0], "ASIA"))
                    if r[1] < al:
                        lows.append((r[1], "ASIA"))
                if kz == "NY":
                    r = rng(*p.london)
                    if r:
                        ah, al = after(p.london[1])
                        if r[0] > ah:
                            highs.append((r[0], "LON"))
                        if r[1] < al:
                            lows.append((r[1], "LON"))
                th, tl = (H[sl_].max(), L[sl_].min()) if i > day_start_i else (-np.inf, np.inf)
                if pdh > th:
                    highs.append((pdh, "PD"))
                if pdl < tl:
                    lows.append((pdl, "PD"))
                hi = np.searchsorted(h1t, T5[i].astype("datetime64[h]"))
                if p.use_swing_levels and hi >= p.swing_lookback:
                    hh, ll = h1h[hi - p.swing_lookback:hi], h1l[hi - p.swing_lookback:hi]
                    nh = nl = 0
                    for k in range(len(hh) - 3, 1, -1):  # swing H1 (2 แท่งสองข้าง) ที่ยังไม่ถูกกวาด
                        if nh < p.swing_max and hh[k] > max(hh[k - 2], hh[k - 1], hh[k + 1], hh[k + 2]) \
                                and hh[k] > hh[k + 1:].max():
                            highs.append((hh[k], "SWING"))
                            nh += 1
                        if nl < p.swing_max and ll[k] < min(ll[k - 2], ll[k - 1], ll[k + 1], ll[k + 2]) \
                                and ll[k] < ll[k + 1:].min():
                            lows.append((ll[k], "SWING"))
                            nl += 1
                for d, s in sides.items():
                    mine = lows if d == 1 else highs      # ฝั่งที่จะถูกกวาด
                    opp = highs if d == 1 else lows       # เป้าหมาย
                    s.targets = sorted(d * x[0] for x in opp)
                    if p.use_ict_levels and (not p.use_bias or b == d):
                        for price, tag in mine:
                            s.levels.append([d * price, tag, None, None, False])
                if p.use_wyckoff:
                    wr = wyckoff_range(h1h[:hi], h1l[:hi], h1c[:hi], p)
                    if wr is not None:
                        rl, rh = wr
                        mid = (rl + rh) / 2
                        sides[1].levels.append([rl, "WYCK", mid, rh, False])
                        sides[-1].levels.append([-rh, "WYCK", -mid, -rl, False])
        if kz is None:
            continue

        # ---------- ติดตามการกวาด / MSS ----------
        for d, s in sides.items():
            if not s.levels:
                continue
            Hd, Ld, Cd, Od = X[d]
            lo = Ld[i]
            new_ext = False
            for lv in s.levels:
                if not lv[4] and lo < lv[0]:
                    lv[4] = True
                    s.lvl = lv
                    new_ext = True
            if s.ext is not None and lo < s.ext:
                new_ext = True
            if new_ext and (s.ext is None or lo < s.ext):
                s.ext, s.ext_i, s.fired = lo, i, False
                s.mss = None
                for j in range(i - 1, max(i - 40, 1), -1):  # swing high ล่าสุดก่อนจุดกวาด
                    if Hd[j] > Hd[j - 1] and Hd[j] > Hd[j + 1] and Hd[j] > Cd[i]:
                        s.mss = Hd[j]
                        break
                continue
            if s.ext is None or s.fired or s.mss is None or (i - s.ext_i) * tf > p.max_mss_min:
                continue
            if Cd[i] <= s.mss:
                continue
            # ---- เกิด MSS ----
            cnt("mss")
            s.fired = True
            if pending is not None or pos is not None:
                cnt("busy")
                continue
            if day_trades >= p.max_trades_day or day_losses >= p.max_losses_day:
                cnt("daycap")
                continue
            if p.news_block[0] <= endm < p.news_block[1] or endm >= kz_end:
                cnt("time")
                continue
            e = s.ext_i
            if e < 20:
                continue
            avg_body = body[e - 20:e].mean()
            A = rng5[e - 20:e].mean()
            leg_body = (Cd[e:i + 1] - Od[e:i + 1]).max()
            if leg_body < p.disp_mult * avg_body:
                cnt("disp")
                continue
            if p.vol_mult > 0 and V[e:i + 1].mean() < p.vol_mult * V[max(e - 20, 0):e].mean():
                cnt("vol")
                continue
            leg_high = Hd[e:i + 1].max()
            eq = (leg_high + s.ext) / 2
            setup = None
            for j in range(i, e, -1):  # FVG จากบนลงล่าง
                g_lo, g_hi = Hd[j - 2], Ld[j]
                if g_hi - g_lo < p.min_fvg * A:
                    continue
                ce = (g_lo + g_hi) / 2
                if j < i and Ld[j + 1:i + 1].min() <= ce:
                    continue  # ถูกเติมเกินครึ่งแล้ว
                ent = ce if p.entry_ce else g_hi
                if p.require_discount and ent > eq:
                    if ce <= eq:
                        ent = ce
                    else:
                        continue
                setup = (ent, g_lo)
                break
            if setup is None:
                cnt("nofvg")
                continue
            ent, fvg_lo = setup
            sl = s.ext - p.sl_buffer * A
            risk = ent - sl
            if risk < p.min_risk * A or risk > p.max_risk * A:
                cnt("risk")
                continue
            lv = s.lvl
            if lv[1] == "WYCK":
                tp1, tp2 = lv[2], lv[3]
                if tp2 - ent < p.min_rr * risk:
                    cnt("wy_rr")
                    continue
            else:
                tp2 = None
                day_hi = Hd[day_start_i:i + 1].max()
                for tgt in s.targets:
                    if tgt > day_hi and tgt - ent >= p.min_rr * risk:
                        tp2 = tgt
                        break
                if tp2 is None:
                    if p.fallback_rr <= 0:
                        cnt("no_target")
                        continue
                    tp2 = ent + p.fallback_rr * risk
                tp1 = None
                for j in range(e - 1, max(e - 96, 1), -1):
                    if Hd[j] > leg_high and Hd[j] > Hd[j - 1] and Hd[j] > Hd[j + 1]:
                        tp1 = Hd[j]
                        break
                if tp1 is None:
                    tp1 = leg_high
            tp1 = min(max(tp1, ent + risk), tp2)
            lot = np.floor(equity * p.risk_pct / 100 / (risk * OZ_PER_LOT) * 100 + 1e-9) / 100
            if lot < 0.01:
                cnt("lot")
                continue
            cnt("order")
            pending = dict(d=d, entry=ent, sl=sl, tp1=tp1, tp2=tp2, lot=lot, fvg_lo=fvg_lo, expire=kz_end + p.order_grace,
                           tag=lv[1], kz=kz, risk_usd=risk * OZ_PER_LOT * lot + p.commission * lot)

    run.funnel = funnel
    return pd.DataFrame(trades), pd.DataFrame(eq_curve, columns=["day", "equity"])


def stats(tr: pd.DataFrame, p: Params) -> dict:
    if len(tr) == 0:
        return dict(trades=0)
    eq = np.concatenate([[p.balance], tr.equity.to_numpy()])
    peak = np.maximum.accumulate(eq)
    dd = ((peak - eq) / peak).max() * 100
    wins = tr[tr.pnl > 0]
    loss = tr[tr.pnl <= 0]
    gp, gl = wins.pnl.sum(), -loss.pnl.sum()
    return dict(trades=len(tr), win_rate=round(len(wins) / len(tr) * 100, 1),
                net=round(tr.pnl.sum(), 2), ret_pct=round((eq[-1] / p.balance - 1) * 100, 2),
                pf=round(gp / gl, 2) if gl > 0 else float("inf"),
                expectancy_R=round(tr.R.mean(), 3), avg_win_R=round(wins.R.mean(), 2) if len(wins) else 0,
                avg_loss_R=round(loss.R.mean(), 2) if len(loss) else 0, max_dd_pct=round(dd, 2))
