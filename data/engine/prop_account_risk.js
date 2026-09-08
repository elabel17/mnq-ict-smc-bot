const fs=require('fs');
const BETRIG=1.2,RR1=1.8,RR2=4,LOCK=0.8,DISP_MULT=2.5,DISP_CLOSE_FRAC=0.6;
const LIQ_LEN=12,LIQ_TOL=4,LIQ_ACCUM=6,SL_BUFFER=2,ENTRY_BUFFER=12,CAP=100,MAXAGE=300;
const PV=2,COMM_PC=0.74,SEG=4*24*3600,SLIP=0.25;
const raw=JSON.parse(fs.readFileSync('C:/Users/diazl/Downloads/mnq-ict-smc-bot/data/mnq_15m_bars.json','utf-8'));
function segment(b){const s=[];let st=0;for(let i=1;i<b.length;i++)if(b[i][0]-b[i-1][0]>SEG){s.push(b.slice(st,i));st=i;}s.push(b.slice(st));return s.filter(x=>x.length>200);}
const fmt=new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false,weekday:'short'});
function ny(b){const n=b.length,M=new Int32Array(n),D=new Array(n),Dy=new Array(n);
 for(let i=0;i<n;i++){const p={};fmt.formatToParts(new Date(b[i][0]*1000)).forEach(x=>p[x.type]=x.value);
  M[i]=(+p.hour%24)*60+(+p.minute);D[i]=p.weekday;Dy[i]=p.year+'-'+p.month+'-'+p.day;}return{M,D,Dy};}
function run(bars,nya){
 const n=bars.length,O=new Float64Array(n),H=new Float64Array(n),L=new Float64Array(n),C=new Float64Array(n);
 for(let i=0;i<n;i++){O[i]=bars[i][1];H[i]=bars[i][2];L[i]=bars[i][3];C[i]=bars[i][4];}
 const avg=new Float64Array(n);let s=0;
 for(let i=0;i<n;i++){s+=H[i]-L[i];if(i>=20)s-=H[i-20]-L[i-20];avg[i]=i>=19?s/20:NaN;}
 const {M,D,Dy}=nya;
 let zones=[],open=false,dir=0,ep=0,sl=0,rk=0,eI=0,tp1=false,mv=false,mae=0;const tr=[];
 for(let i=45;i<n;i++){
  const rng=H[i]-L[i],isD=rng>=DISP_MULT*avg[i-1];
  const bD=isD&&C[i]>O[i]&&(C[i]-L[i])>=DISP_CLOSE_FRAC*rng;
  const sD=isD&&C[i]<O[i]&&(H[i]-C[i])>=DISP_CLOSE_FRAC*rng;
  let k,j,idx,cand,mx,cu;
  if(bD){idx=-1;for(k=1;k<=10;k++){if(i-k<0)break;if(C[i-k]<O[i-k]){idx=k;break;}}
   if(idx>0){cand=L[i-idx];mx=0;cu=0;for(j=idx+1;j<=idx+LIQ_LEN;j++){if(i-j<0)break;if(L[i-j]<=cand+LIQ_TOL){cu++;if(cu>mx)mx=cu;}else cu=0;}
    if(mx<LIQ_ACCUM)zones.push({dir:1,top:H[i-idx],bot:cand,cleared:false,born:i});}}
  if(sD){idx=-1;for(k=1;k<=10;k++){if(i-k<0)break;if(C[i-k]>O[i-k]){idx=k;break;}}
   if(idx>0){cand=H[i-idx];mx=0;cu=0;for(j=idx+1;j<=idx+LIQ_LEN;j++){if(i-j<0)break;if(H[i-j]>=cand-LIQ_TOL){cu++;if(cu>mx)mx=cu;}else cu=0;}
    if(mx<LIQ_ACCUM)zones.push({dir:-1,top:cand,bot:L[i-idx],cleared:false,born:i});}}
  for(const z of zones){if(z.born===i)continue;
   if(z.dir===1){if(!z.cleared&&L[i]>z.top)z.cleared=true;}else{if(!z.cleared&&H[i]<z.bot)z.cleared=true;}}
  let best=null;
  for(const z of zones){
   if(z.born===i||i-z.born>MAXAGE||!z.cleared)continue;
   if(z.dir===1&&L[i]<=z.top+ENTRY_BUFFER&&L[i]>=z.bot){const e=Math.max(L[i],z.top),x=z.bot-SL_BUFFER,r=e-x;
     if(r>0&&r<=CAP&&(!best||z.born>best.born))best={e,x,r,dir:1,born:z.born};}
   if(z.dir===-1&&H[i]>=z.bot-ENTRY_BUFFER&&H[i]<=z.top){const e=Math.min(H[i],z.bot),x=z.top+SL_BUFFER,r=x-e;
     if(r>0&&r<=CAP&&(!best||z.born>best.born))best={e,x,r,dir:-1,born:z.born};}}
  const alive=[];
  for(const z of zones){if(z.born===i){alive.push(z);continue;}
   if(i-z.born>MAXAGE)continue;
   if(z.dir===1&&z.cleared&&L[i]<=z.top)continue;
   if(z.dir===-1&&z.cleared&&H[i]>=z.bot)continue;
   alive.push(z);}
  zones=alive;
  const inS=(M[i]>=1080)||(M[i]<660);let jo=false;
  if(inS&&!open&&best){ep=best.e;sl=best.x;rk=best.r;open=true;dir=best.dir;eI=i;tp1=false;mv=false;mae=0;jo=true;}
  if(open){
   const adv = dir===1 ? (ep-L[i]) : (H[i]-ep);   // excursion adversa en puntos
   if(adv>mae) mae=adv;
   const fav=jo?(dir===1?(C[i]>ep):(C[i]<ep)):true;
   const t1=dir===1?ep+rk*RR1:ep-rk*RR1,t2=dir===1?ep+rk*RR2:ep-rk*RR2;
   const hS=dir===1?L[i]<=sl:H[i]>=sl;let cl=null;
   if(!tp1){const h1=fav&&(dir===1?H[i]>=t1:L[i]<=t1);
    if(hS)cl=!mv?'full':'locked';
    else if(h1){tp1=true;const bl=dir===1?ep+rk*LOCK:ep-rk*LOCK;if(!mv||(dir===1?bl>sl:bl<sl))sl=bl;mv=true;}
    else if(!mv&&fav){const re=dir===1?(C[i]-ep)/rk:(ep-C[i])/rk;if(re>=BETRIG){sl=dir===1?ep+rk*LOCK:ep-rk*LOCK;mv=true;}}
   } else {const h2=fav&&(dir===1?H[i]>=t2:L[i]<=t2);
    if(hS)cl='tp1be'; else if(h2)cl='runner';}
   if(cl){tr.push({e:eI,r:rk,kind:cl,dy:Dy[eI],mae:Math.min(mae,rk)});open=false;}}
 }
 return tr.filter(t=>D[t.e]!=='Sun');
}
const segs=segment(raw.bars),nys=segs.map(ny);
let all=[];segs.forEach((s,i)=>{all=all.concat(run(s,nys[i]));});
function usd(t,ct){const r=t.r,c=t.kind,sF=SLIP*ct*PV,s1=SLIP*(ct/3)*PV,COMM=COMM_PC*ct;
 const n2=Math.round(ct*2/3), n1=ct-n2;
 if(c==='full')return -ct*r*PV-COMM-sF;
 if(c==='locked')return ct*(LOCK*r*PV)-COMM-sF;
 if(c==='tp1be')return n2*(RR1*r*PV)+n1*(LOCK*r*PV)-COMM-s1;
 return n2*(RR1*r*PV)+n1*(RR2*r*PV)-COMM;}
console.log('ANALISIS PARA CUENTA DE FONDEO — config v15 (multi-zona 300)');
console.log('Modelo conservador: disparo por cierre de vela, slippage y comision incluidos.');
console.log('');
console.log('contratos   neto      peor dia   2o peor  3er peor   maxDD cerrado   maxDD con flotante   riesgo max/op');
for(const ct of [1,2,3]){
  const byDay={};
  for(const t of all){byDay[t.dy]=(byDay[t.dy]||0)+usd(t,ct);}
  const days=Object.values(byDay).sort((a,b)=>a-b);
  // equity cerrada
  let eq=0,pk=0,md=0;
  const sorted=all.slice().sort((a,b)=>a.e-b.e);
  for(const t of sorted){eq+=usd(t,ct);if(eq>pk)pk=eq;if(pk-eq>md)md=pk-eq;}
  // equity incluyendo la peor excursion flotante de cada operacion
  let eq2=0,pk2=0,md2=0;
  for(const t of sorted){
    const dip=eq2-(t.mae*ct*PV);        // punto mas bajo mientras la operacion vivia
    if(pk2-dip>md2)md2=pk2-dip;
    eq2+=usd(t,ct); if(eq2>pk2)pk2=eq2; if(pk2-eq2>md2)md2=pk2-eq2;}
  const total=all.reduce((a,t)=>a+usd(t,ct),0);
  console.log(String(ct).padEnd(11)+('$'+Math.round(total).toLocaleString('en-US')).padStart(9)
   +('$'+Math.round(days[0]).toLocaleString('en-US')).padStart(11)
   +('$'+Math.round(days[1]).toLocaleString('en-US')).padStart(10)
   +('$'+Math.round(days[2]).toLocaleString('en-US')).padStart(10)
   +('-$'+Math.round(md).toLocaleString('en-US')).padStart(16)
   +('-$'+Math.round(md2).toLocaleString('en-US')).padStart(21)
   +('$'+Math.round(CAP*ct*PV)).padStart(15));
}
console.log('');
console.log('=== DISTRIBUCION DE DIAS PERDEDORES (3 contratos) ===');
const byDay3={};for(const t of all){byDay3[t.dy]=(byDay3[t.dy]||0)+usd(t,3);}
const d3=Object.values(byDay3);
const neg=d3.filter(x=>x<0).sort((a,b)=>a-b);
console.log('Dias operados: '+d3.length+'   dias en perdida: '+neg.length+' ('+(100*neg.length/d3.length).toFixed(0)+'%)');
for(const lim of [500,750,1000,1500,2000]){
  const c=neg.filter(x=>x<=-lim).length;
  console.log('  dias con perdida >= $'+lim+': '+c+'  ('+(100*c/d3.length).toFixed(2)+'% de los dias operados)');
}
