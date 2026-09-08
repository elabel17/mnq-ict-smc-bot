# Informe: zonas detectadas que no llegaron a operarse

**Fecha:** 2026-09-08
**Motivo:** se observaron en el chart zonas dibujadas que el precio tocó
(incluyendo el margen de 12 puntos) y que no generaron operación.
**Datos:** histórico completo, 136.049 velas de 15M (2020-11 a 2026-09),
config v14 (lock 0.8R), modelo de ejecución realista.

---

## 1. La detección NO es el problema

Punto de partida importante: **si la zona aparece dibujada en el chart, el
script la detectó correctamente.** Las cajas solo se dibujan para Order Blocks
que pasaron todos los filtros de detección (desplazamiento ≥2,5x, cierre
direccional ≥60%, vela de origen dentro de 10 velas, liquidez limpia).

Lo que falló no fue detectar el OB — fue el permiso para entrar. Hay cuatro
filtros que pueden bloquear una entrada sobre una zona ya detectada y tocada.

## 2. Cuánto cuesta cada filtro

Cada toque rechazado se simuló como si se hubiera operado (con slippage y
comisión), para poner precio a lo que se está dejando pasar:

| Motivo del rechazo | Toques | Neto simulado | $/op | Win rate | Pérdida total |
|---|---|---|---|---|---|
| **Fuera de sesión** | 1.168 | **$120.254** | **$103** | 54% | 46% |
| Ya hay operación abierta | 1.666 | $87.248 | $52 | 52% | 48% |
| Stop demasiado grande | 218 | $43.819 | **$201** | 54% | 46% |
| Domingo | 77 | $3.790 | $49 | 53% | 47% |

*Referencia: las 1.185 operaciones que sí se toman dan $129.295, o sea $109/op.*

Dos cosas saltan a la vista:

- Los rechazados **fuera de sesión rinden $103/op**, prácticamente igual que
  los que sí se toman ($109). No son operaciones de peor calidad.
- Los rechazados por **stop grande rinden $201/op**, casi el doble — porque
  a mayor riesgo, mayor es también el valor absoluto de cada R ganada.

## 3. Probado como cambios reales de configuración

Las cifras de arriba son simulaciones aisladas y sobreestiman, porque ignoran
que tomar esas operaciones habría bloqueado otras. Probado de verdad:

### Ampliar el tope de riesgo (sesión actual)

| Tope | Ops | Neto | PF | Max DD | Meses (−) |
|---|---|---|---|---|---|
| **100 pts (actual)** | 1.185 | $129.295 | 2,19 | −$2.715 | 3/71 |
| 120 pts | 1.200 | $138.727 | 2,15 | −$2.715 | 3/71 |
| 150 pts | 1.213 | $140.924 | 2,09 | −$3.093 | 3/71 |
| 200 pts | 1.221 | $137.817 | 1,99 | −$3.456 | 3/71 |
| Sin tope | 1.223 | $133.604 | 1,88 | −$6.034 | 7/71 |

### Ampliar la sesión (tope 100)

| Sesión | Ops | Neto | PF | Max DD | Meses (−) |
|---|---|---|---|---|---|
| **18:00-11:00 (actual)** | 1.185 | $129.295 | 2,19 | −$2.715 | 3/71 |
| 18:00-13:00 | 1.400 | $152.587 | 2,07 | −$2.715 | 5/71 |
| **24 horas** | 1.531 | **$172.501** | 2,06 | −$3.297 | 6/71 |
| Solo NY 09:30-16:00 | 850 | $126.032 | **2,33** | **−$2.251** | 8/71 |

## 4. La prueba que separa hallazgo de sobreajuste

Se partió el histórico en dos mitades y se verificó si la mejora aparece en
ambas o solo en una.

| Config | 1ª mitad (2020-11 → 2023-08) | 2ª mitad (2023-09 → 2026-09) | Total |
|---|---|---|---|
| Actual (100 / 18-11) | $62.213 PF2,15 | $67.082 PF2,22 | $129.295 |
| **Tope 120 / 18-11** | $63.495 PF2,07 | $75.232 PF2,22 | $138.727 |
| Tope 150 / 18-11 | $65.817 PF2,05 | $75.107 PF2,12 | $140.924 |
| **Tope 100 / 24h** | **$86.860 PF2,10** | **$85.641 PF2,02** | **$172.501** |
| Tope 120 / 24h | $84.564 PF1,96 | $95.398 PF2,01 | $179.962 |
| Tope 150 / 24h | $82.301 PF1,84 | $96.365 PF1,92 | $178.667 |

**Quitar el filtro de sesión SÍ es robusto.** Mejora en las dos mitades por
igual: +40% en la primera, +28% en la segunda, y los resultados de ambas
mitades quedan casi idénticos entre sí ($86.860 vs $85.641). Eso es señal de
un efecto real, no de un período afortunado.

**Subir el tope de riesgo NO es robusto.** El paso de 100 a 120 aporta apenas
+$1.282 en la primera mitad (con PF y drawdown peores) contra +$8.150 en la
segunda. Casi toda la ganancia viene de un solo período — es exactamente el
perfil de un parámetro sobreajustado. Y con 24h, subir el tope hace la
primera mitad **peor** ($86.860 → $84.564).

## 5. Conclusiones

1. **El filtro de sesión es, con diferencia, lo que más oportunidad deja
   pasar.** Quitarlo son +$43.206 (+33%) sobre 5,8 años, y aguanta la prueba
   de las dos mitades.
2. **El tope de riesgo debe quedarse en 100.** La mejora aparente al subirlo
   no se sostiene fuera del período donde se midió.
3. Coste de quitar el filtro de sesión: drawdown de −$2.715 a −$3.297 (+21%),
   meses negativos de 3 a 6, PF de 2,19 a 2,06. A cambio de +33% de ganancia.
   En términos de retorno sobre drawdown, en realidad **mejora**: de 47,6 a
   52,3.

## 6. Advertencias antes de decidir

- **Esto contradice una decisión metodológica deliberada.** La ventana
  18:00-11:00 NY no salió de un backtest: viene del marco ICT, donde la tarde
  de NY se considera de menor calidad. Los datos dicen otra cosa, pero es una
  decisión del operador, no del backtest.
- **Riesgo de sobreajuste acumulado.** Este mismo histórico ya se usó para
  fijar TP1, TP2, beTriggerR, lockR y el tope de riesgo. Cada parámetro extra
  que se ajusta sobre los mismos datos aumenta la probabilidad de estar
  midiendo ruido. La prueba de las dos mitades mitiga eso pero no lo elimina.
- **Operar 24h implica que el bot corre 24h**, con alertas a cualquier hora y
  ejecución en horas de menor liquidez.

**Ningún cambio se aplicó.** Queda a decisión del operador.
