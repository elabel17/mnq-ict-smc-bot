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

### 15m — auditado, dos líneas rentables (aún no verificadas en NinjaTrader)

`pine/ICT_15M_OB_Entry_v18.pine` reportaba Net $121.696 / PF 3.08 — **ese
número era inválido**, con tres look-aheads propios ([veredicto
completo](config/VEREDICTO_15M.md)). Corregidos, la detección de OB por
desplazamiento con orden límite descansando en la zona no tiene ventaja
(PF 0.99). Dos líneas causales sí la tienen, exploradas después:

| línea | PF | ops/año | ver |
|---|---|---|---|
| Confirmación por vela de reacción, 09-11 NY | 2.70 | ~35 | [CONFIRMACION.md](config/CONFIRMACION.md) |
| Union (desplazamiento+BOS) + FVG, 08-13 NY | 1.50 | ~140 | [CONFLUENCIA_Y_LIQUIDEZ.md](config/CONFLUENCIA_Y_LIQUIDEZ.md) |
| **Barrido de liquidez + reversión, 09-13 NY** | **2.09** | ~79 | [CONFLUENCIA_Y_LIQUIDEZ.md](config/CONFLUENCIA_Y_LIQUIDEZ.md) |

La última es el mejor resultado combinado (PF, drawdown, 0 años negativos en
7) de todo el proyecto. **Ninguna de las tres se ha verificado en
NinjaTrader todavía** — es el paso obligatorio antes de operar cualquiera.

### Herramientas

- `tools/compilar.ps1` — compila el NinjaScript contra los ensamblados
  reales de NT8. Ningún archivo se copia a NinjaTrader sin pasar por aquí.
- `pine/automation/ICT_5M_Scalp_v2_Strategy.cs` — estrategia de NT8 con
  registro CSV por evento en `Documents/NinjaTrader 8/export/`.
- `pine/OB_FVG_Visualizador.pine` — visualizador v9 para auditoría discrecional
  en TradingView. Detecta OB por desplazamiento/BOS, FVG, pivotes y liquidez
  pendiente; puntúa cada zona con volumen, desplazamiento, liquidez, sesgo 1H
  y FVG. Reevalúa la liquidez del OB vivo más cercano y añade una línea de
  tendencia estructural opcional basada únicamente en pivotes confirmados.
  Es una herramienta visual: el score y la línea de tendencia todavía no son
  reglas validadas del backtester ni deben interpretarse como señal automática.

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
