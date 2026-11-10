import numpy as np, pandas as pd, warnings; warnings.filterwarnings('ignore')
from run import *
T,*_ = go()
m1t=z['m1t']; m1h=z['m1h']; m1l=z['m1l']
risk=(T.entry-T.sl0).abs()
T['slATR']=risk/atr[T.mi]
# MFE (R) between fill and exit; post-stop behaviour
mfe=[];after_tp=[];after_ext=[];hit_wide=[]
for r,rk in zip(T.itertuples(),risk):
    a=np.searchsorted(m1t,r.tin); b=np.searchsorted(m1t,r.tout)
    d=r.dir
    hi=m1h[a:b+1]; lo=m1l[a:b+1]
    mfe.append(((hi.max()-r.entry) if d>0 else (r.entry-lo.min()-0.3))/rk)
    # next 8h after exit
    c=np.searchsorted(m1t,r.tout+480)
    H=m1h[b:c]; L=m1l[b:c]
    if len(H)==0: after_tp.append(False); after_ext.append(0); hit_wide.append(False); continue
    after_tp.append((H.max()>=r.tp) if d>0 else (L.min()+0.3<=r.tp))
    after_ext.append(((r.sl0-L.min()) if d>0 else (H.max()-r.sl0))/rk)   # how far beyond SL (R)
T['mfe']=mfe; T['tp_after']=after_tp; T['beyond']=after_ext
T['fillbars']=(T.tin-t5[T.pl])//5
T['sweepDepthATR']=((T.lvlpx-T.ext).abs())/atr[T.sw]
T['legATR']=None
los=T[T.rsn==0]
print('trades',len(T),' SL-before-BE',len(los),' TP',int((T.rsn==1).sum()),' BE/trail exit',int((T.rsn==2).sum()))
print('\nLOSERS MFE (R) buckets:'); print(pd.cut(los.mfe,[-9,0.1,0.3,0.5,0.75,1.0]).value_counts().sort_index().to_string())
print('\nlosers where price later hit original TP within 8h:', round(los.tp_after.mean()*100,1),'%')
print('losers where price went >=1R beyond SL within 8h (real breakout):', round((los.beyond>=1).mean()*100,1),'%')
print('\nfill speed (bars after order placed) win rate:')
T['win']=T.R>0.05
print(T.groupby(pd.cut(T.fillbars,[-1,0,1,3,12])).agg(n=('R','size'),win=('win','mean'),avgR=('R','mean')).round(2).to_string())
print(T.groupby(pd.cut(T.slATR,[0,0.75,1.0,1.5,2,3.1])).agg(n=('R','size'),win=('win','mean'),avgR=('R','mean')).round(2).to_string())
print(T.groupby(pd.cut(T.sweepDepthATR,[0,0.1,0.25,0.5,1,9])).agg(n=('R','size'),win=('win','mean'),avgR=('R','mean')).round(2).to_string())
T['mssDelay']=T.mi-T.sw
print(T.groupby(pd.cut(T.mssDelay,[-1,1,3,6,20])).agg(n=('R','size'),win=('win','mean'),avgR=('R','mean')).round(2).to_string())
T.to_pickle('trades_full.pkl')
