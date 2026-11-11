import pandas as pd, numpy as np
from run_m1 import go, stats
V110 = dict(slMode=1, slK=1.5, filtM1=1, tpMode=2, minRR=0.8, tpS=2, dowMask=30, paWait=10)
C = [('v1.10 (ฐาน)', {}),
 ('1. EQH/EQL เท่านั้น (tol 0.1)', dict(eqOnly=1, eqTol=0.1)), ('1. EQH/EQL เท่านั้น (tol 0.2)', dict(eqOnly=1, eqTol=0.2)),
 ('2. เพิ่ม PWH/PWL', dict(usePW=1)),
 ('3. OTE ย่อ ≥ 50%', dict(ote=0.5)), ('3. OTE ย่อ ≥ 62%', dict(ote=0.62)),
 ('4. Power of 3 (ราคาเปิดเที่ยงคืน)', dict(po3=1)),
 ('5. Daily bias เข้ม', dict(dbias=1)), ('5. Daily bias หลวม', dict(dbias=2)),
 ('6. TP1 swing 50% + TP2 ขอบ range', dict(tp2=1)), ('6. TP1 30% + TP2', dict(tp2=1, tp2Pct=30)), ('6. TP1 70% + TP2', dict(tp2=1, tp2Pct=70)),
 ('7. SMT ทอง-เงิน', dict(smt=1)),
 ('8. RR ≥ 2', dict(minRR=2.0)), ('8. RR ≥ 1.5', dict(minRR=1.5))]
rows = []
for name, kw in C:
    T = go(**{**V110, **kw}); y = T.date.dt.year
    a = stats(T[y % 2 == 1]); b = stats(T[y % 2 == 0]); s = stats(T); c1 = stats(T[y <= 2017]); c2 = stats(T[y > 2017])
    rows.append(dict(ชุด=name, n=s['n'], win=s.get('win'), avgR=s['avgR'], PF=s.get('PF'), ret=s.get('ret'), maxDD=s.get('maxDD'), t=s.get('tstat'),
                     ปีคี่=a['avgR'], ปีคู่=b['avgR'], y0917=c1['avgR'], y1826=c2['avgR']))
D = pd.DataFrame(rows).set_index('ชุด'); b0 = D.iloc[0]
D['ผ่าน'] = np.where((D.ปีคี่ > b0.ปีคี่ + 0.02) & (D.ปีคู่ > b0.ปีคู่ + 0.02) & (D.n >= 0.5 * b0.n), '✓', '')
pd.set_option('display.width', 250); print(D.to_string()); D.to_pickle('screen_pdf.pkl')
