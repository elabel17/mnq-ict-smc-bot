# Confluencia (OB+FVG+Pivote+BOS) y el hallazgo de sweep+reversión

Fecha: **2026-09-13/14**. Continuación tras cerrar la línea de confirmación
15m ([CONFIRMACION.md](CONFIRMACION.md), PF 1.99-2.70 pero solo ~35-138
ops/año). El usuario pidió explorar libremente cualquier concepto adicional
(FVG, pivotes, zonas de liquidez, estructura, Fibonacci) priorizando
únicamente el mejor resultado real, sin apego a ningún método concreto.

Motor: `data/engine/python/motor_confluencia.py`. Todo causal, cada
ingrediente probado por separado antes de combinar.

## Lo que se probó y NO mejoró (negativo, pero real)

| ingrediente | resultado |
|---|---|
| BOS puro (ruptura de estructura, sin filtro de desplazamiento) | PF 1.26, peor que solo-desplazamiento (1.77) con más operaciones |
| Unión disp+BOS con estructura de pivote **larga** (5-8 velas) | Sin mejora sobre disp solo |
| Ampliar la ventana horaria (08-12 → 06-14) | El PF cae monótonamente cuanto más ancha la ventana — patrón consistente en cada prueba |
| Escalado dinámico de contratos según equity | Inconsistencia encontrada entre dos simulaciones del mismo caso (93.9% vs 98.9%) — **no se reportó como válido**, requiere revisión antes de confiar en el resultado |

## Lo que sí mejoró, moderadamente

| ingrediente | efecto |
|---|---|
| FVG como confluencia con el OB | +0.09 a +0.13 de PF, consistente en ambas mitades |
| Estructura **interna** (pivote de 2 velas) unida a desplazamiento | Sube la frecuencia de ~35 a ~140 ops/año sin destruir el PF |
| Frescura de zona (edad_max) | Sigue siendo la palanca más fuerte, igual que en la sesión anterior |
| Mover el gatillo de BE mucho antes (0.4R en vez de 0.8R) | DD −36% con PF ligeramente mejor — la palanca de riesgo-por-operación que faltaba |

Configuración `union+FVG, 08-13 NY, edad≤12`: **863-920 ops en 6,26 años
(~140/año), PF 1.45-1.50, DD $3.664-5.730**, 0 años negativos en 7.
Ver [CONFIRMACION.md](CONFIRMACION.md) para las cifras completas de esa línea.

## El hallazgo: barrido de liquidez + reversión (`sweep_reversion.py`)

Mecanismo distinto a todo lo probado hasta ahora — no es ruptura, es
**caza de stops sobre un pivote confirmado + cierre de vuelta**, el patrón
de "liquidez pendiente" que describe el manual ICT del usuario. Motor:
`data/engine/python/sweep_reversion.py`.

| variante | ops/año | PF | DD (3c) | años negativos |
|---|---|---|---|---|
| A) 08:00-13:00 NY, RR2=6, lock=0.10 | 110 | 1.81 | $4.099 | 0/7 |
| **B) 09:00-13:00 NY, RR2=6, lock=0.15** | **79** | **2.09** | **$2.628** | **0/7** |

Es el primer resultado de todo el proyecto (dos sesiones completas) con
**cero años negativos y mitades del histórico casi idénticas** (1.93/2.33).

### Dimensionamiento — variante B

| c | DD | neto/año | P(pasar), trailing | mediana |
|---|---|---|---|---|
| 1 | $876 | $2.320 | 100% | 62,1 sem |
| 2 | $1.752 | $4.639 | 100% | 29,1 sem |
| 3 | $2.628 | $6.959 | 73,2% | 13,6 sem |
| 4 | $3.504 | $9.279 | 70,7% | **6,4 sem** |

Con 4 contratos es lo más rápido encontrado en todo el proyecto. Con 2, lo
más seguro. Sigue sin existir una combinación "rápida y 100% segura" —
matemática de drawdown trailing, no un parámetro sin explorar.

**Estado: validado solo en Python. Nunca verificado en NinjaTrader.** Antes
de operar con dinero real, pasar por el mismo ciclo que destapó los ocho
look-aheads anteriores: predicción registrada → replay → comparación
operación por operación.

## Indicador Pine de auditoría: `pine/OB_FVG_Visualizador.pine`

Indicador (no estrategia) que replica exactamente la detección del motor de
Python — mismo umbral de desplazamiento, mismo filtro de liquidez, mismo FVG
de 3 velas, mismos niveles de liquidez por pivote con fusión de "iguales" —
para que el usuario audite visualmente en TradingView lo que el backtester
está encontrando, en vez de confiar ciegamente en los números.

Probado en vivo contra TradingView Desktop vía MCP (no solo compilado — con
el gráfico real cargado y capturas de pantalla verificadas). Se encontraron
y corrigieron dos errores reales durante esa auditoría en vivo:

1. **Error de ejecución (RE10045)**: un bucle de confluencia FVG accedía al
   índice 0 de un array de cajas todavía vacío en las primeras barras.
   Corregido con una guarda de tamaño.
2. **Amontonamiento visual**: cada caja de OB se dibujaba extendida a 300
   velas (más de 3 días) sin importar qué pasara, así que con una detección
   cada ~14 velas se apilaban decenas de cajas semitransparentes unas sobre
   otras — parecía ruido, y el usuario tuvo razón en desconfiar de esa
   imagen. Corregido: la caja ahora nace angosta y **crece vela a vela solo
   mientras la zona sigue viva** (no invalidada, dentro de la frescura
   operable); en cuanto se resuelve, se congela su ancho ahí mismo. El
   tamaño de cada caja ahora refleja cuánto tiempo estuvo realmente vigente.

Con datos reales descargados en vivo de TradingView para el 4-14 de
septiembre de 2026, el motor de Python encontró 35 Order Blocks en 500 velas
de 15m — cifra usada para verificar contra tres zonas que el usuario marcó
manualmente en el gráfico, con coincidencia de precio y fecha en al menos
dos de las tres.

### Evolución del visualizador — v9 (2026-09-14)

Tras nuevas revisiones sobre el gráfico de MNQ 5m se consolidaron estos
criterios visuales:

1. Se muestran tanto OB con FVG como OB sin FVG. El FVG es un bono de 15
   puntos ponderados y una distinción de contorno, no un filtro obligatorio.
2. El componente de liquidez distingue peligro (0), neutralidad (50) y apoyo
   u objetivo favorable (100). Se recalcula cada vela para el OB vivo más
   cercano, después de registrar los pivotes y barridos de la vela actual.
3. La lógica de liquidez/FVG continúa activa aunque sus líneas se oculten.
4. La deduplicación ya no descarta dos zonas por un contacto mínimo. El valor
   predeterminado exige 70% de solape sobre la zona menor.
5. Se corrigió la vela de origen en la rama BOS para cada dirección.
6. Se añadió una única línea de tendencia estructural, tenue y opcional, que
   usa pivotes confirmados y se invalida por cierre. Es estrictamente visual.

El visualizador v9 amplía la auditoría discrecional y no es todavía una
réplica exacta de reglas probadas en Python: ni el score completo ni la línea
estructural se han validado como filtros rentables. Esta distinción evita
convertir una mejora visual en una afirmación de rendimiento no demostrada.

## Pendiente

- Verificar `sweep_reversion.py` (variante B) en NinjaTrader con predicción
  registrada — máxima prioridad antes de considerar operarlo
- Auditar con el mismo rigor las estrategias EMA/Fibonacci del otro chat
  (`EMANY11Replay`, `EMAMaxNetReplay`, `FibBreakoutReplay`,
  `HybridReplayValidation`, `ICT_Market_Research`) — no auditadas todavía
- Resolver la inconsistencia encontrada en la simulación de escalado
  dinámico de contratos antes de confiar en cualquier resultado de esa idea

## Variante F (2026-09-14/15): sin límite de edad + liquidez a favor

Motor: `data/engine/python/experimentos_liquidez.py`. Origen: el usuario
insistió en que la frescura de 3h (edad_max=12) era un número inventado, no
un principio real — "sin importar cuánto lleve abandonada, si no ha sido
tocada y tiene confluencias a favor, sigue siendo válida". Se probó
exactamente esa heurística contra la liquidez a favor (`_liq_favor_peligro`,
puerto de `pineV10.pine`) como reemplazo del límite de tiempo.

**Resultado, verificado tick a tick (sep-dic 2025, MNQ, 3 contratos):
54/55 operaciones, neto $4.213, PF 2.12, drawdown máximo $1.637 (26 sep-10
oct).** Casi duplica la frecuencia de la config anterior (29→54-55 ops) sin
perder calidad — el usuario tenía razón, el límite de tiempo dejaba
operaciones válidas sin tomar. Dimensionamiento (bootstrap 20.000 órdenes,
objetivo TopStep 50k $3.000 / pérdida máx $2.000): 3 contratos = 96,7% de
pasar, mediana 7,1 semanas; 4 contratos = 87,0%, mediana 4,9 semanas.

### Lo que se probó DESPUÉS y no mejoró (todo tick-verificado, no solo bar model)

Una auditoría visual del usuario (ver `web/registro_manual.html` y las notas
dejadas en `web/variante_f_chart.html`) encontró 5-7 operaciones concretas
donde la entrada no tenía apoyo real de OB — casi todas del modo BOS, con
30-260pts de deriva entre el toque y la confirmación. Se investigaron varias
correcciones, ninguna sobrevivió la verificación:

| hipótesis | resultado |
|---|---|
| RR dinámico (estirar objetivo a niveles de liquidez apilados) | Bar model prometía PF 1.59-1.62; tick real: **PF 0.42**, pérdida neta |
| Cadena de liquidez (target al nivel más lejano de una cadena, solo puede alargar) | Bar model ya peor que el control (PF 1.65 vs 2.37) — descartado antes de tick |
| Quitar el BE anticipado (0.4R) | Bar model prometía $10.679; tick real: **$2.570, PF 1.27**, 13/55 sin resolver en 8h (vs 1/55 con BE) |
| Cerrar parcial 1/3 en RR1=1.5, resto a RR2 con BE | Tick real: $4.034/PF 2.07 — practicamente igual al control, no aporta |
| Exigir BOS con los mismos filtros de calidad que el desplazamiento | Bar model PF 2.59; tick real: **$3.531/PF 2.07** — empata o pierde levemente contra el control |
| Excluir ventana de edad 20-50h ("tierra de nadie") | Descartado antes de tick: resultó ser un proxy casi exacto de las mismas 4 operaciones BOS ya detectadas — sobreajuste a n=4, no un principio real |
| Invalidar zona por reemplazo (zona opuesta más reciente y viva) | Colapsó de 55 a 10-12 ops con PF 0.23-0.29 en las 3 implementaciones probadas — descartado |
| Invalidar zona por cierre en contra (sin límite de edad) | Colapsa a 1 operación — incompatible por diseño con "sin límite de edad" (casi toda zona es cruzada por el precio alguna vez en meses de historial) |
| Entrada inmediata al tocar la zona (sin esperar vela de confirmación) | 145 ops, PF 1.58, DD $3.792 (vs 41 ops, PF 2.59, DD $1.487 con confirmación) — la espera sí aporta |
| Ampliar sesión a 09-12+19-24 NY (horarios reales del usuario) | Bar model prometía $7.958/PF 2.07; tick real: **$1.248, PF 1.17, DD $2.307** (ya supera el límite de $2.000 con solo 3 contratos) — la sesión nocturna resultó mucho más errática de lo que el modelo por vela mostraba |

**Conclusión: después de ~10 hipótesis distintas, ninguna superó de forma
verificada a la config base.** No es evidencia de que el sistema esté
"terminado" — es evidencia de que $4.213/PF 2.12 es un punto genuinamente
sólido, no un número de suerte fácil de mejorar con el primer ajuste que se
nos ocurra. El problema puntual del BOS (5-7 casos de 55) sigue sin resolver
por falta de muestra — pendiente si aparecen más ejemplos.

### Pendiente real, no resuelto todavía

- La idea de "liquidez más cercana condicionando la dirección" del usuario
  (el OB puede apuntar en una dirección, pero si la liquidez más cercana
  está del otro lado, el precio probablemente va para allá) — nunca se
  implementó de verdad, solo se probaron versiones parciales (gate de
  favor/peligro, cadena de RR). Sigue siendo la hipótesis más grande sin
  probar.
- Recalibrar la misma lógica para 5m desde cero (los parámetros del 15m
  copiados tal cual pierden: PF 0.91-1.20 según la gestión).
- `web/registro_manual.html` — el usuario está registrando sus propias
  entradas discrecionales (precio, dirección, motivo) para cruzarlas contra
  lo que detecta el motor y encontrar el filtro que falta.
