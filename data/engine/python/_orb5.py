import datetime as dt, collections, motor_orb as M
b=M.load()
tr,T=M.run(b,ini_min=570,fin_min=600,hasta_min=780,cierre_min=955,modo_entrada="stop",
           stop_modo="lado_opuesto",rr=0,buffer_pts=0.0,be_trig=1.0,lock_r=0.5,
           una_por_dia=False,mismo_bar_stop=True)
def pf(v):
    g=sum(x for x in v if x>0); l=-sum(x for x in v if x<0); return g/l if l else 0
r=M.resumen(tr,T,3)
span=(r["times"][-1]-r["times"][0])/86400/365.25
print("ORB 09:30-10:00 NY (sin optimizar) · {} ops en {:.2f} anios = {:.0f}/ano\n".format(
    len(r["pnl"]),span,len(r["pnl"])/span))
per=collections.OrderedDict()
for t,p in zip(r["times"],r["pnl"]):
    per.setdefault(dt.datetime.utcfromtimestamp(t).strftime("%Y"),[]).append(p)
print("{:>6} {:>5} {:>11} {:>6}".format("anio","ops","net 3c","PF"))
for y,v in per.items():
    print("{:>6} {:>5} {:>11} {:>6.2f}".format(y,len(v),"${:,.0f}".format(sum(v)),pf(v)))
print("\n{:>3} {:>9} {:>11} {:>11} {:>11} {:>12}".format("c","DD max","net total","net/anio","P trailing","mediana"))
for q in (1,2,3,4,5,6,8):
    rr=M.resumen(tr,T,q)
    dias=collections.OrderedDict()
    for t,p in zip(rr["times"],rr["pnl"]):
        dias.setdefault(dt.datetime.utcfromtimestamp(t).date(),[]).append(p)
    ks=list(dias); ok=0; tot=0; largo=[]
    for s in range(len(ks)-20):
        eq=0.0; pico=0.0; res=None
        for i in range(s,len(ks)):
            x=eq
            for v in dias[ks[i]]:
                x+=v
                if x<=pico-2000: res="q"; break
            if res: break
            eq=x
            if eq>=3000: res="p"; largo.append((ks[i]-ks[s]).days); break
            pico=max(pico,eq)
        if res: tot+=1; ok+=(res=="p")
    largo.sort()
    med=largo[len(largo)//2] if largo else 0
    print("{:>3} {:>9} {:>11} {:>11} {:>10.1f}% {:>9.1f} sem".format(
        q,"${:,.0f}".format(rr["dd"]),"${:,.0f}".format(rr["net"]),
        "${:,.0f}".format(rr["net"]/span),100*ok/max(1,tot),med/7))
