import random, statistics, engine4 as e4
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
random.seed(20260909)

MORNING = dict(rr1=1.8, rr2=6.0, be_trigger_r=1.2, lock_r=1.0,
               session_start_min=180, session_end_min=660,
               disp_mult=2.5, liq_accum_bars=6, liq_tolerance_pts=4.0,
               entry_buffer_pts=12.0, sl_buffer_pts=2.0)
NIGHT = dict(rr1=1.8, rr2=7.0, be_trigger_r=0.8, lock_r=0.3,
             session_start_min=1080, session_end_min=1440,
             disp_mult=2.5, liq_accum_bars=15, liq_tolerance_pts=2.0,
             entry_buffer_pts=8.0, sl_buffer_pts=1.0)

bars = e4.load_bars()

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
raw_m = e4.select_trades(bars, **MORNING)
raw_n = e4.select_trades(bars, **NIGHT)

QTY = 4
p_m = e4.price_trades(raw_m, qty_tp1=0, qty_tp2=QTY)
p_n = e4.price_trades(raw_n, qty_tp1=0, qty_tp2=QTY)
p_m_f = [t for t in p_m if bias_at(bias_map, t["entry_time"]) == t["dir"]]
p_n_f = [t for t in p_n if bias_at(bias_map, t["entry_time"]) == t["dir"]]
combined = sorted(p_m_f + p_n_f, key=lambda t: t["entry_time"])

sep_dec = [t for t in combined if datetime.fromtimestamp(t["entry_time"], tz=timezone.utc).astimezone(NY).month in (9,10,11,12)]
pnls_sd = [t["pnl"] for t in sep_dec]
print(f"Pool Sep-Dic: {len(pnls_sd)} trades, net total ${sum(pnls_sd):,.0f}, avg/trade ${sum(pnls_sd)/len(pnls_sd):.2f}")

# Trades/semana tipico en esta temporada (para traducir a tiempo real)
n_seasons = 6  # 2020-2025 completos (2026 solo tiene 1 trade, se excluye del promedio de ritmo)
sep_dec_full_seasons = [t for t in sep_dec if datetime.fromtimestamp(t["entry_time"], tz=timezone.utc).astimezone(NY).year < 2026]
trades_per_season = len(sep_dec_full_seasons) / n_seasons
weeks_per_season = 17.3  # ~4 meses
trades_per_week = trades_per_season / weeks_per_season
print(f"Ritmo tipico: {trades_per_season:.1f} trades/temporada completa (~{trades_per_week:.2f} trades/semana)")

TARGET = 3000.0
MAX_LOSS = 1900.0
N_SIMS = 10000
BLOCK = 10
HORIZON = 500

def simulate(pnls, n_sims, block, target, max_loss_static, max_loss_trailing, horizon):
    n = len(pnls)
    results = []
    for _ in range(n_sims):
        equity = 0.0; peak = 0.0; trades_used = 0; outcome = "NEITHER"
        static_failed = trailing_failed = False
        while trades_used < horizon:
            start = random.randint(0, n - 1)
            for k in range(block):
                pnl = pnls[(start + k) % n]
                equity += pnl; trades_used += 1; peak = max(peak, equity)
                if equity <= -max_loss_static: static_failed = True
                if (peak - equity) >= max_loss_trailing: trailing_failed = True
                if equity >= target: outcome = "SUCCESS"; break
                if static_failed or trailing_failed: outcome = "FAIL"; break
                if trades_used >= horizon: break
            if outcome != "NEITHER": break
        results.append({"outcome": outcome, "trades": trades_used})
    return results

res_static = simulate(pnls_sd, N_SIMS, BLOCK, TARGET, MAX_LOSS, 10**9, HORIZON)
res_trail = simulate(pnls_sd, N_SIMS, BLOCK, TARGET, 10**9, MAX_LOSS, HORIZON)
ss = sum(1 for r in res_static if r["outcome"]=="SUCCESS")
fs = sum(1 for r in res_static if r["outcome"]=="FAIL")
st = sum(1 for r in res_trail if r["outcome"]=="SUCCESS")
ft = sum(1 for r in res_trail if r["outcome"]=="FAIL")
tr_s = sorted([r["trades"] for r in res_static if r["outcome"]=="SUCCESS"])

print(f"\n=== Probabilidad usando SOLO historico Sep-Dic, 4 contratos, limite $1900/$3000 ===")
print(f"ESTATICA: exito={100*ss/N_SIMS:.1f}%  fallo={100*fs/N_SIMS:.1f}%  otro={100*(N_SIMS-ss-fs)/N_SIMS:.1f}%")
print(f"TRAILING: exito={100*st/N_SIMS:.1f}%  fallo={100*ft/N_SIMS:.1f}%  otro={100*(N_SIMS-st-ft)/N_SIMS:.1f}%")
if tr_s:
    print(f"Trades hasta exito: mediana={statistics.median(tr_s):.0f}  p10={tr_s[len(tr_s)//10]:.0f}  p90={tr_s[9*len(tr_s)//10]:.0f}")
    med = statistics.median(tr_s)
    print(f"\nA ritmo de {trades_per_week:.2f} trades/semana en esta temporada:")
    print(f"  Mediana ({med:.0f} trades) -> ~{med/trades_per_week:.1f} semanas")
    p10 = tr_s[len(tr_s)//10]; p90 = tr_s[9*len(tr_s)//10]
    print(f"  Rango p10-p90: {p10:.0f}-{p90:.0f} trades -> ~{p10/trades_per_week:.1f} a {p90/trades_per_week:.1f} semanas")
