from run_m1 import *
B=dict(slMode=1,slK=1.5,filtM1=1,tpMode=2,minRR=0.8,tpS=2,dowMask=30,paWait=10,tp2=1,maxSLzone=2.5)
V={'base v1.31':{},
 'MSS window 60m':dict(setupExp=60),
 'MSS swing 1':dict(mssS=1),
 'displacement 0.7':dict(disp=0.7),
 'PA in FVG wait 20':dict(paWait=20),
 'FVG wait 10':dict(fvgWait=10),
 'depth 4 ATR':dict(maxDepth=4.0),
 'maxTrades 3':dict(maxTrades=3),
 'KZ London 01-06, NY 07-12':dict(lonS=1.0,lonE=6.0,nyE=12.0),
 'KZ + NY PM 13-15 (all 1-15)':dict(lonS=1.0,lonE=15.0,nyS=1.0,nyE=15.0),
 'include Monday':dict(dowMask=31),
 'minRR 0.6':dict(minRR=0.6),
 'combo: 60m+disp0.7+fvg10':dict(setupExp=60,disp=0.7,fvgWait=10),
 'combo + KZ wide':dict(setupExp=60,disp=0.7,fvgWait=10,lonS=1.0,lonE=6.0,nyE=12.0),
}
rows=[]
for k,v in V.items():
    T=go(**dict(B,**v)); y=T.date.dt.year; s=stats(T)
    odd=T.R[y%2==1].mean(); even=T.R[y%2==0].mean(); r24=T[T.date>='2024-01-01']
    rows.append([k,s['n'],round(s['n']/17.8,1),len(r24),s['avgR'],round(odd,3),round(even,3),s['ret'],s['maxDD'],s['tstat'],round(r24.R.mean(),2)])
print(pd.DataFrame(rows,columns=['variant','n','n/yr','n24-26','avgR','oddY','evenY','ret%','DD%','t','avgR24-26']).to_string(index=False))
