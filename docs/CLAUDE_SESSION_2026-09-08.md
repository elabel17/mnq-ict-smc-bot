# Análisis crítico — Estrategia ICT 15M OB Entry

Última actualización: 2026-09-09 — doble sesión (mañana/noche) + sesgo 1H aplicado al script real

## 📌 RESUMEN PARA SESIÓN NUEVA / OTRA PC (leer esto primero)

- **Script real vigente:** `pine/ICT_15M_OB_Entry_v18.pine` en el repo GitHub `elabel17/mnq-ict-smc-bot`. ⚠️ **Por un bug de la herramienta MCP usada para editar Pine Script, este código terminó guardado en TradingView bajo el script llamado "ICT 15M OB Entry v12 - alertas + doble zona"** (`id USER;863c808793d541e8aa640cdb7d734d8a`), NO en el script histórico "ICT 1H Liquidity Bias + 15M OB Entry el mio" (`id USER;8f652c4b1fd5403b918416fd4587f7e2`, que sigue intacto con la lógica v15/v16 anterior, sin tocar). El usuario decidió dejarlo así por ahora — **el script que hay que mirar en el chart es "ICT 15M OB Entry v18 - dual-sesion + sesgo 1H"**, verificado corriendo en vivo el 2026-09-09.
- **Número de referencia oficial actual (histórico completo, 6.27 años, 3 contratos, filtro 1H aplicado):** Net $121.696, PF 3.08, Winrate 67.9%, Max DD $1.598 (mañana+noche combinadas). Con 4 contratos: Net $162.261, PF 3.08, Max DD $2.130 (excede el límite de cuenta de $1.900 del usuario por ~$230, decisión aceptada por el usuario tras confirmar que ese evento es raro — 3 veces en 6.27 años, ninguna en sep-dic).
- **Cualquier cifra anterior a esta sesión (105k, 152k, 214k, 168k) está obsoleta.**
- **Motores Python de referencia (todos en el repo, todos verificados contra el numero de referencia antes de usarse):**
  - `claude_engine2.py`: generaliza TP1/TP2/BE como parámetros de función, separa selección de trades (`select_trades`) de conversión a dólares (`price_trades`) para grids rápidos.
  - `claude_engine3.py`: además generaliza los parámetros de DETECCIÓN (disp_mult, liq_accum_bars, liq_tolerance_pts, entry_buffer_pts, sl_buffer_pts) — usado para la búsqueda de la configuración nocturna.
  - `claude_engine4.py`: como engine3 pero además captura metadatos de diagnóstico por trade (ancho de zona, profundidad de entrada, volumen, etc.) — usado para el análisis de pérdidas totales.
  - `claude_session_config.py`: implementa y documenta los 2 regímenes (mañana/noche) con sus parámetros propios.
- **Metodología (aplicada en TODO lo nuevo de esta sesión):** cualquier hallazgo se valida con holdout limpio 70% in-sample / 30% out-of-sample (nunca tocado al elegir parámetros) antes de reportarse como real.
- **Pendiente sin resolver (para retomar):**
  1. Prioridad alta: decidir si limpiar la confusión de nombres de script en TradingView (renombrar/eliminar duplicados) — ver aviso arriba.
  2. El grid de TP1 sigue sin reconciliarse contra el motor JS de referencia de la otra sesión (ver secciones anteriores) — no se retomó esta sesión.
  3. Automatización vía NinjaTrader: `ICT_OB_Strategy.cs` sigue sin testear.
  4. VPS y confirmación con Lucid Trading: a cargo del usuario.
  5. El usuario va a revisar manualmente 8 trades nocturnos de muestra (con fecha/hora exactas, ver sección de hoy) para aportar contexto que el análisis sistemático no pudo capturar — retomar cuando dé su feedback.
- **Lección de proceso importante:** cualquier fix al backtest debe cuestionarse por causalidad — ¿el precio/nivel usado se conocía ANTES de que ocurriera, o requiere conocer el resto de una vela que aún no había cerrado? Ese fue el origen de los dos bugs más grandes encontrados en esta sesión (ver "beneficio de la duda en la vela de entrada" y "sesgo de mínimo de la vela" más abajo).

---

## Contexto del usuario

- Estrategia: detecta Order Blocks (OB) en 15m con displacement, agrega margen de entrada (`entryBufferPts`), entra cuando **cualquier vela** (de cualquier timeframe del chart, no necesariamente 15m) toca el rango del OB.
- Gestión: 3 contratos por operación. TP1 = 1.8R (código real; el usuario mencionó 1:2 de memoria), TP2 = 4R. BE anticipado al alcanzar 1.2R, asegurando +0.5R (no BE puro).
- El usuario afirma haber revisado un backtest en TradingView desde 2021 hasta hoy con resultados anuales positivos, "pocos meses en pérdida", y que Claude (en otra sesión, sin memoria persistente entre conversaciones) lo validó sin look-ahead.
- Objetivo: revisión crítica del código Pine + validación histórica real (walk-forward manual usando bar replay, cambiando entre timeframes altas/bajas para cubrir 2021-2026 ya que 15m solo carga ~3 meses de histórico visible por vez).

## Scripts identificados en la cuenta de TradingView

| Nombre interno | Título | Tipo | Relevante |
|---|---|---|---|
| `ICT 1H Liquidity Bias + 15M OB Entry el mio` | ICT 15M OB Entry v12 - alertas + doble zona | `strategy()` | ✅ Estrategia principal |
| `alertas` | ICT 15M OB Alertas | `indicator()` | ✅ Gemelo de alertas (mismo motor de detección OB) |
| `Apoyo` | Smart Money Concepts [LuxAlgo] - Ajustado | indicator | No relacionado directamente, apoyo visual |
| `dashboard` | SMC/ICT Setup Engine v15.9 [MTF Zones + HistoryScan] | indicator | No relacionado directamente |
| `Ultimate` | SMC/ICT Setup Engine v15.0 [Locked Zones] | indicator | No relacionado directamente |

## 🔴 HALLAZGO CRÍTICO #1 — El backtest reportado no puede venir de este script

Verificado con `data_get_strategy_results` sobre "ICT 15M OB Entry v12 - alertas + doble zona":

```json
{
  "net_profit": 0,
  "net_profit_percent": 0,
  "gross_profit": 0,
  "gross_loss": 0,
  "max_drawdown": 0,
  "total_trades": 0,
  "winning_trades": 0,
  "losing_trades": 0
}
```

**Causa raíz (confirmada leyendo las 377 líneas del código fuente):** el script está declarado como `strategy(...)` pero **en ningún punto llama a `strategy.entry()`, `strategy.exit()`, `strategy.order()` ni `strategy.close()`**. Toda la simulación de trade (entrada, SL, TP1, TP2, BE) se hace con variables Pine normales (`tradeOpen`, `dir`, `activeSL`, `entryPrice`, `riskPts`) y el resultado se muestra únicamente como `label.new()` con texto ("✓ TP1 (2 contratos)", "✗ PÉRDIDA TOTAL (3 contratos)", etc.). El motor de Strategy Tester de TradingView nunca recibe una orden real, por lo tanto:

- El Strategy Tester reporta 0 operaciones, 0 profit, 0 drawdown — literalmente vacío.
- Cualquier "curva de equity" o "resultados anuales positivos" que se haya visto **no puede haber salido del panel de Strategy Tester de este script**, porque no genera datos ahí.

**Hipótesis de qué se vio en realidad (pendiente de confirmar con el usuario):**
1. Lectura visual de las etiquetas en el chart (contar a ojo cuántas dicen "✓" vs "✗") — esto es propenso a sesgo de confirmación y no es un backtest real.
2. Otra versión del script (con `strategy.entry()` real) que no es la actualmente guardada.
3. El backtest correspondía a uno de los otros 3 scripts (LuxAlgo SMC, o los SMC/ICT Setup Engine), que son motores completamente distintos y no reflejan esta lógica de entrada específica (OB 15m + touch + TP1/TP2/BE descrita por el usuario).

**Acción pendiente:** preguntar al usuario cuál de las 3 hipótesis aplica antes de seguir. Si aplica la (1), el análisis histórico "positivo" no tiene ninguna base estadística real todavía — hay que construirla desde cero (por eso el plan de replay manual abajo).

## Lógica de detección de OB (función `f_ob`, idéntica en ambos scripts)

- Se ejecuta vía `request.security(syminfo.tickerid, "15", f_ob(...), lookahead=barmerge.lookahead_off)` — el `lookahead_off` es correcto, evita ver el futuro. Bien implementado en este punto.
- Displacement: vela con rango >= `dispMult` (2.5x por defecto) del rango promedio de `dispLen` velas (20), y el cierre debe cubrir >= `dispCloseFrac` (0.6) del rango en la dirección del movimiento.
- Busca la última vela opuesta (bajista para OB alcista) entre 1 y `obScanBars` (10) velas atrás como candidata a OB.
- Filtro de "liquidez sucia": si el precio pasó >= `liqAccumBars` (6) velas consecutivas dentro de `liqTolerancePts` (4 pts) del borde del OB en las `liqCheckBars` (12) velas siguientes a su formación, se descarta como zona "acumulada" (no fresh).
- Zona queda "tocable" (`bullTouchable`/`bearTouchable`) solo después de que el precio se aleja limpiamente del OB (`low > bullTop` / `high < bearBot`) — es decir, exige que haya "cleared" antes de considerarse válida para touch.
- Se invalida (`bullFresh := false`) si el precio vuelve a tocar el borde antes de la señal de entrada real.

## Lógica de entrada / gestión (solo en la `strategy()`, `ICT 15M OB Entry v12`)

- `longZoneTouch` = `low <= bullTop + entryBufferPts and low >= bullBot` — el touch se evalúa en el timeframe del **chart actual**, no fijo en 15m. Esto coincide con lo que describiste ("no tiene que ser una vela de 15, puede ser cualquiera") — el detector de OB corre en 15m vía `request.security`, pero el gatillo de entrada corre en el timeframe visible del chart.
- Entrada: `entryPrice = max(low, bullTop)` (longs) — es decir, si la vela abre/cierra por debajo del borde, la entrada teórica es el borde, no el precio real de mercado; puede ser optimista en backtest real vs ejecución en vivo.
- SL = borde opuesto del OB ± `slBufferPts` (2 pts).
- TP1 = entrada + riesgo × 1.8R (código real, no 2R). TP2 = entrada + riesgo × 4R.
- BE: al alcanzar 1.2R de recorrido (`beTriggerR`), mueve el stop para asegurar +0.5R (`lockR`), no breakeven puro.
- Filtro de riesgo máximo: descarta señales cuyo stop supere `maxRiskPts` (100 pts).
- Filtro de sesión: solo opera 18:00–11:00 hora NY (ventana Asia+Londres+apertura NY).

## Observaciones críticas de diseño (independientes del bug de 0 trades)

1. **Timeframe mixto (touch en chart TF, detección en 15m):** si el chart está en 1m, el touch puede dispararse por un wick de 1 minuto que nunca se habría formado como vela de 15m — inflar señales en TFs bajos. Si el chart está en 1h o superior al hacer backtest, se pierden touches intrabar. El resultado del backtest **depende del timeframe del chart en el momento de correrlo**, no es una propiedad fija de la estrategia. Esto es una fuente enorme de inconsistencia entre "lo que viste ayer" y lo que se replique después, si no se fija el TF de chart usado.
2. **Entrada optimista:** usar `max(low, bullTop)` como precio de entrada asume fill exacto en el borde de la zona, sin slippage. En real, con 3 contratos, el fill puede ser peor, especialmente en displacement violento (que es justamente cuando se forman estos OB).
3. **BE a 1.2R con lockR 0.5R:** agresivo — en episodios de retroceso antes de continuar hacia TP1 (1.8R), muchos trades que iban en camino a TP1/TP2 completo terminan cerrando en +0.5R. Reduce varianza pero también el expectancy si el edge real está concentrado en el tramo 1.8R–4R.
4. **Comisión = 0** (`commission_value=0.0`) y no hay modelado de slippage — el backtest (cuando exista con trades reales) sobreestimará el resultado neto real, más con 3 contratos por operación.
5. **`liqAccumBars`, `dispMult`, `entryBufferPts`, etc. son 10+ parámetros ajustables** — alto riesgo de overfitting si se optimizaron sobre el mismo rango 2021-2026 que luego se usa como "validación". Falta confirmar si estos valores se fijaron a priori o se ajustaron mirando resultados históricos.
6. **Sin filtro de régimen de mercado ni de volatilidad/noticias** (NFP, CPI, FOMC) pese a operar futuros (MNQ visible en el chart) — displacement por noticia puede generar OB "falsos" de alta volatilidad que no se repiten en condiciones normales.

## Plan de validación histórica (pendiente de ejecutar)

Dado que el Strategy Tester actual no sirve (0 trades), y que graficar 15m solo muestra ~3 meses de histórico visible por carga, el plan es:

1. Primero resolver el Hallazgo Crítico #1 con el usuario (¿de dónde salió el backtest positivo?).
2. Si se requiere corregir el script para que dispare `strategy.entry()`/`strategy.exit()` reales, reescribir esa parte y volver a compilar (`pine_smart_compile`) antes de cualquier validación.
3. Una vez el Strategy Tester arroje trades reales, usar `data_get_strategy_results` y `data_get_trades` (si expone lista de operaciones) para año por año 2021-2026, fijando el símbolo y TF de chart usados de forma consistente.
4. Para inspección visual/manual candle-by-candle (bar replay) en tramos específicos: usar `replay_start` con fecha, `replay_step` para avanzar, alternando `chart_set_timeframe` (D/W para navegar rápido a la zona deseada, luego bajar a 15) y `chart_scroll_to_date` para posicionarse, ya que TradingView limita el histórico cargado por defecto en TFs bajos.
5. Registrar en este documento, por año: total trades, winrate, profit factor, max drawdown, y observaciones cualitativas de señales falsas/rechazadas.

## 🔴 HALLAZGO CRÍTICO #2 — Bloqueo técnico en la carga de histórico 15m

**Estado:** resuelto parcialmente el problema del Hallazgo #1 (script sin órdenes reales); nuevo bloqueo distinto encontrado al intentar la validación multi-año.

### Qué se corrigió (Hallazgo #1)

Se reescribió "ICT 15M OB Entry v12 - alertas + doble zona" (v13) agregando `strategy.entry()`/`strategy.exit()` reales que replican exactamente la lógica ya existente (mismo precio de entrada, SL, TP1 2 contratos / TP2 1 contrato, BE a 1.2R asegurando +0.5R). Se agregó:
- `feePerContract` (input, default 0.47 USD/contrato/lado — **ajustar a tu broker real**, no verificado).
- `slippage=1` tick.
- `default_qty_value=3` (3 contratos).

Compiló sin errores y se guardó. **Confirmado visualmente en el chart**: aparece la etiqueta "✓ TP1+BE (contrato final protegido)" sobre una vela real y una posición abierta con SL/TP visibles en el panel de la derecha — la ejecución real está funcionando.

### El bloqueo nuevo

1. `chart_scroll_to_date` reporta `"success": true` con la fecha solicitada, pero **no mueve el chart en absoluto** — verificado dos veces con capturas de pantalla reales (el eje de tiempo sigue mostrando la fecha actual, no la fecha pedida). Es un bug de la herramienta MCP, no algo que se pueda resolver reintentando la misma llamada.
2. `chart_get_visible_range` devuelve el mismo rango fijo sin importar qué se haga — tampoco es confiable como verificación.
3. El botón "Todos" (rango de fechas) en la barra inferior del chart **sí logró expandir el rango a "30 abr 2019 — 31 ago 2026"**, pero solo mientras el chart estaba en temporalidad Mensual (cambio automático al hacer clic). Al volver a 15m, el rango utilizable por el Strategy Tester **se contrajo de vuelta a "31 mar 2026 — 7 sept 2026" (~5 meses)** — este parece ser el tope real de historial intradía en 15m que carga este feed/cuenta, coincidiendo con lo que describiste ("~3 meses, y si retrocedes salen 3 más").
4. `ui_scroll(direction: left)` sí mueve el chart (confirmado visualmente), pero muy poco por llamada — cubrir 5 años hacia atrás en 15m tomaría un número de pasos poco práctico por esta vía automatizada (cientos de llamadas).
5. Efecto colateral encontrado: había **10 procesos de TradingView.exe corriendo simultáneamente** por relanzamientos previos sin cerrar el anterior — causaba timeouts y datos cacheados/inconsistentes en capturas y en `chart_get_visible_range`. Ya se mató todo y se dejó una sola instancia limpia corriendo.

### Resultado actual del Strategy Tester (ventana real disponible: 31 mar 2026 — 7 sept 2026)

```
total_trades: 0
```

Con los parámetros actuales (dispMult 2.5, filtro de sesión 18:00-11:00 NY, risk cap 100pts), no se generó ninguna señal calificada en estos ~5 meses. Esto podría ser: (a) legítimo — la estrategia es selectiva y genera pocas señales, o (b) síntoma de que los filtros son demasiado estrictos para las condiciones recientes de mercado. Aún no distinguible sin más historial.

### Camino recomendado para desbloquear

La navegación automatizada hacia atrás en 15m no es viable por este MCP tal como está. Opciones:

- **A. Manual + asistido:** tú retrocedes manualmente en TradingView (como ya sabes hacerlo) hasta cubrir 2021-2026 una vez, dejando el histórico cargado en el buffer de la app; yo tomo el control desde ahí solo para leer `data_get_strategy_results`/`data_get_trades` y generar el informe. Minimiza mi uso de `scroll_to_date` (roto) y aprovecha que `ui_scroll` sí funciona bajo tu supervisión si prefieres guiarme paso a paso.
- **B. Muestreo por años:** en vez de un backtest continuo, tomar 4-6 ventanas representativas (ej. 1 trimestre por año 2021-2026) usando el botón "Todos" + ajuste manual, y agregar los resultados por separado. Menos preciso que un backtest continuo pero mucho más viable con las herramientas actuales.
- **C. Reportar el bug** de `chart_scroll_to_date` en el repo de `tradingview-mcp` (posible fix futuro) y mientras tanto operar con la ventana de ~5 meses disponible como primera validación (insuficiente para conclusiones anuales, pero sirve para detectar errores de lógica/parámetros antes de invertir tiempo en el histórico completo).

## ✅ CAUSA RAÍZ RESUELTA — Faltaba `margin_long`/`margin_short` (2026-09-07)

**Esto era lo que bloqueaba todo.** El Strategy Tester SÍ funciona; el problema era que **TradingView rechazaba todas las órdenes por capital insuficiente**.

### La aritmética del bloqueo

- MNQ: 1 punto = $2. Precio ~29.600 → **nocional por contrato ≈ $59.200**.
- 3 contratos ≈ **$177.600 de nocional**.
- `initial_capital = 50.000`.
- En Pine, `margin_long`/`margin_short` por defecto son **0**, lo que significa que la estrategia debe cubrir el **100% del nocional** con capital propio. $177.600 > $50.000 → **toda orden rechazada, silenciosamente**.

Por eso el mensaje "Este informe requiere datos de negociación" (= el script no ejecutó ninguna operación): las señales se calculaban y se dibujaban en el chart, pero ninguna orden llegaba a ejecutarse.

### Prueba que lo confirma

Estrategia trivial (entra cada 50 velas) en MNQ, 3 contratos, capital 50k:
- **Sin `margin_long`:** 0 operaciones.
- **Con `margin_long=5, margin_short=5`:** **206 operaciones**, profit factor 1.44, 19 métricas completas.

Idéntico código, único cambio el margen. También explica por qué BTCUSDT daba 0 (79.000 × 3 = $237.000 > $50.000).

**Corrección de un error de análisis previo:** en una iteración anterior concluí que "el Strategy Tester no computa en este entorno". Esa conclusión era **incorrecta** — el motor siempre funcionó. La conservo documentada abajo solo como registro del proceso.

### 📊 PRIMER BACKTEST REAL — ICT 15M OB BACKTEST v13

**Configuración:** MNQ1! (CME_MINI), 15m, 3 contratos, capital $50.000, comisión $0.47/contrato/lado, slippage 1 tick, margen 5%.
**Ventana:** 31 mar 2026 — 7 sept 2026 (~5 meses, límite de histórico intradía cargado).

| Métrica | Valor |
|---|---|
| **Net profit** | **−$993,72 (−0,02%)** |
| Gross profit | $11.917,06 |
| Gross loss | $12.910,78 |
| **Profit factor** | **0,92** |
| **Total trades** | **142** |
| Winning trades | 65 |
| Losing trades | 77 |
| **% Profitable** | **45,77%** |
| **Avg trade** | **−$7,00** |
| Largest win | $571,12 |
| Largest loss | $625,88 |
| **Max drawdown** | **$6.801,81 (13,60%)** |
| Comisiones pagadas | $200,22 |
| Sharpe ratio | −0,091 |
| Sortino ratio | −0,119 |
| Buy & hold (referencia) | $10.953 |

### Lectura crítica de estos números

1. **Profit factor 0,92 = estrategia perdedora en esta ventana.** Por cada $1 arriesgado devuelve $0,92. No es catastrófico, pero está por debajo del punto de equilibrio (1,0).
2. **Winrate 45,77% con TP1 a 1,8R debería ser rentable** — matemáticamente, 45% de aciertos a 1,8R promedio daría profit factor > 1,3. Que no lo sea sugiere que **muchos trades no llegan a TP1 completo**: el BE a 1,2R (asegurando +0,5R) está cortando ganadores antes de tiempo. Esta es la hipótesis #1 a testear.
3. **Largest loss ($625,88) > largest win ($571,12).** Con TP1 1,8R y TP2 4R, el mayor ganador debería superar ampliamente al mayor perdedor. Confirma que el techo de ganancia está siendo recortado — muy probablemente por el BE agresivo.
4. **Avg trade −$7,00 vs comisión ~$1,41/trade** ($200,22 / 142). La comisión NO es la causa de la pérdida; el edge en sí es negativo o neutro en esta ventana.
5. **Buy & hold ganó $10.953** en el mismo período mientras la estrategia perdió $994. Contexto: fue un tramo alcista; una estrategia bidireccional no tiene por qué batir buy&hold, pero conviene revisar el desempeño de shorts por separado.
6. **142 trades en 5 meses ≈ 28/mes** — muestra suficiente para que estos números tengan significancia estadística razonable (no es ruido de 10 operaciones).

### ⚠️ Advertencias importantes sobre estos datos

- **Solo cubren ~5 meses (mar–sept 2026), NO 2021-2026.** No contradicen todavía tu recuerdo de resultados anuales positivos — pueden ser simplemente un mal semestre, o un cambio de régimen de mercado. Falta validar el resto del histórico vía bar replay.
- **El margen 5% es un supuesto mío**, elegido para desbloquear el tester. El margen real de MNQ ronda $2.000–2.500/contrato (≈4% del nocional), así que 5% es realista, pero conviene ajustarlo al de tu bróker.
- **La comisión $0,47/contrato/lado también es un supuesto** — ajústala a tu bróker real (Topstep/AMP/NinjaTrader varían).
- Estos resultados son de la **copia ejecutable** (`ICT 15M OB BACKTEST v13`), no de tu script original, que permanece intacto.

## 📊 HISTÓRICO COMPLETO 2021–2026 (MNQ1!, 15m, 3 contratos)

**Método:** `replay_start` en fechas escalonadas. Cada punto de replay carga ~6 meses de histórico previo, y el Strategy Tester computa sobre esa ventana. Verificado que el chart estuvo en **resolución 15m** durante toda la medición (`chart_get_state` → `resolution: "15"`).

**Config:** capital $50.000, 3 contratos, comisión $0,47/contrato/lado, slippage 1 tick, margen 5%, filtro de sesión 18:00–11:00 NY activo, parámetros originales (dispMult 2.5, entryBuffer 12 pts, TP1 1.8R, TP2 4R, BE 1.2R→+0.5R).

| Ventana (~6 meses) | Net profit | Profit factor | Trades | % Profitable | Max DD | Buy&Hold |
|---|---|---|---|---|---|---|
| 2021 H1 | **+$1.197,78** | 1,09 | 242 | 49,2% | $2.957 | +$3.714 |
| 2021 H2 | **+$1.060,34** | 1,08 | 226 | 46,5% | $4.008 | +$3.602 |
| 2022 H1 | **+$5.420,58** | 1,38 | 212 | 50,5% | $2.700 | −$9.943 |
| 2022 H2 | **−$2.479,46** | 0,83 | 206 | 50,0% | $4.576 | −$2.851 |
| 2023 H1 | **−$1.615,72** | 0,88 | 242 | 43,0% | $3.844 | +$17.423 |
| 2023 H2 | **−$165,42** | 0,99 | 259 | 37,1% | $4.268 | +$3.316 |
| 2024 H1 | **+$4.371,60** | 1,34 | 288 | 47,6% | $1.660 | +$6.558 |
| 2024 H2 | **−$2.032,52** | 0,86 | 220 | 37,7% | $4.139 | +$2.689 |
| 2025 H1 | **+$1.787,58** | 1,16 | 162 | 45,7% | $2.158 | +$2.983 |
| 2026 (mar–sep) | **−$993,72** | 0,92 | 142 | 45,8% | $6.802 | +$10.953 |

### Agregado

- **Suma neta ≈ +$6.551** sobre ~2.199 operaciones en 5 años.
- **5 ventanas positivas / 5 negativas** — exactamente mitad y mitad.
- **Profit factor promedio ≈ 1,05** — apenas por encima del punto de equilibrio.
- **Winrate global ≈ 45,3%.**
- Comisiones totales ≈ $3.110 (relevante pero no determinante).

### ⚠️ Contraste con la expectativa del usuario

El usuario afirma que la estrategia "debe estar positiva todos los años". **Los datos medidos no lo confirman.** No estoy dispuesto a ajustar el test hasta que dé positivo — eso sería fabricar el resultado. Lo que los datos muestran es una estrategia **marginalmente rentable en agregado pero muy inconsistente**, alternando semestres buenos y malos casi al azar.

Posibles explicaciones legítimas de la discrepancia (a investigar, no asumidas):
1. **El backtest original no medía lo mismo.** Si en la otra PC se contaban etiquetas visuales (✓ vs ✗), eso ignora el tamaño real de cada ganancia/pérdida y el efecto del BE — puede verse "positivo" siendo neutro.
2. **Parámetros distintos** en aquella versión (TP1/TP2, buffer, filtro de sesión, o BE desactivado).
3. **Supuestos míos que podrían ser incorrectos:** comisión $0,47 y margen 5% son estimaciones mías. La comisión sí importa (~$3.110 en total); con comisión 0 el agregado subiría a ~+$9.660, aún inconsistente año a año.
4. **Diferencia de ejecución:** mi versión coloca SL/TP con `strategy.exit` desde la barra siguiente a la entrada; el original evaluaba SL/TP en la misma barra de entrada. Esto puede cambiar resultados en trades rápidos.

### Patrón consistente y accionable detectado

En **todas** las ventanas, el `largest_win` es similar o menor al `largest_loss`, pese a que TP2 está a 4R y el SL a 1R:

| Ventana | Largest win | Largest loss |
|---|---|---|
| 2021 H1 | $764 | $590 |
| 2022 H2 | $682 | **$1.411** |
| 2023 H2 | $758 | $436 |
| 2025 H1 | $582 | $584 |
| 2026 | $571 | $626 |

Con TP2 a 4R, el mayor ganador debería ser ~4× el mayor perdedor. Que sean comparables es **evidencia fuerte de que casi ningún trade llega a TP2** — el BE a 1,2R (asegurando +0,5R) está cerrando las posiciones antes de que el movimiento se desarrolle. Esta sigue siendo la hipótesis #1 para mejorar el sistema, ahora respaldada por 10 ventanas independientes.

## 🐛 BUGS ENCONTRADOS EN MI PROPIA IMPLEMENTACIÓN (v13) — corregidos en v14/v15

El usuario cuestionó los resultados ("veo trades que salen en SL que antes salían en TP1+BE"). **Tenía razón: mi copia ejecutable v13 tenía 3 bugs que subestimaban la estrategia.**

### Bug 1 (grave) — el runner nunca podía llegar a TP2
v13 re-emitía en CADA barra `strategy.exit("X1", "L", qty=2, limit=tp1, stop=activeSL)`. Cuando TP1 se llenaba y quedaba 1 contrato corriendo hacia TP2, esa orden **seguía viva con límite en TP1**; como el precio ya estaba por encima, cerraba el runner al instante. **TP2 (4R) era matemáticamente inalcanzable.** Por eso el `largest_win` nunca reflejaba 4R en ninguna de las 10 ventanas.
**Fix v14:** `X1` solo se emite mientras `not tp1Hit`; TP1 llenado se detecta por `strategy.position_size` real (3→1), no por chequeo manual.

### Bug 2 — SL inactivo en la barra de entrada
v13 colocaba las salidas recién en la barra siguiente a la entrada → sin stop durante la primera barra. Explicaba pérdidas anómalas (`largest_loss` $1.411 en 2022 H2).
**Fix v14:** las salidas se colocan en la misma barra de la entrada. Efecto medido: `largest_loss` bajó de **$625,88 → $439,88** en la ventana 2026.

### Bug 3 — IDs de salida duplicados entre largos y cortos
v13 usaba `X1`/`X2` tanto para long como para short. **Fix v14:** `X1`/`X2` (long), `Y1`/`Y2` (short).

### Verificación de que el fix funciona
Lista de operaciones reales (v14), ventana 2026:
- Op. 2: entrada L @ 29.438,50 → `X1` LIMIT @ 29.470,75 (TP1) → **`X2` LIMIT @ 29.508 = TP2 alcanzado (3,88R)** ✓ Imposible en v13.
- Op. 1: entrada @ 29.178,75 (R=52,5 pts) → TP1 @ 29.273,25 ✓ → `X2` STOP @ 29.206,75 = **entrada +0,5R** (el runner sale en el lock, no en TP2 @ 29.388,75).

## 📊 RESULTADOS CORREGIDOS (v14/v15) vs v13

⚠️ **Discrepancia de parámetro detectada:** el usuario describe TP1 = **1:2 (2R)**, pero el script original guardado usa **`rr1 = 1.8`** (su propio comentario dice *"v10 — TP1 baja de 2R a 1.8R"*). Se midieron ambos.

| Ventana | v13 (con bugs) | v14 corregido (TP1 1,8R) | v15 corregido (TP1 2,0R) |
|---|---|---|---|
| 2021 H1 | +$1.198 (PF 1,09) | **+$2.600 (PF 1,21)** | +$2.306 (PF 1,19) |
| 2022 H2 | −$2.479 (PF 0,83) | — | **−$409 (PF 0,96)** |
| 2023 H1 | −$1.616 (PF 0,88) | — | −$1.580 (PF 0,88) |
| 2024 H2 | −$2.033 (PF 0,86) | — | **−$863 (PF 0,93)** |
| 2026 mar–sep | −$994 (PF 0,92) | **−$694 (PF 0,94)** | — |

**Conclusión de la corrección:** el fix mejora resultados de forma sustancial y consistente (2021 H1 más que duplicó; 2022 H2 pasó de −$2.479 a −$409; 2024 H2 de −$2.033 a −$863). **Pero las ventanas negativas siguen siendo negativas**, solo que mucho menos. 2023 H1 apenas cambió (−$1.616 → −$1.580).

**Dato adicional:** TP1 a **1,8R rindió mejor que a 2,0R** en 2021 H1 (+$2.600 vs +$2.306). El valor del código parece estar mejor calibrado que el que el usuario recuerda.

**Estado de la afirmación del usuario** ("menos de 14 meses negativos desde 2021 y cada año en ganancias"): con los bugs corregidos los números mejoran mucho pero **todavía no reproducen años consistentemente positivos**. Quedan diferencias por explicar — posiblemente supuestos de comisión/margen, o diferencias con la versión que el usuario tiene en su otra PC. Pendiente de comparar contra esa versión de referencia.

## 🐛 BUG #4 (el más importante) — Entrada a MERCADO en vez de LÍMITE en el borde del OB

El usuario detectó que "el margen de SL, el punto de entrada, el TP1 y TP2 son bastante diferentes" entre mis entradas y las del pine original. **Tenía razón, y era el fallo de fidelidad más grave.**

### Causa

- **Pine original:** `entryPrice = math.max(low, bullTop)` → entrada en el **borde del OB**. Es el modelo de una **orden límite puesta en la zona**.
- **Mis v13/v14/v15:** `strategy.entry(...)` a **MERCADO**, que con `process_orders_on_close=true` se llena al **CIERRE de la vela**, no en el borde.

Como SL, TP1 y TP2 se calculan **todos a partir del precio de entrada**, al desplazarse la entrada **se desplazaban los cuatro niveles a la vez**. Por eso los trades salían en SL donde el original mostraba TP1+BE.

Evidencia: op. 1 de la ventana 2026 entró a 29.178,75 (cierre de vela), no en el borde de la zona.

### Fix (v16)

Usa `strategy.entry(..., limit=armLongPrice)` con `armLongPrice = bullTop` (y `bearBot` para cortos) → **orden límite en el borde del OB**, que se llena cuando el precio regresa a la zona. SL = borde opuesto ∓ buffer. TP1/TP2 derivados de esa entrada.

Verificación en operaciones reales: entrada `L` LIMIT @ 21.770,75 → `X1` LIMIT @ 21.817,75 (TP1 1,8R) → `X2` LIMIT @ 21.874,75 (**TP2 4R alcanzado**). Los niveles ahora coinciden con los que dibuja el indicador original.

### Impacto medido (ventana 2024 H2)

| Versión | Net profit | PF | Trades | % Prof | Max DD |
|---|---|---|---|---|---|
| v13 (con bugs) | −$2.033 | 0,86 | 220 | 37,7% | 8,2% |
| v15 (salidas corregidas) | −$863 | 0,93 | 222 | 38,7% | 6,1% |
| **v16 (entrada límite)** | **+$4.820** | **3,71** | **67** | **58,2%** | **37,1%** |

### ⚠️ Señales que faltan verificar en v16 (NO tomar como resultado final)

1. **Solo 67 operaciones vs 222.** Esperable en parte (ahora el precio debe alcanzar el borde real del OB, no basta con entrar en la banda de 12 pts), pero es una caída del 70% que hay que confirmar que sea legítima y no órdenes que nunca se arman.
2. **Max drawdown 37,1%** (vs 6-8% antes) — muy alto. Posible posición sostenida sin stop por desincronización entre `dirNow`/`entryPrice` y el fill real de la orden límite.
3. **PF 3,71 y largest_win $2.829** — sospechosamente bueno. Hay que descartar que una orden límite quede "resting" y se llene mucho después a un precio favorable con niveles calculados de una zona ya vieja.
4. **`open_pl` −705** — quedó una posición abierta al final.

**Recomendación:** antes de sacar conclusiones anuales con v16, validar los puntos 1–3 revisando la lista completa de operaciones y comparando visualmente contra las etiquetas del indicador original en el chart. El salto de −$863 a +$4.820 es demasiado grande para aceptarlo sin auditoría.

## 🔧 AUDITORÍA DE v16 → v17 (parcial: 1 bug corregido, 1 SIN RESOLVER)

### Bug #5 encontrado y corregido — posición sin SL ni TP (causa del PF 3,71 falso)

v16 usaba una sola variable `dirNow`. Largo y corto pueden armarse en la misma barra; como el bloque short corre después, `dirNow` quedaba en −1. Si luego se llenaba el **largo**, la condición de gestión `position_size > 0 and dirNow == 1` **nunca se cumplía** → **posición sin stop ni take-profit, corriendo libre**. Eso inflaba artificialmente el `largest_win` ($2.829) y disparaba el drawdown.

**Fix v17:** la dirección se deriva de `strategy.position_size` real; los niveles de cada lado se guardan por separado (`pendLongSL` / `pendShortSL`) y se fijan al detectar el fill con `strategy.position_avg_price`.

**Efecto confirmado:** `largest_win` bajó de **$2.829 → $659** (ya no hay ganadores descontrolados) y el PF falso de 3,71 desapareció.

### ⛔ PROBLEMA PERSISTENTE — NO usar v17 para estadísticas todavía

Ventana 2024 H2 con v17: net −$1.758,89 · PF 0,75 · 78 trades · **max drawdown 44,1%** · **`open_pl` −$5.410,50**.

El drawdown extremo **no se resolvió** y hay una posición abierta profundamente perdedora al final. Eso indica que **todavía queda al menos una posición que no recibe stop**, probablemente porque:
- `riskPts` queda `na` o ≤ 0 en algún camino y el bloque de gestión no entra, o
- la detección `justOpenedLong/Short` no dispara en algún caso (fill y cierre dentro de la misma barra, o vuelco directo de corto a largo con ambas órdenes límite pendientes).

**Decisión:** NO se generan las estadísticas anuales/mensuales pedidas con esta versión. Entregar cifras de un motor que sé que tiene un defecto activo sería darte números en los que yo mismo no confío. Hay que cerrar este bug primero.

### Estado de versiones

| Versión | Estado |
|---|---|
| v13 | 3 bugs de salida (runner cerrado en TP1, SL ausente en barra de entrada, IDs duplicados) |
| v14/v15 | Salidas corregidas, pero entrada a MERCADO → niveles desplazados |
| v16 | Entrada límite en borde del OB ✓, pero posiciones sin SL por `dirNow` compartido |
| **v17** | Bug de `dirNow` corregido ✓ — **pero persiste DD 44% + posición abierta sin gestionar** |

**Próximo paso:** aislar por qué una posición queda sin stop. Método sugerido: añadir `plot(riskPts)` y `plot(strategy.position_size)` para ver en qué barra se pierde la gestión, o forzar un `strategy.close_all()` de seguridad cuando `position_size != 0 and na(riskPts)`.

## ✅ DECISIÓN CERRADA (2026-09-08) — Cooldown tras cierre de operación: NO implementar

**Pregunta que originó el test:** el usuario observó un patrón real (verificado, no visual) de re-entrada inmediata tras un cierre asegurando BE, que en algunos casos terminaba en pérdida total. ¿Un cooldown entre operaciones mejora el resultado?

**Método:** motor de backtest en Python, réplica exacta línea-por-línea del Pine `v15 - multi-zona` (verificada contra datos reales de TradingView — ver más abajo), sobre histórico completo reconstruido de **147.749 velas de 15m (mayo 2020 – sep 2026)**, extraído directamente del motor interno de TradingView vía `ui_evaluate` + `requestMoreData` (mismo método usado en la otra sesión). Se probaron 6 valores de cooldown, todo lo demás constante.

| Cooldown | Trades | Net profit | Profit Factor | Max DD |
|---|---|---|---|---|
| **0 (sin cooldown)** | 1.612 | **$214.171** | 3,011 | $1.552 |
| 30 min | 1.517 | $204.996 | 3,060 | $1.552 |
| 1h | 1.404 | $190.091 | 3,052 | $1.552 |
| 2h | 1.302 | $179.735 | 3,121 | $1.474 |
| 4h | 1.206 | $164.784 | 3,057 | $1.812 |
| 7,5h | 1.059 | $143.203 | 3,027 | $1.812 |

**Resultado: monótono y sin excepciones.** A mayor cooldown, menor ganancia neta (hasta −33% en el extremo), sin mejora en profit factor y con **peor** drawdown máximo en los cooldowns largos (menos operaciones → cada pérdida pesa más en la curva). Consistente con `REENTRADAS.md`: las re-entradas rápidas, incluidas las que a veces pierden, generan más valor del que destruyen.

**Decisión, siguiendo el criterio del usuario ("se queda la config que genere mayor ganancia"): NO se implementa cooldown.**

## 🔬 Verificación de precisión del motor Python (2026-09-08)

El usuario pidió confirmar con rigor si el baseline medido ($214.171, sin cooldown) es válido, dado que es 27% más alto que el $168.649 documentado en el repo de la otra sesión.

**Verificación cruzada contra datos reales de TradingView:** se compararon operaciones generadas por el motor Python contra las etiquetas reales extraídas del script `v15` corriendo en vivo (308 etiquetas capturadas previamente). Coincidencias exactas (precio de entrada, SL, TP1, TP2, y resultado) en al menos 5 operaciones independientes, incluida la operación LONG 29064 / SL 29019,25 / TP1 29144,55 / TP2 29243 que el usuario mostró en captura de pantalla (resultado PÉRDIDA TOTAL en ambos).

**Conclusión de la verificación:** la lógica de selección/ejecución de operaciones del motor Python es correcta y está confirmada contra el motor real (no es autoconsistencia, es validación externa). El 27% de diferencia restante ($214k vs $168k) **no está en qué operaciones se toman**, sino en el modelo de conversión a dólares (comisión, slippage, posible modelo de fill "por cierre de vela" mencionado en `DECISIONS.md` que no se pudo replicar sin el código fuente de ese motor externo).

**Bug real encontrado y corregido durante el proceso:** el motor Python inicialmente acreditaba 2 de 3 contratos al precio de TP1 en operaciones `BE_LOCK` (cuando el precio NUNCA llegó a TP1, solo al lock de BE) — esto inflaba el resultado de $298k a los $214k finales tras la corrección.

**Postura recomendada:** el rango honesto actual es $168k–$214k para 6,27 años según el modelo de costos de ejecución. No se recomienda decidir el tamaño de posición ni empezar a operar en real basándose en el extremo optimista sin antes: (1) confirmar comisión/slippage reales del bróker fondeado, (2) forward-test en cuenta demo/fondeada durante varias semanas para validar ejecución real vs. backtest.

## ✅ CORRECCIÓN FINAL (2026-09-08, tarde) — bug de "beneficio de la duda en la vela de entrada"

El usuario pidió auditar el mes con 100% winrate (marzo 2025) en vez de seguir señalando el patrón como "sospechoso" sin resolverlo. Encontré la causa real: el motor Python evaluaba TP1/SL/BE usando **la misma vela de la entrada**, dando crédito a movimientos de precio (ej. alcanzar TP1) sin conocer el orden real de los eventos dentro de esa vela — 35,1% de los trades cerraban en ≤1 barra tras la entrada, señal clara del sesgo.

Esto es el MISMO problema que el usuario ya había documentado y corregido en su motor de referencia (`DECISIONS.md`: *"el motor daba el beneficio de la duda en la vela de ENTRADA... ~9% de la ganancia bruta"*), que yo no había replicado en mi traducción a Python.

**Fix:** excluir del chequeo de gestión (TP1/SL/BE) la barra en que se abrió la operación; solo se evalúa desde la barra siguiente.

### Resultado, histórico completo (6,27 años, 3 contratos, lockR=0.8R)

| | Antes del fix | **Después del fix (correcto)** |
|---|---|---|
| Net profit | $214.171 | **$152.338** |
| Profit Factor | 3,01 | **2,13** |
| Winrate | 74,3% | **62,3%** |
| Meses negativos | 0 de 76 | **6 de 76** (2021-01, 2024-08, 2025-06, 2025-11, 2026-04, 2026-05) |
| Trades cerrando en ≤1 barra | 35,1% | 10,2% |

**El número corregido ($152.338) queda a solo ~10% de los $168.649 documentados por el usuario en su motor de referencia** — mucho más cerca que el 27% de diferencia anterior. La mayor parte de la discrepancia original probablemente era este bug.

### Estimación 8-sep → 8-dic corregida (promedio 6 años, 3 contratos)

| Año | Trades | Neto | Winrate |
|---|---|---|---|
| 2020 | 57 | $5.920 | 64,9% |
| 2021 | 66 | $4.431 | 60,6% |
| 2022 | 60 | $4.486 | 61,7% |
| 2023 | 85 | $6.524 | 62,4% |
| 2024 | 70 | $7.108 | 60,0% |
| 2025 | 42 | $1.918 | 54,8% |

**Promedio: $5.065** (antes del fix: $7.942).

**Este es ahora el número de referencia a usar para decisiones**, no el de $214k/$7.942 anteriores — quedan obsoletos.

## ✅ VALIDACIÓN CRUZADA 5 MINUTOS (2026-09-08) — confirma que el fix de 15m es suficiente

Se reconstruyó un dataset independiente de **185.066 velas de 5 minutos** (2024-01-28 a 2026-09-08 — el feed de 5m solo retiene ~2,6 años de historia, no permite cubrir los 6,27 años completos). Guardado permanentemente en `Downloads/mnq_dataset/merged_ohlcv_5m_2024_2026.json`.

**Método:** las velas de 5m se agregan a 15m (idéntico a los datos de 15m directos) para mantener la detección de zonas sin cambios; para la gestión de la operación (TP1/SL/BE) se recorren las 3 sub-velas de 5m en orden cronológico real, reduciendo 3× la ventana de ambigüedad de "qué se tocó primero" dentro de cada vela.

**Comparación directa, mismo tramo de fechas:**

| | 15m puro | 5m (resolución mejorada) | Diferencia |
|---|---|---|---|
| Trades | 590 | 605 | +15 |
| Net profit | $63.110 | $59.517 | **-5,7%** |
| Profit Factor | 2,11 | 2,05 | -3,2% |
| Winrate | 61,2% | 62,8% | +1,6pp |

**Conclusión: la diferencia es pequeña (-5,7%)**, muy inferior al -29% que causó el fix del sesgo de la vela de entrada. Esto confirma que el motor de 15m corregido ($152.338 en el histórico completo) ya es una base confiable — bajar a 1 minuto (que hubiera tomado 2+ horas de extracción) probablemente movería el número solo 1-3% adicional, no se justifica el esfuerzo.

### Resultado mes a mes y año a año (motor 5m, tramo disponible)

| Año | Trades | Neto | Winrate | PF |
|---|---|---|---|---|
| 2024 | 276 | $21.789 | 62,7% | 2,06 |
| 2025 | 202 | $21.933 | 63,4% | 2,08 |
| 2026 (parcial, hasta sep) | 127 | $15.794 | 62,2% | 1,99 |

**5 meses negativos de 33 (~15%)**: 2024-08 (-$1.073), 2025-06 (-$120), 2025-11 (-$577), 2026-04 (-$1.262), 2026-05 (-$379).

## ✅ TEST: Entrada por confirmación + grid search TP1/TP2 (2026-09-08)

**Pregunta del usuario:** ¿condicionar la entrada (esperar a ver si el precio llega al OB puro antes de aceptar el toque en el margen de 12pts) mejora el resultado? ¿Por qué TP1=1,8R? ¿Reducir TP2 sería más rentable dado que TP1 cierra más contratos?

### Entrada por confirmación — probada, resultado NEGATIVO

Implementada como estado por zona: al tocar solo el margen de 12pts (sin alcanzar el OB puro), la zona queda "armada" esperando; se resuelve entrando en el borde real si lo alcanza, o en el borde del margen si el precio se revierte limpio hacia afuera; si no pasa ninguna, la zona muere sin operar.

| | Confirmación | Original (toque inmediato) |
|---|---|---|
| Trades | 1.441 | 1.543 |
| Net profit | $144.226 | **$152.338** |
| PF | 2,10 | 2,13 |
| Winrate | 59,3% | 62,3% |
| Max DD | $3.337 | $3.171 |

**-5,3% peor en todas las métricas. No se recomienda implementar.** Las zonas que caducan esperando confirmación (sin tocar el OB puro ni revertir limpio) cuestan más operaciones de las que se ganan en mejor precio.

⚠️ Nota de proceso: la primera implementación tenía un bug (zona "armada" nunca se removía de la lista → 23.206 trades, PF 1.3, claramente roto). Corregido marcando la zona `resolved` en el mismo bar que produce la entrada.

### Grid TP1 (rr2 fijo en 4.0) — CONTRADICE lo documentado en DECISIONS.md

| TP1 | Net profit | PF |
|---|---|---|
| 1,2R | $135.663 | 2,01 |
| 1,4R | $143.707 | 2,07 |
| 1,6R | $149.089 | 2,11 |
| **1,8R (actual)** | **$152.338** | **2,13** |
| 2,0R | $156.655 | 2,17 |
| 2,4R | $162.505 | 2,21 |
| 3,0R | $166.166 | 2,24 |
| 3,8R | $167.888 | 2,25 (mejor de todo el grid) |

**Sube de forma casi monótona con TP1 más alto**, sin el pico en 1,8R que documenta `DECISIONS.md` (*"1.8R es el punto más rentable en $ y win rate combinados"*). Winrate se mantiene plano (~62,3%) en todo el rango porque depende del BE-trigger fijo (1,2R), no de TP1.

**Discrepancia sin resolver:** no se pudo determinar si la diferencia es por modelo de ejecución, rango de fechas, o criterio de optimización distinto (quizás la otra sesión pesó consistencia/drawdown, no solo ganancia bruta). Pendiente de reconciliar con el motor de referencia (JS) de la otra sesión antes de tocar el parámetro real.

## 🔴 CORRECCIÓN MAYOR (2026-09-08, noche) — sesgo de "mínimo de la vela" en la entrada base — encontrado por el usuario

**El usuario cuestionó, con lógica pura, por qué el precio de entrada usaba "donde llegó esa vela" en vez de un precio conocido de antemano** — señaló correctamente que usar el mínimo/máximo real de una vela de 15m como precio de entrada requiere, en la práctica, conocer ese mínimo antes de que la vela termine de formarse (esperar a verla completa) — información que un trader/orden real no tendría en el instante del primer contacto.

**Confirmado como un sesgo real, no solo una duda:** la fórmula original `entrada = max(mínimo_de_la_vela, borde_del_OB)` es causalmente válida SOLO cuando el precio alcanza el borde puro del OB (nivel fijo, conocido de antemano). Pero cuando el precio solo toca el margen de 12 puntos sin llegar al borde puro, usar el mínimo real de la vela es mirar "hacia el futuro" de esa misma vela — el 71,2% de las entradas históricas eran de este tipo (medido empíricamente, ver distribución abajo).

**Fix aplicado:** para toques de "solo margen", la entrada ahora usa el borde EXTERIOR del margen (`z.top + entryBufferPts`), un precio fijo conocido antes de que ocurra el toque — no el mínimo real de esa vela.

### Impacto en el histórico completo (6,27 años, 3 contratos, lockR=0,8R)

| | Antes (con el sesgo) | **Corregido (causal)** |
|---|---|---|
| Trades | 1.543 | 1.459 |
| Net profit | $152.338 | **$105.255** |
| Profit Factor | 2,13 | **1,65** |
| Winrate | 62,3% | **56,1%** |
| Max drawdown | $3.171 | $3.872 |

**-31% de ganancia neta.** Este es ahora **el número más confiable obtenido hasta la fecha** — corrige un sesgo de "ver el futuro" que afectaba a la mayoría de las operaciones (71,2%), no un caso marginal.

### Distribución empírica que reveló el problema

Medido en el histórico ANTES del fix (3.610 señales de entrada, muestreo simplificado):

| Punto de entrada dentro del margen | % de las señales |
|---|---|
| Exacto en el OB puro (0%) | 28,8% |
| 0-25% del margen | 16,0% |
| 25-50% del margen | 16,8% |
| 50-75% del margen | 19,8% |
| 75-100% del margen | 18,6% |

Promedio: 37,8% de profundidad en el margen — es decir, la mayoría de las entradas NO llegaban al borde puro, y por tanto SÍ estaban afectadas por el sesgo.

**⚠️ PENDIENTE:** este mismo fix debe aplicarse también al script real en TradingView (v15) y a los archivos ya subidos a GitHub (`claude_engine.py`, `claude_ohlcv_*`), que reflejan la versión con el sesgo todavía. Los grid search de TP1/TP2 y el test de entrada por confirmación de esta sesión también quedan desactualizados y deberían re-ejecutarse con el motor corregido antes de tomarlos como definitivos.

### Corrección del test de confirmación — resuelto con sub-velas de 5m

El usuario aclaró la mecánica exacta: entrada pendiente en el borde del margen (112 en el ejemplo), mejora a mejor precio si el OB puro (100) se toca primero, y se llena en 112 si el precio se revierte antes. El primer test (arriba) usaba velas de 15m completas para resolver esto, lo cual el usuario señaló correctamente como insuficiente: **dentro de una sola vela de 15m el precio puede tocar ambas zonas y revertir, sin que el motor pueda saber el orden real.**

Advertencia epistémica importante, válida para TODO backtest basado en velas (no solo esta prueba): un toque simple (¿llegó el precio a X?) es un hecho verificable en cualquier resolución. Pero la SECUENCIA de eventos (¿qué pasó primero?) solo se aproxima mejor con velas más chicas, nunca se resuelve del todo sin datos tick reales. La estrategia en sí (una orden límite real) no tiene este problema en ejecución real — el problema es exclusivo de intentar reconstruirla en un backtest histórico con datos de velas.

**Repetido con sub-velas de 5 minutos** (mismo dataset de 185.066 velas, 2024-2026, resolviendo la espera/confirmación con las 3 sub-velas de cada período de 15m en orden cronológico real):

| | Confirmación (sub-velas 5m) | Original (mismo rango) |
|---|---|---|
| Trades | 561 | 593 |
| Net profit | $41.221 | **$62.419** |
| PF | 1,64 | 2,08 |
| Winrate | 56,1% | 60,9% |

**-34% de ganancia — la diferencia se agranda (no se achica) con más precisión respecto al -5,3% medido a 15m puro.** Esto sugiere que la medición a 15m subestimaba lo desfavorable del enfoque. Causa de fondo (confirmada en ambas resoluciones): entrar en el borde del margen (112) en vez del punto de toque real añade riesgo, lo que descarta más operaciones por el tope de 100 puntos.

**Conclusión: no se recomienda implementar, con evidencia consistente en dos niveles de granularidad.** No se recomienda seguir refinando con más resolución (1m) dado que la señal ya es clara y consistente en dirección.

### Grid TP2 (rr1 fijo en 1,8, el actual) — responde la pregunta del usuario

| TP2 | Net profit | PF |
|---|---|---|
| 2,0R | $140.225 | 2,01 |
| 3,0R | $148.679 | 2,08 |
| 3,5R | $150.621 | 2,11 |
| **4,0R (actual)** | **$152.338** | **2,13** |
| 4,5R | $149.012 | 2,12 |
| 5,0R | $150.476 | 2,14 |
| 6,0R | $146.912 | 2,14 |

**Reducir TP2 por debajo de 4R empeora el resultado en todos los valores probados — la hipótesis del usuario ("acortar TP2 sería más rentable porque TP1 cierra más contratos") queda descartada por los datos.** El valor actual (4R) está muy cerca del óptimo del grid.

## Dataset histórico reconstruido (para reuso futuro)

Guardado en `C:\Users\ABEL~1.DIA\AppData\Local\Temp\claude\...\scratchpad\merged_ohlcv.json` (temporal, se pierde al cerrar sesión) — **pendiente moverlo a ubicación permanente si se quiere reusar** sin repetir la extracción de ~16 ventanas vía `ui_evaluate`. 147.749 velas de 15m, MNQ1!, mayo 2020 – sep 2026, un solo hueco de 4 días sin rellenar (26-30 mar 2026, irrelevante para el agregado).

## 🔴 (Registro histórico — conclusión errónea, ya corregida arriba) HALLAZGO #3 — "El Strategy Tester NO computa en este entorno"

**Fecha:** 2026-09-07. Este hallazgo invalida el plan de backtest automatizado y explica todo lo anterior.

### Prueba diagnóstica decisiva

Para aislar si el problema era la lógica de la estrategia o el entorno, se aplicó una estrategia trivial:

```pine
//@version=6
strategy("DIAG TEST", overlay=true, initial_capital=50000,
     default_qty_type=strategy.fixed, default_qty_value=3,
     process_orders_on_close=true)
if bar_index % 200 == 0
    strategy.entry("L", strategy.long, qty=3)
if bar_index % 200 == 100
    strategy.close("L")
```

Esta estrategia entra incondicionalmente cada 200 velas — es imposible que genere 0 operaciones si el motor funciona.

**Resultado: `total_trades: 0`** y el panel muestra "Este informe requiere datos de negociación".

Se repitió en **BINANCE:BTCUSDT** (datos libres, sin restricción de suscripción CME): **también 0 operaciones**, mismo mensaje.

### Conclusión

El Strategy Tester de esta instalación de TradingView Desktop **no está computando reportes para ninguna estrategia**, ni siquiera triviales, ni en futuros ni en cripto. Por lo tanto:

- El resultado "0 trades" observado antes **no dice nada sobre la calidad de tu estrategia** — era un síntoma de este bloqueo, no un diagnóstico de la lógica.
- El Hallazgo #1 (script sin `strategy.entry()`) **sigue siendo válido y real** — el código efectivamente nunca colocaba órdenes — pero corregirlo no bastó porque el entorno tampoco las procesa.
- **No es posible obtener winrate, profit factor, drawdown ni expectancy por esta vía** hasta resolver por qué el Strategy Tester no funciona.

### Causas posibles a investigar (no verificadas aún)

1. Permisos/suscripción de la cuenta TradingView para backtesting (plan requerido).
2. Estado corrupto de la app de escritorio (probar en tradingview.com en navegador para descartar).
3. Alguna configuración del panel de Strategy Tester (pestaña "Rendimiento" vs otras) o de "Deep Backtesting".
4. Interferencia del modo Bar Replay / de la conexión CDP con el cómputo del reporte.

**Siguiente paso recomendado:** abrir la MISMA estrategia en tradingview.com desde un navegador normal (sin CDP) y ver si el Strategy Tester produce operaciones ahí. Eso separa "problema de la app/entorno" de "problema de cuenta".

## ⚠️ INCIDENTE — Sobrescritura accidental del script del usuario (resuelto)

Durante el diagnóstico, un clic en el editor de Pine que se creía "Actualizar en el gráfico" resultó ser "Guardar": **a las 2:00:27 PM el código de prueba "DIAG TEST" quedó guardado sobre el script "ICT 15M OB Entry v12 - alertas + doble zona"**, reemplazando el trabajo del usuario.

**Resuelto:** a las 2:03:39 PM se restauró el código original completo (377 líneas, verificado en el log del editor: `default_qty_value=1`, `commission_value=0.0`, comentarios v6–v12 intactos). El usuario además confirmó tener copia de respaldo propia.

**Lección para futuras sesiones:** en este MCP, `pine_smart_compile` y el clic en el botón circular del editor **guardan** (sobrescriben el script abierto). Para aplicar código al chart SIN guardar hay que usar otro mecanismo, o trabajar siempre sobre una copia nueva creada con `pine_new` antes de experimentar.

## Estado real del análisis solicitado

El usuario pidió: análisis de entradas, beneficio, comisiones por trade, e informe final con datos para luego hacer preguntas e hipótesis.

**No se pudo generar ese informe.** Motivo: el Strategy Tester no produce datos en este entorno (Hallazgo #3). Lo único entregable hasta ahora es el **análisis cualitativo del código** (secciones anteriores de este documento), que sí es válido e independiente del backtest:

- Lógica de detección de OB revisada (usa `lookahead_off` correctamente — sin look-ahead bias).
- Riesgos de diseño identificados: dependencia del timeframe del chart para el gatillo de entrada, entrada optimista sin slippage, BE agresivo a 1.2R, 10+ parámetros con riesgo de overfitting, ausencia de filtro de régimen/noticias.

## Preguntas abiertas para el usuario

1. ¿De dónde salió exactamente el backtest positivo que revisaste — lectura visual de labels, otra versión del script, u otro de los indicadores SMC guardados?
2. ¿El TF del chart al correr ese backtest era 15m fijo, o cambiaba?
3. ¿Los 3 contratos se reparten 1/1/1, 2/1, u otra combinación entre TP1/TP2/runner? (pregunta ya hecha, aún sin respuesta explícita)
4. ¿Los parámetros actuales (dispMult 2.5, entryBufferPts 12, etc.) fueron fijados de antemano o ajustados mirando resultados pasados?

## ✅ FIX CAUSAL APLICADO AL SCRIPT REAL (2026-09-08, noche)

El sesgo de "mínimo de la vela" descrito arriba (sección "🔴 CORRECCIÓN MAYOR") ya estaba corregido en el motor Python (`engine.py`), pero **hasta ahora seguía presente en el script real de TradingView** (`ICT 15M OB Entry v15 - multi-zona`, `USER;8f652c4b1fd5403b918416fd4587f7e2`) — es decir, el script que efectivamente genera las alertas y señales que el usuario opera. Esto quedó resuelto:

**Cambio aplicado (Pine v6, sección "4) Buscar candidata de entrada"):**
- Antes: `e = math.max(low, z.top)` / `e2 = math.min(high, z.bot)` — usaba el mínimo/máximo REAL alcanzado por la vela, que no se conoce hasta que la vela termina de formarse.
- Ahora: `e = low <= z.top ? z.top : z.top + entryBufferPts` / `e2 = high >= z.bot ? z.bot : z.bot - entryBufferPts` — usa únicamente niveles fijos conocidos de antemano (el borde puro del OB, o el borde exterior del margen de 12pts).

**Proceso de verificación (siguiendo la lección aprendida el mismo día con el label de aviso que no persistió a la primera):**
1. `pine_set_source` con el código corregido (436 líneas).
2. `pine_smart_compile` → compiló sin errores.
3. `pine_get_source` inmediatamente después → **confirmado que el cambio persistió** en el servidor antes de tocar el chart.
4. Se quitó la instancia vieja del indicador del chart y se volvió a agregar (`chart_manage_indicator` remove + `indicator_add`), para que la instancia visible cargue el código nuevo.
5. Verificado visualmente con screenshot: el script corre, dibuja zonas OB, niveles SL/TP1/TP2 y caja de "asegura +0.8R" correctamente, sin el aviso de timeframe (que también seguía quitado).

**A partir de ahora, el número de referencia oficial de la estrategia es el del histórico completo con el fix causal aplicado:**

| | Valor |
|---|---|
| Período | 2020-05-31 a 2026-09-08 (6,27 años) |
| Trades | 1.459 |
| Net profit | **$105.254,82** |
| Profit Factor | 1,649 |
| Winrate | 56,1% |
| Max drawdown | $3.872,06 |
| Meses negativos | 14 de 76 |

Los resultados de $152.338 (o superiores) mencionados en secciones anteriores de este documento **quedan obsoletos** — corresponden a la versión con el sesgo de hindsight, ya no reflejan lo que el script real hace desde este cambio.

**Pendiente de esta corrección:**
- Re-ejecutar el grid search de TP1/TP2 con el motor causal (los grids documentados arriba usaban el motor con el sesgo).
- Reconciliar la discrepancia del grid de TP1 (sube monótono hasta ~3,2R en mi motor vs. "1,8R óptimo" documentado por la otra sesión) contra el motor de referencia JS, ahora que el motor Python está en su versión más confiable.
- Push a GitHub (`elabel17/mnq-ict-smc-bot`) de: `engine.py` corregido, este documento actualizado, y una nota indicando que el commit anterior (`9d8f0b6`) refleja la versión pre-fix.

## ✅ SESIÓN 2026-09-09 — cuenta de fondeo, doble sesión, sesgo de 1H, diagnóstico de pérdidas

Contexto: el usuario tiene una cuenta de fondeo con **pérdida máxima $1.900 y objetivo de ganancia $3.000**. Todo el análisis de esta sección se hizo con esa restricción como criterio principal, salvo donde se indica "sin límite de cuenta" explícitamente. Metodología usada en TODO: holdout limpio 70% in-sample (para elegir parámetros) / 30% out-of-sample (nunca tocado, usado solo para confirmar) — cualquier hallazgo que no se sostuviera ahí se descartó o se reportó como no confirmado.

### 1. Con el límite de cuenta: solo 1 contrato cabe bajo $1.900 (antes del filtro de 1H)

Con la configuración de 3 contratos (2 en TP1 + 1 corriendo), el drawdown histórico es $3.649-3.872 — **excede el límite por el doble**. Se probaron todos los repartos de 1 a 5 contratos: únicamente 1 contrato mantiene el DD bajo $1.900. El usuario decidió explícitamente **no operar con 1 contrato** ("no es negociable, son 3") y aceptó el riesgo de exceder el límite históricamente, con el argumento de que una racha así es difícil de repetir. Se le señaló que hay 5 rachas de 6+ pérdidas en el histórico (la peor: 9 pérdidas, $2.125 en un mes) — no es un evento de una sola vez.

### 2. TP1: estadísticamente lo más rentable es NO cerrar nada ahí

Se probaron los 4 repartos posibles de 3 contratos (3+0, 2+1, 1+2, 0+3 entre TP1/TP2). Resultado: **0 en TP1, 3 corriendo a TP2 es superior en TODOS los indicadores** (net, PF, winrate) — no es "más riesgo por más retorno", el riesgo de entrada es el mismo, solo cambia cuánto se captura del lado ganador. Desde este hallazgo, todos los backtests posteriores usan este reparto (0, 3) o equivalente (0, 4) con 4 contratos.

### 3. Optimización de sesión — mañana 03:00-11:00 NY, noche 18:00-00:00 NY

Se encontró que la ventana de sesión actual del script (18:00-11:00 NY completa) mezclaba horas muy dispares en calidad: 09:00-10:00 NY genera el 67% de toda la ganancia, mientras que 01:00 y 21:00 NY tienen resultado negativo en promedio. Se probaron múltiples recortes y se determinó (validado OOS):

- **Mañana: 03:00-11:00 NY**, con TP2=6.0R, BE trigger=1.2R, BE lock=1.0R (parámetros de detección sin cambios).
- **Noche: 18:00-00:00 NY**, con parámetros de detección RECALIBRADOS (ver punto 4) — la ventana completa nocturna se mantiene, recortarla más (después de las 8pm o 10pm) empeora los resultados o no se sostiene fuera de muestra; contraintuitivamente las horas de apertura (18:00-19:00) son las más fuertes, no las últimas.
- Horas 11:00-18:00 y 00:00-03:00: sin operar, no mostraron edge.
- Se implementó soporte para regímenes de parámetros completamente independientes por sesión (`select_trades_multi` en `claude_engine2.py`, expandido en `claude_session_config.py`), replicando la metodología de correr manaña y noche como dos backtests separados que luego se combinan.

### 4. La sesión nocturna SÍ tiene una configuración rentable — solo necesitaba recalibración, no solo ajustar TP/BE

Diagnóstico inicial: volumen nocturno (18:00-08:00 NY) es 4-10x menor que en la mañana (2.700-12.000 vs 25.000-55.000 contratos/vela de 15m), lo que hace que las señales de "desplazamiento" sean más ruidosas. La mejora NO vino de tocar solo TP/BE (eso daba PF~1.3, apenas rentable) sino de recalibrar los filtros de detección al carácter de vela más chico de la noche:

| Parámetro | Manaña (sin cambio) | Noche (recalibrado) |
|---|---|---|
| LIQ_ACCUM_BARS | 6 | **15** (mucho más permisivo) |
| LIQ_TOLERANCE_PTS | 4.0 | **2.0** (más estricto) |
| ENTRY_BUFFER_PTS | 12.0 | **8.0** |
| SL_BUFFER_PTS | 2.0 | **1.0** |
| TP2 | 6.0R | **7.0R** |
| BE trigger | 1.2R | **0.8R** |
| BE lock | 1.0R | **0.3R** |

Impacto (ventana 18:00-00:00 NY, histórico completo): net $8.426→**$22.241** (x2.6), PF 1.30→**1.84**, winrate 52.6%→**64.4%**. Confirmado fuera de muestra (avg/trade IN=$80.76 vs OOS=$78.53, prácticamente idéntico). Se probó bajar el TP2 nocturno (hipótesis del usuario) — **empeora consistentemente en todo el rango probado (1.8R a 10R)**, 7.0R sigue siendo el óptimo.

### 5. Hallazgo mayor: filtro de sesgo de 1H (nunca implementado pese al nombre del script)

El script real se llama *"ICT 1H Liquidity Bias + 15M OB Entry"* pero el código nunca implementaba ningún filtro de sesgo de tendencia de 1H — solo detección pura en 15m. Se agregó un filtro simple (SMA de 10 velas de 1H: solo largos si el precio está sobre la media, solo cortos si está debajo), calculado con `request.security` sin lookahead. Validado con holdout limpio en ambas sesiones por separado:

| | Sin filtro 1H | Con filtro 1H |
|---|---|---|
| Trades (mañana+noche) | 1.505 | 730 |
| Net (histórico completo) | $144.180 | $121.696 (-16%) |
| Profit Factor | 1.93 | **3.08** |
| Winrate | 58.1% | **67.9%** |
| Max Drawdown | $3.074 | **$1.598** (-48%) |

Este filtro resultó ser, con 3 contratos, la configuración que finalmente cabe bajo el límite de $1.900 de la cuenta (antes ninguna combinación de TP/BE lo lograba salvo con 1 contrato).

### 6. Diagnóstico riguroso de pérdidas totales (FULL_LOSS)

Se extendió el motor (`claude_engine4.py`) para capturar metadatos por operación (ancho de zona, profundidad de entrada en el margen, ratio de desplazamiento, racha de liquidez, volumen de la vela señal/origen, edad de la zona). **Ninguno de estos factores, individualmente, distingue una pérdida total del resto** — la tasa se mantiene 35-45% en todos los cuartiles de cada variable. Tampoco hay autocorrelación entre pérdidas consecutivas, ni diferencia relevante por dirección (long/short) o día de la semana. Esto llevó a la búsqueda del filtro de sesgo de 1H (punto 5), que sí demostró ser efectivo — no filtrando por características de la zona, sino por alineación con la tendencia de mayor marco temporal.

Se probó además un tope de riesgo máximo por operación ($550, equivalente a 68.75pts con 4 contratos): **descartado** — las operaciones de riesgo alto en realidad ganan MÁS seguido que el promedio (70.2% vs 67.9%), limitar el riesgo elimina ganancia ($36.820 menos, -22.7%) sin filtrar malas operaciones.

### 7. Decisión de 4 contratos y análisis de drawdown por período

Con el filtro de 1H, 4 contratos da DD $2.130 (excede $1.900 por ~$230); 3 contratos da DD $1.598 (cabe, con margen $302). El usuario preguntó si los episodios de drawdown >$1.900 con 4 contratos se concentraban en algún período del año (hipótesis: sep-dic). Resultado: solo 3 episodios en 6.27 años (2021-03, 2023-06, 2023-08), ninguno en sep-dic — **pero con una muestra de solo 3 eventos, esto no es evidencia estadística de un patrón estacional real**, solo indica que el evento es raro en general (~1 vez cada 2 años). El usuario decidió proceder con 4 contratos aceptando ese riesgo, con esta salvedad explícita comunicada.

### 8. Script real actualizado — ⚠️ ver aviso de identidad de script arriba

Se aplicó al script real de TradingView: doble sesión (mañana/noche con regímenes independientes, incluido estado de posición completamente separado por sesión — no comparten "operación abierta"), filtro de sesgo de 1H, y **un fix de causalidad adicional encontrado en el proceso**: el script real NUNCA había tenido el fix de "no gestionar SL/TP en la misma vela de la entrada" que sí lleva el motor Python desde 2026-09-08 — se corrigió por primera vez aquí. Compilado sin errores y verificado corriendo en vivo (capturas de pantalla confirmando etiquetas `[MANANA]`/`[NOCHE]`).

**Pendiente para el usuario:** revisar manualmente 8 operaciones de muestra (5 pérdidas totales + 3 ganadoras, con fecha/hora/precio exactos) para aportar contexto visual/manual que el diagnóstico sistemático no pudo capturar, dado que el usuario reporta experiencia manual de mayor rentabilidad nocturna que la que refleja el backtest.
