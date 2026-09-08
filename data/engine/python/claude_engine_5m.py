"""
Variante del motor que usa velas de 5 minutos para resolver con mas
precision el orden de eventos DENTRO de cada vela de 15 minutos (reduce
~3x la ventana de ambiguedad respecto al motor de 15m puro).

Metodo:
  1. Se agregan las velas de 5m en velas de 15m (open=primera, high/low=
     extremos, close=ultima) -> serie identica a la que daria el feed de
     15m directamente. La deteccion de zonas OB corre igual que antes
     sobre esta serie agregada (misma logica exacta, sin cambios).
  2. Para la GESTION de la operacion (TP1/SL/BE), en vez de usar el
     high/low de la vela de 15m completa de una sola vez, se recorren
     sus 3 sub-velas de 5m EN ORDEN CRONOLOGICO real, resolviendo con
     mas precision cual nivel se toco primero.

Sigue existiendo ambiguedad DENTRO de cada vela de 5m individual (mismo
problema, ventana 3x mas chica) — no es un tick-by-tick perfecto.
"""
import json, os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import engine as base  # reutiliza parametros y utilidades del motor de 15m

SCRATCHDIR = r"C:\Users\ABEL~1.DIA\AppData\Local\Temp\claude\C--Users-ABEL-DIAZ-Documents-cache\6cdd0fc2-2293-4b2f-b0a9-dc3487b369e4\scratchpad"
NY = ZoneInfo("America/New_York")


def load_5m_bars():
    path = r"C:\Users\ABEL.DIAZ\Downloads\mnq_dataset\merged_ohlcv_5m_2024_2026.json"
    raw = json.load(open(path, encoding="utf-8"))
    bars = [(b[0], b[1], b[2], b[3], b[4]) for b in raw]
    bars.sort(key=lambda x: x[0])
    return bars


def aggregate_to_15m(bars_5m):
    """Agrupa velas de 5m en velas de 15m (alineadas a :00/:15/:30/:45 UTC-NY
    igual que hace TradingView). Devuelve (bars_15m, children_map) donde
    children_map[i] = lista de sub-velas 5m (hasta 3) de la vela 15m i,
    en orden cronologico."""
    groups = {}
    for b in bars_5m:
        t = b[0]
        bucket = t - (t % 900)  # alinea a bloques de 15 min (900s)
        groups.setdefault(bucket, []).append(b)

    bars_15m = []
    children_map = []
    for bucket in sorted(groups.keys()):
        subs = sorted(groups[bucket], key=lambda x: x[0])
        o = subs[0][1]
        h = max(s[2] for s in subs)
        l = min(s[3] for s in subs)
        c = subs[-1][4]
        bars_15m.append((bucket, o, h, l, c))
        children_map.append(subs)
    return bars_15m, children_map


def run_backtest_5m(bars_15m, children_map, cooldown_bars=0, lock_r=0.8):
    n = len(bars_15m)
    opens = [b[1] for b in bars_15m]
    highs = [b[2] for b in bars_15m]
    lows = [b[3] for b in bars_15m]
    closes = [b[4] for b in bars_15m]
    times = [b[0] for b in bars_15m]

    zones = []
    trade_open = False
    dir_ = 0
    entry_price = None
    active_sl = None
    risk_pts = None
    tp1_hit = False
    be_moved = False
    last_close_bar = -10**9
    trades = []
    cur_trade = None

    avg_range_cache = [None] * n

    for i in range(n):
        t = times[i]
        o, h, l, c = opens[i], highs[i], lows[i], closes[i]

        if i >= base.DISP_LEN - 1:
            s = sum(highs[k] - lows[k] for k in range(i - base.DISP_LEN + 1, i + 1))
            avg_range_cache[i] = s / base.DISP_LEN
        else:
            avg_range_cache[i] = None

        rng = h - l
        avg_prev = avg_range_cache[i - 1] if i >= 1 else None
        is_disp = avg_prev is not None and rng >= base.DISP_MULT * avg_prev
        bull_disp = is_disp and c > o and (c - l) >= base.DISP_CLOSE_FRAC * rng
        bear_disp = is_disp and c < o and (h - c) >= base.DISP_CLOSE_FRAC * rng

        if bull_disp:
            idx = -1
            for k in range(1, base.OB_SCAN_BARS + 1):
                j = i - k
                if j < 0: break
                if closes[j] < opens[j]: idx = k; break
            if idx != -1:
                cand_bot = lows[i - idx]
                max_streak = curr = 0
                for k in range(idx + 1, idx + base.LIQ_CHECK_BARS + 1):
                    j = i - k
                    if j < 0: break
                    if lows[j] <= cand_bot + base.LIQ_TOLERANCE_PTS:
                        curr += 1; max_streak = max(max_streak, curr)
                    else: curr = 0
                if max_streak < base.LIQ_ACCUM_BARS:
                    zones.append(base.Zone(1, highs[i - idx], cand_bot, i))

        if bear_disp:
            idx2 = -1
            for k in range(1, base.OB_SCAN_BARS + 1):
                j = i - k
                if j < 0: break
                if closes[j] > opens[j]: idx2 = k; break
            if idx2 != -1:
                cand_top = highs[i - idx2]
                max_streak2 = curr2 = 0
                for k in range(idx2 + 1, idx2 + base.LIQ_CHECK_BARS + 1):
                    j = i - k
                    if j < 0: break
                    if highs[j] >= cand_top - base.LIQ_TOLERANCE_PTS:
                        curr2 += 1; max_streak2 = max(max_streak2, curr2)
                    else: curr2 = 0
                if max_streak2 < base.LIQ_ACCUM_BARS:
                    zones.append(base.Zone(-1, cand_top, lows[i - idx2], i))

        if len(zones) > base.MAX_ZONES:
            zones = zones[len(zones) - base.MAX_ZONES:]

        for z in zones:
            if z.born != i and not z.cleared:
                if z.dir == 1 and l > z.top: z.cleared = True
                elif z.dir == -1 and h < z.bot: z.cleared = True

        in_sess = base.in_session(t, base.USE_SESSION_FILTER)
        can_enter = in_sess and not trade_open
        if cooldown_bars > 0 and (i - last_close_bar) < cooldown_bars:
            can_enter = False

        cand_entry = cand_sl = cand_risk = None
        cand_dir = 0
        cand_born = -1
        if can_enter:
            for z in zones:
                if z.born == i or not z.cleared: continue
                if (i - z.born) > base.ZONE_MAX_AGE: continue
                if z.dir == 1 and l <= z.top + base.ENTRY_BUFFER_PTS and l >= z.bot:
                    e = max(l, z.top); x = z.bot - base.SL_BUFFER_PTS; r = e - x
                    if r > 0 and (not base.USE_RISK_CAP or r <= base.MAX_RISK_PTS):
                        if z.born > cand_born:
                            cand_entry, cand_sl, cand_risk = e, x, r
                            cand_dir, cand_born = 1, z.born
                if z.dir == -1 and h >= z.bot - base.ENTRY_BUFFER_PTS and h <= z.top:
                    e2 = min(h, z.bot); x2 = z.top + base.SL_BUFFER_PTS; r2 = x2 - e2
                    if r2 > 0 and (not base.USE_RISK_CAP or r2 <= base.MAX_RISK_PTS):
                        if z.born > cand_born:
                            cand_entry, cand_sl, cand_risk = e2, x2, r2
                            cand_dir, cand_born = -1, z.born

        new_zones = []
        for z in zones:
            expired = (i - z.born) > base.ZONE_MAX_AGE
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
                "entry": entry_price, "sl0": active_sl, "risk": risk_pts,
                "tp1": entry_price + risk_pts * base.RR1 * dir_,
                "tp2": entry_price + risk_pts * base.RR2 * dir_,
                "exit_bar": None, "exit_reason": None, "pnl": 0.0,
            }
            # entrada registrada; NO se gestiona en esta misma vela de 15m
            continue

        just_entered_this_bar = trade_open and cur_trade is not None and cur_trade["entry_bar"] == i
        if trade_open and not just_entered_this_bar:
            tp1 = entry_price + risk_pts * base.RR1 * dir_
            tp2 = entry_price + risk_pts * base.RR2 * dir_
            closed_this_bar = False

            # recorrer las sub-velas de 5m EN ORDEN dentro de esta vela de 15m
            for sub in children_map[i]:
                _, so, sh, sl, sc = sub
                if dir_ == 1:
                    hit_sl = sl <= active_sl
                    hit_tp1 = (not tp1_hit) and sh >= tp1
                    hit_tp2 = tp1_hit and sh >= tp2
                    reached_r = (sh - entry_price) / risk_pts
                else:
                    hit_sl = sh >= active_sl
                    hit_tp1 = (not tp1_hit) and sl <= tp1
                    hit_tp2 = tp1_hit and sl <= tp2
                    reached_r = (entry_price - sl) / risk_pts

                # dentro de la sub-vela de 5m TODAVIA hay ambiguedad de orden
                # (mismo problema, ventana 3x mas chica) -> se mantiene la
                # convencion conservadora: SL primero si ambos caben en la
                # misma sub-vela.
                if hit_sl:
                    if be_moved and not tp1_hit:
                        reason = "BE_LOCK"
                    elif tp1_hit:
                        reason = "TP1_BE"
                    else:
                        reason = "FULL_LOSS"
                    _close_trade_5m(cur_trade, i, active_sl, reason, trades, tp1_hit, dir_, entry_price, risk_pts)
                    trade_open = False
                    last_close_bar = i
                    closed_this_bar = True
                    break
                elif hit_tp1:
                    tp1_hit = True
                    be_moved = True
                    if dir_ == 1:
                        active_sl = max(active_sl, entry_price + risk_pts * lock_r)
                    else:
                        active_sl = min(active_sl, entry_price - risk_pts * lock_r)
                elif hit_tp2:
                    _close_trade_5m(cur_trade, i, tp2, "TP1_TP2", trades, tp1_hit, dir_, entry_price, risk_pts)
                    trade_open = False
                    last_close_bar = i
                    closed_this_bar = True
                    break
                elif base.BE_TRIGGER_R > 0 and not be_moved and reached_r >= base.BE_TRIGGER_R:
                    be_moved = True
                    active_sl = entry_price + risk_pts * lock_r * dir_

            if closed_this_bar:
                continue

    return trades


def _close_trade_5m(trade, bar, exit_price, reason, trades_list, tp1_was_hit, dir_, entry, risk):
    slip = base.TICK * base.SLIPPAGE_TICKS
    trade["exit_bar"] = bar
    trade["exit_reason"] = reason
    trade["tp1_was_hit"] = tp1_was_hit

    if reason == "BE_LOCK":
        exit_fill = exit_price - slip * dir_
        pnl_pts = (exit_fill - entry) * dir_ * base.QTY
        gross = pnl_pts * base.POINT_VALUE
        commission = base.COMMISSION_PER_CONTRACT_SIDE * base.QTY * 2
    elif reason == "TP1_BE":
        tp1_px = trade["tp1"]
        fill_tp1 = tp1_px - slip if dir_ == 1 else tp1_px + slip
        pnl_pts_tp1 = (fill_tp1 - entry) * dir_ * 2
        exit_fill = exit_price - slip * dir_
        pnl_pts_rest = (exit_fill - entry) * dir_ * 1
        gross = (pnl_pts_tp1 + pnl_pts_rest) * base.POINT_VALUE
        commission = base.COMMISSION_PER_CONTRACT_SIDE * base.QTY * 2
    elif reason == "TP1_TP2":
        tp1_px = trade["tp1"]; tp2_px = trade["tp2"]
        fill_tp1 = tp1_px - slip if dir_ == 1 else tp1_px + slip
        fill_tp2 = tp2_px - slip if dir_ == 1 else tp2_px + slip
        pnl_pts = (fill_tp1 - entry) * dir_ * 2 + (fill_tp2 - entry) * dir_ * 1
        gross = pnl_pts * base.POINT_VALUE
        commission = base.COMMISSION_PER_CONTRACT_SIDE * base.QTY * 2
    else:  # FULL_LOSS
        exit_fill = exit_price - slip * dir_
        pnl_pts = (exit_fill - entry) * dir_ * base.QTY
        gross = pnl_pts * base.POINT_VALUE
        commission = base.COMMISSION_PER_CONTRACT_SIDE * base.QTY * 2

    trade["pnl"] = gross - commission
    trade["gross"] = gross
    trade["commission"] = commission
    trades_list.append(trade)


if __name__ == "__main__":
    bars_5m = load_5m_bars()
    print(f"Velas 5m cargadas: {len(bars_5m)}")
    bars_15m, children_map = aggregate_to_15m(bars_5m)
    print(f"Velas 15m agregadas: {len(bars_15m)}")

    trades_5m = run_backtest_5m(bars_15m, children_map, cooldown_bars=0, lock_r=0.8)
    base.summarize(trades_5m, "MOTOR 5m (resolucion intrabar mejorada)")

    # comparacion: mismo tramo de fechas con el motor 15m puro
    lo = bars_15m[0][0]
    hi = bars_15m[-1][0]
    bars_15m_full = base.load_bars()
    bars_15m_same_range = [b for b in bars_15m_full if lo <= b[0] <= hi]
    trades_15m_same_range = base.run_backtest(bars_15m_same_range, cooldown_bars=0, lock_r=0.8)
    base.summarize(trades_15m_same_range, "MOTOR 15m puro (mismo rango de fechas, para comparar)")
