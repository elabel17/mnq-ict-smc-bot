# Decisiones cerradas

Registro de decisiones de diseño ya tomadas con el usuario, para no
reabrir debates ya resueltos en sesiones futuras.

- **TP1 = 1.8R (no 1.2R ni 2R).** Validado con grid A/B sobre el histórico
  completo: 1.8R es el punto más rentable en $ y win rate combinados.
- **Breakeven anticipado a 1.2R, asegurando +0.5R real (no $0 puro).**
  El análisis de MFE (max favorable excursion) mostró que 58% de las
  operaciones perdedoras habían llegado a 1R+ a favor antes de revertir —
  esta fue la mejora de mayor impacto encontrada en todo el proceso de
  optimización. +0.5R se eligió específicamente por quedar en la "zona
  interior suave" de la curva de resultados; +1.0R/+1.2R mostraban mejora
  monótona hasta el límite físico, señal de sobreajuste a ejecución
  intra-vela poco realista en velas de 15M (no una ventaja genuina).
- **Tope de riesgo absoluto de 100 puntos por operación (`maxRiskPts`).**
  Confirmado como mejora "gratis": más ganancia y menos drawdown
  simultáneamente (no es un trade-off).
- **Margen de entrada de 12 puntos (`entryBufferPts`) — regla original del
  usuario, no un bug.** Cita textual: *"tu entrada será al toque de ese OB
  agregándole 12 pips de rango extra, es decir, si tu OB empieza en 315 tu
  entrada está permitida desde 327, para mejorar los rangos de respuesta."*
  Confirmado en el análisis de 2026-09-07 (ver `ANALYSIS_LOG.md`) que
  quitarlo para OB de rango grande empeora los resultados — se mantiene sin
  excepciones.
- **Filtro de riesgo relativo a volatilidad local (`riskVol`) — descartado
  como filtro duro.** Es el predictor individual más fuerte de pérdida total
  (8.2% a riskVol<=1.0 vs 40.9% a riskVol>2.5), pero filtrar por él es un
  trade-off genuino: mejor PF/drawdown pero bastante menos $ total. El
  usuario eligió mantener la ganancia total máxima en vez de adoptarlo.
- **Filtro de horario 00:00–07:00 — evaluado y descartado.** Reduce pérdidas
  en madrugada pero reduce más ganancia que pérdida evitada. No se adoptó.
- **v12 y el indicador de alertas están finalizados (2026-09-07).** El
  usuario pidió explícitamente no modificarlos más — cualquier análisis o
  ajuste nuevo se hace en un script/indicador aparte.
- **Automatización en vivo:** confirmado en pruebas controladas que
  `strategy.entry()` no ejecuta órdenes reales en la cuenta actual (feed de
  datos retrasado — símbolo `CME_MINI_DL:MNQ1!`, sufijo `_DL`). El usuario
  planea una suscripción de datos en tiempo real vía su cuenta fondeada —
  pendiente re-testear una vez activa.
