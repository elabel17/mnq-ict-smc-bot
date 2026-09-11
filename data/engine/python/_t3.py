import motor15 as M
b=M.load(); corte=b[len(b)//2][0]
def pf(v):
    g=sum(x for x in v if x>0); l=-sum(x for x in v if x<0); return g/l if l else 0
base=dict(la3_entrada=False,la4_barrido=False,la7_mismavela=False,confirmar=True,
          cuerpo_frac=0.4,espera=8,exigir_cierre_fuera=True,rr1=1.5,rr2=6.0,
          be_trig=1.0,lock_r=0.5,sl_buf=2.0)
tr,T=M.run(b,**base); r=M.resumen(tr,T,3)
print("BASE: {} ops  ${:,.0f}  PF {:.2f}  DD ${:,.0f}\n".format(r["trades"],r["net"],r["pf"],r["dd"]))
print("PnL por hora NY:")
import datetime as dt
from zoneinfo import ZoneInfo
NY=ZoneInfo("America/New_York")
h={}
for t,p in zip(r["times"],r["pnl"]):
    k=dt.datetime.fromtimestamp(t,tz=dt.timezone.utc).astimezone(NY).hour
    h.setdefault(k,[]).append(p)
for k in sorted(h):
    v=h[k]
    if len(v)<15: continue
    print("  {:>2}:00  ops {:>4}  ${:>8,.0f}  PF {:.2f}".format(k,len(v),sum(v),pf(v)))
print("\nfrescura de zona (velas de 15m entre nacimiento y toque):")
for mx in (2,4,8,16,32,999):
    v=[p for p,e in zip(r["pnl"],r["edad"]) if e<=mx]
    if len(v)<80: continue
    print("  <= {:>3}  ops {:>4}  ${:>8,.0f}  PF {:.2f}".format(mx,len(v),sum(v),pf(v)))
print("\nfuerza del desplazamiento:")
f=sorted(r["fuerza"])
for q in (0.25,0.5,0.75):
    u=f[int(q*(len(f)-1))]
    v=[p for p,x in zip(r["pnl"],r["fuerza"]) if x>=u]
    print("  >= {:.2f} (p{:.0f})  ops {:>4}  ${:>8,.0f}  PF {:.2f}".format(u,100*q,len(v),sum(v),pf(v)))
