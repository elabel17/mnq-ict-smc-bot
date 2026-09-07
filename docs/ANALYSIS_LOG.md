# Bitácora de análisis

## 2026-09-07 — Efecto del margen de entrada (12pt) en Order Blocks de rango grande

**Pregunta del usuario:** los OB cuya vela de origen tiene un rango
inusualmente grande, combinados con los 12 puntos de margen de entrada,
generan stops sobredimensionados. ¿Qué pasa si se elimina el margen de
entrada específicamente para esos casos (exigiendo toque exacto/más profundo)?

**Dataset:** 10,369 velas de 15M de `CME_MINI_DL:MNQ1!`, 2026-03-31 a
2026-09-07 (~5.2 meses — el máximo que se pudo cargar en esa sesión de
TradingView tras un crash de la conexión CDP). Ver `data/mnq_15m_bars.json`.

**Metodología:** se detectaron 188 Order Blocks (85 alcistas, 103 bajistas)
con la misma lógica de `f_ob()` de v12. En vez de un umbral estadístico
arbitrario, se usó el propio mecanismo del cap de riesgo: como
`useRiskCap` no cuenta el margen de 12 puntos, un OB puede pasar el filtro
(`origin range + slBufferPts <= 100`) y aun así, al rellenarse con el margen
completo, terminar arriesgando hasta 12 puntos más de lo previsto. Se definió
"rango grande" como `origRisk > 100 - 12 = 88` — los únicos casos donde el
margen puede empujar el riesgo real por encima del cap de 100.

De los 188 OB, solo **7** cayeron en esa categoría y llegaron a tocar zona
(la mayoría de los OB de rango grande ya son rechazados directamente por el
cap de 100, antes de llegar a operarse).

**Resultado** (mismo universo de 107 trades en ambos escenarios, solo cambia
el trato de esos 7):

| | Con margen 12pt (v12 actual) | Sin margen para los 7 grandes |
|---|---|---|
| PnL total (107 trades) | **$20,670** | $19,719 |
| Win rate total | 78.5% | 77.6% |
| PnL de los 7 trades grandes | **-$516** | -$1,467 |
| Win rate de los 7 trades grandes | 42.9% | 28.6% |
| Riesgo promedio (pts) de esos 7 | 97.4 | 95.4 |

**Conclusión:** resultado opuesto a la hipótesis. Quitar el margen de 12
puntos para los OB de rango grande **empeora** los resultados, tanto en el
subconjunto de 7 trades como en el total (~$950 menos en 5 meses). Razón
mecánica: sin margen, la entrada solo se activa cuando el precio realmente
penetra el cuerpo del OB (retroceso más profundo) — eso ocurre más tarde y
deja menos margen de maniobra antes del SL, resultando en una entrada más
tardía y más vulnerable, no más segura.

**Caveat:** la muestra de "grandes" es de solo 7 trades — insuficiente para
ser concluyente por sí sola. La dirección del efecto (negativo) es clara,
pero no debe tomarse como definitivo sin más datos. Pendiente: repetir con
un histórico más largo si se consigue reconstruir (el chart topó un límite de
carga en esa sesión).

**Decisión:** no se implementó ningún cambio en v12 a raíz de este análisis
— se mantiene el margen de 12 puntos tal cual, sin excepciones por rango.
