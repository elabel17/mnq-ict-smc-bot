"""
Configuracion de sesion por bloque horario -- script separado, a pedido
del usuario, para no mezclar esta logica dentro del motor de backtest
principal (engine2.py / engine3.py).

Documenta y aplica los DOS regimenes de parametros encontrados y
validados (holdout limpio 70/30, confirmados fuera de muestra) el
2026-09-08/09:

  - MANANA (03:00-11:00 NY): parametros de deteccion IGUALES a los del
    script real (no hacia falta tocarlos, la sesion de NY ya tiene
    volumen alto). Solo se ajusto TP2/BE.
  - NOCHE (18:00-00:00 NY): el volumen es 4-10x menor que en la manana
    (medido: ~2,700-12,000 vs ~25,000-55,000 contratos/vela de 15m), asi
    que las senales de "desplazamiento" son mas ruidosas. La mejora NO
    vino de tocar TP/BE solamente, sino de RE-CALIBRAR el filtro de
    liquidez y los margenes al caracter mas chico de las velas nocturnas
    (rango promedio de vela: 14-25pts de noche vs 40-62pts en NY dia):

      * LIQ_ACCUM_BARS  6 -> 15   (mucho mas permisivo: de noche, que el
        precio vuelva a testear la misma zona varias veces NO invalida
        la liquidez tan rapido como de dia -- el criterio original era
        demasiado estricto para el ritmo mas lento de la noche)
      * LIQ_TOLERANCE_PTS 4.0 -> 2.0 (mas estricto en QUE CUENTA como
        "mismo nivel" -- con rangos mas chicos, 4pts de tolerancia
        agrupaba niveles que en realidad eran distintos)
      * ENTRY_BUFFER_PTS 12.0 -> 8.0 (margen de entrada mas chico,
        proporcional al rango mas chico de las velas nocturnas)
      * SL_BUFFER_PTS 2.0 -> 1.0 (stop mas ajustado, mismo motivo)
      * TP2 4.0R/5.0R -> 7.0R (los movimientos nocturnos que SI funcionan
        recorren proporcionalmente mas respecto a su propio riesgo mas
        chico -- conviene dejarlos correr mas)
      * BE trigger 1.2R -> 0.8R, lock 1.0R -> 0.3R (activa la proteccion
        antes y asegura menos, porque el riesgo inicial ya es mas chico)

Impacto medido (18:00-00:00 NY, 3 contratos, 0 en TP1 / 3 corren a TP2,
sobre 6.27 anios): net $8,426 -> $22,241 (x2.6), PF 1.30 -> 1.84,
winrate 52.6% -> 64.4%. Confirmado fuera de muestra (avg/trade IN=$80.76
vs OOS=$78.53 -- practicamente identico, no es sobreajuste).

LIMITACION IMPORTANTE: el volumen se redujo el ruido pero NO lo elimino
-- el bloque nocturno sigue operando con 4-10x menos participacion real
que la manana, así que incluso con esta mejora, cada operacion nocturna
individual sigue siendo estadisticamente menos confiable que una de la
manana (mas sensible a que la distribucion futura no se parezca
exactamente a la de este historico). Recomendado forward-test en
simulador antes de operar esto con dinero real.
"""
import engine3 as e3

WINDOWS = {
    "morning": {
        "label": "Manana 03:00-11:00 NY",
        "session_start_min": 180, "session_end_min": 660,
        "rr1": 1.8, "rr2": 6.0, "be_trigger_r": 1.2, "lock_r": 1.0,
        # deteccion: defaults del script real (sin cambios)
        "disp_mult": 2.5, "liq_accum_bars": 6, "liq_tolerance_pts": 4.0,
        "entry_buffer_pts": 12.0, "sl_buffer_pts": 2.0,
    },
    "night": {
        "label": "Noche 18:00-00:00 NY",
        "session_start_min": 1080, "session_end_min": 1440,
        "rr1": 1.8, "rr2": 7.0, "be_trigger_r": 0.8, "lock_r": 0.3,
        # deteccion: RECALIBRADA para el volumen/rango mas chico de la noche
        "disp_mult": 2.5, "liq_accum_bars": 15, "liq_tolerance_pts": 2.0,
        "entry_buffer_pts": 8.0, "sl_buffer_pts": 1.0,
    },
}


def run_window(bars, window_key, qty_tp1=0, qty_tp2=3):
    """Corre el backtest para UNA sola ventana con su propio regimen de
    parametros (deteccion + TP/BE). Devuelve trades ya en dolares."""
    w = dict(WINDOWS[window_key])
    label = w.pop("label")
    raw = e3.select_trades(bars, **w)
    return e3.price_trades(raw, qty_tp1=qty_tp1, qty_tp2=qty_tp2), label


def run_combined(bars, qty_tp1=0, qty_tp2=3):
    """Corre manana Y noche por separado (cada una con su propio regimen) y
    junta los resultados en una sola lista ordenada cronologicamente.

    LIMITACION: cada ventana se simula de forma independiente, así que en
    teoria podria "solaparse" una operacion nocturna que sigue abierta
    con una matutina si cruzara la zona muerta 00:00-03:00 -- en la
    practica esto es raro (las operaciones se resuelven en pocas horas),
    pero es una aproximacion, no una simulacion 100% conjunta."""
    all_trades = []
    for key in WINDOWS:
        trades, label = run_window(bars, key, qty_tp1, qty_tp2)
        for t in trades:
            t["window"] = label
        all_trades.extend(trades)
    all_trades.sort(key=lambda t: t["entry_time"])
    return all_trades


if __name__ == "__main__":
    bars = e3.load_bars()

    print("=" * 90)
    print("RESULTADO POR VENTANA (params propios, historico completo 6.27 anios)")
    print("=" * 90)
    for key in WINDOWS:
        trades, label = run_window(bars, key)
        e3.summarize(trades, label)

    print("\n" + "=" * 90)
    print("COMBINADO: manana + noche, cada una con su regimen (aproximacion)")
    print("=" * 90)
    combined = run_combined(bars)
    e3.summarize(combined, "Manana + Noche combinadas")
