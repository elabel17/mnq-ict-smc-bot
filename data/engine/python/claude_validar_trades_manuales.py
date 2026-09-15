"""
Cruza los trades registrados manualmente por el usuario (Artifact
'registro_manual.html', coleccion manual_trades) contra el motor causal
(v_nivel.py) para ver si un script habria tomado la misma decision --
misma direccion, zona detectada cerca del mismo precio y hora.

IMPORTANTE: el usuario registro estos trades a horas MUY distintas (16:15,
05:15, 15:30, 12:00, 20:45 NY, etc.), no solo dentro de la ventana
03:00-11:00 NY que validamos como la mejor sesion. Por eso aqui se corre
SIN filtro de sesion (0-1440, todo el dia) -- el objetivo no es replicar
el backtest validado, es ver si la LOGICA DE DETECCION (no el filtro de
horario) habria visto lo mismo que el usuario vio a ojo.
"""
import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import v_nivel as V

NY = ZoneInfo("America/New_York")

bars = V.load_bars(filename="../../python/claude_ohlcv_15m_2020_2026.json")

TRADES = [
    dict(id="2025-09-18 20:15 UTC", dir="LONG", precio=24688.64, sl=24624,
         nota="Liquidez superior, OB con FVG previo, llego a ~24880 (~3R)", resultado="GANADOR"),
    dict(id="2025-09-22 09:15 UTC", dir="LONG", precio=24746.61, sl=24727,
         nota="OB reaccionando con FVG, liquidez superior lista", resultado="GANADOR (min 1:2)"),
    dict(id="2025-09-23 19:30 UTC", dir="LONG", precio=24803.35, sl=24768,
         nota="OB de reaccion + FVG, liquidez pendiente arriba", resultado="GANADOR (min 1:2)"),
    dict(id="2025-09-24 16:00 UTC", dir="LONG", precio=24635.45, sl=24645,
         nota="AUTOFLAGEADO DEBIL: liquidez abajo en contra, OB de reaccion SIN FVG", resultado="PERDEDOR (SL)"),
    dict(id="2025-09-25 00:45 UTC", dir="SHORT", precio=24766.31, sl=24794,
         nota="OB de rompimiento + decisional con FVG limpio, sin soporte abajo", resultado="parece GANADOR"),
    dict(id="2025-09-25 09:15 UTC", dir="LONG", precio=24725.16, sl=24710,
         nota="AUTOFLAGEADO DEBIL: 'OB de mala calidad', tomado por apertura de sesion igual", resultado="PERDEDOR (SL, 'el mercado no respeto')"),
    dict(id="2025-09-25 18:00 UTC", dir="LONG", precio=24525.16, sl=None,
         nota="OB con FVG recien tomado, liquidez cercana arriba", resultado="min 1:2 (sin SL explicito)"),
]

# motor causal SIN filtro de sesion (0-1440 = todo el dia) -- parametros de
# deteccion validados (los mismos que usa el 15m real), solo se abre la
# ventana horaria para poder comparar cualquier hora que el usuario opero
params = dict(rr1=1.8, rr2=5.0, be_trigger_r=1.2, lock_r=1.0,
              session_start_min=0, session_end_min=1440,
              disp_len=20, disp_mult=1.5, disp_close_frac=0.6,
              ob_scan_bars=10, liq_check_bars=12, liq_tolerance_pts=4.0,
              liq_accum_bars=6, zone_max_age=300, max_zones=40,
              sl_buffer_pts=2.0, entry_buffer_pts=12.0)

raw = V.sel_real(bars, entry_mode='aire', **params)
times = [b[0] for b in bars]

print(f"{len(raw)} operaciones que el motor SI habria tomado (sin filtro de sesion), 2020-2026\n")

for t in TRADES:
    dt_utc = datetime.strptime(t["id"].replace(" UTC", ""), "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
    dt_ny = dt_utc.astimezone(NY)
    epoch = int(dt_utc.timestamp())

    # 1) el motor tomo ALGUN trade en una ventana de +/- 2 horas de ese momento?
    ventana = 2 * 3600
    cercanos = [r for r in raw if abs(r["entry_time"] - epoch) <= ventana]

    print("=" * 100)
    print(f"{t['id']} (hora NY: {dt_ny.strftime('%Y-%m-%d %H:%M')}) -- {t['dir']} @ {t['precio']}"
          f"{'  SL ' + str(t['sl']) if t['sl'] else ''}")
    print(f"  Nota del usuario: {t['nota']}")
    print(f"  Resultado reportado: {t['resultado']}")
    if not cercanos:
        print("  >>> El motor NO detecto ninguna entrada propia en +/-2h de ese momento.")
    else:
        for r in cercanos:
            rdt = datetime.fromtimestamp(r["entry_time"], tz=timezone.utc).astimezone(NY)
            coincideDir = (r["dir"] == 1 and t["dir"] == "LONG") or (r["dir"] == -1 and t["dir"] == "SHORT")
            print(f"  >>> Motor: {'LONG' if r['dir']==1 else 'SHORT'} @ {r['entry']:.2f} "
                  f"({rdt.strftime('%H:%M')} NY, {(r['entry_time']-epoch)/60:+.0f} min vs tu entrada) "
                  f"| zone_width={r['zone_width']:.1f} disp_ratio={r['disp_ratio']:.2f} "
                  f"vol_signal={r['vol_signal']:.0f} zone_age={r['zone_age']} "
                  f"| {'MISMA DIRECCION' if coincideDir else 'DIRECCION CONTRARIA'}")
    print()
