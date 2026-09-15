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
// Puerto de data/engine/python/experimentos_liquidez.py, variante F: "sin
// limite de edad + liquidez a favor" -- la configuracion mas rentable
// encontrada en todo el proyecto, verificada tick a tick contra datos reales
// (sep-dic 2025):
//     54/55 operaciones, neto $4.213, PF 2.12, WR ~74% (3 contratos)
// Reemplaza la version anterior de este archivo (EdadMaxVelas=12, sin gate
// de liquidez: 24 operaciones, $3.060, PF 2.43) -- esa configuracion queda
// disponible bajando EdadMaxVelas a 12 y ExigirLiquidezFavor a false, pero
// la variante F es la que gana en frecuencia y PF combinados.
//
// DETECCION (modo "union"): un Order Block nace por CUALQUIERA de dos vias:
//   a) desplazamiento -- vela con rango >= dispMult x rango promedio,
//      cerrando en la fraccion direccional, con la vela de origen opuesta
//      dentro de ObScanBars y sin racha de liquidez sucia detras.
//   b) BOS de estructura interna -- ruptura por cierre de un pivote interno
//      (PivLado velas a cada lado), usando la ultima vela opuesta como origen.
// Ambas se conocen SOLO al cerrar la vela que las genera. Nada mira al futuro.
// NOTA: se audito visualmente contra un usuario real y el BOS ocasionalmente
// entra en zonas debiles (sin desplazamiento real detras) -- probado en
// Python agregarle los mismos filtros que el desplazamiento, mejora el PF de
// vela (2.59) pero empata o pierde levemente contra tick real ($3.531 vs
// $4.213) -- no se incluyo aqui, queda pendiente con mas muestra.
//
// CONFLUENCIA FVG: la zona debe tener un Fair Value Gap (hueco de 3 velas)
// de la misma direccion solapado con ella, detectado en cualquier vela
// posterior a su nacimiento (nunca antes -- el hueco de la vela actual solo
// se aplica hacia zonas YA vivas, jamas hacia el futuro).
//
// FRESCURA: EdadMaxVelas=0 (sin limite) -- la zona vive hasta que se toca,
// sin importar cuanto tiempo pase. Reemplaza la frescura de 3 horas de la
// version anterior: probado en Python, quitar el limite de tiempo y exigir
// en su lugar liquidez a favor real duplica la frecuencia sin perder PF.
// IMPORTANTE: a diferencia de versiones anteriores de este archivo, las
// zonas NO se invalidan por cierre en contra -- solo por edad (si
// EdadMaxVelas>0) o por tocarse. Se probo agregar invalidacion por cierre
// sobre esta variante sin edad y colapso de 55 a 1 operacion en Python
// (casi toda zona termina siendo cruzada por el precio alguna vez en meses
// de historial) -- es una incompatibilidad real entre ambas reglas, no un
// descuido.
//
// LIQUIDEZ A FAVOR (ExigirLiquidezFavor): puerto de
// motor_confluencia._liq_favor_peligro -- exige que haya un pivote
// confirmado y sin barrer actuando de iman en la direccion del trade (y
// ninguno actuando de riesgo de invalidacion cerca) antes de armar la zona.
// Es el ingrediente que permitio quitar la frescura por tiempo sin perder
// calidad.
//
// ENTRADA POR CONFIRMACION: cuando el precio toca la zona (dentro de
// EntryBufferPts), se "arma". Si dentro de EsperaVelas aparece una vela de
// reaccion (cuerpo >= CuerpoFrac del rango, cerrando mas alla del borde de
// la zona en el sentido del trade), se entra A MERCADO en OnBarClose de esa
// vela -- no es una orden limite descansando, es una confirmacion real.
// Probado en Python entrar SIN esperar confirmacion: triplica las
// operaciones pero el PF cae de 2.59 a 1.58 y el drawdown casi se triplica
// -- la espera de confirmacion se queda.
//
// GESTION: TP2 = RR2 x riesgo. El gatillo de BE (BeTriggerR) se evalua
// INTRATICK, en una serie secundaria de 1 tick -- a vela cerrada, el 12,5%
// de las operaciones (verificado con datos reales) resolvian mal el orden
// entre el gatillo y el stop original, cobrando ganancias que nunca
// existieron. LockR SIEMPRE debe ser menor que BeTriggerR. Probado en
// Python quitar el gatillo temprano (0.4R): empeora en las 4 variantes
// probadas (con y sin cierre parcial) -- se queda como esta. Probado cerrar
// parcial en RR1 antes de RR2: resultado practicamente identico ($4.034 vs
// $4.213) -- no aporta, no se incluyo por simplicidad.
//
// ESTADO: la deteccion, gate de liquidez y gestion estan verificados tick a
// tick en Python. Este archivo especifico (la integracion en NinjaScript)
// TODAVIA no ha ejecutado una orden real en la plataforma. Correr en Sim o
// Market Replay y comparar el CSV contra el resultado de Python antes de
// cualquier cuenta real.
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
        [NinjaScriptProperty] [Display(Name="Frescura operable en velas (0 = sin limite, variante validada)", Order=9, GroupName="3. Deteccion OB")]
        public int EdadMaxVelas { get; set; }
        [NinjaScriptProperty] [Display(Name="Exigir confluencia FVG", Order=10, GroupName="3. Deteccion OB")]
        public bool ExigirFVG { get; set; }
        [NinjaScriptProperty] [Display(Name="Exigir liquidez a FAVOR cerca (variante validada tick a tick)", Order=14, GroupName="3. Deteccion OB")]
        public bool ExigirLiquidezFavor { get; set; }
        [NinjaScriptProperty] [Display(Name="Distancia liquidez favor/peligro (x altura de zona)", Order=15, GroupName="3. Deteccion OB")]
        public double DistMultLiq { get; set; }
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

        // contadores de diagnostico -- para saber SIN esperar un trade si el
        // problema es "no hay setups" o "el replay no ha avanzado" o un bug real
        private long cntZonaNueva = 0, cntArmados = 0, cntConfirmados = 0;
        private int ultHeartbeatBar = -1;

        // pivotes internos (para BOS): el ultimo alto/bajo confirmado
        private double ultPivHi = double.NaN, ultPivLo = double.NaN;

        // niveles de liquidez VIVOS (para el gate favor/peligro) -- distinto de
        // ultPivHi/Lo (que solo guardan el ULTIMO para BOS): aqui se acumulan
        // todos los pivotes confirmados y sin barrer, igual que en Python
        // (motor_confluencia._liq_favor_peligro / experimentos_liquidez.py).
        private readonly List<double> pivHiVivos = new List<double>();
        private readonly List<double> pivLoVivos = new List<double>();

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
                // EdadMaxVelas = 0 (sin limite) + ExigirLiquidezFavor = true es la
                // variante F, la UNICA verificada tick a tick sin degradarse:
                // 54/55 operaciones, neto $4.213, PF 2.12 (sep-dic 2025, 3 contratos).
                // Es una configuracion DISTINTA a la primera version de este archivo
                // (que usaba EdadMaxVelas=12, PF 2.43 con 24 operaciones) -- esta
                // reemplaza a esa, no la complementa.
                PivLado = 2; EdadMaxVelas = 0; ExigirFVG = true;
                ExigirLiquidezFavor = true; DistMultLiq = 3.0;
                EntryBufferPts = 12.0; SlBufferPts = 2.0; MaxRiskPts = 100.0;

                CuerpoFrac = 0.4; EsperaVelas = 8;

                // LockR SIEMPRE menor que BeTriggerR: al reves el stop queda por
                // encima del precio y el broker lo rechaza (ya nos paso una vez).
                RR2 = 4.0; BeTriggerR = 0.4; LockR = 0.2;

                // Sin restriccion horaria por defecto (0-24): para diagnosticar si el
                // filtro de sesion 08-13 estaba tapando todo por un desfase de huso
                // horario. El CSV registra ny_time en cada evento -- el filtro de
                // 08-13 se aplica DESPUES, sobre el CSV, no aqui.
                SessionStartHour = 0; SessionEndHour = 24;

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
            if (esPivHi) { ultPivHi = candHi; pivHiVivos.Add(candHi); }
            if (esPivLo) { ultPivLo = candLo; pivLoVivos.Add(candLo); }

            // barrido: se retira el nivel cuando el precio lo cruza y cierra de vuelta
            // (idem cur_hi/cur_lo en motor_confluencia.calcular_scores)
            for (int k = pivHiVivos.Count - 1; k >= 0; k--)
            {
                double v = pivHiVivos[k];
                if (High[0] > v + 1.0 && Close[0] < v) pivHiVivos.RemoveAt(k);
            }
            for (int k = pivLoVivos.Count - 1; k >= 0; k--)
            {
                double v = pivLoVivos[k];
                if (Low[0] < v - 1.0 && Close[0] > v) pivLoVivos.RemoveAt(k);
            }
        }

        // Liquidez a favor/peligro -- puerto de motor_confluencia._liq_favor_peligro.
        // 0 = hay liquidez de invalidacion cerca (peligro); 100 = hay liquidez iman
        // a favor y no hay peligro; 50 = sin señal clara.
        private double LiqFavorPeligro(int dir, double top, double bot)
        {
            double alto = Math.Max(top - bot, 0.01);
            double distMax = alto * DistMultLiq;
            bool peligro = false, favor = false;
            if (dir == 1)
            {
                foreach (double niv in pivLoVivos) if (niv >= bot - distMax && niv <= bot) peligro = true;
                foreach (double niv in pivHiVivos) if (niv >= top && niv <= top + distMax) favor = true;
            }
            else
            {
                foreach (double niv in pivHiVivos) if (niv >= top && niv <= top + distMax) peligro = true;
                foreach (double niv in pivLoVivos) if (niv >= bot - distMax && niv <= bot) favor = true;
            }
            if (peligro) return 0.0;
            return favor ? 100.0 : 50.0;
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
                cntZonaNueva++;
                Log("ZONA_NUEVA", nuevoDir == 1 ? "LONG" : "SHORT", nuevoTop, nuevoBot, 0, 0,
                    "zona " + z.Id.ToString(INV));
            }

            // ---------- latido de diagnostico: cada 50 velas (~12.5h de 15m) ----------
            if (CurrentBar - ultHeartbeatBar >= 50)
            {
                ultHeartbeatBar = CurrentBar;
                Log("HEARTBEAT", "", Close[0], 0, 0, 0,
                    "bar=" + CurrentBar.ToString(INV) +
                    " zonas_creadas=" + cntZonaNueva.ToString(INV) +
                    " armados=" + cntArmados.ToString(INV) +
                    " confirmados=" + cntConfirmados.ToString(INV) +
                    " zonas_vivas=" + zonas.Count.ToString(INV) +
                    " ny=" + nyNow.ToString("yyyy-MM-dd HH:mm", INV));
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
            // IMPORTANTE: el motor de Python validado (motor_confluencia.run() y
            // experimentos_liquidez.simular()) NUNCA invalida una zona por cierre
            // en contra -- solo por edad. Se probo agregar esa invalidacion sobre
            // la variante sin limite de edad y colapso de 55 a 1 operacion (casi
            // toda zona termina siendo cruzada por el precio al menos una vez en
            // meses de historial). Por eso aqui NO se invalida por cierre; con
            // EdadMaxVelas=0 la zona vive hasta que se toca, punto.
            for (int i = zonas.Count - 1; i >= 0; i--)
            {
                var z = zonas[i];
                bool vencida = EdadMaxVelas > 0 && (CurrentBar - z.Born) > EdadMaxVelas;
                if (vencida) { zonas.RemoveAt(i); continue; }
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
                    if (ExigirLiquidezFavor && LiqFavorPeligro(z.Dir, z.Top, z.Bot) != 100.0) continue;
                    if (z.Dir == 1 && z.Bot - EntryBufferPts <= Low[0] && Low[0] <= z.Top + EntryBufferPts)
                    { armId = z.Id; armDir = 1; armTop = z.Top; armBot = z.Bot; armBar = CurrentBar;
                      cntArmados++; Log("ARMADO", "LONG", Close[0], 0, 0, 0, "zona " + z.Id.ToString(INV)); break; }
                    if (z.Dir == -1 && z.Bot - EntryBufferPts <= High[0] && High[0] <= z.Top + EntryBufferPts)
                    { armId = z.Id; armDir = -1; armTop = z.Top; armBot = z.Bot; armBar = CurrentBar;
                      cntArmados++; Log("ARMADO", "SHORT", Close[0], 0, 0, 0, "zona " + z.Id.ToString(INV)); break; }
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
                            cntConfirmados++;
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
                            cntConfirmados++;
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
