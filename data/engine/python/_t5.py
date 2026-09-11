import motor15 as M
# Mismo motor, pero alimentado con velas de 5m: zona y confirmacion en 5m.
b5=M.load("../../python/claude_ohlcv_5m_2024_2026.json")
b15=M.load()
corte5=b5[len(b5)//2][0]; corte15=b15[len(b15)//2][0]
def pf(v):
    g=sum(x for x in v if x>0); l=-sum(x for x in v if x<0); return g/l if l else 0
def ev(bars,corte,ini,fin,**kw):
    base=dict(la3_entrada=False,la4_barrido=False,la7_mismavela=False,confirmar=True,
              cuerpo_frac=0.4,espera=8,exigir_cierre_fuera=True,rr1=1.5,rr2=6.0,
              be_trig=1.0,lock_r=0.5,sl_buf=2.0,ses_ini=ini*60,ses_fin=fin*60)
    base.update(kw)
    tr,T=M.run(bars,**base); r=M.resumen(tr,T,3)
    if r["trades"]<80: return None
    A=[x for x,t in zip(r["pnl"],r["times"]) if t<corte]
    B=[x for x,t in zip(r["pnl"],r["times"]) if t>=corte]
    r["a"]=pf(A); r["b"]=pf(B); return r
def fila(lab,r):
    if not r: return
    print("{:<38} {:>5,} {:>10} {:>5.2f} {:>9} {:>5.1f}% | {:>5.2f} {:>5.2f}".format(
      lab,r["trades"],"${:,.0f}".format(r["net"]),r["pf"],"${:,.0f}".format(r["dd"]),100*r["wr"],r["a"],r["b"]))
print("{:<38} {:>5} {:>10} {:>5} {:>9} {:>6} | {:>5} {:>5}".format("variante","ops","net","PF","DD","WR","1a","2a"))
print("--- 15m referencia (6,2 anios) ---")
fila("15m 09-11", ev(b15,corte15,9,11))
print("--- 15m en el periodo del 5m (2,6 anios) ---")
b15r=[x for x in b15 if x[0]>=b5[0][0]]
fila("15m 09-11 (2024-2026)", ev(b15r,b15r[len(b15r)//2][0],9,11))
print("--- 5m: zona y confirmacion en 5m ---")
for esp in (8,16,24):
    for frac in (0.4,0.5):
        fila("5m 09-11 cuerpo>={:.0f}% espera {}".format(100*frac,esp),
             ev(b5,corte5,9,11,cuerpo_frac=frac,espera=esp,sl_buf=0.5,entry_buf=8.0))
for esp in (8,16):
    fila("5m 09-12 espera {}".format(esp), ev(b5,corte5,9,12,espera=esp,sl_buf=0.5,entry_buf=8.0))
    fila("5m 10-11 espera {}".format(esp), ev(b5,corte5,10,11,espera=esp,sl_buf=0.5,entry_buf=8.0))
