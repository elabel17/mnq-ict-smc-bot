// Auditoria independiente del scalping de 5m (claude_engine5.py / ICT_5M_Scalp_v1)
//
// Reimplementa el motor en JS a partir del codigo Python, y le aplica la misma
// bateria de pruebas que en su momento identifico el artefacto de lock=1.2R en
// la version de 15m. El objetivo NO es repetir el backtest, es estresarlo:
//
//   1) Reproducir la cifra base (control: si no reproduce, nada de lo demas vale)
//   2) Riesgo medio en puntos -> traducir el hueco de 0.1R (0.6R trigger vs
//      0.5R lock) a puntos y ticks reales
//   3) Disparo del BE por CIERRE de vela en vez de por extremo intra-vela
//      (esta es la prueba que hundio el 1.2R en 15m)
//   4) Curva de sensibilidad del lock: si sube en linea recta hasta pegarse al
//      disparador, es artefacto; si tiene un pico interior, es real
//
// Uso: node data/engine/scalp5m_audit.js

const fs = require('fs');
const path = require('path');

// ---- parametros hallados para 5m (claude_scalp_5m_found.json) ----
const DISP_LEN = 60, OB_SCAN = 10, DISP_MULT = 1.5;
const LIQ_ACCUM = 15, LIQ_TOL = 1.0, ENTRY_BUF = 8.0, SL_BUF = 0.5;
const RR1 = 1.8, RR2 = 3.0, BE_TRIG = 0.6, LOCK = 0.5;
const ZONE_MAX_AGE = 300, MAX_ZONES = 40;
const USE_RISK_CAP = true, MAX_RISK_PTS = 100.0;
const SESSION_START = 180, SESSION_END = 660;   // 03:00-11:00 NY
const BIAS_LEN = 10;

// ---- supuestos de ejecucion conservadores (los del informe) ----
const PV = 2.0;                 // $ por punto por contrato (MNQ)
const TICK = 0.25;
const COMM_PER_SIDE = 1.00;     // $/contrato/lado
const SLIP_TICKS_EXIT = 2;      // solo en la salida (la entrada es limite)

const bars = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'python', 'claude_ohlcv_5m_2024_2026.json'), 'utf-8'));
const n = bars.length;

const O = new Float64Array(n), H = new Float64Array(n), L = new Float64Array(n), C = new Float64Array(n);
for (let i = 0; i < n; i++) { O[i] = bars[i][1]; H[i] = bars[i][2]; L[i] = bars[i][3]; C[i] = bars[i][4]; }

// ---- hora NY por vela ----
const fmt = new Intl.DateTimeFormat('en-US', {
  timeZone: 'America/New_York', year: 'numeric', month: '2-digit', day: '2-digit',
  hour: '2-digit', minute: '2-digit', hour12: false, weekday: 'short'
});
const MIN = new Int32Array(n), MO = new Array(n), DY = new Array(n), WD = new Array(n);
for (let i = 0; i < n; i++) {
  const p = {}; fmt.formatToParts(new Date(bars[i][0] * 1000)).forEach(x => { p[x.type] = x.value; });
  MIN[i] = (+p.hour % 24) * 60 + (+p.minute);
  MO[i] = p.year + '-' + p.month; DY[i] = p.year + '-' + p.month + '-' + p.day; WD[i] = p.weekday;
}

// ---- sesgo de 1H sin lookahead (SMA 10 de cierres de horas completas) ----
const BIAS = new Int8Array(n);
{
  const hourCloses = [];
  let curHour = null, lastClose = null, bias = 0, ready = false;
  for (let i = 0; i < n; i++) {
    const hk = Math.floor(bars[i][0] / 3600);
    if (curHour === null) curHour = hk;
    if (hk !== curHour) {
      hourCloses.push(lastClose);
      if (hourCloses.length >= BIAS_LEN) {
        let s = 0;
        for (let k = hourCloses.length - BIAS_LEN; k < hourCloses.length; k++) s += hourCloses[k];
        const sma = s / BIAS_LEN, c = hourCloses[hourCloses.length - 1];
        bias = c > sma ? 1 : (c < sma ? -1 : 0); ready = true;
      }
      curHour = hk;
    }
    lastClose = C[i];
    BIAS[i] = ready ? bias : 0;
  }
}

// ---- media de rango ----
const AVG = new Float64Array(n);
{
  let s = 0;
  for (let i = 0; i < n; i++) {
    s += H[i] - L[i];
    if (i >= DISP_LEN) s -= H[i - DISP_LEN] - L[i - DISP_LEN];
    AVG[i] = i >= DISP_LEN - 1 ? s / DISP_LEN : NaN;
  }
}

// beMode: 'intrabar' (como el motor actual) | 'close' (conservador)
function run(lockR, beTrig, beMode) {
  let zones = [];
  let open = false, dir = 0, ep = 0, sl = 0, rk = 0, eBar = -1, tp1Hit = false, beMoved = false;
  const trades = [];

  for (let i = DISP_LEN + 1; i < n; i++) {
    const rng = H[i] - L[i];
    const isD = rng >= DISP_MULT * AVG[i - 1];
    if (isD) {
      const bull = C[i] > O[i] && (C[i] - L[i]) >= 0.6 * rng;
      const bear = C[i] < O[i] && (H[i] - C[i]) >= 0.6 * rng;
      if (bull) {
        let idx = -1;
        for (let k = 1; k <= OB_SCAN; k++) { if (i - k < 0) break; if (C[i - k] < O[i - k]) { idx = k; break; } }
        if (idx > 0) {
          const cand = L[i - idx]; let mx = 0, cu = 0;
          for (let j = idx + 1; j <= idx + 12; j++) { if (i - j < 0) break; if (L[i - j] <= cand + LIQ_TOL) { cu++; if (cu > mx) mx = cu; } else cu = 0; }
          if (mx < LIQ_ACCUM) zones.push({ dir: 1, top: H[i - idx], bot: cand, cleared: false, born: i });
        }
      }
      if (bear) {
        let idx = -1;
        for (let k = 1; k <= OB_SCAN; k++) { if (i - k < 0) break; if (C[i - k] > O[i - k]) { idx = k; break; } }
        if (idx > 0) {
          const cand = H[i - idx]; let mx = 0, cu = 0;
          for (let j = idx + 1; j <= idx + 12; j++) { if (i - j < 0) break; if (H[i - j] >= cand - LIQ_TOL) { cu++; if (cu > mx) mx = cu; } else cu = 0; }
          if (mx < LIQ_ACCUM) zones.push({ dir: -1, top: cand, bot: L[i - idx], cleared: false, born: i });
        }
      }
      if (zones.length > MAX_ZONES) zones.splice(0, zones.length - MAX_ZONES);
    }

    for (const z of zones) {
      if (z.born === i || z.cleared) continue;
      if (z.dir === 1 && L[i] > z.top) z.cleared = true;
      else if (z.dir === -1 && H[i] < z.bot) z.cleared = true;
    }

    const inSess = MIN[i] >= SESSION_START && MIN[i] < SESSION_END;

    if (!open && inSess) {
      let best = null;
      for (const z of zones) {
        if (z.born === i || !z.cleared) continue;
        if (i - z.born > ZONE_MAX_AGE) continue;
        if (z.dir === 1) {
          if (BIAS[i] <= 0) continue;
          if (L[i] <= z.top + ENTRY_BUF && L[i] >= z.bot) {
            const e = L[i] <= z.top ? z.top : z.top + ENTRY_BUF;
            const x = z.bot - SL_BUF, r = e - x;
            if (r > 0 && (!USE_RISK_CAP || r <= MAX_RISK_PTS) && (!best || z.born > best.born))
              best = { e, x, r, dir: 1, born: z.born };
          }
        } else {
          if (BIAS[i] >= 0) continue;
          if (H[i] >= z.bot - ENTRY_BUF && H[i] <= z.top) {
            const e = H[i] >= z.bot ? z.bot : z.bot - ENTRY_BUF;
            const x = z.top + SL_BUF, r = x - e;
            if (r > 0 && (!USE_RISK_CAP || r <= MAX_RISK_PTS) && (!best || z.born > best.born))
              best = { e, x, r, dir: -1, born: z.born };
          }
        }
      }
      if (best) { ep = best.e; sl = best.x; rk = best.r; dir = best.dir; open = true; eBar = i; tp1Hit = false; beMoved = false; }
    }

    for (let k = zones.length - 1; k >= 0; k--) {
      const z = zones[k];
      const expired = (i - z.born) > ZONE_MAX_AGE;
      const consumed = z.born !== i && z.cleared && ((z.dir === 1 && L[i] <= z.top) || (z.dir === -1 && H[i] >= z.bot));
      if (expired || consumed) zones.splice(k, 1);
    }

    if (open && i !== eBar) {
      const tp1 = dir === 1 ? ep + rk * RR1 : ep - rk * RR1;
      const tp2 = dir === 1 ? ep + rk * RR2 : ep - rk * RR2;
      const hitSL = dir === 1 ? L[i] <= sl : H[i] >= sl;
      const hitTP1 = !tp1Hit && (dir === 1 ? H[i] >= tp1 : L[i] <= tp1);
      const hitTP2 = tp1Hit && (dir === 1 ? H[i] >= tp2 : L[i] <= tp2);
      // AQUI esta la diferencia clave entre los dos modelos
      const ref = beMode === 'close' ? C[i] : (dir === 1 ? H[i] : L[i]);
      const reached = dir === 1 ? (ref - ep) / rk : (ep - ref) / rk;

      if (hitSL) {
        trades.push({ e: eBar, r: rk, kind: beMoved ? (tp1Hit ? 'tp1be' : 'lock') : 'full', lock: lockR, mo: MO[eBar], dy: DY[eBar] });
        open = false;
      } else if (hitTP1) {
        tp1Hit = true; beMoved = true;
        sl = dir === 1 ? Math.max(sl, ep + rk * lockR) : Math.min(sl, ep - rk * lockR);
      } else if (hitTP2) {
        trades.push({ e: eBar, r: rk, kind: 'tp2', mo: MO[eBar], dy: DY[eBar] });
        open = false;
      } else if (beTrig > 0 && !beMoved && reached >= beTrig) {
        beMoved = true;
        sl = dir === 1 ? ep + rk * lockR : ep - rk * lockR;
      }
    }
  }
  return trades.filter(t => WD[t.e] !== 'Sun');
}

function usd(t, qty) {
  const comm = COMM_PER_SIDE * 2 * qty;
  const slip = SLIP_TICKS_EXIT * TICK * qty * PV;
  if (t.kind === 'full')  return -qty * t.r * PV - comm - slip;
  if (t.kind === 'lock')  return qty * (t.lock * t.r * PV) - comm - slip;
  if (t.kind === 'tp1be') return qty * (t.lock * t.r * PV) - comm - slip;
  return qty * (RR2 * t.r * PV) - comm;   // tp2 sale por limite, sin slippage
}

function agg(tr, qty) {
  let eq = 0, gp = 0, gl = 0, pk = 0, md = 0, w = 0;
  const byMonth = {};
  for (const t of tr.slice().sort((a, b) => a.e - b.e)) {
    const u = usd(t, qty);
    if (u > 0) { gp += u; w++; } else gl -= u;
    eq += u; if (eq > pk) pk = eq; if (pk - eq > md) md = pk - eq;
    byMonth[t.mo] = (byMonth[t.mo] || 0) + u;
  }
  const months = Object.keys(byMonth);
  return {
    n: tr.length, usd: Math.round(eq), pf: gl > 0 ? +(gp / gl).toFixed(2) : null,
    mdd: Math.round(md), wr: tr.length ? +(100 * w / tr.length).toFixed(1) : 0,
    neg: months.filter(k => byMonth[k] < 0).length, months: months.length
  };
}

// =================== 1) CONTROL: reproducir la cifra base ===================
const base = run(LOCK, BE_TRIG, 'intrabar');
const b4 = agg(base, 4);
console.log('Dataset: ' + n.toLocaleString('en-US') + ' velas de 5m, '
  + new Date(bars[0][0] * 1000).toISOString().slice(0, 10) + ' a '
  + new Date(bars[n - 1][0] * 1000).toISOString().slice(0, 10));
console.log('');
console.log('=== 1) CONTROL — reproduccion de la cifra reportada ===');
console.log('Reportado por la otra sesion (4 contratos, conservador): $386.343, PF ~3.0-3.2, WR ~78%, ~3.752 trades, 0 meses negativos');
console.log('Esta reimplementacion:  $' + b4.usd.toLocaleString('en-US')
  + '  PF ' + b4.pf + '  WR ' + b4.wr + '%  ' + b4.n.toLocaleString('en-US') + ' trades  '
  + b4.neg + '/' + b4.months + ' meses negativos  maxDD -$' + b4.mdd.toLocaleString('en-US'));

// =================== 2) El hueco de 0.1R en puntos reales ===================
const risks = base.map(t => t.r).sort((a, b) => a - b);
const avgRisk = risks.reduce((a, b) => a + b, 0) / risks.length;
const medRisk = risks[Math.floor(risks.length / 2)];
console.log('');
console.log('=== 2) QUE SIGNIFICA EL HUECO DE 0.1R EN PUNTOS ===');
console.log('Riesgo por operacion: medio ' + avgRisk.toFixed(2) + ' pts, mediana ' + medRisk.toFixed(2)
  + ' pts, minimo ' + risks[0].toFixed(2) + ', maximo ' + risks[risks.length - 1].toFixed(2));
console.log('');
console.log('lock     hueco(R)   hueco(pts)   hueco(ticks)   ¿stop en reposo ejecutable?');
for (const lk of [0, 0.2, 0.3, 0.4, 0.5, 0.55, 0.6]) {
  const gapR = BE_TRIG - lk, gapPts = gapR * avgRisk, gapTicks = gapPts / TICK;
  let v;
  if (gapR <= 0) v = 'NO — stop al precio de mercado';
  else if (gapTicks < 4) v = 'NO — por debajo del spread/ruido';
  else if (gapTicks < 12) v = 'dudoso';
  else v = 'si';
  console.log(String(lk).padEnd(9) + gapR.toFixed(2).padStart(7) + gapPts.toFixed(2).padStart(13)
    + gapTicks.toFixed(1).padStart(14) + '   ' + v);
}

// =================== 3) LA PRUEBA DECISIVA: BE por cierre de vela ===========
console.log('');
console.log('=== 3) DISPARO DEL BE: extremo intra-vela (motor actual) vs cierre de vela ===');
console.log('lock    intra-vela      por cierre     diferencia');
for (const lk of [0, 0.2, 0.3, 0.4, 0.5, 0.6]) {
  const a = agg(run(lk, BE_TRIG, 'intrabar'), 4).usd;
  const b = agg(run(lk, BE_TRIG, 'close'), 4).usd;
  const d = a !== 0 ? ((b - a) / Math.abs(a) * 100).toFixed(1) : '0';
  console.log(String(lk).padEnd(8) + ('$' + a.toLocaleString('en-US')).padStart(12)
    + ('$' + b.toLocaleString('en-US')).padStart(15) + (d + '%').padStart(13));
}

// =================== 4) Curva de sensibilidad del lock ======================
console.log('');
console.log('=== 4) CURVA DEL LOCK (intra-vela, 4 contratos) — ¿pico interior o subida al limite? ===');
console.log('lock    trades      neto     PF     maxDD    WR    meses(-)');
for (const lk of [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.55, 0.6]) {
  const r = agg(run(lk, BE_TRIG, 'intrabar'), 4);
  console.log(String(lk).padEnd(8) + String(r.n).padStart(6) + ('$' + r.usd.toLocaleString('en-US')).padStart(11)
    + String(r.pf).padStart(7) + ('-$' + r.mdd.toLocaleString('en-US')).padStart(9)
    + (r.wr + '%').padStart(7) + (r.neg + '/' + r.months).padStart(9));
}
