import motor_orb as M
b5=M.load(); b15=M.load("../../python/claude_ohlcv_15m_2020_2026.json")
def pf(v):
    g=sum(x for x in v if x>0); l=-sum(x for x in v if x<0); return g/l if l else 0
def ev(bars,lab,**kw):
    corte=bars[len(bars)//2][0]
    tr,T=M.run(bars,**kw); r=M.resumen(tr,T,3)
    if r["trades"]<80: print("  %-44s pocas ops"%lab); return
    A=[x for x,t in zip(r["pnl"],r["times"]) if t<corte]
    B=[x for x,t in zip(r["pnl"],r["times"]) if t>=corte]
    print("  {:<44} {:>5,} {:>10} {:>5.2f} {:>9} {:>5.1f}% | {:>5.2f} {:>5.2f}".format(
      lab,r["trades"],"${:,.0f}".format(r["net"]),r["pf"],"${:,.0f}".format(r["dd"]),100*r["wr"],pf(A),pf(B)))
base=dict(ini_min=570,fin_min=600,hasta_min=780,cierre_min=955,modo_entrada="stop",
          stop_modo="lado_opuesto",rr=0,buffer_pts=0.0,be_trig=1.0,lock_r=0.5,una_por_dia=False)
print("{:<46} {:>5} {:>10} {:>5} {:>9} {:>6} | {:>5} {:>5}".format("","ops","net","PF","DD","WR","1a","2a"))
print("5m 2024-2026:")
ev(b5,"sin comprobar stop en la vela de entrada",mismo_bar_stop=False,**base)
ev(b5,"CON stop en la misma vela (realista)",mismo_bar_stop=True,**base)
print("15m 2020-2026 (misma logica, otro marco):")
ev(b15,"sin comprobar stop en la vela de entrada",mismo_bar_stop=False,**base)
ev(b15,"CON stop en la misma vela (realista)",mismo_bar_stop=True,**base)
