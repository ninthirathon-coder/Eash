import json, numpy as np, pandas as pd
import os; os.chdir(os.environ.get('BT_DIR', os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')))
z=np.load('data.npz'); t1=z['m1t']; o=z['m1o']; h=z['m1h']; l=z['m1l']; c=z['m1c']
T=pd.read_pickle('v120_full.pkl')
TFN={1:'H1',2:'H4',3:'PDH/PDL',5:'PWH/PWL'}
EPOCH=pd.Timestamp('1970-01-01')
def thai(mins):
    srv=pd.to_datetime(np.asarray(mins,dtype=np.int64)*60,unit='s'); ny=srv-pd.Timedelta(hours=7)
    utc=pd.DatetimeIndex(ny).tz_localize('America/New_York',ambiguous='NaT',nonexistent='shift_forward').tz_convert('UTC').tz_localize(None)
    return utc+pd.Timedelta(hours=7), pd.DatetimeIndex(ny)
def secs(dti): return ((dti-EPOCH)//pd.Timedelta(seconds=1)).astype(np.int64)
out=[]
for k,r in enumerate(T.itertuples()):
    d=int(r.dir); fi=int(np.searchsorted(t1,r.tin)); xi=int(np.searchsorted(t1,r.tout)); sw=int(r.sw); mi=int(r.mi)
    seg=slice(sw,mi+1); ei=sw+int(np.argmin(l[seg]) if d>0 else np.argmax(h[seg])); ext=float(l[ei] if d>0 else h[ei])
    t1i=None
    if abs(r.tp1-r.tp)>1e-9:
        for j in range(fi+1,xi+1):
            if (d>0 and h[j]>=r.tp1) or (d<0 and l[j]+0.30<=r.tp1): t1i=j; break
    a=max(sw-45,0); b=min(xi+30,len(t1)-1); span=b-a
    P=1 if span<=360 else (5 if span<=1800 else 15)
    idx=np.arange(a,b+1); key=t1[idx]//P
    st=np.flatnonzero(np.r_[True,key[1:]!=key[:-1]]); en=np.r_[st[1:],len(idx)]-1
    bo=o[idx][st]; bh=np.maximum.reduceat(h[idx],st); bl=np.minimum.reduceat(l[idx],st); bc=c[idx][en]
    th,_=thai(key[st]*P); ts=secs(th)
    keep=np.r_[True, ts[1:]>ts[:-1]]          # drop the rare duplicate around DST switches
    st_idx=idx[st][keep]; ts=ts[keep]; bo,bh,bl,bc=bo[keep],bh[keep],bl[keep],bc[keep]
    def bar_of(i):
        p=int(np.searchsorted(st_idx,i,'right')-1); return int(ts[max(p,0)])
    R=float(r.R); rk=float(r.risk); rtp1=abs(r.tp1-r.entry)/rk; rtp=abs(r.tp-r.entry)/rk
    cands={'SL':-1.0}
    if abs(r.tp-r.tp1)<1e-9: cands['TP']=rtp1
    else: cands['TP2']=0.5*rtp1+0.5*rtp; cands['BE']=0.5*rtp1+0.5*(0.10/rk)
    ex=min(cands,key=lambda q:abs(cands[q]-R))
    xpx={'SL':r.sl,'TP':r.tp1,'TP2':r.tp,'BE':r.entry+d*0.10}[ex]
    thS,_=thai([t1[sw]]); thF,nyF=thai([t1[fi]]); thX,_=thai([t1[xi]]); thM,_=thai([t1[mi]])
    mk=dict(sweep=bar_of(ei), mssA=bar_of(max(sw-30,a)), mss=bar_of(mi), fvg=bar_of(max(mi-2,a)), entry=bar_of(fi-1),
            tp1=bar_of(t1i) if t1i is not None else (bar_of(xi) if ex=='BE' else None), exit=bar_of(xi))
    out.append(dict(id=k+1, dir='Buy' if d>0 else 'Sell', zone=TFN.get(int(r.tf),'?'), lvl=round(float(r.lvl),2),
        ext=round(ext,2), mss=round(float(r.msspx),2), zt=round(float(r.zt),2), zb=round(float(r.zb),2),
        entry=round(float(r.entry),2), sl=round(float(r.sl),2), tp1=round(float(r.tp1),2), tp2=round(float(r.tp),2),
        R=round(R,2), pnl=round(float(r.pnl),2), risk=round(rk,2), rr1=round(rtp1,2), rr2=round(rtp,2), exit=ex, xpx=round(float(xpx),2),
        kz='London' if int(r.kz)==1 else 'New York', tf=P,
        tSweep=thS[0].strftime('%Y-%m-%d %H:%M'), tMss=thM[0].strftime('%H:%M'), tEntry=thF[0].strftime('%Y-%m-%d %H:%M'),
        tExit=thX[0].strftime('%Y-%m-%d %H:%M'), nyEntry=nyF[0].strftime('%H:%M'), mk=mk,
        bars=[[int(ts[i]),round(float(bo[i]),2),round(float(bh[i]),2),round(float(bl[i]),2),round(float(bc[i]),2)] for i in range(len(ts))]))
eq=10000+T.pnl.cumsum()
summ=dict(n=len(T),win=round(float((T.R>0.05).mean()*100),1),avgR=round(float(T.R.mean()),3),ret=round(float((eq.iloc[-1]/10000-1)*100),1),
          dd=round(float(((eq/eq.cummax().clip(lower=10000))-1).min()*100),1), first=T.date.min().strftime('%Y'), last=T.date.max().strftime('%Y'))
bad=[t['id'] for t in out if not all(x[0]<y[0] for x,y in zip(t['bars'],t['bars'][1:]))]
import datetime
t=out[60]; print('check', datetime.datetime.fromtimestamp(t['mk']['sweep'],datetime.UTC).strftime('%Y-%m-%d %H:%M'), 'vs', t['tSweep'], '| non-increasing:', bad)
json.dump(dict(summary=summ,trades=out),open('vt_data.json','w'),ensure_ascii=False,separators=(',',':'))
