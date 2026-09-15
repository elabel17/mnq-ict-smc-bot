"""Diagnostico correcto: reusa la logica REAL de simular() (con la zona sin
limite de edad) y registra, para cada entrada, el modo de deteccion
(desplazamiento/BOS), cuantas velas llevaba viva la zona al tocarse, y la
deriva de precio en la confirmacion -- para cruzar con TODAS las notas
dejadas en el artifact, no solo las primeras 5."""
import motor_confluencia as M
from liquidez_apilada import _apilamiento
import experimentos_liquidez as E
import datetime as dt
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
bars = E.cargar_bars()
O = [b[1] for b in bars]; H = [b[2] for b in bars]
L = [b[3] for b in bars]; C = [b[4] for b in bars]; T = [b[0] for b in bars]
n = len(bars)
cfg = E.BASE_CFG
avg = M._avg_range(H, L, n)
ob_disp = M.detectar_ob(O, H, L, C, avg, cfg["disp_mult"], cfg["disp_frac"])
ob_bos = M.detectar_ob_bos(O, H, L, C, cfg["pivote_lado"], cfg["bos_disp_mult"], avg, cfg["bos_scan"])
ob = [ob_disp[i] if ob_disp[i] is not None else ob_bos[i] for i in range(n)]
modo_arr = ["DISP" if ob_disp[i] is not None else ("BOS" if ob_bos[i] is not None else None) for i in range(n)]
fvg = M.detectar_fvg(O, H, L, C)
piv_hi, piv_lo, conf = M.detectar_pivotes(H, L, cfg["pivote_lado"])
activar_hi = {}; activar_lo = {}
for i in range(n):
    if piv_hi[i] is not None: activar_hi.setdefault(conf[i], []).append(piv_hi[i])
    if piv_lo[i] is not None: activar_lo.setdefault(conf[i], []).append(piv_lo[i])
cur_hi, cur_lo = [], []
nym = [dt.datetime.fromtimestamp(t, tz=dt.timezone.utc).astimezone(NY).hour * 60 +
       dt.datetime.fromtimestamp(t, tz=dt.timezone.utc).astimezone(NY).minute for t in T]

vivas = []
arm = None
open_ = False; dir_ = 0
resultados = {}

for i in range(n):
    cur_hi.extend(activar_hi.get(i, [])); cur_lo.extend(activar_lo.get(i, []))
    cur_hi[:] = [v for v in cur_hi if not (H[i] > v + 1.0 and C[i] < v)]
    cur_lo[:] = [v for v in cur_lo if not (L[i] < v - 1.0 and C[i] > v)]
    if ob[i] is not None:
        d0, top, bot = ob[i]
        vivas.append([d0, top, bot, i, False, False, modo_arr[i]])
    if fvg[i] is not None:
        fd, f_top, f_bot = fvg[i]
        for z in vivas:
            if z[0] == fd and not (f_bot > z[1] or f_top < z[2]): z[5] = True
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
                if not z[5]: continue
                liqS = M._liq_favor_peligro(z[0], z[1], z[2], cur_hi, cur_lo, cfg["dist_mult_liq"])
                if liqS != 100: continue
                if z[0] == 1 and z[2] - cfg["entry_buf"] <= L[i] <= z[1] + cfg["entry_buf"]:
                    arm = [1, z[1], z[2], i, z[3], z[6]]; break
                if z[0] == -1 and z[2] - cfg["entry_buf"] <= H[i] <= z[1] + cfg["entry_buf"]:
                    arm = [-1, z[1], z[2], i, z[3], z[6]]; break
        elif i - arm[3] > cfg["espera"]:
            arm = None
        if arm is not None and i > arm[3]:
            cuerpo = abs(C[i] - O[i]); r_ = H[i] - L[i]
            if arm[0] == 1:
                ok = C[i] > O[i] and r_ > 0 and cuerpo >= cfg["cuerpo_frac"] * r_ and C[i] > arm[1]
                if ok:
                    ep = C[i]
                    s = dt.datetime.fromtimestamp(T[i], tz=dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                    resultados[s] = dict(dir="LONG", zona=(arm[2], arm[1]), entrada=ep,
                                          deriva=ep - arm[1], modo=arm[5], edad_al_tocar=arm[3] - arm[4])
                    open_ = True; dir_ = 1; arm = None
            else:
                ok = C[i] < O[i] and r_ > 0 and cuerpo >= cfg["cuerpo_frac"] * r_ and C[i] < arm[2]
                if ok:
                    ep = C[i]
                    s = dt.datetime.fromtimestamp(T[i], tz=dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                    resultados[s] = dict(dir="SHORT", zona=(arm[2], arm[1]), entrada=ep,
                                          deriva=arm[2] - ep, modo=arm[5], edad_al_tocar=arm[3] - arm[4])
                    open_ = True; dir_ = -1; arm = None
    if open_ and i > 0:
        # simplificado: no seguimos gestion aqui, solo detectamos la proxima vela para liberar open_
        # (el diagnostico solo necesita el momento de entrada, no el resultado)
        open_ = False

TODAS_LAS_NOTAS = [
    "2025-09-26 13:45:00", "2025-09-26 14:45:00", "2025-10-03 15:45:00",
    "2025-10-06 13:15:00", "2025-10-10 13:30:00", "2025-11-13 17:15:00",
    "2025-11-17 13:15:00",
]
for s in TODAS_LAS_NOTAS:
    r = resultados.get(s)
    if r is None:
        print(f"{s}  -> NO ENCONTRADA en la simulacion (revisar timestamp)")
        continue
    print(f"{s}  {r['dir']:5}  modo={r['modo']:4}  zona=[{r['zona'][1]:.2f},{r['zona'][0]:.2f}]  "
          f"entrada={r['entrada']:.2f}  deriva={r['deriva']:+.2f}pts  edad_al_tocar={r['edad_al_tocar']}velas")
