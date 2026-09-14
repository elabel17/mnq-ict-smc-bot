"""
Dos preguntas del usuario, respondidas con el motor causal validado
(v_nivel.py / entry_mode='aire' es el unico ejecutable de verdad, ver
README.md de este directorio):

1) "diferentes OB, proyecciones de ejecucion, cual resulta mejor" ->
   compara los 4 modos de proyectar el precio de entrada sobre el OB
   (aire/mecha/cuerpo/medio), con holdout de dos mitades.

2) "puedes usar varios factores... para hacer algo incluso mejor" (el
   score de fuerza que se agrego al Pine) -> prueba si ese mismo score
   (volumen de la vela disparadora + cuanto se paso del umbral de
   desplazamiento) predice trades mejores en el HISTORICO REAL, no solo
   en la intuicion visual. Solo se pueden reconstruir 2 de los 5
   factores del Pine con lo que este motor ya registra por trade
   (vol_signal, disp_ratio) -- liquidez/FVG/sesgo-1H no estan
   trackeados aqui, se nota explicitamente.

Dataset: mismo de siempre (185.066 velas 5m, 2024-01-28 a 2026-09-08).
Supuestos conservadores: 2 ticks slippage, $1.00/contrato/lado, 4 contratos.
"""
import json
import v_nivel as V

V.SLIPPAGE_TICKS = 2
V.COMMISSION_PER_CONTRACT_SIDE = 1.00

bars = V.load_bars(filename="../../python/claude_ohlcv_5m_2024_2026.json")
corte = bars[len(bars) // 2][0]

F = json.load(open("claude_scalp_5m_found.json"))
BASE = dict(rr1=1.8, session_start_min=180, session_end_min=660)
BASE.update(F)
# mejor config de gestion encontrada en la busqueda causal de 450 combos
# (busqueda_causal.json), la unica que se sostiene en las dos mitades
BASE.update(dict(entry_buffer_pts=8.0, rr2=4.0, be_trigger_r=0.6, sl_buffer_pts=4.0))

QTY = 4

print("=" * 96)
print("1) COMPARACION DE PROYECCIONES DE ENTRADA SOBRE EL OB (entry_mode)")
print("=" * 96)
print(f"{'modo':>8} {'ops':>6} {'net':>12} {'PF':>6} {'DD':>10} {'WR':>7} | {'PF 1a mitad':>11} {'PF 2a mitad':>11}")
resultados_modo = {}
for modo in ["aire", "mecha", "cuerpo", "medio"]:
    raw = V.sel_real(bars, entry_mode=modo, **BASE)
    pr = V.price_trades(raw, 0, QTY)
    a = V.summarize([t for t in pr if t["entry_time"] < corte], silent=True)
    b = V.summarize([t for t in pr if t["entry_time"] >= corte], silent=True)
    t = V.summarize(pr, silent=True)
    resultados_modo[modo] = (raw, pr, t)
    print(f"{modo:>8} {t['trades']:>6,} ${t['net']:>10,.0f} {t['pf']:>6.2f} ${t['max_dd']:>8,.0f} "
          f"{100*t['winrate']:>6.1f}% | {a['pf']:>10.2f} {b['pf']:>11.2f}")

print("\n'aire' es el UNICO ejecutable en la realidad (orden limite fuera de la mecha,")
print("la unica que un broker puede llenar sin que ya se conozca el extremo de la vela).")
print("Los demas se muestran solo de referencia/comparacion, no son operables.")

# ======================================================================
# 2) SCORE DE FUERZA (volumen + desplazamiento) -- prueba con datos reales
# ======================================================================
print("\n" + "=" * 96)
print("2) SCORE DE FUERZA (volumen+desplazamiento) vs RESULTADO REAL, sobre 'aire'")
print("=" * 96)

raw_aire, pr_aire, t_aire = resultados_modo["aire"]

DISP_LEN = BASE.get("disp_len", 20)
# volumen promedio movil sobre las velas del dataset, mismo criterio que
# el Pine: SMA(volume, disp_len) desplazado 1 vela (no incluye la vela actual)
times = [b[0] for b in bars]
vols = [b[5] for b in bars]
time_to_idx = {t: i for i, t in enumerate(times)}
avg_vol_cache = {}


def avg_vol_en(i):
    if i in avg_vol_cache:
        return avg_vol_cache[i]
    if i < DISP_LEN:
        avg_vol_cache[i] = None
        return None
    s = sum(vols[i - DISP_LEN:i])
    v = s / DISP_LEN
    avg_vol_cache[i] = v
    return v


DISP_MULT = BASE["disp_mult"]


def vol_score(ratio):
    return max(0.0, min(100.0, (ratio - 1.0) / 2.0 * 100))


def rng_score(ratio):
    return max(0.0, min(100.0, (ratio - DISP_MULT) / DISP_MULT * 100))


scored = []
for rt, pt in zip(raw_aire, pr_aire):
    ib = rt["entry_bar"]
    av = avg_vol_en(ib)
    if av is None or av <= 0:
        continue
    vr = rt["vol_signal"] / av
    rr = rt["disp_ratio"]
    vs = vol_score(vr)
    rs = rng_score(rr)
    score = round((vs + rs) / 2)
    pt2 = dict(pt)
    pt2["fuerza"] = score
    scored.append(pt2)

print(f"{len(scored):,} de {len(pr_aire):,} operaciones pudieron puntuarse "
      f"(las primeras {DISP_LEN} velas del dataset no tienen promedio de volumen valido)")

print(f"\n{'fuerza minima':>14} {'ops':>6} {'net':>12} {'PF':>6} {'DD':>10} {'WR':>7} "
      f"| {'PF 1a mitad':>11} {'PF 2a mitad':>11}")
for umbral in [0, 10, 20, 30, 40, 50, 60, 70]:
    sub = [t for t in scored if t["fuerza"] >= umbral]
    if len(sub) < 30:
        print(f"{umbral:>13}% {'(muy pocas operaciones, <30, se omite)':>70}")
        continue
    a = V.summarize([t for t in sub if t["entry_time"] < corte], silent=True)
    b = V.summarize([t for t in sub if t["entry_time"] >= corte], silent=True)
    r = V.summarize(sub, silent=True)
    print(f"{umbral:>13}% {r['trades']:>6,} ${r['net']:>10,.0f} {r['pf']:>6.2f} ${r['max_dd']:>8,.0f} "
          f"{100*r['winrate']:>6.1f}% | {a['pf']:>10.2f} {b['pf']:>11.2f}")

# correlacion simple: promedio de PnL por decil de fuerza (sin definir un
# umbral, solo ver si la relacion es monotona o es ruido)
print("\nPnL promedio por decil de fuerza (10=mas fuerte), para ver si hay relacion real:")
scored_sorted = sorted(scored, key=lambda t: t["fuerza"])
n = len(scored_sorted)
for d in range(10):
    lo = n * d // 10
    hi = n * (d + 1) // 10
    grupo = scored_sorted[lo:hi]
    if not grupo:
        continue
    avg_pnl = sum(t["pnl"] for t in grupo) / len(grupo)
    avg_fuerza = sum(t["fuerza"] for t in grupo) / len(grupo)
    wr = sum(1 for t in grupo if t["pnl"] > 0) / len(grupo)
    print(f"  decil {d+1:>2} (fuerza ~{avg_fuerza:>5.1f}%): {len(grupo):>5,} ops, "
          f"avg PnL/trade ${avg_pnl:>7.2f}, WR {100*wr:>5.1f}%")

print("\nNota honesta: liquidez (barrido reciente), confluencia FVG y sesgo de 1H --")
print("los otros 3 factores del score del Pine -- NO estan trackeados en este motor")
print("Python todavia. Esto solo valida la mitad del score (volumen+desplazamiento).")
print("Para probar el score completo de 5 factores habria que instrumentar v_nivel.py")
print("igual que se hizo en el Pine, un trabajo aparte si el resultado de aqui lo amerita.")
