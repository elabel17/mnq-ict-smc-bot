# Informe: el script descarta Order Blocks válidos sin mitigar

**Fecha:** 2026-09-08
**Origen:** hipótesis del operador — el script busca el OB más cercano y
descarta los que están más atrás en el tiempo pero siguen hábiles, quedándose
solo con los OB "internos" entre desplazamientos consecutivos.
**Veredicto: la hipótesis es correcta**, y corregirlo es la mejora más grande
encontrada en todo el proyecto.

---

## 1. Dónde está exactamente el problema

No está en `obScanBars` (la búsqueda de la vela de origen), como parecía a
primera vista. Está en que **el script solo puede recordar una zona por lado**:

```pine
var float bullTop = na      // UNA sola variable
var float bullBot = na

if bullDisp
    ...
    bullTop := high[idx]    // sobreescribe: el OB anterior desaparece
    bullBot := candBot
```

Cuando se forma un OB alcista nuevo, el anterior **se destruye aunque siguiera
sin mitigar y perfectamente operable**. Lo mismo del lado bajista. El script
nunca puede tener dos zonas alcistas vivas a la vez.

## 2. `obScanBars` no era el problema

| obScanBars | Ops | Neto | PF | Max DD |
|---|---|---|---|---|
| 10 (actual) | 1.183 | $130.935 | 2,21 | −$2.715 |
| 15 | 1.184 | $131.407 | 2,21 | −$2.715 |
| 20 | 1.184 | $131.407 | 2,21 | −$2.715 |
| 30 | 1.184 | $131.407 | 2,21 | −$2.715 |

Buscar la vela de origen más atrás aporta **una sola operación** en 5,8 años.
Lógico: después de un desplazamiento casi siempre hay una vela de color
opuesto a pocas velas de distancia. Descartado como vía de mejora.

## 3. Mantener varias zonas vivas: el resultado

Cada zona se guarda por separado, con su propio estado de `cleared`/`fresh`, y
caduca a las N velas si nadie la toca.

| Config | Ops | Neto | PF | Max DD | Meses (−) | 1ª mitad / 2ª mitad |
|---|---|---|---|---|---|---|
| **Actual: 1 zona por lado** | 1.183 | $130.935 | 2,21 | −$2.715 | 2/71 | $62.341 / $68.594 |
| Multi, caduca 100 velas | 1.273 | $153.684 | 2,35 | **−$2.137** | **1/71** | $75.536 / $78.148 |
| Multi, caduca 200 velas | 1.339 | $164.909 | 2,38 | −$2.264 | 2/71 | $78.672 / $86.237 |
| **Multi, caduca 300 velas** | **1.365** | **$168.649** | **2,39** | **−$2.264** | **2/71** | **$80.199 / $88.450** |
| Multi, caduca 500 velas | 1.397 | $170.838 | 2,35 | −$2.264 | 2/71 | $81.085 / $89.753 |
| Multi, caduca 1000 velas | 1.437 | $173.927 | 2,32 | −$2.595 | 2/71 | $83.470 / $90.457 |
| Multi, sin caducidad | 1.501 | $177.190 | 2,27 | −$2.595 | 2/71 | $84.685 / $92.506 |

**Mejora las cuatro dimensiones a la vez.** Con caducidad a 300 velas:

- Ganancia: $130.935 → **$168.649** (+$37.714, **+29%**)
- Profit factor: 2,21 → **2,39**
- Max drawdown: −$2.715 → **−$2.264** (17% menos)
- Meses negativos: 2 → **2** (igual)

Y la prueba de las dos mitades: **+29% en la primera y +29% en la segunda.**
Idéntico en ambas. Eso no es un período afortunado, es un efecto estructural.

## 4. Por qué 300 velas y no "sin caducidad"

La curva **se estanca**, no crece sin límite — señal sana, no de sobreajuste:

- 100 → 200 velas: +$11.225
- 200 → 300: +$3.740
- 300 → 500: +$2.189
- 500 → sin caducidad: +$6.352 (con PF cayendo de 2,35 a 2,27 y peor drawdown)

A partir de 300 velas el dinero extra viene acompañado de PF peor y, pasadas
500, de más drawdown. 300 velas ≈ **3 días de mercado**, que además es una
regla defendible: un OB sin mitigar sigue siendo relevante unos días, no
eternamente.

## 5. Si varias zonas se tocan en la misma vela

| Criterio | Neto | PF |
|---|---|---|
| La más reciente | $164.909 | 2,38 |
| La de menor riesgo | $162.275 | 2,36 |

Diferencia marginal. Se queda "la más reciente" por ser la más simple.

## 6. Operaciones por día (duda planteada)

El script **sí permite más de una al día**, aunque no es lo común:

| Operaciones ese día | Nº de días |
|---|---|
| 1 | 550 |
| 2 | 222 |
| 3 | 46 |
| 4 | 10 |
| 5 | 1 |
| 6 | 1 |

830 días operados en 5,8 años, promedio **1,43 por día operado**, máximo 6.
La observación de "casi siempre una al día" es correcta: el 66% de los días
operados tienen exactamente una. El límite real no es una regla de "una por
día" — es la combinación de una sola operación abierta a la vez más una sola
zona viva por lado. Con multi-zona sube a ~1,6 por día operado.

## 7. Estado

**Nada implementado todavía.** Llevar esto a Pine no es cambiar un parámetro:
requiere reescribir la gestión de zonas con arrays (`array<box>`, estado por
zona) en vez de las variables sueltas actuales. Es un cambio estructural del
núcleo del script y conviene decidirlo explícitamente antes de tocarlo.
