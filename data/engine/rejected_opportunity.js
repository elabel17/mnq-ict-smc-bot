const fs=require('fs');
const BETRIG=1.2,RR1=1.8,RR2=4,LOCK=0.8,DISP_MULT=2.5,DISP_CLOSE_FRAC=0.6,OB_SCAN=10;
const LIQ_LEN=12,LIQ_TOL=4,LIQ_ACCUM=6,SL_BUFFER=2,ENTRY_BUFFER=12;
const PV=2,CT=3,COMM=2.22,SEG=4*24*3600,SLIP=0.25;
const raw=JSON.parse(fs.readFileSync('C:/Users/diazl/Downloads/mnq-ict-smc-bot/data/mnq_15m_bars.json','utf-8'));
function segment(b){const s=[];let st=0;for(let i=1;i<b.length;i++)if(b[i][0]-b[i-1][0]>SEG){s.push(b.slice(st,i));st=i;}s.push(b.slice(st));return s.filter(x=>x.length>200);}
const fmt=new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',hour:'2-digit',minute:'2-digit',hour12:false,weekday:'short'});
function ny(b){const n=b.length,M=new Int32Array(n),D=new Array(n);
 for(let i=0;i<n;i++){const p={};fmt.formatToParts(new Date(b[i][0]*1000)).forEach(x=>p[x.type]=x.value);
  M[i]=(+p.hour%24)*60+(+p.minute);D[i]=p.weekday;}return{M,D};}
function usd(kind,r){const sF=SLIP*CT*PV,s1=SLIP*PV;
 if(kind==='full')return -CT*r*PV-COMM-sF; if(kind==='locked')return CT*(LOCK*r*PV)-COMM-sF;
 if(kind==='tp1be')return 2*(RR1*r*PV)+1*(LOCK*r*PV)-COMM-s1;
 return 2*(RR1*r*PV)+1*(RR2*r*PV)-COMM;}
// simula una operacion aislada desde la barra de entrada (para valorar los rechazos)
function shadow(H,L,C,i0,dirv,ep,sl0,rk){
 let sl=sl0,tp1=false,mv=false;
 const t1=dirv===1?ep+rk*RR1:ep-rk*RR1, t2=dirv===1?ep+rk*RR2:ep-rk*RR2;
 for(let i=i0;i<Math.min(H.length,i0+3000);i++){
  const fav = i===i0 ? (dirv===1?(C[i]>ep):(C[i]<ep)) : true;
  const hS=dirv===1?L[i]<=sl:H[i]>=sl;
  if(!tp1){
   const h1=fav&&(dirv===1?H[i]>=t1:L[i]<=t1);
   if(hS) return mv?'locked':'full';
   if(h1){tp1=true;const bl=dirv===1?ep+rk*LOCK:ep-rk*LOCK;if(!mv||(dirv===1?bl>sl:bl<sl))sl=bl;mv=true;}
   else if(!mv&&fav){const re=dirv===1?(C[i]-ep)/rk:(ep-C[i])/rk;if(re>=BETRIG){sl=dirv===1?ep+rk*LOCK:ep-rk*LOCK;mv=true;}}
  } else {
   const h2=fav&&(dirv===1?H[i]>=t2:L[i]<=t2);
   if(hS) return 'tp1be';
   if(h2) return 'runner';
  }
 }
 return null;
}
function scan(bars,nya){
 const n=bars.length,O=new Float64Array(n),H=new Float64Array(n),L=new Float64Array(n),C=new Float64Array(n);
 for(let i=0;i<n;i++){O[i]=bars[i][1];H[i]=bars[i][2];L[i]=bars[i][3];C[i]=bars[i][4];}
 const avg=new Float64Array(n);let s=0;
 for(let i=0;i<n;i++){s+=H[i]-L[i];if(i>=20)s-=H[i-20]-L[i-20];avg[i]=i>=19?s/20:NaN;}
 const {M,D}=nya;
 let bT=NaN,bB=NaN,bF=false,bC=false,sT=NaN,sB=NaN,sF=false,sC=false;
 let open=false,dir=0,ep=0,sl=0,rk=0,tp1=false,mv=false;
 const rej=[];
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
  const inS=(M[i]>=1080)||(M[i]<660);
  const sun=D[i]==='Sun';
  if(lz){const e=Math.max(L[i],bT),x=bB-SL_BUFFER,r=e-x;
   let motivo=null;
   if(sun) motivo='DOMINGO';
   else if(!inS) motivo='FUERA DE SESION';
   else if(open) motivo='OPERACION ABIERTA';
   else if(r>100) motivo='STOP GRANDE';
   if(motivo){ if(r>0){const k2=shadow(H,L,C,i,1,e,x,r); if(k2) rej.push({motivo,kind:k2,r,u:usd(k2,r)});} }
   else {ep=e;sl=x;rk=r;open=true;dir=1;tp1=false;mv=false;}}
  if(sz){const e=Math.min(H[i],sB),x=sT+SL_BUFFER,r=x-e;
   let motivo=null;
   if(sun) motivo='DOMINGO';
   else if(!inS) motivo='FUERA DE SESION';
   else if(open) motivo='OPERACION ABIERTA';
   else if(r>100) motivo='STOP GRANDE';
   if(motivo){ if(r>0){const k2=shadow(H,L,C,i,-1,e,x,r); if(k2) rej.push({motivo,kind:k2,r,u:usd(k2,r)});} }
   else {ep=e;sl=x;rk=r;open=true;dir=-1;tp1=false;mv=false;}}
  if(open){
   const t1=dir===1?ep+rk*RR1:ep-rk*RR1,t2=dir===1?ep+rk*RR2:ep-rk*RR2;
   const hS=dir===1?L[i]<=sl:H[i]>=sl;
   if(!tp1){const h1=dir===1?H[i]>=t1:L[i]<=t1;
    if(hS)open=false;
    else if(h1){tp1=true;const bl=dir===1?ep+rk*LOCK:ep-rk*LOCK;if(!mv||(dir===1?bl>sl:bl<sl))sl=bl;mv=true;}
    else if(!mv){const re=dir===1?(C[i]-ep)/rk:(ep-C[i])/rk;if(re>=BETRIG){sl=dir===1?ep+rk*LOCK:ep-rk*LOCK;mv=true;}}
   } else {const h2=dir===1?H[i]>=t2:L[i]<=t2; if(hS||h2)open=false;}
  }
 }
 return rej;
}
const segs=segment(raw.bars),nys=segs.map(ny);
let rej=[];segs.forEach((s,i)=>{rej=rej.concat(scan(s,nys[i]));});
console.log('=== OPORTUNIDAD DEJADA PASAR, POR MOTIVO DE RECHAZO ===');
console.log('(cada toque rechazado simulado como si se hubiera operado, con slippage y comision)');
console.log('');
console.log('motivo               toques      neto     $/op   WR   perd.total');
const motivos=['FUERA DE SESION','OPERACION ABIERTA','STOP GRANDE','DOMINGO'];
for(const m of motivos){
 const g=rej.filter(x=>x.motivo===m); if(!g.length)continue;
 const tot=g.reduce((a,b)=>a+b.u,0), w=g.filter(x=>x.u>0).length, f=g.filter(x=>x.kind==='full').length;
 console.log(m.padEnd(20)+String(g.length).padStart(5)+('$'+Math.round(tot).toLocaleString('en-US')).padStart(11)
  +String((tot/g.length).toFixed(0)).padStart(7)+String((100*w/g.length).toFixed(0)+'%').padStart(6)+String((100*f/g.length).toFixed(0)+'%').padStart(11));
}
console.log('');
console.log('(Referencia: las 1.185 operaciones que SI se toman dan $129.295, o sea $109/op)');
console.log('');
const fs2=rej.filter(x=>x.motivo==='FUERA DE SESION');
console.log('=== DETALLE: los rechazados FUERA DE SESION, por hora NY de entrada ===');
console.log('(la sesion actual es 18:00-11:00 NY; estos ocurren entre 11:00 y 18:00)');
