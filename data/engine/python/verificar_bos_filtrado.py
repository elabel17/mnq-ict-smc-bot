"""Verifica a tick la correccion propuesta: BOS con los mismos filtros de
calidad que el desplazamiento (liquidez limpia detras del origen, cierre
direccional fuerte en la vela de ruptura) -- surgio de que el usuario marco
5 operaciones malas en el visualizador, las 4 identificadas eran BOS sin
esos filtros."""
import datetime as dt

TRADES = [
    ("2025-09-24 14:45:00", -1, 24794.0, 68.5, 24780.3, 4.0),
    ("2025-09-29 15:45:00", -1, 24849.0, 46.5, 24839.7, 4.0),
    ("2025-09-30 13:00:00", -1, 24822.75, 59.0, 24810.95, 4.0),
    ("2025-09-30 15:45:00", 1, 24810.75, 48.75, 24820.5, 4.0),
    ("2025-10-02 16:45:00", 1, 25077.25, 36.0, 25084.45, 4.0),
    ("2025-10-08 13:30:00", 1, 25132.75, 61.5, 25378.75, 4.0),
    ("2025-10-09 16:45:00", -1, 25203.75, 58.5, 25192.05, 4.0),
    ("2025-10-13 15:45:00", 1, 24892.75, 71.5, 24907.05, 4.0),
    ("2025-10-14 13:00:00", 1, 24646.0, 69.0, 24577.0, 4.0),
    ("2025-10-16 13:30:00", 1, 25091.5, 57.5, 25034.0, 4.0),
    ("2025-10-16 14:45:00", -1, 25107.25, 74.5, 25092.35, 4.0),
    ("2025-10-20 15:15:00", 1, 25321.0, 33.75, 25327.75, 4.0),
    ("2025-10-20 16:45:00", 1, 25314.75, 65.5, 25327.85, 4.0),
    ("2025-10-21 13:15:00", 1, 25301.25, 52.0, 25249.25, 4.0),
    ("2025-10-21 16:45:00", -1, 25285.5, 64.0, 25272.7, 4.0),
    ("2025-10-22 14:00:00", -1, 25211.5, 71.5, 24925.5, 4.0),
    ("2025-10-23 12:45:00", 1, 25008.0, 77.5, 25318.0, 4.0),
    ("2025-10-29 14:30:00", -1, 26278.0, 34.0, 26271.2, 4.0),
    ("2025-11-03 16:15:00", -1, 26052.25, 68.0, 26120.25, 4.0),
    ("2025-11-06 13:45:00", -1, 25767.0, 51.5, 25561.0, 4.0),
    ("2025-11-07 13:45:00", 1, 25111.25, 72.75, 25038.5, 4.0),
    ("2025-11-13 17:15:00", 1, 25233.75, 64.0, 25169.75, 4.0),
    ("2025-11-14 13:15:00", -1, 24709.5, 55.25, 24698.45, 4.0),
    ("2025-11-17 13:15:00", 1, 25097.5, 86.0, 25011.5, 4.0),
    ("2025-11-19 16:45:00", 1, 24715.0, 68.25, 24646.75, 4.0),
    ("2025-11-20 13:45:00", 1, 25230.0, 92.0, 25248.4, 4.0),
    ("2025-11-27 13:30:00", 1, 25311.0, 52.5, 25521.0, 4.0),
    ("2025-12-01 16:15:00", 1, 25380.75, 74.5, 25395.65, 4.0),
    ("2025-12-02 15:00:00", 1, 25634.5, 88.75, 25545.75, 4.0),
    ("2025-12-03 15:45:00", -1, 25562.5, 86.25, 25545.25, 4.0),
    ("2025-12-03 17:00:00", 1, 25597.75, 55.75, 25608.9, 4.0),
    ("2025-12-08 14:15:00", -1, 25791.25, 30.25, 25821.5, 4.0),
    ("2025-12-09 15:30:00", 1, 25679.75, 49.25, 25689.6, 4.0),
    ("2025-12-09 16:45:00", 1, 25708.75, 58.25, 25720.4, 4.0),
    ("2025-12-10 14:15:00", -1, 25647.25, 31.5, 25640.95, 4.0),
    ("2025-12-10 16:45:00", 1, 25650.5, 42.25, 25658.95, 4.0),
    ("2025-12-11 14:00:00", 1, 25668.75, 42.5, 25626.25, 4.0),
    ("2025-12-11 17:15:00", 1, 25604.25, 62.25, 25616.7, 4.0),
    ("2025-12-15 13:30:00", 1, 25357.75, 51.5, 25368.05, 4.0),
    ("2025-12-16 17:45:00", -1, 24960.5, 68.75, 24946.75, 4.0),
    ("2025-12-17 14:00:00", -1, 25187.75, 90.0, 24827.75, 4.0),
]
BE_TRIG, LOCK_R = 0.4, 0.2
HORIZONTE = 8 * 3600

ops = []
for s, d, ep, risk, exb, rr in TRADES:
    t0 = dt.datetime.strptime(s, "%Y-%m-%d %H:%M:%S").replace(tzinfo=dt.timezone.utc).timestamp()
    ops.append(dict(s=s, t0=t0, t1=t0 + HORIZONTE, dir=d, ep=ep, risk=risk,
                     sl=ep - risk * d, tp=ep + risk * rr * d, exit_barra=exb,
                     moved=False, resuelto=False, exit_tick=None, motivo=None))

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
            hitTP = (precio >= op["tp"]) if d == 1 else (precio <= op["tp"])
            if hitSL:
                op["resuelto"] = True; op["exit_tick"] = precio; op["motivo"] = "BE" if op["moved"] else "STOP"
            elif hitTP:
                op["resuelto"] = True; op["exit_tick"] = precio; op["motivo"] = "TP2"
            elif not op["moved"]:
                r_now = (precio - op["ep"]) / op["risk"] * d
                if r_now >= BE_TRIG:
                    op["moved"] = True; op["sl"] = op["ep"] + op["risk"] * LOCK_R * d

slip = 0.5; PV, QTY = 2.0, 3
sin_resolver = 0; neto_bar = neto_tick = g_bar = l_bar = g_tick = l_tick = 0.0
for op, (s, d, ep, risk, exb, rr) in zip(ops, TRADES):
    pnl_bar = ((exb - ep) * d - slip) * PV * QTY - 1.0 * QTY * 2
    neto_bar += pnl_bar
    if pnl_bar > 0: g_bar += pnl_bar
    else: l_bar += -pnl_bar
    if not op["resuelto"]:
        sin_resolver += 1
        continue
    pnl_tick = ((op["exit_tick"] - ep) * d - slip) * PV * QTY - 1.0 * QTY * 2
    neto_tick += pnl_tick
    if pnl_tick > 0: g_tick += pnl_tick
    else: l_tick += -pnl_tick

print(f"operaciones: {len(ops)}   sin resolver dentro de {HORIZONTE//3600}h: {sin_resolver}")
print(f"\nBAR MODEL : net=${neto_bar:9.2f}  PF={(g_bar/l_bar if l_bar else 0):.2f}")
print(f"TICK REAL : net=${neto_tick:9.2f}  PF={(g_tick/l_tick if l_tick else 0):.2f}  "
      f"(sobre {len(ops)-sin_resolver}/{len(ops)} resueltas)")
