"""Colapsa el archivo de ticks (UTC, confirmado contra el 5m ya validado) a
velas de 1 minuto. Unica fuente de datos permitida a partir de ahora, junto
con el propio archivo de ticks para la verificacion final mas fina."""
import json, time, datetime as dt

ARCHIVO = r"C:\Users\diazl\Downloads\mnq-ict-smc-bot\ticks data\MNQ 12-25 complete.Last.txt"
SALIDA_1M = "ticks_1m_sep_dic_2025.json"

t0 = time.time()
agg = {}  # minute_epoch -> [o,h,l,c,vol]
dia_cache = None
medianoche_epoch = 0
n_lineas = 0

with open(ARCHIVO, "r", encoding="ascii", errors="ignore") as f:
    for linea in f:
        n_lineas += 1
        try:
            campo0, resto = linea.split(";", 1)
            fecha = campo0[0:8]
            hh = int(campo0[9:11]); mm = int(campo0[11:13])
        except (ValueError, IndexError):
            continue
        if fecha != dia_cache:
            dia_cache = fecha
            d = dt.datetime.strptime(fecha, "%Y%m%d").replace(tzinfo=dt.timezone.utc)
            medianoche_epoch = int(d.timestamp())
        minuto = medianoche_epoch + hh * 3600 + mm * 60
        try:
            precio = float(resto.split(";", 1)[0])
            vol = int(resto.rsplit(";", 1)[1])
        except (ValueError, IndexError):
            continue
        bar = agg.get(minuto)
        if bar is None:
            agg[minuto] = [precio, precio, precio, precio, vol]
        else:
            if precio > bar[1]: bar[1] = precio
            if precio < bar[2]: bar[2] = precio
            bar[3] = precio
            bar[4] += vol

print("lineas leidas: {:,}  minutos distintos: {:,}  tiempo: {:.1f}s".format(
    n_lineas, len(agg), time.time() - t0))

bars = [[t] + v for t, v in sorted(agg.items())]
json.dump(bars, open(SALIDA_1M, "w"))
print("guardado {} ({} velas de 1m)".format(SALIDA_1M, len(bars)))
print("desde", dt.datetime.utcfromtimestamp(bars[0][0]), "hasta", dt.datetime.utcfromtimestamp(bars[-1][0]))
