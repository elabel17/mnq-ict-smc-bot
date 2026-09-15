"""
Compara el precio de entrada que el usuario marco a mano (registro manual)
contra dos definiciones de "borde de la zona": el borde puro (mecha de la
vela de origen, modo 'mecha' -- sin buffer) y el borde+8pts (modo 'aire',
el que usa el backtest validado). Resultado: las entradas del usuario se
parecen mucho mas a 'mecha' que a 'aire' -- confirma que su ejecucion real
entra pegada al borde, sin el margen que el backtest asume como el unico
ejecutable. Ver docs/CLAUDE_SESSION_2026-09-08.md, sesion 2026-09-15, para
el contexto completo de esta comparacion.
"""
import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
bars = json.load(open("../../python/claude_ohlcv_15m_2020_2026.json"))
bars = [(b[0], b[1], b[2], b[3], b[4], b[5] if len(b) > 5 else 0) for b in bars]
bars.sort(key=lambda x: x[0])
n = len(bars)
opens=[b[1] for b in bars]; highs=[b[2] for b in bars]; lows=[b[3] for b in bars]
closes=[b[4] for b in bars]; times=[b[0] for b in bars]; vols=[b[5] for b in bars]

DISP_LEN, DISP_MULT, DISP_CLOSE_FRAC = 20, 1.5, 0.6
OB_SCAN_BARS, LIQ_CHECK_BARS, LIQ_TOL, LIQ_ACCUM = 10, 12, 4.0, 6
ZONE_MAX_AGE = 300
avg_range_cache = [None]*n

TRADES = [
  ("2025-09-18 20:15", "LONG", 24688.64),
  ("2025-09-19 15:15", "LONG", 24716.14),
  ("2025-09-22 07:30", "LONG", 24785.77),
  ("2025-09-22 09:15", "LONG", 24746.61),
  ("2025-09-23 19:30", "LONG", 24803.35),
  ("2025-09-24 16:00", "LONG", 24635.45),
  ("2025-09-25 00:45", "SHORT", 24766.31),
  ("2025-09-25 09:15", "LONG", 24725.16),
  ("2025-09-25 18:00", "LONG", 24525.16),
  ("2025-09-26 14:30", "LONG", 24625.04),
]
target_epochs = {tid: int(datetime.strptime(tid, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc).timestamp()) for tid,_,_ in TRADES}
VENTANA = 3*3600
resultados = {tid: [] for tid,_,_ in TRADES}
zones = []
lo_t = min(target_epochs.values()) - VENTANA*2
hi_t = max(target_epochs.values()) + VENTANA*2

for i in range(n):
    if times[i] < lo_t: continue
    if times[i] > hi_t: break
    if i >= DISP_LEN-1:
        s = sum(highs[k]-lows[k] for k in range(i-DISP_LEN+1, i+1))
        avg_range_cache[i] = s/DISP_LEN
    h,l,o,c = highs[i],lows[i],opens[i],closes[i]
    rng = h-l
    avg_prev = avg_range_cache[i-1] if i>=1 and avg_range_cache[i-1] else None
    is_disp = avg_prev is not None and rng >= DISP_MULT*avg_prev
    bull = is_disp and c>o and (c-l) >= DISP_CLOSE_FRAC*rng
    bear = is_disp and c<o and (h-c) >= DISP_CLOSE_FRAC*rng
    if bull:
        idx=-1
        for k in range(1,OB_SCAN_BARS+1):
            j=i-k
            if j<0: break
            if closes[j]<opens[j]: idx=k; break
        if idx!=-1:
            cand=lows[i-idx]; mx=cu=0
            for k in range(idx+1, idx+LIQ_CHECK_BARS+1):
                j=i-k
                if j<0: break
                if lows[j]<=cand+LIQ_TOL: cu+=1; mx=max(mx,cu)
                else: cu=0
            if mx<LIQ_ACCUM:
                zones.append(dict(dir=1, top=highs[i-idx], bot=cand, cleared=False, born=i))
    if bear:
        idx2=-1
        for k in range(1,OB_SCAN_BARS+1):
            j=i-k
            if j<0: break
            if closes[j]>opens[j]: idx2=k; break
        if idx2!=-1:
            cand=highs[i-idx2]; mx=cu=0
            for k in range(idx2+1, idx2+LIQ_CHECK_BARS+1):
                j=i-k
                if j<0: break
                if highs[j]>=cand-LIQ_TOL: cu+=1; mx=max(mx,cu)
                else: cu=0
            if mx<LIQ_ACCUM:
                zones.append(dict(dir=-1, top=cand, bot=lows[i-idx2], cleared=False, born=i))
    for z in zones:
        if z["born"]!=i and not z["cleared"]:
            if z["dir"]==1 and l>z["top"]: z["cleared"]=True
            elif z["dir"]==-1 and h<z["bot"]: z["cleared"]=True
    zones = [z for z in zones if (i-z["born"])<=ZONE_MAX_AGE]
    for tid in target_epochs:
        if abs(times[i]-target_epochs[tid]) <= VENTANA:
            for z in zones:
                if not z["cleared"]: continue
                resultados[tid].append(dict(z))

print(f"{'trade':>17} {'dir':>5} {'entrada':>10} | {'borde puro (mecha)':>19} {'dist':>7} | {'borde+8 (aire)':>15} {'dist':>7}")
for tid, d, precio in TRADES:
    vistos = resultados[tid]
    uniq = {}
    for v in vistos:
        k = (v["born"], v["dir"])
        uniq[k] = v
    dz_want = 1 if d=="LONG" else -1
    candidatos = [v for v in uniq.values() if v["dir"]==dz_want]
    if not candidatos:
        print(f"{tid:>17} {d:>5} {precio:>10.2f} | (sin zona coincidente en esa direccion)")
        continue
    mejor = min(candidatos, key=lambda v: abs(precio - (v["top"] if dz_want==1 else v["bot"])))
    borde_puro = mejor["top"] if dz_want==1 else mejor["bot"]
    borde_aire = borde_puro + 8 if dz_want==1 else borde_puro - 8
    print(f"{tid:>17} {d:>5} {precio:>10.2f} | {borde_puro:>19.2f} {abs(precio-borde_puro):>7.2f} | {borde_aire:>15.2f} {abs(precio-borde_aire):>7.2f}")
