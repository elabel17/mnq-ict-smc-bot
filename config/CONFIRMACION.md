# Entrada por confirmación — la única línea con ventaja

Fecha: **2026-09-11**. Tras descartar los Order Blocks operados con orden
límite descansando en la zona (ver VEREDICTO_5M.md y VEREDICTO_15M.md), se
probó la mecánica que describe el manual del usuario: esperar la vela de
reacción y entrar a su cierre.

**Causal por construcción**: el precio de entrada es el cierre de una vela ya
formada. No existe forma de escogerlo mirando hasta dónde llegó la vela.

Motor: `data/engine/python/motor15.py` con `confirmar=True` y los tres
look-ahead desactivados (`la3_entrada`, `la4_barrido`, `la7_mismavela` = False).

## Resultados (3 contratos, 2020-2026, 2 ticks slippage, $1/lado)

| variante | ops | neto | PF | DD | WR | mitad 1 / 2 |
|---|---|---|---|---|---|---|
| límite en zona (referencia causal) | 1.224 | −$2.311 | 0.99 | $15.548 | 50,2% | — |
| confirmación 15m, sesión 18-11 | 811 | $34.928 | 1.36 | $6.160 | 52,2% | 1.40 / 1.32 |
| **confirmación 15m, sesión 09-11 NY** | **273** | **$39.001** | **1.99** | **$4.235** | 57,1% | **1.99 / 2.00** |
| confirmación 15m, sesión 10-11 NY | 191 | $33.217 | 2.20 | $4.325 | 58,6% | 2.32 / 2.07 |
| confirmación 15m, sesión 09-14 NY | 588 | $57.823 | 1.68 | $6.652 | 53,9% | 1.57 / 1.80 |

Parámetros de la fila marcada: `cuerpo_frac 0.4`, `espera 8`, cierre fuera de
la zona exigido, `rr1 1.5`, `rr2 6.0`, `be_trig 1.0`, `lock_r 0.5`, `sl_buf 2.0`.

## Por qué la sesión importa tanto

PnL por hora NY con la ventana amplia (18:00-11:00):

| hora | ops | neto | PF |
|---|---|---|---|
| **10:00** | 160 | **$29.803** | **2.34** |
| 9:00 | 71 | $2.481 | 1.22 |
| 5:00 | 98 | −$4.375 | 0.56 |
| 6:00 | 61 | −$1.877 | 0.65 |

La hora de 10:00 NY produce el 85% del beneficio en el 6% del tiempo de
sesión. El sistema nunca fue rentable durante diecisiete horas: era rentable
dos horas al día y el resto devolvía las ganancias.

## Lo que NO funciona

| variante | PF | problema |
|---|---|---|
| confirmación con vela de **5m** sobre zona de 15m | 1.11 | la vela de 5m es demasiado barata como señal: aparece aunque el precio siga empujando en contra |
| zona y confirmación ambas en **5m** | 1.39 | mitades 0.97 / 1.86 — solo funcionó en 2025-2026 |
| filtro de fuerza del desplazamiento | 1.96 vs 1.99 | útil en la ventana amplia (1.36→1.56), irrelevante acotando la sesión |
| filtro de frescura de zona | 1.56 con edad≤2 | no mejora sobre la ventana acotada |

## Advertencias

1. **273 operaciones en 6,2 años** (~44/año). Muestra corta. Restringido a
   2024-2026 quedan 98 operaciones y las mitades se abren a 1.56 / 3.06.
2. **La ventana horaria se eligió mirando qué horas ganaron.** Es ajuste a la
   muestra por construcción. Lo que lo salva parcialmente es que las mitades
   del histórico completo dan 1.99 y 2.00.
3. **La magnitud es pequeña**: $39.001 en 6,2 años con 3 contratos son $6.290
   al año. Con un límite de drawdown de $2.000 solo admite 1 contrato
   (~$2.100/año).

## Pendiente

- Barrido de gestión (RR1, RR2, BE, lock, buffer de stop) — nunca se ajustó
  a la entrada por confirmación
- Verificación en NinjaTrader con predicción registrada
