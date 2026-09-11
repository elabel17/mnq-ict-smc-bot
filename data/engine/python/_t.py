import motor_mtf as M
b5=M.load5(); b15,c15=M.agrupa(b5,15); z=M.zonas15(b15)
print("velas 5m",len(b5)," velas 15m",len(b15)," zonas",sum(1 for x in z if x))
corte=b5[len(b5)//2][0]
def pf(v):
    g=sum(x for x in v if x>0); l=-sum(x for x in v if x<0); return g/l if l else 0
print()
print("{:<46} {:>5} {:>10} {:>5} {:>9} {:>6} | {:>5} {:>5}".format("variante","ops","net","PF","DD","WR","1a","2a"))
for frac in (0.4,0.5,0.6):
    for esp in (3,6,9):
        tr,T=M.run(b5,b15,c15,z,cuerpo_frac=frac,espera=esp)
        r=M.resumen(tr,T,3)
        if r["trades"]<150: continue
        ta=list(zip(r["times"],r["pnl"]))
        A=[p for x,p in ta if x<corte]; B=[p for x,p in ta if x>=corte]
        print("{:<46} {:>5,} {:>10} {:>5.2f} {:>9} {:>5.1f}% | {:>5.2f} {:>5.2f}".format(
          "zona 15m + vela 5m cuerpo>=%.0f%% espera %d"%(100*frac,esp),
          r["trades"],"${:,.0f}".format(r["net"]),r["pf"],"${:,.0f}".format(r["dd"]),100*r["wr"],pf(A),pf(B)))
