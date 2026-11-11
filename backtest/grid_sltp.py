import sys, pandas as pd
from run_m1 import go, stats
B=dict(tpS=2,dowMask=30,paWait=10,tp2=1,maxSLzone=2.5)
SL={'โซน−1.5ATR(ใช้อยู่)':dict(slMode=1,slK=1.5,filtM1=1),
    'ไส้−0.25ATR M1':dict(slMode=0,slBuf=0.25,filtM1=0),'ไส้−0.5ATR M1':dict(slMode=0,slBuf=0.5,filtM1=0),
    'ไส้−1ATR M1':dict(slMode=0,slBuf=1.0,filtM1=0),'ไส้−2ATR M1':dict(slMode=0,slBuf=2.0,filtM1=0)}
TP={'swingก่อนกลับตัว RR≥0.8':dict(tpMode=2,minRR=0.8),
    'swingH1แรกที่RR≥1':dict(tpMode=3,minRR=1.0),'swingH1แรกที่RR≥1.5':dict(tpMode=3,minRR=1.5),'swingH1แรกที่RR≥2':dict(tpMode=3,minRR=2.0),
    'LQตรงข้ามRR≥1':dict(tpMode=4,minRR=1.0),'LQตรงข้ามRR≥1.5':dict(tpMode=4,minRR=1.5),'LQตรงข้ามRR≥2':dict(tpMode=4,minRR=2.0),
    'RR 1.5':dict(tpMode=0,RR=1.5,minRR=0.5),'RR 2':dict(tpMode=0,RR=2.0,minRR=0.5),'RR 3':dict(tpMode=0,RR=3.0,minRR=0.5)}
keys=list(SL)[int(sys.argv[1]):int(sys.argv[2])]
rows=[]
for sn in keys:
    for tn,tk in TP.items():
        T=go(**{**B,**SL[sn],**tk}); y=T.date.dt.year; s=stats(T)
        rows.append(dict(SL=sn,TP=tn,n=s['n'],win=s.get('win'),avgR=s.get('avgR'),ret=s.get('ret'),dd=s.get('maxDD'),t=s.get('tstat'),
            คี่=stats(T[y%2==1]).get('avgR'),คู่=stats(T[y%2==0]).get('avgR'),SLกลาง=round(T.risk.median(),2) if len(T) else None))
pd.DataFrame(rows).to_pickle(f'grid_{sys.argv[1]}.pkl')
pd.set_option('display.width',250); print(pd.DataFrame(rows).to_string(index=False))
