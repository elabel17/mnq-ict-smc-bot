# Informe: operaciones consecutivas / re-entradas en la misma zona

**Fecha:** 2026-09-08
**Motivo:** se observaron en el chart varias operaciones seguidas en pocas velas.
Sospecha planteada: si la primera no logró desplazamiento, repetir en la vela
siguiente aumentaría la probabilidad de pérdida total.
**Datos:** histórico completo, 136.049 velas de 15M (2020-11 a 2026-09),
config v13 (lock 0.8R), modelo de ejecución realista.

---

## 1. Primero: el chart exagera visualmente lo que ocurre

Cada operación dibuja hasta **tres etiquetas** distintas:

1. la entrada (`LONG …` / `SHORT …`),
2. el momento en que mueve el stop (`→ Asegura +0.8R (1.2R)`),
3. el cierre (`= Cerrado asegurando +0.8R`, `✓ TP1`, `✗ PÉRDIDA TOTAL`).

Un bloque que parece 8-10 operaciones suele ser **3 o 4 reales**. Conviene
contar solo las etiquetas de entrada antes de juzgar la densidad.

## 2. El hallazgo principal: el caso que te preocupa NO existe

| Re-entrada en la MISMA zona, según cómo cerró la anterior | Casos |
|---|---|
| **La anterior fue PÉRDIDA TOTAL** | **0** |
| La anterior cerró asegurando +0.8R | 32 |
| La anterior hizo TP1 | 63 |
| La anterior hizo TP2 | 16 |

**Cero casos en 5.8 años.** Y no es casualidad estadística — es estructural:

- Para que una operación larga sufra pérdida total, el precio tiene que caer
  hasta `bullBot − 2` (debajo del suelo del OB).
- Para llegar ahí necesariamente atraviesa `bullTop`.
- Y atravesar `bullTop` es justo lo que marca la zona como consumida
  (`bullFresh := false`).

Es decir: **toda pérdida total mata la zona automáticamente.** El script nunca
puede insistir en un Order Block que ya falló.

## 3. Entonces, ¿qué son las operaciones consecutivas que se ven?

Son re-entradas en zonas que **cerraron en ganancia** y siguen vivas. Ocurre
cuando el precio entra en la banda de 12 puntos pero no llega a tocar el borde
exacto del OB: la operación se abre, se protege en +0.8R, cierra ahí, y la zona
sigue intacta porque el precio nunca la penetró de verdad.

Leído así, no es "insistir en una idea fallida" — es lo contrario: **es la zona
aguantando y el precio respetándola.** Y el rendimiento lo confirma:

| Grupo | Ops | Neto | Win rate | Pérdida total | $/op |
|---|---|---|---|---|---|
| Zona nueva (referencia) | 1.074 | $116.682 | 61% | 39% | $109 |
| Re-entrada tras cierre en +0.8R | 32 | $3.354 | 66% | 34% | $105 |
| Re-entrada tras TP1 | 63 | $7.331 | 63% | 37% | $116 |
| Re-entrada tras TP2 | 16 | $1.927 | 75% | 25% | **$120** |

Las re-entradas tienen **mejor win rate y MENOR tasa de pérdida total** que las
entradas en zona nueva. No son un problema: son de las mejores del sistema.

## 4. El único patrón levemente negativo encontrado

| Grupo | Ops | Neto | $/op |
|---|---|---|---|
| Abre ≤2 velas después de una PÉRDIDA TOTAL (en otra zona) | 27 | $1.380 | **$51** |
| Abre ≤2 velas después de un cierre en ganancia | 105 | $9.172 | $87 |
| Referencia general | 1.185 | $129.295 | $109 |

Entrar muy pegado a una pérdida total rinde la mitad de lo normal. Pero son
**27 operaciones en 5.8 años** que suman $1.380 — filtrarlas no cambia nada
material, y con esa muestra no se puede distinguir señal de ruido.

## 5. Qué costaría cada arreglo

| Variante | Ops | Neto | PF | Max DD | Meses (−) |
|---|---|---|---|---|---|
| **Actual (v13)** | 1.185 | **$129.295** | 2,19 | **−$2.715** | **3/71** |
| Prohibir re-entrada tras pérdida total | 1.185 | $129.295 | 2,19 | −$2.715 | 3/71 |
| Consumir la zona al ENTRAR (coherencia lógica) | 1.077 | $116.577 | 2,13 | −$3.093 | 4/71 |
| Cooldown 2 velas | 1.147 | $125.463 | 2,18 | −$2.715 | 3/71 |
| Cooldown 3 velas | 1.109 | $121.292 | 2,19 | −$2.715 | 3/71 |
| Cooldown 4 velas | 1.078 | $117.573 | 2,18 | −$2.715 | 5/71 |
| Cooldown 8 velas | 1.002 | $105.885 | 2,11 | −$2.715 | 5/71 |

- "Prohibir re-entrada tras pérdida total" da **exactamente el mismo resultado**
  — confirmación independiente de que no hay ni un caso que bloquear.
- Todos los cooldowns cuestan dinero, en proporción a lo restrictivos que son.
- Hacer coherente el consumo de zona (marcarla usada al entrar, no al tocar el
  borde) cuesta **−$12.718 y empeora el drawdown y los meses negativos.**

## 6. Conclusión

**No recomiendo cambiar nada.** La sospecha era razonable pero los datos la
descartan: el sistema ya es estructuralmente incapaz de repetir sobre una zona
que falló, y las re-entradas que sí existen son sobre zonas que están
demostrando que aguantan.

**Nota sobre riesgo:** las operaciones consecutivas no concentran riesgo. El
script mantiene la regla de una sola operación abierta a la vez, así que la
exposición máxima siempre son 3 contratos, pase lo que pase.

**Inconsistencia lógica documentada (no corregir):** la entrada se dispara en
`bullTop + 12` pero la zona solo se consume al tocar `bullTop`. Es una
asimetría real en el código, y es la que permite las re-entradas. Corregirla
"limpiaría" la lógica pero cuesta $12.718. Queda documentada aquí para que
nadie la "arregle" por error en el futuro.
