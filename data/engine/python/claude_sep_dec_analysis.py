import engine4 as e4
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")

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

e4.summarize(combined, f"Referencia historico completo, {QTY} contratos, filtro 1H")

# ---------------- Desglose por mes calendario (todos los anios) ----------------
print(f"\n{'='*80}\nRESULTADO POR MES CALENDARIO (todos los anios 2020-2026, {QTY} contratos)\n{'='*80}")
meses = ["", "Enero","Febrero","Marzo","Abril","Mayo","Junio","Julio","Agosto",
         "Septiembre","Octubre","Noviembre","Diciembre"]
by_month = {}
for t in combined:
    dt = datetime.fromtimestamp(t["entry_time"], tz=timezone.utc).astimezone(NY)
    by_month.setdefault(dt.month, []).append(t)

for m in range(1, 13):
    trades = by_month.get(m, [])
    if not trades:
        continue
    net = sum(t["pnl"] for t in trades)
    wins = sum(1 for t in trades if t["pnl"] > 0)
    years_present = len(set(datetime.fromtimestamp(t["entry_time"], tz=timezone.utc).astimezone(NY).year for t in trades))
    avg_per_year = net / years_present
    print(f"  {meses[m]:12s}: {len(trades):4d} trades  net_total(todos los anios)=${net:>9,.0f}  "
          f"WR={100*wins/len(trades):.1f}%  anios con datos={years_present}  promedio/anio=${avg_per_year:>8,.0f}")

# ---------------- Sep-Oct-Nov-Dic especificamente ----------------
sep_dec_trades = [t for t in combined if datetime.fromtimestamp(t["entry_time"], tz=timezone.utc).astimezone(NY).month in (9,10,11,12)]
print(f"\n{'='*80}\nSEPTIEMBRE-OCTUBRE-NOVIEMBRE-DICIEMBRE (todos los anios combinados)\n{'='*80}")
r_sd = e4.summarize(sep_dec_trades, "Sep-Oct-Nov-Dic, todos los anios juntos")

# por anio individual, para ver dispersion real
years = sorted(set(datetime.fromtimestamp(t["entry_time"], tz=timezone.utc).astimezone(NY).year for t in sep_dec_trades))
print("\nPor anio (Sep-Dic de cada anio):")
for y in years:
    yr_trades = [t for t in sep_dec_trades if datetime.fromtimestamp(t["entry_time"], tz=timezone.utc).astimezone(NY).year == y]
    if not yr_trades: continue
    net_y = sum(t["pnl"] for t in yr_trades)
    wr_y = sum(1 for t in yr_trades if t["pnl"]>0)/len(yr_trades)
    print(f"  {y}: {len(yr_trades)} trades  net=${net_y:,.0f}  WR={100*wr_y:.1f}%")

avg_net_per_season = sum(sum(t["pnl"] for t in [tt for tt in sep_dec_trades if datetime.fromtimestamp(tt["entry_time"], tz=timezone.utc).astimezone(NY).year==y]) for y in years) / len(years)
print(f"\nPromedio de ganancia neta por temporada Sep-Dic (un anio completo de esos 4 meses): ${avg_net_per_season:,.0f}")
