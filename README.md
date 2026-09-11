# MNQ ICT/SMC Order Block Bot

Estrategia Pine Script v6 (ICT/SMC Order Blocks) para MNQ (Micro Nasdaq-100
futures, `CME_MINI_DL:MNQ1!`), backtesteada con un servidor MCP a medida
(TradingView Desktop controlado vía CDP). Regla no negociable en todo el
proyecto: **ningún backtest usa información futura del precio**.

## Estado (actualizado 2026-09-10, noche)

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

### 15m — SIN AUDITAR

`pine/ICT_15M_OB_Entry_v18.pine` reportaba Net $121.696 / PF 3.08. **Ese
número no ha pasado por la auditoría de causalidad** que se aplicó al de 5m
y no debe usarse hasta revisarlo. Es trabajo pendiente.

### Herramientas

- `tools/compilar.ps1` — compila el NinjaScript contra los ensamblados
  reales de NT8. Ningún archivo se copia a NinjaTrader sin pasar por aquí.
- `pine/automation/ICT_5M_Scalp_v2_Strategy.cs` — estrategia de NT8 con
  registro CSV por evento en `Documents/NinjaTrader 8/export/`.

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
