import os
import numpy as np, pandas as pd, warnings, matplotlib, os, sys
warnings.filterwarnings('ignore')
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.patches import Rectangle

F = os.environ.get('THAI_FONT_DIR', os.path.dirname(os.path.abspath(__file__)) + '/fonts/')
for f in ('Sarabun-Regular.ttf', 'Sarabun-Bold.ttf'):
    fm.fontManager.addfont(F + f)
plt.rcParams.update({'font.family': 'Sarabun', 'font.size': 11, 'axes.titleweight': 'bold'})
OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)

from run import z, t5, o, h, l, c, atr
T = pd.read_pickle('trades_full.pkl')
T['win'] = T.R > 0.05
los = T[T.rsn == 0]
RED, GRN, BLU, GLD, GRY = '#c0392b', '#1e8449', '#2463b0', '#d4a017', '#7f8c8d'

# ------------------------------------------------------------------ 1) dashboard
fig, ax = plt.subplots(2, 3, figsize=(19, 9), dpi=150)
fig.suptitle('ICT Candle EA แพ้ตรงไหน? (XAUUSD 2009-2026, 544 ไม้)', fontsize=17, fontweight='bold')

a = ax[0, 0]
n_brk = int((los.beyond >= 1).sum()); n_hunt = int(((los.beyond <= 0.5) & los.tp_after).sum())
n_oth = len(los) - n_brk - n_hunt
vals = [n_brk, n_hunt, n_oth]
labs = [f'ราคาเบรคทะลุจริง\n(วิ่งเลย SL ≥ 1R)\n{n_brk} ไม้', f'โดนกวาด SL นิดเดียว\nแล้วกลับไป TP\n{n_hunt} ไม้', f'อื่นๆ\n{n_oth} ไม้']
a.pie(vals, labels=labs, colors=[RED, GLD, GRY], startangle=90, wedgeprops=dict(width=0.45, edgecolor='white'),
      textprops=dict(fontsize=10.5))
a.set_title(f'1. ไม้ที่โดน SL ก่อนกันทุน {len(los)} ไม้: เกิดจากอะไร')


def bars(a, g, labels, title, note):
    r = T.groupby(g).agg(n=('R', 'size'), avgR=('R', 'mean'))
    cols = [GRN if v > 0 else RED for v in r.avgR]
    b = a.bar(range(len(r)), r.avgR, color=cols, width=0.6)
    for i, (v, n) in enumerate(zip(r.avgR, r.n)):
        a.text(i, v + (0.01 if v >= 0 else -0.01), f'{v:+.2f}R\n({n} ไม้)', ha='center', va='bottom' if v >= 0 else 'top', fontsize=10)
    a.axhline(0, color='k', lw=0.8)
    a.set_xticks(range(len(r)), labels)
    a.set_ylabel('กำไรเฉลี่ยต่อไม้ (R)')
    a.set_title(title)
    lo = min(r.avgR.min() * 1.6, -0.1); hi = max(r.avgR.max() * 1.6, 0.15)
    a.set_ylim(lo, hi)
    a.text(0.02, 0.03, note, transform=a.transAxes, fontsize=9.5, color='#444')


bars(ax[0, 1], T.H4 > 0, ['สวนเทรนด์ H4', 'ตามเทรนด์ H4'], '2. Bias H1 ไม่พอ: 35% ของไม้สวนเทรนด์ H4',
     'EA ดูแค่ H1 จึงเข้าสวนทางใหญ่บ่อย')
T['mssg'] = pd.cut(T.mi - T.sw, [-1, 1, 3, 99], labels=['MSS ภายใน 1 แท่ง', '2-3 แท่ง', 'ช้ากว่า 3 แท่ง'])
bars(ax[0, 2], 'mssg', list(T.mssg.cat.categories), '3. MSS ช้า = แรงกลับตัวอ่อน',
     'sweep จริงควรถูกปฏิเสธทันที แต่ EA รอได้ถึง 20 แท่ง')
T['fg'] = pd.cut((T.tin - t5[T.pl]) // 5, [-1, 0, 3, 99], labels=['ชน FVG ทันที\n(แท่งแรก)', '1-3 แท่ง', 'มากกว่า 3 แท่ง'])
bars(ax[1, 0], 'fg', list(T.fg.cat.categories), '4. ราคาพุ่งทะลุ FVG ทันที = โมเมนตัมสวน',
     'Limit ถูกแมตช์เพราะราคาวิ่งสวนแรง ไม่ใช่ย่อมาเทส')
T['spg'] = pd.cut(0.30 / (T.entry - T.sl0).abs(), [0, 0.1, 0.2, 9], labels=['spread < 10%\nของ SL', '10-20%', 'spread > 20%\nของ SL'])
bars(ax[1, 1], 'spg', list(T.spg.cat.categories), '5. SL แคบเกิน: spread กินความเสี่ยงไปมาก',
     'SL กลาง ~1.9 ดอลลาร์ แต่ spread 0.30 ดอลลาร์ = เสียเปรียบ 16% ทุกไม้')
a = ax[1, 2]; a.axis('off')
a.text(0.02, 0.98, 'สรุปจุดที่ต้องแก้ใน EA\n'
       '1. Liquidity เล็กเกินไป (swing M5 = 97% ของไม้)\n    → ใช้ swing H1/H4, PDH/PDL, Equal highs/lows\n'
       '2. Bias ดูแค่ H1 → เพิ่มเงื่อนไขเทรนด์ H4/D1\n'
       '3. รอ MSS ได้ถึง 20 แท่ง → จำกัด 3 แท่ง\n'
       '4. Limit ถูกแมตช์ตอนราคาพุ่งสวน\n    → รอแท่งเทียนปฏิเสธใน FVG ก่อนเข้า\n'
       '5. SL เล็กเทียบ spread → กำหนด SL ขั้นต่ำ\n    (เช่น spread ≤ 10% ของ SL)\n\n'
       'ไม่ใช่ปัญหาหลัก: ระยะ SL (ขยายแล้วยังติดลบ)\n'
       'มีแค่ 28 จาก 319 ไม้ที่ "โดนกวาด SL แล้วกลับ"',
       transform=a.transAxes, va='top', fontsize=11, linespacing=1.3,
       bbox=dict(boxstyle='round,pad=0.8', fc='#fffbe6', ec=GLD))
plt.tight_layout(rect=(0, 0, 1, 0.95))
plt.savefig(OUT + '/0_summary.png'); plt.close()


# ------------------------------------------------------------------ 2) example trades
def ny(tmin):
    return pd.to_datetime((tmin - 420) * 60, unit='s')


def chart(r, fname, title, notes, pre=25, post=35):
    i0 = max(r.sw - pre, 0)
    ix = int(np.searchsorted(t5, r.tout, 'right') - 1)
    i1 = min(ix + post, len(t5) - 1)
    idx = np.arange(i0, i1 + 1)
    fig = plt.figure(figsize=(15, 7), dpi=150)
    gs = fig.add_gridspec(1, 2, width_ratios=[3.1, 1], wspace=0.02)
    a = fig.add_subplot(gs[0]); tx = fig.add_subplot(gs[1]); tx.axis('off')
    for k, j in enumerate(idx):
        up = c[j] >= o[j]; col = '#26a69a' if up else '#ef5350'
        a.vlines(k, l[j], h[j], color=col, lw=1)
        a.add_patch(Rectangle((k - 0.35, min(o[j], c[j])), 0.7, max(abs(c[j] - o[j]), 1e-6), color=col))
    X = lambda j: j - i0
    d = r.dir
    # liquidity level + sweep
    a.hlines(r.lvlpx, X(r.sw) - 18, X(r.sw) + 1, color=GLD, ls='--', lw=1.6)
    a.text(X(r.sw) - 18, r.lvlpx, ' Liquidity (swing M5)', color=GLD, va='bottom' if d < 0 else 'top', fontsize=10, fontweight='bold')
    yS = r.ext
    a.annotate('1. Sweep', (X(r.sw), yS), xytext=(-50, -d * 38), textcoords='offset points', color=BLU, fontweight='bold',
               arrowprops=dict(arrowstyle='->', color=BLU, lw=1.5))
    # MSS
    a.hlines(r.msspx, X(r.sw) - 3, X(r.mi), color=BLU, lw=1.4)
    a.annotate('2. MSS', (X(r.mi), r.msspx), xytext=(25, d * 55), textcoords='offset points', color=BLU, fontweight='bold',
               arrowprops=dict(arrowstyle='->', color=BLU, lw=1.5))
    # FVG
    if r.top > 0:
        a.add_patch(Rectangle((X(r.pl) - 3, r.bot), X(ix) - X(r.pl) + 3, r.top - r.bot, color=BLU, alpha=0.15))
        a.text(X(r.pl) - 3, r.top if d < 0 else r.bot, ' FVG', color=BLU, va='bottom' if d < 0 else 'top', fontsize=10)
    # entry / sl / tp
    xe = X(int(np.searchsorted(t5, r.tin, 'right') - 1))
    for y, col, lab in [(r.entry, BLU, 'Entry'), (r.sl0, RED, 'SL'), (r.tp, GRN, 'TP')]:
        a.hlines(y, X(r.pl), X(ix) + 2, color=col, lw=1.6)
        a.text(len(idx) + 1, y, f'{lab} {y:.2f}', color=col, va='center', fontsize=10, fontweight='bold')
    a.plot(xe, r.entry, marker='^' if d > 0 else 'v', color=BLU, ms=12, zorder=5)
    a.text(xe, r.entry - d * 1.2 * atr[r.mi], '3. เข้า', color=BLU, ha='center', fontweight='bold')
    a.plot(X(ix), r.xpx, marker='X', color=RED, ms=13, zorder=5)
    a.text(X(ix), r.xpx - d * 1.4 * atr[r.mi], '4. โดน SL', color=RED, ha='center', fontweight='bold')
    # x labels in NY time
    step = max(len(idx) // 10, 1)
    a.set_xticks(range(0, len(idx), step), [ny(t5[j]).strftime('%H:%M') for j in idx[::step]])
    a.set_xlim(-1, len(idx) + 10)
    a.set_xlabel(f'เวลานิวยอร์ก  ({ny(t5[r.sw]).strftime("%d %b %Y")})   XAUUSD M5')
    a.set_title(title, fontsize=15)
    tx.text(0.04, 0.97, notes, transform=tx.transAxes, va='top', fontsize=12.5, linespacing=1.6, wrap=True,
            bbox=dict(boxstyle='round,pad=0.8', fc='#fffbe6', ec=GLD))
    a.grid(alpha=0.15)
    fig.subplots_adjust(left=0.05, right=0.99, top=0.92, bottom=0.09); plt.savefig(OUT + '/' + fname); plt.close()


def pick(df, k=0):
    return df.sort_values('date', ascending=False).iloc[k]


yrs = T.date.dt.year.isin([2024, 2025, 2026])
L = T[(T.rsn == 0) & yrs]
# A: sweep that was actually a breakout, against H4
A = pick(L[(L.beyond >= 3) & (L.H4 < 0) & ((L.mi - L.sw) <= 6)])
chart(A, '1_fake_sweep_breakout.png', 'ผิดพลาดข้อ 1+2: "Sweep" ที่จริงคือการเบรคทะลุ และสวนเทรนด์ H4',
      'สิ่งที่ EA เห็น\n'
      'ราคาแทงไส้ใต้ swing low\nแล้วปิดกลับ → นึกว่าเป็น\nstop hunt จึงเข้า Buy\n\n'
      'ความจริง\n'
      'H4 เป็นขาลง ราคาแค่พักตัว\nสั้นๆ แล้วทะลุลงต่อ\n'
      f'ราคาวิ่งเลย SL ไปอีก {A.beyond:.1f}R\nSL กว้างแค่ไหนก็ไม่รอด\n\n'
      'วิธีแก้\n'
      '• เช็กเทรนด์ H4/D1 ด้วย\n• ใช้ liquidity ที่ใหญ่กว่า\n  swing M5 (เช่น swing H1)')

# B: instant fill through FVG
B = pick(L[((L.tin - t5[L.pl]) // 5 == 0) & (L.mfe < 0.15) & (L.top > 0)])
chart(B, '2_instant_fill.png', 'ผิดพลาดข้อ 4: ราคาพุ่งทะลุ FVG ทันทีที่ตั้ง Limit',
      'สิ่งที่เกิดขึ้น\n'
      'ตั้ง Limit ที่กลาง FVG\nแท่งถัดมาราคาวิ่งสวนผ่าน\nFVG ทั้งก้อนทันที\n\n'
      'FVG ไม่ได้เป็นแนวรับ/ต้าน\nแต่ Limit ยังถูกแมตช์\nแล้วถือจนโดน SL\n'
      f'กำไรสูงสุดระหว่างถือ {max(B.mfe, 0):.2f}R\n\n'
      'วิธีแก้\n'
      '• รอแท่งเทียนปฏิเสธใน FVG\n  ก่อนเข้า แทน Limit ล้วน\n'
      '• ยกเลิก Limit ถ้าแท่งเดียว\n  วิ่งทะลุ FVG แรงๆ')

# C: slow MSS
C = pick(L[((L.mi - L.sw) >= 8) & (L.beyond >= 1)])
chart(C, '3_slow_mss.png', 'ผิดพลาดข้อ 3: MSS เกิดช้า หลัง sweep หลายแท่ง',
      'สิ่งที่เกิดขึ้น\n'
      f'Sweep แล้วราคาเดินออกข้าง\n{int(C.mi - C.sw)} แท่ง กว่าจะเกิด MSS\n\n'
      'sweep ที่ดี ราคาต้องถูก\nปฏิเสธแรงทันที\n(ภายใน 1-3 แท่ง)\n\n'
      'MSS ที่มาช้า = ราคาแค่\nแกว่งในกรอบ ไม่ใช่การกลับตัว\n\n'
      'วิธีแก้\n'
      '• ให้ setup หมดอายุถ้าไม่เกิด\n  MSS ภายใน 3 แท่ง\n  (ตอนนี้ EA รอได้ 20 แท่ง)')

# D: true stop hunt (for contrast)
Dd = pick(L[(L.beyond <= 0.5) & L.tp_after])
chart(Dd, '4_stop_hunt.png', 'เคสส่วนน้อย (28 จาก 319 ไม้): โดนกวาด SL นิดเดียวแล้วกลับไปทาง TP',
      'ไม้แบบนี้ "คิดถูก แต่ SL แคบไป"\n\n'
      'SL วางใต้ไส้ sweep พอดี\nซึ่งเป็นจุดที่ liquidity\nก้อนใหม่รวมตัว\n\n'
      'แต่มีแค่ 28 จาก 319 ไม้\n(9% ของไม้ที่แพ้)\n\n'
      'ทดสอบขยาย SL แล้ว\nผลยังติดลบ\n→ ไม่ใช่ปัญหาหลัก',
      post=60)
print('examples', A.date, B.date, C.date, Dd.date)
