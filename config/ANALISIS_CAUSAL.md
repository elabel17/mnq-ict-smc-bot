# Los cinco look-aheads del motor original

Encontrados el 2026-09-10 al portar la estrategia a NinjaTrader. Cada uno
describe operaciones que exigen saber algo que solo se conoce al cerrar la vela.

| # | look-ahead | efecto |
|---|---|---|
| 1 | **Sesgo de 1H** calculado con el cierre de la hora en curso | $386.343 → $290.250 |
| 2 | **Selección de zona**: elegía la más reciente ENTRE LAS TOCADAS, sabiendo cuáles se tocaron. En el 11,1% de las entradas había 2+ niveles tocados a la vez | $290.250 → $232.396 |
| 3 | **Precio de entrada**: cobraba el borde del OB si la vela llegaba hasta ahí, y el del margen si no. El mejor de los dos, decidido después de ver la vela. Solo el 27% de las entradas llega al OB | $232.396 → $154.638 |
| 4 | **Filtro del barrido**: descartaba las operaciones donde la vela perforó el fondo del OB. Una límite descansando se llena igual | $154.638 → $102.790 |
| 5 | **`lock_r` > `be_trigger_r`**: colocaba el stop asegurado por encima del precio y lo daba por ejecutado | aparecía como PF 1.78 falso |

## Verificación

El motor causal (`v_nivel.py`, modo `aire`) produjo **83 operaciones** en la
ventana 27-ago a 8-sep de 2026. El replay de NinjaTrader produjo **83**.
Los precios de entrada coinciden en las operaciones comunes (desviación media
0,03 pts entre el nivel pedido y el fill, máximo 2,25 pts en 65 operaciones).

## Recuperación

Partiendo del causal PF 1.25, la búsqueda contra ese motor (no contra el
inflado) recuperó hasta PF 1.92:

| paso | PF | DD (3c) |
|---|---|---|
| causal, parámetros viejos | 1.25 | $6.824 |
| + disp_mult 2.0 | 1.41 | $4.864 |
| + ventana 09–11, RR2 5.0 | 1.55 | $5.022 |
| + segunda sesión 02–06 | 1.47 | $3.771 |
| + **frescura de zona ≤ 3 velas** | **1.92** | **$1.870** |

El hallazgo decisivo es la **frescura**: si el precio vuelve a la zona en las
3 primeras velas la reacción es fiable; a partir de la vela 8 el PF cae a 1.5.
El `zone_max_age = 60` heredado permitía operar zonas de hasta 5 horas.
