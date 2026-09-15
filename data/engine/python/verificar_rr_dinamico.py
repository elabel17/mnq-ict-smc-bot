"""Verificacion tick a tick de la variante C (RR dinamico por liquidez
apilada, nivel 2) -- mismo metodo que verificar_ticks.py, pero con un
target por operacion en vez de RR2 fijo (target ya resuelto en
liquidez_apilada.py --export-c, incluye el 3er ingrediente pendiente: gaps
de fin de semana + niveles de pivote apilados por delante)."""
import datetime as dt

# (entry_utc, dir, entry, risk, exit_barra(modelo por vela), rr_dinamico_usado)
TRADES = [
    ("2025-09-19 16:00:00", 1, 24806.0, 74.0, 24820.8, 4.0),
    ("2025-09-22 13:15:00", 1, 24814.75, 50.0, 25014.75, 4.0),
    ("2025-09-23 12:15:00", -1, 24995.25, 17.5, 24991.75, 4.0),
    ("2025-09-23 13:30:00", -1, 24954.5, 57.25, 24943.05, 1.9388646288209608),
    ("2025-09-24 13:00:00", -1, 24874.5, 24.0, 24898.5, 2.375),
    ("2025-09-25 15:15:00", -1, 24598.75, 59.0, 24657.75, 4.0),
    ("2025-09-26 14:30:00", 1, 24626.75, 89.75, 24644.7, 1.7966573816155988),
    ("2025-09-29 13:15:00", -1, 24851.25, 48.25, 24899.5, 2.005181347150259),
    ("2025-09-30 14:45:00", 1, 24842.75, 56.25, 24786.5, 4.0),
    ("2025-09-30 16:45:00", -1, 24783.5, 60.25, 24771.45, 3.5726141078838176),
    ("2025-10-01 13:00:00", 1, 24787.0, 68.0, 24800.6, 1.8014705882352942),
    ("2025-10-06 16:00:00", -1, 25186.5, 33.5, 25220.0, 1.8507462686567164),
    ("2025-10-07 12:15:00", 1, 25213.25, 35.75, 25220.4, 4.0),
    ("2025-10-08 13:30:00", 1, 25132.75, 76.25, 25265.5, 1.740983606557377),
    ("2025-10-13 12:45:00", -1, 24786.75, 71.25, 24858.0, 1.8982456140350876),
    ("2025-10-13 14:15:00", -1, 24824.5, 82.0, 24808.1, 2.1097560975609757),
    ("2025-10-16 12:30:00", 1, 25095.0, 91.25, 25113.25, 4.0),
    ("2025-10-22 13:15:00", -1, 25265.25, 41.75, 25256.9, 4.868263473053892),
    ("2025-10-28 12:45:00", 1, 26012.5, 24.0, 26017.3, 4.0),
    ("2025-10-28 15:45:00", 1, 26060.5, 72.0, 26074.9, 4.0),
    ("2025-10-31 12:15:00", 1, 26262.75, 72.5, 26190.25, 1.8862068965517242),
    ("2025-11-11 15:00:00", -1, 25571.75, 67.5, 25558.25, 1.7148148148148148),
    ("2025-11-11 17:30:00", 1, 25584.25, 82.75, 25754.5, 2.0574018126888216),
    ("2025-11-17 15:00:00", -1, 25126.75, 91.25, 25108.5, 1.8794520547945206),
    ("2025-11-27 13:45:00", -1, 25300.5, 17.0, 25297.1, 6.720588235294118),
    ("2025-11-28 15:30:00", 1, 25389.25, 57.5, 25400.75, 4.0),
    ("2025-12-01 14:15:00", -1, 25254.75, 52.25, 25307.0, 4.0),
    ("2025-12-12 14:15:00", -1, 25559.75, 54.25, 25614.0, 1.6451612903225807),
    ("2025-12-17 14:00:00", -1, 25187.75, 69.5, 25079.0, 1.564748201438849),
]
BE_TRIG, LOCK_R = 0.4, 0.2
HORIZONTE = 8 * 3600  # RR dinamico puede tardar mas en resolver que RR2 fijo

ops = []
for s, d, ep, risk, exb, rr in TRADES:
    t0 = dt.datetime.strptime(s, "%Y-%m-%d %H:%M:%S").replace(tzinfo=dt.timezone.utc).timestamp()
    ops.append(dict(t0=t0, t1=t0 + HORIZONTE, dir=d, ep=ep, risk=risk, rr=rr,
                     sl0=ep - risk * d, tp=ep + risk * rr * d, exit_barra=exb,
                     moved=False, sl=ep - risk * d, resuelto=False,
                     exit_tick=None, motivo=None))

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
        activo = any(not op["resuelto"] and op["t0"] <= ts <= op["t1"] for op in ops)
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
                op["resuelto"] = True; op["exit_tick"] = precio; op["motivo"] = "TP_DINAMICO"
            elif not op["moved"]:
                r_now = (precio - op["ep"]) / op["risk"] * d
                if r_now >= BE_TRIG:
                    op["moved"] = True
                    op["sl"] = op["ep"] + op["risk"] * LOCK_R * d

print("lineas escaneadas: {:,}".format(n))
print()
print("{:<20}{:>5}{:>7}{:>10}{:>11}{:>11}{:>13}{:>9}".format(
    "entrada", "dir", "RR", "exit_bar", "exit_tick", "motivo", "", "dif_pts"))
slip = 0.5  # 2 ticks, igual que motor_confluencia
PV, QTY = 2.0, 3
sin_resolver = 0
neto_bar = 0.0; neto_tick = 0.0
g_bar = l_bar = g_tick = l_tick = 0.0
for op, (s, d, ep, risk, exb, rr) in zip(ops, TRADES):
    pnl_bar = ((exb - ep) * d - slip) * PV * QTY - 1.0 * QTY * 2
    neto_bar += pnl_bar
    if pnl_bar > 0: g_bar += pnl_bar
    else: l_bar += -pnl_bar
    if not op["resuelto"]:
        sin_resolver += 1
        print("{:<20}{:>5}{:>7.2f}{:>10.2f}{:>11}{:>11}{:>13}{:>9}".format(
            s, d, rr, exb, "SIN_RES", "-", "", "-"))
        continue
    dif = abs(op["exit_tick"] - exb)
    pnl_tick = ((op["exit_tick"] - ep) * d - slip) * PV * QTY - 1.0 * QTY * 2
    neto_tick += pnl_tick
    if pnl_tick > 0: g_tick += pnl_tick
    else: l_tick += -pnl_tick
    print("{:<20}{:>5}{:>7.2f}{:>10.2f}{:>11.2f}{:>11}{:>13}{:>9.2f}".format(
        s, d, rr, exb, op["exit_tick"], op["motivo"], "", dif))

print("\nsin resolver dentro de {}h: {}/{}".format(HORIZONTE // 3600, sin_resolver, len(ops)))
print(f"\nBAR MODEL : net=${neto_bar:9.2f}  PF={(g_bar/l_bar if l_bar else 0):.2f}")
print(f"TICK REAL : net=${neto_tick:9.2f}  PF={(g_tick/l_tick if l_tick else 0):.2f}  "
      f"(sobre {len(ops)-sin_resolver}/{len(ops)} resueltas)")
