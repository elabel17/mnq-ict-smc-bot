"""Busqueda de parametros contra el motor CAUSAL (v_real), el unico que
reproduce lo que NinjaTrader ejecuta de verdad. Cada configuracion se mide
por separado en la primera y la segunda mitad del historico: si solo funciona
en una, es ajuste a la muestra y se descarta."""
import json, itertools, datetime as dt
import claude_engine5 as e5, v_real

bars = e5.load_bars(filename="../../python/claude_ohlcv_5m_2024_2026.json")
F = json.load(open("claude_scalp_5m_found.json"))
v_real.SLIPPAGE_TICKS = 2; v_real.COMMISSION_PER_CONTRACT_SIDE = 1.00
corte = bars[len(bars)//2][0]

grid = dict(
    entry_buffer_pts = [4.0, 6.0, 8.0, 10.0, 12.0, 16.0],
    rr2              = [2.0, 2.5, 3.0, 4.0, 5.0],
    be_trigger_r     = [0.6, 1.0, 1.5, 2.0, 99.0],   # 99 = BE desactivado
    sl_buffer_pts    = [0.5, 2.0, 4.0],
)
claves = list(grid)
res = []
for combo in itertools.product(*[grid[k] for k in claves]):
    p = dict(rr1=1.8, session_start_min=180, session_end_min=660); p.update(F)
    p.update(dict(zip(claves, combo)))
    pr = v_real.price_trades(v_real.sel_real(bars, **p), 0, 3)
    if len(pr) < 400: continue
    a = v_real.summarize([t for t in pr if t["entry_time"] <  corte], silent=True)
    b = v_real.summarize([t for t in pr if t["entry_time"] >= corte], silent=True)
    t = v_real.summarize(pr, silent=True)
    res.append(dict(zip(claves, combo)) | dict(
        ops=t['trades'], net=t['net'], pf=t['pf'], dd=t['max_dd'], wr=t['winrate'],
        pf_a=a['pf'], pf_b=b['pf'], net_a=a['net'], net_b=b['net'], dd_b=b['max_dd']))

# solo lo que funciona en LAS DOS mitades
ok = [r for r in res if r['pf_a'] > 1.15 and r['pf_b'] > 1.15]
ok.sort(key=lambda r: -min(r['pf_a'], r['pf_b']))
print("{} configuraciones probadas, {} rentables en ambas mitades\n".format(len(res), len(ok)))
print("{:>4} {:>4} {:>5} {:>4} | {:>6} {:>10} {:>5} {:>8} {:>6} | {:>5} {:>5}".format(
    "buf","RR2","BE","slB","ops","net","PF","DD","WR","PF_1a","PF_2a"))
for r in ok[:20]:
    print("{:>4.0f} {:>4.1f} {:>5.1f} {:>4.1f} | {:>6,} {:>10} {:>5.2f} {:>8} {:>5.1f}% | {:>5.2f} {:>5.2f}".format(
        r['entry_buffer_pts'], r['rr2'], r['be_trigger_r'], r['sl_buffer_pts'],
        r['ops'], "${:,.0f}".format(r['net']), r['pf'], "${:,.0f}".format(r['dd']),
        100*r['wr'], r['pf_a'], r['pf_b']))
json.dump(res, open("busqueda_causal.json","w"))
