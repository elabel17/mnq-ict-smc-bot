import datetime as dt, collections, motor15 as M
b=M.load()
tr,T=M.run(b,la3_entrada=False,la4_barrido=False,la7_mismavela=False,confirmar=True,
           cuerpo_frac=0.5,espera=8,exigir_cierre_fuera=True,rr1=1.5,rr2=6.0,
           be_trig=0.8,lock_r=0.3,sl_buf=4.0,ses_ini=540,ses_fin=660)
print("CONFIRMACION 15m · 09:00-11:00 NY\n")
print("{:>6} {:>5} {:>11} {:>6} {:>9}".format("anio","ops","net 3c","PF","DD 3c"))
def pf(v):
    g=sum(x for x in v if x>0); l=-sum(x for x in v if x<0); return g/l if l else 0
r=M.resumen(tr,T,3)
per=collections.OrderedDict()
for t,p in zip(r["times"],r["pnl"]):
    per.setdefault(dt.datetime.utcfromtimestamp(t).year,[]).append(p)
for y,v in per.items():
    eq=pk=dd=0.0
    for x in v:
        eq+=x; pk=max(pk,eq); dd=max(dd,pk-eq)
    print("{:>6} {:>5} {:>11} {:>6.2f} {:>9}".format(y,len(v),"${:,.0f}".format(sum(v)),pf(v),"${:,.0f}".format(dd)))
span=(r["times"][-1]-r["times"][0])/86400/365.25
print("\nperiodo {:.2f} anios · {} ops · {:.1f} ops/anio".format(span,len(r["pnl"]),len(r["pnl"])/span))
print("\n{:>3} {:>9} {:>11} {:>11} {:>10} {:>10}".format("c","DD max","net total","net/anio","P estatico","P trailing"))
for q in (1,2,3,4,5,6):
    r=M.resumen(tr,T,q)
    pn=r["pnl"]; ts=r["times"]
    dias=collections.OrderedDict()
    for t,p in zip(ts,pn):
        dias.setdefault(dt.datetime.utcfromtimestamp(t).date(),[]).append(p)
    ks=list(dias)
    def sim(modo):
        ok=0; tot=0; largo=[]
        for s in range(len(ks)-20):
            eq=0.0; pico=0.0; res=None
            for i in range(s,len(ks)):
                x=eq
                for v in dias[ks[i]]:
                    x+=v
                    if x <= ((pico-2000) if modo=="tr" else -2000): res="q"; break
                if res: break
                eq=x
                if eq>=3000: res="p"; largo.append((ks[i]-ks[s]).days); break
                pico=max(pico,eq)
            if res: tot+=1; ok+= (res=="p")
        largo.sort()
        return (100*ok/max(1,tot), largo[len(largo)//2] if largo else 0)
    e=sim("es"); t2=sim("tr")
    print("{:>3} {:>9} {:>11} {:>11} {:>9.1f}% {:>9.1f}%".format(
        q,"${:,.0f}".format(r["dd"]),"${:,.0f}".format(r["net"]),
        "${:,.0f}".format(r["net"]/span),e[0],t2[0]))
    if q in (1,2,3):
        print("      mediana para pasar: {} dias estatico / {} dias trailing ({:.1f} / {:.1f} semanas)".format(
            e[1],t2[1],e[1]/7,t2[1]/7))
