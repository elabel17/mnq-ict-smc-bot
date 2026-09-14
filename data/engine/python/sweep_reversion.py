import motor_confluencia as M
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
NY = ZoneInfo("America/New_York")

def detectar_sweep_reversion(bars, n_lado=8, tol_pts=1.0, rr1=1.5, rr2=5.0, be_trig=0.3, lock_r=0.15,
                              sl_buf=2.0, espera=3, cuerpo_frac=0.4, ses_ini=480, ses_fin=780):
    O=[b[1] for b in bars]; H=[b[2] for b in bars]; L=[b[3] for b in bars]; C=[b[4] for b in bars]; T=[b[0] for b in bars]
    n=len(bars)
    piv_hi, piv_lo, conf = M.detectar_pivotes(H, L, n_lado)
    nym=[]
    for t in T:
        d=datetime.fromtimestamp(t,tz=timezone.utc).astimezone(NY); nym.append(d.hour*60+d.minute)
    activar_hi={}; activar_lo={}
    for i in range(n):
        if piv_hi[i] is not None: activar_hi.setdefault(conf[i], []).append(piv_hi[i])
        if piv_lo[i] is not None: activar_lo.setdefault(conf[i], []).append(piv_lo[i])
    ult_hi = ult_lo = None
    arm=None; open_=False; dir_=0; ep=sl=0.0; risk=0.0; eIdx=0; tp1=False; moved=False
    trades=[]
    for i in range(n):
        for v in activar_hi.get(i, []): ult_hi=v
        for v in activar_lo.get(i, []): ult_lo=v
        inS = ses_ini<=nym[i]<ses_fin
        if i<30: continue
        if not open_ and inS:
            if arm is None:
                if ult_lo is not None and L[i] < ult_lo - tol_pts and C[i] > ult_lo:
                    arm = [1, ult_lo, L[i], i]; ult_lo=None
                elif ult_hi is not None and H[i] > ult_hi + tol_pts and C[i] < ult_hi:
                    arm = [-1, H[i], ult_hi, i]; ult_hi=None
            elif i - arm[3] > espera:
                arm = None
            if arm is not None and i > arm[3]:
                cuerpo=abs(C[i]-O[i]); r_=H[i]-L[i]
                if arm[0]==1:
                    ok = C[i]>O[i] and r_>0 and cuerpo>=cuerpo_frac*r_
                    if ok:
                        _ep=C[i]; _sl=arm[2]-sl_buf; _r=_ep-_sl
                        if 0<_r<=100:
                            ep,sl,risk,open_,dir_,eIdx,tp1,moved=_ep,_sl,_r,True,1,i,False,False
                            arm=None
                else:
                    ok = C[i]<O[i] and r_>0 and cuerpo>=cuerpo_frac*r_
                    if ok:
                        _ep=C[i]; _sl=arm[1]+sl_buf; _r=_sl-_ep
                        if 0<_r<=100:
                            ep,sl,risk,open_,dir_,eIdx,tp1,moved=_ep,_sl,_r,True,-1,i,False,False
                            arm=None
        if open_ and i>eIdx:
            t1=ep+risk*rr1*dir_; t2=ep+risk*rr2*dir_
            hitSL=(L[i]<=sl) if dir_==1 else (H[i]>=sl)
            if not tp1:
                hT1=(H[i]>=t1) if dir_==1 else (L[i]<=t1)
                if hitSL: trades.append((eIdx,risk,dir_,sl,ep)); open_=False
                elif hT1:
                    tp1=True; be=ep+risk*lock_r*dir_
                    if (not moved) or (be>sl if dir_==1 else be<sl): sl=be
                    moved=True
                elif not moved:
                    re=(H[i]-ep)/risk if dir_==1 else (ep-L[i])/risk
                    if re>=be_trig: sl=ep+risk*lock_r*dir_; moved=True
            else:
                hT2=(H[i]>=t2) if dir_==1 else (L[i]<=t2)
                if hitSL: trades.append((eIdx,risk,dir_,sl,ep)); open_=False
                elif hT2: trades.append((eIdx,risk,dir_,t2,ep)); open_=False
    return trades, T
