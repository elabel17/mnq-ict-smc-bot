// Prueba estructural: ¿estamos perdiendo Order Blocks válidos?
//
// Dos limitaciones sospechadas en la lógica actual:
//   A) obScanBars=10: solo busca la vela de origen hasta 10 velas atrás.
//   B) MÁS GRAVE: el script guarda una sola variable bullTop/bullBot. Cuando
//      se forma un OB nuevo, el anterior se DESTRUYE aunque siguiera sin
//      mitigar. Solo puede seguir una zona alcista y una bajista a la vez.
//
// Este script compara la lógica actual contra una que mantiene varias zonas
// vivas simultáneamente, con caducidad configurable.
//
// Uso: node data/engine/multizone_test.js

const fs = require('fs');
const path = require('path');
const BETRIG = 1.2, RR1 = 1.8, RR2 = 4, LOCK = 0.8;
const DISP_MULT = 2.5, DISP_CLOSE_FRAC = 0.6;
const LIQ_LEN = 12, LIQ_TOL = 4, LIQ_ACCUM = 6;
const SL_BUFFER = 2, ENTRY_BUFFER = 12, CAP = 100;
const PV = 2, CT = 3, COMM = 2.22, SEG = 4 * 24 * 3600, SLIP = 0.25;
const SPLIT = '2023-09';

const raw = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'mnq_15m_bars.json'), 'utf-8'));
function segment(b) { const s = []; let st = 0; for (let i = 1; i < b.length; i++) if (b[i][0] - b[i - 1][0] > SEG) { s.push(b.slice(st, i)); st = i; } s.push(b.slice(st)); return s.filter(x => x.length > 200); }
const fmt = new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false, weekday: 'short' });
function ny(b) {
  const n = b.length, M = new Int32Array(n), D = new Array(n), Mo = new Array(n), Dy = new Array(n);
  for (let i = 0; i < n; i++) {
    const p = {}; fmt.formatToParts(new Date(b[i][0] * 1000)).forEach(x => { p[x.type] = x.value; });
    M[i] = (+p.hour % 24) * 60 + (+p.minute); D[i] = p.weekday; Mo[i] = p.year + '-' + p.month; Dy[i] = p.year + '-' + p.month + '-' + p.day;
  }
  return { M, D, Mo, Dy };
}
function usd(t) {
  const r = t.r, c = t.kind, sF = SLIP * CT * PV, s1 = SLIP * PV;
  if (c === 'full') return -CT * r * PV - COMM - sF;
  if (c === 'locked') return CT * (LOCK * r * PV) - COMM - sF;
  if (c === 'tp1be') return 2 * (RR1 * r * PV) + 1 * (LOCK * r * PV) - COMM - s1;
  return 2 * (RR1 * r * PV) + 1 * (RR2 * r * PV) - COMM;
}
function agg(tr) {
  let eq = 0, gp = 0, gl = 0, pk = 0, md = 0, w = 0; const bm = {};
  for (const t of tr.slice().sort((a, b) => a.e - b.e)) {
    const u = usd(t); if (u > 0) { gp += u; w++; } else gl -= u;
    eq += u; if (eq > pk) pk = eq; if (pk - eq > md) md = pk - eq;
    bm[t.mo] = (bm[t.mo] || 0) + u;
  }
  const mk = Object.keys(bm);
  return { n: tr.length, usd: Math.round(eq), pf: gl > 0 ? +(gp / gl).toFixed(2) : null, mdd: Math.round(md), wr: tr.length ? +(100 * w / tr.length).toFixed(1) : 0, neg: mk.filter(k => bm[k] < 0).length, mo: mk.length };
}

// multi=false -> una zona por lado (lógica actual). multi=true -> varias vivas.
function run(bars, nya, scanBars, multi, maxAge, pick) {
  const n = bars.length;
  const O = new Float64Array(n), H = new Float64Array(n), L = new Float64Array(n), C = new Float64Array(n);
  for (let i = 0; i < n; i++) { O[i] = bars[i][1]; H[i] = bars[i][2]; L[i] = bars[i][3]; C[i] = bars[i][4]; }
  const avg = new Float64Array(n); let s = 0;
  for (let i = 0; i < n; i++) { s += H[i] - L[i]; if (i >= 20) s -= H[i - 20] - L[i - 20]; avg[i] = i >= 19 ? s / 20 : NaN; }
  const { M, D, Mo, Dy } = nya;
  let zones = [];
  let open = false, dir = 0, ep = 0, sl = 0, rk = 0, eI = 0, tp1 = false, mv = false;
  const tr = [];

  for (let i = 45; i < n; i++) {
    const rng = H[i] - L[i], isD = rng >= DISP_MULT * avg[i - 1];
    const bD = isD && C[i] > O[i] && (C[i] - L[i]) >= DISP_CLOSE_FRAC * rng;
    const sD = isD && C[i] < O[i] && (H[i] - C[i]) >= DISP_CLOSE_FRAC * rng;
    let k, j, idx, cand, mx, cu;

    if (bD) {
      idx = -1;
      for (k = 1; k <= scanBars; k++) { if (i - k < 0) break; if (C[i - k] < O[i - k]) { idx = k; break; } }
      if (idx > 0) {
        cand = L[i - idx]; mx = 0; cu = 0;
        for (j = idx + 1; j <= idx + LIQ_LEN; j++) { if (i - j < 0) break; if (L[i - j] <= cand + LIQ_TOL) { cu++; if (cu > mx) mx = cu; } else cu = 0; }
        if (mx < LIQ_ACCUM) {
          if (!multi) zones = zones.filter(z => z.dir !== 1);
          zones.push({ dir: 1, top: H[i - idx], bot: cand, cleared: false, born: i });
        }
      }
    }
    if (sD) {
      idx = -1;
      for (k = 1; k <= scanBars; k++) { if (i - k < 0) break; if (C[i - k] > O[i - k]) { idx = k; break; } }
      if (idx > 0) {
        cand = H[i - idx]; mx = 0; cu = 0;
        for (j = idx + 1; j <= idx + LIQ_LEN; j++) { if (i - j < 0) break; if (H[i - j] >= cand - LIQ_TOL) { cu++; if (cu > mx) mx = cu; } else cu = 0; }
        if (mx < LIQ_ACCUM) {
          if (!multi) zones = zones.filter(z => z.dir !== -1);
          zones.push({ dir: -1, top: cand, bot: L[i - idx], cleared: false, born: i });
        }
      }
    }

    // Orden idéntico al Pine original:
    //  1) actualizar 'cleared' con la vela actual
    //  2) calcular candidatas (touchable = cleared && fresh)
    //  3) consumir las zonas tocadas
    // Ojo: una zona puede volverse 'cleared' y entrar en la MISMA vela, si el
    // low queda entre top y top+buffer. El original lo permite.
    for (const z of zones) {
      if (z.born === i) continue;
      if (z.dir === 1) { if (!z.cleared && L[i] > z.top) z.cleared = true; }
      else { if (!z.cleared && H[i] < z.bot) z.cleared = true; }
    }

    const cands = [];
    for (const z of zones) {
      if (z.born === i) continue;
      if (i - z.born > maxAge) continue;
      if (!z.cleared) continue;
      if (z.dir === 1 && L[i] <= z.top + ENTRY_BUFFER && L[i] >= z.bot) {
        const e = Math.max(L[i], z.top), x = z.bot - SL_BUFFER, r = e - x;
        if (r > 0 && r <= CAP) cands.push({ z, e, x, r, dir: 1 });
      }
      if (z.dir === -1 && H[i] >= z.bot - ENTRY_BUFFER && H[i] <= z.top) {
        const e = Math.min(H[i], z.bot), x = z.top + SL_BUFFER, r = x - e;
        if (r > 0 && r <= CAP) cands.push({ z, e, x, r, dir: -1 });
      }
    }

    // depurar: caducadas y consumidas por toque del borde exacto
    const alive = [];
    for (const z of zones) {
      if (z.born === i) { alive.push(z); continue; }
      if (i - z.born > maxAge) continue;
      if (z.dir === 1 && z.cleared && L[i] <= z.top) continue;
      if (z.dir === -1 && z.cleared && H[i] >= z.bot) continue;
      alive.push(z);
    }
    zones = alive;

    const inS = (M[i] >= 1080) || (M[i] < 660);
    let jo = false;
    if (inS && !open && cands.length) {
      cands.sort((a, b) => pick === 'riesgo' ? a.r - b.r : b.z.born - a.z.born);
      const c0 = cands[0];
      ep = c0.e; sl = c0.x; rk = c0.r; open = true; dir = c0.dir; eI = i; tp1 = false; mv = false; jo = true;
    }

    if (open) {
      const fav = jo ? (dir === 1 ? (C[i] > ep) : (C[i] < ep)) : true;
      const t1 = dir === 1 ? ep + rk * RR1 : ep - rk * RR1, t2 = dir === 1 ? ep + rk * RR2 : ep - rk * RR2;
      const hS = dir === 1 ? L[i] <= sl : H[i] >= sl;
      let cl = null;
      if (!tp1) {
        const h1 = fav && (dir === 1 ? H[i] >= t1 : L[i] <= t1);
        if (hS) cl = !mv ? 'full' : 'locked';
        else if (h1) { tp1 = true; const bl = dir === 1 ? ep + rk * LOCK : ep - rk * LOCK; if (!mv || (dir === 1 ? bl > sl : bl < sl)) sl = bl; mv = true; }
        else if (!mv && fav) { const re = dir === 1 ? (C[i] - ep) / rk : (ep - C[i]) / rk; if (re >= BETRIG) { sl = dir === 1 ? ep + rk * LOCK : ep - rk * LOCK; mv = true; } }
      } else {
        const h2 = fav && (dir === 1 ? H[i] >= t2 : L[i] <= t2);
        if (hS) cl = 'tp1be'; else if (h2) cl = 'runner';
      }
      if (cl) { tr.push({ e: eI, r: rk, kind: cl, mo: Mo[eI], dy: Dy[eI] }); open = false; }
    }
  }
  return tr.filter(t => D[t.e] !== 'Sun');
}

const segs = segment(raw.bars), nys = segs.map(ny);
function all(sb, multi, age, pick) { let a = []; segs.forEach((s, i) => { a = a.concat(run(s, nys[i], sb, multi, age, pick)); }); return a; }
function show(lab, tr) {
  const r = agg(tr);
  const h1 = agg(tr.filter(t => t.mo < SPLIT)), h2 = agg(tr.filter(t => t.mo >= SPLIT));
  console.log(lab.padEnd(30) + String(r.n).padStart(5) + ('$' + r.usd.toLocaleString('en-US')).padStart(11)
    + String(r.pf).padStart(7) + ('-$' + r.mdd.toLocaleString('en-US')).padStart(9) + (r.wr + '%').padStart(7)
    + (r.neg + '/' + r.mo).padStart(8) + ('   $' + h1.usd.toLocaleString('en-US') + ' / $' + h2.usd.toLocaleString('en-US')).padStart(24));
}

console.log('cabecera:  ops / neto / PF / maxDD / winRate / meses(-) / 1a mitad-2a mitad');
console.log('');
console.log('=== A) BUSCAR LA VELA DE ORIGEN MAS ATRAS (sigue 1 zona por lado) ===');
for (const sb of [10, 15, 20, 30]) show('obScanBars = ' + sb, all(sb, false, 99999, 'nueva'));

console.log('');
console.log('=== B) MANTENER VARIAS ZONAS VIVAS A LA VEZ (obScanBars = 10) ===');
show('actual: 1 zona por lado', all(10, false, 99999, 'nueva'));
for (const age of [50, 100, 200, 500]) show('multi, caduca a ' + age + ' velas', all(10, true, age, 'nueva'));

console.log('');
console.log('=== C) MULTI-ZONA: si varias se tocan a la vez, cual elegir ===');
show('la mas reciente (caduca 200)', all(10, true, 200, 'nueva'));
show('la de menor riesgo (cad. 200)', all(10, true, 200, 'riesgo'));

console.log('');
console.log('=== D) OPERACIONES POR DIA (config actual) ===');
const cur = all(10, false, 99999, 'nueva');
const perDay = {}; for (const t of cur) perDay[t.dy] = (perDay[t.dy] || 0) + 1;
const counts = {}; for (const d in perDay) counts[perDay[d]] = (counts[perDay[d]] || 0) + 1;
const days = Object.keys(perDay).length;
console.log('Dias con al menos una operacion: ' + days);
for (const k of Object.keys(counts).sort((a, b) => a - b)) console.log('   ' + k + ' operacion(es): ' + counts[k] + ' dias');
console.log('Promedio: ' + (cur.length / days).toFixed(2) + ' operaciones por dia operado');
console.log('Maximo en un solo dia: ' + Math.max(...Object.values(perDay)));

console.log('');
console.log('=== E) CURVA DE CADUCIDAD: se estanca o crece sin limite? ===');
for (const age of [100, 200, 300, 500, 1000, 2000, 99999]) {
  show((age === 99999 ? 'sin caducidad' : 'caduca a ' + age + ' velas'), all(10, true, age, 'nueva'));
}
console.log('');
console.log('(referencia: 96 velas de 15M = 1 dia; 480 = 1 semana de mercado)');
