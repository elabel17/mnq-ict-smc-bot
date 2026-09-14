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
for fin,modo,stopm,rr in itertools.product([585,600,630,660],["stop","cierre"],
                                           ["lado_opuesto","mitad","fijo"],[0,1.5,2.0,3.0]):
    r=ev(ini_min=570,fin_min=fin,hasta_min=780,cierre_min=955,modo_entrada=modo,
         stop_modo=stopm,stop_pts=25.0,rr=rr,buffer_pts=1.0)
    if r: out.append((min(r["a"],r["b"]),fin,modo,stopm,rr,r))
out.sort(key=lambda x:-x[0])
print("rango desde 09:30 NY · 3 contratos · 2024-2026\n")
print("{:>6} {:>7} {:>13} {:>4} | {:>5} {:>10} {:>5} {:>9} {:>6} | {:>5} {:>5}".format(
  "fin","entrada","stop","RR","ops","net","PF","DD","WR","1a","2a"))
for mn,fin,modo,stopm,rr,r in out[:15]:
    print("{:>6} {:>7} {:>13} {:>4.1f} | {:>5,} {:>10} {:>5.2f} {:>9} {:>5.1f}% | {:>5.2f} {:>5.2f}".format(
      "%02d:%02d"%(fin//60,fin%60),modo,stopm,rr,r["trades"],"${:,.0f}".format(r["net"]),
      r["pf"],"${:,.0f}".format(r["dd"]),100*r["wr"],r["a"],r["b"]))
