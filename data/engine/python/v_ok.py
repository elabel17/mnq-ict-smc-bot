"""
Motor v5: identico a engine3/engine4 (deteccion + TP/BE totalmente
parametrizados) pero apuntado por defecto al dataset de 5 MINUTOS
nativo (no 15m agregado a 5m como en engine_mtf.py -- aqui el OB se
detecta directamente sobre velas de 5m, con su propio juego de
parametros, para explorar si existe una parametrizacion de scalping
genuinamente distinta a la de 15m).

Dataset: merged_ohlcv_5m_2024_2026.json, 185.066 velas, 2024-01-28 a
2026-09-08 (~2.6 anios -- limite de profundidad del feed de 5m, mucho
menos historico que los 6.27 anios de 15m, asi que cualquier hallazgo
aqui tiene menos poder estadistico y debe tratarse con mas cautela).
"""
import json, os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

DATADIR = os.path.dirname(os.path.abspath(__file__))
NY = ZoneInfo("America/New_York")

POINT_VALUE = 2.0
TICK = 0.25
SLIPPAGE_TICKS = 1
COMMISSION_PER_CONTRACT_SIDE = 0.47

_BARS_CACHE = {}


def load_bars(filename="merged_ohlcv_5m_2024_2026.json"):
    if filename in _BARS_CACHE:
        return _BARS_CACHE[filename]
    path = os.path.join(DATADIR, filename)
    raw = json.load(open(path, encoding="utf-8"))
    bars = [(b[0], b[1], b[2], b[3], b[4], b[5] if len(b) > 5 else 0) for b in raw]
    bars.sort(key=lambda x: x[0])
    _BARS_CACHE[filename] = bars
    return bars


def _nivel(z, modo, buf):
    """Donde se pone la limite.
       aire   = fuera de la mecha (top+buffer)  <- lo actual
       mecha  = justo en el extremo de la vela de origen
       cuerpo = en el borde del CUERPO (open/close), dentro de vela real
       medio  = mitad del cuerpo (mean threshold clasico de ICT)"""
    if z.dir == 1:
        if modo == 'aire':   return z.top + buf
        if modo == 'mecha':  return z.top
        if modo == 'cuerpo': return z.body_hi
        return (z.body_hi + z.body_lo) / 2.0
    else:
        if modo == 'aire':   return z.bot - buf
        if modo == 'mecha':  return z.bot
        if modo == 'cuerpo': return z.body_lo
        return (z.body_hi + z.body_lo) / 2.0


class Zone:
    __slots__ = ("dir", "top", "bot", "cleared", "born",
                 "disp_ratio", "liq_streak", "vol_signal", "vol_origin",
                 "body_hi", "body_lo")
    def __init__(self, dir_, top, bot, born, disp_ratio=0.0, liq_streak=0,
                 vol_signal=0.0, vol_origin=0.0):
        self.dir = dir_; self.top = top; self.bot = bot
        self.cleared = False; self.born = born
        self.disp_ratio = disp_ratio      # rng / avg_range de la vela de desplazamiento
        self.liq_streak = liq_streak      # cuan cerca estuvo del limite liq_accum_bars (mas alto = mas "sucia")
        self.vol_signal = vol_signal      # volumen de la vela de desplazamiento
        self.vol_origin = vol_origin      # volumen de la vela origen del OB
        self.body_hi = 0.0; self.body_lo = 0.0   # cuerpo de la vela de origen


def _window_match(min_of_day, start_min, end_min):
    if start_min > end_min:
        return min_of_day >= start_min or min_of_day < end_min
    return start_min <= min_of_day < end_min


def sel_real(bars, entry_mode='aire', rr1=1.8, rr2=5.0, be_trigger_r=1.2, lock_r=1.0, cooldown_bars=0,
                   session_start_min=1080, session_end_min=660,
                   disp_len=20, disp_mult=2.5, disp_close_frac=0.6,
                   ob_scan_bars=10, liq_check_bars=12, liq_tolerance_pts=4.0,
                   liq_accum_bars=6, zone_max_age=300, max_zones=40,
                   sl_buffer_pts=2.0, entry_buffer_pts=12.0,
                   use_risk_cap=True, max_risk_pts=100.0):
    n = len(bars)
    zones = []
    trade_open = False
    dir_ = 0
    entry_price = active_sl = risk_pts = None
    tp1_hit = be_moved = False
    last_close_bar = -10**9
    trades = []

    opens = [b[1] for b in bars]; highs = [b[2] for b in bars]
    lows = [b[3] for b in bars]; closes = [b[4] for b in bars]; times = [b[0] for b in bars]
    vols = [b[5] for b in bars]
    avg_range_cache = [None] * n
    cur_trade = None

    for i in range(n):
        t = times[i]
        o, h, l, c = opens[i], highs[i], lows[i], closes[i]

        if i >= disp_len - 1:
            s = 0.0
            for k in range(i - disp_len + 1, i + 1):
                s += highs[k] - lows[k]
            avg_range_cache[i] = s / disp_len

        rng = h - l
        avg_prev = avg_range_cache[i - 1] if i >= 1 else None
        is_disp = avg_prev is not None and rng >= disp_mult * avg_prev
        bull_disp = is_disp and c > o and (c - l) >= disp_close_frac * rng
        bear_disp = is_disp and c < o and (h - c) >= disp_close_frac * rng
        disp_ratio_now = (rng / avg_prev) if (avg_prev and avg_prev > 0) else 0.0

        if bull_disp:
            idx = -1
            for k in range(1, ob_scan_bars + 1):
                j = i - k
                if j < 0: break
                if closes[j] < opens[j]: idx = k; break
            if idx != -1:
                cand_bot = lows[i - idx]
                max_streak = cur_streak = 0
                for k in range(idx + 1, idx + liq_check_bars + 1):
                    j = i - k
                    if j < 0: break
                    if lows[j] <= cand_bot + liq_tolerance_pts:
                        cur_streak += 1; max_streak = max(max_streak, cur_streak)
                    else:
                        cur_streak = 0
                if max_streak < liq_accum_bars:
                    _z = Zone(1, highs[i - idx], cand_bot, i,
                              disp_ratio=disp_ratio_now, liq_streak=max_streak,
                              vol_signal=vols[i], vol_origin=vols[i - idx])
                    _j = i - idx
                    _z.body_hi = max(opens[_j], closes[_j]); _z.body_lo = min(opens[_j], closes[_j])
                    zones.append(_z)

        if bear_disp:
            idx2 = -1
            for k in range(1, ob_scan_bars + 1):
                j = i - k
                if j < 0: break
                if closes[j] > opens[j]: idx2 = k; break
            if idx2 != -1:
                cand_top = highs[i - idx2]
                max_streak2 = cur_streak2 = 0
                for k in range(idx2 + 1, idx2 + liq_check_bars + 1):
                    j = i - k
                    if j < 0: break
                    if highs[j] >= cand_top - liq_tolerance_pts:
                        cur_streak2 += 1; max_streak2 = max(max_streak2, cur_streak2)
                    else:
                        cur_streak2 = 0
                if max_streak2 < liq_accum_bars:
                    _z = Zone(-1, cand_top, lows[i - idx2], i,
                              disp_ratio=disp_ratio_now, liq_streak=max_streak2,
                              vol_signal=vols[i], vol_origin=vols[i - idx2])
                    _j = i - idx2
                    _z.body_hi = max(opens[_j], closes[_j]); _z.body_lo = min(opens[_j], closes[_j])
                    zones.append(_z)

        if len(zones) > max_zones:
            zones = zones[len(zones) - max_zones:]

        for z in zones:
            if z.born != i and not z.cleared:
                if z.dir == 1 and l > z.top: z.cleared = True
                elif z.dir == -1 and h < z.bot: z.cleared = True

        dt_ny = datetime.fromtimestamp(t, tz=timezone.utc).astimezone(NY)
        min_of_day = dt_ny.hour * 60 + dt_ny.minute
        in_sess = _window_match(min_of_day, session_start_min, session_end_min)
        can_enter = in_sess and not trade_open
        if cooldown_bars > 0 and (i - last_close_bar) < cooldown_bars:
            can_enter = False

        cand_entry = cand_sl = cand_risk = None
        cand_dir = 0
        cand_born = -1
        cand_zone = None

        if can_enter:
            _best = None; _bd = None
            _ref = closes[i-1] if i > 0 else c
            for z in zones:
                if z.born == i or not z.cleared: continue
                if (i - z.born) > zone_max_age: continue
                _lv = _nivel(z, entry_mode, entry_buffer_pts)
                if z.dir == 1 and _ref <= _lv: continue
                if z.dir == -1 and _ref >= _lv: continue
                _d = abs(_ref - _lv)
                if _bd is None or _d < _bd: _bd = _d; _best = z
            _elegibles = [_best] if _best is not None else []
            for z in _elegibles:
                if z.born == i or not z.cleared: continue
                if (i - z.born) > zone_max_age: continue
                _lvz = _nivel(z, entry_mode, entry_buffer_pts)
                if z.dir == 1 and l <= _lvz:
                    e = _lvz
                    x = z.bot - sl_buffer_pts
                    r = e - x
                    if r > 0 and (not use_risk_cap or r <= max_risk_pts):
                        if z.born > cand_born:
                            cand_entry, cand_sl, cand_risk = e, x, r
                            cand_dir, cand_born = 1, z.born
                            cand_zone = z
                if z.dir == -1 and h >= _lvz:
                    e2 = _lvz
                    x2 = z.top + sl_buffer_pts
                    r2 = x2 - e2
                    if r2 > 0 and (not use_risk_cap or r2 <= max_risk_pts):
                        if z.born > cand_born:
                            cand_entry, cand_sl, cand_risk = e2, x2, r2
                            cand_dir, cand_born = -1, z.born
                            cand_zone = z

        new_zones = []
        for z in zones:
            expired = (i - z.born) > zone_max_age
            consumed = (z.born != i and z.cleared and
                        ((z.dir == 1 and l <= z.top) or (z.dir == -1 and h >= z.bot)))
            if not (expired or consumed):
                new_zones.append(z)
        zones = new_zones

        if can_enter and cand_dir != 0:
            entry_price = cand_entry; active_sl = cand_sl; risk_pts = cand_risk
            tp1_hit = False; be_moved = False; trade_open = True; dir_ = cand_dir
            zone_width = cand_zone.top - cand_zone.bot
            if entry_buffer_pts > 0:
                if cand_dir == 1:
                    buf_depth = (entry_price - cand_zone.top) / entry_buffer_pts
                else:
                    buf_depth = (cand_zone.bot - entry_price) / entry_buffer_pts
            else:
                buf_depth = 0.0
            cur_trade = {"entry_bar": i, "entry_time": t, "dir": dir_,
                         "entry": entry_price, "risk": risk_pts,
                         "tp1": entry_price + risk_pts * rr1 * dir_,
                         "tp2": entry_price + risk_pts * rr2 * dir_,
                         "zone_width": zone_width, "buf_depth": buf_depth,
                         "disp_ratio": cand_zone.disp_ratio, "liq_streak": cand_zone.liq_streak,
                         "vol_signal": cand_zone.vol_signal, "vol_origin": cand_zone.vol_origin,
                         "zone_age": i - cand_zone.born}

        just_entered = trade_open and cur_trade is not None and cur_trade["entry_bar"] == i
        if trade_open and dir_ == 1 and not just_entered:
            tp1 = entry_price + risk_pts * rr1
            tp2 = entry_price + risk_pts * rr2
            hit_sl = l <= active_sl
            hit_tp1 = (not tp1_hit) and h >= tp1
            hit_tp2 = tp1_hit and h >= tp2
            reached_r = (h - entry_price) / risk_pts
            if hit_sl:
                reason = "BE_LOCK" if (be_moved and not tp1_hit) else ("TP1_BE" if tp1_hit else "FULL_LOSS")
                cur_trade.update(exit_bar=i, exit_time=t, exit_reason=reason, exit_price=active_sl, tp1_was_hit=tp1_hit)
                trades.append(cur_trade); trade_open = False; last_close_bar = i
            elif hit_tp1:
                tp1_hit = True; be_moved = True
                active_sl = max(active_sl, entry_price + risk_pts * lock_r)
            elif hit_tp2:
                cur_trade.update(exit_bar=i, exit_time=t, exit_reason="TP1_TP2", exit_price=tp2, tp1_was_hit=tp1_hit)
                trades.append(cur_trade); trade_open = False; last_close_bar = i
            elif be_trigger_r > 0 and not be_moved and reached_r >= be_trigger_r:
                _nuevo = entry_price + risk_pts * lock_r
                if _nuevo < c:                      # solo si queda POR DEBAJO del precio
                    be_moved = True; active_sl = _nuevo

        elif trade_open and dir_ == -1 and not just_entered:
            tp1 = entry_price - risk_pts * rr1
            tp2 = entry_price - risk_pts * rr2
            hit_sl = h >= active_sl
            hit_tp1 = (not tp1_hit) and l <= tp1
            hit_tp2 = tp1_hit and l <= tp2
            reached_r = (entry_price - l) / risk_pts
            if hit_sl:
                reason = "BE_LOCK" if (be_moved and not tp1_hit) else ("TP1_BE" if tp1_hit else "FULL_LOSS")
                cur_trade.update(exit_bar=i, exit_time=t, exit_reason=reason, exit_price=active_sl, tp1_was_hit=tp1_hit)
                trades.append(cur_trade); trade_open = False; last_close_bar = i
            elif hit_tp1:
                tp1_hit = True; be_moved = True
                active_sl = min(active_sl, entry_price - risk_pts * lock_r)
            elif hit_tp2:
                cur_trade.update(exit_bar=i, exit_time=t, exit_reason="TP1_TP2", exit_price=tp2, tp1_was_hit=tp1_hit)
                trades.append(cur_trade); trade_open = False; last_close_bar = i
            elif be_trigger_r > 0 and not be_moved and reached_r >= be_trigger_r:
                _nuevo = entry_price - risk_pts * lock_r
                if _nuevo > c:                      # solo si queda POR ENCIMA del precio
                    be_moved = True; active_sl = _nuevo

    return trades


def price_trades(raw_trades, qty_tp1=0, qty_tp2=3):
    total_qty = qty_tp1 + qty_tp2
    slip = TICK * SLIPPAGE_TICKS
    priced = []
    for rt in raw_trades:
        dir_ = rt["dir"]; entry = rt["entry"]; reason = rt["exit_reason"]
        t = dict(rt)
        if reason == "TP1_TP2":
            fill_tp1 = rt["tp1"] - slip * dir_; fill_tp2 = rt["tp2"] - slip * dir_
            pnl_pts = (fill_tp1 - entry) * dir_ * qty_tp1 + (fill_tp2 - entry) * dir_ * qty_tp2
        elif reason == "BE_LOCK":
            exit_fill = rt["exit_price"] - slip * dir_
            pnl_pts = (exit_fill - entry) * dir_ * total_qty
        elif reason == "TP1_BE":
            fill_tp1 = rt["tp1"] - slip * dir_
            exit_fill = rt["exit_price"] - slip * dir_
            pnl_pts = (fill_tp1 - entry) * dir_ * qty_tp1 + (exit_fill - entry) * dir_ * qty_tp2
        else:
            exit_fill = rt["exit_price"] - slip * dir_
            pnl_pts = (exit_fill - entry) * dir_ * total_qty
        gross = pnl_pts * POINT_VALUE
        commission = COMMISSION_PER_CONTRACT_SIDE * total_qty * 2
        t["pnl"] = gross - commission; t["gross"] = gross; t["commission"] = commission
        priced.append(t)
    return priced


def summarize(trades, label="", silent=False):
    if not trades:
        if not silent: print(f"[{label}] Sin operaciones.")
        return {"trades": 0, "net": 0, "pf": 0, "max_dd": 0, "winrate": 0, "max_loss_streak": 0}
    net = sum(t["pnl"] for t in trades)
    gp = sum(t["pnl"] for t in trades if t["pnl"] > 0)
    gl = -sum(t["pnl"] for t in trades if t["pnl"] < 0)
    wins = [t for t in trades if t["pnl"] > 0]
    pf = gp / gl if gl > 0 else float("inf")
    equity = peak = max_dd = 0.0
    streak = max_streak = 0
    for t in trades:
        equity += t["pnl"]; peak = max(peak, equity); max_dd = max(max_dd, peak - equity)
        if t["pnl"] <= 0: streak += 1; max_streak = max(max_streak, streak)
        else: streak = 0
    res = {"trades": len(trades), "net": net, "pf": pf, "max_dd": max_dd,
           "winrate": len(wins) / len(trades), "max_loss_streak": max_streak}
    if not silent:
        print(f"=== {label} ===")
        print(f"Trades: {res['trades']}  WR: {100*res['winrate']:.1f}%  Net: ${res['net']:,.2f}  "
              f"PF: {res['pf']:.3f}  DD: ${res['max_dd']:,.2f}  streak: {res['max_loss_streak']}")
    return res
