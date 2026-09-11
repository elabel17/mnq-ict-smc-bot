# Veredicto 15m — SIN VENTAJA

Fecha: **2026-09-11**. Auditoría del motor `backtest_engine_validated.js`
(el que reportaba $121.696 / PF 3.08) con el mismo rasero aplicado al de 5m.

Puerto fiel en `data/engine/python/motor15.py`, con un interruptor por cada
look-ahead para poder medir su aporte por separado. El puerto reproduce el
original: $120.913 / PF 2.33.

## Los tres look-aheads encontrados

| # | qué hace | dónde |
|---|---|---|
| 3 | `ep = max(low, zoneTop)` — el precio de entrada se escoge después de ver hasta dónde llegó la vela | línea 55 del .js |
| 4 | exige `low >= zoneBot` — descarta a posteriori las velas que perforaron el fondo del OB | línea 52 |
| 7 | permite entrar en la MISMA vela en que la zona se valida, cuando la orden aún no podía estar puesta | líneas 48-49 |

## Impacto medido (3 contratos, 2020-2026)

| modelo | ops | neto | PF | DD | WR |
|---|---|---|---|---|---|
| ORIGINAL | 1.324 | $120.913 | 2.33 | $2.559 | 73,1% |
| sin #3 | 1.195 | $57.893 | 1.44 | $5.568 | 58,9% |
| sin #4 | 1.442 | $103.539 | 1.95 | $3.324 | 67,9% |
| sin #7 | 1.174 | $79.593 | 1.92 | $2.618 | 71,2% |
| **CAUSAL** | 1.224 | **−$2.311** | **0.99** | $15.548 | **50,2%** |

El win rate cae del 73,1% al 50,2%. Es una moneda.

El más caro es el #3, que vale $63.000 por sí solo. Es el mismo error
`math.max(low, z.top)` ya identificado en el Pine semanas antes.

## Conclusión conjunta con el 5m

| | original | causal |
|---|---|---|
| 5m | $386.343 · PF 3.02 | $3.312 · PF 1.03 |
| 15m | $120.913 · PF 2.33 | −$2.311 · PF 0.99 |

La detección de Order Blocks por desplazamiento, operada con **orden límite
descansando en la zona**, no tiene ventaja en MNQ en ninguno de los dos
marcos temporales.

Los dos motores se escribieron por separado, con parámetros distintos, y
contienen el mismo error central. No es casualidad: cada uno se optimizó
contra su propio motor, y la optimización busca precisamente donde el motor
miente.

## Lo que NO se ha probado

**Entrada por confirmación**: esperar la vela de reacción en la zona y entrar
a su cierre. Causal por construcción — el precio es el cierre de una vela ya
formada, no se puede escoger a posteriori. Único camino abierto para esta
familia de estrategia.
