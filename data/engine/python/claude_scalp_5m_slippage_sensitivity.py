"""
Sensibilidad del resultado de scalping 5m a supuestos de slippage MAS
REALISTAS que el 1 tick usado hasta ahora. Con un stop de 2 ticks
(0.5pts), 1 tick de slippage ya es el 50% del stop -- si el slippage
real es mayor (probable a esta frecuencia/precision), el resultado
cambia sustancialmente. No se re-selecciona ningun trade, solo se
recalcula el PnL en dolares con distintos supuestos de slippage.
"""
import json, claude_engine5 as e5

bars = e5.load_bars(filename="../../python/claude_ohlcv_5m_2024_2026.json")

def build_1h_bias(bars, sma_len=10):
    groups = {}
    for b in bars:
        t = b[0]; bucket = t - (t % 3600)
        groups.setdefault(bucket, []).append(b)
    buckets_sorted = sorted(groups.keys())
    closes_1h = [sorted(groups[bk], key=lambda x: x[0])[-1][4] for bk in buckets_sorted]
    sma = [None]*len(closes_1h)
    for i in range(len(closes_1h)):
        if i >= sma_len-1: sma[i] = sum(closes_1h[i-sma_len+1:i+1])/sma_len
    return {bk: (0 if sma[i] is None else (1 if closes_1h[i] > sma[i] else -1)) for i, bk in enumerate(buckets_sorted)}

def bias_at(m, t): return m.get(t - (t % 3600), 0)

bias_map = build_1h_bias(bars, sma_len=10)
FOUND = json.load(open("claude_scalp_5m_found.json"))
params = dict(rr1=1.8, lock_r=FOUND["lock_r"], session_start_min=180, session_end_min=660)
params.update(FOUND)

raw = e5.select_trades(bars, **params)  # la SELECCION de trades no depende del slippage

print("Sensibilidad a slippage (4 contratos, filtro 1H, historico completo 2.6 anios):\n")
print(f"{'Slippage (ticks)':>18s} {'Net':>14s} {'PF':>6s} {'DD':>10s} {'avg/trade':>10s}  {'vs 1 tick':>10s}")

results = {}
for slip_ticks in [1, 2, 3, 4, 5]:
    e5.SLIPPAGE_TICKS = slip_ticks
    priced = e5.price_trades(raw, qty_tp1=0, qty_tp2=4)
    p_bias = [t for t in priced if bias_at(bias_map, t["entry_time"]) == t["dir"]]
    r = e5.summarize(p_bias, silent=True)
    results[slip_ticks] = r
    ref = results[1]["net"]
    delta = 100*(r["net"]-ref)/ref if slip_ticks > 1 else 0
    print(f"{slip_ticks:>18d} ${r['net']:>12,.0f} {r['pf']:>6.2f} ${r['max_dd']:>9,.0f} "
          f"${r['net']/r['trades']:>9.2f}  {delta:>+9.1f}%")

# tambien con comision mas alta (broker real puede cobrar mas que $0.47/lado)
print("\nSensibilidad a COMISION (manteniendo slippage=1 tick):")
e5.SLIPPAGE_TICKS = 1
for comm in [0.47, 1.00, 2.00, 3.00]:
    e5.COMMISSION_PER_CONTRACT_SIDE = comm
    priced = e5.price_trades(raw, qty_tp1=0, qty_tp2=4)
    p_bias = [t for t in priced if bias_at(bias_map, t["entry_time"]) == t["dir"]]
    r = e5.summarize(p_bias, silent=True)
    print(f"  ${comm:.2f}/contrato/lado: net=${r['net']:,.0f} PF={r['pf']:.2f}")

# combinado: slippage realista (2 ticks) + comision mas alta ($1.00)
print("\nCombinado (2 ticks slippage + $1.00 comision, escenario 'realista conservador'):")
e5.SLIPPAGE_TICKS = 2
e5.COMMISSION_PER_CONTRACT_SIDE = 1.00
priced = e5.price_trades(raw, qty_tp1=0, qty_tp2=4)
p_bias = [t for t in priced if bias_at(bias_map, t["entry_time"]) == t["dir"]]
r = e5.summarize(p_bias, silent=True)
print(f"  net=${r['net']:,.0f} PF={r['pf']:.2f} DD=${r['max_dd']:,.0f} WR={100*r['winrate']:.1f}%")

# anualizar para comparar contra 15m de forma justa
years = 2.6
print(f"\nGanancia ANUALIZADA (/{years} anios) en el escenario realista conservador: ${r['net']/years:,.0f}/anio")
