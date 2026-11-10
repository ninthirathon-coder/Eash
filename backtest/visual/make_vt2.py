import json, numpy as np, pandas as pd
from run_m1 import go, TFN
z=np.load('data.npz'); t1=z['m1t']; o=z['m1o']; h=z['m1h']; l=z['m1l']; c=z['m1c']
EPOCH=pd.Timestamp('1970-01-01')
def thai(mins):
    srv=pd.to_datetime(np.asarray(mins,dtype=np.int64)*60,unit='s'); ny=srv-pd.Timedelta(hours=7)
    utc=pd.DatetimeIndex(ny).tz_localize('America/New_York',ambiguous='NaT',nonexistent='shift_forward').tz_convert('UTC').tz_localize(None)
    return utc+pd.Timedelta(hours=7), pd.DatetimeIndex(ny)
def secs(d): return ((d-EPOCH)//pd.Timedelta(seconds=1)).astype(np.int64)
V=dict(slMode=1,slK=1.5,filtM1=1,tpMode=2,minRR=0.8,tpS=2,dowMask=30,paWait=10,tp2=1,maxSLzone=2.5)
T=go(**V); E=T.attrs['ev']
D=json.load(open('vt_data.json'))           # trades already built by make_vt.py (v1.31)
for t in D['trades']: t['key']='T%d'%t['id']
REASON={10:'ครบทุกขั้น แต่ PA เกิดนอก Kill Zone',13:'ครบทุกขั้น แต่เป็นวันจันทร์',14:'SL ตามโครงสร้าง M1 กว้างเกิน 3 ATR(M5)',
        15:'spread เกิน 20% ของ SL',16:'TP (swing ก่อนกลับตัว) ใกล้เกิน RR < 0.8',19:'SL ไกลเกินเพดาน 2.5 ATR'}
miss=[]
k=0
for ev in E:
    code=int(ev[2])
    if code not in REASON: continue
    k+=1
    si=int(np.searchsorted(t1,int(ev[0]))); ei=int(np.searchsorted(t1,int(ev[1])))
    a=max(si-40,0); b=min(ei+60,len(t1)-1)
    idx=np.arange(a,b+1)
    th,_=thai(t1[idx]); ts=secs(th); keep=np.r_[True,ts[1:]>ts[:-1]]; idx=idx[keep]; ts=ts[keep]
    d=int(ev[3])
    seg=slice(si,ei+1); xi=si+int(np.argmin(l[seg]) if d>0 else np.argmax(h[seg]))
    def bar_of(i): p=int(np.searchsorted(idx,i,'right')-1); return int(ts[max(p,0)])
    thS,nyS=thai([t1[si]]); thE,nyE=thai([t1[ei]])
    miss.append(dict(key='S%d'%k, id=k, dir='Buy' if d>0 else 'Sell', zone=TFN.get(int(ev[5]),'?'), lvl=round(float(ev[4]),2),
        ext=round(float(l[xi] if d>0 else h[xi]),2), code=code, reason=REASON[code], tSweep=thS[0].strftime('%Y-%m-%d %H:%M'),
        tPA=thE[0].strftime('%Y-%m-%d %H:%M'), nyPA=nyE[0].strftime('%H:%M'), tf=1,
        mk=dict(sweep=bar_of(xi), pa=bar_of(ei)),
        bars=[[int(ts[i]),round(float(o[idx[i]]),2),round(float(h[idx[i]]),2),round(float(l[idx[i]]),2),round(float(c[idx[i]]),2)] for i in range(len(ts))]))
D['missed']=miss
json.dump(D,open('vt2_data.json','w'),ensure_ascii=False,separators=(',',':'))
import collections; print(len(D['trades']),'trades', len(miss),'missed', collections.Counter(m['code'] for m in miss), round(len(json.dumps(D))/1e6,2),'MB')
