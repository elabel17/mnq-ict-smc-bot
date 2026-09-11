"""Etapa 2: parametros que deciden QUE setups califican, no como se gestionan.
El objetivo no es mas operaciones sino mejores: se ordena por PF y se exige
que aguante en las dos mitades del historico."""
import json, itertools
import claude_engine5 as e5, v_real

bars = e5.load_bars(filename="../../python/claude_ohlcv_5m_2024_2026.json")
F = json.load(open("claude_scalp_5m_found.json"))
v_real.SLIPPAGE_TICKS = 2; v_real.COMMISSION_PER_CONTRACT_SIDE = 1.00
corte = bars[len(bars)//2][0]

grid = dict(
    disp_mult         = [1.5, 2.0, 2.5, 3.0],
    liq_tolerance_pts = [1.0, 2.0, 4.0],
    liq_accum_bars    = [6, 10, 15],
    zone_max_age      = [60, 150, 300],
    max_risk_pts      = [40.0, 60.0, 100.0],
)
claves = list(grid); res = []
for combo in itertools.product(*[grid[k] for k in claves]):
    p = dict(rr1=1.8, session_start_min=180, session_end_min=660); p.update(F)
    p.update(dict(zip(claves, combo))); p["use_risk_cap"] = True
    pr = v_real.price_trades(v_real.sel_real(bars, **p), 0, 3)
    if len(pr) < 200: continue
    a = v_real.summarize([t for t in pr if t["entry_time"] <  corte], silent=True)
    b = v_real.summarize([t for t in pr if t["entry_time"] >= corte], silent=True)
    t = v_real.summarize(pr, silent=True)
    res.append(dict(zip(claves, combo)) | dict(ops=t['trades'], net=t['net'], pf=t['pf'],
        dd=t['max_dd'], wr=t['winrate'], pf_a=a['pf'], pf_b=b['pf']))

ok = [r for r in res if r['pf_a'] > 1.2 and r['pf_b'] > 1.2]
ok.sort(key=lambda r: -min(r['pf_a'], r['pf_b']))
print("{} probadas, {} rentables en ambas mitades\n".format(len(res), len(ok)))
print("{:>5} {:>5} {:>5} {:>5} {:>6} | {:>6} {:>10} {:>5} {:>8} {:>6} | {:>5} {:>5}".format(
    "disp","liqT","liqA","edad","rCap","ops","net","PF","DD","WR","PF_1a","PF_2a"))
for r in ok[:20]:
    print("{:>5.1f} {:>5.1f} {:>5} {:>5} {:>6.0f} | {:>6,} {:>10} {:>5.2f} {:>8} {:>5.1f}% | {:>5.2f} {:>5.2f}".format(
        r['disp_mult'], r['liq_tolerance_pts'], r['liq_accum_bars'], r['zone_max_age'],
        r['max_risk_pts'], r['ops'], "${:,.0f}".format(r['net']), r['pf'],
        "${:,.0f}".format(r['dd']), 100*r['wr'], r['pf_a'], r['pf_b']))
json.dump(res, open("busqueda_calidad.json","w"))
