import run_m1 as R, numpy as np, pandas as pd
from run_m1 import go, stats, t1, h, l, n
B=dict(slMode=1,slK=1.5,filtM1=1,tpMode=2,minRR=0.8,tpS=2,dowMask=30,paWait=10,tp2=1,maxSLzone=2.5)
nym = (t1 - 420) % 1440            # NY minute of day (server = NY+7)
nyday = (t1 - 420) // 1440
def asia_arrays(s, e):
    """range from NY s:00 (previous evening) to e:00 ; level published at first bar >= e:00"""
    st=np.zeros(n,np.int64); hi=np.zeros(n); lo=np.zeros(n); fs=np.zeros(n,np.int64); fe=np.zeros(n,np.int64)
    # session id: shift so that the session starting at s (evening) belongs to next day
    sh = (t1 - 420 - s*60) // 1440
    m = (t1 - 420 - s*60) % 1440
    L = ((e - s) % 24) * 60
    ins = m < L
    pub = np.flatnonzero(np.r_[False, (m[1:] >= L) & (m[:-1] < L) & (sh[1:] == sh[:-1])])
    a_st=np.zeros(n,np.int64)
    for p in pub:
        sid=sh[p]; j=p-1; k=j
        while k>0 and sh[k-1]==sid and ins[k-1]: k-=1
        if p-k < 60: continue
        st[p]=1; hi[p]=h[k:p].max(); lo[p]=l[k:p].min(); fs[p]=k; fe[p]=p-1
    # wStart[t]==t is the trigger -> build index array
    ws=np.where(st==1, np.arange(n), -1)
    return ws, hi, lo, fs, fe
orig=(R.wStart,R.pwh,R.pwl,R.prevWS,R.prevWE)
rows=[]
def rep(k,T):
    y=T.date.dt.year; s=stats(T); r=T[T.date>='2024-01-01']
    rows.append([k,s['n'],round(s['n']/17.8,1),len(r),s['avgR'],round(T.R[y%2==1].mean(),3),round(T.R[y%2==0].mean(),3),s['ret'],s['maxDD'],s['tstat']])
    return T
base=rep('base v1.31',go(**B))
res={}
for s_,e_ in [(20,0),(19,0),(18,2),(20,2)]:
    R.wStart,R.pwh,R.pwl,R.prevWS,R.prevWE = asia_arrays(s_,e_)
    T=rep(f'+Asia {s_:02d}-{e_:02d}',go(**dict(B,usePW=1))); res[(s_,e_)]=T
    T=rep(f'  Asia only {s_:02d}-{e_:02d}',go(**dict(B,usePW=1,useH1=0,useH4=0,usePD=0)))
R.wStart,R.pwh,R.pwl,R.prevWS,R.prevWE=orig
print(pd.DataFrame(rows,columns=['variant','n','n/yr','n24-26','avgR','oddY','evenY','ret%','DD%','t']).to_string(index=False))
pd.to_pickle(res,'asia_res.pkl'); pd.to_pickle(base,'base131.pkl')
