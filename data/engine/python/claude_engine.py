"""
Motor de backtest que replica EXACTAMENTE la logica de
"ICT 15M OB Entry v15 - multi-zona" (Pine v6), bar por bar.

Fuente: leida directamente del editor de Pine via MCP el 2026-09-08,
script id USER;8f652c4b1fd5403b918416fd4587f7e2, version 40.

Parametros identicos a los defaults del script real.
"""
import json, os, sys
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

SCRATCHDIR = r"C:\Users\ABEL~1.DIA\AppData\Local\Temp\claude\C--Users-ABEL-DIAZ-Documents-cache\6cdd0fc2-2293-4b2f-b0a9-dc3487b369e4\scratchpad"

# ---------------- Parametros (identicos al script real) ----------------
DISP_LEN = 20
DISP_MULT = 2.5
DISP_CLOSE_FRAC = 0.6
OB_SCAN_BARS = 10
LIQ_CHECK_BARS = 12
LIQ_TOLERANCE_PTS = 4.0
LIQ_ACCUM_BARS = 6
ZONE_MAX_AGE = 300
MAX_ZONES = 40
SL_BUFFER_PTS = 2.0
ENTRY_BUFFER_PTS = 12.0
RR1 = 1.8
RR2 = 4.0
USE_RISK_CAP = True
MAX_RISK_PTS = 100.0
BE_TRIGGER_R = 1.2
LOCK_R = 0.8  # actualizado 2026-09-08 (era 0.5R)
USE_SESSION_FILTER = True

POINT_VALUE = 2.0       # USD por punto por contrato, MNQ
QTY = 3                 # contratos por operacion
TICK = 0.25             # tamano de tick MNQ
SLIPPAGE_TICKS = 1
COMMISSION_PER_CONTRACT_SIDE = 0.47  # supuesto, ajustable

NY = ZoneInfo("America/New_York")


def load_bars():
    path = os.path.join(SCRATCHDIR, "merged_ohlcv.json")
    raw = json.load(open(path, encoding="utf-8"))
    # cada bar: [time, open, high, low, close, volume]
    bars = []
    for b in raw:
        t, o, h, l, c = b[0], b[1], b[2], b[3], b[4]
        bars.append((t, o, h, l, c))
    bars.sort(key=lambda x: x[0])
    return bars


class Zone:
    __slots__ = ("dir", "top", "bot", "cleared", "born")
    def __init__(self, dir_, top, bot, born):
        self.dir = dir_
        self.top = top
        self.bot = bot
        self.cleared = False
        self.born = born


def sma(vals, n):
    if len(vals) < n:
        return None
    return sum(vals[-n:]) / n


def in_session(ts, use_filter):
    if not use_filter:
        return True
    dt_ny = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(NY)
    min_of_day = dt_ny.hour * 60 + dt_ny.minute
    return min_of_day >= 1080 or min_of_day < 660  # 18:00-11:00 NY


def run_backtest(bars, cooldown_bars=0, lock_r=LOCK_R, verbose_trades=False):
    """
    cooldown_bars: si >0, no se permite ninguna entrada nueva hasta que
    hayan pasado al menos esa cantidad de barras desde el cierre de la
    operacion anterior (cualquier resultado). 0 = comportamiento original
    del script (sin cooldown).
    """
    n = len(bars)
    ranges = []          # high-low de cada barra, para el SMA
    zones = []            # lista de Zone vivas
    trade_open = False
    dir_ = 0
    entry_price = None
    active_sl = None
    risk_pts = None
    tp1_hit = False
    be_moved = False
    last_close_bar = -10**9  # para cooldown

    trades = []  # cada trade: dict con detalle

    # necesitamos closes/opens recientes para deteccion de vela opuesta y streaks
    opens = [b[1] for b in bars]
    highs = [b[2] for b in bars]
    lows = [b[3] for b in bars]
    closes = [b[4] for b in bars]
    times = [b[0] for b in bars]

    def bar_range(i):
        return highs[i] - lows[i]

    avg_range_cache = [None] * n  # avgRange en la barra i (SMA incluyendo i)

    cur_trade = None

    for i in range(n):
        t = times[i]
        o, h, l, c = opens[i], highs[i], lows[i], closes[i]

        # ---- avgRange = sma(high-low, 20) en la barra actual ----
        if i >= DISP_LEN - 1:
            s = 0.0
            for k in range(i - DISP_LEN + 1, i + 1):
                s += highs[k] - lows[k]
            avg_range_cache[i] = s / DISP_LEN
        else:
            avg_range_cache[i] = None

        rng = h - l
        avg_prev = avg_range_cache[i - 1] if i >= 1 else None
        is_disp = avg_prev is not None and rng >= DISP_MULT * avg_prev
        bull_disp = is_disp and c > o and (c - l) >= DISP_CLOSE_FRAC * rng
        bear_disp = is_disp and c < o and (h - c) >= DISP_CLOSE_FRAC * rng

        # ---------------- 1) formar zonas nuevas ----------------
        if bull_disp:
            idx = -1
            for k in range(1, OB_SCAN_BARS + 1):
                j = i - k
                if j < 0:
                    break
                if closes[j] < opens[j]:
                    idx = k
                    break
            if idx != -1:
                cand_bot = lows[i - idx]
                max_streak = 0
                cur_streak = 0
                for k in range(idx + 1, idx + LIQ_CHECK_BARS + 1):
                    j = i - k
                    if j < 0:
                        break
                    if lows[j] <= cand_bot + LIQ_TOLERANCE_PTS:
                        cur_streak += 1
                        max_streak = max(max_streak, cur_streak)
                    else:
                        cur_streak = 0
                if max_streak < LIQ_ACCUM_BARS:
                    zones.append(Zone(1, highs[i - idx], cand_bot, i))

        if bear_disp:
            idx2 = -1
            for k in range(1, OB_SCAN_BARS + 1):
                j = i - k
                if j < 0:
                    break
                if closes[j] > opens[j]:
                    idx2 = k
                    break
            if idx2 != -1:
                cand_top = highs[i - idx2]
                max_streak2 = 0
                cur_streak2 = 0
                for k in range(idx2 + 1, idx2 + LIQ_CHECK_BARS + 1):
                    j = i - k
                    if j < 0:
                        break
                    if highs[j] >= cand_top - LIQ_TOLERANCE_PTS:
                        cur_streak2 += 1
                        max_streak2 = max(max_streak2, cur_streak2)
                    else:
                        cur_streak2 = 0
                if max_streak2 < LIQ_ACCUM_BARS:
                    zones.append(Zone(-1, cand_top, lows[i - idx2], i))

        if len(zones) > MAX_ZONES:
            zones = zones[len(zones) - MAX_ZONES:]

        # ---------------- 2) actualizar cleared ----------------
        for z in zones:
            if z.born != i and not z.cleared:
                if z.dir == 1 and l > z.top:
                    z.cleared = True
                elif z.dir == -1 and h < z.bot:
                    z.cleared = True

        # ---------------- 3) estado sesion/fecha ----------------
        in_sess = in_session(t, USE_SESSION_FILTER)
        can_enter = in_sess and not trade_open
        if cooldown_bars > 0 and (i - last_close_bar) < cooldown_bars:
            can_enter = False

        # ---------------- 4) buscar candidata (zona mas reciente) ----------------
        cand_entry = cand_sl = cand_risk = None
        cand_dir = 0
        cand_born = -1

        if can_enter:
            for z in zones:
                if z.born == i or not z.cleared:
                    continue
                if (i - z.born) > ZONE_MAX_AGE:
                    continue
                if z.dir == 1 and l <= z.top + ENTRY_BUFFER_PTS and l >= z.bot:
                    # FIX: precio de entrada causal, sin mirar el futuro de la vela.
                    # Si alcanzo el OB puro (z.top, nivel fijo conocido de antemano)
                    # -> entra ahi. Si solo toco el margen -> entra en el borde
                    # EXTERIOR del margen (z.top+buffer), que es el primer nivel
                    # que el precio cruza viniendo de afuera, no en "donde termino
                    # llegando" esa vela (eso requeriria conocer el minimo final
                    # de la vela antes de que termine de formarse).
                    e = z.top if l <= z.top else z.top + ENTRY_BUFFER_PTS
                    x = z.bot - SL_BUFFER_PTS
                    r = e - x
                    if r > 0 and (not USE_RISK_CAP or r <= MAX_RISK_PTS):
                        if z.born > cand_born:
                            cand_entry, cand_sl, cand_risk = e, x, r
                            cand_dir, cand_born = 1, z.born
                if z.dir == -1 and h >= z.bot - ENTRY_BUFFER_PTS and h <= z.top:
                    e2 = z.bot if h >= z.bot else z.bot - ENTRY_BUFFER_PTS
                    x2 = z.top + SL_BUFFER_PTS
                    r2 = x2 - e2
                    if r2 > 0 and (not USE_RISK_CAP or r2 <= MAX_RISK_PTS):
                        if z.born > cand_born:
                            cand_entry, cand_sl, cand_risk = e2, x2, r2
                            cand_dir, cand_born = -1, z.born

        # ---------------- 5) retirar zonas caducadas/consumidas ----------------
        new_zones = []
        for z in zones:
            expired = (i - z.born) > ZONE_MAX_AGE
            consumed = (z.born != i and z.cleared and
                        ((z.dir == 1 and l <= z.top) or (z.dir == -1 and h >= z.bot)))
            if not (expired or consumed):
                new_zones.append(z)
        zones = new_zones

        # ---------------- 6) entrada ----------------
        if can_enter and cand_dir != 0:
            entry_price = cand_entry
            active_sl = cand_sl
            risk_pts = cand_risk
            tp1_hit = False
            be_moved = False
            trade_open = True
            dir_ = cand_dir
            cur_trade = {
                "entry_bar": i, "entry_time": t, "dir": dir_,
                "entry": entry_price, "sl0": active_sl, "risk": risk_pts,
                "tp1": entry_price + risk_pts * RR1 * dir_,
                "tp2": entry_price + risk_pts * RR2 * dir_,
                "qty_left": QTY,
                "exit_bar": None, "exit_reason": None, "pnl": 0.0,
            }

        # ---------------- 7) gestion ----------------
        # FIX: no evaluar TP1/SL/BE en la MISMA barra de la entrada — evita
        # el "beneficio de la duda" de usar el low (para entrar) y el high
        # (para el TP) de una misma vela sin conocer el orden real intrabar.
        # Corrige el mismo problema que el usuario documento en DECISIONS.md
        # (~9% de ganancia bruta atribuible a este sesgo).
        just_entered_this_bar = trade_open and cur_trade is not None and cur_trade["entry_bar"] == i
        if trade_open and dir_ == 1 and not just_entered_this_bar:
            tp1 = entry_price + risk_pts * RR1
            tp2 = entry_price + risk_pts * RR2
            hit_sl = l <= active_sl
            hit_tp1 = (not tp1_hit) and h >= tp1
            hit_tp2 = tp1_hit and h >= tp2
            reached_r = (h - entry_price) / risk_pts
            if hit_sl:
                if be_moved and not tp1_hit:
                    exit_price = active_sl
                    reason = "BE_LOCK"
                elif tp1_hit:
                    exit_price = active_sl
                    reason = "TP1_BE"
                else:
                    exit_price = active_sl
                    reason = "FULL_LOSS"
                _close_trade(cur_trade, i, exit_price, reason, trades,
                             tp1_hit, dir_, entry_price, risk_pts)
                trade_open = False
                last_close_bar = i
            elif hit_tp1:
                tp1_hit = True
                be_moved = True
                active_sl = max(active_sl, entry_price + risk_pts * lock_r)
                cur_trade["tp1_bar"] = i
            elif hit_tp2:
                _close_trade(cur_trade, i, tp2, "TP1_TP2", trades,
                             tp1_hit, dir_, entry_price, risk_pts)
                trade_open = False
                last_close_bar = i
            elif BE_TRIGGER_R > 0 and not be_moved and reached_r >= BE_TRIGGER_R:
                be_moved = True
                active_sl = entry_price + risk_pts * lock_r

        elif trade_open and dir_ == -1 and not just_entered_this_bar:
            tp1 = entry_price - risk_pts * RR1
            tp2 = entry_price - risk_pts * RR2
            hit_sl = h >= active_sl
            hit_tp1 = (not tp1_hit) and l <= tp1
            hit_tp2 = tp1_hit and l <= tp2
            reached_r = (entry_price - l) / risk_pts
            if hit_sl:
                if be_moved and not tp1_hit:
                    exit_price = active_sl
                    reason = "BE_LOCK"
                elif tp1_hit:
                    exit_price = active_sl
                    reason = "TP1_BE"
                else:
                    exit_price = active_sl
                    reason = "FULL_LOSS"
                _close_trade(cur_trade, i, exit_price, reason, trades,
                             tp1_hit, dir_, entry_price, risk_pts)
                trade_open = False
                last_close_bar = i
            elif hit_tp1:
                tp1_hit = True
                be_moved = True
                active_sl = min(active_sl, entry_price - risk_pts * lock_r)
                cur_trade["tp1_bar"] = i
            elif hit_tp2:
                _close_trade(cur_trade, i, tp2, "TP1_TP2", trades,
                             tp1_hit, dir_, entry_price, risk_pts)
                trade_open = False
                last_close_bar = i
            elif BE_TRIGGER_R > 0 and not be_moved and reached_r >= BE_TRIGGER_R:
                be_moved = True
                active_sl = entry_price - risk_pts * lock_r

    return trades


def _close_trade(trade, bar, exit_price, reason, trades_list, tp1_was_hit, dir_, entry, risk):
    """Calcula el PnL en USD con slippage y comision, y registra el trade."""
    trade["exit_bar"] = bar
    trade["exit_reason"] = reason
    trade["tp1_was_hit"] = tp1_was_hit

    slip = TICK * SLIPPAGE_TICKS  # puntos de slippage por fill

    if reason == "TP1_TP2":
        # 2 contratos ya cerrados en TP1 (con slippage a favor del mercado, es decir
        # en contra nuestra: el fill de venta/compra es "slip" peor que el nivel).
        tp1_px = trade["tp1"]
        tp2_px = trade["tp2"]
        if dir_ == 1:
            fill_tp1 = tp1_px - slip
            fill_tp2 = tp2_px - slip
        else:
            fill_tp1 = tp1_px + slip
            fill_tp2 = tp2_px + slip
        pnl_pts_tp1 = (fill_tp1 - entry) * dir_ * 2
        pnl_pts_tp2 = (fill_tp2 - entry) * dir_ * 1
        gross = (pnl_pts_tp1 + pnl_pts_tp2) * POINT_VALUE
        commission = COMMISSION_PER_CONTRACT_SIDE * QTY * 2  # entrada+salida, 3 contratos totales
    elif reason == "BE_LOCK":
        # TP1 NUNCA se toco (tp1Hit=false): los 3 contratos cierran juntos
        # al nivel de lock (entry + risk*lockR), no hay reparto 2+1.
        exit_fill = exit_price - slip * dir_
        pnl_pts = (exit_fill - entry) * dir_ * QTY
        gross = pnl_pts * POINT_VALUE
        commission = COMMISSION_PER_CONTRACT_SIDE * QTY * 2
        trade["pnl"] = gross - commission
        trade["gross"] = gross
        trade["commission"] = commission
        trades_list.append(trade)
        return
    elif reason == "TP1_BE":
        tp1_px = trade["tp1"]
        if dir_ == 1:
            fill_tp1 = tp1_px - slip
        else:
            fill_tp1 = tp1_px + slip
        pnl_pts_tp1 = (fill_tp1 - entry) * dir_ * 2
        exit_fill = exit_price - slip * dir_
        pnl_pts_rest = (exit_fill - entry) * dir_ * 1
        gross = (pnl_pts_tp1 + pnl_pts_rest) * POINT_VALUE
        commission = COMMISSION_PER_CONTRACT_SIDE * QTY * 2
    else:  # FULL_LOSS
        exit_fill = exit_price - slip * dir_
        pnl_pts = (exit_fill - entry) * dir_ * QTY
        gross = pnl_pts * POINT_VALUE
        commission = COMMISSION_PER_CONTRACT_SIDE * QTY * 2

    trade["pnl"] = gross - commission
    trade["gross"] = gross
    trade["commission"] = commission
    trades_list.append(trade)


def summarize(trades, label=""):
    if not trades:
        print(f"[{label}] Sin operaciones.")
        return {}
    net = sum(t["pnl"] for t in trades)
    gp = sum(t["pnl"] for t in trades if t["pnl"] > 0)
    gl = -sum(t["pnl"] for t in trades if t["pnl"] < 0)
    wins = [t for t in trades if t["pnl"] > 0]
    losses = [t for t in trades if t["pnl"] <= 0]
    pf = gp / gl if gl > 0 else float("inf")
    # drawdown sobre equity acumulada
    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    for t in trades:
        equity += t["pnl"]
        peak = max(peak, equity)
        dd = peak - equity
        max_dd = max(max_dd, dd)
    largest_win = max((t["pnl"] for t in trades), default=0)
    largest_loss = min((t["pnl"] for t in trades), default=0)

    print(f"=== {label} ===")
    print(f"Trades: {len(trades)}  Wins: {len(wins)} ({100*len(wins)/len(trades):.1f}%)")
    print(f"Net profit: ${net:,.2f}")
    print(f"Profit factor: {pf:.3f}")
    print(f"Max drawdown: ${max_dd:,.2f}")
    print(f"Largest win: ${largest_win:,.2f}  Largest loss: ${largest_loss:,.2f}")
    print(f"Total commission: ${sum(t['commission'] for t in trades):,.2f}")
    print()
    return {"trades": len(trades), "net": net, "pf": pf, "max_dd": max_dd,
            "largest_win": largest_win, "largest_loss": largest_loss,
            "winrate": len(wins)/len(trades)}


if __name__ == "__main__":
    bars = load_bars()
    print(f"Barras cargadas: {len(bars)}")
    print(f"Desde {datetime.fromtimestamp(bars[0][0], tz=timezone.utc)} hasta {datetime.fromtimestamp(bars[-1][0], tz=timezone.utc)}")
    print()

    trades_baseline = run_backtest(bars, cooldown_bars=0)
    summarize(trades_baseline, "BASELINE (sin cooldown, igual que v15 real)")
