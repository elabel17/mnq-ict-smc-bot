// ============================================================
// ICT 15M OB Entry v18 - dual-sesion + sesgo 1H (NinjaScript / NinjaTrader 8)
//
// Puerto a NinjaScript de la logica validada en Pine v18 (2026-09-09):
//   - Deteccion de Order Blocks por desplazamiento + filtro de liquidez,
//     con DOS regimenes de parametros independientes (manana / noche).
//   - Entrada CAUSAL (nunca usa el high/low final de la vela para decidir
//     el precio de entrada -- solo niveles fijos conocidos de antemano).
//   - Filtro de sesgo de 1H: solo largos si el precio de 1H esta sobre su
//     propia SMA, solo cortos si esta debajo (request.security -> AddDataSeries).
//   - Sin cierre parcial en TP1 (se valido estadisticamente que dejar
//     correr el 100% hasta TP2 es mas rentable en todos los escenarios
//     probados) -- TP1 no se usa para nada operativo, solo queda el TP2.
//   - Break-even anticipado: al alcanzar BeTriggerR se mueve el stop a
//     asegurar LockR (no es breakeven puro).
//   - Fix de causalidad: nunca gestiona SL/TP en la misma barra en que se
//     abrio la operacion.
//
// DIFERENCIA DELIBERADA respecto al backtest de Python/Pine: en el
// backtest, manana y noche se simularon como DOS BACKTESTS INDEPENDIENTES
// (podian, en teoria, tener una operacion "abierta" simultaneamente sin
// bloquearse entre si). En NinjaTrader solo existe UNA posicion real por
// instrumento -- este script usa un unico estado de posicion compartido:
// una operacion de la sesion nocturna que siga abierta bloquea nuevas
// entradas (de cualquier sesion) hasta que se cierre. Es la version
// correcta para dinero real, y es una simplificacion conservadora (nunca
// arriesga mas de 1 operacion a la vez).
//
// ESTADO: PRIMER BORRADOR, SIN TESTEAR. Validar exhaustivamente en Sim
// antes de arriesgar la cuenta real o fondeada. En particular verificar:
//   - Que SetStopLoss/SetProfitTarget interactuan como se espera con las
//     modificaciones manuales de stop al activarse el break-even.
//   - Que el filtro de sesion NY (TimeZoneInfo) calcula correctamente el
//     horario de verano/invierno en el servidor donde corra esto.
//   - Comisiones/slippage reales de tu broker (el backtest asumio 1 tick
//     de slippage y $0.47/contrato/lado -- NO verificado contra ejecucion
//     real).
// ============================================================

#region Using declarations
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using NinjaTrader.Cbi;
using NinjaTrader.Gui.Tools;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.Strategies;
#endregion

namespace NinjaTrader.NinjaScript.Strategies
{
    public class ICTOBStrategyV18 : Strategy
    {
        // ---------------- Zona OB (equivalente al "type Zone" de Pine) ----------------
        private class Zone
        {
            public int Dir;          // 1 = alcista (long), -1 = bajista (short)
            public double Top;
            public double Bot;
            public bool Cleared;
            public int BornBar;
        }

        // ---------------- Parametros comunes de deteccion ----------------
        [NinjaScriptProperty]
        [Display(Name = "Barras rango promedio (DispLen)", GroupName = "1. Deteccion comun", Order = 1)]
        public int DispLen { get; set; } = 20;

        [NinjaScriptProperty]
        [Display(Name = "Umbral desplazamiento (DispMult)", GroupName = "1. Deteccion comun", Order = 2)]
        public double DispMult { get; set; } = 2.5;

        [NinjaScriptProperty]
        [Display(Name = "Fraccion cierre direccional (DispCloseFrac)", GroupName = "1. Deteccion comun", Order = 3)]
        public double DispCloseFrac { get; set; } = 0.6;

        [NinjaScriptProperty]
        [Display(Name = "Barras scan vela origen (ObScanBars)", GroupName = "1. Deteccion comun", Order = 4)]
        public int ObScanBars { get; set; } = 10;

        [NinjaScriptProperty]
        [Display(Name = "Ventana chequeo liquidez (LiqCheckBars)", GroupName = "1. Deteccion comun", Order = 5)]
        public int LiqCheckBars { get; set; } = 12;

        [NinjaScriptProperty]
        [Display(Name = "Edad maxima de zona (barras 15m)", GroupName = "1. Deteccion comun", Order = 6)]
        public int ZoneMaxAge { get; set; } = 300;

        [NinjaScriptProperty]
        [Display(Name = "Maximo zonas vivas por regimen", GroupName = "1. Deteccion comun", Order = 7)]
        public int MaxZones { get; set; } = 40;

        [NinjaScriptProperty]
        [Display(Name = "RR1 (referencia visual, no cierra nada)", GroupName = "1. Deteccion comun", Order = 8)]
        public double RR1 { get; set; } = 1.8;

        [NinjaScriptProperty]
        [Display(Name = "Usar tope de riesgo maximo", GroupName = "1. Deteccion comun", Order = 9)]
        public bool UseRiskCap { get; set; } = true;

        [NinjaScriptProperty]
        [Display(Name = "Tope maximo de riesgo (pts)", GroupName = "1. Deteccion comun", Order = 10)]
        public double MaxRiskPts { get; set; } = 100.0;

        // ---------------- Sesgo de 1H ----------------
        [NinjaScriptProperty]
        [Display(Name = "Aplicar filtro de sesgo 1H", GroupName = "2. Sesgo 1H", Order = 1)]
        public bool Use1hBias { get; set; } = true;

        [NinjaScriptProperty]
        [Display(Name = "Largo SMA de 1H", GroupName = "2. Sesgo 1H", Order = 2)]
        public int BiasSmaLen { get; set; } = 10;

        // ---------------- Regimen MANANA (03:00-11:00 NY) ----------------
        [NinjaScriptProperty]
        [Display(Name = "[M] Tolerancia liquidez (pts)", GroupName = "3. Manana 03-11 NY", Order = 1)]
        public double MLiqTolerancePts { get; set; } = 4.0;

        [NinjaScriptProperty]
        [Display(Name = "[M] Racha invalida liquidez", GroupName = "3. Manana 03-11 NY", Order = 2)]
        public int MLiqAccumBars { get; set; } = 6;

        [NinjaScriptProperty]
        [Display(Name = "[M] Buffer SL (pts)", GroupName = "3. Manana 03-11 NY", Order = 3)]
        public double MSlBufferPts { get; set; } = 2.0;

        [NinjaScriptProperty]
        [Display(Name = "[M] Margen entrada (pts)", GroupName = "3. Manana 03-11 NY", Order = 4)]
        public double MEntryBufferPts { get; set; } = 12.0;

        [NinjaScriptProperty]
        [Display(Name = "[M] TP2 (multiplo R)", GroupName = "3. Manana 03-11 NY", Order = 5)]
        public double MRR2 { get; set; } = 6.0;

        [NinjaScriptProperty]
        [Display(Name = "[M] Gatillo BE (multiplo R)", GroupName = "3. Manana 03-11 NY", Order = 6)]
        public double MBeTriggerR { get; set; } = 1.2;

        [NinjaScriptProperty]
        [Display(Name = "[M] Lock BE (multiplo R)", GroupName = "3. Manana 03-11 NY", Order = 7)]
        public double MLockR { get; set; } = 1.0;

        // ---------------- Regimen NOCHE (18:00-00:00 NY) ----------------
        [NinjaScriptProperty]
        [Display(Name = "[N] Tolerancia liquidez (pts)", GroupName = "4. Noche 18-00 NY", Order = 1)]
        public double NLiqTolerancePts { get; set; } = 2.0;

        [NinjaScriptProperty]
        [Display(Name = "[N] Racha invalida liquidez", GroupName = "4. Noche 18-00 NY", Order = 2)]
        public int NLiqAccumBars { get; set; } = 15;

        [NinjaScriptProperty]
        [Display(Name = "[N] Buffer SL (pts)", GroupName = "4. Noche 18-00 NY", Order = 3)]
        public double NSlBufferPts { get; set; } = 1.0;

        [NinjaScriptProperty]
        [Display(Name = "[N] Margen entrada (pts)", GroupName = "4. Noche 18-00 NY", Order = 4)]
        public double NEntryBufferPts { get; set; } = 8.0;

        [NinjaScriptProperty]
        [Display(Name = "[N] TP2 (multiplo R)", GroupName = "4. Noche 18-00 NY", Order = 5)]
        public double NRR2 { get; set; } = 7.0;

        [NinjaScriptProperty]
        [Display(Name = "[N] Gatillo BE (multiplo R)", GroupName = "4. Noche 18-00 NY", Order = 6)]
        public double NBeTriggerR { get; set; } = 0.8;

        [NinjaScriptProperty]
        [Display(Name = "[N] Lock BE (multiplo R)", GroupName = "4. Noche 18-00 NY", Order = 7)]
        public double NLockR { get; set; } = 0.3;

        // ---------------- Ejecucion ----------------
        [NinjaScriptProperty]
        [Display(Name = "Contratos por operacion", GroupName = "5. Ejecucion", Order = 1)]
        public int Contracts { get; set; } = 4;

        // ---------------- Estado interno ----------------
        private List<Zone> zonesM = new List<Zone>();
        private List<Zone> zonesN = new List<Zone>();

        private double[] avgRangeCache;
        private int barCount = 0;

        // Serie de 1H para el sesgo (BarsArray[1])
        private int h1Bias = 0; // +1 alcista, -1 bajista, 0 sin datos suficientes

        // Estado de la operacion (UNICO -- ver nota de diferencia deliberada arriba)
        private bool tradeOpen = false;
        private int tradeDir = 0;           // 1 long, -1 short
        private double entryPriceRef = 0;   // precio de entrada objetivo (causal)
        private double activeSL = 0;
        private double riskPts = 0;
        private bool beMoved = false;
        private int entryBarIdx = -1;
        private string regimeOfOpenTrade = ""; // "M" o "N", para saber que RR2/BE usar
        private double activeRR2 = 0;
        private double activeLockR = 0;
        private double activeBeTrigger = 0;

        private TimeZoneInfo nyTz;

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = "ICT 15M OB Entry v18 - dual-sesion + sesgo 1H (puerto de Pine, SIN TESTEAR)";
                Name = "ICTOBStrategyV18";
                Calculate = Calculate.OnBarClose;
                EntriesPerDirection = 1;
                EntryHandling = EntryHandling.AllEntries;
                IsExitOnSessionCloseStrategy = false;
                ExitOnSessionCloseSeconds = 30;
                IsFillLimitOnTouch = false;
                MaximumBarsLookBack = MaximumBarsLookBack.TwoHundredFiftySix;
                OrderFillResolution = OrderFillResolution.Standard;
                Slippage = 1; // ticks, ajustar a tu broker real
                StartBehavior = StartBehavior.WaitUntilFlat;
                TimeInForce = TimeInForce.Gtc;
                TraceOrders = false;
                RealtimeErrorHandling = RealtimeErrorHandling.StopCancelClose;
                StopTargetHandling = StopTargetHandling.PerEntryExecution;
                BarsRequiredToTrade = Math.Max(DispLen, ObScanBars + LiqCheckBars) + 5;
                IsInstantiatedOnEachOptimizationIteration = true;
            }
            else if (State == State.Configure)
            {
                // Serie secundaria de 1H para el sesgo (equivalente a request.security "60")
                AddDataSeries(BarsPeriodType.Minute, 60);
            }
            else if (State == State.DataLoaded)
            {
                nyTz = TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time");
                avgRangeCache = new double[0];
            }
        }

        protected override void OnBarUpdate()
        {
            // ---------------- Actualizar sesgo de 1H (BIP 1) ----------------
            if (BarsInProgress == 1)
            {
                if (CurrentBars[1] >= BiasSmaLen - 1)
                {
                    double sma1h = SMA(Closes[1], BiasSmaLen)[0];
                    h1Bias = Closes[1][0] > sma1h ? 1 : (Closes[1][0] < sma1h ? -1 : 0);
                }
                return; // el resto de la logica corre solo en la serie principal (15m)
            }

            if (BarsInProgress != 0) return;
            if (CurrentBar < BarsRequiredToTrade) return;

            int i = CurrentBar;
            double o = Open[0], h = High[0], l = Low[0], c = Close[0];

            // ---------------- 1) Deteccion de desplazamiento (comun a ambos regimenes) ----------------
            double sumRange = 0;
            for (int k = 0; k < DispLen; k++)
                sumRange += High[1 + k] - Low[1 + k];
            double avgRangePrev = sumRange / DispLen; // avgRange[1] en terminos Pine (excluye la barra actual)

            double rng = h - l;
            bool isDisp = rng >= DispMult * avgRangePrev;
            bool bullDisp = isDisp && c > o && (c - l) >= DispCloseFrac * rng;
            bool bearDisp = isDisp && c < o && (h - c) >= DispCloseFrac * rng;

            // ---------------- 2) Formar zonas nuevas (una pasada por regimen) ----------------
            FormZones(bullDisp, bearDisp, MLiqTolerancePts, MLiqAccumBars, zonesM, i);
            FormZones(bullDisp, bearDisp, NLiqTolerancePts, NLiqAccumBars, zonesN, i);

            TrimZones(zonesM);
            TrimZones(zonesN);

            // ---------------- 3) Actualizar 'cleared' ----------------
            UpdateCleared(zonesM, i, h, l);
            UpdateCleared(zonesN, i, h, l);

            // ---------------- 4) Sesion NY actual ----------------
            DateTime nyNow = TimeZoneInfo.ConvertTime(Time[0], TimeZoneInfo.Local, nyTz);
            int nyMinOfDay = nyNow.Hour * 60 + nyNow.Minute;
            bool inMorning = nyMinOfDay >= 180 && nyMinOfDay < 660;   // 03:00-11:00 NY
            bool inNight = nyMinOfDay >= 1080;                        // 18:00-00:00 NY (no cruza medianoche en este calculo: 00:00-00:00 del dia siguiente ya es 0-179, cubierto por "not in window" -- ver nota abajo)
            // NOTA: 18:00-00:00 NY es sencillo (min_of_day >= 1080 hasta 23:59) porque no
            // cruza a el dia SIGUIENTE calendario dentro de la ventana (termina en medianoche
            // exacta). Si se quisiera extender pasada la medianoche, se necesitaria la logica
            // de "wrap" como en Pine (start>end). Con 18:00-00:00 no hace falta.

            bool canEnter = !tradeOpen;

            // ---------------- 5) Buscar candidata segun la sesion activa ----------------
            if (canEnter && inMorning)
                TryEnter(zonesM, i, h, l, MEntryBufferPts, MSlBufferPts, "M", MRR2, MBeTriggerR, MLockR);
            else if (canEnter && inNight)
                TryEnter(zonesN, i, h, l, NEntryBufferPts, NSlBufferPts, "N", NRR2, NBeTriggerR, NLockR);

            // ---------------- 6) Retirar zonas caducadas/consumidas ----------------
            PruneZones(zonesM, i, h, l);
            PruneZones(zonesN, i, h, l);

            // ---------------- 7) Gestion (unica, comun a la operacion abierta) ----------------
            ManageOpenTrade(i, h, l);
        }

        private void FormZones(bool bullDisp, bool bearDisp, double liqTolPts, int liqAccBars, List<Zone> zoneArr, int i)
        {
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
                        if (Low[j] <= candBot + liqTolPts) { curStreak++; maxStreak = Math.Max(maxStreak, curStreak); }
                        else curStreak = 0;
                    }
                    if (maxStreak < liqAccBars)
                        zoneArr.Add(new Zone { Dir = 1, Top = High[idx], Bot = candBot, Cleared = false, BornBar = i });
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
                        if (High[j] >= candTop - liqTolPts) { curStreak2++; maxStreak2 = Math.Max(maxStreak2, curStreak2); }
                        else curStreak2 = 0;
                    }
                    if (maxStreak2 < liqAccBars)
                        zoneArr.Add(new Zone { Dir = -1, Top = candTop, Bot = Low[idx2], Cleared = false, BornBar = i });
                }
            }
        }

        private void TrimZones(List<Zone> zoneArr)
        {
            while (zoneArr.Count > MaxZones)
                zoneArr.RemoveAt(0);
        }

        private void UpdateCleared(List<Zone> zoneArr, int i, double h, double l)
        {
            foreach (var z in zoneArr)
            {
                if (z.BornBar != i && !z.Cleared)
                {
                    if (z.Dir == 1 && l > z.Top) z.Cleared = true;
                    else if (z.Dir == -1 && h < z.Bot) z.Cleared = true;
                }
            }
        }

        private void PruneZones(List<Zone> zoneArr, int i, double h, double l)
        {
            for (int idx = zoneArr.Count - 1; idx >= 0; idx--)
            {
                var z = zoneArr[idx];
                bool expired = (i - z.BornBar) > ZoneMaxAge;
                bool consumed = z.BornBar != i && z.Cleared &&
                                 ((z.Dir == 1 && l <= z.Top) || (z.Dir == -1 && h >= z.Bot));
                if (expired || consumed)
                    zoneArr.RemoveAt(idx);
            }
        }

        // ---------------- Entrada CAUSAL: nunca usa el low/high final de la vela para fijar
        // el precio -- solo el borde puro del OB o el borde EXTERIOR fijo del margen, que son
        // niveles conocidos de antemano. En vivo esto se traduce en una orden LIMITE al nivel
        // causal (no una orden de mercado al "toque"). ----------------
        private void TryEnter(List<Zone> zoneArr, int i, double h, double l, double entryBufPts, double slBufPts,
                               string regime, double rr2, double beTrigger, double lockR)
        {
            double candEntry = 0, candSL = 0, candRisk = 0;
            int candDir = 0, candBorn = -1;

            foreach (var z in zoneArr)
            {
                if (z.BornBar == i || !z.Cleared) continue;
                if ((i - z.BornBar) > ZoneMaxAge) continue;

                if (z.Dir == 1 && l <= z.Top + entryBufPts && l >= z.Bot)
                {
                    if (!Use1hBias || h1Bias > 0)
                    {
                        double e = l <= z.Top ? z.Top : z.Top + entryBufPts;
                        double x = z.Bot - slBufPts;
                        double r = e - x;
                        if (r > 0 && (!UseRiskCap || r <= MaxRiskPts) && z.BornBar > candBorn)
                        {
                            candEntry = e; candSL = x; candRisk = r; candDir = 1; candBorn = z.BornBar;
                        }
                    }
                }
                if (z.Dir == -1 && h >= z.Bot - entryBufPts && h <= z.Top)
                {
                    if (!Use1hBias || h1Bias < 0)
                    {
                        double e2 = h >= z.Bot ? z.Bot : z.Bot - entryBufPts;
                        double x2 = z.Top + slBufPts;
                        double r2 = x2 - e2;
                        if (r2 > 0 && (!UseRiskCap || r2 <= MaxRiskPts) && z.BornBar > candBorn)
                        {
                            candEntry = e2; candSL = x2; candRisk = r2; candDir = -1; candBorn = z.BornBar;
                        }
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
            entryBarIdx = i;
            regimeOfOpenTrade = regime;
            activeRR2 = rr2;
            activeBeTrigger = beTrigger;
            activeLockR = lockR;

            // Entrada real: orden limite al precio causal (no market-on-touch).
            // Si el precio ya paso ese nivel en la misma barra de senal, NinjaTrader
            // rellenara al primer precio disponible en la siguiente barra -- coherente
            // con "no gestionar en la misma vela de entrada" (ver ManageOpenTrade).
            if (candDir == 1)
                EnterLongLimit(0, true, Contracts, candEntry, "OB_Long_" + regime);
            else
                EnterShortLimit(0, true, Contracts, candEntry, "OB_Short_" + regime);
        }

        private void ManageOpenTrade(int i, double h, double l)
        {
            if (!tradeOpen) return;
            if (Position.MarketPosition == MarketPosition.Flat)
            {
                // La orden limite de entrada nunca se lleno (precio se alejo) -> zona consumida,
                // liberar el estado para permitir la proxima señal.
                if (i > entryBarIdx + 1 && !HasEntryOrderPending())
                {
                    tradeOpen = false;
                }
                return;
            }

            bool justEntered = (i == entryBarIdx);
            if (justEntered) return; // FIX causal: no gestionar en la misma barra de la entrada

            double tp2 = tradeDir == 1
                ? entryPriceRef + riskPts * activeRR2
                : entryPriceRef - riskPts * activeRR2;

            if (tradeDir == 1)
            {
                bool hitSL = l <= activeSL;
                bool hitTP2 = h >= tp2;
                double reachedR = (h - entryPriceRef) / riskPts;

                if (hitSL)
                {
                    ExitLong(Contracts, "SL_" + regimeOfOpenTrade, "OB_Long_" + regimeOfOpenTrade);
                    tradeOpen = false;
                }
                else if (hitTP2)
                {
                    ExitLong(Contracts, "TP2_" + regimeOfOpenTrade, "OB_Long_" + regimeOfOpenTrade);
                    tradeOpen = false;
                }
                else if (activeBeTrigger > 0 && !beMoved && reachedR >= activeBeTrigger)
                {
                    beMoved = true;
                    activeSL = entryPriceRef + riskPts * activeLockR;
                }
            }
            else
            {
                bool hitSL = h >= activeSL;
                bool hitTP2 = l <= tp2;
                double reachedR = (entryPriceRef - l) / riskPts;

                if (hitSL)
                {
                    ExitShort(Contracts, "SL_" + regimeOfOpenTrade, "OB_Short_" + regimeOfOpenTrade);
                    tradeOpen = false;
                }
                else if (hitTP2)
                {
                    ExitShort(Contracts, "TP2_" + regimeOfOpenTrade, "OB_Short_" + regimeOfOpenTrade);
                    tradeOpen = false;
                }
                else if (activeBeTrigger > 0 && !beMoved && reachedR >= activeBeTrigger)
                {
                    beMoved = true;
                    activeSL = entryPriceRef - riskPts * activeLockR;
                }
            }

            // Sincronizar el stop real con NinjaTrader (se re-emite cada barra tras BE;
            // NinjaTrader ignora si el nivel no cambio).
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
