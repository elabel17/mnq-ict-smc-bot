#region Using declarations
using System;
using System.Collections.Generic;
using System.ComponentModel.DataAnnotations;
using System.Globalization;
using System.IO;
using NinjaTrader.Cbi;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.Strategies;
#endregion

// ============================================================================
// ICT Union+FVG 15M — NinjaScript
//
// Puerto de data/engine/python/motor_confluencia.py, configuracion
// "union+FVG, 08-13 NY", la unica linea del proyecto verificada tick a tick
// (no solo por vela) contra datos reales de NinjaTrader (sep-dic 2025):
//     24 operaciones, neto $3.060, PF 2.43, WR ~71% (3 contratos)
// El modelo por vela sobreestimaba esto en +43% ($5.402, PF 3.18) -- la
// correccion viene de resolver el orden real dentro de cada vela con ticks,
// exactamente lo que hace esta estrategia con el gatillo de BE.
//
// DETECCION (modo "union"): un Order Block nace por CUALQUIERA de dos vias:
//   a) desplazamiento -- vela con rango >= dispMult x rango promedio,
//      cerrando en la fraccion direccional, con la vela de origen opuesta
//      dentro de ObScanBars y sin racha de liquidez sucia detras.
//   b) BOS de estructura interna -- ruptura por cierre de un pivote interno
//      (PivLado velas a cada lado), usando la ultima vela opuesta como origen.
// Ambas se conocen SOLO al cerrar la vela que las genera. Nada mira al futuro.
//
// CONFLUENCIA FVG: la zona debe tener un Fair Value Gap (hueco de 3 velas)
// de la misma direccion solapado con ella, detectado en cualquier vela
// posterior a su nacimiento (nunca antes -- el hueco de la vela actual solo
// se aplica hacia zonas YA vivas, jamas hacia el futuro).
//
// FRESCURA: la zona deja de ser operable a los EdadMaxVelas de nacida
// (12 velas de 15m = 3 horas). Es el filtro individual mas potente
// encontrado en todo el proyecto.
//
// ENTRADA POR CONFIRMACION: cuando el precio toca la zona (dentro de
// EntryBufferPts), se "arma". Si dentro de EsperaVelas aparece una vela de
// reaccion (cuerpo >= CuerpoFrac del rango, cerrando mas alla del borde de
// la zona en el sentido del trade), se entra A MERCADO en OnBarClose de esa
// vela -- no es una orden limite descansando, es una confirmacion real.
//
// GESTION: TP2 = RR2 x riesgo. El gatillo de BE (BeTriggerR) se evalua
// INTRATICK, en una serie secundaria de 1 tick -- a vela cerrada, el 12,5%
// de las operaciones (verificado con datos reales) resolvian mal el orden
// entre el gatillo y el stop original, cobrando ganancias que nunca
// existieron. LockR SIEMPRE debe ser menor que BeTriggerR.
//
// ESTADO: NO PROBADO EN NINJATRADER TODAVIA. Verificado en Python contra
// tick data real (sep-dic 2025), pero nunca ha ejecutado una orden en la
// plataforma. Correr en Sim y comparar contra el CSV antes de cualquier
// cuenta real.
// ============================================================================

namespace NinjaTrader.NinjaScript.Strategies
{
    public class ICTUnionFVG15MStrategy : Strategy
    {
        // ---------------- Ejecucion ----------------
        [NinjaScriptProperty] [Display(Name="Contratos", Order=1, GroupName="1. Ejecucion")]
        public int Qty { get; set; }

        // ---------------- Proteccion de cuenta ----------------
        [NinjaScriptProperty] [Display(Name="Limite de perdida diaria USD (0 = off)", Order=1, GroupName="2. Proteccion")]
        public double DailyLossLimit { get; set; }
        [NinjaScriptProperty] [Display(Name="Limite de perdida total USD (0 = off)", Order=2, GroupName="2. Proteccion")]
        public double TotalLossLimit { get; set; }
        [NinjaScriptProperty] [Display(Name="Detener al alcanzar esta ganancia USD (0 = off)", Order=3, GroupName="2. Proteccion")]
        public double ProfitTargetStop { get; set; }

        // ---------------- Deteccion OB ----------------
        [NinjaScriptProperty] [Display(Name="Velas rango promedio", Order=1, GroupName="3. Deteccion OB")]
        public int DispLen { get; set; }
        [NinjaScriptProperty] [Display(Name="Umbral desplazamiento", Order=2, GroupName="3. Deteccion OB")]
        public double DispMult { get; set; }
        [NinjaScriptProperty] [Display(Name="Fraccion cierre direccional", Order=3, GroupName="3. Deteccion OB")]
        public double DispCloseFrac { get; set; }
        [NinjaScriptProperty] [Display(Name="Velas atras vela origen", Order=4, GroupName="3. Deteccion OB")]
        public int ObScanBars { get; set; }
        [NinjaScriptProperty] [Display(Name="Ventana liquidez", Order=5, GroupName="3. Deteccion OB")]
        public int LiqCheckBars { get; set; }
        [NinjaScriptProperty] [Display(Name="Tolerancia liquidez (pts)", Order=6, GroupName="3. Deteccion OB")]
        public double LiqTolerancePts { get; set; }
        [NinjaScriptProperty] [Display(Name="Racha que invalida liquidez", Order=7, GroupName="3. Deteccion OB")]
        public int LiqAccumBars { get; set; }
        [NinjaScriptProperty] [Display(Name="Velas a cada lado del pivote (BOS)", Order=8, GroupName="3. Deteccion OB")]
        public int PivLado { get; set; }
        [NinjaScriptProperty] [Display(Name="Frescura operable (velas)", Order=9, GroupName="3. Deteccion OB")]
        public int EdadMaxVelas { get; set; }
        [NinjaScriptProperty] [Display(Name="Exigir confluencia FVG", Order=10, GroupName="3. Deteccion OB")]
        public bool ExigirFVG { get; set; }
        [NinjaScriptProperty] [Display(Name="Margen de entrada (pts)", Order=11, GroupName="3. Deteccion OB")]
        public double EntryBufferPts { get; set; }
        [NinjaScriptProperty] [Display(Name="Buffer SL (pts)", Order=12, GroupName="3. Deteccion OB")]
        public double SlBufferPts { get; set; }
        [NinjaScriptProperty] [Display(Name="Tope de riesgo (pts)", Order=13, GroupName="3. Deteccion OB")]
        public double MaxRiskPts { get; set; }

        // ---------------- Confirmacion ----------------
        [NinjaScriptProperty] [Display(Name="Cuerpo minimo (fraccion del rango)", Order=1, GroupName="4. Confirmacion")]
        public double CuerpoFrac { get; set; }
        [NinjaScriptProperty] [Display(Name="Velas de espera tras armar", Order=2, GroupName="4. Confirmacion")]
        public int EsperaVelas { get; set; }

        // ---------------- Gestion ----------------
        [NinjaScriptProperty] [Display(Name="TP2 (multiplo R)", Order=1, GroupName="5. Gestion")]
        public double RR2 { get; set; }
        [NinjaScriptProperty] [Display(Name="Gatillo BE (multiplo R)", Order=2, GroupName="5. Gestion")]
        public double BeTriggerR { get; set; }
        [NinjaScriptProperty] [Display(Name="Ganancia asegurada (multiplo R)", Order=3, GroupName="5. Gestion")]
        public double LockR { get; set; }

        // ---------------- Sesion ----------------
        [NinjaScriptProperty] [Display(Name="Hora inicio (NY)", Order=1, GroupName="6. Sesion")]
        public int SessionStartHour { get; set; }
        [NinjaScriptProperty] [Display(Name="Hora fin (NY, exclusiva)", Order=2, GroupName="6. Sesion")]
        public int SessionEndHour { get; set; }

        // ---------------- Registro ----------------
        [NinjaScriptProperty] [Display(Name="Guardar CSV de verificacion", Order=1, GroupName="7. Registro")]
        public bool WriteCsvLog { get; set; }
        [NinjaScriptProperty] [Display(Name="Carpeta CSV", Order=2, GroupName="7. Registro")]
        public string CsvFolder { get; set; }

        private const string Build = "ICT-UNIONFVG-15M-20260914-01";

        // ---------------- zonas vivas ----------------
        private class Zone
        {
            public int Dir; public double Top, Bot; public int Born;
            public bool Cleared; public bool TieneFVG; public long Id;
        }
        private readonly List<Zone> zonas = new List<Zone>();
        private long zoneSeq = 0;

        // pivotes internos (para BOS): el ultimo alto/bajo confirmado
        private double ultPivHi = double.NaN, ultPivLo = double.NaN;

        // vela armada esperando confirmacion
        private long armId = -1; private int armDir = 0; private int armBar = -1;
        private double armTop, armBot;

        // posicion abierta
        private bool inPosition = false; private int plannedDir = 0;
        private double fillPrice, riskPts, activeStop, targetPx;
        private bool beMoved = false; private int entryBar = -1;
        private string entrySignal = "";

        // proteccion de cuenta
        private DateTime currentDay = DateTime.MinValue;
        private double dayStartPnL = 0; private bool haltToday = false, haltTotal = false;

        // series
        private int tickIdx = 1;
        private TimeZoneInfo nyTz;
        private Series<double> rangeSeries;
        private Series<double> avgRange;

        // registro csv
        private StreamWriter csv = null;
        private static readonly CultureInfo INV = CultureInfo.InvariantCulture;

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
                    zonas.Count.ToString(INV),
                    nota
                }));
            }
            catch (Exception) { /* nunca dejar que el log rompa la estrategia */ }
        }

        private DateTime NyTime(DateTime barTime)
        {
            return TimeZoneInfo.ConvertTime(barTime,
                       NinjaTrader.Core.Globals.GeneralOptions.TimeZoneInfo, nyTz);
        }

        // Salidas como ordenes explicitas Exit*: reenviar con el MISMO nombre
        // de senal modifica la orden existente en vez de crear un OCO nuevo
        // (Set*Loss/Set*ProfitTarget rechaza el reenvio con "OCO ID cannot
        // be reused" en cuanto se mueve el stop a breakeven).
        private void SubmitExits()
        {
            if (Position.MarketPosition == MarketPosition.Flat) return;
            int    q  = Position.Quantity;
            double sl = Instrument.MasterInstrument.RoundToTickSize(activeStop);
            double tp = Instrument.MasterInstrument.RoundToTickSize(targetPx);
            double ref0 = Close[0];
            bool imposible = (plannedDir == 1 && sl >= ref0) || (plannedDir == -1 && sl <= ref0);
            if (imposible)
            {
                Log("STOP_INALCANZABLE", plannedDir == 1 ? "LONG" : "SHORT", ref0, sl, riskPts, 0,
                    "stop del lado equivocado del mercado, salida a mercado");
                if (plannedDir == 1) ExitLong("STOPX", entrySignal); else ExitShort("STOPX", entrySignal);
                return;
            }
            if (plannedDir == 1)
            {
                ExitLongStopMarket(0, true, q, sl, "SL", entrySignal);
                ExitLongLimit     (0, true, q, tp, "TP", entrySignal);
            }
            else
            {
                ExitShortStopMarket(0, true, q, sl, "SL", entrySignal);
                ExitShortLimit     (0, true, q, tp, "TP", entrySignal);
            }
        }

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description  = Build + " -- union(disp+BOS)+FVG, confirmacion, verificado tick a tick";
                Name         = "ICTUnionFVG15M";
                Calculate                    = Calculate.OnBarClose;
                EntriesPerDirection          = 1;
                EntryHandling                = EntryHandling.AllEntries;
                IsExitOnSessionCloseStrategy = false;
                IsFillLimitOnTouch           = false;
                MaximumBarsLookBack          = MaximumBarsLookBack.Infinite;
                OrderFillResolution          = OrderFillResolution.Standard; // varias series -> no admite High
                Slippage                     = 0;
                StartBehavior                = StartBehavior.WaitUntilFlat;
                TimeInForce                  = TimeInForce.Gtc;
                RealtimeErrorHandling        = RealtimeErrorHandling.StopCancelCloseIgnoreRejects;
                StopTargetHandling           = StopTargetHandling.ByStrategyPosition;
                BarsRequiredToTrade          = 40;
                IsInstantiatedOnEachOptimizationIteration = false;

                Qty = 3;
                // Frenos a CERO por defecto: falsean cualquier verificacion contra
                // el motor de Python, que no los tiene. Para operar en real:
                // diaria 800, total 1700, objetivo 3000 (ajustar segun la cuenta).
                DailyLossLimit = 0; TotalLossLimit = 0; ProfitTargetStop = 0;

                DispLen = 20; DispMult = 1.5; DispCloseFrac = 0.6; ObScanBars = 10;
                LiqCheckBars = 12; LiqTolerancePts = 4.0; LiqAccumBars = 6;
                PivLado = 2; EdadMaxVelas = 12; ExigirFVG = true;
                EntryBufferPts = 12.0; SlBufferPts = 2.0; MaxRiskPts = 100.0;

                CuerpoFrac = 0.4; EsperaVelas = 8;

                // LockR SIEMPRE menor que BeTriggerR: al reves el stop queda por
                // encima del precio y el broker lo rechaza (ya nos paso una vez).
                RR2 = 4.0; BeTriggerR = 0.4; LockR = 0.2;

                SessionStartHour = 8; SessionEndHour = 13;

                WriteCsvLog = true;
                CsvFolder   = @"C:\Users\diazl\Documents\NinjaTrader 8\export";
            }
            else if (State == State.Configure)
            {
                // serie de 1 tick SOLO para el gatillo de BE -- con OnBarClose
                // en la serie principal, el indice [0] sigue siendo la vela de
                // 15m ya cerrada; el estado de BE se decide en la serie fina.
                AddDataSeries(BarsPeriodType.Tick, 1);
                tickIdx = 1;
                rangeSeries = new Series<double>(this);
                avgRange    = new Series<double>(this);
            }
            else if (State == State.DataLoaded)
            {
                nyTz = TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time");
                if (WriteCsvLog)
                {
                    try
                    {
                        Directory.CreateDirectory(CsvFolder);
                        string f = Path.Combine(CsvFolder,
                            "ICTUnionFVG15M_verify_" + DateTime.Now.ToString("yyyyMMdd_HHmmss", INV) + ".csv");
                        csv = new StreamWriter(f, false);
                        csv.AutoFlush = true;
                        csv.WriteLine("bar_time;ny_time;evento;dir;precio;stop;riesgo;target;o;h;l;c;posicion;qty;pnl_acum;zonas_vivas;nota");
                    }
                    catch (Exception ex) { Print("No se pudo abrir el CSV: " + ex.Message); csv = null; }
                }
            }
            else if (State == State.Terminated)
            {
                if (csv != null) { try { csv.Flush(); csv.Close(); } catch (Exception) { } csv = null; }
            }
        }

        // -------- BOS: el ultimo pivote interno confirmado (PivLado a cada lado) --------
        private void ActualizarPivotes()
        {
            if (CurrentBar < PivLado * 2) return;
            int c = PivLado; // indice del candidato: PivLado velas atras
            double candHi = High[c], candLo = Low[c];
            bool esPivHi = true, esPivLo = true;
            for (int k = 1; k <= PivLado; k++)
            {
                if (High[c - k] >= candHi || High[c + k] >= candHi) esPivHi = false;
                if (Low[c - k]  <= candLo || Low[c + k]  <= candLo) esPivLo = false;
            }
            if (esPivHi) ultPivHi = candHi;
            if (esPivLo) ultPivLo = candLo;
        }

        // busca la ultima vela opuesta dentro de ObScanBars velas atras
        private int BuscarOrigen(bool alcista)
        {
            for (int k = 1; k <= ObScanBars; k++)
            {
                if (k > CurrentBar) break;
                if (alcista) { if (Close[k] < Open[k]) return k; }
                else         { if (Close[k] > Open[k]) return k; }
            }
            return -1;
        }

        private bool LiquidezLimpia(bool alcista, double cand, int idxOrigen)
        {
            int mx = 0, cu = 0;
            for (int j = idxOrigen + 1; j <= idxOrigen + LiqCheckBars; j++)
            {
                if (j > CurrentBar) break;
                bool cerca = alcista ? (Low[j] <= cand + LiqTolerancePts)
                                      : (High[j] >= cand - LiqTolerancePts);
                if (cerca) { cu++; mx = Math.Max(mx, cu); } else cu = 0;
            }
            return mx < LiqAccumBars;
        }

        protected override void OnBarUpdate()
        {
            // ---------- gatillo de BE, sobre la serie de 1 tick ----------
            if (BarsInProgress == tickIdx)
            {
                if (inPosition && Position.MarketPosition != MarketPosition.Flat
                    && CurrentBars[0] > entryBar && BeTriggerR > 0 && !beMoved && riskPts > 0)
                {
                    double px   = Closes[tickIdx][0];
                    double rNow = plannedDir == 1 ? (px - fillPrice) / riskPts
                                                  : (fillPrice - px) / riskPts;
                    if (rNow >= BeTriggerR)
                    {
                        beMoved = true;
                        activeStop = plannedDir == 1 ? fillPrice + riskPts * LockR
                                                     : fillPrice - riskPts * LockR;
                        Log("BE_MOVE", plannedDir == 1 ? "LONG" : "SHORT", px, activeStop, riskPts, 0,
                            "intratick, alcanzo " + rNow.ToString("F2", INV) + "R");
                        SubmitExits();
                    }
                }
                return;
            }
            if (BarsInProgress != 0) return;
            if (CurrentBars[0] < BarsRequiredToTrade) return;

            rangeSeries[0] = High[0] - Low[0];
            double s = rangeSeries[0];
            for (int k = 1; k < DispLen && k <= CurrentBar; k++) s += rangeSeries[k];
            avgRange[0] = CurrentBar >= DispLen ? s / DispLen : double.NaN;

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

            // ---------- deteccion: desplazamiento ----------
            ActualizarPivotes();
            double avgPrev = CurrentBar >= 1 ? avgRange[1] : double.NaN;
            double rng = High[0] - Low[0];
            bool isDisp = !double.IsNaN(avgPrev) && avgPrev > 0 && rng >= DispMult * avgPrev;
            bool bullDisp = isDisp && Close[0] > Open[0] && (Close[0] - Low[0]) >= DispCloseFrac * rng;
            bool bearDisp = isDisp && Close[0] < Open[0] && (High[0] - Close[0]) >= DispCloseFrac * rng;

            int nuevoDir = 0; double nuevoTop = 0, nuevoBot = 0;
            if (bullDisp)
            {
                int idx = BuscarOrigen(true);
                if (idx > 0)
                {
                    double cand = Low[idx];
                    if (LiquidezLimpia(true, cand, idx))
                    { nuevoDir = 1; nuevoTop = High[idx]; nuevoBot = cand; }
                }
            }
            if (nuevoDir == 0 && bearDisp)
            {
                int idx = BuscarOrigen(false);
                if (idx > 0)
                {
                    double cand = High[idx];
                    if (LiquidezLimpia(false, cand, idx))
                    { nuevoDir = -1; nuevoTop = cand; nuevoBot = Low[idx]; }
                }
            }
            // ---------- deteccion: BOS de estructura interna (si disp no dio nada) ----------
            if (nuevoDir == 0 && !double.IsNaN(ultPivHi) && Close[0] > ultPivHi && Close[0] > Open[0])
            {
                int idx = BuscarOrigen(true);
                if (idx > 0) { nuevoDir = 1; nuevoTop = High[idx]; nuevoBot = Low[idx]; ultPivHi = double.NaN; }
            }
            else if (nuevoDir == 0 && !double.IsNaN(ultPivLo) && Close[0] < ultPivLo && Close[0] < Open[0])
            {
                int idx = BuscarOrigen(false);
                if (idx > 0) { nuevoDir = -1; nuevoTop = High[idx]; nuevoBot = Low[idx]; ultPivLo = double.NaN; }
            }
            if (nuevoDir != 0)
            {
                var z = new Zone { Dir = nuevoDir, Top = nuevoTop, Bot = nuevoBot,
                                    Born = CurrentBar, Cleared = false, TieneFVG = false, Id = ++zoneSeq };
                zonas.Add(z);
                Log("ZONA_NUEVA", nuevoDir == 1 ? "LONG" : "SHORT", nuevoTop, nuevoBot, 0, 0,
                    "zona " + z.Id.ToString(INV));
            }

            // ---------- FVG: hueco de 3 velas, se conoce AHORA (usa [0],[1],[2]) ----------
            if (ExigirFVG && CurrentBar >= 2)
            {
                bool fvgAlc = Low[0] > High[2];
                bool fvgBaj = High[0] < Low[2];
                if (fvgAlc || fvgBaj)
                {
                    int fd = fvgAlc ? 1 : -1;
                    double fTop = fvgAlc ? Low[0] : Low[2];
                    double fBot = fvgAlc ? High[2] : High[0];
                    foreach (var z in zonas)
                        if (z.Dir == fd && !(fBot > z.Top || fTop < z.Bot)) z.TieneFVG = true;
                }
            }

            // ---------- purgar zonas: invalidadas o vencidas ----------
            // TIENE que ir antes de cualquier return, igual que en el motor de
            // Python: si se salta con posicion abierta, zonas ya resueltas
            // sobreviven y se vuelven a operar despues.
            for (int i = zonas.Count - 1; i >= 0; i--)
            {
                var z = zonas[i];
                bool invalidada = z.Dir == 1 ? Close[0] < z.Bot : Close[0] > z.Top;
                bool vencida = (CurrentBar - z.Born) > EdadMaxVelas;
                if (invalidada || vencida) { zonas.RemoveAt(i); continue; }
            }

            // ---------- red de seguridad: exceso de contratos ----------
            if (Position.Quantity > Qty)
            {
                Log("EXCESO_CONTRATOS", Position.MarketPosition.ToString(), Close[0], 0, 0, 0,
                    "posicion de " + Position.Quantity.ToString(INV) + " con Qty=" + Qty.ToString(INV));
                if (Position.MarketPosition == MarketPosition.Long) ExitLong("EXCESO", "");
                else                                                ExitShort("EXCESO", "");
                return;
            }
            // ---------- red de seguridad: posicion huerfana ----------
            if (!inPosition && Position.MarketPosition != MarketPosition.Flat)
            {
                Log("HUERFANA", Position.MarketPosition.ToString(), Close[0], 0, 0, 0,
                    "posicion sin registro interno, cierre forzado");
                if (Position.MarketPosition == MarketPosition.Long) ExitLong("HUERFANA", "");
                else                                                ExitShort("HUERFANA", "");
                return;
            }

            // ---------- gestion de la posicion abierta ----------
            if (inPosition && Position.MarketPosition != MarketPosition.Flat)
            {
                SubmitExits();   // mantiene vivas SL y TP2 con el precio actual
                return;
            }

            int nyMin = nyNow.Hour * 60 + nyNow.Minute;
            bool inSession = nyMin >= SessionStartHour * 60 && nyMin < SessionEndHour * 60;
            if (haltToday || haltTotal || !inSession)
            {
                armId = -1;
                return;
            }

            // ---------- armar: precio toca una zona viva ----------
            if (armId == -1)
            {
                foreach (var z in zonas)
                {
                    if (z.Born == CurrentBar) continue;
                    if (ExigirFVG && !z.TieneFVG) continue;
                    if (z.Dir == 1 && z.Bot - EntryBufferPts <= Low[0] && Low[0] <= z.Top + EntryBufferPts)
                    { armId = z.Id; armDir = 1; armTop = z.Top; armBot = z.Bot; armBar = CurrentBar; break; }
                    if (z.Dir == -1 && z.Bot - EntryBufferPts <= High[0] && High[0] <= z.Top + EntryBufferPts)
                    { armId = z.Id; armDir = -1; armTop = z.Top; armBot = z.Bot; armBar = CurrentBar; break; }
                }
            }
            else if (CurrentBar - armBar > EsperaVelas)
            {
                armId = -1; // se agoto la espera sin confirmar
            }

            // ---------- confirmar y entrar a mercado ----------
            if (armId != -1 && CurrentBar > armBar)
            {
                double cuerpo = Math.Abs(Close[0] - Open[0]);
                double rango  = High[0] - Low[0];
                if (rango > 0)
                {
                    if (armDir == 1 && Close[0] > Open[0] && cuerpo >= CuerpoFrac * rango && Close[0] > armTop)
                    {
                        double ep = Close[0];
                        double sl = Math.Min(armBot, Low[0]) - SlBufferPts;
                        double r  = ep - sl;
                        if (r > 0 && r <= MaxRiskPts)
                        {
                            EnterLong(0, Qty, "L" + armId.ToString(INV));
                            plannedDir = 1; fillPrice = ep; activeStop = sl; riskPts = r;
                            targetPx = ep + r * RR2; entrySignal = "L" + armId.ToString(INV);
                            entryBar = CurrentBar; beMoved = false; inPosition = true; armId = -1;
                        }
                    }
                    else if (armDir == -1 && Close[0] < Open[0] && cuerpo >= CuerpoFrac * rango && Close[0] < armBot)
                    {
                        double ep = Close[0];
                        double sl = Math.Max(armTop, High[0]) + SlBufferPts;
                        double r  = sl - ep;
                        if (r > 0 && r <= MaxRiskPts)
                        {
                            EnterShort(0, Qty, "S" + armId.ToString(INV));
                            plannedDir = -1; fillPrice = ep; activeStop = sl; riskPts = r;
                            targetPx = ep - r * RR2; entrySignal = "S" + armId.ToString(INV);
                            entryBar = CurrentBar; beMoved = false; inPosition = true; armId = -1;
                        }
                    }
                }
            }
        }

        protected override void OnExecutionUpdate(Execution execution, string executionId, double price,
            int quantity, MarketPosition marketPosition, string orderId, DateTime time)
        {
            if (execution.Order == null) return;
            bool esEntrada = execution.Order.Name == entrySignal &&
                             (execution.Order.OrderAction == OrderAction.Buy || execution.Order.OrderAction == OrderAction.SellShort);
            if (esEntrada && execution.Order.OrderState == OrderState.Filled && inPosition && entryBar == CurrentBar)
            {
                // el fill real puede diferir un poco del cierre usado para planear
                fillPrice = price;
                riskPts   = Math.Abs(fillPrice - activeStop);
                targetPx  = fillPrice + riskPts * RR2 * plannedDir;
                if (riskPts <= 0)
                {
                    Log("RIESGO_INVALIDO", plannedDir == 1 ? "LONG" : "SHORT", fillPrice, activeStop, 0, 0, "cierre de seguridad");
                    if (plannedDir == 1) ExitLong("SAFE", entrySignal); else ExitShort("SAFE", entrySignal);
                    return;
                }
                SubmitExits();
                Log("FILL_ENTRADA", plannedDir == 1 ? "LONG" : "SHORT", fillPrice, activeStop, riskPts, targetPx, "");
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
INSTALACION

1. Copiar a Documents\NinjaTrader 8\bin\Custom\Strategies\
2. F5 en el NinjaScript Editor para compilar
3. Confirmar en pantalla: Contratos 3, todos los limites de perdida en 0,
   sesion 08-13, RR2 4.0, BE 0.4/0.2 -- vienen asi por defecto
4. Order Fill Resolution debe quedar en Standard (con dos series NinjaTrader
   no admite High) -- ya viene forzado en el codigo, no hay que tocarlo
5. Playback o Market Replay del mismo periodo verificado en Python
   (sep-dic 2025) para comparar contra los $3.060 / PF 2.43 ya confirmados
   tick a tick
============================================================================ */
