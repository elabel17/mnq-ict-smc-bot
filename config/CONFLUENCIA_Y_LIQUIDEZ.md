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
