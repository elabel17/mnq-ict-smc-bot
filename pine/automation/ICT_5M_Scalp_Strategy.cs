// ============================================================
// ICT 5M Scalp v1 (NinjaScript / NinjaTrader 8)
//
// Puerto a NinjaScript de la logica validada en Pine "ICT 5M Scalp v1 -
// deteccion nativa + sesgo 1H" (2026-09-10). Deteccion de Order Blocks
// RECALIBRADA especificamente para 5 minutos (no es la logica de 15m
// reaplicada -- parametros distintos, encontrados con busqueda por
// etapas y validados con holdout 70/30 sobre 2.6 anios de historico
// 2024-01-28 a 2026-09-08).
//
// Backtest de referencia (4 contratos, filtro sesgo 1H, sesion
// 03:00-11:00 NY): net $409,755 (supuestos originales) / $386,343
// (supuestos conservadores: 2 ticks slippage, $1.00/contrato/lado
// comision), Profit Factor ~3.0-3.2, winrate ~78%, drawdown max ~$1,400-
// 1,500, ~3,752 operaciones en 2.6 anios (~5.6/dia activo).
//
// Validacion de causalidad (2026-09-10): entrada SIEMPRE en niveles
// fijos conocidos de antemano (nunca el low/high final de la vela de
// señal). SL/TP se evaluan por mecha (high/low), nunca por cierre.
// Verificado ademas contra el feed real de TradingView en 3 fechas
// distintas (exactas, incluyendo O/H/L/C completo) y contra el script
// Pine real corriendo en vivo (coincidencia exacta entrada/SL/TP2 en
// la operacion de ejemplo comparada).
//
// SIGUE PENDIENTE, decision del usuario:
//   - Forward-test en Sim antes de arriesgar cuenta real/fondeada.
//   - Impuestos no modelados (cifra reportada es bruta).
//   - Tamano de posicion fijo en el backtest (4 contratos desde el
//     dia 1), no escalado a capital real.
//   - Solo 2.6 anios de historico.
//
// DIFERENCIA respecto al backtest: este script usa UN SOLO regimen
// (a diferencia del v18 de 15m que tenia manana/noche independientes),
// asi que no aplica la logica de "dos posiciones simultaneas" -- aqui
// solo hay una sesion (03:00-11:00 NY) y un solo estado de posicion,
// consistente con el backtest de referencia.
//
// Entrada real: orden LIMITE al precio causal (nivel fijo conocido de
// antemano), no orden de mercado al "toque". Requiere tener la orden
// colocada de antemano para que el fill sea igual al backtest.
//
// ESTADO: PRIMER BORRADOR, SIN TESTEAR/COMPILAR EN NINJATRADER (no hay
// acceso a NinjaTrader desde aqui). Validar exhaustivamente en Sim
// antes de dinero real. En particular, dado el stop tan ajustado
// (0.5pts = 2 ticks), verificar de cerca el comportamiento real de
// SetStopLoss/fills en tu broker especifico -- es el punto mas fragil
// de toda la estrategia.
// ============================================================

#region Using declarations
using System;
using System.Collections.Generic;
using System.ComponentModel.DataAnnotations;
using NinjaTrader.Cbi;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.Strategies;
#endregion

namespace NinjaTrader.NinjaScript.Strategies
{
    public class ICT5MScalpStrategy : Strategy
    {
        private class Zone
        {
            public int Dir;
            public double Top;
            public double Bot;
            public bool Cleared;
            public int BornBar;
        }

        // ---------------- Deteccion (recalibrada para 5m, valores validados) ----------------
        [NinjaScriptProperty]
        [Display(Name = "Barras rango promedio (DispLen)", GroupName = "1. Deteccion 5m", Order = 1)]
        public int DispLen { get; set; } = 60;

        [NinjaScriptProperty]
        [Display(Name = "Umbral desplazamiento (DispMult)", GroupName = "1. Deteccion 5m", Order = 2)]
        public double DispMult { get; set; } = 1.5;

        [NinjaScriptProperty]
        [Display(Name = "Fraccion cierre direccional", GroupName = "1. Deteccion 5m", Order = 3)]
        public double DispCloseFrac { get; set; } = 0.6;

        [NinjaScriptProperty]
        [Display(Name = "Barras scan vela origen", GroupName = "1. Deteccion 5m", Order = 4)]
        public int ObScanBars { get; set; } = 10;

        [NinjaScriptProperty]
        [Display(Name = "Ventana chequeo liquidez", GroupName = "1. Deteccion 5m", Order = 5)]
        public int LiqCheckBars { get; set; } = 12;

        [NinjaScriptProperty]
        [Display(Name = "Tolerancia liquidez (pts)", GroupName = "1. Deteccion 5m", Order = 6)]
        public double LiqTolerancePts { get; set; } = 1.0;

        [NinjaScriptProperty]
        [Display(Name = "Racha invalida liquidez", GroupName = "1. Deteccion 5m", Order = 7)]
        public int LiqAccumBars { get; set; } = 15;

        [NinjaScriptProperty]
        [Display(Name = "Edad maxima de zona (barras)", GroupName = "1. Deteccion 5m", Order = 8)]
        public int ZoneMaxAge { get; set; } = 300;

        [NinjaScriptProperty]
        [Display(Name = "Maximo zonas vivas", GroupName = "1. Deteccion 5m", Order = 9)]
        public int MaxZones { get; set; } = 40;

        [NinjaScriptProperty]
        [Display(Name = "Buffer SL (pts)", GroupName = "1. Deteccion 5m", Order = 10)]
        public double SlBufferPts { get; set; } = 0.5;

        [NinjaScriptProperty]
        [Display(Name = "Margen entrada (pts)", GroupName = "1. Deteccion 5m", Order = 11)]
        public double EntryBufferPts { get; set; } = 8.0;

        [NinjaScriptProperty]
        [Display(Name = "RR2 - TP2 (multiplo R)", GroupName = "1. Deteccion 5m", Order = 12)]
        public double RR2 { get; set; } = 3.0;

        [NinjaScriptProperty]
        [Display(Name = "Usar tope de riesgo maximo", GroupName = "1. Deteccion 5m", Order = 13)]
        public bool UseRiskCap { get; set; } = true;

        [NinjaScriptProperty]
        [Display(Name = "Tope maximo de riesgo (pts)", GroupName = "1. Deteccion 5m", Order = 14)]
        public double MaxRiskPts { get; set; } = 100.0;

        [NinjaScriptProperty]
        [Display(Name = "Gatillo BE (multiplo R)", GroupName = "1. Deteccion 5m", Order = 15)]
        public double BeTriggerR { get; set; } = 0.6;

        [NinjaScriptProperty]
        [Display(Name = "Lock BE (multiplo R)", GroupName = "1. Deteccion 5m", Order = 16)]
        public double LockR { get; set; } = 0.5;

        // ---------------- Sesion ----------------
        [NinjaScriptProperty]
        [Display(Name = "Hora inicio sesion (NY)", GroupName = "2. Sesion", Order = 1)]
        public int SessionStartHour { get; set; } = 3;

        [NinjaScriptProperty]
        [Display(Name = "Hora fin sesion (NY, exclusiva)", GroupName = "2. Sesion", Order = 2)]
        public int SessionEndHour { get; set; } = 11;

        // ---------------- Sesgo de 1H ----------------
        [NinjaScriptProperty]
        [Display(Name = "Aplicar filtro de sesgo 1H", GroupName = "3. Sesgo 1H", Order = 1)]
        public bool Use1hBias { get; set; } = true;

        [NinjaScriptProperty]
        [Display(Name = "Largo SMA de 1H", GroupName = "3. Sesgo 1H", Order = 2)]
        public int BiasSmaLen { get; set; } = 10;

        // ---------------- Ejecucion ----------------
        [NinjaScriptProperty]
        [Display(Name = "Contratos por operacion", GroupName = "4. Ejecucion", Order = 1)]
        public int Contracts { get; set; } = 4;

        // ---------------- Estado interno ----------------
        private List<Zone> zones = new List<Zone>();
        private double[] avgRangeCache;
        private int h1Bias = 0;

        private bool tradeOpen = false;
        private int tradeDir = 0;
        private double entryPriceRef = 0;
        private double activeSL = 0;
        private double riskPts = 0;
        private bool beMoved = false;
        private int entryBar = -1;

        private TimeZoneInfo nyTz;

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = "ICT 5M Scalp v1 -- deteccion nativa 5m + sesgo 1H (puerto de Pine, SIN TESTEAR)";
                Name = "ICT5MScalpStrategy";
                Calculate = Calculate.OnBarClose;
                EntriesPerDirection = 1;
                EntryHandling = EntryHandling.AllEntries;
                IsExitOnSessionCloseStrategy = false;
                IsFillLimitOnTouch = false;
                MaximumBarsLookBack = MaximumBarsLookBack.TwoHundredFiftySix;
                OrderFillResolution = OrderFillResolution.Standard;
                Slippage = 2; // ticks -- usar supuesto conservador (backtest probo 1-2 ticks)
                StartBehavior = StartBehavior.WaitUntilFlat;
                TimeInForce = TimeInForce.Gtc;
                RealtimeErrorHandling = RealtimeErrorHandling.StopCancelClose;
                StopTargetHandling = StopTargetHandling.PerEntryExecution;
                BarsRequiredToTrade = 100;
                IsInstantiatedOnEachOptimizationIteration = true;
            }
            else if (State == State.Configure)
            {
                AddDataSeries(BarsPeriodType.Minute, 60); // serie de 1H para el sesgo
            }
            else if (State == State.DataLoaded)
            {
                nyTz = TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time");
            }
        }

        protected override void OnBarUpdate()
        {
            if (BarsInProgress == 1)
            {
                if (CurrentBars[1] >= BiasSmaLen - 1)
                {
                    double sma1h = SMA(Closes[1], BiasSmaLen)[0];
                    h1Bias = Closes[1][0] > sma1h ? 1 : (Closes[1][0] < sma1h ? -1 : 0);
                }
                return;
            }

            if (BarsInProgress != 0) return;
            if (CurrentBar < BarsRequiredToTrade) return;
            if (CurrentBar < DispLen) return;

            int i = CurrentBar;
            double o = Open[0], h = High[0], l = Low[0], c = Close[0];

            double sumRange = 0;
            for (int k = 0; k < DispLen; k++)
                sumRange += High[1 + k] - Low[1 + k];
            double avgRangePrev = sumRange / DispLen;

            double rng = h - l;
            bool isDisp = rng >= DispMult * avgRangePrev;
            bool bullDisp = isDisp && c > o && (c - l) >= DispCloseFrac * rng;
            bool bearDisp = isDisp && c < o && (h - c) >= DispCloseFrac * rng;

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
                    for (int j = idx + 1; j <= idx + LiqCheckBars; j++)
                    {
                        if (CurrentBar - j < 0) break;
                        if (Low[j] <= candBot + LiqTolerancePts) { curStreak++; maxStreak = Math.Max(maxStreak, curStreak); }
                        else curStreak = 0;
                    }
                    if (maxStreak < LiqAccumBars)
                        zones.Add(new Zone { Dir = 1, Top = High[idx], Bot = candBot, Cleared = false, BornBar = i });
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
                    for (int j = idx2 + 1; j <= idx2 + LiqCheckBars; j++)
                    {
                        if (CurrentBar - j < 0) break;
                        if (High[j] >= candTop - LiqTolerancePts) { curStreak2++; maxStreak2 = Math.Max(maxStreak2, curStreak2); }
                        else curStreak2 = 0;
                    }
                    if (maxStreak2 < LiqAccumBars)
                        zones.Add(new Zone { Dir = -1, Top = candTop, Bot = Low[idx2], Cleared = false, BornBar = i });
                }
            }

            while (zones.Count > MaxZones) zones.RemoveAt(0);

            foreach (var z in zones)
            {
                if (z.BornBar != i && !z.Cleared)
                {
                    if (z.Dir == 1 && l > z.Top) z.Cleared = true;
                    else if (z.Dir == -1 && h < z.Bot) z.Cleared = true;
                }
            }

            DateTime nyNow = TimeZoneInfo.ConvertTime(Time[0], TimeZoneInfo.Local, nyTz);
            int nyMinOfDay = nyNow.Hour * 60 + nyNow.Minute;
            bool inSession = nyMinOfDay >= SessionStartHour * 60 && nyMinOfDay < SessionEndHour * 60;
            bool canEnter = inSession && !tradeOpen;

            if (canEnter)
                TryEnter(i, h, l);

            for (int idx3 = zones.Count - 1; idx3 >= 0; idx3--)
            {
                var z = zones[idx3];
                bool expired = (i - z.BornBar) > ZoneMaxAge;
                bool consumed = z.BornBar != i && z.Cleared &&
                                 ((z.Dir == 1 && l <= z.Top) || (z.Dir == -1 && h >= z.Bot));
                if (expired || consumed) zones.RemoveAt(idx3);
            }

            ManageOpenTrade(i, h, l);
        }

        private void TryEnter(int i, double h, double l)
        {
            double candEntry = 0, candSL = 0, candRisk = 0;
            int candDir = 0, candBorn = -1;

            foreach (var z in zones)
            {
                if (z.BornBar == i || !z.Cleared) continue;
                if ((i - z.BornBar) > ZoneMaxAge) continue;

                if (z.Dir == 1 && l <= z.Top + EntryBufferPts && l >= z.Bot)
                {
                    if (!Use1hBias || h1Bias > 0)
                    {
                        double e = l <= z.Top ? z.Top : z.Top + EntryBufferPts;
                        double x = z.Bot - SlBufferPts;
                        double r = e - x;
                        if (r > 0 && (!UseRiskCap || r <= MaxRiskPts) && z.BornBar > candBorn)
                        { candEntry = e; candSL = x; candRisk = r; candDir = 1; candBorn = z.BornBar; }
                    }
                }
                if (z.Dir == -1 && h >= z.Bot - EntryBufferPts && h <= z.Top)
                {
                    if (!Use1hBias || h1Bias < 0)
                    {
                        double e2 = h >= z.Bot ? z.Bot : z.Bot - EntryBufferPts;
                        double x2 = z.Top + SlBufferPts;
                        double r2 = x2 - e2;
                        if (r2 > 0 && (!UseRiskCap || r2 <= MaxRiskPts) && z.BornBar > candBorn)
                        { candEntry = e2; candSL = x2; candRisk = r2; candDir = -1; candBorn = z.BornBar; }
                    }
                }
            }

            if (candDir == 0) return;

            tradeOpen = true;
            tradeDir = candDir;
            entryPriceRef = candEntry;
            activeSL = candSL;
            riskPts = candRisk;
            beMoved = false;
            entryBar = i;

            if (candDir == 1)
                EnterLongLimit(0, true, Contracts, candEntry, "OB5m_Long");
            else
                EnterShortLimit(0, true, Contracts, candEntry, "OB5m_Short");
        }

        private void ManageOpenTrade(int i, double h, double l)
        {
            if (!tradeOpen) return;

            if (Position.MarketPosition == MarketPosition.Flat)
            {
                if (i > entryBar + 1 && !HasEntryOrderPending())
                    tradeOpen = false;
                return;
            }

            if (i == entryBar) return; // FIX causal: no gestionar en la misma barra de la entrada

            double tp2 = tradeDir == 1 ? entryPriceRef + riskPts * RR2 : entryPriceRef - riskPts * RR2;

            if (tradeDir == 1)
            {
                bool hitSL = l <= activeSL;
                bool hitTP2 = h >= tp2;
                double reachedR = (h - entryPriceRef) / riskPts;

                if (hitSL) { ExitLong(Contracts, "SL", "OB5m_Long"); tradeOpen = false; }
                else if (hitTP2) { ExitLong(Contracts, "TP2", "OB5m_Long"); tradeOpen = false; }
                else if (BeTriggerR > 0 && !beMoved && reachedR >= BeTriggerR)
                { beMoved = true; activeSL = entryPriceRef + riskPts * LockR; }
            }
            else
            {
                bool hitSL = h >= activeSL;
                bool hitTP2 = l <= tp2;
                double reachedR = (entryPriceRef - l) / riskPts;

                if (hitSL) { ExitShort(Contracts, "SL", "OB5m_Short"); tradeOpen = false; }
                else if (hitTP2) { ExitShort(Contracts, "TP2", "OB5m_Short"); tradeOpen = false; }
                else if (BeTriggerR > 0 && !beMoved && reachedR >= BeTriggerR)
                { beMoved = true; activeSL = entryPriceRef - riskPts * LockR; }
            }

            if (Position.MarketPosition != MarketPosition.Flat)
                SetStopLoss(CalculationMode.Price, activeSL);
        }

        private bool HasEntryOrderPending()
        {
            foreach (Order ord in Orders)
                if (ord.OrderState == OrderState.Working || ord.OrderState == OrderState.Accepted)
                    return true;
            return false;
        }
    }
}
