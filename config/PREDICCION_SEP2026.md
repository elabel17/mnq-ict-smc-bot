# Predicción registrada ANTES del replay — 2026-09-10

Configuración A (frescura ≤3), dos sesiones, **4 contratos**.
Emitida antes de correr el replay en NinjaTrader, para que la comparación
sea una prueba real y no un ajuste posterior.

## 1 al 8 de septiembre de 2026

**8 operaciones · 8 aciertos · neto $1.188**

| entrada (NY) | dir | entrada | stop | salida | pnl |
|---|---|---|---|---|---|
| 09-01 04:40 | CORTO | 29273.00 | 29313.25 | 29252.88 | $149 |
| 09-02 02:05 | CORTO | 29054.00 | 29078.50 | 29041.75 | $86 |
| 09-02 02:45 | LARGO | 29063.00 | 29020.75 | 29084.12 | $157 |
| 09-02 09:50 | CORTO | 29067.50 | 29119.50 | 29041.50 | $196 |
| 09-03 10:15 | CORTO | 29310.75 | 29368.50 | 29281.88 | $219 |
| 09-04 03:35 | LARGO | 29630.75 | 29613.00 | 29639.62 | $59 |
| 09-04 09:55 | LARGO | 29653.00 | 29596.25 | 29681.38 | $215 |
| 09-08 02:50 | LARGO | 29596.50 | 29566.75 | 29611.38 | $107 |

## 27 agosto al 8 septiembre (ventana completa del replay)

**15 operaciones · 13 aciertos · neto $1.625**
Perdedoras: 27-ago 03:45 (−$284) y 27-ago 09:40 (−$204).

NinjaTrader arranca a cargar desde el 27 de agosto por el calentamiento de
80 barras, así que ésta es la cifra a comparar.

## Criterio de aceptación

| | |
|---|---|
| **coincide** | 13–17 operaciones, neto entre $1.300 y $1.900 |
| **no coincide** | menos de 10 o más de 20 operaciones, o neto fuera de ese rango |

Si no coincide, el CSV de `Documents/NinjaTrader 8/export/` dirá en qué
operación se separan los dos.

## Resultado real

_(pendiente — rellenar tras el replay)_
