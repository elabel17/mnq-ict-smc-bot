# MNQ ICT/SMC Order Block Bot

Estrategia Pine Script v6 (ICT/SMC Order Blocks) para MNQ (Micro Nasdaq-100
futures, `CME_MINI_DL:MNQ1!`), backtesteada con un servidor MCP a medida
(TradingView Desktop controlado vía CDP). Regla no negociable en todo el
proyecto: **ningún backtest usa información futura del precio**.

## Estado (actualizado 2026-09-10, tarde)

> **AVISO — las cifras anteriores de este README eran inválidas.**
> Al portar la estrategia a NinjaTrader se encontraron **cinco look-aheads**
> en el motor de Python. Los $386.343 y los $290.250 que figuraban aquí
> describían operaciones imposibles de ejecutar. Detalle completo en
> [config/ANALISIS_CAUSAL.md](config/ANALISIS_CAUSAL.md).

### 5m — configuración validada causalmente

Motor de referencia: `data/engine/python/v_nivel.py` (modo `aire`).
Reprodujo **exactamente las 83 operaciones** del replay de NinjaTrader
del 27-ago al 8-sep de 2026.

| configuración | ops | PF | neto 2,61a (3c) | DD (3c) | mitades |
|---|---|---|---|---|---|
| **A · pasar la cuenta** (frescura ≤3) | 1.054 | **1.92** | $59.150 | **$1.870** | 1.87 / 1.98 |
| B · máximo neto (sin frescura) | 2.897 | 1.47 | $91.882 | $3.771 | 1.48 / 1.45 |

Parámetros completos y tablas por número de contratos en
[config/CONFIGURACIONES.md](config/CONFIGURACIONES.md).

**En uso: configuración A con 4 contratos** — DD $2.493, 96,6% de
probabilidad de +$3.000 antes de −$2.000, mediana 5 semanas. Últimos 12
meses: PF 2.27, $43.295, cero meses negativos.

El hallazgo decisivo fue la **frescura de zona**: si el precio vuelve al
Order Block dentro de las 3 primeras velas de 5m la reacción es fiable
(PF 1.92); a partir de la vela 8 cae a 1.5. El `zone_max_age = 60` heredado
permitía operar zonas de hasta cinco horas.

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
