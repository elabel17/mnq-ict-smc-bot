# Motores de backtest — qué es cada archivo

| archivo | qué es | usar |
|---|---|---|
| `claude_engine5.py` | motor ORIGINAL de 5m | **NO** — contiene los look-aheads 2, 3, 4 y 5 |
| `v_borde.py` | + entrada siempre en el borde del margen | intermedio |
| `v_ob.py` | + entrada siempre en el borde del OB | comparativa |
| `v_real.py` | + sin el filtro del barrido | causal, base |
| `v_nivel.py` | + nivel de entrada seleccionable (`entry_mode`) | **ESTE** |
| `v_ok.py` | v_nivel con guarda de stop a vela cerrada | solo para modelar `OnBarClose` |
| `v_split.py` | registra si la vela penetró hasta el OB | análisis de parciales |
| `buscar_causal.py` | barrido de gestión (450 combinaciones) | reproducible |
| `buscar_calidad.py` | barrido de detección (324 combinaciones) | reproducible |

## El motor a usar

```python
import v_nivel as V
V.SLIPPAGE_TICKS = 2
V.COMMISSION_PER_CONTRACT_SIDE = 1.00
raw = V.sel_real(bars, entry_mode='aire', **params)
pr  = [t for t in V.price_trades(raw, 0, 4) if t['zone_age'] <= 3]
```

`entry_mode='aire'` pone la límite en `high + margen`, fuera de la mecha.
Es el único modo ejecutable y además el más rentable (`cuerpo` da PF 1.10,
`medio` da PF 1.17 con 44% de aciertos).

El filtro `zone_age <= 3` se aplica DESPUÉS porque el atributo se registra
en cada operación. En NinjaScript es el parámetro `ZoneMaxAge`.

## Regla que no se puede romper

`lock_r` SIEMPRE menor que `be_trigger_r`. Al revés, el stop asegurado queda
por encima del precio: el motor lo daba por ejecutado y el broker lo rechaza.
Era el quinto look-ahead y aparecía como un falso PF 1.78.
