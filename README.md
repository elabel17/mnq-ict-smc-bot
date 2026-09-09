# MNQ ICT/SMC Order Block Bot

Estrategia Pine Script v6 (ICT/SMC Order Blocks) para MNQ (Micro Nasdaq-100
futures, `CME_MINI_DL:MNQ1!`), backtesteada con un servidor MCP a medida
(TradingView Desktop controlado vía CDP). Regla no negociable en todo el
proyecto: **ningún backtest usa información futura del precio**.

## Estado (actualizado 2026-09-09)

- **Script real en producción:** `pine/ICT_15M_OB_Entry_v18.pine` — doble
  sesión (mañana 03:00-11:00 NY / noche 18:00-00:00 NY, cada una con su
  propio régimen de detección y TP/BE), filtro de sesgo de 1H, y fix de
  causalidad en la gestión (nunca gestionar en la misma vela de entrada).
  Verificado corriendo en vivo en TradingView el 2026-09-09.
  **⚠️ Por un bug de la herramienta de edición usada, este código quedó
  guardado en TradingView bajo el script "ICT 15M OB Entry v12 - alertas +
  doble zona" (`id USER;863c808793d541e8aa640cdb7d734d8a`), NO en
  "ICT 1H Liquidity Bias + 15M OB Entry el mio" (que sigue intacto con la
  lógica v15/v16 anterior). Ver detalle en
  `docs/CLAUDE_SESSION_2026-09-08.md`, sección "SESIÓN 2026-09-09" → punto 8.**
  `pine/ICT_15M_OB_Entry_v15.pine`, `v14.pine` y `ICT_15M_OB_Alertas.pine`
  son versiones anteriores, conservadas de referencia.
- **Motores Python de referencia:** `claude_engine.py` (validado, causal),
  `claude_engine2.py`/`claude_engine3.py`/`claude_engine4.py` (generalizan
  TP/BE, parámetros de detección, y diagnóstico por trade respectivamente),
  `claude_session_config.py` (implementa los 2 regímenes mañana/noche).
  Número de referencia actual (3 contratos, filtro 1H, histórico completo
  6.27 años): **Net $121.696, PF 3.08, Winrate 67.9%, Max DD $1.598**.
  Con 4 contratos: Net $162.261, PF 3.08, Max DD $2.130. Cualquier cifra
  anterior a 2026-09-09 (105k, 152k, 214k, 168k) queda obsoleta.
- Cualquier análisis o ajuste nuevo se hace en un script/indicador aparte y se
  documenta en `docs/`.
- **Para poner al día una sesión de Claude nueva/otra PC:** leer primero
  `docs/CLAUDE_SESSION_2026-09-08.md` completo (bitácora cronológica de todos
  los hallazgos y fixes, incluida la sección "SESIÓN 2026-09-09" al final)
  antes de tocar el script o el motor.

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
