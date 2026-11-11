import sys, itertools, pandas as pd, numpy as np
from run_m1 import go, stats
extra = eval(sys.argv[1]) if len(sys.argv) > 1 else {}
split = int(sys.argv[2]) if len(sys.argv) > 2 else 2017
grid = []
for sl in [('M1', {}), ('z1.0', dict(slMode=1, slK=1.0, filtM1=1)), ('z1.25', dict(slMode=1, slK=1.25, filtM1=1)),
           ('z1.5', dict(slMode=1, slK=1.5, filtM1=1)), ('z2.0', dict(slMode=1, slK=2.0, filtM1=1))]:
    for tp in [('2R', {}), ('sw0.8', dict(tpMode=2, minRR=0.8)), ('sw1.0', dict(tpMode=2, minRR=1.0))]:
        grid.append((sl[0] + '|' + tp[0], dict(**sl[1], **tp[1])))
rows = []
for name, kw in grid:
    T = go(**kw, **extra); y = T.date.dt.year
    a = stats(T[y <= split]); b = stats(T[y > split]); s = stats(T)
    rows.append(dict(cfg=name, IS_n=a['n'], IS_avgR=a['avgR'], OOS_n=b['n'], OOS_avgR=b['avgR'], ALL_n=s['n'], ALL_avgR=s['avgR'], ALL_t=s.get('tstat')))
D = pd.DataFrame(rows).set_index('cfg')
print(D.to_string())
ok = D[D.IS_n >= 20]
best = ok.IS_avgR.idxmax()
print(f'\nbest in-sample: {best}  IS {ok.loc[best,"IS_avgR"]:+.3f} ({ok.loc[best,"IS_n"]})  ->  OOS {ok.loc[best,"OOS_avgR"]:+.3f} ({ok.loc[best,"OOS_n"]})')
print(f'OOS across all {len(D)} configs: median {D.OOS_avgR.median():+.3f}, positive {int((D.OOS_avgR>0).sum())}/{len(D)}')
print(f'rank corr IS vs OOS: {D.IS_avgR.rank().corr(D.OOS_avgR.rank()):+.2f}')
