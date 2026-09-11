"""Motor de 15m — puerto fiel de backtest_engine_validated.js con interruptores
para cada look-ahead detectado, de modo que se pueda medir cuanto aporta cada uno.

  la3_entrada   : ep = max(low, zoneTop)  -> el precio de entrada se escoge
                  DESPUES de ver hasta donde llego la vela
  la4_barrido   : exige low >= zoneBot    -> descarta a posteriori las velas que
                  perforaron el fondo del OB
  la7_mismavela : permite entrar en la MISMA vela en que la zona se valida,
                  cuando la orden aun no podia estar puesta
"""
import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
NY = ZoneInfo("America/New_York")
TICK, PV = 0.25, 2.0
SLIPPAGE_TICKS = 2
COMMISSION_PER_CONTRACT_SIDE = 1.00

def load(fn="../../python/claude_ohlcv_15m_2020_2026.json"):
    d = json.load(open(fn)); return d["bars"] if isinstance(d, dict) else d

def run(bars, lock_r=0.5, be_trig=1.2, rr1=1.8, rr2=4.0, risk_cap=100,
        disp_mult=2.5, disp_frac=0.6, ob_scan=10, liq_win=12, liq_tol=4.0,
        liq_accum=6, sl_buf=2.0, entry_buf=12.0,
        la3_entrada=True, la4_barrido=True, la7_mismavela=True,
        confirmar=False, cuerpo_frac=0.5, espera=3, exigir_cierre_fuera=True,
        ses_ini=1080, ses_fin=660):
    n = len(bars)
    O=[b[1] for b in bars]; H=[b[2] for b in bars]; L=[b[3] for b in bars]
    C=[b[4] for b in bars]; T=[b[0] for b in bars]
    avg=[None]*n; s=0.0
    for i in range(n):
        s += H[i]-L[i]
        if i>=20: s -= H[i-20]-L[i-20]
        avg[i] = s/20 if i>=19 else None
    nym=[]; nyd=[]
    for t in T:
        d=datetime.fromtimestamp(t,tz=timezone.utc).astimezone(NY)
        nym.append(d.hour*60+d.minute); nyd.append(d.weekday())

    bT=bB=sT=sB=None; bF=bC=sF=sC=False; bClr=sClr=-1
    bBorn=sBorn=-1; bDr=sDr=0.0
    open_=False; dir_=0; ep=sl=0.0; risk=0.0; eIdx=0; tp1=False; moved=False
    trades=[]; meta=(0,0.0)
    armL=[-1,0.0,0.0,0,0.0]; armS=[-1,0.0,0.0,0,0.0]   # zona armada: [vela del toque, top, bot]
    for i in range(45,n):
        rng=H[i]-L[i]
        isD = avg[i-1] is not None and rng >= disp_mult*avg[i-1]
        bD = isD and C[i]>O[i] and (C[i]-L[i])>=disp_frac*rng
        sD = isD and C[i]<O[i] and (H[i]-C[i])>=disp_frac*rng
        bN=sN=False
        if bD:
            idx=-1
            for k in range(1,ob_scan+1):
                if C[i-k]<O[i-k]: idx=k; break
            if idx>0:
                cand=L[i-idx]; mx=cu=0
                for j in range(idx+1,idx+liq_win+1):
                    if i-j<0: break
                    if L[i-j]<=cand+liq_tol: cu+=1; mx=max(mx,cu)
                    else: cu=0
                if mx<liq_accum: bT=H[i-idx]; bB=cand; bF=True; bC=False; bN=True; bClr=-1; bBorn=i; bDr=rng/avg[i-1]
        if sD:
            idx=-1
            for k in range(1,ob_scan+1):
                if C[i-k]>O[i-k]: idx=k; break
            if idx>0:
                cand=H[i-idx]; mx=cu=0
                for j in range(idx+1,idx+liq_win+1):
                    if i-j<0: break
                    if H[i-j]>=cand-liq_tol: cu+=1; mx=max(mx,cu)
                    else: cu=0
                if mx<liq_accum: sT=cand; sB=L[i-idx]; sF=True; sC=False; sN=True; sClr=-1; sBorn=i; sDr=rng/avg[i-1]
        if (not bN) and bF and (not bC) and bT is not None and L[i]>bT: bC=True; bClr=i
        if (not sN) and sF and (not sC) and sB is not None and H[i]<sB: sC=True; sClr=i
        bTou=(not bN) and bC and bF
        sTou=(not sN) and sC and sF
        if not la7_mismavela:
            bTou = bTou and i > bClr
            sTou = sTou and i > sClr
        if (not bN) and bC and bF and bT is not None and L[i]<=bT: bF=False
        if (not sN) and sC and sF and sB is not None and H[i]>=sB: sF=False
        lz = bTou and bT is not None and L[i]<=bT+entry_buf and ((L[i]>=bB) if la4_barrido else True)
        sz = sTou and sB is not None and H[i]>=sB-entry_buf and ((H[i]<=sT) if la4_barrido else True)
        inS = (nym[i]>=ses_ini) or (nym[i]<ses_fin) if ses_ini>ses_fin else (ses_ini<=nym[i]<ses_fin)
        ce = inS and (not open_) and nyd[i]!=6
        if confirmar:
            # ---- ENTRADA POR CONFIRMACION ----
            # El toque solo ARMA la zona. Se entra al CIERRE de una vela de
            # reaccion posterior. Causal por construccion: el precio de entrada
            # es el cierre de una vela ya formada, no se puede escoger mirando
            # hasta donde llego la vela.
            if lz and armL[0] < 0: armL[0] = i; armL[1] = bT; armL[2] = bB; armL[3] = i-bBorn; armL[4] = bDr
            if sz and armS[0] < 0: armS[0] = i; armS[1] = sT; armS[2] = sB; armS[3] = i-sBorn; armS[4] = sDr
            if armL[0] >= 0 and i - armL[0] > espera: armL[0] = -1
            if armS[0] >= 0 and i - armS[0] > espera: armS[0] = -1

            if ce and armL[0] >= 0 and i > armL[0]:
                cuerpo = abs(C[i]-O[i]); r_ = H[i]-L[i]
                ok = C[i] > O[i] and r_ > 0 and cuerpo >= cuerpo_frac*r_
                if ok and exigir_cierre_fuera: ok = C[i] > armL[1]
                if ok:
                    _ep = C[i]; _sl = min(armL[2], L[i]) - sl_buf; _r = _ep-_sl
                    if 0 < _r <= risk_cap:
                        ep,sl,risk,open_,dir_,eIdx,tp1,moved=_ep,_sl,_r,True,1,i,False,False
                        meta=(armL[3],armL[4]); armL[0] = -1; armS[0] = -1
            if ce and (not open_) and armS[0] >= 0 and i > armS[0]:
                cuerpo = abs(C[i]-O[i]); r_ = H[i]-L[i]
                ok = C[i] < O[i] and r_ > 0 and cuerpo >= cuerpo_frac*r_
                if ok and exigir_cierre_fuera: ok = C[i] < armS[1]
                if ok:
                    _ep = C[i]; _sl = max(armS[2], H[i]) + sl_buf; _r = _sl-_ep
                    if 0 < _r <= risk_cap:
                        ep,sl,risk,open_,dir_,eIdx,tp1,moved=_ep,_sl,_r,True,-1,i,False,False
                        meta=(armS[3],armS[4]); armL[0] = -1; armS[0] = -1
        elif ce and lz:
            _ep = max(L[i],bT) if la3_entrada else bT+entry_buf
            _sl = bB-sl_buf; _r=_ep-_sl
            if 0 < _r <= risk_cap:
                ep,sl,risk,open_,dir_,eIdx,tp1,moved=_ep,_sl,_r,True,1,i,False,False
        elif ce and sz:
            _ep = min(H[i],sB) if la3_entrada else sB-entry_buf
            _sl = sT+sl_buf; _r=_sl-_ep
            if 0 < _r <= risk_cap:
                ep,sl,risk,open_,dir_,eIdx,tp1,moved=_ep,_sl,_r,True,-1,i,False,False
        if open_:
            t1 = ep+risk*rr1*dir_; t2 = ep+risk*rr2*dir_
            hitSL = (L[i]<=sl) if dir_==1 else (H[i]>=sl)
            if not tp1:
                hT1 = (H[i]>=t1) if dir_==1 else (L[i]<=t1)
                if hitSL:
                    trades.append((eIdx,risk,dir_,sl,ep,'full' if not moved else 'locked',meta)); open_=False
                elif hT1:
                    tp1=True; be=ep+risk*lock_r*dir_
                    if (not moved) or (be>sl if dir_==1 else be<sl): sl=be
                    moved=True
                elif not moved:
                    re = (H[i]-ep)/risk if dir_==1 else (ep-L[i])/risk
                    if re>=be_trig: sl=ep+risk*lock_r*dir_; moved=True
            else:
                hT2 = (H[i]>=t2) if dir_==1 else (L[i]<=t2)
                if hitSL: trades.append((eIdx,risk,dir_,sl,ep,'tras_tp1',meta)); open_=False
                elif hT2: trades.append((eIdx,risk,dir_,t2,ep,'runner',meta)); open_=False
    return trades, T

def resumen(trades, T, qty=3, label=""):
    slip=TICK*SLIPPAGE_TICKS; pnl=[]
    for eIdx,risk,d,exitp,ep,kind,meta in trades:
        pts=(exitp-ep)*d - slip
        pnl.append(pts*PV*qty - COMMISSION_PER_CONTRACT_SIDE*qty*2)
    if not pnl: return dict(trades=0,net=0,pf=0,dd=0,wr=0)
    g=sum(x for x in pnl if x>0); l=-sum(x for x in pnl if x<0)
    eq=pk=dd=0.0
    for x in pnl:
        eq+=x; pk=max(pk,eq); dd=max(dd,pk-eq)
    return dict(trades=len(pnl), net=sum(pnl), pf=(g/l if l else 0),
                dd=dd, wr=sum(1 for x in pnl if x>0)/len(pnl),
                times=[T[t[0]] for t in trades], pnl=pnl,
                edad=[t[6][0] for t in trades], fuerza=[t[6][1] for t in trades])
