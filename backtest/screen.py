import pandas as pd, numpy as np, sys
from run_m1 import go, stats
EA = dict(slMode=1, slK=1.5, filtM1=1, tpMode=2, minRR=0.8, tpS=2)
C = [('base', {}),
 ('bias H1', dict(bias=1)), ('bias H4', dict(bias=2)), ('bias H1+H4', dict(bias=3)),
 ('ไม่ใช้ PDH/PDL', dict(usePD=0)), ('ไม่ใช้ swing H1', dict(useH1=0)),
 ('London อย่างเดียว', dict(nyk=0)), ('NY อย่างเดียว', dict(lon=0)), ('NY 8-11', dict(nyS=8, nyE=11)), ('NY 7-11', dict(nyE=11)),
 ('London 1-5', dict(lonS=1)), ('Silver Bullet (3-4, 10-11)', dict(lonS=3, lonE=4, nyS=10, nyE=11)),
 ('ไม่เทรดจันทร์', dict(dowMask=30)), ('ไม่เทรดศุกร์', dict(dowMask=15)), ('อังคาร-พฤหัส', dict(dowMask=14)),
 ('P/D วันก่อน', dict(pdF=1)), ('P/D dealing range', dict(pdF=2)),
 ('displacement 0.8', dict(disp=0.8)), ('displacement 1.5', dict(disp=1.5)),
 ('FVG ≥ 0.2', dict(minFVG=0.2)), ('FVG ≥ 0.5', dict(minFVG=0.5)),
 ('ไม่กันทุน', dict(BE=0)), ('กันทุนที่ 0.75R', dict(BE=0.75)), ('กันทุนที่ 1.5R', dict(BE=1.5)),
 ('กันทุนไม่ปิดบางส่วน', dict(partial=0)), ('ปิดบางส่วน 30%', dict(partial=30)),
 ('trail swing M1 แรง 3', dict(trail=3)), ('trail swing M1 แรง 5', dict(trail=5)),
 ('PA ที่ไส้ ไม่บังคับ', dict(sweepPA=0)), ('PA ที่ไส้ ≤5 แท่ง', dict(sweepPA=5)),
 ('ไส้ลึก ≤2 ATR', dict(maxDepth=2)), ('ไส้ลึก ≤4 ATR', dict(maxDepth=4)),
 ('รอ MSS 20', dict(setupExp=20)), ('รอ MSS 45', dict(setupExp=45)),
 ('รอ PA ใน FVG 10', dict(paWait=10)), ('รอ PA ใน FVG 25', dict(paWait=25)),
 ('SL 1.25 ATR', dict(slK=1.25)), ('SL 1.75 ATR', dict(slK=1.75)),
 ('สูงสุด 1 ไม้/วัน', dict(maxTrades=1)), ('สูงสุด 3 ไม้/วัน', dict(maxTrades=3)), ('TP swing แรง 3', dict(tpS=3))]
rows = []
for name, kw in C:
    T = go(**{**EA, **kw}); y = T.date.dt.year
    a = stats(T[y % 2 == 1]); b = stats(T[y % 2 == 0]); s = stats(T)
    rows.append(dict(ชุด=name, n=s['n'], avgR=s['avgR'], PF=s['PF'], ret=s['ret'], maxDD=s['maxDD'], t=s['tstat'],
                     ปีคี่=a['avgR'], n_คี่=a['n'], ปีคู่=b['avgR'], n_คู่=b['n']))
D = pd.DataFrame(rows).set_index('ชุด')
b0 = D.loc['base']
D['ผ่าน'] = np.where((D.ปีคี่ > b0.ปีคี่ + 0.02) & (D.ปีคู่ > b0.ปีคู่ + 0.02) & (D.n >= 0.5 * b0.n), '✓', '')
pd.set_option('display.width', 250)
print(D.to_string())
D.to_pickle('screen.pkl')
