"""Prueba de las 3 hipotesis de liquidez del usuario, cada una POR SEPARADO
y luego combinadas, sobre la MISMA base ya tick-verificada (union+FVG, 08-13
NY, edad<=12) para no repetir el error del score compuesto (diluir señal).

Ejemplo real que motiva esto: entrada en zona con 2 OBs apilados, target
estirado hasta el 2do/3er nivel de liquidez + un gap de fin de semana
alineados por delante, RR logrado 3.26 en vez de un RR fijo.

Hipotesis:
  A) baseline          -- config ya validada, sin cambios (control)
  B) filtro apilamiento -- solo entrar si hay 2+ OBs de la misma direccion
                            solapados/adyacentes en la zona
  C) RR dinamico        -- en vez de RR fijo, extender el target al 2do/3er
                            nivel de liquidez (pivote o GAP) alineado por
                            delante, si hay varios apilados
  D) B + C combinados

Datos: SOLO ticks_15m_sep_dic_2025.json (derivado de tick real, no bar
sintetico), igual que toda la verificacion de esta linea.
"""
import json
import motor_confluencia as M
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")

CFG = dict(
    ses_ini=480, ses_fin=780,           # 08:00-13:00 NY
    disp_mult=1.5, disp_frac=0.6,
    entry_buf=12.0, sl_buf=2.0,
    cuerpo_frac=0.4, espera=8,
    rr1=1.5, rr2=4.0, be_trig=0.4, lock_r=0.2,
    exigir_fvg=True, edad_max=12,
    modo_ob="union", bos_disp_mult=0, bos_scan=10, pivote_lado=2,
)


def cargar_bars():
    d = json.load(open("ticks_15m_sep_dic_2025.json"))
    return d["bars"] if isinstance(d, dict) else d


def detectar_gaps(T, O, C, min_gap_pts=5.0, min_salto_seg=3 * 900):
    """Gap de sesion/fin de semana: hueco de tiempo (barras faltantes) +
    hueco de precio real entre el cierre anterior y la apertura siguiente.
    Se mantiene como zona 'objetivo' activa hasta que el precio la rellena
    por completo (low<=lo y high>=hi en alguna vela posterior)."""
    n = len(T)
    gaps = []  # [lo, hi, dir(1=alcista/abajo hacia arriba), nacido_en, rellenado(bool)]
    for i in range(1, n):
        if T[i] - T[i - 1] <= min_salto_seg:
            continue
        if abs(O[i] - C[i - 1]) < min_gap_pts:
            continue
        lo, hi = sorted((O[i], C[i - 1]))
        dir_ = 1 if O[i] > C[i - 1] else -1
        gaps.append([lo, hi, dir_, i, False])
    return gaps


def _niveles_pivote_activos(pivs, i):
    return pivs[i] if pivs and i < len(pivs) else []


def _apilamiento(ob, i, d0, top, bot, ventana=20, tol=None):
    """Cuenta OBs de la MISMA direccion nacidos en las ultimas `ventana`
    velas cuyo rango se solapa o queda a menos de `tol` puntos de este."""
    alto = max(top - bot, 0.01)
    if tol is None:
        tol = alto * 0.5
    cnt = 0
    for j in range(max(0, i - ventana), i):
        if ob[j] is None:
            continue
        dj, tj, bj = ob[j]
        if dj != d0:
            continue
        solapa = not (bj - tol > top or tj + tol < bot)
        if solapa:
            cnt += 1
    return cnt


def simular(bars, filtro_apilamiento=False, rr_dinamico=False,
            min_apilamiento=1, niveles_objetivo=2, rr_max=8.0, rr_min=1.5):
    O = [b[1] for b in bars]; H = [b[2] for b in bars]
    L = [b[3] for b in bars]; C = [b[4] for b in bars]; T = [b[0] for b in bars]
    n = len(bars)
    cfg = CFG
    avg = M._avg_range(H, L, n)
    ob_disp = M.detectar_ob(O, H, L, C, avg, cfg["disp_mult"], cfg["disp_frac"])
    ob_bos = M.detectar_ob_bos(O, H, L, C, cfg["pivote_lado"], cfg["bos_disp_mult"], avg, cfg["bos_scan"])
    ob = [ob_disp[i] if ob_disp[i] is not None else ob_bos[i] for i in range(n)]
    fvg = M.detectar_fvg(O, H, L, C)
    pivs = M.zonas_pivote(H, L, cfg["pivote_lado"], max_edad=200)
    gaps = detectar_gaps(T, O, C)

    nym = []
    for t in T:
        d = datetime.fromtimestamp(t, tz=timezone.utc).astimezone(NY)
        nym.append(d.hour * 60 + d.minute)

    vivas = []  # [dir, top, bot, nacida, cleared, tiene_fvg_cerca, apilamiento]
    arm = None
    open_ = False; dir_ = 0; ep = sl = risk = 0.0
    eIdx = 0; tp1 = False; moved = False; target2 = None
    trades = []
    metas = []  # (eIdx, rr2_efectivo) -- para poder reconstruir el target real usado en verificacion tick

    for i in range(n):
        # actualizar relleno de gaps (causal: se conoce al cerrar la vela i)
        for g in gaps:
            if not g[4] and g[3] < i and L[i] <= g[0] and H[i] >= g[1]:
                g[4] = True

        if ob[i] is not None:
            d0, top, bot = ob[i]
            apilado = _apilamiento(ob, i, d0, top, bot)
            vivas.append([d0, top, bot, i, False, False, apilado])

        if fvg[i] is not None:
            fd, f_top, f_bot = fvg[i]
            for z in vivas:
                if z[0] == fd and not (f_bot > z[1] or f_top < z[2]):
                    z[5] = True

        vivas = [z for z in vivas if (i - z[3]) <= cfg["edad_max"]]
        for z in vivas:
            if z[4] or z[3] == i:
                continue
            if z[0] == 1 and L[i] > z[1]:
                z[4] = True
            elif z[0] == -1 and H[i] < z[2]:
                z[4] = True

        ses_ini, ses_fin = cfg["ses_ini"], cfg["ses_fin"]
        inS = ses_ini <= nym[i] < ses_fin if ses_ini < ses_fin else (nym[i] >= ses_ini or nym[i] < ses_fin)

        if not open_ and inS:
            if arm is None:
                for z in vivas:
                    if not z[4] or z[3] == i:
                        continue
                    if not z[5]:
                        continue  # exigir FVG, igual que la linea base
                    if filtro_apilamiento and z[6] < min_apilamiento:
                        continue
                    if z[0] == 1 and z[2] - cfg["entry_buf"] <= L[i] <= z[1] + cfg["entry_buf"]:
                        arm = [1, z[1], z[2], i]; break
                    if z[0] == -1 and z[2] - cfg["entry_buf"] <= H[i] <= z[1] + cfg["entry_buf"]:
                        arm = [-1, z[1], z[2], i]; break
            elif i - arm[3] > cfg["espera"]:
                arm = None
            if arm is not None and i > arm[3]:
                cuerpo = abs(C[i] - O[i]); r_ = H[i] - L[i]
                if arm[0] == 1:
                    ok = C[i] > O[i] and r_ > 0 and cuerpo >= cfg["cuerpo_frac"] * r_ and C[i] > arm[1]
                    if ok:
                        _ep = C[i]; _sl = min(arm[2], L[i]) - cfg["sl_buf"]; _r = _ep - _sl
                        if 0 < _r <= 100.0:
                            ep, sl, risk, open_, dir_, eIdx, tp1, moved = _ep, _sl, _r, True, 1, i, False, False
                            target2 = None
                            if rr_dinamico:
                                target2 = _target_apilado(1, ep, risk, pivs[i], gaps, i,
                                                           niveles_objetivo, rr_min, rr_max)
                            metas.append((i, target2 if target2 is not None else cfg["rr2"]))
                            arm = None
                else:
                    ok = C[i] < O[i] and r_ > 0 and cuerpo >= cfg["cuerpo_frac"] * r_ and C[i] < arm[2]
                    if ok:
                        _ep = C[i]; _sl = max(arm[1], H[i]) + cfg["sl_buf"]; _r = _sl - _ep
                        if 0 < _r <= 100.0:
                            ep, sl, risk, open_, dir_, eIdx, tp1, moved = _ep, _sl, _r, True, -1, i, False, False
                            target2 = None
                            if rr_dinamico:
                                target2 = _target_apilado(-1, ep, risk, pivs[i], gaps, i,
                                                           niveles_objetivo, rr_min, rr_max)
                            metas.append((i, target2 if target2 is not None else cfg["rr2"]))
                            arm = None

        if open_ and i > eIdx:
            rr2_efectivo = target2 if target2 is not None else cfg["rr2"]
            t1 = ep + risk * cfg["rr1"] * dir_
            t2 = ep + risk * rr2_efectivo * dir_
            hitSL = (L[i] <= sl) if dir_ == 1 else (H[i] >= sl)
            if not tp1:
                hT1 = (H[i] >= t1) if dir_ == 1 else (L[i] <= t1)
                if hitSL:
                    trades.append((eIdx, risk, dir_, sl, ep)); open_ = False
                elif hT1:
                    tp1 = True; be = ep + risk * cfg["lock_r"] * dir_
                    if (not moved) or (be > sl if dir_ == 1 else be < sl): sl = be
                    moved = True
                elif not moved:
                    re = (H[i] - ep) / risk if dir_ == 1 else (ep - L[i]) / risk
                    if re >= cfg["be_trig"]: sl = ep + risk * cfg["lock_r"] * dir_; moved = True
            else:
                hT2 = (H[i] >= t2) if dir_ == 1 else (L[i] <= t2)
                if hitSL: trades.append((eIdx, risk, dir_, sl, ep)); open_ = False
                elif hT2: trades.append((eIdx, risk, dir_, t2, ep)); open_ = False
    return trades, T, metas


def _target_apilado(dir_, ep, risk, pivs_i, gaps, i, niveles_objetivo, rr_min, rr_max):
    """Junta niveles de pivote (ya confirmados, causales) y gaps sin rellenar
    que quedan por DELANTE de la entrada en la direccion del trade, ordena
    por distancia y devuelve el RR del nivel N-esimo si hay al menos
    `niveles_objetivo` apilados dentro de [rr_min, rr_max]*risk. Si no hay
    suficientes niveles alineados, devuelve None (usa el RR fijo)."""
    candidatos = []
    for niv, tipo in pivs_i:
        if dir_ == 1 and tipo == 1 and niv > ep:
            candidatos.append(niv)
        elif dir_ == -1 and tipo == -1 and niv < ep:
            candidatos.append(niv)
    for g in gaps:
        if g[4] or g[3] >= i:
            continue
        borde = g[1] if dir_ == 1 else g[0]  # borde lejano del gap en la direccion del trade
        if dir_ == 1 and borde > ep:
            candidatos.append(borde)
        elif dir_ == -1 and borde < ep:
            candidatos.append(borde)
    if dir_ == 1:
        candidatos = sorted(set(round(c, 2) for c in candidatos))
    else:
        candidatos = sorted(set(round(c, 2) for c in candidatos), reverse=True)
    rrs = [(c - ep) / risk * dir_ for c in candidatos]
    rrs = [r for r in rrs if rr_min <= r <= rr_max]
    if len(rrs) < niveles_objetivo:
        return None
    return rrs[niveles_objetivo - 1]


def reportar(nombre, trades, T):
    r = M.resumen(trades, T)
    print(f"{nombre:28s} ops={r['trades']:4d}  net=${r['net']:9.2f}  "
          f"PF={r['pf']:.2f}  DD=${r['dd']:8.2f}  WR={r['wr']*100:5.1f}%")
    return r


if __name__ == "__main__":
    import sys
    bars = cargar_bars()
    print(f"Barras 15m cargadas: {len(bars)}  ({len(bars)} velas, "
          f"tick-derivadas sep-dic 2025)\n")

    trA, TA, _ = simular(bars, filtro_apilamiento=False, rr_dinamico=False)
    reportar("A) baseline (control)", trA, TA)

    trB, TB, _ = simular(bars, filtro_apilamiento=True, rr_dinamico=False, min_apilamiento=1)
    reportar("B) filtro apilamiento>=1", trB, TB)

    trB2, TB2, _ = simular(bars, filtro_apilamiento=True, rr_dinamico=False, min_apilamiento=2)
    reportar("B) filtro apilamiento>=2", trB2, TB2)

    trC, TC, metaC = simular(bars, filtro_apilamiento=False, rr_dinamico=True, niveles_objetivo=2)
    reportar("C) RR dinamico (nivel 2)", trC, TC)

    trC3, TC3, _ = simular(bars, filtro_apilamiento=False, rr_dinamico=True, niveles_objetivo=3)
    reportar("C) RR dinamico (nivel 3)", trC3, TC3)

    trD, TD, _ = simular(bars, filtro_apilamiento=True, rr_dinamico=True,
                          min_apilamiento=1, niveles_objetivo=2)
    reportar("D) apilamiento+RR dinamico", trD, TD)

    if "--export-c" in sys.argv:
        import datetime as dt
        meta_by_eidx = dict(metaC)
        print("\n# TRADES para verificar_rr_dinamico.py (variante C, nivel 2)")
        for eIdx, risk, d, exitp, ep in trC:
            t_entry = TC[eIdx]
            s = dt.datetime.fromtimestamp(t_entry, tz=dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            rr_usado = meta_by_eidx.get(eIdx, CFG["rr2"])
            print(f'    ("{s}", {d}, {ep}, {risk}, {exitp}, {rr_usado}),')
