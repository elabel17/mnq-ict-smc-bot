import itertools, motor_orb as M
b=M.load(); corte=b[len(b)//2][0]
def pf(v):
    g=sum(x for x in v if x>0); l=-sum(x for x in v if x<0); return g/l if l else 0
def ev(**kw):
    tr,T=M.run(b,**kw); r=M.resumen(tr,T,3)
    if r["trades"]<150: return None
    A=[x for x,t in zip(r["pnl"],r["times"]) if t<corte]
    B=[x for x,t in zip(r["pnl"],r["times"]) if t>=corte]
    r["a"]=pf(A); r["b"]=pf(B); return r
out=[]
for buf,be,lk,cierre,una,minr in itertools.product(
        [0.0,1.0,3.0],[0.0,1.0,1.5],[0.0,0.3,0.5],[720,840,955],[True,False],[0.0,20.0,30.0]):
    if be>0 and lk>=be: continue
    if be==0 and lk>0: continue
    r=ev(ini_min=570,fin_min=600,hasta_min=780,cierre_min=cierre,modo_entrada="stop",
         stop_modo="lado_opuesto",rr=0,buffer_pts=buf,be_trig=be,lock_r=lk,
         una_por_dia=una,min_rango=minr)
    if r: out.append((min(r["a"],r["b"]),buf,be,lk,cierre,una,minr,r))
out.sort(key=lambda x:-x[0])
print("ORB 09:30-10:00 · salida por hora · 3 contratos\n")
print("{:>4} {:>4} {:>4} {:>6} {:>5} {:>5} | {:>5} {:>10} {:>5} {:>9} {:>6} | {:>5} {:>5}".format(
  "buf","BE","lock","cierre","1/dia","rmin","ops","net","PF","DD","WR","1a","2a"))
for mn,buf,be,lk,ci,una,minr,r in out[:16]:
    print("{:>4.1f} {:>4.1f} {:>4.1f} {:>6} {:>5} {:>5.0f} | {:>5,} {:>10} {:>5.2f} {:>9} {:>5.1f}% | {:>5.2f} {:>5.2f}".format(
      buf,be,lk,"%02d:%02d"%(ci//60,ci%60),"si" if una else "no",minr,
      r["trades"],"${:,.0f}".format(r["net"]),r["pf"],"${:,.0f}".format(r["dd"]),100*r["wr"],r["a"],r["b"]))
