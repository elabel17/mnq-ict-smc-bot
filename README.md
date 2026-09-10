# MNQ ICT/SMC Order Block Bot

Estrategia Pine Script v6 (ICT/SMC Order Blocks) para MNQ (Micro Nasdaq-100
futures, `CME_MINI_DL:MNQ1!`), backtesteada con un servidor MCP a medida
(TradingView Desktop controlado vía CDP). Regla no negociable en todo el
proyecto: **ningún backtest usa información futura del precio**.

## Estado (actualizado 2026-09-10)

- **DOS líneas de estrategia activas en paralelo:**
  1. **15m (mañana/noche + sesgo 1H):** `pine/ICT_15M_OB_Entry_v18.pine`.
     Número de referencia (3 contratos, histórico completo 6.27 años):
     Net $121.696, PF 3.08, Winrate 67.9%, Max DD $1.598.
  2. **5m scalping nativo (NUEVO, 2026-09-10):** `pine/ICT_5M_Scalp_v1.pine`
     — parámetros de detección recalibrados específicamente para 5 minutos
     (no es la lógica de 15m reaplicada), filtro de sesgo 1H, sesión
     03:00-11:00 NY únicamente. Número de referencia (4 contratos,
     histórico completo 2.6 años, supuestos conservadores de ejecución):
     **Net $386.343, PF ~3.2, Winrate ~78%, Max DD ~$1.500**. Auditado a
     fondo por causalidad y verificado contra el feed real de TradingView
     y contra el script Pine corriendo en vivo (coincidencia exacta).
     NinjaScript: `pine/automation/ICT_5M_Scalp_Strategy.cs` (primer
     borrador, SIN COMPILAR — pendiente de que el usuario lo pruebe en su
     NinjaTrader).
  Ver el detalle completo, metodología y advertencias de ambas en
  `docs/CLAUDE_SESSION_2026-09-08.md` (secciones "SESIÓN 2026-09-09" y
  "SESIÓN 2026-09-10").
  **⚠️ Aviso de identidad de scripts en TradingView:** por un bug
  reproducible de la herramienta de edición usada, el código real terminó
  guardado bajo nombres de scripts preexistentes del usuario en su cuenta
  de TradingView, no bajo los nombres "originales": v18 (15m) vive en
  "Ultimate", y el scalping de 5m vive en "Apoyo" — ambos casos con
  autorización expresa del usuario tras confirmarle el problema. Ningún
  script propio del proyecto se perdió. Detalle completo en
  `docs/CLAUDE_SESSION_2026-09-08.md`.
  `pine/ICT_15M_OB_Entry_v15.pine`, `v14.pine` y `ICT_15M_OB_Alertas.pine`
  son versiones anteriores de 15m, conservadas de referencia.
- **Motores Python de referencia:** `claude_engine.py` (15m, validado
  causal), `claude_engine2/3/4.py` (generalizan TP/BE, parámetros de
  detección, y diagnóstico por trade), `claude_engine5.py` (motor nativo
  de 5m), `claude_session_config.py` (regímenes mañana/noche de 15m).
  Cualquier cifra anterior a 2026-09-09 (105k, 152k, 214k, 168k para 15m)
  queda obsoleta.
- **Datos de validación en vivo:** `data/python/claude_september_2026_mtd_5m.json`
  y `claude_september_2026_mtd_trades.csv` — velas reales y las 47
  operaciones esperadas de septiembre 2026 (1-10), para que el usuario
  valide el NinjaScript vía replay antes de Sim/cuenta real.
- Cualquier análisis o ajuste nuevo se hace en un script/indicador aparte y se
  documenta en `docs/`.
- **Para poner al día una sesión de Claude nueva/otra PC:** leer primero
  `docs/CLAUDE_SESSION_2026-09-08.md` completo (bitácora cronológica de
  todos los hallazgos y fixes, hasta la sección "SESIÓN 2026-09-10" al
  final) antes de tocar cualquier script o motor.

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
