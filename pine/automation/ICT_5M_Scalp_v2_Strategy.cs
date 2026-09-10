#region Using declarations
using System;
using System.Collections.Generic;
using System.ComponentModel.DataAnnotations;
using System.Globalization;
using System.IO;
using NinjaTrader.Cbi;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.Indicators;
using NinjaTrader.NinjaScript.Strategies;
#endregion

// ============================================================================
// ICT 5M Scalp v2 — NinjaScript
//
// Reescritura del puerto de 5m. Misma deteccion y gestion que el motor Python
// validado, pero con la ejecucion corregida.
//
// ------------------------- QUE CAMBIA FRENTE A v1 --------------------------
//
// 1) FILTRO DE SESGO DE 1H: DESACTIVADO por defecto.
//    El informe original le atribuia PF 3.02 y net $386.343. Se comprobo
//    (2026-09-10) que ese beneficio venia de un error de fechado: el sesgo de
//    la hora en curso se calculaba con el CIERRE de esa misma hora, es decir
//    informacion futura. Corregido el fechado, en el mismo motor:
//        con sesgo look-ahead : 3.752 ops, $386.343, PF 3.02, DD $1.483
//        con sesgo causal     : 3.697 ops, $217.733, PF 1.87, DD $2.745
//        SIN filtro           : 6.480 ops, $387.000, PF 1.89, DD $2.974
//    El filtro causal no mejora el PF (1.87 vs 1.89) y elimina la mitad de las
//    operaciones -> no aporta nada. Queda el parametro por si se quiere
//    reactivar, pero apagado por defecto.
//
// 2) ENTRADA POR ORDEN LIMITE COLOCADA POR ADELANTADO.
//    v1 detectaba el toque al cierre de vela y RECIEN entonces mandaba la
//    limite a ese nivel -- pero el precio ya habia estado ahi. Aqui la orden
//    se deja puesta mientras el precio todavia no ha llegado, que es lo que
//    el backtest asume.
//
// 3) SL Y TP2 SON ORDENES REALES (SetStopLoss / SetProfitTarget).
//    v1 solo comprobaba `h >= tp2` al cierre y salia a mercado -> salias al
//    cierre de la vela, no en el TP2. Con TP2 = 3R sobre un riesgo medio de
//    ~29 pts (87 puntos de objetivo) esa diferencia es grande.
//
// 4) EL RIESGO SE CALCULA CON EL FILL REAL, no con el precio pedido
//    (OnExecutionUpdate). Si el fill difiere, el stop sigue quedando bien.
//
// 5) ZONA HORARIA: v1 usaba TimeZoneInfo.Local. NinjaTrader entrega Time[0]
//    en la zona de VISUALIZACION de la plataforma, que no siempre coincide.
//    Aqui se usa Globals.GeneralOptions.TimeZoneInfo.
//
// 6) UN SOLO MECANISMO DE SALIDA (v1 mezclaba SetStopLoss con ExitLong).
//
// 7) LIMITES DE PERDIDA DIARIA Y TOTAL. El peor drawdown historico
//    ($2.974 con 4 contratos) ocurrio en 16 operaciones y 1,1 dias -- cabe
//    entero en una sola jornada. Un freno diario importa mas que el tamano.
//
// ---------------------------- NUMEROS DE REFERENCIA ------------------------
// Config por defecto (sin filtro 1H, 3 contratos, 2 ticks slippage,
// $1.00/contrato/lado), histórico 2024-01 a 2026-09 (2,6 anios):
//     Net $290.250   PF 1.89   Max DD $2.230   WR 70,8%   6.480 operaciones
//     0 meses negativos de 33 (~196 operaciones/mes suavizan la varianza)
// Probabilidad de +$3.000 antes de -$2.000 recorriendo la secuencia real:
//     99,8% con limite estatico / 97,2% con limite trailing, mediana 9,2 dias
// Son estadisticas IN-SAMPLE sobre el mismo historico: no son un pronostico.
//
// -------------------------------- ESTADO -----------------------------------
// NO PROBADO EN NINJATRADER. No ha ejecutado ni una orden. Correr en Sim y
// comparar contra las señales del script Pine antes de cualquier cuenta real.
// ============================================================================

namespace NinjaTrader.NinjaScript.Strategies
{
    public class ICT5MScalpV2Strategy : Strategy
    {
        // ---------------- Ejecucion ----------------
        [NinjaScriptProperty] [Display(Name="Contratos", Order=1, GroupName="1. Ejecucion")]
        public int Qty { get; set; }

        [NinjaScriptProperty] [Display(Name="Entrar en el borde del margen (si no, en el borde del OB)", Order=2, GroupName="1. Ejecucion")]
        public bool EntryAtBufferEdge { get; set; }

        // ---------------- Proteccion de cuenta ----------------
        [NinjaScriptProperty] [Display(Name="Limite de perdida diaria USD (0 = off)", Order=1, GroupName="2. Proteccion")]
        public double DailyLossLimit { get; set; }

        [NinjaScriptProperty] [Display(Name="Limite de perdida total USD (0 = off)", Order=2, GroupName="2. Proteccion")]
        public double TotalLossLimit { get; set; }

        [NinjaScriptProperty] [Display(Name="Detener al alcanzar esta ganancia USD (0 = off)", Order=3, GroupName="2. Proteccion")]
        public double ProfitTargetStop { get; set; }

        // ---------------- Deteccion (parametros 5m) ----------------
        [NinjaScriptProperty] [Display(Name="Barras rango promedio", Order=1, GroupName="3. Deteccion 5m")]
        public int DispLen { get; set; }
        [NinjaScriptProperty] [Display(Name="Umbral desplazamiento", Order=2, GroupName="3. Deteccion 5m")]
        public double DispMult { get; set; }
        [NinjaScriptProperty] [Display(Name="Fraccion cierre direccional", Order=3, GroupName="3. Deteccion 5m")]
        public double DispCloseFrac { get; set; }
        [NinjaScriptProperty] [Display(Name="Barras atras vela de origen", Order=4, GroupName="3. Deteccion 5m")]
        public int ObScanBars { get; set; }
        [NinjaScriptProperty] [Display(Name="Ventana liquidez", Order=5, GroupName="3. Deteccion 5m")]
        public int LiqCheckBars { get; set; }
        [NinjaScriptProperty] [Display(Name="Tolerancia liquidez (pts)", Order=6, GroupName="3. Deteccion 5m")]
        public double LiqTolerancePts { get; set; }
        [NinjaScriptProperty] [Display(Name="Racha que invalida liquidez", Order=7, GroupName="3. Deteccion 5m")]
        public int LiqAccumBars { get; set; }
        [NinjaScriptProperty] [Display(Name="Vida maxima de zona (velas)", Order=8, GroupName="3. Deteccion 5m")]
        public int ZoneMaxAge { get; set; }
        [NinjaScriptProperty] [Display(Name="Max zonas vivas", Order=9, GroupName="3. Deteccion 5m")]
        public int MaxZones { get; set; }
        [NinjaScriptProperty] [Display(Name="Buffer SL (pts)", Order=10, GroupName="3. Deteccion 5m")]
        public double SlBufferPts { get; set; }
        [NinjaScriptProperty] [Display(Name="Margen de entrada (pts)", Order=11, GroupName="3. Deteccion 5m")]
        public double EntryBufferPts { get; set; }
        [NinjaScriptProperty] [Display(Name="Usar tope de riesgo", Order=12, GroupName="3. Deteccion 5m")]
        public bool UseRiskCap { get; set; }
        [NinjaScriptProperty] [Display(Name="Tope de riesgo (pts)", Order=13, GroupName="3. Deteccion 5m")]
        public double MaxRiskPts { get; set; }

        // ---------------- Gestion ----------------
        [NinjaScriptProperty] [Display(Name="TP2 (multiplo R)", Order=1, GroupName="4. Gestion")]
        public double RR2 { get; set; }
        [NinjaScriptProperty] [Display(Name="Gatillo BE (multiplo R)", Order=2, GroupName="4. Gestion")]
        public double BeTriggerR { get; set; }
        [NinjaScriptProperty] [Display(Name="Ganancia asegurada (multiplo R)", Order=3, GroupName="4. Gestion")]
        public double LockR { get; set; }

        // ---------------- Sesion ----------------
        [NinjaScriptProperty] [Display(Name="Hora inicio (NY)", Order=1, GroupName="5. Sesion")]
        public int SessionStartHour { get; set; }
        [NinjaScriptProperty] [Display(Name="Hora fin (NY, exclusiva)", Order=2, GroupName="5. Sesion")]
        public int SessionEndHour { get; set; }

        // ---------------- Sesgo 1H (apagado: ver cabecera) ----------------
        [NinjaScriptProperty] [Display(Name="Aplicar sesgo de 1H (no recomendado, ver cabecera)", Order=1, GroupName="6. Sesgo 1H")]
        public bool Use1hBias { get; set; }
        [NinjaScriptProperty] [Display(Name="Largo SMA de 1H", Order=2, GroupName="6. Sesgo 1H")]
        public int BiasSmaLen { get; set; }

        // ---------------- Registro para verificacion ----------------
        [NinjaScriptProperty] [Display(Name="Escribir CSV de verificacion", Order=1, GroupName="7. Registro")]
        public bool WriteCsvLog { get; set; }

        [NinjaScriptProperty] [Display(Name="Carpeta del CSV", Order=2, GroupName="7. Registro")]
        public string CsvFolder { get; set; }

        // ---------------- Estado ----------------
        private class Zone
        {
            public int Dir; public double Top; public double Bot;
            public bool Cleared; public int Born;
        }
        private List<Zone> zones = new List<Zone>();

        private SMA avgRange, bias1hSma;
        private Series<double> rangeSeries;
        private TimeZoneInfo nyTz;

        private double fillPrice, riskPts, activeStop, plannedStop;
        private int    plannedDir, entryBar = -1;
        private bool   beMoved, inPosition;

        private Order  pendingEntry = null;
        private double pendingLevel = 0, pendingStop = 0;
        private int    pendingDir = 0;
        private double pendingLevelPrev = 0;   // para no repetir la linea de log cada vela
        private int    pendingDirPrev = 0;

        private double dayStartPnL = 0;
        private DateTime currentDay = DateTime.MinValue;
        private bool haltToday = false, haltTotal = false;

        // ---------------- Registro CSV ----------------
        private StreamWriter csv = null;
        private static readonly CultureInfo INV = CultureInfo.InvariantCulture;

        // Una linea por evento. El objetivo es poder comparar, fuera de
        // NinjaTrader, cada operacion contra el motor Python de referencia.
        private void Log(string evento, string dirTxt, double px, double stop,
                         double risk, double target, string nota)
        {
            if (csv == null) return;
            try
            {
                DateTime ny = NyTime(Time[0]);
                csv.WriteLine(string.Join(";", new string[] {
                    Time[0].ToString("yyyy-MM-dd HH:mm:ss", INV),
                    ny.ToString("yyyy-MM-dd HH:mm", INV),
                    evento, dirTxt,
                    px     == 0 ? "" : px.ToString("F2", INV),
                    stop   == 0 ? "" : stop.ToString("F2", INV),
                    risk   == 0 ? "" : risk.ToString("F2", INV),
                    target == 0 ? "" : target.ToString("F2", INV),
                    Open[0].ToString("F2", INV), High[0].ToString("F2", INV),
                    Low[0].ToString("F2", INV),  Close[0].ToString("F2", INV),
                    Position.MarketPosition.ToString(),
                    Position.Quantity.ToString(INV),
                    SystemPerformance.AllTrades.TradesPerformance.Currency.CumProfit.ToString("F2", INV),
                    zones.Count.ToString(INV),
                    nota
                }));
            }
            catch (Exception) { /* nunca dejar que el log rompa la estrategia */ }
        }

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description  = "ICT 5M Scalp v2 — entrada limite causal, SL/TP reales, sin sesgo 1H";
                Name         = "ICT5MScalpV2";
                Calculate                    = Calculate.OnBarClose;
                EntriesPerDirection          = 1;
                EntryHandling                = EntryHandling.AllEntries;
                IsExitOnSessionCloseStrategy = false;
                ExitOnSessionCloseSeconds    = 30;
                IsFillLimitOnTouch           = false;
                MaximumBarsLookBack          = MaximumBarsLookBack.TwoHundredFiftySix;
                OrderFillResolution          = OrderFillResolution.High;
                OrderFillResolutionType      = BarsPeriodType.Minute;
                OrderFillResolutionValue     = 1;
                Slippage                     = 0;   // el slippage real se configura en las propiedades
                StartBehavior                = StartBehavior.WaitUntilFlat;
                TimeInForce                  = TimeInForce.Gtc;
                TraceOrders                  = false;
                RealtimeErrorHandling        = RealtimeErrorHandling.StopCancelCloseIgnoreRejects;
                StopTargetHandling           = StopTargetHandling.ByStrategyPosition;
                BarsRequiredToTrade          = 80;
                IsInstantiatedOnEachOptimizationIteration = false;

                Qty = 3;  EntryAtBufferEdge = true;
                DailyLossLimit = 800;  TotalLossLimit = 1700;  ProfitTargetStop = 3000;

                DispLen = 60; DispMult = 1.5; DispCloseFrac = 0.6; ObScanBars = 10;
                LiqCheckBars = 12; LiqTolerancePts = 1.0; LiqAccumBars = 15;
                ZoneMaxAge = 300; MaxZones = 40;
                SlBufferPts = 0.5; EntryBufferPts = 8.0;
                UseRiskCap = true; MaxRiskPts = 100.0;

                RR2 = 3.0; BeTriggerR = 0.6; LockR = 0.5;
                SessionStartHour = 3; SessionEndHour = 11;

                Use1hBias = false; BiasSmaLen = 10;

                WriteCsvLog = true;
                CsvFolder   = @"C:\Users\diazl\Documents\NinjaTrader 8\export";
            }
            else if (State == State.Configure)
            {
                // Solo se agrega la serie de 1H si el sesgo esta activado. Con una
                // sola serie NinjaTrader permite 'Order Fill Resolution: High', que
                // rellena las ordenes con datos de 1 minuto en vez de con el OHLC de
                // la vela de 5m -- mucho mas fiel para las limites de esta estrategia.
                if (Use1hBias)
                    AddDataSeries(BarsPeriodType.Minute, 60);
                rangeSeries = new Series<double>(this);
            }
            else if (State == State.DataLoaded)
            {
                avgRange  = SMA(rangeSeries, DispLen);
                if (Use1hBias) bias1hSma = SMA(Closes[1], BiasSmaLen);
                nyTz      = TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time");

                if (WriteCsvLog)
                {
                    try
                    {
                        if (!Directory.Exists(CsvFolder)) Directory.CreateDirectory(CsvFolder);
                        string f = Path.Combine(CsvFolder,
                            "ICT5M_verify_" + DateTime.Now.ToString("yyyyMMdd_HHmmss", INV) + ".csv");
                        csv = new StreamWriter(f, false);
                        csv.AutoFlush = true;
                        csv.WriteLine("bar_time;ny_time;evento;dir;precio;stop;riesgo;target;o;h;l;c;posicion;qty;pnl_acum;zonas_vivas;nota");
                        Print("CSV de verificacion: " + f);
                    }
                    catch (Exception ex) { Print("No se pudo abrir el CSV: " + ex.Message); csv = null; }
                }
            }
            else if (State == State.Terminated)
            {
                if (csv != null) { try { csv.Flush(); csv.Close(); } catch (Exception) { } csv = null; }
            }
        }

        private DateTime NyTime(DateTime barTime)
        {
            // Globals vive en NinjaTrader.Core; hay que calificarlo entero porque
            // dentro de la clase Strategy el nombre corto no resuelve.
            return TimeZoneInfo.ConvertTime(barTime,
                       NinjaTrader.Core.Globals.GeneralOptions.TimeZoneInfo, nyTz);
        }

        protected override void OnBarUpdate()
        {
            if (BarsInProgress != 0) return;
            if (CurrentBars[0] < BarsRequiredToTrade) return;
            if (Use1hBias && (CurrentBars.Length < 2 || CurrentBars[1] < BiasSmaLen + 1)) return;

            rangeSeries[0] = High[0] - Low[0];
            if (CurrentBars[0] < DispLen + 1) return;

            // ---------- proteccion de cuenta ----------
            DateTime nyNow = NyTime(Time[0]);
            if (nyNow.Date != currentDay)
            {
                currentDay  = nyNow.Date;
                dayStartPnL = SystemPerformance.AllTrades.TradesPerformance.Currency.CumProfit;
                haltToday   = false;
            }
            double cum   = SystemPerformance.AllTrades.TradesPerformance.Currency.CumProfit;
            double today = cum - dayStartPnL;
            if (DailyLossLimit   > 0 && today <= -Math.Abs(DailyLossLimit))   haltToday = true;
            if (TotalLossLimit   > 0 && cum   <= -Math.Abs(TotalLossLimit))   haltTotal = true;
            if (ProfitTargetStop > 0 && cum   >=  Math.Abs(ProfitTargetStop)) haltTotal = true;

            // ---------- deteccion ----------
            double rng = High[0] - Low[0];
            bool isDisp = rng >= DispMult * avgRange[1];
            if (isDisp)
            {
                if (Close[0] > Open[0] && (Close[0] - Low[0]) >= DispCloseFrac * rng)
                {
                    int idx = -1;
                    for (int k = 1; k <= ObScanBars; k++)
                    { if (CurrentBar - k < 0) break; if (Close[k] < Open[k]) { idx = k; break; } }
                    if (idx > 0)
                    {
                        double candBot = Low[idx];
                        int mx = 0, cu = 0;
                        for (int k = idx + 1; k <= idx + LiqCheckBars; k++)
                        {
                            if (CurrentBar - k < 0) break;
                            if (Low[k] <= candBot + LiqTolerancePts) { cu++; if (cu > mx) mx = cu; } else cu = 0;
                        }
                        if (mx < LiqAccumBars)
                        {
                            zones.Add(new Zone { Dir = 1, Top = High[idx], Bot = candBot, Cleared = false, Born = CurrentBar });
                            Log("ZONA_NUEVA", "LONG", High[idx], candBot, 0, 0, "top/bot de la zona");
                        }
                    }
                }
                if (Close[0] < Open[0] && (High[0] - Close[0]) >= DispCloseFrac * rng)
                {
                    int idx = -1;
                    for (int k = 1; k <= ObScanBars; k++)
                    { if (CurrentBar - k < 0) break; if (Close[k] > Open[k]) { idx = k; break; } }
                    if (idx > 0)
                    {
                        double candTop = High[idx];
                        int mx = 0, cu = 0;
                        for (int k = idx + 1; k <= idx + LiqCheckBars; k++)
                        {
                            if (CurrentBar - k < 0) break;
                            if (High[k] >= candTop - LiqTolerancePts) { cu++; if (cu > mx) mx = cu; } else cu = 0;
                        }
                        if (mx < LiqAccumBars)
                        {
                            zones.Add(new Zone { Dir = -1, Top = candTop, Bot = Low[idx], Cleared = false, Born = CurrentBar });
                            Log("ZONA_NUEVA", "SHORT", candTop, Low[idx], 0, 0, "top/bot de la zona");
                        }
                    }
                }
                if (zones.Count > MaxZones) zones.RemoveRange(0, zones.Count - MaxZones);
            }

            // ---------- 'cleared' ----------
            foreach (var z in zones)
            {
                if (z.Born == CurrentBar || z.Cleared) continue;
                if (z.Dir == 1 && Low[0] > z.Top) z.Cleared = true;
                else if (z.Dir == -1 && High[0] < z.Bot) z.Cleared = true;
            }

            // ---------- gestion de la posicion abierta ----------
            if (inPosition && Position.MarketPosition != MarketPosition.Flat)
            {
                // nunca gestionar en la misma vela del fill
                if (CurrentBar != entryBar && BeTriggerR > 0 && !beMoved)
                {
                    double reachedR = plannedDir == 1
                        ? (High[0] - fillPrice) / riskPts
                        : (fillPrice - Low[0]) / riskPts;
                    if (reachedR >= BeTriggerR)
                    {
                        beMoved = true;
                        activeStop = plannedDir == 1
                            ? fillPrice + riskPts * LockR
                            : fillPrice - riskPts * LockR;
                        SetStopLoss(CalculationMode.Price, Instrument.MasterInstrument.RoundToTickSize(activeStop));
                        Print(Time[0] + "  BE -> stop " + activeStop.ToString("F2"));
                        Log("BE_MOVE", plannedDir == 1 ? "LONG" : "SHORT", fillPrice, activeStop, riskPts, 0,
                            "alcanzo " + BeTriggerR.ToString("F2", INV) + "R, asegura " + LockR.ToString("F2", INV) + "R");
                    }
                }
                return;
            }

            // ---------- purgar zonas ----------
            zones.RemoveAll(z =>
            {
                bool expired  = (CurrentBar - z.Born) > ZoneMaxAge;
                bool consumed = z.Born != CurrentBar && z.Cleared &&
                                ((z.Dir == 1 && Low[0] <= z.Top) || (z.Dir == -1 && High[0] >= z.Bot));
                return expired || consumed;
            });

            // ---------- sesion / frenos ----------
            int nyMin = nyNow.Hour * 60 + nyNow.Minute;
            bool inSession = nyMin >= SessionStartHour * 60 && nyMin < SessionEndHour * 60;
            if (haltToday || haltTotal || !inSession || Position.MarketPosition != MarketPosition.Flat)
            { CancelPending(); return; }

            int h1Bias = 0;
            if (Use1hBias)
            {
                double c1 = Closes[1][0], s1 = bias1hSma[0];
                h1Bias = c1 > s1 ? 1 : (c1 < s1 ? -1 : 0);
            }

            // ---------- candidata: zona viva mas reciente que el precio AUN no cruzo ----------
            int candDir = 0, candBorn = -1;
            double candLevel = 0, candStop = 0;

            foreach (var z in zones)
            {
                if (z.Born == CurrentBar || !z.Cleared) continue;
                if ((CurrentBar - z.Born) > ZoneMaxAge) continue;
                if (z.Born <= candBorn) continue;

                if (z.Dir == 1)
                {
                    if (Use1hBias && h1Bias <= 0) continue;
                    double lvl = EntryAtBufferEdge ? z.Top + EntryBufferPts : z.Top;
                    double stp = z.Bot - SlBufferPts;
                    double r   = lvl - stp;
                    if (r <= 0 || (UseRiskCap && r > MaxRiskPts)) continue;
                    if (Close[0] <= lvl) continue;             // el precio ya lo cruzo: no perseguir
                    candDir = 1; candBorn = z.Born; candLevel = lvl; candStop = stp;
                }
                else
                {
                    if (Use1hBias && h1Bias >= 0) continue;
                    double lvl = EntryAtBufferEdge ? z.Bot - EntryBufferPts : z.Bot;
                    double stp = z.Top + SlBufferPts;
                    double r   = stp - lvl;
                    if (r <= 0 || (UseRiskCap && r > MaxRiskPts)) continue;
                    if (Close[0] >= lvl) continue;
                    candDir = -1; candBorn = z.Born; candLevel = lvl; candStop = stp;
                }
            }

            // ---------- colocar / refrescar la limite ----------
            if (candDir != 0)
            {
                double lim = Instrument.MasterInstrument.RoundToTickSize(candLevel);
                pendingDir = candDir; pendingStop = candStop; pendingLevel = lim;
                bool nuevaOrden = (pendingLevelPrev != lim || pendingDirPrev != candDir);
                if (candDir == 1) pendingEntry = EnterLongLimit(0, true, Qty, lim, "ICT5-L");
                else              pendingEntry = EnterShortLimit(0, true, Qty, lim, "ICT5-S");
                if (nuevaOrden)
                    Log("ORDEN_LIMITE", candDir == 1 ? "LONG" : "SHORT", lim, candStop,
                        Math.Abs(lim - candStop), 0, "colocada por adelantado");
                pendingLevelPrev = lim; pendingDirPrev = candDir;
            }
            else CancelPending();
        }

        private void CancelPending()
        {
            if (pendingEntry != null &&
                (pendingEntry.OrderState == OrderState.Working || pendingEntry.OrderState == OrderState.Accepted))
            {
                CancelOrder(pendingEntry);
                Log("ORDEN_CANCELADA", pendingDirPrev == 1 ? "LONG" : "SHORT", pendingLevelPrev, 0, 0, 0, "");
            }
            pendingEntry = null;
            pendingLevelPrev = 0; pendingDirPrev = 0;
        }

        // El stop y el TP2 se fijan con el precio REALMENTE ejecutado.
        protected override void OnExecutionUpdate(Execution execution, string executionId, double price,
            int quantity, MarketPosition marketPosition, string orderId, DateTime time)
        {
            if (execution.Order == null) return;
            bool isEntry = execution.Order.Name == "ICT5-L" || execution.Order.Name == "ICT5-S";

            if (isEntry && execution.Order.OrderState == OrderState.Filled)
            {
                fillPrice   = price;
                plannedDir  = pendingDir;
                plannedStop = pendingStop;
                activeStop  = pendingStop;
                riskPts     = Math.Abs(fillPrice - pendingStop);
                beMoved     = false;
                entryBar    = CurrentBar;
                inPosition  = true;
                pendingEntry = null;

                if (riskPts <= 0)
                {
                    Print("Riesgo invalido tras el fill — cerrando por seguridad.");
                    if (plannedDir == 1) ExitLong("SAFE", "ICT5-L"); else ExitShort("SAFE", "ICT5-S");
                    return;
                }

                double target = plannedDir == 1
                    ? fillPrice + riskPts * RR2
                    : fillPrice - riskPts * RR2;

                SetStopLoss(CalculationMode.Price,   Instrument.MasterInstrument.RoundToTickSize(activeStop));
                SetProfitTarget(CalculationMode.Price, Instrument.MasterInstrument.RoundToTickSize(target));

                Print(string.Format("{0}  ENTRADA {1} fill={2:F2} stop={3:F2} riesgo={4:F2}pts TP2={5:F2}",
                    Time[0], plannedDir == 1 ? "LONG" : "SHORT", fillPrice, activeStop, riskPts, target));
                Log("FILL_ENTRADA", plannedDir == 1 ? "LONG" : "SHORT", fillPrice, activeStop, riskPts, target,
                    "pedido " + pendingLevel.ToString("F2", INV) + ", diferencia "
                    + (Math.Abs(fillPrice - pendingLevel)).ToString("F2", INV) + " pts");
            }

            if (Position.MarketPosition == MarketPosition.Flat)
            {
                if (inPosition)
                {
                    double ultimo = 0;
                    int nt = SystemPerformance.AllTrades.Count;
                    if (nt > 0) ultimo = SystemPerformance.AllTrades[nt - 1].ProfitCurrency;
                    Log("SALIDA", plannedDir == 1 ? "LONG" : "SHORT", price, activeStop, riskPts, 0,
                        (beMoved ? "con BE activado" : "sin BE") + ", pnl " + ultimo.ToString("F2", INV));
                }
                inPosition = false; beMoved = false; entryBar = -1;
            }
        }
    }
}

/* ============================================================================
INSTALACION Y PRIMERA PRUEBA

1. Copiar a:  Documents\NinjaTrader 8\bin\Custom\Strategies\ICT_5M_Scalp_v2_Strategy.cs
   NinjaScript Editor -> F5 para compilar.

2. Aplicar a un grafico de MNQ de 5 MINUTOS. La serie de 60m se agrega sola
   (solo se usa si activas el sesgo de 1H, que viene apagado).

3. Valores por defecto ya puestos:
      Contratos 3   |  Sesion 03:00-11:00 NY  |  Sesgo 1H: OFF
      Limite diario $800  |  Limite total $1.700  |  Parar en +$3.000

   Los tres frenos estan pensados para una cuenta de $2.000 de perdida maxima
   y $3.000 de objetivo: el diario corta un mal dia antes de que se lleve la
   cuenta, y "parar en +$3.000" evita seguir operando despues de pasar.

4. QUE VERIFICAR EN SIM, en este orden:
   a) Que NO opera fuera de 03:00-11:00 NY  <- el fallo mas probable.
      Mirar la hora de las entradas en el Output window.
   b) Que el stop y el TP2 aparecen como ORDENES en el chart al entrar,
      no solo como salidas a mercado despues.
   c) Que "riesgo=" en el Output coincide con |fill - stop|.
   d) Que el BE se activa (buscar "BE -> stop" en el Output).
   e) Contrastar las entradas contra las etiquetas del Pine de 5m.

5. Frecuencia esperada: ~10 operaciones por dia de sesion. Si ves muchas mas o
   muchas menos, algo no coincide con el backtest — parar y revisar.

DESVIACIONES CONOCIDAS RESPECTO AL BACKTEST
  - Precio de entrada: el backtest usa "borde del OB si el precio llego ahi,
    borde del margen si no". Con una sola orden en reposo hay que elegir uno;
    por defecto se usa el borde del margen (captura las mismas señales, entra
    algo peor en las que habrian llegado al OB). Cambiable con
    EntryAtBufferEdge.
  - Los numeros de referencia son IN-SAMPLE sobre 2,6 anios. No son promesa.
============================================================================ */
