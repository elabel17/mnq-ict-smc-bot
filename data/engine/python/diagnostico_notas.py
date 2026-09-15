"""Cruza las 5 operaciones marcadas por el usuario en el artifact contra el
motor: identifica el modo de deteccion (desplazamiento vs BOS), y cuanto se
alejo el precio de ENTRADA real respecto al borde de la zona -- para
confirmar o descartar la queja: 'entra en el punto mas alto, sin apoyo de OB
decente ni liquidez a favor'."""
import motor_confluencia as M
from liquidez_apilada import _apilamiento
import experimentos_liquidez as E
import datetime as dt

FLAGGED = [
    "2025-09-26 13:45:00",
    "2025-09-26 14:45:00",
    "2025-10-03 15:45:00",
    "2025-10-06 13:15:00",
    "2025-10-10 13:30:00",
]

bars = E.cargar_bars()
O = [b[1] for b in bars]; H = [b[2] for b in bars]
L = [b[3] for b in bars]; C = [b[4] for b in bars]; T = [b[0] for b in bars]
n = len(bars)
cfg = E.BASE_CFG
avg = M._avg_range(H, L, n)
ob_disp = M.detectar_ob(O, H, L, C, avg, cfg["disp_mult"], cfg["disp_frac"])
ob_bos = M.detectar_ob_bos(O, H, L, C, cfg["pivote_lado"], cfg["bos_disp_mult"], avg, cfg["bos_scan"])

t_to_idx = {t: i for i, t in enumerate(T)}

for s in FLAGGED:
    t0 = dt.datetime.strptime(s, "%Y-%m-%d %H:%M:%S").replace(tzinfo=dt.timezone.utc).timestamp()
    idx = t_to_idx.get(int(t0))
    if idx is None:
        print(s, "-> no encontrado exacto"); continue
    ep = C[idx]
    # buscar hacia atras la zona que armo esta entrada (dentro de esperaVelas)
    encontrado = False
    for back in range(1, cfg["espera"] + 2):
        j = idx - back
        if j < 0: break
        for arr, modo in [(ob_disp, "DESPLAZAMIENTO"), (ob_bos, "BOS")]:
            if arr[j] is not None:
                d0, top, bot = arr[j]
                if (d0 == 1 and C[idx] > O[idx]) or (d0 == -1 and C[idx] < O[idx]):
                    dist = (ep - top) if d0 == 1 else (bot - ep)
                    print(f"{s}  dir={'LONG' if d0==1 else 'SHORT'}  modo={modo:15}  "
                          f"zona=[{bot:.2f},{top:.2f}]  entrada={ep:.2f}  "
                          f"distancia_mas_alla_del_borde={dist:+.2f}pts  (nacida {back} velas antes)")
                    encontrado = True
                    break
        if encontrado: break
    if not encontrado:
        print(s, "-> zona de origen no identificada en la ventana de espera")
