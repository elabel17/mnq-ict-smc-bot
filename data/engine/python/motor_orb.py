"""Ruptura del rango de apertura (ORB) — motor CAUSAL.

El rango se define con una ventana horaria que YA CERRO. Sus maximos y minimos
son niveles fijos, conocidos antes de operar. La entrada es una orden stop en
ese nivel, o el cierre de la vela que rompe. No hay ningun punto donde se
escoja un precio mirando hasta donde llego la vela.

Parametros:
  ini_min/fin_min : ventana del rango, en minutos desde medianoche NY
  hasta_min       : hora limite para abrir posicion
  cierre_min      : hora a la que se cierra cualquier posicion abierta
  modo_entrada    : 'stop'  = orden stop en el borde del rango (se llena al tocar)
                    'cierre'= entra al cierre de la primera vela que cierra fuera
  buffer_pts      : cuanto por fuera del borde se coloca el nivel
  stop_modo       : 'lado_opuesto' = stop en el otro extremo del rango
                    'fijo'         = stop_pts puntos desde la entrada
                    'mitad'        = stop en la mitad del rango
  rr              : objetivo en multiplos del riesgo (0 = solo cierre por hora)
  be_trig/lock_r  : proteccion anticipada (lock_r DEBE ser menor que be_trig)
  min_rango/max_rango : filtros de tamano del rango en puntos
  una_por_dia     : si True, un solo intento por dia (evita perseguir)
"""
import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
NY = ZoneInfo("America/New_York")
TICK, PV = 0.25, 2.0
SLIPPAGE_TICKS = 2
COMMISSION_PER_CONTRACT_SIDE = 1.00


def load(fn="../../python/claude_ohlcv_5m_2024_2026.json"):
    d = json.load(open(fn))
    return d["bars"] if isinstance(d, dict) else d


def run(bars, ini_min=570, fin_min=600, hasta_min=780, cierre_min=955,
        modo_entrada="stop", buffer_pts=1.0, stop_modo="lado_opuesto",
        stop_pts=20.0, rr=2.0, be_trig=0.0, lock_r=0.0,
        min_rango=0.0, max_rango=1e9, risk_cap=120.0, una_por_dia=True,
        mismo_bar_stop=True):
    O = [b[1] for b in bars]; H = [b[2] for b in bars]
    L = [b[3] for b in bars]; C = [b[4] for b in bars]; T = [b[0] for b in bars]
    n = len(bars)
    dia = []; nym = []
    for t in T:
        d = datetime.fromtimestamp(t, tz=timezone.utc).astimezone(NY)
        dia.append(d.date()); nym.append(d.hour * 60 + d.minute)

    trades = []
    i = 0
    while i < n:
        d0 = dia[i]
        j = i
        while j < n and dia[j] == d0:
            j += 1
        # ---- rango de la ventana de apertura (ya cerrada) ----
        rh = rl = None
        for k in range(i, j):
            if ini_min <= nym[k] < fin_min:
                rh = H[k] if rh is None else max(rh, H[k])
                rl = L[k] if rl is None else min(rl, L[k])
        if rh is None or rl is None:
            i = j; continue
        ancho = rh - rl
        if not (min_rango <= ancho <= max_rango):
            i = j; continue

        arriba = rh + buffer_pts
        abajo = rl - buffer_pts
        abierto = False; dir_ = 0; ep = sl = tp = 0.0
        risk = 0.0; moved = False; eIdx = 0; intentos = 0
        # Una orden stop solo se puede llenar la PRIMERA vez que el precio cruza
        # el nivel. Despues el nivel ya quedo atras: seguir entrando ahi seria
        # cobrar un precio que el mercado ya dejo de ofrecer.
        cruzado_arr = cruzado_aba = False

        for k in range(i, j):
            if nym[k] < fin_min:
                continue
            if not abierto and nym[k] < hasta_min and (intentos == 0 or not una_por_dia):
                lado = 0
                if modo_entrada == "stop":
                    # la orden stop descansa en el nivel: se llena al tocarlo,
                    # y solo la primera vez
                    if H[k] >= arriba and not cruzado_arr: lado, px = 1, arriba
                    elif L[k] <= abajo and not cruzado_aba: lado, px = -1, abajo
                else:
                    if C[k] > arriba and not cruzado_arr: lado, px = 1, C[k]
                    elif C[k] < abajo and not cruzado_aba: lado, px = -1, C[k]
                if lado != 0:
                    if stop_modo == "lado_opuesto":
                        _sl = (rl - buffer_pts) if lado == 1 else (rh + buffer_pts)
                    elif stop_modo == "mitad":
                        _sl = (rh + rl) / 2.0
                    else:
                        _sl = px - stop_pts * lado
                    _r = abs(px - _sl)
                    if 0 < _r <= risk_cap:
                        abierto = True; dir_ = lado; ep = px; sl = _sl
                        risk = _r; moved = False; eIdx = k; intentos += 1
                        tp = ep + risk * rr * dir_ if rr > 0 else None
                        # MISMA VELA: la ruptura puede darse la vuelta y tocar el
                        # stop antes de que cierre. Saltarselo es optimista.
                        if mismo_bar_stop:
                            golpe = (L[k] <= _sl) if lado == 1 else (H[k] >= _sl)
                            if golpe:
                                trades.append((k, _r, lado, _sl, px)); abierto = False
                        continue
            # el nivel se marca como cruzado en cuanto el precio lo alcanza,
            # haya entrada o no
            if H[k] >= arriba: cruzado_arr = True
            if L[k] <= abajo: cruzado_aba = True

            if abierto:
                hitSL = (L[k] <= sl) if dir_ == 1 else (H[k] >= sl)
                hitTP = tp is not None and ((H[k] >= tp) if dir_ == 1 else (L[k] <= tp))
                if hitSL:
                    trades.append((eIdx, risk, dir_, sl, ep)); abierto = False
                elif hitTP:
                    trades.append((eIdx, risk, dir_, tp, ep)); abierto = False
                elif nym[k] >= cierre_min:
                    trades.append((eIdx, risk, dir_, C[k], ep)); abierto = False
                elif be_trig > 0 and not moved:
                    re = (H[k] - ep) / risk if dir_ == 1 else (ep - L[k]) / risk
                    if re >= be_trig:
                        sl = ep + risk * lock_r * dir_; moved = True
        if abierto:
            trades.append((eIdx, risk, dir_, C[j - 1], ep))
        i = j
    return trades, T


def resumen(trades, T, qty=3):
    slip = TICK * SLIPPAGE_TICKS
    pnl = []
    for eIdx, risk, d, exitp, ep in trades:
        pnl.append(((exitp - ep) * d - slip) * PV * qty
                   - COMMISSION_PER_CONTRACT_SIDE * qty * 2)
    if not pnl:
        return dict(trades=0, net=0, pf=0, dd=0, wr=0, times=[], pnl=[])
    g = sum(x for x in pnl if x > 0); l = -sum(x for x in pnl if x < 0)
    eq = pk = dd = 0.0
    for x in pnl:
        eq += x; pk = max(pk, eq); dd = max(dd, pk - eq)
    return dict(trades=len(pnl), net=sum(pnl), pf=(g / l if l else 0), dd=dd,
                wr=sum(1 for x in pnl if x > 0) / len(pnl),
                times=[T[t[0]] for t in trades], pnl=pnl)
