// Modelo intra-vela realista.
//
// El problema: en la vela de ENTRADA el motor usa el low (para entrar) y el
// high (para TP1 / disparador 1.2R) de la MISMA vela, sin saber en qué orden
// ocurrieron. Eso le da sistemáticamente el beneficio de la duda.
//
// Tres modos:
//   'optimista'  - el original: cualquier evento de la vela de entrada cuenta.
//   'pesimista'  - nada se gestiona en la vela de entrada (demasiado severo:
//                  también elimina los SL de esa vela, que sí son reales).
//   'realista'   - en la vela de entrada:
//                    * el STOP siempre puede ejecutarse (asunción adversa),
//                    * el TP1 / disparador 1.2R solo cuenta si la vela CERRÓ
//                      a favor de la operación (evidencia de que el impulso
//                      siguió después del llenado, no antes).
//                  Si en la vela de entrada se cumplen las condiciones de SL
//                  Y de TP a la vez, se asume el SL (peor caso).
//
// Uso: node data/engine/intrabar_test.js

const fs = require('fs');
const path = require('path');

const RISKCAP = 100, BETRIG = 1.2, RR1 = 1.8, RR2 = 4;
const DISP_MULT = 2.5, DISP_CLOSE_FRAC = 0.6, OB_SCAN = 10;
const LIQ_LEN = 12, LIQ_TOL = 4, LIQ_ACCUM = 6;
const SL_BUFFER = 2, ENTRY_BUFFER = 12;
const POINT_VALUE = 2, CONTRACTS = 3, COMMISSION = 2.22;
const SEGMENT_BREAK = 4 * 24 * 3600;
const SLIP = 0.25; // 1 tick de slippage en salidas por stop

const raw = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'mnq_15m_bars.json'), 'utf-8'));
function segment(bars) {
  const segs = []; let start = 0;
  for (let i = 1; i < bars.length; i++) if (bars[i][0] - bars[i - 1][0] > SEGMENT_BREAK) { segs.push(bars.slice(start, i)); start = i; }
  segs.push(bars.slice(start)); return segs.filter(s => s.length > 200);
}
const nyFmt = new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', year: 'numeric', month: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false, weekday: 'short' });
function nyArrays(bars) {
  const n = bars.length, NYmin = new Int32Array(n), NYd = new Array(n), NYmo = new Array(n);
  for (let i = 0; i < n; i++) {
    const p = {}; nyFmt.formatToParts(new Date(bars[i][0] * 1000)).forEach(x => { p[x.type] = x.value; });
    NYmin[i] = (+p.hour % 24) * 60 + (+p.minute); NYd[i] = p.weekday; NYmo[i] = p.year + '-' + p.month;
  }
  return { NYmin, NYd, NYmo };
}

function run(bars, ny, lockR, mode) {
  const n = bars.length;
  const O = new Float64Array(n), H = new Float64Array(n), L = new Float64Array(n), C = new Float64Array(n);
  for (let i = 0; i < n; i++) { O[i] = bars[i][1]; H[i] = bars[i][2]; L[i] = bars[i][3]; C[i] = bars[i][4]; }
  const avg = new Float64Array(n); let s = 0;
  for (let i = 0; i < n; i++) { s += H[i] - L[i]; if (i >= 20) s -= H[i - 20] - L[i - 20]; avg[i] = i >= 19 ? s / 20 : NaN; }
  const { NYmin, NYd, NYmo } = ny;

  let bT = NaN, bB = NaN, bF = false, bC = false, sT = NaN, sB = NaN, sF = false, sC = false;
  let open = false, dir = 0, ep = 0, sl = 0, origRisk = 0, eIdx = 0, tp1Hit = false, moved = false;
  const tr = [];

  for (let i = 45; i < n; i++) {
    const rng = H[i] - L[i], isD = rng >= DISP_MULT * avg[i - 1];
    const bD = isD && C[i] > O[i] && (C[i] - L[i]) >= DISP_CLOSE_FRAC * rng;
    const sD = isD && C[i] < O[i] && (H[i] - C[i]) >= DISP_CLOSE_FRAC * rng;
    let bN = false, sN = false, k, j, idx, cand, mx, cu;
    if (bD) {
      idx = -1; for (k = 1; k <= OB_SCAN; k++) if (C[i - k] < O[i - k]) { idx = k; break; }
      if (idx > 0) { cand = L[i - idx]; mx = 0; cu = 0;
        for (j = idx + 1; j <= idx + LIQ_LEN; j++) { if (i - j < 0) break; if (L[i - j] <= cand + LIQ_TOL) { cu++; if (cu > mx) mx = cu; } else cu = 0; }
        if (mx < LIQ_ACCUM) { bT = H[i - idx]; bB = cand; bF = true; bC = false; bN = true; } }
    }
    if (sD) {
      idx = -1; for (k = 1; k <= OB_SCAN; k++) if (C[i - k] > O[i - k]) { idx = k; break; }
      if (idx > 0) { cand = H[i - idx]; mx = 0; cu = 0;
        for (j = idx + 1; j <= idx + LIQ_LEN; j++) { if (i - j < 0) break; if (H[i - j] >= cand - LIQ_TOL) { cu++; if (cu > mx) mx = cu; } else cu = 0; }
        if (mx < LIQ_ACCUM) { sT = cand; sB = L[i - idx]; sF = true; sC = false; sN = true; } }
    }
    if (!bN && bF && !bC && !isNaN(bT) && L[i] > bT) bC = true;
    if (!sN && sF && !sC && !isNaN(sB) && H[i] < sB) sC = true;
    const bTou = !bN && bC && bF, sTou = !sN && sC && sF;
    if (!bN && bC && bF && !isNaN(bT) && L[i] <= bT) bF = false;
    if (!sN && sC && sF && !isNaN(sB) && H[i] >= sB) sF = false;

    const lz = bTou && !isNaN(bT) && L[i] <= bT + ENTRY_BUFFER && L[i] >= bB;
    const sz = sTou && !isNaN(sB) && H[i] >= sB - ENTRY_BUFFER && H[i] <= sT;
    const ce = ((NYmin[i] >= 1080) || (NYmin[i] < 660)) && !open;
    let justOpened = false;

    if (ce && lz) { const _ep = Math.max(L[i], bT), _sl = bB - SL_BUFFER, _r = _ep - _sl;
      if (!(_r <= 0 || _r > RISKCAP)) { ep = _ep; sl = _sl; origRisk = _r; open = true; dir = 1; eIdx = i; tp1Hit = false; moved = false; justOpened = true; } }
    if (ce && sz) { const _ep2 = Math.min(H[i], sB), _sl2 = sT + SL_BUFFER, _r2 = _sl2 - _ep2;
      if (!(_r2 <= 0 || _r2 > RISKCAP)) { ep = _ep2; sl = _sl2; origRisk = _r2; open = true; dir = -1; eIdx = i; tp1Hit = false; moved = false; justOpened = true; } }

    if (open) {
      // ¿se permite contar eventos FAVORABLES en esta vela?
      let allowFav = true;
      if (justOpened) {
        if (mode === 'pesimista') allowFav = false;
        else if (mode === 'realista') allowFav = dir === 1 ? (C[i] > ep) : (C[i] < ep);
      }
      const allowStop = !(justOpened && mode === 'pesimista');

      const tp1 = dir === 1 ? ep + origRisk * RR1 : ep - origRisk * RR1;
      const tp2 = dir === 1 ? ep + origRisk * RR2 : ep - origRisk * RR2;
      const hitSL = allowStop && (dir === 1 ? L[i] <= sl : H[i] >= sl);
      if (!tp1Hit) {
        const hT1 = allowFav && (dir === 1 ? H[i] >= tp1 : L[i] <= tp1);
        if (hitSL) { tr.push({ e: eIdx, r: origRisk, kind: !moved ? 'full' : (lockR > 0 ? 'locked' : 'befirst'), mo: NYmo[eIdx] }); open = false; }
        else if (hT1) { tp1Hit = true;
          const bl = dir === 1 ? ep + origRisk * lockR : ep - origRisk * lockR;
          if (!moved || (dir === 1 ? bl > sl : bl < sl)) sl = bl; moved = true; }
        else if (!moved && allowFav) {
          const re = dir === 1 ? (H[i] - ep) / origRisk : (ep - L[i]) / origRisk;
          if (re >= BETRIG) { sl = dir === 1 ? ep + origRisk * lockR : ep - origRisk * lockR; moved = true; } }
      } else {
        const hT2 = allowFav && (dir === 1 ? H[i] >= tp2 : L[i] <= tp2);
        if (hitSL) { tr.push({ e: eIdx, r: origRisk, kind: 'be_or_locked_after_tp1', mo: NYmo[eIdx] }); open = false; }
        else if (hT2) { tr.push({ e: eIdx, r: origRisk, kind: 'runner', mo: NYmo[eIdx] }); open = false; }
      }
    }
  }
  return tr.filter(t => NYd[t.e] !== 'Sun');
}

function usd(t, lockR) {
  const r = t.r, c = t.kind;
  const sF = SLIP * CONTRACTS * POINT_VALUE, s1 = SLIP * POINT_VALUE;
  if (c === 'full') return -CONTRACTS * r * POINT_VALUE - COMMISSION - sF;
  if (c === 'befirst') return -COMMISSION - sF;
  if (c === 'locked') return CONTRACTS * (lockR * r * POINT_VALUE) - COMMISSION - sF;
  if (c === 'be_or_locked_after_tp1') return 2 * (RR1 * r * POINT_VALUE) + 1 * (lockR * r * POINT_VALUE) - COMMISSION - s1;
  return 2 * (RR1 * r * POINT_VALUE) + 1 * (RR2 * r * POINT_VALUE) - COMMISSION;
}
function agg(trades, lockR) {
  let eq = 0, gp = 0, gl = 0, peak = 0, mdd = 0, wins = 0;
  const byYear = {}, byMonth = {};
  for (const t of trades.slice().sort((a, b) => a.e - b.e)) {
    const u = usd(t, lockR);
    if (u > 0) { gp += u; wins++; } else gl -= u;
    eq += u; if (eq > peak) peak = eq; if (peak - eq > mdd) mdd = peak - eq;
    byYear[t.mo.slice(0, 4)] = (byYear[t.mo.slice(0, 4)] || 0) + u;
    byMonth[t.mo] = (byMonth[t.mo] || 0) + u;
  }
  const mk = Object.keys(byMonth);
  return { n: trades.length, usd: Math.round(eq), pf: gl > 0 ? +(gp / gl).toFixed(2) : null,
    maxDD: Math.round(mdd), wr: +(100 * wins / trades.length).toFixed(1),
    negMonths: mk.filter(k => byMonth[k] < 0).length, months: mk.length, byYear };
}

const segs = segment(raw.bars), nys = segs.map(nyArrays);
function runAll(lockR, mode) { let a = []; segs.forEach((s, i) => { a = a.concat(run(s, nys[i], lockR, mode)); }); return a; }

const LOCKS = [0, 0.5, 0.6, 0.8, 0.9, 1.0, 1.2];
const MODES = ['optimista', 'realista', 'pesimista'];

console.log('Con 1 tick de slippage en salidas por stop y $2.22 de comision por operacion.');
console.log('Periodo: 2020-11 a 2026-09 (5.8 anios). Capital 50k, 3 contratos MNQ.');
console.log('');
console.log('=== NETO POR MODO INTRA-VELA ===');
console.log('lock      optimista        realista       pesimista');
const store = {};
for (const l of LOCKS) {
  const row = MODES.map(m => { const a = agg(runAll(l, m), l); store[l + '|' + m] = a; return a.usd; });
  console.log(String(l).padEnd(6) + row.map(v => ('$' + v.toLocaleString('en-US')).padStart(16)).join(''));
}

console.log('');
console.log('=== MODO REALISTA - detalle ===');
console.log('lock   trades     neto     PF    maxDD    winRate  meses(-)');
for (const l of LOCKS) {
  const a = store[l + '|realista'];
  console.log(String(l).padEnd(6) + String(a.n).padStart(6) + ('$' + a.usd.toLocaleString('en-US')).padStart(11)
    + String(a.pf).padStart(7) + ('-$' + a.maxDD.toLocaleString('en-US')).padStart(9)
    + (a.wr + '%').padStart(9) + (a.negMonths + '/' + a.months).padStart(10));
}

console.log('');
console.log('=== MODO REALISTA - por anio ===');
const yrs = Object.keys(store['0.5|realista'].byYear).sort();
console.log('anio  ' + LOCKS.map(l => ('lock' + l).padStart(11)).join(''));
for (const y of yrs) {
  console.log(y.padEnd(6) + LOCKS.map(l => ('$' + Math.round(store[l + '|realista'].byYear[y] || 0).toLocaleString('en-US')).padStart(11)).join(''));
}

console.log('');
console.log('=== 0.5R vs 0.8R vs 0.9R en modo realista ===');
const b = store['0.5|realista'];
for (const l of [0.8, 0.9]) {
  const a = store[l + '|realista'];
  const d = a.usd - b.usd;
  console.log('lock=' + l + 'R vs 0.5R: ' + (d >= 0 ? '+' : '') + '$' + d.toLocaleString('en-US')
    + '  (' + (d / b.usd * 100).toFixed(1) + '%)   maxDD ' + (a.maxDD < b.maxDD ? 'mejor' : 'peor')
    + ' (-$' + a.maxDD.toLocaleString('en-US') + ' vs -$' + b.maxDD.toLocaleString('en-US') + ')');
}
