#region Using declarations
using System;
using System.Collections.Generic;
using NinjaTrader.Cbi;
using NinjaTrader.Gui.Tools;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.Strategies;
#endregion

// ============================================================================
// ICT 15M OB Strategy — puerto a NinjaScript de "ICT 15M OB Entry v15 -
// multi-zona" (Pine v6). Misma logica de deteccion y gestion, verificada
// bar-por-bar contra el motor Python que a su vez fue validado contra
// operaciones reales extraidas del script Pine corriendo en TradingView
// (ver docs/analisis_estrategia_ict_ob.md, seccion "Verificacion de precision").
//
// IMPORTANTE — LEER ANTES DE USAR:
//   - Disenado y probado SOLO para 15 minutos. No es valido en otro TF.
//   - Requiere backtest/paper-trading en NinjaTrader (Sim) antes de asumir
//     que replica exactamente los mismos resultados que el motor Python,
//     por diferencias de modelo de ejecucion propias de cada plataforma.
//   - default_qty = 3 contratos (2 cierran en TP1, 1 en TP2/BE). Ajustable
//     abajo en Qty si se usan mas/menos contratos.
//   - Comision y slippage: configurar en las propiedades de la estrategia
//     dentro de NinjaTrader (Data Series / Strategy properties), no aqui.
// ============================================================================

namespace NinjaTrader.NinjaScript.Strategies
{
    public class ICTOBStrategy : Strategy
    {
        // ---------------- Parametros (identicos al Pine v15) ----------------
        [NinjaScriptProperty]
        [Display(Name = "Filtro de sesion (18:00-11:00 NY)", GroupName = "Parametros", Order = 1)]
        public bool UseSessionFilter { get; set; } = true;

        [NinjaScriptProperty]
        [Display(Name = "Avg-range lookback", GroupName = "Parametros", Order = 2)]
        public int DispLen { get; set; } = 20;

        [NinjaScriptProperty]
        [Display(Name = "Displacement threshold", GroupName = "Parametros", Order = 3)]
        public double DispMult { get; set; } = 2.5;

        [NinjaScriptProperty]
        [Display(Name = "Min close fraction", GroupName = "Parametros", Order = 4)]
        public double DispCloseFrac { get; set; } = 0.6;

        [NinjaScriptProperty]
        [Display(Name = "Max bars back to find OB candle", GroupName = "Parametros", Order = 5)]
        public int ObScanBars { get; set; } = 10;

        [NinjaScriptProperty]
        [Display(Name = "Liquidity lookback", GroupName = "Parametros", Order = 6)]
        public int LiqCheckBars { get; set; } = 12;

        [NinjaScriptProperty]
        [Display(Name = "Liquidity tolerance (pts)", GroupName = "Parametros", Order = 7)]
        public double LiqTolerancePts { get; set; } = 4.0;

        [NinjaScriptProperty]
        [Display(Name = "Min consecutive bars = dirty", GroupName = "Parametros", Order = 8)]
        public int LiqAccumBars { get; set; } = 6;

        [NinjaScriptProperty]
        [Display(Name = "Zone max age (bars)", GroupName = "Parametros", Order = 9)]
        public int ZoneMaxAge { get; set; } = 300;

        [NinjaScriptProperty]
        [Display(Name = "Max zonas vivas simultaneas", GroupName = "Parametros", Order = 10)]
        public int MaxZones { get; set; } = 40;

        [NinjaScriptProperty]
        [Display(Name = "SL buffer (pts)", GroupName = "Parametros", Order = 11)]
        public double SlBufferPts { get; set; } = 2.0;

        [NinjaScriptProperty]
        [Display(Name = "Entry buffer (pts)", GroupName = "Parametros", Order = 12)]
        public double EntryBufferPts { get; set; } = 12.0;

        [NinjaScriptProperty]
        [Display(Name = "TP1 R multiple (2 contratos)", GroupName = "Parametros", Order = 13)]
        public double Rr1 { get; set; } = 1.8;

        [NinjaScriptProperty]
        [Display(Name = "TP2 R multiple (1 contrato)", GroupName = "Parametros", Order = 14)]
        public double Rr2 { get; set; } = 4.0;

        [NinjaScriptProperty]
        [Display(Name = "Usar tope de riesgo", GroupName = "Parametros", Order = 15)]
        public bool UseRiskCap { get; set; } = true;

        [NinjaScriptProperty]
        [Display(Name = "Tope maximo de riesgo (pts)", GroupName = "Parametros", Order = 16)]
        public double MaxRiskPts { get; set; } = 100.0;

        [NinjaScriptProperty]
        [Display(Name = "BE trigger (R)", GroupName = "Parametros", Order = 17)]
        public double BeTriggerR { get; set; } = 1.2;

        [NinjaScriptProperty]
        [Display(Name = "Lock R (ganancia asegurada)", GroupName = "Parametros", Order = 18)]
        public double LockR { get; set; } = 0.8;

        [NinjaScriptProperty]
        [Display(Name = "Contratos por operacion", GroupName = "Parametros", Order = 19)]
        public int Qty { get; set; } = 3;

        [NinjaScriptProperty]
        [Display(Name = "Contratos que cierran en TP1", GroupName = "Parametros", Order = 20)]
        public int Tp1Qty { get; set; } = 2;

        // ---------------- Estado interno: zonas OB vivas ----------------
        private class Zone
        {
            public int Dir;         // 1 = bull, -1 = bear
            public double Top;
            public double Bot;
            public bool Cleared;
            public int Born;        // CurrentBar en el que se formo
        }

        private List<Zone> zones = new List<Zone>();

        // ---------------- Estado de la operacion abierta ----------------
        private bool tradeOpen = false;
        private int dir = 0;
        private double entryPrice;
        private double activeSL;
        private double riskPts;
        private bool tp1Hit = false;
        private bool beMoved = false;

        // series auxiliar para el promedio de rango (equivalente a ta.sma(high-low, DispLen))
        private SMA avgRangeSeries;
        private Series<double> rangeSeries;

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = "ICT 15M OB Entry - puerto de v15 multi-zona (Pine)";
                Name = "ICTOBStrategy";
                Calculate = Calculate.OnBarClose;   // IMPORTANTE: igual que process_orders_on_close en Pine
                EntriesPerDirection = 1;
                EntryHandling = EntryHandling.AllEntries;
                IsExitOnSessionCloseStrategy = false;
                IsFillLimitOnTouch = false;
                MaximumBarsLookBack = MaximumBarsLookBack.TwoHundredFiftySix;
                OrderFillResolution = OrderFillResolution.Standard;
                Slippage = 1; // en ticks, ajustar segun el instrumento
                StartBehavior = StartBehavior.WaitUntilFlat;
                TimeInForce = TimeInForce.Gtc;
                TraceOrders = false;
                RealtimeErrorHandling = RealtimeErrorHandling.StopCancelClose;
                StopTargetHandling = StopTargetHandling.PerEntryExecution;
                BarsRequiredToTrade = 30;
                IsInstantiatedOnEachOptimizationIteration = true;
            }
            else if (State == State.Configure)
            {
                rangeSeries = new Series<double>(this);
            }
            else if (State == State.DataLoaded)
            {
                avgRangeSeries = SMA(rangeSeries, DispLen);
            }
        }

        protected override void OnBarUpdate()
        {
            if (CurrentBar < BarsRequiredToTrade) return;

            // ---- rango de la barra actual, usado por el SMA ----
            rangeSeries[0] = High[0] - Low[0];

            if (CurrentBar < DispLen) return;

            double avgRangePrev = avgRangeSeries[1]; // excluye la barra actual, igual que avgRange[1] en Pine
            double rng = High[0] - Low[0];
            bool isDisp = rng >= DispMult * avgRangePrev;
            bool bullDisp = isDisp && Close[0] > Open[0] && (Close[0] - Low[0]) >= DispCloseFrac * rng;
            bool bearDisp = isDisp && Close[0] < Open[0] && (High[0] - Close[0]) >= DispCloseFrac * rng;

            // ---------------- 1) formar zonas nuevas ----------------
            if (bullDisp)
            {
                int idx = -1;
                for (int k = 1; k <= ObScanBars; k++)
                {
                    if (CurrentBar - k < 0) break;
                    if (Close[k] < Open[k]) { idx = k; break; }
                }
                if (idx != -1)
                {
                    double candBot = Low[idx];
                    int maxStreak = 0, curStreak = 0;
                    for (int k = idx + 1; k <= idx + LiqCheckBars; k++)
                    {
                        if (CurrentBar - k < 0) break;
                        if (Low[k] <= candBot + LiqTolerancePts) { curStreak++; maxStreak = Math.Max(maxStreak, curStreak); }
                        else curStreak = 0;
                    }
                    if (maxStreak < LiqAccumBars)
                        zones.Add(new Zone { Dir = 1, Top = High[idx], Bot = candBot, Cleared = false, Born = CurrentBar });
                }
            }

            if (bearDisp)
            {
                int idx2 = -1;
                for (int k = 1; k <= ObScanBars; k++)
                {
                    if (CurrentBar - k < 0) break;
                    if (Close[k] > Open[k]) { idx2 = k; break; }
                }
                if (idx2 != -1)
                {
                    double candTop = High[idx2];
                    int maxStreak2 = 0, curStreak2 = 0;
                    for (int k = idx2 + 1; k <= idx2 + LiqCheckBars; k++)
                    {
                        if (CurrentBar - k < 0) break;
                        if (High[k] >= candTop - LiqTolerancePts) { curStreak2++; maxStreak2 = Math.Max(maxStreak2, curStreak2); }
                        else curStreak2 = 0;
                    }
                    if (maxStreak2 < LiqAccumBars)
                        zones.Add(new Zone { Dir = -1, Top = candTop, Bot = Low[idx2], Cleared = false, Born = CurrentBar });
                }
            }

            if (zones.Count > MaxZones)
                zones.RemoveRange(0, zones.Count - MaxZones);

            // ---------------- 2) actualizar cleared ----------------
            foreach (var z in zones)
            {
                if (z.Born != CurrentBar && !z.Cleared)
                {
                    if (z.Dir == 1 && Low[0] > z.Top) z.Cleared = true;
                    else if (z.Dir == -1 && High[0] < z.Bot) z.Cleared = true;
                }
            }

            // ---------------- 3) sesion / fecha ----------------
            bool inSession = true;
            if (UseSessionFilter)
            {
                DateTime nyTime = TimeZoneInfo.ConvertTime(Time[0], TimeZoneInfo.Utc,
                    TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time"));
                int minOfDay = nyTime.Hour * 60 + nyTime.Minute;
                inSession = (minOfDay >= 1080 || minOfDay < 660); // 18:00-11:00 NY
            }
            bool canEnter = inSession && !tradeOpen && Position.MarketPosition == MarketPosition.Flat;

            // ---------------- 4) buscar candidata (zona mas reciente) ----------------
            double candEntry = 0, candSL = 0, candRisk = 0;
            int candDir = 0, candBorn = -1;

            if (canEnter)
            {
                foreach (var z in zones)
                {
                    if (z.Born == CurrentBar || !z.Cleared) continue;
                    if ((CurrentBar - z.Born) > ZoneMaxAge) continue;

                    if (z.Dir == 1 && Low[0] <= z.Top + EntryBufferPts && Low[0] >= z.Bot)
                    {
                        double e = Math.Max(Low[0], z.Top);
                        double x = z.Bot - SlBufferPts;
                        double r = e - x;
                        if (r > 0 && (!UseRiskCap || r <= MaxRiskPts) && z.Born > candBorn)
                        {
                            candEntry = e; candSL = x; candRisk = r; candDir = 1; candBorn = z.Born;
                        }
                    }
                    if (z.Dir == -1 && High[0] >= z.Bot - EntryBufferPts && High[0] <= z.Top)
                    {
                        double e2 = Math.Min(High[0], z.Bot);
                        double x2 = z.Top + SlBufferPts;
                        double r2 = x2 - e2;
                        if (r2 > 0 && (!UseRiskCap || r2 <= MaxRiskPts) && z.Born > candBorn)
                        {
                            candEntry = e2; candSL = x2; candRisk = r2; candDir = -1; candBorn = z.Born;
                        }
                    }
                }
            }

            // ---------------- 5) retirar zonas caducadas/consumidas ----------------
            zones.RemoveAll(z =>
            {
                bool expired = (CurrentBar - z.Born) > ZoneMaxAge;
                bool consumed = z.Born != CurrentBar && z.Cleared &&
                    ((z.Dir == 1 && Low[0] <= z.Top) || (z.Dir == -1 && High[0] >= z.Bot));
                return expired || consumed;
            });

            // ---------------- 6) entrada ----------------
            if (canEnter && candDir != 0)
            {
                entryPrice = candEntry;
                activeSL = candSL;
                riskPts = candRisk;
                tp1Hit = false;
                beMoved = false;
                tradeOpen = true;
                dir = candDir;

                if (dir == 1)
                    EnterLong(Qty, "ICTOB-L");
                else
                    EnterShort(Qty, "ICTOB-S");
            }

            // ---------------- 7) gestion de la posicion abierta ----------------
            if (tradeOpen && dir == 1 && Position.MarketPosition == MarketPosition.Long)
            {
                double tp1 = entryPrice + riskPts * Rr1;
                double tp2 = entryPrice + riskPts * Rr2;
                double reachedR = (High[0] - entryPrice) / riskPts;

                if (!tp1Hit)
                {
                    tp1Hit = High[0] >= tp1;
                }

                if (tp1Hit && Position.Quantity == Qty)
                {
                    // TP1 se acaba de tocar: cerrar Tp1Qty contratos, mover SL del resto
                    beMoved = true;
                    activeSL = Math.Max(activeSL, entryPrice + riskPts * LockR);
                    ExitLongLimit(Tp1Qty, tp1, "ICTOB-L");
                }
                else if (BeTriggerR > 0 && !beMoved && reachedR >= BeTriggerR)
                {
                    beMoved = true;
                    activeSL = entryPrice + riskPts * LockR;
                }

                // salidas: SL siempre activo, TP2 solo para el remanente tras TP1
                SetStopLoss("ICTOB-L", CalculationMode.Price, activeSL, false);
                if (Position.Quantity < Qty) // ya se cerro parte en TP1, queda el corredor
                    ExitLongLimit(0, true, Position.Quantity, tp2, "TP2", "ICTOB-L");

                if (Low[0] <= activeSL)
                {
                    tradeOpen = false;
                }
            }
            else if (tradeOpen && dir == -1 && Position.MarketPosition == MarketPosition.Short)
            {
                double tp1 = entryPrice - riskPts * Rr1;
                double tp2 = entryPrice - riskPts * Rr2;
                double reachedR = (entryPrice - Low[0]) / riskPts;

                if (!tp1Hit)
                {
                    tp1Hit = Low[0] <= tp1;
                }

                if (tp1Hit && Position.Quantity == Qty)
                {
                    beMoved = true;
                    activeSL = Math.Min(activeSL, entryPrice - riskPts * LockR);
                    ExitShortLimit(Tp1Qty, tp1, "ICTOB-S");
                }
                else if (BeTriggerR > 0 && !beMoved && reachedR >= BeTriggerR)
                {
                    beMoved = true;
                    activeSL = entryPrice - riskPts * LockR;
                }

                SetStopLoss("ICTOB-S", CalculationMode.Price, activeSL, false);
                if (Position.Quantity < Qty)
                    ExitShortLimit(0, true, Position.Quantity, tp2, "TP2", "ICTOB-S");

                if (High[0] >= activeSL)
                {
                    tradeOpen = false;
                }
            }
        }

        protected override void OnExecutionUpdate(Execution execution, string executionId, double price,
            int quantity, MarketPosition marketPosition, string orderId, DateTime time)
        {
            if (Position.MarketPosition == MarketPosition.Flat)
            {
                tradeOpen = false;
                tp1Hit = false;
                beMoved = false;
            }
        }
    }
}

/* ============================================================================
NOTAS DE INSTALACION:

1. Copiar este archivo dentro de NinjaTrader: Tools -> Edit NinjaScript ->
   Strategy -> New -> pegar este codigo (o copiar el .cs directo a
   Documents\NinjaTrader 8\bin\Custom\Strategies\ y compilar con F5 dentro
   del editor de NinjaScript).

2. Aplicar la estrategia a un chart de MNQ en 15 minutos (Strategies -> Add
   -> ICTOBStrategy), en la cuenta Sim de Lucid.

3. PROBAR PRIMERO EN MODO "DISABLED" leyendo el Output window / Strategy
   Performance report varios dias, comparando manualmente contra lo que
   marca el indicador visual "ICT 15M OB Alertas" en TradingView, antes de
   habilitarla para ejecutar ordenes reales (aunque sea en Sim).

4. Este puerto NO ha sido probado en NinjaTrader todavia (solo el motor
   Python fue validado contra datos reales de TradingView). Es el PRIMER
   PASO de la migracion, no un producto terminado — esperar diferencias de
   comportamiento entre el modelo de ordenes de NinjaTrader y el de Pine/
   Python (ej. como NinjaTrader maneja stops y limits simultaneos con
   SetStopLoss + ExitLimit) y ajustar segun lo que se observe en Sim.
============================================================================ */
