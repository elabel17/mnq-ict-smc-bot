# Parámetros — ICT 15M OB Entry v12

| Parámetro | Valor | Notas |
|---|---|---|
| `dispLen` | 20 | Barras para el rango promedio (SMA de high-low) que define "desplazamiento" |
| `dispMult` | 2.5 | La vela debe tener rango >= 2.5x el promedio para contar como desplazamiento |
| `dispCloseFrac` | 0.6 | El cierre debe cubrir >= 60% del rango en la dirección del desplazamiento |
| `obScanBars` | 10 | Barras hacia atrás para buscar la vela de origen (última opuesta) |
| `liqCheckBars` | 12 | Ventana para el filtro de "liquidez limpia" detrás del OB |
| `liqTolerancePts` | 4.0 | Tolerancia (pts) para considerar que una mecha "testeó" el mismo nivel |
| `liqAccumBars` | 6 | Barras consecutivas dentro de la tolerancia = acumulación real → OB descartado |
| `slBufferPts` | 2.0 | Buffer más allá del borde lejano del OB para el stop loss |
| `entryBufferPts` | 12.0 | Margen de entrada más allá del borde cercano del OB — regla original del usuario: *"tu entrada será al toque de ese OB agregándole 12 pips de rango extra"* |
| `rr1` | 1.8 | TP1 (cierra 2 de 3 contratos) — validado como óptimo vs. 1.2R y 2R |
| `rr2` | 4.0 | TP2 (cierra el contrato restante) |
| `useRiskCap` | true | Descarta la señal si el riesgo proyectado supera `maxRiskPts` |
| `maxRiskPts` | 100.0 | Tope de riesgo — mejora "gratis" confirmada (más $, menos drawdown) |
| `beTriggerR` | 1.2 | Al alcanzar 1.2R a favor, se activa la protección |
| `lockR` | 0.5 | En vez de breakeven puro, asegura +0.5R real — la mejora de mayor impacto encontrada (58% de las operaciones perdedoras habían llegado a 1R+ antes de revertir) |
| Sesión | 18:00–11:00 NY | `useSessionFilter=true` |
| Contratos | 3 | 2 cierran en TP1, 1 corre hasta TP2 |
| Comisión | $0 | `commission_value=0.0` en el backtest — no refleja comisiones reales del broker |

## Importante sobre `useRiskCap` y `entryBufferPts`

El cap de riesgo (`longRisk0`/`shortRisk0`) se calcula **sin** contar el
margen de entrada de 12 puntos — usa solo `origin range + slBufferPts`. Esto
significa que el riesgo real de una operación (una vez rellenada con el
margen completo) puede superar el tope de 100 puntos hasta en 12 puntos más.
Ver `docs/ANALYSIS_LOG.md` para el análisis de este caso específico.
