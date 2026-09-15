# MNQ ICT/SMC Order Block Bot

Estrategia Pine Script v6 (ICT/SMC Order Blocks) para MNQ (Micro Nasdaq-100
futures, `CME_MINI_DL:MNQ1!`), backtesteada con un servidor MCP a medida
(TradingView Desktop controlado vía CDP). Regla no negociable en todo el
proyecto: **ningún backtest usa información futura del precio**.

## Estado (actualizado 2026-09-14)

> ## ⛔ La estrategia de 5m NO ES OPERABLE
>
> Verificada contra NinjaTrader: predicción +$1.625, resultado real **−$832**.
> Se encontraron **siete look-aheads** en el motor de Python. Corregidos todos,
> el sistema da **PF 1.03**. Una búsqueda de 160 configuraciones contra el motor
> causal no supera **PF 1.13**.
>
> Veredicto completo: [config/VEREDICTO_5M.md](config/VEREDICTO_5M.md)
> Historia de los errores: [config/ANALISIS_CAUSAL.md](config/ANALISIS_CAUSAL.md)
>
> **Cualquier cifra anterior de este repositorio ($386.343, $290.250, $84.831)
> es inválida.** Las configuraciones de `config/CONFIGURACIONES.md` se midieron
> con motores que tenían el séptimo look-ahead y tampoco deben usarse.

### 15m — variante F, verificada tick a tick (la línea de mayor confianza del proyecto)

**Union (desplazamiento+BOS) + FVG + liquidez a favor, sin límite de edad de
zona, sesión 08-13 NY**: 54/55 operaciones resueltas, **neto $4.213, PF 2.12**
(sep-dic 2025, 3 contratos), verificado tick a tick contra el archivo real de
ticks de MNQ — no solo modelo por vela. Drawdown máximo real: $1.637 (3
contratos). Con 4 contratos: 87% de probabilidad de pasar una cuenta de
evaluación TopStep 50k ($3.000 objetivo, $2.000 pérdida máxima) en mediana
4,9 semanas (con 3 contratos: 96,7% en 7,1 semanas). Detalle completo:
[CONFLUENCIA_Y_LIQUIDEZ.md](config/CONFLUENCIA_Y_LIQUIDEZ.md).

Reemplaza la configuración anterior de esta misma línea (frescura de 3h,
sin gate de liquidez: 24 ops, $3.060, PF 2.43) — esa sigue disponible como
opción en `pine/automation/ICT_UnionFVG_15M_Strategy.cs` (EdadMaxVelas=12,
ExigirLiquidezFavor=false) pero la variante F gana en frecuencia y PF
combinados.

Otras líneas exploradas, con menor confianza (no verificadas tick a tick o
con muestra insuficiente):

| línea | PF | ops/año | ver |
|---|---|---|---|
| Confirmación por vela de reacción, 09-11 NY | 2.70 | ~35 | [CONFIRMACION.md](config/CONFIRMACION.md) |
| Barrido de liquidez + reversión, 09-13 NY | 2.09 | ~79 | [CONFLUENCIA_Y_LIQUIDEZ.md](config/CONFLUENCIA_Y_LIQUIDEZ.md) |

Ninguna de estas dos se ha verificado en NinjaTrader todavía — es el paso
obligatorio antes de operar cualquiera que no sea la variante F.

### Herramientas

- `tools/compilar.ps1` — compila el NinjaScript contra los ensamblados
  reales de NT8. Ningún archivo se copia a NinjaTrader sin pasar por aquí.
- `pine/automation/ICT_UnionFVG_15M_Strategy.cs` — estrategia de NT8 con la
  variante F (ver arriba), registro CSV por evento en
  `Documents/NinjaTrader 8/export/`. Compilada y desplegada, aún sin
  ejecutar una orden real en la plataforma — correr en Sim/Market Replay y
  comparar contra el CSV antes de cuenta real.
- `pine/ICT_LiquidezFavor_UnionFVG_Strategy.pine` — la misma variante F
  portada a Pine v6 (`strategy()`) para TradingView, con el mismo
  advertencia: su propio Strategy Tester tiene la misma ambigüedad de
  orden intra-vela que el modelo por vela en Python — usar para señales/
  alertas en vivo, no para confiar en su Net Profit reportado.
- `pine/automation/ICT_5M_Scalp_v2_Strategy.cs` — estrategia de NT8 con
  registro CSV por evento en `Documents/NinjaTrader 8/export/`.
- `pine/OB_FVG_Visualizador.pine` — visualizador v9 para auditoría discrecional
  en TradingView. Detecta OB por desplazamiento/BOS, FVG, pivotes y liquidez
  pendiente; puntúa cada zona con volumen, desplazamiento, liquidez, sesgo 1H
  y FVG. Reevalúa la liquidez del OB vivo más cercano y añade una línea de
  tendencia estructural opcional basada únicamente en pivotes confirmados.
  Es una herramienta visual: el score y la línea de tendencia todavía no son
  reglas validadas del backtester ni deben interpretarse como señal automática.
- `web/` — herramientas publicadas como Claude Artifacts: auditoría visual
  de operaciones y registro manual de entradas discrecionales del usuario
  (ver [web/README.md](web/README.md) para los links en vivo).
- `data/engine/python/experimentos_liquidez.py` — motor de experimentos
  configurable (frescura, apilamiento, gate de liquidez, RR dinámico) que
  produjo la variante F. Corre una batería de variantes y las vuelca a un
  CSV con columna `variante` para filtrar/pivotear sin escribir scripts
  nuevos.

## Contenido

- `pine/ICT_15M_OB_Entry_v12.pine` — estrategia final (`strategy()`), con
  gestión de salida TP1/TP2/breakeven-anticipado y las dos zonas visuales
  (OB puro + OB ampliado por el margen de entrada).
- `pine/ICT_15M_OB_Alertas.pine` — indicador gemelo (`indicator()`) que replica
  la misma detección solo para exponer `alertcondition()` nativas de
  TradingView (los scripts `strategy()` no permiten elegirlas en el diálogo de
  Alertas).
- `data/mnq_15m_bars.json` — histórico de velas de 15M usado en el último
  análisis (ver métricas abajo). Formato: `{symbol, timeframe, columns:[t,o,h,l,c], bars:[[...],...]}`,
  `t` en epoch segundos (UTC).
- `data/detected_obs_snapshot.json` — Order Blocks ya detectados sobre ese
  histórico (índice de barra, dirección, top/bot, rango del origen), para no
  tener que re-correr la detección desde cero en cada sesión.
- `docs/PARAMETERS.md` — todos los parámetros de la estrategia y su valor
  actual.
- `docs/ANALYSIS_LOG.md` — bitácora de los análisis hechos sobre el histórico
  (hallazgos, no solo resultados).
- `docs/DECISIONS.md` — decisiones de diseño ya cerradas con el usuario y el
  razonamiento detrás (para no reabrir debates ya resueltos).

## Cómo reusar el histórico en una sesión nueva

En vez de reconstruir `window.__BARS` desde cero vía `ui_scroll` en
TradingView (lento y consume mucho contexto), cargar directamente
`data/mnq_15m_bars.json` y `data/detected_obs_snapshot.json` para cualquier
análisis nuevo. Solo hace falta volver a tocar TradingView si se necesita
historial más reciente o más largo que el ya cubierto (ver rango de fechas en
`docs/ANALYSIS_LOG.md`).
