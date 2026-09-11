"""Multi-marco CAUSAL: zonas detectadas en 15m, confirmacion y ejecucion en 5m.

Reglas de causalidad, todas comprobadas:
  - una zona de 15m solo existe DESPUES de que su vela de 15m haya cerrado
  - el toque ARMA la zona; no entra
  - se entra al CIERRE de una vela de 5m de reaccion posterior al toque
  - el stop se fija con datos ya conocidos en ese momento
No hay ningun punto donde se escoja un precio mirando hasta donde llego la vela.
"""
import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
NY = ZoneInfo("America/New_York")
TICK, PV = 0.25, 2.0
SLIPPAGE_TICKS = 2
COMMISSION_PER_CONTRACT_SIDE = 1.00


def load5(fn="../../python/claude_ohlcv_5m_2024_2026.json"):
    d = json.load(open(fn))
    return d["bars"] if isinstance(d, dict) else d


def agrupa(bars5, mins=15):
    """15m a partir de 5m. Devuelve (barras15, idx de la ultima vela 5m de cada 15m)."""
    seg = mins * 60
    g = {}
    for i, b in enumerate(bars5):
        k = b[0] - (b[0] % seg)
        g.setdefault(k, []).append(i)
    out = []
    cierre = []
    for k in sorted(g):
        idxs = g[k]
        o = bars5[idxs[0]][1]
        h = max(bars5[j][2] for j in idxs)
        l = min(bars5[j][3] for j in idxs)
        c = bars5[idxs[-1]][4]
        out.append([k, o, h, l, c])
        cierre.append(idxs[-1])
    return out, cierre


def zonas15(b15, disp_mult=2.5, disp_frac=0.6, ob_scan=10, liq_win=12,
            liq_tol=4.0, liq_accum=6):
    """Por cada indice de 15m, la zona nacida ahi (dir, top, bot) o None."""
    n = len(b15)
    O = [x[1] for x in b15]; H = [x[2] for x in b15]
    L = [x[3] for x in b15]; C = [x[4] for x in b15]
    avg = [None] * n
    s = 0.0
    for i in range(n):
        s += H[i] - L[i]
        if i >= 20:
            s -= H[i - 20] - L[i - 20]
        avg[i] = s / 20 if i >= 19 else None
    res = [None] * n
    for i in range(25, n):
        rng = H[i] - L[i]
        if avg[i - 1] is None or rng < disp_mult * avg[i - 1]:
            continue
        if C[i] > O[i] and (C[i] - L[i]) >= disp_frac * rng:
            idx = -1
            for k in range(1, ob_scan + 1):
                if C[i - k] < O[i - k]:
                    idx = k
                    break
            if idx > 0:
                cand = L[i - idx]
                mx = cu = 0
                for j in range(idx + 1, idx + liq_win + 1):
                    if i - j < 0:
                        break
                    if L[i - j] <= cand + liq_tol:
                        cu += 1
                        mx = max(mx, cu)
                    else:
                        cu = 0
                if mx < liq_accum:
                    res[i] = (1, H[i - idx], cand)
        elif C[i] < O[i] and (H[i] - C[i]) >= disp_frac * rng:
            idx = -1
            for k in range(1, ob_scan + 1):
                if C[i - k] > O[i - k]:
                    idx = k
                    break
            if idx > 0:
                cand = H[i - idx]
                mx = cu = 0
                for j in range(idx + 1, idx + liq_win + 1):
                    if i - j < 0:
                        break
                    if H[i - j] >= cand - liq_tol:
                        cu += 1
                        mx = max(mx, cu)
                    else:
                        cu = 0
                if mx < liq_accum:
                    res[i] = (-1, cand, L[i - idx])
    return res


def run(bars5, b15, cierre15, znas, entry_buf=12.0, sl_buf=2.0, risk_cap=100,
        cuerpo_frac=0.5, espera=8, exigir_cierre_fuera=True, edad_max=40,
        rr1=1.5, rr2=6.0, be_trig=1.0, lock_r=0.5,
        ses_ini=1080, ses_fin=660):
    n5 = len(bars5)
    O = [b[1] for b in bars5]; H = [b[2] for b in bars5]
    L = [b[3] for b in bars5]; C = [b[4] for b in bars5]; T = [b[0] for b in bars5]
    nym = []
    for t in T:
        d = datetime.fromtimestamp(t, tz=timezone.utc).astimezone(NY)
        nym.append(d.hour * 60 + d.minute)

    # una zona de 15m solo existe desde la vela de 5m SIGUIENTE a su cierre
    nace = {}
    for i15, z in enumerate(znas):
        if z is not None:
            nace.setdefault(cierre15[i15] + 1, []).append(z)

    vivas = []   # [dir, top, bot, nacida5, cleared]
    arm = None   # [dir, top, bot, vela_del_toque]
    open_ = False; dir_ = 0; ep = sl = 0.0; risk = 0.0
    eIdx = 0; tp1 = False; moved = False
    trades = []

    for i in range(n5):
        for z in nace.get(i, []):
            vivas.append([z[0], z[1], z[2], i, False])
        vivas = [z for z in vivas if (i - z[3]) <= edad_max]
        for z in vivas:
            if z[4] or z[3] == i:
                continue
            if z[0] == 1 and L[i] > z[1]:
                z[4] = True
            elif z[0] == -1 and H[i] < z[2]:
                z[4] = True

        inS = (nym[i] >= ses_ini) or (nym[i] < ses_fin)

        if not open_ and inS:
            if arm is None:
                for z in vivas:
                    if not z[4] or z[3] == i:
                        continue
                    if z[0] == 1 and z[2] - entry_buf <= L[i] <= z[1] + entry_buf:
                        arm = [1, z[1], z[2], i]
                        break
                    if z[0] == -1 and z[2] - entry_buf <= H[i] <= z[1] + entry_buf:
                        arm = [-1, z[1], z[2], i]
                        break
            elif i - arm[3] > espera:
                arm = None
            if arm is not None and i > arm[3]:
                cuerpo = abs(C[i] - O[i]); r_ = H[i] - L[i]
                if arm[0] == 1:
                    ok = C[i] > O[i] and r_ > 0 and cuerpo >= cuerpo_frac * r_
                    if ok and exigir_cierre_fuera:
                        ok = C[i] > arm[1]
                    if ok:
                        _ep = C[i]; _sl = min(arm[2], L[i]) - sl_buf; _r = _ep - _sl
                        if 0 < _r <= risk_cap:
                            ep, sl, risk, open_, dir_, eIdx, tp1, moved = _ep, _sl, _r, True, 1, i, False, False
                            arm = None
                else:
                    ok = C[i] < O[i] and r_ > 0 and cuerpo >= cuerpo_frac * r_
                    if ok and exigir_cierre_fuera:
                        ok = C[i] < arm[2]
                    if ok:
                        _ep = C[i]; _sl = max(arm[1], H[i]) + sl_buf; _r = _sl - _ep
                        if 0 < _r <= risk_cap:
                            ep, sl, risk, open_, dir_, eIdx, tp1, moved = _ep, _sl, _r, True, -1, i, False, False
                            arm = None

        if open_ and i > eIdx:
            t1 = ep + risk * rr1 * dir_
            t2 = ep + risk * rr2 * dir_
            hitSL = (L[i] <= sl) if dir_ == 1 else (H[i] >= sl)
            if not tp1:
                hT1 = (H[i] >= t1) if dir_ == 1 else (L[i] <= t1)
                if hitSL:
                    trades.append((eIdx, risk, dir_, sl, ep)); open_ = False
                elif hT1:
                    tp1 = True
                    be = ep + risk * lock_r * dir_
                    if (not moved) or (be > sl if dir_ == 1 else be < sl):
                        sl = be
                    moved = True
                elif not moved:
                    re = (H[i] - ep) / risk if dir_ == 1 else (ep - L[i]) / risk
                    if re >= be_trig:
                        sl = ep + risk * lock_r * dir_
                        moved = True
            else:
                hT2 = (H[i] >= t2) if dir_ == 1 else (L[i] <= t2)
                if hitSL:
                    trades.append((eIdx, risk, dir_, sl, ep)); open_ = False
                elif hT2:
                    trades.append((eIdx, risk, dir_, t2, ep)); open_ = False
    return trades, T


def resumen(trades, T, qty=3):
    slip = TICK * SLIPPAGE_TICKS
    pnl = []
    for eIdx, risk, d, exitp, ep in trades:
        pnl.append(((exitp - ep) * d - slip) * PV * qty
                   - COMMISSION_PER_CONTRACT_SIDE * qty * 2)
    if not pnl:
        return dict(trades=0, net=0, pf=0, dd=0, wr=0, times=[], pnl=[])
    g = sum(x for x in pnl if x > 0)
    l = -sum(x for x in pnl if x < 0)
    eq = pk = dd = 0.0
    for x in pnl:
        eq += x
        pk = max(pk, eq)
        dd = max(dd, pk - eq)
    return dict(trades=len(pnl), net=sum(pnl), pf=(g / l if l else 0), dd=dd,
                wr=sum(1 for x in pnl if x > 0) / len(pnl),
                times=[T[t[0]] for t in trades], pnl=pnl)
