# Configuraciones validadas — MNQ 5m

Fecha de la validación: **2026-09-10**
Histórico: 2024-01 a 2026-09 (2,61 años, 185.066 velas de 5m)
Supuestos: 2 ticks de slippage, $1,00/contrato/lado, MNQ ($2/punto)
Motor: `data/engine/python/v_nivel.py` (causal — reprodujo exactamente las
83 operaciones del replay de NinjaTrader del 27-ago al 8-sep de 2026)

---

## Parámetros comunes a las dos configuraciones

| parámetro | valor |
|---|---|
| sesiones (NY) | 09:00–11:00 y 02:00–06:00 |
| disp_len / disp_mult | 60 / **2.0** |
| disp_close_frac | 0.6 |
| ob_scan_bars | 10 |
| liq_check_bars / liq_tolerance | 12 / 1.0 pts |
| liq_accum_bars | 15 |
| nivel de entrada | `high + margen` (FUERA de la mecha) |
| entry_buffer | 8.0 pts |
| sl_buffer | 0.5 pts |
| RR2 | 5.0 |
| BE: gatillo / asegura | 0.6R / 0.5R |
| tope de riesgo | 100 pts |

**Regla dura:** `lock_r` SIEMPRE menor que `be_trigger_r`. Al revés el stop
queda por encima del precio y el broker lo rechaza (ver ANALISIS_CAUSAL.md).

---

## A) PASAR LA CUENTA  ·  `zone_max_age = 3`

Solo se opera la zona si el precio vuelve dentro de las **3 primeras velas**.

1.054 operaciones · PF **1.92** · mitades 1.87 / 1.98 · WR 69.4% · 5 meses negativos de 33

| contratos | DD máx | neto 2,61a | por año |
|---|---|---|---|
| 1 | $623 | $19.716 | $7.554 |
| 2 | $1.246 | $39.433 | $15.108 |
| **3** | **$1.870** | **$59.150** | **$22.663** |
| 4 | $2.493 | $78.866 | $30.217 |
| 6 | $3.740 | $118.299 | $45.325 |
| 10 | $6.232 | $197.165 | $75.542 |

Días de calendario hasta +$3.000 con 3 contratos:
p10 21 d · p25 29 d · **mediana 44 d (6,3 semanas)** · p75 76 d · p90 121 d

## B) MÁXIMO NETO  ·  `zone_max_age = 60`

Sin filtro de frescura. Más dinero, casi el doble de drawdown.

2.897 operaciones · PF **1.47** · mitades 1.48 / 1.45 · WR 64.9%

| contratos | DD máx | neto 2,61a | por año |
|---|---|---|---|
| 2 | $2.514 | $61.254 | $23.469 |
| 3 | $3.771 | $91.882 | $35.204 |
| 4 | $5.028 | $122.509 | $46.938 |
| 6 | $7.542 | $183.764 | $70.407 |
| 10 | $12.570 | $306.272 | $117.346 |

## Variante: solo mañana 09–11, frescura ≤3

510 operaciones · PF **2.13** (el más alto) · mitades 2.21 / 2.07
3 contratos → neto $45.404, DD $3.244 · 4 contratos → $60.539, DD $4.326

Mejor calidad, peor drawdown: las dos sesiones no pierden a la vez y eso
suaviza la curva. Usar después de pasar la cuenta.

---

## Descartado, con datos

| idea | resultado |
|---|---|
| entrada en el cuerpo del OB | PF 1.10 |
| mean threshold (mitad del cuerpo) | PF 1.17, WR 44% |
| sesgo 15m/30m/1h/4h (EMA y SMA 10/20/50) | ninguno supera 1.42 vs 1.41 |
| sesión 18:00–24:00 NY | PF 1.06, pierde en la 1ª mitad |
| sesión 20:00–24:00 NY | PF 1.01 |
| parciales al mover a BE | hasta −40% |
| `lock_r` > `be_trigger_r` | imposible de ejecutar |
| una orden por cada zona viva | fills múltiples, 8 contratos en el replay |
