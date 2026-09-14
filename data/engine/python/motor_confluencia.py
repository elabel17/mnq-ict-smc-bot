"""Motor de CONFLUENCIA — Order Block + Fair Value Gap + Pivote + Fibonacci.

Cada detector es independiente y CAUSAL: usa solo informacion ya cerrada en
el momento de decidir. Se puede medir el aporte de cada ingrediente por
separado antes de combinarlos (asi se hizo con disp_mult, la sesion y la
frescura de zona en el 5m, y funciono).

  OB  : desplazamiento + filtro de liquidez (igual a motor15/motor_orb)
  FVG : hueco de 3 velas -- low[i] > high[i-2] (alcista) o high[i] < low[i-2]
        (bajista). Se conoce en cuanto la vela i cierra.
  PIV : pivote de swing confirmado -- high[i] es el mayor de N velas a cada
        lado. Solo se puede saber que i fue un pivote N velas DESPUES de i,
        es decir, el pivote se conoce recien en la vela i+N.
  FIB : retroceso 38.2/50/61.8 del ultimo swing confirmado (pivote-a-pivote).

Entrada: confirmacion por vela de reaccion (lo unico que dio ventaja el
2026-09-11/12), sobre la zona que resulte de las confluencias activas.
"""
import json
_CACHE = {}
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
NY = ZoneInfo("America/New_York")
TICK, PV = 0.25, 2.0
SLIPPAGE_TICKS = 2
COMMISSION_PER_CONTRACT_SIDE = 1.00


def load(fn="../../python/claude_ohlcv_5m_2024_2026.json"):
    d = json.load(open(fn))
    return d["bars"] if isinstance(d, dict) else d


def _avg_range(H, L, n, win=20):
    avg = [None] * n
    s = 0.0
    for i in range(n):
        s += H[i] - L[i]
        if i >= win:
            s -= H[i - win] - L[i - win]
        avg[i] = s / win if i >= win - 1 else None
    return avg


def detectar_ob(O, H, L, C, avg, disp_mult=2.0, disp_frac=0.6, ob_scan=10,
                 liq_win=12, liq_tol=4.0, liq_accum=6):
    n = len(O)
    zonas = [None] * n
    for i in range(30, n):
        rng = H[i] - L[i]
        if avg[i - 1] is None or rng < disp_mult * avg[i - 1]:
            continue
        if C[i] > O[i] and (C[i] - L[i]) >= disp_frac * rng:
            idx = -1
            for k in range(1, ob_scan + 1):
                if C[i - k] < O[i - k]:
                    idx = k; break
            if idx > 0:
                cand = L[i - idx]; mx = cu = 0
                for j in range(idx + 1, idx + liq_win + 1):
                    if i - j < 0: break
                    if L[i - j] <= cand + liq_tol: cu += 1; mx = max(mx, cu)
                    else: cu = 0
                if mx < liq_accum:
                    zonas[i] = (1, H[i - idx], cand)
        elif C[i] < O[i] and (H[i] - C[i]) >= disp_frac * rng:
            idx = -1
            for k in range(1, ob_scan + 1):
                if C[i - k] > O[i - k]: idx = k; break
            if idx > 0:
                cand = H[i - idx]; mx = cu = 0
                for j in range(idx + 1, idx + liq_win + 1):
                    if i - j < 0: break
                    if H[i - j] >= cand - liq_tol: cu += 1; mx = max(mx, cu)
                    else: cu = 0
                if mx < liq_accum:
                    zonas[i] = (-1, cand, L[i - idx])
    return zonas


def detectar_fvg(O, H, L, C, min_gap_pts=0.0):
    """FVG de 3 velas. Se conoce COMPLETO al cerrar la vela i (usa i-2, i-1, i).
    top/bot del hueco: alcista = (low[i], high[i-2]); bajista = (high[i], low[i-2])."""
    n = len(O)
    fvg = [None] * n
    for i in range(2, n):
        if L[i] > H[i - 2] and (L[i] - H[i - 2]) >= min_gap_pts:
            fvg[i] = (1, L[i], H[i - 2])
        elif H[i] < L[i - 2] and (L[i - 2] - H[i]) >= min_gap_pts:
            fvg[i] = (-1, L[i - 2], H[i])
    return fvg


def detectar_pivotes(H, L, n_lado=5):
    """Pivote de swing. IMPORTANTE: un pivote en la vela i solo se CONFIRMA
    (se sabe que existe) en la vela i+n_lado, cuando ya se vieron las n_lado
    velas posteriores. confirmado_en[i] = indice de vela donde se supo."""
    n = len(H)
    piv_hi = [None] * n  # valor del pivote (si lo hay), indexado por vela DE ORIGEN
    piv_lo = [None] * n
    confirmado_en = [None] * n
    for i in range(n_lado, n - n_lado):
        seg_h = H[i - n_lado:i + n_lado + 1]
        seg_l = L[i - n_lado:i + n_lado + 1]
        if H[i] == max(seg_h) and seg_h.count(H[i]) == 1:
            piv_hi[i] = H[i]; confirmado_en[i] = i + n_lado
        if L[i] == min(seg_l) and seg_l.count(L[i]) == 1:
            piv_lo[i] = L[i]; confirmado_en[i] = i + n_lado
    return piv_hi, piv_lo, confirmado_en


def detectar_ob_bos(O, H, L, C, n_lado=5, disp_mult=0.0, avg=None,
                     origin_scan=10):
    """OB anclado a RUPTURA DE ESTRUCTURA (BOS), no a un ratio de rango fijo.
    dispMult=0 desactiva el filtro de displacement (BOS puro); >0 exige
    ademas que la vela de ruptura sea de rango >= dispMult*avg (BOS + fuerza).
    """
    n = len(O)
    piv_hi, piv_lo, conf = detectar_pivotes(H, L, n_lado)
    zonas = [None] * n
    ult_hi = ult_lo = None
    # cola de pivotes pendientes de activarse (ordenados por vela de origen)
    activar_hi = {}; activar_lo = {}
    for i in range(n):
        if piv_hi[i] is not None: activar_hi.setdefault(conf[i], []).append(piv_hi[i])
        if piv_lo[i] is not None: activar_lo.setdefault(conf[i], []).append(piv_lo[i])
    for i in range(n):
        for v in activar_hi.get(i, []): ult_hi = v
        for v in activar_lo.get(i, []): ult_lo = v
        if i < 30: continue
        rng = H[i] - L[i]
        fuerte = disp_mult <= 0 or (avg[i - 1] is not None and rng >= disp_mult * avg[i - 1])
        if ult_hi is not None and C[i] > ult_hi and C[i] > O[i] and fuerte:
            idx = -1
            for k in range(1, origin_scan + 1):
                if C[i - k] < O[i - k]: idx = k; break
            if idx > 0:
                zonas[i] = (1, H[i - idx], L[i - idx])
                ult_hi = None  # esa ruptura ya se conto, no repetir cada vela
        elif ult_lo is not None and C[i] < ult_lo and C[i] < O[i] and fuerte:
            idx = -1
            for k in range(1, origin_scan + 1):
                if C[i - k] > O[i - k]: idx = k; break
            if idx > 0:
                zonas[i] = (-1, H[i - idx], L[i - idx])
                ult_lo = None
    return zonas


def zonas_pivote(H, L, n_lado=5, max_edad=200):
    """Convierte pivotes confirmados en niveles S/R activos desde que se
    confirman. Devuelve, por vela, la lista de niveles (precio, tipo) vivos
    -- solo los confirmados en las ultimas `max_edad` velas, para no acumular
    para siempre (S/R muy viejo deja de ser relevante y encarece el calculo)."""
    piv_hi, piv_lo, conf = detectar_pivotes(H, L, n_lado)
    n = len(H)
    disponibles_desde = {}
    for i in range(n):
        if piv_hi[i] is not None:
            disponibles_desde.setdefault(conf[i], []).append((piv_hi[i], 1))
        if piv_lo[i] is not None:
            disponibles_desde.setdefault(conf[i], []).append((piv_lo[i], -1))
    activos_por_vela = [None] * n
    ventana = []  # [(nivel, tipo, nacido_en)]
    for i in range(n):
        for niv in disponibles_desde.get(i, []):
            ventana.append((niv[0], niv[1], i))
        if ventana and ventana[0][2] < i - max_edad:
            ventana = [v for v in ventana if v[2] >= i - max_edad]
        activos_por_vela[i] = [(v[0], v[1]) for v in ventana]
    return activos_por_vela


def run(bars, ses_ini=480, ses_fin=720, disp_mult=2.0, disp_frac=0.6,
        entry_buf=8.0, sl_buf=2.0, cuerpo_frac=0.5, espera=8,
        rr1=1.5, rr2=6.0, be_trig=0.8, lock_r=0.3, risk_cap=100.0,
        exigir_fvg=False, exigir_pivote=False, pivote_tol=8.0, pivote_lado=5,
        edad_max=999, modo_ob="disp", bos_disp_mult=0.0, bos_scan=10,
        breaker=False):
    """modo_ob: 'disp'  = solo desplazamiento (el usado todo el dia de hoy)
                'bos'   = solo ruptura de estructura confirmada (BOS)
                'union' = displacement O bos (mas zonas, mas variado)
                'ambos' = displacement Y bos coincidiendo en la misma vela"""
    O = [b[1] for b in bars]; H = [b[2] for b in bars]
    L = [b[3] for b in bars]; C = [b[4] for b in bars]; T = [b[0] for b in bars]
    n = len(bars)
    # Los tres detectores no dependen de los parametros de gestion (RR, BE,
    # lock, buffers) -- se cachean por (disp_mult,disp_frac,pivote_lado) para
    # no recalcular lo mismo miles de veces en un barrido de gestion.
    key = (disp_mult, disp_frac, pivote_lado if (exigir_pivote or modo_ob != "disp") else None,
           modo_ob, bos_disp_mult, bos_scan, exigir_pivote, id(bars))
    if key not in _CACHE:
        avg = _avg_range(H, L, n)
        ob_disp = detectar_ob(O, H, L, C, avg, disp_mult, disp_frac)
        ob_bos = (detectar_ob_bos(O, H, L, C, pivote_lado, bos_disp_mult, avg, bos_scan)
                  if modo_ob != "disp" else None)
        if modo_ob == "disp": ob = ob_disp
        elif modo_ob == "bos": ob = ob_bos
        elif modo_ob == "union":
            ob = [ob_disp[i] if ob_disp[i] is not None else ob_bos[i] for i in range(n)]
        else:  # ambos: solo cuenta si coinciden en la misma vela y direccion
            ob = [ob_disp[i] if (ob_disp[i] is not None and ob_bos[i] is not None
                                  and ob_disp[i][0] == ob_bos[i][0]) else None for i in range(n)]
        fvg = detectar_fvg(O, H, L, C)
        pivs = zonas_pivote(H, L, pivote_lado, max_edad=200) if exigir_pivote else None
        _CACHE[key] = (ob, fvg, pivs)
    ob, fvg, pivs = _CACHE[key]
    if not exigir_fvg: fvg = [None] * n

    nym = []
    for t in T:
        d = datetime.fromtimestamp(t, tz=timezone.utc).astimezone(NY)
        nym.append(d.hour * 60 + d.minute)

    vivas = []  # [dir, top, bot, nacida, cleared, tiene_fvg_cerca]
    breakers_pend = []  # OBs invalidados esperando confirmar barrido+cierre
    arm = None
    open_ = False; dir_ = 0; ep = sl = 0.0; risk = 0.0
    eIdx = 0; tp1 = False; moved = False
    trades = []

    for i in range(n):
        if ob[i] is not None:
            d0, top, bot = ob[i]
            vivas.append([d0, top, bot, i, False, False])
        if breaker:
            # BREAKER BLOCK: un OB alcista se invalida cuando el precio CIERRA
            # por debajo de su piso (no solo lo toca) -- la zona rota se
            # reutiliza como resistencia (zona bajista) desde esa misma vela.
            # Causal: la invalidacion se conoce al cerrar la vela i.
            nuevos_break = []
            for z in vivas:
                if z[4] or z[3] == i: continue  # solo zonas ya 'cleared' (tocadas)
                if z[0] == 1 and C[i] < z[2]:
                    nuevos_break.append([-1, z[2], z[1], i, False, False])
                elif z[0] == -1 and C[i] > z[1]:
                    nuevos_break.append([1, z[2], z[1], i, False, False])
            vivas.extend(nuevos_break)
        if exigir_fvg and fvg[i] is not None:
            # el FVG de la vela i solo se conoce AHORA (usa i, i-1, i-2).
            # se aplica hacia atras a zonas YA EXISTENTES que se solapen --
            # nunca hacia adelante, porque eso seria mirar el futuro.
            fd, f_top, f_bot = fvg[i]
            for z in vivas:
                if z[0] == fd and not (f_bot > z[1] or f_top < z[2]):
                    z[5] = True
        vivas = [z for z in vivas if (i - z[3]) <= edad_max]
        for z in vivas:
            if z[4] or z[3] == i: continue
            if z[0] == 1 and L[i] > z[1]: z[4] = True
            elif z[0] == -1 and H[i] < z[2]: z[4] = True

        inS = ses_ini <= nym[i] < ses_fin if ses_ini < ses_fin else (nym[i] >= ses_ini or nym[i] < ses_fin)

        if not open_ and inS:
            if arm is None:
                for z in vivas:
                    if not z[4] or z[3] == i: continue
                    if exigir_fvg and not z[5]: continue
                    if z[0] == 1 and z[2] - entry_buf <= L[i] <= z[1] + entry_buf:
                        ok_piv = True
                        if exigir_pivote:
                            ok_piv = any(t_ == -1 and abs(niv - z[2]) <= pivote_tol
                                         for niv, t_ in pivs[i])
                        if ok_piv:
                            arm = [1, z[1], z[2], i]; break
                    if z[0] == -1 and z[2] - entry_buf <= H[i] <= z[1] + entry_buf:
                        ok_piv = True
                        if exigir_pivote:
                            ok_piv = any(t_ == 1 and abs(niv - z[1]) <= pivote_tol
                                         for niv, t_ in pivs[i])
                        if ok_piv:
                            arm = [-1, z[1], z[2], i]; break
            elif i - arm[3] > espera:
                arm = None
            if arm is not None and i > arm[3]:
                cuerpo = abs(C[i] - O[i]); r_ = H[i] - L[i]
                if arm[0] == 1:
                    ok = C[i] > O[i] and r_ > 0 and cuerpo >= cuerpo_frac * r_ and C[i] > arm[1]
                    if ok:
                        _ep = C[i]; _sl = min(arm[2], L[i]) - sl_buf; _r = _ep - _sl
                        if 0 < _r <= risk_cap:
                            ep, sl, risk, open_, dir_, eIdx, tp1, moved = _ep, _sl, _r, True, 1, i, False, False
                            arm = None
                else:
                    ok = C[i] < O[i] and r_ > 0 and cuerpo >= cuerpo_frac * r_ and C[i] < arm[2]
                    if ok:
                        _ep = C[i]; _sl = max(arm[1], H[i]) + sl_buf; _r = _sl - _ep
                        if 0 < _r <= risk_cap:
                            ep, sl, risk, open_, dir_, eIdx, tp1, moved = _ep, _sl, _r, True, -1, i, False, False
                            arm = None
        if open_ and i > eIdx:
            t1 = ep + risk * rr1 * dir_; t2 = ep + risk * rr2 * dir_
            hitSL = (L[i] <= sl) if dir_ == 1 else (H[i] >= sl)
            if not tp1:
                hT1 = (H[i] >= t1) if dir_ == 1 else (L[i] <= t1)
                if hitSL:
                    trades.append((eIdx, risk, dir_, sl, ep)); open_ = False
                elif hT1:
                    tp1 = True; be = ep + risk * lock_r * dir_
                    if (not moved) or (be > sl if dir_ == 1 else be < sl): sl = be
                    moved = True
                elif not moved:
                    re = (H[i] - ep) / risk if dir_ == 1 else (ep - L[i]) / risk
                    if re >= be_trig: sl = ep + risk * lock_r * dir_; moved = True
            else:
                hT2 = (H[i] >= t2) if dir_ == 1 else (L[i] <= t2)
                if hitSL: trades.append((eIdx, risk, dir_, sl, ep)); open_ = False
                elif hT2: trades.append((eIdx, risk, dir_, t2, ep)); open_ = False
    return trades, T


def resumen(trades, T, qty=3):
    slip = TICK * SLIPPAGE_TICKS
    pnl = []
    for eIdx, risk, d, exitp, ep in trades:
        pnl.append(((exitp - ep) * d - slip) * PV * qty - COMMISSION_PER_CONTRACT_SIDE * qty * 2)
    if not pnl:
        return dict(trades=0, net=0, pf=0, dd=0, wr=0, times=[], pnl=[])
    g = sum(x for x in pnl if x > 0); l = -sum(x for x in pnl if x < 0)
    eq = pk = dd = 0.0
    for x in pnl:
        eq += x; pk = max(pk, eq); dd = max(dd, pk - eq)
    return dict(trades=len(pnl), net=sum(pnl), pf=(g / l if l else 0), dd=dd,
                wr=sum(1 for x in pnl if x > 0) / len(pnl), times=[T[t[0]] for t in trades], pnl=pnl)
