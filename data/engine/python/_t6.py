import itertools, motor15 as M
b=M.load(); corte=b[len(b)//2][0]
def pf(v):
    g=sum(x for x in v if x>0); l=-sum(x for x in v if x<0); return g/l if l else 0
out=[]
for rr1,rr2,be,lk,slb,frac,esp in itertools.product(
        [1.2,1.5,2.0],[3.0,4.0,6.0,8.0],[0.8,1.0,1.5],[0.3,0.5,0.8],
        [1.0,2.0,4.0],[0.3,0.4,0.5],[5,8,12]):
    if lk >= be: continue
    tr,T=M.run(b,la3_entrada=False,la4_barrido=False,la7_mismavela=False,confirmar=True,
               cuerpo_frac=frac,espera=esp,exigir_cierre_fuera=True,
               rr1=rr1,rr2=rr2,be_trig=be,lock_r=lk,sl_buf=slb,
               ses_ini=540,ses_fin=660)
    r=M.resumen(tr,T,3)
    if r["trades"]<180: continue
    A=[x for x,t in zip(r["pnl"],r["times"]) if t<corte]
    B=[x for x,t in zip(r["pnl"],r["times"]) if t>=corte]
    a,bb=pf(A),pf(B)
    out.append((min(a,bb),rr1,rr2,be,lk,slb,frac,esp,r,a,bb))
out.sort(key=lambda x:-x[0])
print("{} configuraciones validas\n".format(len(out)))
print("{:>4} {:>4} {:>4} {:>4} {:>4} {:>5} {:>4} | {:>5} {:>10} {:>5} {:>9} {:>6} | {:>5} {:>5}".format(
    "RR1","RR2","BE","lock","slB","cuer","esp","ops","net","PF","DD","WR","1a","2a"))
for mn,rr1,rr2,be,lk,slb,frac,esp,r,a,bb in out[:15]:
    print("{:>4.1f} {:>4.1f} {:>4.1f} {:>4.1f} {:>4.1f} {:>5.0%} {:>4} | {:>5,} {:>10} {:>5.2f} {:>9} {:>5.1f}% | {:>5.2f} {:>5.2f}".format(
        rr1,rr2,be,lk,slb,frac,esp,r["trades"],"${:,.0f}".format(r["net"]),r["pf"],
        "${:,.0f}".format(r["dd"]),100*r["wr"],a,bb))
