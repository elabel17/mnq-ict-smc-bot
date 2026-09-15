"""Igual que verificar_parcial.py (1 de 3 contratos banca en RR1=1.5, resto
corre a RR2=4.0) pero SIN el gatillo de BE anticipado (0.4R) -- el unico
movimiento de stop para el remanente es al tomar el parcial en RR1."""
import datetime as dt
import json

TRADES = json.load(open("variante_f_visual_data.json"))["trades"]

RR1, LOCK_R = 1.5, 0.0   # sin BE anticipado: el stop del remanente se mueve SOLO al tomar parcial
HORIZONTE = 8 * 3600
QTY_TOTAL, QTY_PARCIAL = 3, 1

ops = []
for t in TRADES:
    s, d, ep, risk = t["s"], t["dir"], t["ep"], t["risk"]
    t0 = dt.datetime.strptime(s, "%Y-%m-%d %H:%M:%S").replace(tzinfo=dt.timezone.utc).timestamp()
    ops.append(dict(
        s=s, t0=t0, t1=t0 + HORIZONTE, dir=d, ep=ep, risk=risk,
        sl=ep - risk * d, tp_final=ep + risk * 4.0 * d, tp1=ep + risk * RR1 * d,
        tomoParcial=False, resuelto=False,
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
                op["motivo"] = "BE" if op["tomoParcial"] else "STOP"
                continue
            if op["tomoParcial"] and hitTPfinal:
                op["resuelto"] = True; op["final_px"] = precio; op["motivo"] = "TP2"
                continue
            if not op["tomoParcial"] and hitTP1:
                op["tomoParcial"] = True
                op["parcial_px"] = precio
                op["sl"] = op["ep"] + op["risk"] * LOCK_R * d

slip = 0.5; PV = 2.0
sin_resolver = 0
neto = 0.0; g = l = 0.0
for op in ops:
    if op["tomoParcial"] and not op["resuelto"]:
        sin_resolver += 1
        continue
    if not op["tomoParcial"] and not op["resuelto"]:
        sin_resolver += 1
        continue
    pnl = 0.0
    if op["tomoParcial"]:
        pnl += ((op["parcial_px"] - op["ep"]) * op["dir"] - slip) * PV * QTY_PARCIAL - 1.0 * QTY_PARCIAL * 2
        qty_rest = QTY_TOTAL - QTY_PARCIAL
        pnl += ((op["final_px"] - op["ep"]) * op["dir"] - slip) * PV * qty_rest - 1.0 * qty_rest * 2
    else:
        pnl += ((op["final_px"] - op["ep"]) * op["dir"] - slip) * PV * QTY_TOTAL - 1.0 * QTY_TOTAL * 2
    neto += pnl
    if pnl > 0: g += pnl
    else: l += -pnl

print(f"operaciones: {len(ops)}   sin resolver: {sin_resolver}")
print(f"\nCON PARCIAL, SIN BE anticipado (1 de 3 en RR1=1.5, resto a RR2=4.0, sin gatillo 0.4R):")
print(f"  net=${neto:9.2f}  PF={(g/l if l else 0):.2f}")
