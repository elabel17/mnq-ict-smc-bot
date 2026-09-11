"""Busqueda contra v_causal.py — el UNICO motor que reproduce el replay real.
Los parametros actuales se optimizaron contra motores con look-ahead: estan
calibrados para un juego que no existe. Esta es la primera busqueda honesta."""
import json, itertools
import claude_engine5 as e5, v_causal as V
bars = e5.load_bars(filename="../../python/claude_ohlcv_5m_2024_2026.json")
F = json.load(open("claude_scalp_5m_found.json"))
V.SLIPPAGE_TICKS = 2; V.COMMISSION_PER_CONTRACT_SIDE = 1.00
corte = bars[len(bars)//2][0]

def corre(dm, buf, zma, rr2, be, lk, ventanas):
    out = []
    for i, f in ventanas:
        p = dict(rr1=1.8, session_start_min=i*60, session_end_min=f*60); p.update(F)
        p.update(disp_mult=dm, entry_buffer_pts=buf, rr2=rr2, zone_max_age=zma,
                 max_risk_pts=100.0, use_risk_cap=True, liq_accum_bars=15,
                 sl_buffer_pts=0.5, be_trigger_r=be, lock_r=lk)
        out += V.sel_causal(bars, entry_mode='aire', **p)
    return sorted(V.price_trades(out, 0, 3), key=lambda x: x['entry_time'])

res = []
for dm, buf, zma, rr2 in itertools.product([1.5,2.0,2.5,3.0],[4.,8.,12.,16.,20.],[3,10,30,60],[3.0,5.0]):
    pr = corre(dm, buf, zma, rr2, 0.6, 0.5, [(9,11),(2,6)])
    if len(pr) < 300: continue
    a = V.summarize([t for t in pr if t['entry_time'] <  corte], silent=True)
    b = V.summarize([t for t in pr if t['entry_time'] >= corte], silent=True)
    t = V.summarize(pr, silent=True)
    res.append((min(a['pf'],b['pf']), dm, buf, zma, rr2, t, a, b))
res.sort(key=lambda x: -x[0])
print("{:>4} {:>4} {:>5} {:>4} | {:>6} {:>10} {:>5} {:>9} {:>6} | {:>5} {:>5}".format(
    "disp","buf","edad","RR2","ops","net","PF","DD","WR","PF_1a","PF_2a"))
for mn,dm,buf,zma,rr2,t,a,b in res[:15]:
    print("{:>4.1f} {:>4.0f} {:>5} {:>4.1f} | {:>6,} {:>10} {:>5.2f} {:>9} {:>5.1f}% | {:>5.2f} {:>5.2f}".format(
        dm,buf,zma,rr2,t['trades'],"${:,.0f}".format(t['net']),t['pf'],
        "${:,.0f}".format(t['max_dd']),100*t['winrate'],a['pf'],b['pf']))
