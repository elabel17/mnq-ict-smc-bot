import motor_mtf as M, motor15 as M15
b5=M.load5(); b15,c15=M.agrupa(b5,15); z=M.zonas15(b15)
corte=b5[len(b5)//2][0]
def pf(v):
    g=sum(x for x in v if x>0); l=-sum(x for x in v if x<0); return g/l if l else 0
def fila(lab,r):
    if r["trades"]<120: return
    ta=list(zip(r["times"],r["pnl"]))
    A=[p for x,p in ta if x<corte]; B=[p for x,p in ta if x>=corte]
    print("{:<44} {:>5,} {:>10} {:>5.2f} {:>9} {:>5.1f}% | {:>5.2f} {:>5.2f}".format(
      lab,r["trades"],"${:,.0f}".format(r["net"]),r["pf"],"${:,.0f}".format(r["dd"]),100*r["wr"],pf(A),pf(B)))
print("{:<44} {:>5} {:>10} {:>5} {:>9} {:>6} | {:>5} {:>5}".format("variante","ops","net","PF","DD","WR","1a","2a"))
print("--- confirmacion en 5m (zona 15m) ---")
for esp in (9,12,18,24,36):
    for frac in (0.4,0.5):
        tr,T=M.run(b5,b15,c15,z,cuerpo_frac=frac,espera=esp)
        fila("5m cuerpo>=%.0f%% espera %d"%(100*frac,esp), M.resumen(tr,T,3))
print("--- confirmacion en 15m, MISMO periodo 2024-2026 ---")
b15p=[[x[0],x[1],x[2],x[3],x[4],0] for x in b15]
for esp in (5,8,12):
    for frac in (0.4,0.5):
        tr,T=M15.run(b15p,la3_entrada=False,la4_barrido=False,la7_mismavela=False,
                     confirmar=True,cuerpo_frac=frac,espera=esp,exigir_cierre_fuera=True,
                     rr1=1.5,rr2=6.0,be_trig=1.0,lock_r=0.5,sl_buf=2.0)
        fila("15m cuerpo>=%.0f%% espera %d"%(100*frac,esp), M15.resumen(tr,T,3))
