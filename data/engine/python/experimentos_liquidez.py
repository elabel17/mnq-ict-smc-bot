"""Motor de EXPERIMENTOS configurable -- corre varias hipotesis de liquidez
en un solo lugar y vuelca TODAS las operaciones a un unico CSV con una
columna `variante`, para filtrar/pivotear en Excel/Sheets sin pedir un
script nuevo cada vez.

Hipotesis que soporta (todas independientes, combinables por config):
  edad_max        None = SIN limite de tiempo (solo importa no estar tocada)
                  N    = igual que antes, expira a N velas de nacida
  min_apilamiento 0 = off. N = exigir N+ OBs de la misma direccion
                  solapados/adyacentes nacidos en las ultimas 20 velas
  liquidez_modo   'off'            -- no se evalua
                  'excluir_peligro'-- descarta si hay liquidez de invalidacion
                                      cerca (igual a liqEnPeligro del Pine)
                  'solo_favor'     -- exige liquidez a favor cerca (iman)
  rr_modo         'fijo'      -- RR2 constante (parametro rr2)
                  'dinamico'  -- estira al nivel N-esimo de liquidez+gap
                                 apilado por delante (niveles_objetivo)

Cada operacion se guarda con: edad al tocar la zona, apilamiento, score de
liquidez, si tenia FVG, RR objetivo usado y el resultado -- para que se
pueda evaluar CUALQUIER combinacion de columnas despues, sin re-correr nada.
"""
import csv
import json
import datetime as dt
from datetime import timezone
from zoneinfo import ZoneInfo

import motor_confluencia as M
from liquidez_apilada import detectar_gaps, _apilamiento, _target_apilado


def _target_cadena(dir_, ep, risk, cur_hi, cur_lo, max_gap_mult=3.0, rr_max=10.0, min_niveles=2):
    """Apunta al nivel MAS LEJANO dentro de una cadena de liquidez consecutiva:
    parte de la entrada y va sumando niveles (de los mismos pivotes vivos que
    ya validan la entrada, no pivotes sueltos inventados) mientras el salto
    entre uno y el siguiente sea 'razonable' (<= max_gap_mult x riesgo). En
    cuanto aparece un salto grande, la cadena se corta ahi -- no se aspira a
    liquidez aislada y lejana. El objetivo final ademas se topa en rr_max
    (nunca 'mil pips', por mas alineados que esten los niveles)."""
    candidatos = sorted(v for v in (cur_hi if dir_ == 1 else cur_lo) if (v > ep if dir_ == 1 else v < ep))
    if dir_ == -1:
        candidatos = sorted(candidatos, reverse=True)
    cadena = []
    anterior = ep
    for niv in candidatos:
        if abs(niv - anterior) > max_gap_mult * risk:
            break
        cadena.append(niv)
        anterior = niv
    if len(cadena) < min_niveles:
        return None
    rr = abs(cadena[-1] - ep) / risk
    return min(rr, rr_max)

NY = ZoneInfo("America/New_York")

BASE_CFG = dict(
    ses_ini=480, ses_fin=780,           # 08:00-13:00 NY (poner 0,1440 para 24h)
    disp_mult=1.5, disp_frac=0.6,
    entry_buf=12.0, sl_buf=2.0,
    cuerpo_frac=0.4, espera=8,
    rr1=1.5, rr2=4.0, be_trig=0.4, lock_r=0.2,
    pivote_lado=2, bos_disp_mult=0, bos_scan=10,
    dist_mult_liq=3.0,
)


def cargar_bars(fn="ticks_15m_sep_dic_2025.json"):
    d = json.load(open(fn))
    return d["bars"] if isinstance(d, dict) else d


def simular(bars, variante, edad_max=12, exigir_fvg=True, min_apilamiento=0,
            liquidez_modo="off", rr_modo="fijo", niveles_objetivo=2,
            rr_min=1.5, rr_max=8.0, cadena_max_gap_mult=3.0, cadena_min_niveles=2,
            ses_ini=None, ses_fin=None, ses_ventanas=None, cfg=None):
    """ses_ventanas: lista opcional de (ini_min, fin_min) NY -- permite varias
    franjas horarias disjuntas (ej. manana + noche). Si se pasa, tiene
    prioridad sobre ses_ini/ses_fin (que siguen soportando la unica ventana
    con wraparound de medianoche)."""
    cfg = dict(cfg or BASE_CFG)
    if ses_ini is not None: cfg["ses_ini"] = ses_ini
    if ses_fin is not None: cfg["ses_fin"] = ses_fin

    O = [b[1] for b in bars]; H = [b[2] for b in bars]
    L = [b[3] for b in bars]; C = [b[4] for b in bars]; T = [b[0] for b in bars]
    n = len(bars)
    avg = M._avg_range(H, L, n)
    ob_disp = M.detectar_ob(O, H, L, C, avg, cfg["disp_mult"], cfg["disp_frac"])
    ob_bos = M.detectar_ob_bos(O, H, L, C, cfg["pivote_lado"], cfg["bos_disp_mult"], avg, cfg["bos_scan"])
    ob = [ob_disp[i] if ob_disp[i] is not None else ob_bos[i] for i in range(n)]
    fvg = M.detectar_fvg(O, H, L, C)
    pivs = M.zonas_pivote(H, L, cfg["pivote_lado"], max_edad=200)
    gaps = detectar_gaps(T, O, C)

    # pivotes vivos (causales) para el gate de liquidez favor/peligro
    piv_hi, piv_lo, conf = M.detectar_pivotes(H, L, cfg["pivote_lado"])
    activar_hi = {}; activar_lo = {}
    for i in range(n):
        if piv_hi[i] is not None: activar_hi.setdefault(conf[i], []).append(piv_hi[i])
        if piv_lo[i] is not None: activar_lo.setdefault(conf[i], []).append(piv_lo[i])
    cur_hi, cur_lo = [], []

    nym = []
    for t in T:
        d = dt.datetime.fromtimestamp(t, tz=timezone.utc).astimezone(NY)
        nym.append(d.hour * 60 + d.minute)

    vivas = []  # [dir, top, bot, nacida, tocada, tiene_fvg, apilamiento]
    arm = None
    open_ = False; dir_ = 0; ep = sl = risk = 0.0
    eIdx = 0; tp1 = False; moved = False; target2 = None
    meta_actual = None
    filas = []

    for i in range(n):
        cur_hi.extend(activar_hi.get(i, [])); cur_lo.extend(activar_lo.get(i, []))
        cur_hi[:] = [v for v in cur_hi if not (H[i] > v + 1.0 and C[i] < v)]
        cur_lo[:] = [v for v in cur_lo if not (L[i] < v - 1.0 and C[i] > v)]

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

        if edad_max is not None:
            vivas = [z for z in vivas if (i - z[3]) <= edad_max]
        for z in vivas:
            if z[4] or z[3] == i: continue
            if z[0] == 1 and L[i] > z[1]: z[4] = True
            elif z[0] == -1 and H[i] < z[2]: z[4] = True

        if ses_ventanas is not None:
            inS = any(ini <= nym[i] < fin for ini, fin in ses_ventanas)
        else:
            ses_ini_, ses_fin_ = cfg["ses_ini"], cfg["ses_fin"]
            inS = ses_ini_ <= nym[i] < ses_fin_ if ses_ini_ < ses_fin_ else (nym[i] >= ses_ini_ or nym[i] < ses_fin_)

        if not open_ and inS:
            if arm is None:
                for z in vivas:
                    if not z[4] or z[3] == i: continue
                    if exigir_fvg and not z[5]: continue
                    if min_apilamiento and z[6] < min_apilamiento: continue
                    if liquidez_modo != "off":
                        liqS = M._liq_favor_peligro(z[0], z[1], z[2], cur_hi, cur_lo, cfg["dist_mult_liq"])
                        if liquidez_modo == "excluir_peligro" and liqS == 0.0: continue
                        if liquidez_modo == "solo_favor" and liqS != 100.0: continue
                    else:
                        liqS = None
                    tocado_en = i
                    if z[0] == 1 and z[2] - cfg["entry_buf"] <= L[i] <= z[1] + cfg["entry_buf"]:
                        arm = [1, z[1], z[2], i]
                        meta_actual = dict(nacida=z[3], edad_toque=i - z[3], apilamiento=z[6],
                                            liq=liqS, fvg=z[5])
                        break
                    if z[0] == -1 and z[2] - cfg["entry_buf"] <= H[i] <= z[1] + cfg["entry_buf"]:
                        arm = [-1, z[1], z[2], i]
                        meta_actual = dict(nacida=z[3], edad_toque=i - z[3], apilamiento=z[6],
                                            liq=liqS, fvg=z[5])
                        break
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
                            if rr_modo == "dinamico":
                                target2 = _target_apilado(1, ep, risk, pivs[i], gaps, i, niveles_objetivo, rr_min, rr_max)
                            elif rr_modo in ("cadena", "cadena_extiende"):
                                target2 = _target_cadena(1, ep, risk, cur_hi, cur_lo, cadena_max_gap_mult,
                                                          rr_max, cadena_min_niveles)
                                if rr_modo == "cadena_extiende" and target2 is not None and target2 < cfg["rr2"]:
                                    target2 = None  # la cadena solo puede ALARGAR el objetivo, nunca acortarlo
                            else:
                                target2 = None
                            meta_actual["rr_objetivo"] = target2 if target2 is not None else cfg["rr2"]
                            meta_actual["rr_dinamico_disponible"] = target2 is not None
                            arm = None
                else:
                    ok = C[i] < O[i] and r_ > 0 and cuerpo >= cfg["cuerpo_frac"] * r_ and C[i] < arm[2]
                    if ok:
                        _ep = C[i]; _sl = max(arm[1], H[i]) + cfg["sl_buf"]; _r = _sl - _ep
                        if 0 < _r <= 100.0:
                            ep, sl, risk, open_, dir_, eIdx, tp1, moved = _ep, _sl, _r, True, -1, i, False, False
                            if rr_modo == "dinamico":
                                target2 = _target_apilado(-1, ep, risk, pivs[i], gaps, i, niveles_objetivo, rr_min, rr_max)
                            elif rr_modo in ("cadena", "cadena_extiende"):
                                target2 = _target_cadena(-1, ep, risk, cur_hi, cur_lo, cadena_max_gap_mult,
                                                          rr_max, cadena_min_niveles)
                                if rr_modo == "cadena_extiende" and target2 is not None and target2 < cfg["rr2"]:
                                    target2 = None
                            else:
                                target2 = None
                            meta_actual["rr_objetivo"] = target2 if target2 is not None else cfg["rr2"]
                            meta_actual["rr_dinamico_disponible"] = target2 is not None
                            arm = None

        if open_ and i > eIdx:
            rr2_ef = meta_actual["rr_objetivo"]
            t1 = ep + risk * cfg["rr1"] * dir_
            t2 = ep + risk * rr2_ef * dir_
            hitSL = (L[i] <= sl) if dir_ == 1 else (H[i] >= sl)
            cerrar = None
            if not tp1:
                hT1 = (H[i] >= t1) if dir_ == 1 else (L[i] <= t1)
                if hitSL: cerrar = ("STOP" if not moved else "BE", sl)
                elif hT1:
                    tp1 = True; be = ep + risk * cfg["lock_r"] * dir_
                    if (not moved) or (be > sl if dir_ == 1 else be < sl): sl = be
                    moved = True
                elif not moved:
                    re = (H[i] - ep) / risk if dir_ == 1 else (ep - L[i]) / risk
                    if re >= cfg["be_trig"]: sl = ep + risk * cfg["lock_r"] * dir_; moved = True
            else:
                hT2 = (H[i] >= t2) if dir_ == 1 else (L[i] <= t2)
                if hitSL: cerrar = ("BE" if moved else "STOP", sl)
                elif hT2: cerrar = ("TP", t2)
            if cerrar is not None:
                motivo, exitp = cerrar
                slip = M.TICK * M.SLIPPAGE_TICKS
                pnl = ((exitp - ep) * dir_ - slip) * M.PV * 3 - M.COMMISSION_PER_CONTRACT_SIDE * 3 * 2
                filas.append(dict(
                    variante=variante,
                    entrada_utc=dt.datetime.fromtimestamp(T[eIdx], tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                    dir="LONG" if dir_ == 1 else "SHORT",
                    entry=round(ep, 2), stop_inicial=round(ep - risk * dir_, 2), riesgo=round(risk, 2),
                    exit=round(exitp, 2), motivo=motivo, pnl=round(pnl, 2),
                    edad_al_tocar_velas=meta_actual["edad_toque"],
                    apilamiento=meta_actual["apilamiento"],
                    liquidez=meta_actual["liq"], tenia_fvg=meta_actual["fvg"],
                    rr_objetivo=round(meta_actual["rr_objetivo"], 2),
                    rr_dinamico_disponible=meta_actual.get("rr_dinamico_disponible"),
                ))
                open_ = False
    return filas


VARIANTES = [
    dict(variante="A_control_edad12h3_fvg", edad_max=12, exigir_fvg=True),
    dict(variante="B_sin_limite_edad_solo_fvg", edad_max=None, exigir_fvg=True),
    dict(variante="C_sin_edad_apilamiento2", edad_max=None, exigir_fvg=True, min_apilamiento=2),
    dict(variante="D_gate_excluir_peligro", edad_max=12, exigir_fvg=True, liquidez_modo="excluir_peligro"),
    dict(variante="E_gate_solo_favor", edad_max=12, exigir_fvg=True, liquidez_modo="solo_favor"),
    dict(variante="F_sin_edad_solo_favor", edad_max=None, exigir_fvg=True, liquidez_modo="solo_favor"),
    dict(variante="G_rr_dinamico_nivel2", edad_max=12, exigir_fvg=True, rr_modo="dinamico", niveles_objetivo=2),
    dict(variante="H_sin_edad_apilamiento2_rrdinamico", edad_max=None, exigir_fvg=True,
         min_apilamiento=2, rr_modo="dinamico", niveles_objetivo=2),
    dict(variante="I_favor_rr_cadena_liquidez", edad_max=None, exigir_fvg=True,
         liquidez_modo="solo_favor", rr_modo="cadena", cadena_max_gap_mult=3.0,
         cadena_min_niveles=2, rr_max=10.0),
    dict(variante="J_favor_rr_cadena_solo_extiende", edad_max=None, exigir_fvg=True,
         liquidez_modo="solo_favor", rr_modo="cadena_extiende", cadena_max_gap_mult=3.0,
         cadena_min_niveles=2, rr_max=10.0),
]


def resumen_de(filas):
    if not filas:
        return dict(trades=0, net=0, pf=0, wr=0)
    pnl = [f["pnl"] for f in filas]
    g = sum(x for x in pnl if x > 0); l = -sum(x for x in pnl if x < 0)
    return dict(trades=len(pnl), net=round(sum(pnl), 2),
                pf=round(g / l, 2) if l else 0,
                wr=round(sum(1 for x in pnl if x > 0) / len(pnl) * 100, 1))


if __name__ == "__main__":
    bars = cargar_bars()
    todas = []
    print(f"{'variante':<38}{'ops':>5}{'net':>12}{'PF':>7}{'WR%':>7}")
    for v in VARIANTES:
        filas = simular(bars, **v)
        todas.extend(filas)
        r = resumen_de(filas)
        print(f"{v['variante']:<38}{r['trades']:>5}{r['net']:>12.2f}{r['pf']:>7.2f}{r['wr']:>7.1f}")

    out = "experimentos_liquidez.csv"
    cols = ["variante", "entrada_utc", "dir", "entry", "stop_inicial", "riesgo", "exit",
            "motivo", "pnl", "edad_al_tocar_velas", "apilamiento", "liquidez", "tenia_fvg",
            "rr_objetivo", "rr_dinamico_disponible"]
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for fila in todas:
            w.writerow(fila)
    print(f"\n{len(todas)} operaciones (todas las variantes) escritas en {out}")
    print("Recorda: esto es MODELO POR VELA -- cualquier variante que se vea bien hay que")
    print("tick-verificarla antes de creerla (ya paso una vez que el bar model mintio 4x).")
