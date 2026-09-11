import motor15 as M
b=M.load(); corte=b[len(b)//2][0]
def pf(v):
    g=sum(x for x in v if x>0); l=-sum(x for x in v if x<0); return g/l if l else 0
def ev(ini,fin,dmin=0.0,**kw):
    base=dict(la3_entrada=False,la4_barrido=False,la7_mismavela=False,confirmar=True,
              cuerpo_frac=0.4,espera=8,exigir_cierre_fuera=True,rr1=1.5,rr2=6.0,
              be_trig=1.0,lock_r=0.5,sl_buf=2.0,ses_ini=ini*60,ses_fin=fin*60)
    base.update(kw)
    tr,T=M.run(b,**base); r=M.resumen(tr,T,3)
    idx=[i for i,f in enumerate(r["fuerza"]) if f>=dmin]
    p=[r["pnl"][i] for i in idx]; t=[r["times"][i] for i in idx]
    if len(p)<100: return None
    A=[x for x,tt in zip(p,t) if tt<corte]; B=[x for x,tt in zip(p,t) if tt>=corte]
    eq=pk=dd=0.0
    for x in p:
        eq+=x; pk=max(pk,eq); dd=max(dd,pk-eq)
    return dict(ops=len(p),net=sum(p),pf=pf(p),dd=dd,a=pf(A),b=pf(B),
                wr=sum(1 for x in p if x>0)/len(p))
print("{:<30} {:>5} {:>10} {:>5} {:>9} {:>6} | {:>5} {:>5}".format("ventana","ops","net","PF","DD","WR","1a","2a"))
for ini,fin in [(18,11),(9,12),(10,12),(9,11),(10,11),(8,12),(7,12),(3,5),(9,14),(10,14)]:
    for dmin in (0.0,2.74):
        r=ev(ini,fin,dmin)
        if not r: continue
        print("{:<30} {:>5,} {:>10} {:>5.2f} {:>9} {:>5.1f}% | {:>5.2f} {:>5.2f}".format(
          "{:02d}-{:02d}{}".format(ini,fin," fuerza>=2.74" if dmin else ""),
          r["ops"],"${:,.0f}".format(r["net"]),r["pf"],"${:,.0f}".format(r["dd"]),100*r["wr"],r["a"],r["b"]))
