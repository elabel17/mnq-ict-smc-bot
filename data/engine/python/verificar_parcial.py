"""Prueba parciales reales: banca 1 de 3 contratos en RR1=1.5 (ganancia
efectiva, no solo mover el stop), deja 2 contratos corriendo con el mismo
BE temprano (0.4R) ya validado, hasta RR2=4.0. Verificado tick a tick sobre
las mismas 55 entradas de la variante F -- comparacion directa, misma
entrada, distinta gestion de salida."""
import datetime as dt
import json

TRADES = json.load(open("variante_f_visual_data.json"))["trades"]
# variante_f_visual_data.json trae sl0/tp de RR2=4.0 fijo, ya calculado

RR1, BE_TRIG, LOCK_R = 1.5, 0.4, 0.2
HORIZONTE = 8 * 3600
QTY_TOTAL, QTY_PARCIAL = 3, 1

ops = []
for t in TRADES:
    s, d, ep, risk = t["s"], t["dir"], t["ep"], t["risk"]
    t0 = dt.datetime.strptime(s, "%Y-%m-%d %H:%M:%S").replace(tzinfo=dt.timezone.utc).timestamp()
    ops.append(dict(
        s=s, t0=t0, t1=t0 + HORIZONTE, dir=d, ep=ep, risk=risk,
        sl=ep - risk * d, tp_final=ep + risk * 4.0 * d, tp1=ep + risk * RR1 * d,
        movedBE=False, tomoParcial=False, resuelto=False,
        parcial_px=None, final_px=None, motivo=None,
    ))

ARCHIVO = r"C:\Users\diazl\Downloads\mnq-ict-smc-bot\ticks data\MNQ 12-25 complete.Last.txt"
dia_cache = None; medianoche_epoch = 0
with open(ARCHIVO, "r", encoding="ascii", errors="ignore") as f:
    for linea in f:
        try:
            campo0, resto = linea.split(";", 1)
            fecha = campo0[0:8]; hh = int(campo0[9:11]); mm = int(campo0[11:13]); ss = int(campo0[13:15])
        except (ValueError, IndexError):
            continue
        if fecha != dia_cache:
            dia_cache = fecha
            dd = dt.datetime.strptime(fecha, "%Y%m%d").replace(tzinfo=dt.timezone.utc)
            medianoche_epoch = int(dd.timestamp())
        ts = medianoche_epoch + hh * 3600 + mm * 60 + ss
        if not any(not op["resuelto"] and op["t0"] <= ts <= op["t1"] for op in ops):
            continue
        try:
            precio = float(resto.split(";", 1)[0])
        except (ValueError, IndexError):
            continue
        for op in ops:
            if op["resuelto"] or not (op["t0"] <= ts <= op["t1"]): continue
            d = op["dir"]
            hitSL = (precio <= op["sl"]) if d == 1 else (precio >= op["sl"])
            hitTP1 = (precio >= op["tp1"]) if d == 1 else (precio <= op["tp1"])
            hitTPfinal = (precio >= op["tp_final"]) if d == 1 else (precio <= op["tp_final"])

            if hitSL:
                op["resuelto"] = True
                op["final_px"] = precio
                op["motivo"] = "BE" if op["movedBE"] else "STOP"
                continue

            if op["tomoParcial"] and hitTPfinal:
                op["resuelto"] = True; op["final_px"] = precio; op["motivo"] = "TP2"
                continue

            if not op["tomoParcial"] and hitTP1:
                op["tomoParcial"] = True
                op["parcial_px"] = precio
                be = op["ep"] + op["risk"] * LOCK_R * d
                if (not op["movedBE"]) or (be > op["sl"] if d == 1 else be < op["sl"]):
                    op["sl"] = be
                op["movedBE"] = True
                continue

            if not op["movedBE"]:
                r_now = (precio - op["ep"]) / op["risk"] * d
                if r_now >= BE_TRIG:
                    op["movedBE"] = True
                    op["sl"] = op["ep"] + op["risk"] * LOCK_R * d

slip = 0.5; PV = 2.0
sin_resolver = 0
neto_parcial = 0.0; g_p = l_p = 0.0
neto_full = 0.0; g_f = l_f = 0.0   # comparacion: mismas entradas, SIN parcial (todo a RR2)
for op in ops:
    if not op["resuelto"] and not op["tomoParcial"]:
        sin_resolver += 1
        continue
    # ---- con parcial ----
    pnl = 0.0
    if op["tomoParcial"]:
        pnl += ((op["parcial_px"] - op["ep"]) * op["dir"] - slip) * PV * QTY_PARCIAL - 1.0 * QTY_PARCIAL * 2
        qty_rest = QTY_TOTAL - QTY_PARCIAL
        if op["resuelto"]:
            pnl += ((op["final_px"] - op["ep"]) * op["dir"] - slip) * PV * qty_rest - 1.0 * qty_rest * 2
        else:
            sin_resolver += 1
            continue
    else:
        pnl += ((op["final_px"] - op["ep"]) * op["dir"] - slip) * PV * QTY_TOTAL - 1.0 * QTY_TOTAL * 2
    neto_parcial += pnl
    if pnl > 0: g_p += pnl
    else: l_p += -pnl

print(f"operaciones: {len(ops)}   sin resolver: {sin_resolver}")
print(f"\nCON PARCIAL (1 de 3 en RR1=1.5, resto a RR2=4.0 con BE 0.4R):")
print(f"  net=${neto_parcial:9.2f}  PF={(g_p/l_p if l_p else 0):.2f}")
