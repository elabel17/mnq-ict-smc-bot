# v15 multi-zona — verificación antes de operar en vivo

**Fecha:** 2026-09-08. Contexto: se implementa justo antes de empezar a operar
una cuenta de fondeo, así que se verifica en lugar de asumir.

## 1. Qué cambia en v15

1. **Multi-zona.** Array de zonas vivas en vez de una sola variable por lado.
   Una zona muere al tocarse su borde o al caducar (300 velas ≈ 3 días).
2. **Corrige un desajuste real entre el Pine y el backtest.** Hasta v14, al
   tocar TP1 el stop del corredor iba a *breakeven*; el motor validado lo movía
   al nivel asegurado (+lockR). El script rendía menos que su propio backtest.
3. **Se elimina `request.security()`.** Pedía "15" desde un gráfico de 15M, lo
   cual era redundante. Ahora es nativo — y por eso el script avisa en pantalla
   si no está en 15M.

## 2. Verificación 1 — el conteo de zonas vivas no es un bug

El plot de diagnóstico marcaba "Zonas vivas: 0", lo que parecía sospechoso.
El motor de referencia confirma que es normal:

- Promedio de zonas vivas por vela: **2,07**
- Máximo simultáneo en 5,8 años: **12** (el tope de 40 nunca se alcanza)
- **17,9% de las velas tienen cero zonas vivas**

## 3. Verificación 2 — comparación trade por trade contra el motor

Se reprodujo en Node el modelo exacto del Pine (disparo del 1.2R con el
extremo de la vela) y se comparó con las etiquetas reales del gráfico para el
período 2026-08-25 → 2026-09-03:

| Motor de referencia | Etiqueta en el Pine | ✓ |
|---|---|---|
| SHORT 29275,50 SL 29312 r36,50 → asegura → cierra +0.8R | idéntico | ✓ |
| SHORT 29277,00 SL 29312 r35,00 → asegura → cierra +0.8R | idéntico | ✓ |
| SHORT 29278,75 SL 29312 r33,25 → asegura → cierra +0.8R | idéntico | ✓ |
| SHORT 29181,75 SL 29261 r79,25 → PÉRDIDA TOTAL | idéntico | ✓ |
| LONG 29181,75 SL 29131 r50,75 → asegura → cierra +0.8R | idéntico | ✓ |
| LONG 29440,00 SL 29423 r17,00 → TP1 → TP1+BE | idéntico | ✓ |
| LONG 29065,25 SL 29019,25 r46,00 → asegura → cierra +0.8R | idéntico | ✓ |
| LONG 29064,00 SL 29019,25 r44,75 → PÉRDIDA TOTAL | idéntico | ✓ |

**8 de 8 coinciden** en precio de entrada, stop, riesgo y desenlace.

## 4. Aviso: el gráfico es más optimista que el backtest

El Pine dispara la protección del 1.2R con el **extremo intra-vela**; el número
validado de $168.649 usa el **cierre de vela**, que es más conservador. En el
gráfico verás algún desenlace mejor del que el backtest asume. La diferencia
medida es de −3% a −20% según la configuración. **Usa $168.649 como
expectativa, no lo que se ve en el chart.**

## 5. Riesgo para una cuenta de fondeo

Lo importante no es el drawdown total sino el **peor día** y el **drawdown
incluyendo flotante** (lo que ve la regla de trailing de la prop firm).

| Contratos | Neto 5,8 años | Peor día | 2º peor | Max DD cerrado | Max DD con flotante | Riesgo máx/op |
|---|---|---|---|---|---|---|
| 1 | $56.301 | −$375 | −$293 | −$726 | **−$765** | $200 |
| 2 | $112.348 | −$749 | −$586 | −$1.538 | **−$1.657** | $400 |
| 3 | $168.649 | −$1.124 | −$879 | −$2.264 | **−$2.422** | $600 |

Días perdedores con 3 contratos (904 días operados, 36% en pérdida):

| Pérdida del día | Nº de días | % de días operados |
|---|---|---|
| ≥ $500 | 37 | 4,09% |
| ≥ $750 | 3 | 0,33% |
| ≥ $1.000 | 1 | 0,11% |
| ≥ $1.500 | 0 | 0% |

### Cómo leer esto

- El **"max DD con flotante"** suma la peor excursión adversa de cada operación
  mientras estaba abierta. Es la aproximación más cercana a lo que mide el
  trailing drawdown de una prop firm, y es un 7% peor que el drawdown cerrado.
- Con **3 contratos** el riesgo máximo por operación es **$600** (tope de 100
  puntos). Si tu cuenta tiene un trailing de $2.000, una sola operación puede
  consumir el 30% del colchón, y el peor día histórico ($1.124) más de la mitad.
- Con **1 contrato**, el peor día histórico es $375 y el DD con flotante $765.

**Esto es histórico, no una garantía.** El peor día futuro puede superar al
peor día pasado. El dimensionamiento es decisión del operador según las reglas
concretas de su cuenta.
