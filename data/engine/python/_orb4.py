import itertools, motor_orb as M
b=M.load(); corte=b[len(b)//2][0]
def pf(v):
    g=sum(x for x in v if x>0); l=-sum(x for x in v if x<0); return g/l if l else 0
out=[]
for fin,hasta,cierre,be,lk,rr,stopm in itertools.product(
        [585,600,630],[720,780,840],[840,900,955],[0.8,1.0,1.5],[0.3,0.5],
        [0,2.0,3.0],["lado_opuesto","mitad"]):
    if lk>=be: continue
    tr,T=M.run(b,ini_min=570,fin_min=fin,hasta_min=hasta,cierre_min=cierre,
               modo_entrada="stop",stop_modo=stopm,rr=rr,buffer_pts=0.0,
               be_trig=be,lock_r=lk,una_por_dia=False,mismo_bar_stop=True)
    r=M.resumen(tr,T,3)
    if r["trades"]<200: continue
    A=[x for x,t in zip(r["pnl"],r["times"]) if t<corte]
    B=[x for x,t in zip(r["pnl"],r["times"]) if t>=corte]
    a,bb=pf(A),pf(B)
    out.append((min(a,bb),fin,hasta,cierre,be,lk,rr,stopm,r,a,bb))
out.sort(key=lambda x:-x[0])
print("{} configuraciones\n".format(len(out)))
print("{:>6} {:>6} {:>6} {:>4} {:>4} {:>4} {:>13} | {:>5} {:>10} {:>5} {:>9} {:>6} | {:>5} {:>5}".format(
  "rango","hasta","cierre","BE","lock","RR","stop","ops","net","PF","DD","WR","1a","2a"))
for mn,fin,hasta,ci,be,lk,rr,stopm,r,a,bb in out[:14]:
    hm=lambda m:"%02d:%02d"%(m//60,m%60)
    print("{:>6} {:>6} {:>6} {:>4.1f} {:>4.1f} {:>4.1f} {:>13} | {:>5,} {:>10} {:>5.2f} {:>9} {:>5.1f}% | {:>5.2f} {:>5.2f}".format(
      hm(fin),hm(hasta),hm(ci),be,lk,rr,stopm,r["trades"],"${:,.0f}".format(r["net"]),
      r["pf"],"${:,.0f}".format(r["dd"]),100*r["wr"],a,bb))
