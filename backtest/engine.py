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
    use_model_2022: bool = True     # 2022 Mentorship Model (กวาด -> MSS -> FVG)
    use_silver_bullet: bool = False # Silver Bullet: FVG แรกในชั่วโมง
    sb_windows: tuple = ((600, 660), (1020, 1080), (1260, 1320))  # 03-04, 10-11, 14-15 NY
    sb_tp1_r: float = 0.0           # แบ่งปิด/เลื่อน SL เท่าทุนเมื่อกำไรกี่ R (0 = ไม่ใช้)
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
    wy_tfs: tuple = (60,)           # timeframe (นาที) ที่ใช้หากรอบ ไล่จากใหญ่ไปเล็ก หยุดเมื่อเจอกรอบ
    wy_bars: int = 72
    wy_min_width: float = 3.0       # ความกว้างกรอบขั้นต่ำ (เท่าของค่าเฉลี่ย high-low H1 ในกรอบ)
    wy_max_drift: float = 0.5       # |close สุดท้าย - close แรก| / ความกว้างกรอบ
    wy_min_touches: int = 2
    # --- ออเดอร์ ---
    sl_buffer: float = 0.5          # เผื่อ SL เลยจุดกวาด (เท่าของ A)
    min_risk: float = 2.0           # ระยะ SL สั้นกว่านี้ข้าม (เท่าของ A)
    max_risk: float = 12.0          # ระยะ SL กว้างกว่านี้ข้าม (เท่าของ A)
    min_rr: float = 2.0
    tp_mode: str = "liquidity"      # "liquidity" = สภาพคล่องฝั่งตรงข้าม, "range" = swing ก่อนกลับตัว + ขอบ dealing range
    tp_swing_strength: int = 2      # โหมด range: ความแรง swing H1 ที่ใช้เป็น TP1
    range_lookback: int = 3000      # โหมด range: ย้อนหาจุดที่โซนเกิดไม่เกินกี่แท่ง
    sl_mode: str = "wick"           # "wick" = เลยไส้ที่กวาด, "zone" = พ้นโซน (x ATR H1)
    sl_zone_atr: float = 1.5
    sl_zone_max: float = 2.5        # เพดานระยะ SL โหมด zone (x ATR H1)
    order_grace: int = 60           # นาทีที่ออเดอร์รอได้หลังหมด Kill Zone
    fallback_rr: float = 0.0        # ถ้าไม่มีเป้าสภาพคล่อง ใช้ RR คงที่ (0 = ไม่เข้า)
    partial_at_tp1: bool = True
    exit_on_fvg_fail: bool = True   # แท่ง M5 ปิดทะลุ FVG สวนทาง -> ปิดเอง
    # --- Fibonacci: TF ใหญ่บอกเทรนด์หลัก, TF เล็กหาจังหวะเข้า ---
    htf_fib: bool = False           # ใช้ Fibonacci ของ swing บน TF ใหญ่เป็นตัวกรองเทรนด์หลัก + โซนราคา
    htf_tf: int = 60                # TF ใหญ่หลัก (นาที)
    htf_strength: int = 3           # ความแรง swing บน TF ใหญ่
    htf_min_retr: float = 0.5       # ราคาต้องย่อเข้ามาอย่างน้อยเท่านี้ของขาใหญ่ (0.5 = ครึ่ง Discount/Premium)
    htf_max_retr: float = 1.0
    ltf_fib: bool = False           # จุดเข้าที่ระดับ Fibonacci ของขา displacement บน TF เล็ก (แทนขอบ FVG)
    fib_entry: float = 0.705
    fib_need_fvg: bool = False      # โซน 0.62-0.79 ต้องมี FVG ซ้อนอยู่
    fib_tp_ext: float = 0.27        # tp_mode="fib": TP1 = ระดับ 0, TP2 = ระดับ -0.27
    # --- Quarter Zone: กรอบ 0 / 0.25 / 0.5 / 0.75 / 1 ของขา TF ใหญ่ (ใช้ htf_tf, htf_strength) ---
    quarter_zones: bool = False     # ขอบกรอบเป็นระดับที่รอให้ราคามาแตะ แล้วยืนยันบน TF เล็ก (กวาด -> MSS -> FVG)
    qz_band: float = 0.059          # ขอบกรอบห่างจากเส้นกลางเท่านี้ของขา
    qz_mid_trend: bool = True       # กรอบ 0.5 เข้าตามเทรนด์หลักของ TF ใหญ่เท่านั้น (ไม่มองเป็นจุดกลับตัว)
    qz_ct_ltf: bool = True          # ไม้สวนเทรนด์หลัก: TP ตามขาของ TF เล็ก (ระดับ 0 และ -0.27) แทนกรอบ TF ใหญ่
    qz_all_ltf: bool = False        # ทุกไม้ใช้ TP ตามขาของ TF เล็ก
    qz_conf_tfs: tuple = ()         # TF อื่นที่ดูควบกัน (นาที) เช่น (240, 15): ขอบของ TF หลักต้องอยู่ในกรอบของ TF เหล่านี้ด้วย
    qz_min_conf: int = 1            # ต้องตรงกับ TF อื่นอย่างน้อยกี่ TF
    # --- Order Block H1: ราคาแทงผ่านโซนแล้วถูกดึงกลับเข้าโซน -> เข้า Market ---
    ob_model: bool = False
    ob_window: tuple = (900, 1080)  # ช่วงเวลาที่เข้าได้ (นาทีนับจาก 17:00 NY) ค่าเริ่มต้น 08:00-11:00 NY
    ob_disp: float = 1.5            # แท่งที่ออกจาก OB: ตัวแท่ง >= กี่เท่าของค่าเฉลี่ย 20 แท่ง H1
    ob_break_bars: int = 3          # ต้องปิดทะลุ OB ภายในกี่แท่ง H1
    ob_max_age: int = 120           # อายุโซน (ชั่วโมง)
    ob_max_zones: int = 6           # จำนวนโซนต่อฝั่ง
    ob_sl_buf: float = 0.5          # SL พ้นขอบโซน (เท่าของ A)
    ob_min_risk: float = 2.0        # ระยะ SL ขั้นต่ำ (เท่าของ A)
    ob_rr: float = 3.0              # TP = RR คงที่ (เท่าของความเสี่ยง)
    ob_need_sweep: bool = True      # ต้องแทงทะลุขอบโซนก่อน (false = แค่แตะโซนแล้วมีแท่งกลับตัว)
    ob_max_depth: float = 0.0       # แทงเลยโซนได้ไม่เกินกี่เท่าของความสูงโซน (0 = ไม่จำกัด)
    ob_steps: int = 0               # ยืนยันกลับตัวบน TF เล็ก: ต้องปิดทะลุ swing high ก่อนจุดต่ำสุดกี่ขั้น (0 = ใช้แท่งปิดกลับเข้าโซน)
    ob_step_strength: int = 2       # ความแรง swing ของแต่ละขั้น (แท่งซ้าย/ขวา)
    ob_max_entry: float = 1.0       # โหมดขั้น: จุดเข้าอยู่เหนือขอบบนโซนได้ไม่เกินกี่เท่าของความสูงโซน
    ob_retest_step: int = 0         # หลังผ่านครบทุกขั้น ตั้ง Limit รอราคาย่อกลับมาที่ขั้นนี้ (1 = ขั้นแรก, 0 = เข้า Market ทันที)
    ob_sl_mode: str = "zone"        # "zone" = ใต้ขอบโซน H1, "low" = ใต้จุดต่ำสุดของการกลับตัว, "hl" = ใต้ higher low หลังจุดต่ำสุด
    ob_sl_struct_buf: float = 0.2   # ระยะเผื่อของ SL แบบโครงสร้าง (เท่าของ A)
    ob_tp_hidden: bool = False      # TP ที่ hidden zone ของ TF ใหญ่ (ไส้ซ้อนกัน) ที่ใกล้สุดและให้ RR >= ob_hz_min_rr
    ob_hz_tfs: tuple = (240, 60)
    ob_hz_bars: int = 3
    ob_hz_min_rr: float = 2.0
    ob_sw_min: int = 0              # ตัด setup เมื่อ TF ใน ob_sw_tfs เป็น sideway อย่างน้อยกี่ TF (0 = ปิด)
    ob_sw_tfs: tuple = (5, 15, 30)
    ob_sw_bars: int = 20            # จำนวนแท่งที่ใช้วัด
    ob_sw_er: float = 0.3           # efficiency ratio ต่ำกว่านี้ = sideway
    # --- ตัวเลือกจาก ICT_TopDown ---
    persist_zones: bool = False     # เก็บโซนข้ามวันจนกว่าจะถูกแตะ
    zone_cap: int = 64
    sweep_pa_bars: int = 0          # ต้องมีแท่งกลับตัวภายในกี่แท่งจากจุดสุดของไส้ (0 = ไม่บังคับ)
    require_reclaim: bool = False   # แท่ง MSS ต้องปิดกลับเหนือโซนที่ถูกกวาด
    mss_vol_mult: float = 0.0       # volume แท่ง MSS > ค่าเฉลี่ย 50 แท่ง x เท่านี้ (0 = ปิด, ข้ามถ้าข้อมูลไม่มี volume)
    entry_pa: bool = False          # รอแท่งปฏิเสธใน FVG แล้วเข้า Market (แทนการตั้ง Limit)
    pa_wait: int = 10               # รอแท่งปฏิเสธใน FVG ได้กี่แท่ง
    pin_wick_ratio: float = 2.0
    max_spread_to_sl: float = 0.0   # spread / ระยะ SL สูงสุด (0 = ปิด)
    risk_pct_london: float = 0.0    # ความเสี่ยงไม้ช่วง London (0 = ใช้ risk_pct)
    max_daily_loss_pct: float = 0.0 # หยุดเมื่อขาดทุนของวันถึง % นี้ (0 = ปิด)
    be_plus: float = 0.0            # กันทุนบวก (ดอลลาร์) หลังถึง TP1
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
        self.cand = False
        self.qz_done = False


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
    h1o = pd.DataFrame({"h": hkey, "open": O}).groupby("h").open.first().to_numpy()
    h1t = h1.index.to_numpy()
    h1h, h1l, h1c = h1.high.to_numpy(), h1.low.to_numpy(), h1.close.to_numpy()
    hk = T5.astype("datetime64[m]").astype("int64") // p.htf_tf
    gh_ = pd.DataFrame({"k": hk, "high": H, "low": L, "close": C}).groupby("k").agg(
        high=("high", "max"), low=("low", "min"), close=("close", "last"))
    htk, htH, htL, htC = gh_.index.to_numpy(), gh_.high.to_numpy(), gh_.low.to_numpy(), gh_.close.to_numpy()

    def htf_fib(i, d):
        """เทรนด์หลักจากโครงสร้าง TF ใหญ่ และระดับที่ราคาย่อเข้ามาในขาใหญ่ (0 = ปลายขา, 1 = ต้นขา)
        คืน (trend, retracement, ต้นขา', ปลายขา') ในพิกัดของทิศ d"""
        cut = np.searchsorted(htk, hk[i])            # แท่ง TF ใหญ่ที่ปิดแล้ว
        st = p.htf_strength
        a = max(cut - 300, st)
        trend, sh, sl_, shB, slB = 0, 0.0, 0.0, True, True
        for j in range(a + st, cut):
            k = j - st
            if k - st >= 0:
                if htH[k] > htH[k - st:k].max() and htH[k] > htH[k + 1:k + st + 1].max():
                    sh, shB = htH[k], False
                if htL[k] < htL[k - st:k].min() and htL[k] < htL[k + 1:k + st + 1].min():
                    sl_, slB = htL[k], False
            if not shB and htC[j] > sh:
                trend, shB = 1, True
            if not slB and htC[j] < sl_:
                trend, slB = -1, True
        Hh, Lh = (htH, htL) if d == 1 else (-htL, -htH)
        for k in range(cut - st - 1, a, -1):         # swing low' ล่าสุด = ต้นขา
            if Lh[k] < Lh[k - st:k].min() and Lh[k] < Lh[k + 1:k + st + 1].min():
                lo = Lh[k]
                hi_ = max(Hh[k:cut].max(), X[d][0][day_start_i:i + 1].max())
                if hi_ <= lo:
                    return trend, None, lo, hi_
                return trend, (hi_ - X[d][2][i]) / (hi_ - lo), lo, hi_
        return trend, None, None, None

    tfb = {p.htf_tf: (htk, htH, htL)}
    for m_ in p.qz_conf_tfs:
        if m_ not in tfb:
            k_ = T5.astype("datetime64[m]").astype("int64") // m_
            g_ = pd.DataFrame({"k": k_, "high": H, "low": L}).groupby("k").agg(high=("high", "max"), low=("low", "min"))
            tfb[m_] = (g_.index.to_numpy(), g_.high.to_numpy(), g_.low.to_numpy())

    def qz_range(i, m=None):
        """กรอบของ TF m: swing low และ swing high ล่าสุดที่ยืนยันแล้ว คืน (low, high) หรือ None"""
        m = m or p.htf_tf
        tk_, tH_, tL_ = tfb[m]
        cut = np.searchsorted(tk_, T5[i].astype("datetime64[m]").astype("int64") // m)
        st = p.htf_strength
        lo = hi_ = None
        for k in range(cut - st - 1, max(cut - 300, st), -1):
            if hi_ is None and tH_[k] > tH_[k - st:k].max() and tH_[k] > tH_[k + 1:k + st + 1].max():
                hi_ = tH_[k]
            if lo is None and tL_[k] < tL_[k - st:k].min() and tL_[k] < tL_[k + 1:k + st + 1].min():
                lo = tL_[k]
            if lo is not None and hi_ is not None:
                break
        if lo is None or hi_ is None or hi_ <= lo:
            return None
        return lo, hi_

    def qz_conf(i, price, d):
        """จำนวน TF อื่นที่ราคานี้อยู่ในกรอบ Quarter ฝั่งเดียวกัน (Buy: กรอบ 0-0.5, Sell: กรอบ 0.5-1)"""
        n_ = 0
        for m_ in p.qz_conf_tfs:
            rg = qz_range(i, m_)
            if rg is None:
                continue
            pos = (price - rg[0]) / (rg[1] - rg[0])
            for c in ((0.0, 0.25, 0.5) if d == 1 else (0.5, 0.75, 1.0)):
                if abs(pos - c) <= p.qz_band:
                    n_ += 1
                    break
        return n_

    wy = {}  # แท่งของแต่ละ timeframe ที่ใช้หากรอบ Wyckoff
    for m in p.wy_tfs:
        if m == 60:
            wy[m] = (h1t, h1h, h1l, h1c)
            continue
        key = T5.astype("datetime64[m]").astype("int64") // m
        g = pd.DataFrame({"k": key, "high": H, "low": L, "close": C}).groupby("k").agg(
            high=("high", "max"), low=("low", "min"), close=("close", "last"))
        wy[m] = (g.index.to_numpy(), g.high.to_numpy(), g.low.to_numpy(), g.close.to_numpy())

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
    day_pnl = 0.0
    day_eq0 = p.balance
    zs_hi, zs_lo = {}, {}           # โซนที่เก็บข้ามวัน: ราคา -> tag
    Ha, La, Ca, Oa = H, L, C, O

    def pa(i, d):
        """แท่งกลับตัว: Pin bar / Engulfing / Morning-Evening star (นิยามเดียวกับ ICT_TopDown)"""
        o, h, l, c = Oa[i], Ha[i], La[i], Ca[i]
        rg = h - l
        if rg > 0:
            bd = abs(c - o)
            up, dn = h - max(o, c), min(o, c) - l
            wick, opp = (dn, up) if d == 1 else (up, dn)
            if wick >= p.pin_wick_ratio * max(bd, rg * 0.1) and wick >= 0.55 * rg and opp <= 0.25 * rg:
                return True
        po, pc = Oa[i - 1], Ca[i - 1]
        cb, pb = d * (c - o), d * (po - pc)
        if cb > 0 and pb > 0 and ((c > po and o <= pc) if d == 1 else (c < po and o >= pc)):
            return True
        o1, c1, r1 = Oa[i - 2], Ca[i - 2], Ha[i - 2] - La[i - 2]
        b1 = d * (o1 - c1)
        if r1 > 0 and b1 >= 0.5 * r1 and abs(pc - po) <= 0.3 * b1 and cb > 0:
            mid = (o1 + c1) / 2
            return c > mid if d == 1 else c < mid
        return False

    def prune(i):
        for k in [k for k in zs_hi if Ha[i] > k]:
            del zs_hi[k]
        for k in [k for k in zs_lo if La[i] < k]:
            del zs_lo[k]

    # ---- Order Block บน H1: แท่งสีตรงข้ามแท่งสุดท้ายก่อนขาที่ปิดทะลุมันด้วย displacement ----
    ob_list = []                    # (เวลาที่เริ่มใช้ได้, ทิศ, ล่าง, บน)
    if p.ob_model:
        hb = np.abs(h1c - h1o)
        for k in range(20, len(h1c) - 1):
            for d_ in (1, -1):
                if d_ * (h1c[k] - h1o[k]) >= 0:
                    continue        # ต้องเป็นแท่งสวนทาง
                avg = hb[k - 20:k].mean()
                for m_ in range(k + 1, min(k + 1 + p.ob_break_bars, len(h1c))):
                    broke = h1c[m_] > h1h[k] if d_ == 1 else h1c[m_] < h1l[k]
                    if broke:
                        if (d_ * (h1c[k + 1:m_ + 1] - h1o[k + 1:m_ + 1])).max() >= p.ob_disp * avg:
                            ob_list.append((h1t[m_] + np.timedelta64(1, "h"), d_, h1l[k], h1h[k]))
                        break
        ob_list.sort(key=lambda z: z[0])
    ob_ptr = 0
    hz_sets = []
    if p.ob_model and p.ob_tp_hidden:
        for m_ in p.ob_hz_tfs:
            k_ = T5.astype("datetime64[m]").astype("int64") // m_
            g_ = pd.DataFrame({"k": k_, "o": O, "h": H, "l": L, "c": C}).groupby("k").agg(
                o=("o", "first"), h=("h", "max"), l=("l", "min"), c=("c", "last"))
            hz_sets.append((m_, g_.index.to_numpy(), g_.o.to_numpy(), g_.h.to_numpy(), g_.l.to_numpy(), g_.c.to_numpy()))
    W = np.lib.stride_tricks.sliding_window_view
    sw_sets = []
    if p.ob_model and p.ob_sw_min > 0:
        for m_ in p.ob_sw_tfs:
            if m_ < tf:                     # TF เล็กกว่าข้อมูลสัญญาณ: ใช้แท่ง M1
                k_ = m1["time"].astype("datetime64[m]").astype("int64") // m_
                g_ = pd.DataFrame({"k": k_, "c": m1["close"]}).groupby("k").c.last()
            else:
                k_ = T5.astype("datetime64[m]").astype("int64") // m_
                g_ = pd.DataFrame({"k": k_, "c": C}).groupby("k").c.last()
            c_ = g_.to_numpy()
            n_ = p.ob_sw_bars
            er = np.full(len(c_), np.nan)
            if len(c_) > n_:
                dif = np.abs(np.diff(c_))
                den = np.convolve(dif, np.ones(n_), "valid")          # ผลรวม |Δ| ของ n_ ช่วง
                num = np.abs(c_[n_:] - c_[:-n_])
                er[n_:] = np.where(den > 0, num / den, 1.0)
            sw_sets.append((m_, g_.index.to_numpy(), er))
    tmin = T5.astype("datetime64[m]").astype("int64")

    def sideway_count(i):
        """จำนวน TF ที่ efficiency ratio ของแท่งที่ปิดแล้วต่ำกว่าเกณฑ์"""
        n_ = 0
        for m_, keys, er in sw_sets:
            cut = np.searchsorted(keys, (tmin[i] + tf) // m_)
            if cut >= 1 and er[cut - 1] == er[cut - 1] and er[cut - 1] < p.ob_sw_er:
                n_ += 1
        return n_

    def hz_target(i, d, ent, risk):
        """hidden zone: ไส้ซ้อนกัน ob_hz_bars แท่งบน TF ใหญ่ ยังไม่ถูกปิดทะลุ คืนขอบใกล้ (ราคา') หรือ None"""
        best, nb = np.inf, p.ob_hz_bars
        for m_, tk, o_, h_, l_, c_ in hz_sets:
            cut = np.searchsorted(tk, T5[i].astype("datetime64[m]").astype("int64") // m_)
            a = max(0, cut - 300)
            if cut - a < nb + 2:
                continue
            if d == 1:
                top, hh, cc = np.maximum(o_[a:cut], c_[a:cut]), h_[a:cut], c_[a:cut]
            else:
                top, hh, cc = np.maximum(-o_[a:cut], -c_[a:cut]), -l_[a:cut], -c_[a:cut]
            zl, zh = W(top, nb).max(axis=1), W(hh, nb).min(axis=1)
            suf = np.maximum.accumulate(cc[::-1])[::-1]
            fut = np.append(suf[nb:], -np.inf)[:len(zl)]
            ok = (zh > zl) & (zl > ent) & (zl - ent >= p.ob_hz_min_rr * risk) & (fut <= zh)
            if ok.any():
                best = min(best, zl[ok].min())
        return None if not np.isfinite(best) else best

    ob_act = []                     # [ทิศ, ล่าง', บน', เวลาเกิด, แทงผ่านแล้ว, จุดต่ำสุด']
    sb_win = None
    sb_done = False
    sb_tg = {}
    day_start_i = 0
    m1o, m1h, m1l, m1c, m1t = m1["open"], m1["high"], m1["low"], m1["close"], m1["time"]

    def close_pos(price_t, when, reason, frac_lot=None):
        nonlocal equity, pos, day_losses, day_pnl
        lot = pos["lot"] if frac_lot is None else frac_lot
        pnl = (price_t - pos["entry"]) * OZ_PER_LOT * lot - p.commission * lot
        equity += pnl
        day_pnl += pnl
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

    def liq(i, day, d0, with_lon):
        """สภาพคล่องที่ยังไม่ถูกกวาด ณ แท่ง i: คืน (highs, lows, จุดสูงวันนี้, จุดต่ำวันนี้, จำนวนแท่ง H1 ที่ปิดแล้ว)"""
        b, pdh, pdl = bias[day]
        sl_ = slice(d0, i)  # แท่งของวันนี้ก่อนเข้า KZ
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
        if with_lon:
            r = rng(*p.london)
            if r:
                ah, al = after(p.london[1])
                if r[0] > ah:
                    highs.append((r[0], "LON"))
                if r[1] < al:
                    lows.append((r[1], "LON"))
        th, tl = (H[sl_].max(), L[sl_].min()) if i > d0 else (-np.inf, np.inf)
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
        return highs, lows, th, tl, hi

    for i in range(n):
        mod = MOD[i]
        # ---------- วันใหม่ ----------
        if DAY[i] != cur_day:
            cur_day = DAY[i]
            day_trades = day_losses = 0
            day_pnl, day_eq0 = 0.0, equity
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
                    if not pending.get("wait_pa") and l + ea <= pending["entry"]:
                        pos = dict(pending, t_open=m1t[k], pnl=0.0, be=False, sl0=pending["sl"], lot0=pending["lot"])
                        pending = None
                        day_trades += 1
                        if l - xa <= pos["sl"]:
                            close_pos(pos["sl"], m1t[k], "SL")
                        continue
                    if h - xa >= (pending["tp2"] if (pending["tag"] == "SB" or p.ltf_fib) else pending["tp1"]):
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
                    pos["sl"] = pos["entry"] + p.be_plus
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

        if pending is not None and pending.get("wait_pa"):
            d = pending["d"]
            Hd, Ld, Cd, Od = X[d]
            pending["age"] += 1
            if pending["age"] > p.pa_wait or Ld[i] < pending["ext"]:
                pending = None
            elif Ld[i] <= pending["entry"] and pa(i, d):
                ent = Cd[i] + (p.spread if d == 1 else 0.0)   # เข้า Market ที่ราคาปิดแท่งปฏิเสธ
                risk = ent - pending["sl"]
                tgt = pending["tp1"] if p.tp_mode == "range" else pending["tp2"]
                rp = p.risk_pct_london if (pending["kz"] == "LON" and p.risk_pct_london > 0) else p.risk_pct
                lot = np.floor(equity * rp / 100 / (risk * OZ_PER_LOT) * 100 + 1e-9) / 100 if risk > 0 else 0
                ok = (risk > 0 and tgt - ent >= p.min_rr * risk and lot >= 0.01
                      and not (p.max_spread_to_sl > 0 and p.spread / risk > p.max_spread_to_sl)
                      and (p.london[0] <= mod + tf <= p.london[1] or p.nyam[0] <= mod + tf <= p.nyam[1]))
                if ok:
                    pos = dict(pending, entry=ent, lot=lot, t_open=T5[i], pnl=0.0, be=False, sl0=pending["sl"], lot0=lot,
                               tp1=max(pending["tp1"], ent), risk_usd=risk * OZ_PER_LOT * lot + p.commission * lot)
                    day_trades += 1
                pending = None

        if not day_ok:
            if p.persist_zones:
                prune(i)
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
                b = bias[cur_day][0]
                highs, lows, _, _, hi = liq(i, cur_day, day_start_i, kz == "NY")
                if p.persist_zones:
                    for store, new in ((zs_hi, highs), (zs_lo, lows)):
                        for price, tag in new:
                            store.setdefault(price, tag)
                        while len(store) > p.zone_cap:
                            del store[next(iter(store))]
                    highs, lows = list(zs_hi.items()), list(zs_lo.items())
                for d, s in sides.items():
                    mine = lows if d == 1 else highs      # ฝั่งที่จะถูกกวาด
                    opp = highs if d == 1 else lows       # เป้าหมาย
                    s.targets = sorted(d * x[0] for x in opp)
                    if p.use_ict_levels and (not p.use_bias or b == d):
                        for price, tag in mine:
                            s.levels.append([d * price, tag, None, None, False])
                if p.use_wyckoff:
                    for m in p.wy_tfs:  # ไล่จาก timeframe ใหญ่ลงเล็ก หยุดเมื่อเจอกรอบ
                        wt, wh, wl, wc = wy[m]
                        cut = hi if m == 60 else np.searchsorted(wt, T5[i].astype("datetime64[m]").astype("int64") // m)
                        wr = wyckoff_range(wh[:cut], wl[:cut], wc[:cut], p)
                        if wr is not None:
                            rl, rh = wr
                            mid = (rl + rh) / 2
                            sides[1].levels.append([rl, f"WYCK{m}", mid, rh, False])
                            sides[-1].levels.append([-rh, f"WYCK{m}", -mid, -rl, False])
                            break
        if p.quarter_zones and kz is not None and not sides[1].qz_done:
            sides[1].qz_done = True
            rg = qz_range(i)
            if rg is not None and i > 0:
                lo_, hi_ = rg
                r_, b_, px = hi_ - lo_, p.qz_band, C[i - 1]
                trend = htf_fib(i, 1)[0]
                P = lambda v: lo_ + v * r_
                for c in ((0.0, 0.25) if p.qz_mid_trend else (0.0, 0.25, 0.5)):   # ขอบล่างฝั่ง Discount -> Buy
                    if px > P(c - b_):
                        sides[1].levels.append([P(c - b_), "QZ", P(c + b_), P(c + 0.25 - b_), False,
                                                p.qz_all_ltf or (p.qz_ct_ltf and trend == -1)])
                for c in ((0.75, 1.0) if p.qz_mid_trend else (0.5, 0.75, 1.0)):   # ขอบบนฝั่ง Premium -> Sell
                    if px < P(c + b_):
                        sides[-1].levels.append([-P(c + b_), "QZ", -P(c - b_), -P(c - 0.25 + b_), False,
                                                 p.qz_all_ltf or (p.qz_ct_ltf and trend == 1)])
                if p.qz_mid_trend and trend == 1:      # กรอบ 0.5: เข้าตามเทรนด์หลักเท่านั้น
                    for e_, t1, t2 in ((0.5 - b_, 0.5 + b_, 0.75 - b_), (0.5 + b_, 0.75 - b_, 0.75 + b_)):
                        if px > P(e_):
                            sides[1].levels.append([P(e_), "QZ", P(t1), P(t2), False, p.qz_all_ltf])
                elif p.qz_mid_trend and trend == -1:
                    for e_, t1, t2 in ((0.5 + b_, 0.5 - b_, 0.25 + b_), (0.5 - b_, 0.25 + b_, 0.25 - b_)):
                        if px < P(e_):
                            sides[-1].levels.append([-P(e_), "QZ", -P(t1), -P(t2), False, p.qz_all_ltf])
                if p.qz_conf_tfs:               # ดูควบหลาย TF: เก็บเฉพาะขอบที่ตรงกับกรอบของ TF อื่น
                    for d_ in (1, -1):
                        sides[d_].levels = [lv for lv in sides[d_].levels
                                            if lv[1] != "QZ" or qz_conf(i, d_ * lv[0], d_) >= p.qz_min_conf]
        if p.persist_zones:
            prune(i)
        # ---------- Order Block H1: แทงผ่านโซน -> ดึงกลับเข้าโซน -> เข้า Market ----------
        if p.ob_model:
            tnow = T5[i]
            while ob_ptr < len(ob_list) and ob_list[ob_ptr][0] <= tnow:
                _, d_, zl, zh = ob_list[ob_ptr]
                ob_ptr += 1
                ob_act.append([d_, zl, zh, tnow, False, None, -1, None, []] if d_ == 1 else [d_, -zh, -zl, tnow, False, None, -1, None, []])
                same = [z for z in ob_act if z[0] == d_]
                if len(same) > p.ob_max_zones:
                    ob_act.remove(same[0])
            hour_end = (mod + tf) % 60 == 0
            for z in list(ob_act):
                d_ = z[0]
                Hd, Ld, Cd, Od = X[d_]
                if (tnow - z[3]) / np.timedelta64(1, "h") > p.ob_max_age or (hour_end and Cd[i] < z[1]):
                    ob_act.remove(z)        # หมดอายุ หรือแท่ง H1 ปิดหลุดโซน
                    continue
                touched = Ld[i] < z[1] if p.ob_need_sweep else Ld[i] <= z[2]
                if touched:
                    z[4] = True
                if z[4] and (z[5] is None or Ld[i] < z[5]):
                    z[5], z[6], z[7], z[8] = Ld[i], i, None, []   # จุดต่ำสุดใหม่: หาขั้นใหม่
                    if p.ob_steps > 0:
                        st_, found, last = p.ob_step_strength, 0, -np.inf
                        for j in range(i - st_ - 1, max(i - 180, st_), -1):
                            if Hd[j] > last and Hd[j] > Hd[j - st_:j].max() and Hd[j] > Hd[j + 1:j + st_ + 1].max():
                                last = Hd[j]
                                found += 1
                                z[8].append(last)
                                if found == p.ob_steps:
                                    z[7] = last
                                    break
                if not z[4] or pos is not None or pending is not None or i < 22:
                    continue
                if not (p.ob_window[0] <= endm <= p.ob_window[1]):
                    continue
                if day_trades >= p.max_trades_day or day_losses >= p.max_losses_day or \
                        (p.max_daily_loss_pct > 0 and day_pnl <= -p.max_daily_loss_pct / 100 * day_eq0):
                    continue
                hgt = z[2] - z[1]
                if p.ob_max_depth > 0 and z[1] - z[5] > p.ob_max_depth * hgt:
                    ob_act.remove(z)        # แทงลึกเกิน = โซนแตก
                    continue
                if p.ob_steps > 0:
                    if z[7] is None or i <= z[6] or Cd[i] <= z[7] or Cd[i] <= z[1]:
                        continue            # ต้องปิดทะลุครบทุกขั้น
                    if p.ob_retest_step == 0 and Cd[i] > z[2] + p.ob_max_entry * hgt:
                        continue            # เข้า Market: ยังไม่ไกลจากโซนเกินไป
                elif not (z[1] < Cd[i] <= z[2] + 0.25 * hgt and Cd[i] > Od[i]):
                    continue                # ต้องปิดกลับเข้าโซนด้วยแท่งตามทิศ
                if p.ob_sw_min > 0 and sideway_count(i) >= p.ob_sw_min:
                    continue                # TF 5-30 นาทีอยู่ใน sideway = setup หลอก
                A = rng5[i - 20:i].mean()
                limit = p.ob_steps > 0 and p.ob_retest_step > 0
                ent = z[8][p.ob_retest_step - 1] if limit else Cd[i] + (p.spread if d_ == 1 else 0.0)
                if p.ob_sl_mode == "low" and z[5] is not None:
                    sl = z[5] - p.ob_sl_struct_buf * A
                elif p.ob_sl_mode == "hl" and z[6] is not None and i > z[6]:
                    sl = Ld[z[6] + 1:i + 1].min() - p.ob_sl_struct_buf * A
                else:
                    sl = z[1] - p.ob_sl_buf * A
                risk = ent - sl
                if risk <= 0:
                    continue
                if risk < p.ob_min_risk * A:
                    continue
                if p.max_spread_to_sl > 0 and p.spread / risk > p.max_spread_to_sl:
                    continue
                rp = p.risk_pct_london if (p.london[0] <= mod < p.london[1] and p.risk_pct_london > 0) else p.risk_pct
                lot = np.floor(equity * rp / 100 / (risk * OZ_PER_LOT) * 100 + 1e-9) / 100
                if lot < 0.01:
                    continue
                tp = ent + p.ob_rr * risk
                if p.ob_tp_hidden:
                    t_ = hz_target(i, d_, ent, risk)
                    if t_ is not None:
                        tp = t_
                    elif p.ob_rr <= 0:
                        continue
                if limit:                   # ตั้ง Limit ที่ขั้นที่ทะลุ รอราคาย่อกลับมา
                    pending = dict(d=d_, entry=ent, sl=sl, tp1=tp, tp2=tp, lot=lot, fvg_lo=sl, tag="OB",
                                   expire=p.ob_window[1] + p.order_grace, kz="NY",
                                   risk_usd=risk * OZ_PER_LOT * lot + p.commission * lot)
                    ob_act.remove(z)
                    break
                pos = dict(d=d_, entry=ent, sl=sl, tp1=tp, tp2=tp, lot=lot, fvg_lo=-np.inf, expire=0, tag="OB",
                           kz="LON" if p.london[0] <= mod < p.london[1] else "NY" if p.nyam[0] <= mod < p.nyam[1] else "OTH",
                           risk_usd=risk * OZ_PER_LOT * lot + p.commission * lot,
                           t_open=T5[i], pnl=0.0, be=False, sl0=sl, lot0=lot)
                day_trades += 1
                ob_act.remove(z)
                break
        # ---------- Silver Bullet: FVG แรกในชั่วโมงที่ชี้ไปทางเป้า ----------
        if p.use_silver_bullet:
            win = None
            for w in p.sb_windows:
                if w[0] <= mod < w[1]:
                    win = w
            if win != sb_win:
                sb_win, sb_done = win, False
                if win is not None:
                    highs, lows, th, tl, _ = liq(i, cur_day, day_start_i, mod >= p.london[1])
                    sb_tg = {1: sorted([x[0] for x in highs] + [th]), -1: sorted([-x[0] for x in lows] + [-tl])}
            if (win is not None and not sb_done and pending is None and pos is None and i >= 22
                    and MOD[i - 1] >= win[0] and endm < win[1]
                    and day_trades < p.max_trades_day and day_losses < p.max_losses_day
                    and not (p.news_block[0] <= endm < p.news_block[1])):
                b = bias[cur_day][0]
                A = rng5[i - 22:i - 2].mean()
                for d in (1, -1):
                    if p.use_bias and b != d:
                        continue
                    Hd, Ld, Cd, Od = X[d]
                    g_lo, g_hi = Hd[i - 2], Ld[i]
                    if g_hi - g_lo < p.min_fvg * A:
                        continue
                    ent = (g_lo + g_hi) / 2 if p.entry_ce else g_hi
                    sl = Ld[i - 2] - p.sl_buffer * A      # หลังแท่งที่ 1 ของช่อง
                    risk = ent - sl
                    if risk < p.min_risk * A or risk > p.max_risk * A:
                        continue
                    day_hi = Hd[day_start_i:i + 1].max()
                    tp2 = None
                    for tgt in sb_tg[d]:
                        if tgt >= day_hi and tgt - ent >= p.min_rr * risk:
                            tp2 = tgt
                            break
                    if tp2 is None:
                        continue
                    lot = np.floor(equity * p.risk_pct / 100 / (risk * OZ_PER_LOT) * 100 + 1e-9) / 100
                    if lot < 0.01:
                        continue
                    tp1 = min(ent + p.sb_tp1_r * risk, tp2) if p.sb_tp1_r > 0 else tp2
                    pending = dict(d=d, entry=ent, sl=sl, tp1=tp1, tp2=tp2, lot=lot, fvg_lo=g_lo, expire=win[1],
                                   tag="SB", kz=f"SB{win[0]}", risk_usd=risk * OZ_PER_LOT * lot + p.commission * lot)
                    sb_done = True
                    break

        if kz is None or not p.use_model_2022:
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
                s.cand = p.sweep_pa_bars > 0 and pa(i, d)
                s.mss = None
                for j in range(i - 1, max(i - 40, 1), -1):  # swing high ล่าสุดก่อนจุดกวาด
                    if Hd[j] > Hd[j - 1] and Hd[j] > Hd[j + 1] and Hd[j] > Cd[i]:
                        s.mss = Hd[j]
                        break
                continue
            if s.ext is None or s.fired or s.mss is None or (i - s.ext_i) * tf > p.max_mss_min:
                continue
            if p.sweep_pa_bars > 0 and i - s.ext_i <= p.sweep_pa_bars and pa(i, d):
                s.cand = True
            if Cd[i] <= s.mss:
                continue
            if p.require_reclaim and Cd[i] <= s.lvl[0]:
                continue                       # ยังไม่ปิดกลับเหนือโซน: รอแท่งถัดไป
            if p.mss_vol_mult > 0 and i >= 51:
                av = V[i - 50:i].mean()
                if av > 0 and V[i] <= p.mss_vol_mult * av:
                    continue                   # volume แท่ง MSS ต่ำ: รอแท่งถัดไป
            if p.sweep_pa_bars > 0 and not s.cand:
                s.fired = True
                cnt("no_pa")
                continue
            # ---- เกิด MSS ----
            cnt("mss")
            s.fired = True
            if pending is not None or pos is not None:
                cnt("busy")
                continue
            if day_trades >= p.max_trades_day or day_losses >= p.max_losses_day or \
                    (p.max_daily_loss_pct > 0 and day_pnl <= -p.max_daily_loss_pct / 100 * day_eq0):
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
            if p.htf_fib:
                tr_, retr, _, _ = htf_fib(i, d)
                if tr_ != d or retr is None or not (p.htf_min_retr <= retr <= p.htf_max_retr):
                    cnt("htf")
                    continue
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
            if p.ltf_fib:
                rg_ = leg_high - s.ext
                z_hi, z_lo = leg_high - 0.62 * rg_, leg_high - 0.79 * rg_
                if p.fib_need_fvg and (setup is None or setup[1] > z_hi or setup[0] < z_lo):
                    setup = None
                else:
                    setup = (leg_high - p.fib_entry * rg_, s.ext)
            if setup is None:
                cnt("nofvg")
                continue
            ent, fvg_lo = setup
            lv = s.lvl
            he = np.searchsorted(h1t, T5[e].astype("datetime64[h]"))   # แท่ง H1 ที่มีจุดสุดของไส้
            sl = s.ext - p.sl_buffer * A
            if p.sl_mode == "zone" and he >= 15:
                aH1 = (h1h[he - 14:he] - h1l[he - 14:he]).mean()
                sl = min(sl, lv[0] - p.sl_zone_atr * aH1)       # พ้นโซน TF ใหญ่ (หรือหลังไส้ถ้าไส้ลึกกว่า)
                risk = ent - sl
                if risk <= 0 or risk > p.sl_zone_max * aH1:
                    cnt("risk")
                    continue
            else:
                risk = ent - sl
                if risk < p.min_risk * A or risk > p.max_risk * A:
                    cnt("risk")
                    continue
            if p.tp_mode == "fib":
                tp1 = leg_high                                   # ระดับ 0
                tp2 = leg_high + p.fib_tp_ext * (leg_high - s.ext)   # ระดับ -0.27
                if tp2 - ent < p.min_rr * risk:
                    cnt("no_target")
                    continue
            elif p.tp_mode == "range":
                # เป้าจากกรอบราคา: TP1 = swing H1 ก่อนจุดกลับตัว, TP2 = ขอบ dealing range (จุดสูงสุดตั้งแต่โซนเกิดจนถึงจุดกวาด)
                hH = h1h if d == 1 else -h1l
                tp1 = None
                ts = p.tp_swing_strength
                for k in range(he - 1, max(he - 300, ts), -1):
                    if k + ts > he:
                        continue
                    if hH[k] > ent and all(hH[k] > hH[k + q] and hH[k] >= hH[k - q] for q in range(1, ts + 1)):
                        tp1 = hH[k]
                        break
                if tp1 is None or tp1 - ent < p.min_rr * risk:
                    cnt("no_target")
                    continue
                j = e - 1
                lim = max(e - p.range_lookback, 0)
                while j > lim and Ld[j] > lv[0]:
                    j -= 1
                edge = Hd[j:e + 1].max()
                tp2 = edge if edge > tp1 else tp1
            else:
                if lv[2] is not None:              # Wyckoff / Quarter Zone: เป้ากำหนดมากับระดับ
                    tp1, tp2 = lv[2], lv[3]
                    if len(lv) > 5 and lv[5]:         # เป้าตามขาของ TF เล็ก
                        tp1, tp2 = leg_high, leg_high + p.fib_tp_ext * (leg_high - s.ext)
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
            if p.max_spread_to_sl > 0 and p.spread / risk > p.max_spread_to_sl:
                cnt("spread")
                continue
            rp = p.risk_pct_london if (kz == "LON" and p.risk_pct_london > 0) else p.risk_pct
            lot = np.floor(equity * rp / 100 / (risk * OZ_PER_LOT) * 100 + 1e-9) / 100
            if lot < 0.01:
                cnt("lot")
                continue
            cnt("order")
            pending = dict(d=d, entry=ent, sl=sl, tp1=tp1, tp2=tp2, lot=lot, fvg_lo=fvg_lo, expire=kz_end + p.order_grace,
                           tag=lv[1], kz=kz, risk_usd=risk * OZ_PER_LOT * lot + p.commission * lot)
            if p.entry_pa:
                pending.update(wait_pa=True, age=0, ext=s.ext)

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
