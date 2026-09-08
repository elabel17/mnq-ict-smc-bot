const fs=require('fs');
const BETRIG=1.2,RR1=1.8,RR2=4,LOCK=0.8,DISP_MULT=2.5,DISP_CLOSE_FRAC=0.6,OB_SCAN=10;
const LIQ_LEN=12,LIQ_TOL=4,LIQ_ACCUM=6,SL_BUFFER=2,ENTRY_BUFFER=12;
const PV=2,CT=3,COMM=2.22,SEG=4*24*3600,SLIP=0.25;
const raw=JSON.parse(fs.readFileSync('C:/Users/diazl/Downloads/mnq-ict-smc-bot/data/mnq_15m_bars.json','utf-8'));
function segment(b){const s=[];let st=0;for(let i=1;i<b.length;i++)if(b[i][0]-b[i-1][0]>SEG){s.push(b.slice(st,i));st=i;}s.push(b.slice(st));return s.filter(x=>x.length>200);}
const fmt=new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',year:'numeric',month:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false,weekday:'short'});
function ny(b){const n=b.length,M=new Int32Array(n),D=new Array(n),Mo=new Array(n);
 for(let i=0;i<n;i++){const p={};fmt.formatToParts(new Date(b[i][0]*1000)).forEach(x=>p[x.type]=x.value);
  M[i]=(+p.hour%24)*60+(+p.minute);D[i]=p.weekday;Mo[i]=p.year+'-'+p.month;}return{M,D,Mo};}
function run(bars,nya,cap,session){
 const n=bars.length,O=new Float64Array(n),H=new Float64Array(n),L=new Float64Array(n),C=new Float64Array(n);
 for(let i=0;i<n;i++){O[i]=bars[i][1];H[i]=bars[i][2];L[i]=bars[i][3];C[i]=bars[i][4];}
 const avg=new Float64Array(n);let s=0;
 for(let i=0;i<n;i++){s+=H[i]-L[i];if(i>=20)s-=H[i-20]-L[i-20];avg[i]=i>=19?s/20:NaN;}
 const {M,D,Mo}=nya;
 let bT=NaN,bB=NaN,bF=false,bC=false,sT=NaN,sB=NaN,sF=false,sC=false;
 let open=false,dir=0,ep=0,sl=0,rk=0,eI=0,tp1=false,mv=false;const tr=[];
 for(let i=45;i<n;i++){
  const rng=H[i]-L[i],isD=rng>=DISP_MULT*avg[i-1];
  const bD=isD&&C[i]>O[i]&&(C[i]-L[i])>=DISP_CLOSE_FRAC*rng, sD=isD&&C[i]<O[i]&&(H[i]-C[i])>=DISP_CLOSE_FRAC*rng;
  let bN=false,sN=false,k,j,idx,cand,mx,cu;
  if(bD){idx=-1;for(k=1;k<=OB_SCAN;k++)if(C[i-k]<O[i-k]){idx=k;break;}
   if(idx>0){cand=L[i-idx];mx=0;cu=0;for(j=idx+1;j<=idx+LIQ_LEN;j++){if(i-j<0)break;if(L[i-j]<=cand+LIQ_TOL){cu++;if(cu>mx)mx=cu;}else cu=0;}
    if(mx<LIQ_ACCUM){bT=H[i-idx];bB=cand;bF=true;bC=false;bN=true;}}}
  if(sD){idx=-1;for(k=1;k<=OB_SCAN;k++)if(C[i-k]>O[i-k]){idx=k;break;}
   if(idx>0){cand=H[i-idx];mx=0;cu=0;for(j=idx+1;j<=idx+LIQ_LEN;j++){if(i-j<0)break;if(H[i-j]>=cand-LIQ_TOL){cu++;if(cu>mx)mx=cu;}else cu=0;}
    if(mx<LIQ_ACCUM){sT=cand;sB=L[i-idx];sF=true;sC=false;sN=true;}}}
  if(!bN&&bF&&!bC&&!isNaN(bT)&&L[i]>bT)bC=true;
  if(!sN&&sF&&!sC&&!isNaN(sB)&&H[i]<sB)sC=true;
  const bTou=!bN&&bC&&bF,sTou=!sN&&sC&&sF;
  if(!bN&&bC&&bF&&!isNaN(bT)&&L[i]<=bT)bF=false;
  if(!sN&&sC&&sF&&!isNaN(sB)&&H[i]>=sB)sF=false;
  const lz=bTou&&!isNaN(bT)&&L[i]<=bT+ENTRY_BUFFER&&L[i]>=bB;
  const sz=sTou&&!isNaN(sB)&&H[i]>=sB-ENTRY_BUFFER&&H[i]<=sT;
  let inS;
  if(session==='actual') inS=(M[i]>=1080)||(M[i]<660);
  else if(session==='24h') inS=true;
  else if(session==='sin_tarde') inS=(M[i]>=1080)||(M[i]<780); // 18:00-13:00
  else if(session==='solo_ny') inS=(M[i]>=570&&M[i]<960);      // 09:30-16:00
  const ce=inS&&!open;let jo=false;
  if(ce&&lz){const e=Math.max(L[i],bT),x=bB-SL_BUFFER,r=e-x;if(!(r<=0||r>cap)){ep=e;sl=x;rk=r;open=true;dir=1;eI=i;tp1=false;mv=false;jo=true;}}
  if(ce&&sz){const e=Math.min(H[i],sB),x=sT+SL_BUFFER,r=x-e;if(!(r<=0||r>cap)){ep=e;sl=x;rk=r;open=true;dir=-1;eI=i;tp1=false;mv=false;jo=true;}}
  if(open){
   const fav=jo?(dir===1?(C[i]>ep):(C[i]<ep)):true;
   const t1=dir===1?ep+rk*RR1:ep-rk*RR1,t2=dir===1?ep+rk*RR2:ep-rk*RR2;
   const hS=dir===1?L[i]<=sl:H[i]>=sl;let cl=null;
   if(!tp1){const h1=fav&&(dir===1?H[i]>=t1:L[i]<=t1);
    if(hS)cl=!mv?'full':'locked';
    else if(h1){tp1=true;const bl=dir===1?ep+rk*LOCK:ep-rk*LOCK;if(!mv||(dir===1?bl>sl:bl<sl))sl=bl;mv=true;}
    else if(!mv&&fav){const re=dir===1?(C[i]-ep)/rk:(ep-C[i])/rk;if(re>=BETRIG){sl=dir===1?ep+rk*LOCK:ep-rk*LOCK;mv=true;}}
   } else {const h2=fav&&(dir===1?H[i]>=t2:L[i]<=t2);
    if(hS)cl='tp1be'; else if(h2)cl='runner';}
   if(cl){tr.push({e:eI,r:rk,kind:cl,mo:Mo[eI]});open=false;}
  }
 }
 return tr.filter(t=>D[t.e]!=='Sun');
}
function usd(t){const r=t.r,c=t.kind,sF=SLIP*CT*PV,s1=SLIP*PV;
 if(c==='full')return -CT*r*PV-COMM-sF; if(c==='locked')return CT*(LOCK*r*PV)-COMM-sF;
 if(c==='tp1be')return 2*(RR1*r*PV)+1*(LOCK*r*PV)-COMM-s1;
 return 2*(RR1*r*PV)+1*(RR2*r*PV)-COMM;}
function agg(tr){let eq=0,gp=0,gl=0,pk=0,md=0,w=0;const bm={};
 for(const t of tr.slice().sort((a,b)=>a.e-b.e)){const u=usd(t);if(u>0){gp+=u;w++}else gl-=u;eq+=u;if(eq>pk)pk=eq;if(pk-eq>md)md=pk-eq;bm[t.mo]=(bm[t.mo]||0)+u;}
 const mk=Object.keys(bm);
 return{n:tr.length,usd:Math.round(eq),pf:+(gp/gl).toFixed(2),mdd:Math.round(md),wr:+(100*w/tr.length).toFixed(1),neg:mk.filter(k=>bm[k]<0).length,mo:mk.length};}
const segs=segment(raw.bars),nys=segs.map(ny);
function all(cap,ses){let a=[];segs.forEach((s,i)=>{a=a.concat(run(s,nys[i],cap,ses));});return agg(a);}
const SPLIT='2023-09';
function allSplit(cap,ses){let a=[];segs.forEach((s,i)=>{a=a.concat(run(s,nys[i],cap,ses));});
 const h1=a.filter(t=>t.mo<SPLIT),h2=a.filter(t=>t.mo>=SPLIT);return{h1:agg(h1),h2:agg(h2),all:agg(a)};}
console.log('=== VALIDACION EN DOS MITADES (corte '+SPLIT+') ===');
console.log('config                  1a mitad 2020-11..2023-08   2a mitad 2023-09..2026-09       TOTAL');
for(const [lab,c,s] of [['actual 100 / 18-11',100,'actual'],['tope 120 / 18-11',120,'actual'],['tope 150 / 18-11',150,'actual'],['tope 100 / 24h',100,'24h'],['tope 120 / 24h',120,'24h'],['tope 150 / 24h',150,'24h']]){
 const r=allSplit(c,s);
 console.log(lab.padEnd(22)+('$'+r.h1.usd.toLocaleString('en-US')+' PF'+r.h1.pf+' DD-$'+r.h1.mdd.toLocaleString('en-US')).padStart(30)+('  $'+r.h2.usd.toLocaleString('en-US')+' PF'+r.h2.pf+' DD-$'+r.h2.mdd.toLocaleString('en-US')).padStart(30)+('  $'+r.all.usd.toLocaleString('en-US')).padStart(12));}
console.log('');
console.log('=== A) AMPLIAR EL TOPE DE RIESGO (sesion actual 18:00-11:00) ===');
console.log('tope           ops      neto     PF     maxDD    WR   meses(-)');
for(const c of [100,120,150,200,99999]){
 const r=all(c,'actual');
 console.log((c===99999?'sin tope':(c+' pts')).padEnd(14)+String(r.n).padStart(5)+('$'+r.usd.toLocaleString('en-US')).padStart(11)
  +String(r.pf).padStart(7)+('-$'+r.mdd.toLocaleString('en-US')).padStart(9)+(r.wr+'%').padStart(7)+(r.neg+'/'+r.mo).padStart(9));}
console.log('');
console.log('=== B) AMPLIAR LA SESION (tope 100 pts) ===');
console.log('sesion                 ops      neto     PF     maxDD    WR   meses(-)');
for(const [lab,s] of [['18:00-11:00 (actual)','actual'],['18:00-13:00','sin_tarde'],['24 horas','24h'],['solo NY 09:30-16:00','solo_ny']]){
 const r=all(100,s);
 console.log(lab.padEnd(22)+String(r.n).padStart(5)+('$'+r.usd.toLocaleString('en-US')).padStart(11)
  +String(r.pf).padStart(7)+('-$'+r.mdd.toLocaleString('en-US')).padStart(9)+(r.wr+'%').padStart(7)+(r.neg+'/'+r.mo).padStart(9));}
console.log('');
console.log('=== C) COMBINADO: 24 horas + tope ampliado ===');
console.log('config                 ops      neto     PF     maxDD    WR   meses(-)');
for(const [lab,c,s] of [['actual (100 / 18-11)',100,'actual'],['24h + tope 100',100,'24h'],
  ['24h + tope 150',150,'24h'],['24h + sin tope',99999,'24h'],['18-11 + tope 150',150,'actual']]){
 const r=all(c,s);
 console.log(lab.padEnd(22)+String(r.n).padStart(5)+('$'+r.usd.toLocaleString('en-US')).padStart(11)
  +String(r.pf).padStart(7)+('-$'+r.mdd.toLocaleString('en-US')).padStart(9)+(r.wr+'%').padStart(7)+(r.neg+'/'+r.mo).padStart(9));}
