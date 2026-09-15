"""Bar-model rapido de parciales (1 de 3 en RR1=1.5, resto a RR2=4.0), con
y sin BE anticipado, sobre 5m Y 15m -- solo para tener un panorama de
contexto en 5m (no vale la pena verificar a tick un timeframe con
parametros sin recalibrar, ya sabemos que pierde con posicion completa)."""
import experimentos_liquidez as E


def simular_parcial(bars, edad_max, exigir_fvg, liquidez_modo, be_trig, lock_r,
                     rr1=1.5, rr2=4.0, qty_total=3, qty_parcial=1):
    cfg = dict(E.BASE_CFG, be_trig=be_trig, lock_r=lock_r, rr1=rr1, rr2=rr2)
    O = [b[1] for b in bars]; H = [b[2] for b in bars]
    L = [b[3] for b in bars]; C = [b[4] for b in bars]
    n = len(bars)
    import motor_confluencia as M
    from liquidez_apilada import detectar_gaps, _apilamiento
    avg = M._avg_range(H, L, n)
    ob_disp = M.detectar_ob(O, H, L, C, avg, cfg["disp_mult"], cfg["disp_frac"])
    ob_bos = M.detectar_ob_bos(O, H, L, C, cfg["pivote_lado"], cfg["bos_disp_mult"], avg, cfg["bos_scan"])
    ob = [ob_disp[i] if ob_disp[i] is not None else ob_bos[i] for i in range(n)]
    fvg = M.detectar_fvg(O, H, L, C)
    piv_hi, piv_lo, conf = M.detectar_pivotes(H, L, cfg["pivote_lado"])
    activar_hi = {}; activar_lo = {}
    for i in range(n):
        if piv_hi[i] is not None: activar_hi.setdefault(conf[i], []).append(piv_hi[i])
        if piv_lo[i] is not None: activar_lo.setdefault(conf[i], []).append(piv_lo[i])
    cur_hi, cur_lo = [], []
    T = [b[0] for b in bars]
    import datetime as dt
    from zoneinfo import ZoneInfo
    NY = ZoneInfo("America/New_York")
    nym = [dt.datetime.fromtimestamp(t, tz=dt.timezone.utc).astimezone(NY).hour * 60 +
           dt.datetime.fromtimestamp(t, tz=dt.timezone.utc).astimezone(NY).minute for t in T]

    vivas = []
    arm = None
    open_ = False; dir_ = 0; ep = sl = risk = 0.0
    eIdx = 0; tomoParcial = False; movedBE = False
    pnl_total = 0.0; g = l = 0.0; n_trades = 0

    for i in range(n):
        cur_hi.extend(activar_hi.get(i, [])); cur_lo.extend(activar_lo.get(i, []))
        cur_hi[:] = [v for v in cur_hi if not (H[i] > v + 1.0 and C[i] < v)]
        cur_lo[:] = [v for v in cur_lo if not (L[i] < v - 1.0 and C[i] > v)]
        if ob[i] is not None:
            d0, top, bot = ob[i]
            vivas.append([d0, top, bot, i, False, False, _apilamiento(ob, i, d0, top, bot)])
        if fvg[i] is not None:
            fd, f_top, f_bot = fvg[i]
            for z in vivas:
                if z[0] == fd and not (f_bot > z[1] or f_top < z[2]): z[5] = True
        if edad_max is not None:
            vivas = [z for z in vivas if (i - z[3]) <= edad_max]
        for z in vivas:
            if z[4] or z[3] == i: continue
            if z[0] == 1 and L[i] > z[1]: z[4] = True
            elif z[0] == -1 and H[i] < z[2]: z[4] = True

        ses_ini_, ses_fin_ = cfg["ses_ini"], cfg["ses_fin"]
        inS = ses_ini_ <= nym[i] < ses_fin_ if ses_ini_ < ses_fin_ else (nym[i] >= ses_ini_ or nym[i] < ses_fin_)
        if not open_ and inS:
            if arm is None:
                for z in vivas:
                    if not z[4] or z[3] == i: continue
                    if exigir_fvg and not z[5]: continue
                    if liquidez_modo != "off":
                        liqS = M._liq_favor_peligro(z[0], z[1], z[2], cur_hi, cur_lo, cfg["dist_mult_liq"])
                        if liquidez_modo == "solo_favor" and liqS != 100: continue
                    if z[0] == 1 and z[2] - cfg["entry_buf"] <= L[i] <= z[1] + cfg["entry_buf"]:
                        arm = [1, z[1], z[2], i]; break
                    if z[0] == -1 and z[2] - cfg["entry_buf"] <= H[i] <= z[1] + cfg["entry_buf"]:
                        arm = [-1, z[1], z[2], i]; break
            elif i - arm[3] > cfg["espera"]:
                arm = None
            if arm is not None and i > arm[3]:
                cuerpo = abs(C[i] - O[i]); r_ = H[i] - L[i]
                if arm[0] == 1:
                    ok = C[i] > O[i] and r_ > 0 and cuerpo >= cfg["cuerpo_frac"] * r_ and C[i] > arm[1]
                    if ok:
                        _ep = C[i]; _sl = min(arm[2], L[i]) - cfg["sl_buf"]; _r = _ep - _sl
                        if 0 < _r <= 100.0:
                            ep, sl, risk, open_, dir_, eIdx = _ep, _sl, _r, True, 1, i
                            tomoParcial = movedBE = False
                            arm = None
                else:
                    ok = C[i] < O[i] and r_ > 0 and cuerpo >= cfg["cuerpo_frac"] * r_ and C[i] < arm[2]
                    if ok:
                        _ep = C[i]; _sl = max(arm[1], H[i]) + cfg["sl_buf"]; _r = _sl - _ep
                        if 0 < _r <= 100.0:
                            ep, sl, risk, open_, dir_, eIdx = _ep, _sl, _r, True, -1, i
                            tomoParcial = movedBE = False
                            arm = None
        if open_ and i > eIdx:
            t1 = ep + risk * rr1 * dir_; t2 = ep + risk * rr2 * dir_
            hitSL = (L[i] <= sl) if dir_ == 1 else (H[i] >= sl)
            hitT1 = (H[i] >= t1) if dir_ == 1 else (L[i] <= t1)
            hitT2 = (H[i] >= t2) if dir_ == 1 else (L[i] <= t2)
            slip = 0.5; PV = 2.0
            if hitSL:
                pnl = 0.0
                if tomoParcial:
                    pnl += ((t1 - ep) * dir_ - slip) * PV * qty_parcial - 1.0 * qty_parcial * 2
                    qr = qty_total - qty_parcial
                    pnl += ((sl - ep) * dir_ - slip) * PV * qr - 1.0 * qr * 2
                else:
                    pnl += ((sl - ep) * dir_ - slip) * PV * qty_total - 1.0 * qty_total * 2
                pnl_total += pnl; n_trades += 1
                if pnl > 0: g += pnl
                else: l += -pnl
                open_ = False
            elif tomoParcial and hitT2:
                pnl = ((t1 - ep) * dir_ - slip) * PV * qty_parcial - 1.0 * qty_parcial * 2
                qr = qty_total - qty_parcial
                pnl += ((t2 - ep) * dir_ - slip) * PV * qr - 1.0 * qr * 2
                pnl_total += pnl; n_trades += 1
                if pnl > 0: g += pnl
                else: l += -pnl
                open_ = False
            elif not tomoParcial and hitT1:
                tomoParcial = True
                be = ep + risk * lock_r * dir_
                if (not movedBE) or (be > sl if dir_ == 1 else be < sl): sl = be
                movedBE = True
            elif not movedBE and be_trig < 999:
                re = (H[i] - ep) / risk if dir_ == 1 else (ep - L[i]) / risk
                if re >= be_trig:
                    sl = ep + risk * lock_r * dir_; movedBE = True
    return dict(trades=n_trades, net=round(pnl_total, 2), pf=round(g / l, 2) if l else 0)


for tf, fn in [("15m", "ticks_15m_sep_dic_2025.json"), ("5m", "ticks_5m_sep_dic_2025.json")]:
    bars = E.cargar_bars(fn)
    for be_label, be_trig, lock_r in [("con BE 0.4R", 0.4, 0.2), ("sin BE", 999, 0.0)]:
        r = simular_parcial(bars, edad_max=None, exigir_fvg=True, liquidez_modo="solo_favor",
                             be_trig=be_trig, lock_r=lock_r)
        print(f"{tf:>4}  parcial + {be_label:12}  ->  ops={r['trades']:>4}  net=${r['net']:>10.2f}  PF={r['pf']:.2f}")
