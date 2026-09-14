import datetime as dt

TRADES = [
    ("2025-09-26 14:00:00", -1, 24605.5, 83.5, 24592.975),
    ("2025-09-26 16:00:00", 1, 24599.5, 56.0, 24935.5),
    ("2025-09-29 15:15:00", -1, 24866.75, 78.5, 24854.975),
    ("2025-10-17 14:30:00", -1, 24807.25, 84.75, 24794.5375),
    ("2025-10-29 14:30:00", -1, 26278.0, 50.5, 26270.425),
    ("2025-11-25 16:15:00", 1, 24854.25, 93.75, 24868.3125),
    ("2025-12-01 16:00:00", -1, 25349.0, 27.25, 25376.25),
    ("2025-12-08 14:15:00", -1, 25791.25, 34.75, 25826.0),
    ("2025-12-09 14:45:00", 1, 25630.25, 34.75, 25635.4625),
    ("2025-12-09 17:15:00", -1, 25707.5, 8.25, 25715.75),
]
RR2, BE_TRIG, LOCK_R = 6.0, 0.3, 0.15
HORIZONTE = 8 * 3600

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
        activo = any(op["t0"] <= ts <= op["t1"] for op in ops if not op["resuelto"])
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
        print("{:<20} {:>5} {:>10.4f} {:>10} {:>10} {:>8}".format(s,d,exb,"SIN RESOLVER","-","-"))
        continue
    dif = abs(op["exit_tick"] - exb)
    print("{:<20} {:>5} {:>10.4f} {:>10.4f} {:>10} {:>8.2f}".format(s,d,exb,op["exit_tick"],op["motivo"],dif))
print("\nsin resolver dentro de 8h: {}/{}".format(sin_resolver, len(ops)))
