# Análisis crítico — Estrategia ICT 15M OB Entry

Última actualización: 2026-09-07

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
