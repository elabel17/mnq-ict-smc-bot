"""
Motor de backtest generalizado (v2) para re-optimizacion completa tras el
fix de entrada causal (2026-09-08).

Separa DOS pasos que antes estaban mezclados:
  1) select_trades(): decide QUE operaciones se toman y como se resuelven
     (entrada, SL, TP1, TP2, BE) -- esto depende SOLO de rr1, rr2,
     be_trigger_r, lock_r. Es la parte cara (recorre las 147k barras).
  2) price_trades(): convierte esas operaciones "en puntos" a dolares para
     un tamano de posicion y reparto de contratos dado (qty_tp1, qty_tp2).
     Es barato (recorre solo la lista de trades), así que se puede probar
     decenas de combinaciones de tamano de posicion SIN re-correr el
     backtest completo cada vez.

Logica de deteccion/entrada identica a engine.py (fix de entrada causal
ya incluido), sincronizada con el script real de TradingView 2026-09-08.
"""
import json, os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

DATADIR = os.path.dirname(os.path.abspath(__file__))

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
USE_RISK_CAP = True
MAX_RISK_PTS = 100.0
USE_SESSION_FILTER = True

POINT_VALUE = 2.0
TICK = 0.25
SLIPPAGE_TICKS = 1
COMMISSION_PER_CONTRACT_SIDE = 0.47

NY = ZoneInfo("America/New_York")

_BARS_CACHE = {}


def load_bars(filename="merged_ohlcv_15m_2020_2026.json"):
    if filename in _BARS_CACHE:
        return _BARS_CACHE[filename]
    path = os.path.join(DATADIR, filename)
    raw = json.load(open(path, encoding="utf-8"))
    bars = [(b[0], b[1], b[2], b[3], b[4]) for b in raw]
    bars.sort(key=lambda x: x[0])
    _BARS_CACHE[filename] = bars
    return bars


class Zone:
    __slots__ = ("dir", "top", "bot", "cleared", "born")
    def __init__(self, dir_, top, bot, born):
        self.dir = dir_; self.top = top; self.bot = bot
        self.cleared = False; self.born = born


def in_session(ts, use_filter, start_min=1080, end_min=660):
    """Ventana de sesion NY. Por defecto 18:00-11:00 (igual al script real):
    start_min=1080 (18:00), end_min=660 (11:00) -> cruza medianoche."""
    if not use_filter:
        return True
    dt_ny = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(NY)
    min_of_day = dt_ny.hour * 60 + dt_ny.minute
    if start_min > end_min:  # ventana que cruza medianoche
        return min_of_day >= start_min or min_of_day < end_min
    return start_min <= min_of_day < end_min


def select_trades(bars, rr1=1.8, rr2=4.0, be_trigger_r=1.2, lock_r=0.8, cooldown_bars=0,
                   session_start_min=1080, session_end_min=660):
    """Devuelve trades 'en puntos' (sin convertir a dolares): cada uno trae
    dir, entry, risk, tp1, tp2, reason, exit_price, tp1_was_hit, entry_time,
    exit_time, bars_held."""
    n = len(bars)
    zones = []
    trade_open = False
    dir_ = 0
    entry_price = active_sl = risk_pts = None
    tp1_hit = be_moved = False
    last_close_bar = -10**9
    trades = []

    opens = [b[1] for b in bars]
    highs = [b[2] for b in bars]
    lows = [b[3] for b in bars]
    closes = [b[4] for b in bars]
    times = [b[0] for b in bars]

    avg_range_cache = [None] * n
    cur_trade = None

    for i in range(n):
        t = times[i]
        o, h, l, c = opens[i], highs[i], lows[i], closes[i]

        if i >= DISP_LEN - 1:
            s = 0.0
            for k in range(i - DISP_LEN + 1, i + 1):
                s += highs[k] - lows[k]
            avg_range_cache[i] = s / DISP_LEN

        rng = h - l
        avg_prev = avg_range_cache[i - 1] if i >= 1 else None
        is_disp = avg_prev is not None and rng >= DISP_MULT * avg_prev
        bull_disp = is_disp and c > o and (c - l) >= DISP_CLOSE_FRAC * rng
        bear_disp = is_disp and c < o and (h - c) >= DISP_CLOSE_FRAC * rng

        if bull_disp:
            idx = -1
            for k in range(1, OB_SCAN_BARS + 1):
                j = i - k
                if j < 0: break
                if closes[j] < opens[j]:
                    idx = k; break
            if idx != -1:
                cand_bot = lows[i - idx]
                max_streak = cur_streak = 0
                for k in range(idx + 1, idx + LIQ_CHECK_BARS + 1):
                    j = i - k
                    if j < 0: break
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
                if j < 0: break
                if closes[j] > opens[j]:
                    idx2 = k; break
            if idx2 != -1:
                cand_top = highs[i - idx2]
                max_streak2 = cur_streak2 = 0
                for k in range(idx2 + 1, idx2 + LIQ_CHECK_BARS + 1):
                    j = i - k
                    if j < 0: break
                    if highs[j] >= cand_top - LIQ_TOLERANCE_PTS:
                        cur_streak2 += 1
                        max_streak2 = max(max_streak2, cur_streak2)
                    else:
                        cur_streak2 = 0
                if max_streak2 < LIQ_ACCUM_BARS:
                    zones.append(Zone(-1, cand_top, lows[i - idx2], i))

        if len(zones) > MAX_ZONES:
            zones = zones[len(zones) - MAX_ZONES:]

        for z in zones:
            if z.born != i and not z.cleared:
                if z.dir == 1 and l > z.top:
                    z.cleared = True
                elif z.dir == -1 and h < z.bot:
                    z.cleared = True

        in_sess = in_session(t, USE_SESSION_FILTER, session_start_min, session_end_min)
        can_enter = in_sess and not trade_open
        if cooldown_bars > 0 and (i - last_close_bar) < cooldown_bars:
            can_enter = False

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

        new_zones = []
        for z in zones:
            expired = (i - z.born) > ZONE_MAX_AGE
            consumed = (z.born != i and z.cleared and
                        ((z.dir == 1 and l <= z.top) or (z.dir == -1 and h >= z.bot)))
            if not (expired or consumed):
                new_zones.append(z)
        zones = new_zones

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
                "entry": entry_price, "risk": risk_pts,
                "tp1": entry_price + risk_pts * rr1 * dir_,
                "tp2": entry_price + risk_pts * rr2 * dir_,
            }

        just_entered_this_bar = trade_open and cur_trade is not None and cur_trade["entry_bar"] == i
        if trade_open and dir_ == 1 and not just_entered_this_bar:
            tp1 = entry_price + risk_pts * rr1
            tp2 = entry_price + risk_pts * rr2
            hit_sl = l <= active_sl
            hit_tp1 = (not tp1_hit) and h >= tp1
            hit_tp2 = tp1_hit and h >= tp2
            reached_r = (h - entry_price) / risk_pts
            if hit_sl:
                reason = "BE_LOCK" if (be_moved and not tp1_hit) else ("TP1_BE" if tp1_hit else "FULL_LOSS")
                cur_trade.update(exit_bar=i, exit_time=t, exit_reason=reason,
                                  exit_price=active_sl, tp1_was_hit=tp1_hit)
                trades.append(cur_trade)
                trade_open = False; last_close_bar = i
            elif hit_tp1:
                tp1_hit = True; be_moved = True
                active_sl = max(active_sl, entry_price + risk_pts * lock_r)
            elif hit_tp2:
                cur_trade.update(exit_bar=i, exit_time=t, exit_reason="TP1_TP2",
                                  exit_price=tp2, tp1_was_hit=tp1_hit)
                trades.append(cur_trade)
                trade_open = False; last_close_bar = i
            elif be_trigger_r > 0 and not be_moved and reached_r >= be_trigger_r:
                be_moved = True
                active_sl = entry_price + risk_pts * lock_r

        elif trade_open and dir_ == -1 and not just_entered_this_bar:
            tp1 = entry_price - risk_pts * rr1
            tp2 = entry_price - risk_pts * rr2
            hit_sl = h >= active_sl
            hit_tp1 = (not tp1_hit) and l <= tp1
            hit_tp2 = tp1_hit and l <= tp2
            reached_r = (entry_price - l) / risk_pts
            if hit_sl:
                reason = "BE_LOCK" if (be_moved and not tp1_hit) else ("TP1_BE" if tp1_hit else "FULL_LOSS")
                cur_trade.update(exit_bar=i, exit_time=t, exit_reason=reason,
                                  exit_price=active_sl, tp1_was_hit=tp1_hit)
                trades.append(cur_trade)
                trade_open = False; last_close_bar = i
            elif hit_tp1:
                tp1_hit = True; be_moved = True
                active_sl = min(active_sl, entry_price - risk_pts * lock_r)
            elif hit_tp2:
                cur_trade.update(exit_bar=i, exit_time=t, exit_reason="TP1_TP2",
                                  exit_price=tp2, tp1_was_hit=tp1_hit)
                trades.append(cur_trade)
                trade_open = False; last_close_bar = i
            elif be_trigger_r > 0 and not be_moved and reached_r >= be_trigger_r:
                be_moved = True
                active_sl = entry_price - risk_pts * lock_r

    return trades


def _window_match(min_of_day, start_min, end_min):
    if start_min > end_min:
        return min_of_day >= start_min or min_of_day < end_min
    return start_min <= min_of_day < end_min


def select_trades_multi(bars, windows, cooldown_bars=0):
    """Como select_trades, pero permite parametros DISTINTOS de rr1/rr2/
    be_trigger_r/lock_r segun la ventana horaria (NY) en que se ABRE la
    operacion. 'windows' es una lista de dicts:
      {"start_min":.., "end_min":.., "rr1":.., "rr2":.., "be_trigger_r":..,
       "lock_r":..}
    No deben solaparse. Una vez abierta, la operacion usa SIEMPRE los
    parametros de la ventana en que se abrio (no cambia a mitad de camino
    aunque la hora avance a otra ventana)."""
    n = len(bars)
    zones = []
    trade_open = False
    dir_ = 0
    entry_price = active_sl = risk_pts = None
    tp1_hit = be_moved = False
    last_close_bar = -10**9
    trades = []
    active_rr1 = active_rr2 = active_be_trigger = active_lock = None

    opens = [b[1] for b in bars]
    highs = [b[2] for b in bars]
    lows = [b[3] for b in bars]
    closes = [b[4] for b in bars]
    times = [b[0] for b in bars]

    avg_range_cache = [None] * n
    cur_trade = None

    for i in range(n):
        t = times[i]
        o, h, l, c = opens[i], highs[i], lows[i], closes[i]

        if i >= DISP_LEN - 1:
            s = 0.0
            for k in range(i - DISP_LEN + 1, i + 1):
                s += highs[k] - lows[k]
            avg_range_cache[i] = s / DISP_LEN

        rng = h - l
        avg_prev = avg_range_cache[i - 1] if i >= 1 else None
        is_disp = avg_prev is not None and rng >= DISP_MULT * avg_prev
        bull_disp = is_disp and c > o and (c - l) >= DISP_CLOSE_FRAC * rng
        bear_disp = is_disp and c < o and (h - c) >= DISP_CLOSE_FRAC * rng

        if bull_disp:
            idx = -1
            for k in range(1, OB_SCAN_BARS + 1):
                j = i - k
                if j < 0: break
                if closes[j] < opens[j]:
                    idx = k; break
            if idx != -1:
                cand_bot = lows[i - idx]
                max_streak = cur_streak = 0
                for k in range(idx + 1, idx + LIQ_CHECK_BARS + 1):
                    j = i - k
                    if j < 0: break
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
                if j < 0: break
                if closes[j] > opens[j]:
                    idx2 = k; break
            if idx2 != -1:
                cand_top = highs[i - idx2]
                max_streak2 = cur_streak2 = 0
                for k in range(idx2 + 1, idx2 + LIQ_CHECK_BARS + 1):
                    j = i - k
                    if j < 0: break
                    if highs[j] >= cand_top - LIQ_TOLERANCE_PTS:
                        cur_streak2 += 1
                        max_streak2 = max(max_streak2, cur_streak2)
                    else:
                        cur_streak2 = 0
                if max_streak2 < LIQ_ACCUM_BARS:
                    zones.append(Zone(-1, cand_top, lows[i - idx2], i))

        if len(zones) > MAX_ZONES:
            zones = zones[len(zones) - MAX_ZONES:]

        for z in zones:
            if z.born != i and not z.cleared:
                if z.dir == 1 and l > z.top:
                    z.cleared = True
                elif z.dir == -1 and h < z.bot:
                    z.cleared = True

        dt_ny = datetime.fromtimestamp(t, tz=timezone.utc).astimezone(NY)
        min_of_day = dt_ny.hour * 60 + dt_ny.minute
        win = None
        for w in windows:
            if _window_match(min_of_day, w["start_min"], w["end_min"]):
                win = w
                break
        can_enter = (win is not None) and not trade_open
        if cooldown_bars > 0 and (i - last_close_bar) < cooldown_bars:
            can_enter = False

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

        new_zones = []
        for z in zones:
            expired = (i - z.born) > ZONE_MAX_AGE
            consumed = (z.born != i and z.cleared and
                        ((z.dir == 1 and l <= z.top) or (z.dir == -1 and h >= z.bot)))
            if not (expired or consumed):
                new_zones.append(z)
        zones = new_zones

        if can_enter and cand_dir != 0:
            entry_price = cand_entry
            active_sl = cand_sl
            risk_pts = cand_risk
            tp1_hit = False
            be_moved = False
            trade_open = True
            dir_ = cand_dir
            active_rr1 = win["rr1"]; active_rr2 = win["rr2"]
            active_be_trigger = win["be_trigger_r"]; active_lock = win["lock_r"]
            cur_trade = {
                "entry_bar": i, "entry_time": t, "dir": dir_,
                "entry": entry_price, "risk": risk_pts,
                "tp1": entry_price + risk_pts * active_rr1 * dir_,
                "tp2": entry_price + risk_pts * active_rr2 * dir_,
                "window": win.get("label", ""),
            }

        just_entered_this_bar = trade_open and cur_trade is not None and cur_trade["entry_bar"] == i
        if trade_open and dir_ == 1 and not just_entered_this_bar:
            tp1 = entry_price + risk_pts * active_rr1
            tp2 = entry_price + risk_pts * active_rr2
            hit_sl = l <= active_sl
            hit_tp1 = (not tp1_hit) and h >= tp1
            hit_tp2 = tp1_hit and h >= tp2
            reached_r = (h - entry_price) / risk_pts
            if hit_sl:
                reason = "BE_LOCK" if (be_moved and not tp1_hit) else ("TP1_BE" if tp1_hit else "FULL_LOSS")
                cur_trade.update(exit_bar=i, exit_time=t, exit_reason=reason,
                                  exit_price=active_sl, tp1_was_hit=tp1_hit)
                trades.append(cur_trade)
                trade_open = False; last_close_bar = i
            elif hit_tp1:
                tp1_hit = True; be_moved = True
                active_sl = max(active_sl, entry_price + risk_pts * active_lock)
            elif hit_tp2:
                cur_trade.update(exit_bar=i, exit_time=t, exit_reason="TP1_TP2",
                                  exit_price=tp2, tp1_was_hit=tp1_hit)
                trades.append(cur_trade)
                trade_open = False; last_close_bar = i
            elif active_be_trigger > 0 and not be_moved and reached_r >= active_be_trigger:
                be_moved = True
                active_sl = entry_price + risk_pts * active_lock

        elif trade_open and dir_ == -1 and not just_entered_this_bar:
            tp1 = entry_price - risk_pts * active_rr1
            tp2 = entry_price - risk_pts * active_rr2
            hit_sl = h >= active_sl
            hit_tp1 = (not tp1_hit) and l <= tp1
            hit_tp2 = tp1_hit and l <= tp2
            reached_r = (entry_price - l) / risk_pts
            if hit_sl:
                reason = "BE_LOCK" if (be_moved and not tp1_hit) else ("TP1_BE" if tp1_hit else "FULL_LOSS")
                cur_trade.update(exit_bar=i, exit_time=t, exit_reason=reason,
                                  exit_price=active_sl, tp1_was_hit=tp1_hit)
                trades.append(cur_trade)
                trade_open = False; last_close_bar = i
            elif hit_tp1:
                tp1_hit = True; be_moved = True
                active_sl = min(active_sl, entry_price - risk_pts * active_lock)
            elif hit_tp2:
                cur_trade.update(exit_bar=i, exit_time=t, exit_reason="TP1_TP2",
                                  exit_price=tp2, tp1_was_hit=tp1_hit)
                trades.append(cur_trade)
                trade_open = False; last_close_bar = i
            elif active_be_trigger > 0 and not be_moved and reached_r >= active_be_trigger:
                be_moved = True
                active_sl = entry_price - risk_pts * active_lock

    return trades


def price_trades(raw_trades, qty_tp1=2, qty_tp2=1):
    """Convierte trades 'en puntos' a dolares para un tamano/reparto dado.
    qty_tp1=0 significa 'todo corre a TP2, ignora TP1 para el cierre parcial'
    -- en ese caso TP1_BE se trata igual que si el runner completo se hubiera
    movido a BE tras tocar TP1 (mismo stop, pero sin cerrar nada ahi)."""
    total_qty = qty_tp1 + qty_tp2
    slip = TICK * SLIPPAGE_TICKS
    priced = []
    for rt in raw_trades:
        dir_ = rt["dir"]; entry = rt["entry"]; reason = rt["exit_reason"]
        t = dict(rt)
        if reason == "TP1_TP2":
            fill_tp1 = rt["tp1"] - slip * dir_
            fill_tp2 = rt["tp2"] - slip * dir_
            pnl_pts = (fill_tp1 - entry) * dir_ * qty_tp1 + (fill_tp2 - entry) * dir_ * qty_tp2
        elif reason == "BE_LOCK":
            exit_fill = rt["exit_price"] - slip * dir_
            pnl_pts = (exit_fill - entry) * dir_ * total_qty
        elif reason == "TP1_BE":
            fill_tp1 = rt["tp1"] - slip * dir_
            exit_fill = rt["exit_price"] - slip * dir_
            pnl_pts = (fill_tp1 - entry) * dir_ * qty_tp1 + (exit_fill - entry) * dir_ * qty_tp2
        else:  # FULL_LOSS
            exit_fill = rt["exit_price"] - slip * dir_
            pnl_pts = (exit_fill - entry) * dir_ * total_qty
        gross = pnl_pts * POINT_VALUE
        commission = COMMISSION_PER_CONTRACT_SIDE * total_qty * 2
        t["pnl"] = gross - commission
        t["gross"] = gross
        t["commission"] = commission
        priced.append(t)
    return priced


def summarize(trades, label="", silent=False):
    if not trades:
        if not silent:
            print(f"[{label}] Sin operaciones.")
        return {"trades": 0, "net": 0, "pf": 0, "max_dd": 0, "winrate": 0, "max_loss_streak": 0}
    net = sum(t["pnl"] for t in trades)
    gp = sum(t["pnl"] for t in trades if t["pnl"] > 0)
    gl = -sum(t["pnl"] for t in trades if t["pnl"] < 0)
    wins = [t for t in trades if t["pnl"] > 0]
    pf = gp / gl if gl > 0 else float("inf")
    equity = peak = max_dd = 0.0
    streak = max_streak = 0
    for t in trades:
        equity += t["pnl"]
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
        if t["pnl"] <= 0:
            streak += 1
            max_streak = max(max_streak, streak)
        else:
            streak = 0
    res = {"trades": len(trades), "net": net, "pf": pf, "max_dd": max_dd,
           "winrate": len(wins) / len(trades), "max_loss_streak": max_streak}
    if not silent:
        print(f"=== {label} ===")
        print(f"Trades: {res['trades']}  Winrate: {100*res['winrate']:.1f}%  "
              f"Net: ${res['net']:,.2f}  PF: {res['pf']:.3f}  MaxDD: ${res['max_dd']:,.2f}  "
              f"MaxLossStreak: {res['max_loss_streak']}")
    return res
