// Runner en Node del motor validado (backtest_engine_validated.js).
// No requiere navegador ni TradingView: lee data/mnq_15m_bars.json.
//
// RIGOR: el dataset tiene huecos (meses no reconstruidos). El motor recorre
// velas en secuencia, así que dos velas separadas por años se tratarían como
// consecutivas y producirían resultados sin sentido. Por eso el dataset se
// parte en SEGMENTOS contiguos (corte si el hueco entre velas > 4 días) y el
// motor corre por separado en cada segmento; los resultados se agregan.
//
// Uso: node data/engine/run_backtest.js

const fs = require('fs');
const path = require('path');

const DATA = path.join(__dirname, '..', 'mnq_15m_bars.json');

// ---- Parámetros (idénticos a ICT 15M OB Entry v12) ----
const RISKCAP = 100, BETRIG = 1.2, RR1 = 1.8, RR2 = 4;
const DISP_MULT = 2.5, DISP_CLOSE_FRAC = 0.6, OB_SCAN = 10;
const LIQ_LEN = 12, LIQ_TOL = 4, LIQ_ACCUM = 6;
const SL_BUFFER = 2, ENTRY_BUFFER = 12;
const POINT_VALUE = 2, CONTRACTS = 3;
const COMMISSION = 2.22;          // por operación, ida y vuelta (3 contratos)
const SEGMENT_BREAK = 4 * 24 * 3600;

// ---- Carga y segmentación ----
const raw = JSON.parse(fs.readFileSync(DATA, 'utf-8'));
const allBars = raw.bars;

function segment(bars) {
  const segs = [];
  let start = 0;
  for (let i = 1; i < bars.length; i++) {
    if (bars[i][0] - bars[i - 1][0] > SEGMENT_BREAK) { segs.push(bars.slice(start, i)); start = i; }
  }
  segs.push(bars.slice(start));
  return segs.filter(s => s.length > 200);
}

// ---- Arrays de hora NY ----
const nyFmt = new Intl.DateTimeFormat('en-US', {
  timeZone: 'America/New_York', year: 'numeric', month: '2-digit', day: '2-digit',
  hour: '2-digit', minute: '2-digit', hour12: false, weekday: 'short'
});
function nyArrays(bars) {
  const n = bars.length;
  const NYmin = new Int32Array(n), NYd = new Array(n), NYmonth = new Array(n);
  for (let i = 0; i < n; i++) {
    const p = {};
    nyFmt.formatToParts(new Date(bars[i][0] * 1000)).forEach(x => { p[x.type] = x.value; });
    NYmin[i] = (+p.hour % 24) * 60 + (+p.minute);
    NYd[i] = p.weekday;
    NYmonth[i] = p.year + '-' + p.month;
  }
  return { NYmin, NYd, NYmonth };
}

// ---- Motor (transcripción exacta del validado) ----
function run(bars, ny, lockR) {
  const n = bars.length;
  const O = new Float64Array(n), H = new Float64Array(n), L = new Float64Array(n), C = new Float64Array(n);
  for (let i = 0; i < n; i++) { O[i] = bars[i][1]; H[i] = bars[i][2]; L[i] = bars[i][3]; C[i] = bars[i][4]; }
  const avg = new Float64Array(n);
  let s = 0;
  for (let i = 0; i < n; i++) { s += H[i] - L[i]; if (i >= 20) s -= H[i - 20] - L[i - 20]; avg[i] = i >= 19 ? s / 20 : NaN; }
  const { NYmin, NYd, NYmonth } = ny;

  let bT = NaN, bB = NaN, bF = false, bC = false, sT = NaN, sB = NaN, sF = false, sC = false;
  let open = false, dir = 0, ep = 0, sl = 0, origRisk = 0, eIdx = 0, tp1Hit = false, moved = false;
  const tr = [];
  let openAtEnd = 0;

  for (let i = 45; i < n; i++) {
    const rng = H[i] - L[i], isD = rng >= DISP_MULT * avg[i - 1];
    const bD = isD && C[i] > O[i] && (C[i] - L[i]) >= DISP_CLOSE_FRAC * rng;
    const sD = isD && C[i] < O[i] && (H[i] - C[i]) >= DISP_CLOSE_FRAC * rng;
    let bN = false, sN = false, k, j, idx, cand, mx, cu;

    if (bD) {
      idx = -1;
      for (k = 1; k <= OB_SCAN; k++) { if (C[i - k] < O[i - k]) { idx = k; break; } }
      if (idx > 0) {
        cand = L[i - idx]; mx = 0; cu = 0;
        for (j = idx + 1; j <= idx + LIQ_LEN; j++) { if (i - j < 0) break; if (L[i - j] <= cand + LIQ_TOL) { cu++; if (cu > mx) mx = cu; } else cu = 0; }
        if (mx < LIQ_ACCUM) { bT = H[i - idx]; bB = cand; bF = true; bC = false; bN = true; }
      }
    }
    if (sD) {
      idx = -1;
      for (k = 1; k <= OB_SCAN; k++) { if (C[i - k] > O[i - k]) { idx = k; break; } }
      if (idx > 0) {
        cand = H[i - idx]; mx = 0; cu = 0;
        for (j = idx + 1; j <= idx + LIQ_LEN; j++) { if (i - j < 0) break; if (H[i - j] >= cand - LIQ_TOL) { cu++; if (cu > mx) mx = cu; } else cu = 0; }
        if (mx < LIQ_ACCUM) { sT = cand; sB = L[i - idx]; sF = true; sC = false; sN = true; }
      }
    }

    if (!bN && bF && !bC && !isNaN(bT) && L[i] > bT) bC = true;
    if (!sN && sF && !sC && !isNaN(sB) && H[i] < sB) sC = true;
    const bTou = !bN && bC && bF, sTou = !sN && sC && sF;
    if (!bN && bC && bF && !isNaN(bT) && L[i] <= bT) bF = false;
    if (!sN && sC && sF && !isNaN(sB) && H[i] >= sB) sF = false;

    const lz = bTou && !isNaN(bT) && L[i] <= bT + ENTRY_BUFFER && L[i] >= bB;
    const sz = sTou && !isNaN(sB) && H[i] >= sB - ENTRY_BUFFER && H[i] <= sT;
    const inS = (NYmin[i] >= 1080) || (NYmin[i] < 660);
    const ce = inS && !open;

    if (ce && lz) {
      const _ep = Math.max(L[i], bT), _sl = bB - SL_BUFFER, _r = _ep - _sl;
      if (!(_r <= 0 || _r > RISKCAP)) { ep = _ep; sl = _sl; origRisk = _r; open = true; dir = 1; eIdx = i; tp1Hit = false; moved = false; }
    }
    if (ce && sz) {
      const _ep2 = Math.min(H[i], sB), _sl2 = sT + SL_BUFFER, _r2 = _sl2 - _ep2;
      if (!(_r2 <= 0 || _r2 > RISKCAP)) { ep = _ep2; sl = _sl2; origRisk = _r2; open = true; dir = -1; eIdx = i; tp1Hit = false; moved = false; }
    }

    if (open) {
      const tp1 = dir === 1 ? ep + origRisk * RR1 : ep - origRisk * RR1;
      const tp2 = dir === 1 ? ep + origRisk * RR2 : ep - origRisk * RR2;
      const hitSL = dir === 1 ? L[i] <= sl : H[i] >= sl;
      if (!tp1Hit) {
        const hT1 = dir === 1 ? H[i] >= tp1 : L[i] <= tp1;
        if (hitSL) {
          const code = !moved ? 'full' : (lockR > 0 ? 'locked' : 'befirst');
          tr.push({ e: eIdx, x: i, r: origRisk, kind: code, dir });
          open = false;
        } else if (hT1) {
          tp1Hit = true;
          const beLevel = dir === 1 ? ep + origRisk * lockR : ep - origRisk * lockR;
          if (!moved || (dir === 1 ? beLevel > sl : beLevel < sl)) sl = beLevel;
          moved = true;
        } else if (!moved) {
          const re = dir === 1 ? (H[i] - ep) / origRisk : (ep - L[i]) / origRisk;
          if (re >= BETRIG) { sl = dir === 1 ? ep + origRisk * lockR : ep - origRisk * lockR; moved = true; }
        }
      } else {
        const hT2 = dir === 1 ? H[i] >= tp2 : L[i] <= tp2;
        if (hitSL) { tr.push({ e: eIdx, x: i, r: origRisk, kind: 'be_or_locked_after_tp1', dir }); open = false; }
        else if (hT2) { tr.push({ e: eIdx, x: i, r: origRisk, kind: 'runner', dir }); open = false; }
      }
    }
  }
  if (open) openAtEnd = 1;

  const kept = tr.filter(t => NYd[t.e] !== 'Sun');
  kept.forEach(t => { t.month = NYmonth[t.e]; });
  return { trades: kept, openAtEnd, dropped: tr.length - kept.length };
}

function usd(t, lockR) {
  const risk = t.r, c = t.kind;
  if (c === 'full') return -CONTRACTS * risk * POINT_VALUE - COMMISSION;
  if (c === 'befirst') return -COMMISSION;
  if (c === 'locked') return CONTRACTS * (lockR * risk * POINT_VALUE) - COMMISSION;
  if (c === 'be_or_locked_after_tp1') return 2 * (RR1 * risk * POINT_VALUE) + 1 * (lockR * risk * POINT_VALUE) - COMMISSION;
  return 2 * (RR1 * risk * POINT_VALUE) + 1 * (RR2 * risk * POINT_VALUE) - COMMISSION;
}

function aggregate(trades, lockR) {
  let eq = 0, peak = 0, mdd = 0, gp = 0, gl = 0, wins = 0;
  const counts = {}, byMonth = {}, byYear = {};
  const sorted = trades.slice().sort((a, b) => a.e - b.e);
  for (const t of sorted) {
    const u = usd(t, lockR);
    if (u > 0) { gp += u; wins++; } else gl -= u;
    eq += u;
    if (eq > peak) peak = eq;
    if (peak - eq > mdd) mdd = peak - eq;
    counts[t.kind] = (counts[t.kind] || 0) + 1;
    byMonth[t.month] = (byMonth[t.month] || 0) + u;
    const y = t.month.slice(0, 4);
    byYear[y] = (byYear[y] || 0) + u;
  }
  return {
    n: trades.length,
    usd: Math.round(eq),
    pf: gl > 0 ? +(gp / gl).toFixed(2) : null,
    maxDD: Math.round(mdd),
    winRate: trades.length ? +(100 * wins / trades.length).toFixed(1) : 0,
    counts,
    byMonth,
    byYear
  };
}

// ---- Ejecución ----
const segs = segment(allBars);
console.log('Segmentos contiguos:', segs.length);
segs.forEach((s, i) => {
  console.log('  seg' + i + ':', new Date(s[0][0] * 1000).toISOString().slice(0, 10),
    '->', new Date(s[s.length - 1][0] * 1000).toISOString().slice(0, 10), ' velas:', s.length);
});
console.log('');

const nys = segs.map(nyArrays);
const LOCKS = [0, 0.3, 0.5, 0.6, 0.8, 0.9, 1.0, 1.2];
const results = {};

for (const lockR of LOCKS) {
  let allTrades = [];
  let openAtEnd = 0;
  segs.forEach((s, i) => {
    const r = run(s, nys[i], lockR);
    allTrades = allTrades.concat(r.trades);
    openAtEnd += r.openAtEnd;
  });
  results[lockR] = aggregate(allTrades, lockR);
  results[lockR].openAtEnd = openAtEnd;
}

console.log('=== BARRIDO DE lockR (protección al llegar a 1.2R) ===');
console.log('lock   trades    neto USD     PF    maxDD    winRate');
for (const lockR of LOCKS) {
  const r = results[lockR];
  console.log(
    String(lockR).padEnd(6),
    String(r.n).padStart(6),
    ('$' + r.usd.toLocaleString('en-US')).padStart(12),
    String(r.pf).padStart(6),
    ('-$' + r.maxDD.toLocaleString('en-US')).padStart(9),
    String(r.winRate + '%').padStart(8)
  );
}

console.log('');
console.log('=== DESGLOSE POR AÑO ===');
const years = Object.keys(results[0.5].byYear).sort();
console.log('año     ' + LOCKS.map(l => ('lock' + l).padStart(11)).join(''));
for (const y of years) {
  console.log(y.padEnd(8) + LOCKS.map(l => ('$' + Math.round(results[l].byYear[y] || 0).toLocaleString('en-US')).padStart(11)).join(''));
}

console.log('');
console.log('=== MESES POSITIVOS / NEGATIVOS ===');
for (const lockR of [0, 0.5, 0.8, 0.9]) {
  const m = results[lockR].byMonth;
  const keys = Object.keys(m).sort();
  const pos = keys.filter(k => m[k] > 0).length;
  const neg = keys.filter(k => m[k] < 0).length;
  console.log('lock=' + lockR + 'R -> meses: ' + keys.length + '  positivos: ' + pos + '  negativos: ' + neg);
}

console.log('');
console.log('=== DETALLE lock=0.5R (config adoptada) ===');
const r5 = results[0.5];
console.log('desenlaces:', JSON.stringify(r5.counts));
console.log('trades abiertos al final de segmento (descartados):', r5.openAtEnd);
const m5 = r5.byMonth;
console.log('');
console.log('mes        neto');
for (const k of Object.keys(m5).sort()) {
  console.log(k + '  ' + ('$' + Math.round(m5[k]).toLocaleString('en-US')).padStart(10));
}

fs.writeFileSync(path.join(__dirname, '..', 'backtest_results.json'), JSON.stringify(results, null, 1));
console.log('');
console.log('Resultados completos guardados en data/backtest_results.json');
