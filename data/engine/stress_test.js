// Pruebas de robustez sobre el motor validado.
//
// Test A - SLIPPAGE: penaliza cada salida por STOP (no las salidas por límite/TP).
//   MNQ: 1 tick = 0.25 puntos = $0.50 por contrato.
//
// Test B - SIN RESOLUCION EN LA MISMA VELA: el motor original abre y puede
//   cerrar la operación en la MISMA vela, usando el high y el low de esa vela
//   sin saber en qué orden ocurrieron. Esta variante prohíbe gestionar la
//   operación hasta la vela siguiente a la entrada.
//
// Test C - GAP DE REALISMO: mide, para cada lockR, cuántos puntos separan el
//   disparador (1.2R) del nivel asegurado. Si el gap es 0 (lock=1.2R) el
//   modelo asume que puedes garantizar la salida exactamente en el tick
//   extremo Y seguir corriendo al alza: eso es imposible.
//
// Uso: node data/engine/stress_test.js

const fs = require('fs');
const path = require('path');

const RISKCAP = 100, BETRIG = 1.2, RR1 = 1.8, RR2 = 4;
const DISP_MULT = 2.5, DISP_CLOSE_FRAC = 0.6, OB_SCAN = 10;
const LIQ_LEN = 12, LIQ_TOL = 4, LIQ_ACCUM = 6;
const SL_BUFFER = 2, ENTRY_BUFFER = 12;
const POINT_VALUE = 2, CONTRACTS = 3;
const COMMISSION = 2.22;
const SEGMENT_BREAK = 4 * 24 * 3600;

const raw = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'mnq_15m_bars.json'), 'utf-8'));

function segment(bars) {
  const segs = []; let start = 0;
  for (let i = 1; i < bars.length; i++) if (bars[i][0] - bars[i - 1][0] > SEGMENT_BREAK) { segs.push(bars.slice(start, i)); start = i; }
  segs.push(bars.slice(start));
  return segs.filter(s => s.length > 200);
}
const nyFmt = new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', hour: '2-digit', minute: '2-digit', hour12: false, weekday: 'short' });
function nyArrays(bars) {
  const n = bars.length, NYmin = new Int32Array(n), NYd = new Array(n);
  for (let i = 0; i < n; i++) {
    const p = {}; nyFmt.formatToParts(new Date(bars[i][0] * 1000)).forEach(x => { p[x.type] = x.value; });
    NYmin[i] = (+p.hour % 24) * 60 + (+p.minute); NYd[i] = p.weekday;
  }
  return { NYmin, NYd };
}

// noSameBar: si true, la gestión de la operación empieza en la vela SIGUIENTE a la entrada
function run(bars, ny, lockR, noSameBar) {
  const n = bars.length;
  const O = new Float64Array(n), H = new Float64Array(n), L = new Float64Array(n), C = new Float64Array(n);
  for (let i = 0; i < n; i++) { O[i] = bars[i][1]; H[i] = bars[i][2]; L[i] = bars[i][3]; C[i] = bars[i][4]; }
  const avg = new Float64Array(n); let s = 0;
  for (let i = 0; i < n; i++) { s += H[i] - L[i]; if (i >= 20) s -= H[i - 20] - L[i - 20]; avg[i] = i >= 19 ? s / 20 : NaN; }
  const { NYmin, NYd } = ny;

  let bT = NaN, bB = NaN, bF = false, bC = false, sT = NaN, sB = NaN, sF = false, sC = false;
  let open = false, dir = 0, ep = 0, sl = 0, origRisk = 0, eIdx = 0, tp1Hit = false, moved = false;
  const tr = [];
  let sameBarResolved = 0, whipsawTrigger = 0;

  for (let i = 45; i < n; i++) {
    const rng = H[i] - L[i], isD = rng >= DISP_MULT * avg[i - 1];
    const bD = isD && C[i] > O[i] && (C[i] - L[i]) >= DISP_CLOSE_FRAC * rng;
    const sD = isD && C[i] < O[i] && (H[i] - C[i]) >= DISP_CLOSE_FRAC * rng;
    let bN = false, sN = false, k, j, idx, cand, mx, cu;
    if (bD) {
      idx = -1; for (k = 1; k <= OB_SCAN; k++) if (C[i - k] < O[i - k]) { idx = k; break; }
      if (idx > 0) {
        cand = L[i - idx]; mx = 0; cu = 0;
        for (j = idx + 1; j <= idx + LIQ_LEN; j++) { if (i - j < 0) break; if (L[i - j] <= cand + LIQ_TOL) { cu++; if (cu > mx) mx = cu; } else cu = 0; }
        if (mx < LIQ_ACCUM) { bT = H[i - idx]; bB = cand; bF = true; bC = false; bN = true; }
      }
    }
    if (sD) {
      idx = -1; for (k = 1; k <= OB_SCAN; k++) if (C[i - k] > O[i - k]) { idx = k; break; }
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
    let justOpened = false;

    if (ce && lz) {
      const _ep = Math.max(L[i], bT), _sl = bB - SL_BUFFER, _r = _ep - _sl;
      if (!(_r <= 0 || _r > RISKCAP)) { ep = _ep; sl = _sl; origRisk = _r; open = true; dir = 1; eIdx = i; tp1Hit = false; moved = false; justOpened = true; }
    }
    if (ce && sz) {
      const _ep2 = Math.min(H[i], sB), _sl2 = sT + SL_BUFFER, _r2 = _sl2 - _ep2;
      if (!(_r2 <= 0 || _r2 > RISKCAP)) { ep = _ep2; sl = _sl2; origRisk = _r2; open = true; dir = -1; eIdx = i; tp1Hit = false; moved = false; justOpened = true; }
    }

    if (open && !(noSameBar && justOpened)) {
      const tp1 = dir === 1 ? ep + origRisk * RR1 : ep - origRisk * RR1;
      const tp2 = dir === 1 ? ep + origRisk * RR2 : ep - origRisk * RR2;
      const hitSL = dir === 1 ? L[i] <= sl : H[i] >= sl;
      if (!tp1Hit) {
        const hT1 = dir === 1 ? H[i] >= tp1 : L[i] <= tp1;
        if (hitSL) {
          if (justOpened) sameBarResolved++;
          tr.push({ e: eIdx, r: origRisk, kind: !moved ? 'full' : (lockR > 0 ? 'locked' : 'befirst'), stopExit: true });
          open = false;
        } else if (hT1) {
          tp1Hit = true;
          const beLevel = dir === 1 ? ep + origRisk * lockR : ep - origRisk * lockR;
          if (!moved || (dir === 1 ? beLevel > sl : beLevel < sl)) sl = beLevel;
          moved = true;
          if (justOpened) sameBarResolved++;
        } else if (!moved) {
          const re = dir === 1 ? (H[i] - ep) / origRisk : (ep - L[i]) / origRisk;
          if (re >= BETRIG) {
            // ¿la MISMA vela que disparó el 1.2R ya volvió por debajo del nivel asegurado?
            const lockLevel = dir === 1 ? ep + origRisk * lockR : ep - origRisk * lockR;
            const whip = dir === 1 ? (L[i] <= lockLevel) : (H[i] >= lockLevel);
            if (whip) whipsawTrigger++;
            sl = lockLevel; moved = true;
          }
        }
      } else {
        const hT2 = dir === 1 ? H[i] >= tp2 : L[i] <= tp2;
        if (hitSL) { tr.push({ e: eIdx, r: origRisk, kind: 'be_or_locked_after_tp1', stopExit: true }); open = false; }
        else if (hT2) { tr.push({ e: eIdx, r: origRisk, kind: 'runner', stopExit: false }); open = false; }
      }
    }
  }
  const kept = tr.filter(t => NYd[t.e] !== 'Sun');
  return { trades: kept, sameBarResolved, whipsawTrigger };
}

function usd(t, lockR, slipPts) {
  const risk = t.r, c = t.kind;
  // slippage solo en salidas por stop; afecta a los contratos que salen por stop
  const slipFull = slipPts * CONTRACTS * POINT_VALUE;
  const slipOne = slipPts * 1 * POINT_VALUE;
  if (c === 'full') return -CONTRACTS * risk * POINT_VALUE - COMMISSION - slipFull;
  if (c === 'befirst') return -COMMISSION - slipFull;
  if (c === 'locked') return CONTRACTS * (lockR * risk * POINT_VALUE) - COMMISSION - slipFull;
  if (c === 'be_or_locked_after_tp1') return 2 * (RR1 * risk * POINT_VALUE) + 1 * (lockR * risk * POINT_VALUE) - COMMISSION - slipOne;
  return 2 * (RR1 * risk * POINT_VALUE) + 1 * (RR2 * risk * POINT_VALUE) - COMMISSION;
}

function agg(trades, lockR, slipPts) {
  let eq = 0, gp = 0, gl = 0, peak = 0, mdd = 0;
  for (const t of trades.slice().sort((a, b) => a.e - b.e)) {
    const u = usd(t, lockR, slipPts);
    if (u > 0) gp += u; else gl -= u;
    eq += u; if (eq > peak) peak = eq; if (peak - eq > mdd) mdd = peak - eq;
  }
  return { n: trades.length, usd: Math.round(eq), pf: gl > 0 ? +(gp / gl).toFixed(2) : null, maxDD: Math.round(mdd) };
}

const segs = segment(raw.bars);
const nys = segs.map(nyArrays);
const LOCKS = [0, 0.5, 0.6, 0.8, 0.9, 1.0, 1.1, 1.2];

function runAll(lockR, noSameBar) {
  let all = [], sbr = 0, whip = 0;
  segs.forEach((s, i) => { const r = run(s, nys[i], lockR, noSameBar); all = all.concat(r.trades); sbr += r.sameBarResolved; whip += r.whipsawTrigger; });
  return { trades: all, sameBarResolved: sbr, whipsawTrigger: whip };
}

// riesgo medio en puntos
const base = runAll(0.5, false);
const avgRisk = base.trades.reduce((a, t) => a + t.r, 0) / base.trades.length;

console.log('Riesgo medio por operación: ' + avgRisk.toFixed(1) + ' puntos ($' + (avgRisk * POINT_VALUE * CONTRACTS).toFixed(0) + ' con 3 contratos)');
console.log('');

console.log('=== TEST C: gap de realismo entre el disparador (1.2R) y el nivel asegurado ===');
console.log('lock    gap en R   gap en puntos   ¿ejecutable con stop en reposo?');
for (const l of LOCKS) {
  const gapR = BETRIG - l;
  const gapPts = gapR * avgRisk;
  let verdict;
  if (gapR <= 0) verdict = 'NO - stop al precio de mercado (imposible)';
  else if (gapPts < 8) verdict = 'dudoso - por debajo del ruido intra-vela';
  else if (gapPts < 20) verdict = 'ajustado';
  else verdict = 'si - holgado';
  console.log(String(l).padEnd(8) + gapR.toFixed(1).padStart(6) + gapPts.toFixed(1).padStart(14) + '   ' + verdict);
}

console.log('');
console.log('=== TEST A: sensibilidad al slippage (solo salidas por stop) ===');
console.log('lock        0 ticks     1 tick     2 ticks    4 ticks   degradacion 0->4t');
for (const l of LOCKS) {
  const r = runAll(l, false);
  const vals = [0, 0.25, 0.5, 1.0].map(sp => agg(r.trades, l, sp).usd);
  const deg = ((vals[3] - vals[0]) / vals[0] * 100).toFixed(1);
  console.log(String(l).padEnd(6) + vals.map(v => ('$' + v.toLocaleString('en-US')).padStart(11)).join('') + ('  ' + deg + '%').padStart(20));
}

console.log('');
console.log('=== TEST B: prohibir resolucion en la misma vela de la entrada ===');
console.log('lock    normal      sin-misma-vela   diferencia   trades(normal/sin)');
for (const l of LOCKS) {
  const a = runAll(l, false), b = runAll(l, true);
  const ua = agg(a.trades, l, 0).usd, ub = agg(b.trades, l, 0).usd;
  const diff = ((ub - ua) / ua * 100).toFixed(1);
  console.log(String(l).padEnd(6) + ('$' + ua.toLocaleString('en-US')).padStart(10) + ('$' + ub.toLocaleString('en-US')).padStart(17) + (diff + '%').padStart(13) + ('  ' + a.trades.length + '/' + b.trades.length).padStart(16));
}

console.log('');
console.log('=== Whipsaw: velas donde el 1.2R se toco Y la misma vela volvio por debajo del nivel asegurado ===');
console.log('(mide cuantas veces el modelo asume una secuencia intra-vela que no puede verificar)');
for (const l of LOCKS) {
  const r = runAll(l, false);
  console.log('lock=' + String(l).padEnd(5) + ' whipsaws: ' + String(r.whipsawTrigger).padStart(4) + '   resueltos en la vela de entrada: ' + r.sameBarResolved);
}
