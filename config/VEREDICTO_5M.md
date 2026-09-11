# Veredicto 5m — NO OPERABLE

Fecha: **2026-09-10** (noche). Cierra la línea de Order Blocks en 5m con
orden límite descansando en la zona.

## Qué demostró el replay

Predicción registrada antes de correr: 15 operaciones, +$1.625 (4 contratos).
Resultado real en NinjaTrader: **16 operaciones, −$832**.

Las entradas coincidieron **al céntimo** — mismos precios, mismos stops. La
lógica de detección funciona. Lo que falló fue el motor, no el script.

## El séptimo look-ahead

El motor validaba la zona (`cleared`) y **en esa misma vela** comprobaba si
el precio la había tocado. Una orden límite no puede estar descansando en un
nivel antes de que la zona exista: solo se puede colocar al cierre de esa vela.

| | ops | neto | PF | DD |
|---|---|---|---|---|
| entrada en la misma vela (lo que se medía) | 1.415 | $84.831 | 1.69 | $5.472 |
| **entrada desde la vela siguiente (real)** | 1.032 | **$3.312** | **1.03** | $10.292 |

Con la corrección, el modelo predice −$312 para la ventana del replay. El
resultado real fue −$832. Mismo rango; la diferencia es ruido sobre 16 ops.

## El BE NO era el problema

Se sospechó del mecanismo de breakeven y se descartó con datos:

- Motor **pesimista** (todo empate BE/stop resuelto a favor del stop) da
  resultado **idéntico** al optimista: el motor ya comprobaba el stop primero.
- En el replay: **10 movimientos a BE** en el modelo, **10** en NinjaTrader.
  Una sola línea `STOP_INALCANZABLE` en 16 operaciones.

El BE se replica bien. El problema es que aporta el 47,7% de las operaciones
y $61.048, y con la entrada una vela más tarde el margen se evapora:
ganancias $120.502 contra pérdidas $117.190. **Un margen del 3%.**

## Búsqueda de rescate

160 configuraciones contra `v_causal.py`, con validación en dos mitades.
Mejor resultado: **PF 1.13** (disp 2.0, margen 20, edad 10, RR2 5.0),
$23.849 con DD $7.833. Ninguna configuración supera 1.13.

Señal de agotamiento: el margen de entrada óptimo se va a **20 puntos**, el
borde de la rejilla. El sistema pide entrar cada vez más lejos de la zona.

## Conclusión

Los Order Blocks en 5m, con límite descansando en la zona, **no tienen
ventaja** en MNQ. Los $386.343 originales eran siete errores de causalidad
apilados. No volver sobre esta línea.

## Qué queda en pie

- El histórico (185.066 velas de 5m, 136.049 de 15m)
- `v_causal.py` — el motor que reproduce la ejecución real
- El NinjaScript instrumentado con registro CSV por evento
- `tools/compilar.ps1` — puerta de compilación contra los ensamblados de NT8
- El método: predicción registrada → replay → comparación operación por operación

## Líneas abiertas

1. **Auditar el 15m** — reportaba $121.696 / PF 3.08, nunca medido con este rasero
2. **Entrada por confirmación** — esperar la vela de reacción en la zona y entrar
   a su cierre. Causal por construcción. Nunca probado
3. Otra familia de estrategia si 1 y 2 no dan
