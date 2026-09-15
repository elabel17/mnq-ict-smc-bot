"""
Version 2: la primera comparacion (claude_validar_trades_manuales.py) usaba
sel_real(), que solo puede tener UNA operacion abierta a la vez -- si el
motor ya estaba en otro trade, "no detectaba nada" aunque la zona SI
existiera. Eso confunde "el motor no vio la zona" con "el motor estaba
ocupado". Aqui se reconstruye SOLO la deteccion de zonas (igual logica de
desplazamiento + origen + filtro de liquidez que usa v_nivel.py), sin la
gestion de una sola posicion, para responder la pregunta real: ¿existia
una zona tocable en la misma direccion, cerca del mismo precio, en el
momento en que el usuario entro?
"""
import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")

bars = json.load(open("../../python/claude_ohlcv_15m_2020_2026.json"))
bars = [(b[0], b[1], b[2], b[3], b[4], b[5] if len(b) > 5 else 0) for b in bars]
bars.sort(key=lambda x: x[0])
n = len(bars)
opens = [b[1] for b in bars]; highs = [b[2] for b in bars]
lows = [b[3] for b in bars]; closes = [b[4] for b in bars]; times = [b[0] for b in bars]
vols = [b[5] for b in bars]

DISP_LEN, DISP_MULT, DISP_CLOSE_FRAC = 20, 1.5, 0.6   # umbral REAL del Pine (no el del backtest 15m validado)
OB_SCAN_BARS, LIQ_CHECK_BARS, LIQ_TOL, LIQ_ACCUM = 10, 12, 4.0, 6
ZONE_MAX_AGE = 300

avg_range_cache = [None] * n

TRADES = [
    dict(id="2025-09-18 20:15 UTC", dir="LONG", precio=24688.64),
    dict(id="2025-09-22 09:15 UTC", dir="LONG", precio=24746.61),
    dict(id="2025-09-23 19:30 UTC", dir="LONG", precio=24803.35),
    dict(id="2025-09-24 16:00 UTC", dir="LONG", precio=24635.45, flag="AUTOFLAGEADO DEBIL (sin FVG, liquidez en contra) -- PERDIO"),
    dict(id="2025-09-25 00:45 UTC", dir="SHORT", precio=24766.31),
    dict(id="2025-09-25 09:15 UTC", dir="LONG", precio=24725.16, flag="AUTOFLAGEADO DEBIL ('OB de mala calidad') -- PERDIO"),
    dict(id="2025-09-25 18:00 UTC", dir="LONG", precio=24525.16),
]
target_epochs = {}
for t in TRADES:
    dt = datetime.strptime(t["id"].replace(" UTC", ""), "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
    target_epochs[t["id"]] = int(dt.timestamp())

VENTANA = 3 * 3600  # +/- 3 horas de margen
resultados = {t["id"]: [] for t in TRADES}
min_i = min(range(n), key=lambda i: abs(times[i] - (min(target_epochs.values()) - VENTANA)))

zones = []  # cada zona: dict(dir, top, bot, cleared, born, disp_ratio, vol_signal)

for i in range(n):
    if times[i] < min(target_epochs.values()) - VENTANA * 2:
        continue
    if times[i] > max(target_epochs.values()) + VENTANA * 2:
        break

    if i >= DISP_LEN - 1:
        s = sum(highs[k] - lows[k] for k in range(i - DISP_LEN + 1, i + 1))
        avg_range_cache[i] = s / DISP_LEN

    h, l, o, c = highs[i], lows[i], opens[i], closes[i]
    rng = h - l
    avg_prev = avg_range_cache[i - 1] if i >= 1 and avg_range_cache[i - 1] else None
    is_disp = avg_prev is not None and rng >= DISP_MULT * avg_prev
    bull_disp = is_disp and c > o and (c - l) >= DISP_CLOSE_FRAC * rng
    bear_disp = is_disp and c < o and (h - c) >= DISP_CLOSE_FRAC * rng
    disp_ratio_now = (rng / avg_prev) if avg_prev else 0.0

    if bull_disp:
        idx = -1
        for k in range(1, OB_SCAN_BARS + 1):
            j = i - k
            if j < 0: break
            if closes[j] < opens[j]: idx = k; break
        if idx != -1:
            cand_bot = lows[i - idx]
            mx = cu = 0
            for k in range(idx + 1, idx + LIQ_CHECK_BARS + 1):
                j = i - k
                if j < 0: break
                if lows[j] <= cand_bot + LIQ_TOL: cu += 1; mx = max(mx, cu)
                else: cu = 0
            if mx < LIQ_ACCUM:
                zones.append(dict(dir=1, top=highs[i - idx], bot=cand_bot, cleared=False, born=i,
                                   disp_ratio=disp_ratio_now, vol_signal=vols[i]))

    if bear_disp:
        idx2 = -1
        for k in range(1, OB_SCAN_BARS + 1):
            j = i - k
            if j < 0: break
            if closes[j] > opens[j]: idx2 = k; break
        if idx2 != -1:
            cand_top = highs[i - idx2]
            mx2 = cu2 = 0
            for k in range(idx2 + 1, idx2 + LIQ_CHECK_BARS + 1):
                j = i - k
                if j < 0: break
                if highs[j] >= cand_top - LIQ_TOL: cu2 += 1; mx2 = max(mx2, cu2)
                else: cu2 = 0
            if mx2 < LIQ_ACCUM:
                zones.append(dict(dir=-1, top=cand_top, bot=lows[i - idx2], cleared=False, born=i,
                                   disp_ratio=disp_ratio_now, vol_signal=vols[i]))

    for z in zones:
        if z["born"] != i and not z["cleared"]:
            if z["dir"] == 1 and l > z["top"]: z["cleared"] = True
            elif z["dir"] == -1 and h < z["bot"]: z["cleared"] = True

    zones = [z for z in zones if (i - z["born"]) <= ZONE_MAX_AGE]

    # snapshot: si este bar cae dentro de la ventana de algun trade manual,
    # registrar TODAS las zonas cleared (tocables) vivas en ese instante
    for t in TRADES:
        te = target_epochs[t["id"]]
        if abs(times[i] - te) <= VENTANA:
            for z in zones:
                if not z["cleared"]:
                    continue
                dist = abs(((z["top"] + z["bot"]) / 2) - t["precio"])
                if dist <= 80:  # zona cuyo centro esta a <=80pts del precio de entrada del usuario
                    resultados[t["id"]].append(dict(
                        bar_time=times[i], dz=z["dir"], top=z["top"], bot=z["bot"],
                        dist=dist, disp_ratio=z["disp_ratio"], vol_signal=z["vol_signal"],
                        born=z["born"]))

print(f"Zonas totales detectadas en la ventana analizada: {len(zones)} (al final del recorrido)\n")

for t in TRADES:
    print("=" * 100)
    flag = f"  [{t.get('flag')}]" if t.get("flag") else ""
    print(f"{t['id']} -- {t['dir']} @ {t['precio']}{flag}")
    vistos = resultados[t["id"]]
    # de-duplicar por (born, dir) -- la misma zona aparece en muchos snapshots
    unicos = {}
    for v in vistos:
        key = (v["born"], v["dz"])
        if key not in unicos or v["dist"] < unicos[key]["dist"]:
            unicos[key] = v
    if not unicos:
        print("  >>> NINGUNA zona tocable (cleared) a <=80pts del precio en +/-3h. El motor no habria visto nada ahi.")
    else:
        for v in sorted(unicos.values(), key=lambda x: x["dist"]):
            dz_txt = "LONG" if v["dz"] == 1 else "SHORT"
            coincide = (v["dz"] == 1 and t["dir"] == "LONG") or (v["dz"] == -1 and t["dir"] == "SHORT")
            bt = datetime.fromtimestamp(v["bar_time"], tz=timezone.utc).astimezone(NY)
            print(f"  >>> Zona {dz_txt} [{v['bot']:.2f}-{v['top']:.2f}] dist={v['dist']:.1f}pts "
                  f"disp_ratio={v['disp_ratio']:.2f} vol={v['vol_signal']:.0f} "
                  f"vista en {bt.strftime('%H:%M')} NY | {'COINCIDE DIRECCION' if coincide else 'DIRECCION CONTRARIA'}")
    print()
