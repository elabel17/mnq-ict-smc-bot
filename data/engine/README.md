# Motor de backtest recuperado y validado

Este motor (`backtest_engine_validated.js` + `setup_ny_arrays.js`) es el
código real, recuperado línea por línea del log crudo de la sesión (el
archivo `.jsonl` de la conversación, que conserva todo el historial aunque
el contexto visible se resuma), que generó los números considerados
"definitivos" del proyecto hasta el 2026-09-06.

## Por qué se perdió y cómo se recuperó

Todo el trabajo de backtesting de este proyecto se hizo ejecutando JS
directamente en la consola del navegador de TradingView Desktop (vía
`ui_evaluate`/CDP), sin guardar nunca el código como archivo. Cuando el
contexto de la conversación se resume, ese código deja de estar visible —
pero el log crudo de la sesión (`.jsonl`) sí lo conserva íntegro. Se
recuperó buscando el resultado exacto ("118990", "127834") dentro del log y
extrayendo el `tool_use` de `ui_evaluate` inmediatamente anterior.

## Resultados oficiales confirmados (histórico ~5 años, construido vía
anclas de Replay + cambio a 15M — dataset ya no disponible, ver limitación
abajo)

| Config | Trades | Neto | PF | Max DD |
|---|---|---|---|---|
| Baseline (breakeven puro al llegar a 1.2R, TP1=1.8R/TP2=4R) | 970 | **$118.990** | 2.81 | −$1.894 |
| +0.2R asegurado | 1.022 | $125.111 | 2.84 | −$1.859 |
| +0.3R | 1.039 | $124.334 | 2.79 | −$1.841 |
| +0.4R | 1.063 | $126.597 | 2.78 | −$1.823 |
| **+0.5R — CONFIG ADOPTADA** | **1.074** | **$127.834** | 2.75 | −$1.806 |
| +0.6R | 1.084 | $131.631 | 2.78 | −$1.788 |
| +0.8R (rechazada — cerca del límite físico) | 1.105 | $139.942 | 2.87 | −$1.753 |
| +0.9R (rechazada) | 1.108 | $144.351 | 2.93 | −$1.736 |
| +1.0R (rechazada) | 1.112 | $147.751 | 2.96 | −$1.718 |
| +1.1R (rechazada) | 1.115 | $156.223 | 3.07 | −$1.701 |
| +1.2R = límite físico (rechazada, señal de sobreajuste) | 1.116 | $164.545 | 3.18 | −$1.683 |

**El número correcto y adoptado es $127.834, no $118.990 (ese es el
baseline previo a la mejora) ni $140.000 (ese es aproximadamente el valor
de +0.8R/+0.9R, explícitamente descartado por estar demasiado cerca del
límite físico de 1.2R donde el backtest deja de ser confiable).**

## Auditoría de fidelidad (2026-09-07)

Se comparó línea por línea este motor contra el código fuente real de
`ICT_15M_OB_Entry_v12.pine` y se confirmó que replica correctamente:

- el ciclo de vida de la zona `cleared -> touchable -> consumida`
  (`bTou`/`sTou`) — un OB solo es "tocable" para entrada después de que el
  precio se alejó limpiamente de él, no desde el momento en que se forma;
- la exclusividad de un solo trade abierto a la vez (`ce = inSession && !open`);
- el modelo de entrada tipo orden límite en el borde del OB
  (`ep = max(low, bullTop)`), no una entrada a mercado;
- el filtro de domingo;
- el "no downgradear" una protección de breakeven ya mejor.

Esto es justo lo que un análisis apresurado hecho el mismo día (2026-09-07,
para el estudio del margen de 12pt en OB de rango grande) NO tenía —
faltaba la condición `cleared`, lo cual duplicaba aproximadamente el
resultado ($20.670 en vez de los $9.217 reales sobre la misma ventana de 5
meses). Ver `docs/ANALYSIS_LOG.md`.

## Verificación cruzada parcial (2026-09-07)

Se corrió este mismo motor recuperado, sin modificarlo, sobre el dataset de
5.2 meses guardado en `data/mnq_15m_bars.json` (abr-sep 2026, el único
histórico disponible hoy):

| Config | Trades | Neto |
|---|---|---|
| lock=0R | 63 | $6.209 |
| lock=0.5R | 68 | $8.621 |

**La dirección del hallazgo se confirma de forma independiente**: el
breakeven anticipado con +0.5R sigue mejorando el resultado en una ventana
de datos completamente distinta a la usada originalmente. Esto NO prueba
que $127.834 sea exacto (la magnitud no es comparable, la ventana es mucho
más corta), pero sí es evidencia de que el mecanismo y el motor son
metodológicamente sólidos, no un artefacto de una muestra particular.

## Limitación pendiente

El histórico completo de ~5 años usado para llegar a $118.990/$127.834 se
construyó vía anclas de Bar Replay (Daily -> cambio a 15M, ~13 anclas) y
se perdió en un crash de la conexión CDP con TradingView Desktop. Hoy solo
se pudo reconstruir una ventana de 5.2 meses (abr-sep 2026, ver
`data/mnq_15m_bars.json`). Para confirmar $127.834 con certeza total
(no solo la dirección del efecto), hace falta reconstruir el histórico
completo y volver a correr exactamente este motor (`backtest_engine_validated.js`)
sobre él.
