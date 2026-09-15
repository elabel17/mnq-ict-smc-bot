"""Verificacion tick a tick de la variante F (sin limite de edad, exige
liquidez a favor cerca, exige FVG) -- la que mas se parece a tu heuristica
manual: 'sin importar cuanto lleve abandonada, si no esta tocada y tiene
confluencias a favor, sigue siendo valida'."""
import datetime as dt

TRADES = [
    ("2025-09-24 14:45:00", -1, 24794.0, 68.5, 24780.3, 4.0),
    ("2025-09-26 12:15:00", 1, 24647.5, 16.5, 24713.5, 4.0),
    ("2025-09-26 13:45:00", 1, 24706.5, 75.5, 24631.0, 4.0),
    ("2025-09-26 14:45:00", -1, 24565.5, 72.75, 24638.25, 4.0),
    ("2025-09-29 15:45:00", -1, 24849.0, 46.5, 24839.7, 4.0),
    ("2025-09-30 13:00:00", -1, 24822.75, 59.0, 24810.95, 4.0),
    ("2025-09-30 15:45:00", 1, 24810.75, 48.75, 24820.5, 4.0),
    ("2025-10-03 15:45:00", 1, 25145.25, 41.25, 25104.0, 4.0),
    ("2025-10-06 13:15:00", 1, 25214.25, 46.0, 25168.25, 4.0),
    ("2025-10-06 14:45:00", 1, 25152.75, 66.75, 25166.1, 4.0),
    ("2025-10-08 13:30:00", 1, 25132.75, 61.5, 25378.75, 4.0),
    ("2025-10-09 16:45:00", -1, 25203.75, 58.5, 25192.05, 4.0),
    ("2025-10-10 13:30:00", 1, 25368.5, 76.75, 25291.75, 4.0),
    ("2025-10-13 13:00:00", 1, 24849.0, 65.5, 24783.5, 4.0),
    ("2025-10-13 15:45:00", 1, 24892.75, 71.5, 24907.05, 4.0),
    ("2025-10-16 13:30:00", 1, 25091.5, 57.5, 25034.0, 4.0),
    ("2025-10-16 14:45:00", -1, 25107.25, 74.5, 25092.35, 4.0),
    ("2025-10-20 15:15:00", 1, 25321.0, 33.75, 25327.75, 4.0),
    ("2025-10-20 16:45:00", 1, 25314.75, 65.5, 25327.85, 4.0),
    ("2025-10-21 13:30:00", -1, 25256.0, 72.25, 25241.55, 4.0),
    ("2025-10-21 15:45:00", 1, 25322.75, 59.25, 25334.6, 4.0),
    ("2025-10-22 14:00:00", -1, 25211.5, 71.5, 24925.5, 4.0),
    ("2025-10-23 12:45:00", 1, 25008.0, 77.5, 25318.0, 4.0),
    ("2025-10-29 14:30:00", -1, 26278.0, 34.0, 26271.2, 4.0),
    ("2025-10-31 15:15:00", -1, 26136.75, 59.0, 26124.95, 4.0),
    ("2025-11-03 13:30:00", 1, 26175.25, 60.75, 26187.4, 4.0),
    ("2025-11-05 13:15:00", 1, 25561.25, 48.75, 25571.0, 4.0),
    ("2025-11-06 13:45:00", -1, 25767.0, 51.5, 25561.0, 4.0),
    ("2025-11-07 13:45:00", 1, 25111.25, 58.25, 25053.0, 4.0),
    ("2025-11-10 15:30:00", -1, 25616.5, 64.25, 25603.65, 4.0),
    ("2025-11-13 14:00:00", -1, 25462.75, 76.25, 25447.5, 4.0),
    ("2025-11-13 17:15:00", 1, 25233.75, 64.0, 25169.75, 4.0),
    ("2025-11-14 13:15:00", -1, 24709.5, 55.25, 24698.45, 4.0),
    ("2025-11-17 13:15:00", 1, 25097.5, 86.0, 25011.5, 4.0),
    ("2025-11-19 16:45:00", 1, 24715.0, 68.25, 24646.75, 4.0),
    ("2025-11-20 13:30:00", 1, 25197.25, 70.25, 25211.3, 4.0),
    ("2025-11-24 14:00:00", 1, 24570.0, 77.25, 24585.45, 4.0),
    ("2025-11-25 16:15:00", 1, 24854.25, 82.25, 24870.7, 4.0),
    ("2025-11-25 17:15:00", 1, 24991.25, 95.75, 25010.4, 4.0),
    ("2025-11-26 13:45:00", 1, 25215.0, 37.5, 25177.5, 4.0),
    ("2025-11-26 15:30:00", 1, 25224.5, 42.25, 25393.5, 4.0),
    ("2025-11-28 15:30:00", 1, 25389.25, 32.0, 25395.65, 4.0),
    ("2025-12-01 16:15:00", 1, 25380.75, 74.5, 25395.65, 4.0),
    ("2025-12-02 15:30:00", 1, 25622.0, 96.0, 25641.2, 4.0),
    ("2025-12-03 15:45:00", -1, 25562.5, 86.25, 25545.25, 4.0),
    ("2025-12-03 17:00:00", 1, 25597.75, 65.0, 25610.75, 4.0),
    ("2025-12-08 14:15:00", -1, 25791.25, 30.25, 25821.5, 4.0),
    ("2025-12-09 17:45:00", 1, 25717.25, 39.25, 25725.1, 4.0),
    ("2025-12-10 14:15:00", -1, 25647.25, 31.5, 25640.95, 4.0),
    ("2025-12-10 16:15:00", 1, 25647.25, 44.25, 25656.1, 4.0),
    ("2025-12-11 14:00:00", 1, 25668.75, 42.5, 25626.25, 4.0),
    ("2025-12-11 17:15:00", 1, 25604.25, 62.25, 25616.7, 4.0),
    ("2025-12-15 13:30:00", 1, 25357.75, 51.5, 25368.05, 4.0),
    ("2025-12-16 17:45:00", -1, 24960.5, 68.75, 24946.75, 4.0),
    ("2025-12-17 14:00:00", -1, 25187.75, 88.5, 24833.75, 4.0),
]
RR2, BE_TRIG, LOCK_R = 4.0, 0.4, 0.2
HORIZONTE = 6 * 3600

ops = []
for s, d, ep, risk, exb, rr in TRADES:
    t0 = dt.datetime.strptime(s, "%Y-%m-%d %H:%M:%S").replace(tzinfo=dt.timezone.utc).timestamp()
    ops.append(dict(t0=t0, t1=t0 + HORIZONTE, dir=d, ep=ep, risk=risk,
                     sl=ep - risk * d, tp=ep + risk * rr * d, exit_barra=exb,
                     moved=False, resuelto=False, exit_tick=None, motivo=None))

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

print("lineas escaneadas: {:,}\n".format(n))
slip = 0.5; PV, QTY = 2.0, 3
sin_resolver = 0; neto_bar = neto_tick = g_bar = l_bar = g_tick = l_tick = 0.0
for op, (s, d, ep, risk, exb, rr) in zip(ops, TRADES):
    pnl_bar = ((exb - ep) * d - slip) * PV * QTY - 1.0 * QTY * 2
    neto_bar += pnl_bar
    if pnl_bar > 0: g_bar += pnl_bar
    else: l_bar += -pnl_bar
    if not op["resuelto"]:
        sin_resolver += 1
        print(f"{s}  dir={d:>2}  exit_bar={exb:.2f}  SIN_RESOLVER")
        continue
    dif = abs(op["exit_tick"] - exb)
    pnl_tick = ((op["exit_tick"] - ep) * d - slip) * PV * QTY - 1.0 * QTY * 2
    neto_tick += pnl_tick
    if pnl_tick > 0: g_tick += pnl_tick
    else: l_tick += -pnl_tick
    if dif > 5:
        print(f"{s}  dir={d:>2}  exit_bar={exb:.2f}  exit_tick={op['exit_tick']:.2f}  "
              f"{op['motivo']:<5}  dif={dif:.2f}")

print(f"\nsin resolver dentro de {HORIZONTE//3600}h: {sin_resolver}/{len(ops)}")
print(f"\nBAR MODEL : net=${neto_bar:9.2f}  PF={(g_bar/l_bar if l_bar else 0):.2f}")
print(f"TICK REAL : net=${neto_tick:9.2f}  PF={(g_tick/l_tick if l_tick else 0):.2f}  "
      f"(sobre {len(ops)-sin_resolver}/{len(ops)} resueltas)")
