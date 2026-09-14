"""Reconstruye, tick a tick, las 24 operaciones de union+FVG 08-13 y compara
contra lo que asumio el simulador por velas (que solo ve high/low, no el
orden real dentro de la vela)."""
import datetime as dt

TRADES = [
    # (entry_utc_str, dir, entry, risk, exit_barra)
    ("2025-09-19 16:00:00", 1, 24806.0, 74.0, 24820.8),
    ("2025-09-22 13:15:00", 1, 24814.75, 50.0, 25014.75),
    ("2025-09-23 12:15:00", -1, 24995.25, 17.5, 24991.75),
    ("2025-09-23 13:30:00", -1, 24954.5, 57.25, 24943.05),
    ("2025-09-24 13:30:00", -1, 24835.5, 65.75, 24822.35),
    ("2025-09-26 14:30:00", 1, 24626.75, 89.75, 24644.7),
    ("2025-09-29 13:15:00", -1, 24851.25, 48.25, 24899.5),
    ("2025-09-30 14:45:00", 1, 24842.75, 56.25, 24786.5),
    ("2025-09-30 16:45:00", -1, 24783.5, 60.25, 24771.45),
    ("2025-10-06 16:00:00", -1, 25186.5, 33.5, 25220.0),
    ("2025-10-07 12:15:00", 1, 25213.25, 35.75, 25220.4),
    ("2025-10-13 12:45:00", -1, 24786.75, 71.25, 24858.0),
    ("2025-10-13 14:15:00", -1, 24824.5, 82.0, 24808.1),
    ("2025-10-16 12:30:00", 1, 25095.0, 91.25, 25113.25),
    ("2025-10-22 14:00:00", -1, 25211.5, 95.5, 24829.5),
    ("2025-10-27 14:30:00", 1, 25889.25, 80.0, 26209.25),
    ("2025-11-11 15:00:00", -1, 25571.75, 67.5, 25558.25),
    ("2025-11-26 13:45:00", 1, 25215.0, 77.5, 25230.5),
    ("2025-11-27 13:45:00", -1, 25300.5, 17.0, 25297.1),
    ("2025-11-28 15:30:00", 1, 25389.25, 57.5, 25400.75),
    ("2025-12-01 14:15:00", -1, 25254.75, 52.25, 25307.0),
    ("2025-12-11 17:45:00", -1, 25592.5, 86.5, 25679.0),
    ("2025-12-12 14:15:00", -1, 25559.75, 54.25, 25614.0),
    ("2025-12-17 14:00:00", -1, 25187.75, 69.5, 24909.75),
]
RR2, BE_TRIG, LOCK_R = 4.0, 0.4, 0.2
HORIZONTE = 6 * 3600  # 6 horas maximo por operacion

ops = []
for s, d, ep, risk, exb in TRADES:
    t0 = dt.datetime.strptime(s, "%Y-%m-%d %H:%M:%S").replace(tzinfo=dt.timezone.utc).timestamp()
    ops.append(dict(t0=t0, t1=t0+HORIZONTE, dir=d, ep=ep, risk=risk, sl0=ep-risk*d,
                     tp=ep+risk*RR2*d, exit_barra=exb, moved=False, sl=ep-risk*d,
                     resuelto=False, exit_tick=None, motivo=None))

ARCHIVO = r"C:\Users\diazl\Downloads\mnq-ict-smc-bot\ticks data\MNQ 12-25 complete.Last.txt"
dia_cache = None; medianoche_epoch = 0
n = 0
with open(ARCHIVO, "r", encoding="ascii", errors="ignore") as f:
    for linea in f:
        n += 1
        try:
            campo0, resto = linea.split(";", 1)
            fecha = campo0[0:8]; hh = int(campo0[9:11]); mm = int(campo0[11:13]); ss = int(campo0[13:15])
        except (ValueError, IndexError):
            continue
        if fecha != dia_cache:
            dia_cache = fecha
            dd = dt.datetime.strptime(fecha, "%Y%m%d").replace(tzinfo=dt.timezone.utc)
            medianoche_epoch = int(dd.timestamp())
        ts = medianoche_epoch + hh*3600 + mm*60 + ss
        activo = False
        for op in ops:
            if op["resuelto"]: continue
            if op["t0"] <= ts <= op["t1"]:
                activo = True
        if not activo:
            continue
        try:
            precio = float(resto.split(";", 1)[0])
        except (ValueError, IndexError):
            continue
        for op in ops:
            if op["resuelto"] or not (op["t0"] <= ts <= op["t1"]):
                continue
            d = op["dir"]
            hitSL = (precio <= op["sl"]) if d == 1 else (precio >= op["sl"])
            hitTP = (precio >= op["tp"]) if d == 1 else (precio <= op["tp"])
            if hitSL:
                op["resuelto"] = True; op["exit_tick"] = precio
                op["motivo"] = "BE" if op["moved"] else "STOP"
            elif hitTP:
                op["resuelto"] = True; op["exit_tick"] = precio; op["motivo"] = "TP2"
            elif not op["moved"]:
                r_now = (precio - op["ep"]) / op["risk"] * d
                if r_now >= BE_TRIG:
                    op["moved"] = True
                    op["sl"] = op["ep"] + op["risk"] * LOCK_R * d

print("lineas escaneadas: {:,}".format(n))
print()
print("{:<20} {:>5} {:>10} {:>10} {:>10} {:>8}".format("entrada","dir","exit_barra","exit_tick","motivo","dif_pts"))
sin_resolver = 0
for op, (s,d,ep,risk,exb) in zip(ops, TRADES):
    if not op["resuelto"]:
        sin_resolver += 1
        print("{:<20} {:>5} {:>10.2f} {:>10} {:>10} {:>8}".format(s,d,exb,"SIN RESOLVER","-","-"))
        continue
    dif = abs(op["exit_tick"] - exb)
    print("{:<20} {:>5} {:>10.2f} {:>10.2f} {:>10} {:>8.2f}".format(s,d,exb,op["exit_tick"],op["motivo"],dif))
print("\nsin resolver dentro de 6h: {}/{}".format(sin_resolver, len(ops)))
