"""
Hipotesis del usuario (2026-09-14): tras 2 trades reales positivos hoy con
OBs de mas de 40 puntos de rango, sospecha que agregar un buffer de entrada
extra (12-15 pips) sobre esas zonas anchas podria dar "mayor captacion"
(mas fills / mejor resultado). Se prueba con el motor causal (v_nivel.py,
entry_mode='aire', el unico ejecutable), sobre el histórico real de 5m.

zone_width y entry_buffer_pts ya estan trackeados/parametrizados en el
motor, no hace falta instrumentar nada nuevo para esta prueba especifica.
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
BASE.update(dict(rr2=4.0, be_trigger_r=0.6, sl_buffer_pts=4.0))
QTY = 4

print("=" * 100)
print("1) ¿Las zonas ANCHAS (>40 pts) ya rinden distinto a las angostas, con el buffer actual (8pts)?")
print("=" * 100)
raw = V.sel_real(bars, entry_mode='aire', **BASE)
pr = V.price_trades(raw, 0, QTY)
anchas = [t for t in pr if t["zone_width"] > 40]
angostas = [t for t in pr if t["zone_width"] <= 40]
for nombre, grupo in [("ANCHAS (>40pts)", anchas), ("angostas (<=40pts)", angostas)]:
    a = V.summarize([t for t in grupo if t["entry_time"] < corte], silent=True)
    b = V.summarize([t for t in grupo if t["entry_time"] >= corte], silent=True)
    r = V.summarize(grupo, silent=True)
    print(f"{nombre:>20}: {r['trades']:>5,} ops  net ${r['net']:>10,.0f}  PF {r['pf']:>5.2f}  "
          f"DD ${r['max_dd']:>8,.0f}  WR {100*r['winrate']:>5.1f}% | PF mitades {a['pf']:.2f}/{b['pf']:.2f}")

print("\n" + "=" * 100)
print("2) Barrido de entry_buffer_pts (8 actual -> 10/12/14/15/16/20), TODAS las zonas")
print("=" * 100)
print(f"{'buffer':>8} {'ops':>6} {'net':>12} {'PF':>6} {'DD':>10} {'WR':>7} | {'PF 1a':>6} {'PF 2a':>6}")
for buf in [8.0, 10.0, 12.0, 14.0, 15.0, 16.0, 20.0]:
    p = dict(BASE); p["entry_buffer_pts"] = buf
    raw_b = V.sel_real(bars, entry_mode='aire', **p)
    pr_b = V.price_trades(raw_b, 0, QTY)
    a = V.summarize([t for t in pr_b if t["entry_time"] < corte], silent=True)
    b = V.summarize([t for t in pr_b if t["entry_time"] >= corte], silent=True)
    r = V.summarize(pr_b, silent=True)
    print(f"{buf:>7.0f}p {r['trades']:>6,} ${r['net']:>10,.0f} {r['pf']:>6.2f} ${r['max_dd']:>8,.0f} "
          f"{100*r['winrate']:>6.1f}% | {a['pf']:>5.2f} {b['pf']:>5.2f}")

print("\n" + "=" * 100)
print("3) LA PRUEBA CLAVE: mismo barrido de buffer, pero SOLO sobre zonas anchas (>40pts)")
print("   (la hipotesis especifica del usuario: buffer extra AYUDA MAS en zonas anchas?)")
print("=" * 100)
print(f"{'buffer':>8} {'ops':>6} {'net':>12} {'PF':>6} {'DD':>10} {'WR':>7} | {'PF 1a':>6} {'PF 2a':>6}")
for buf in [8.0, 10.0, 12.0, 14.0, 15.0, 16.0, 20.0]:
    p = dict(BASE); p["entry_buffer_pts"] = buf
    raw_b = V.sel_real(bars, entry_mode='aire', **p)
    pr_b = V.price_trades(raw_b, 0, QTY)
    anchas_b = [t for t in pr_b if t["zone_width"] > 40]
    if len(anchas_b) < 20:
        print(f"{buf:>7.0f}p  (muy pocas zonas anchas, <20, se omite)")
        continue
    a = V.summarize([t for t in anchas_b if t["entry_time"] < corte], silent=True)
    b = V.summarize([t for t in anchas_b if t["entry_time"] >= corte], silent=True)
    r = V.summarize(anchas_b, silent=True)
    print(f"{buf:>7.0f}p {r['trades']:>6,} ${r['net']:>10,.0f} {r['pf']:>6.2f} ${r['max_dd']:>8,.0f} "
          f"{100*r['winrate']:>6.1f}% | {a['pf']:>5.2f} {b['pf']:>5.2f}")
