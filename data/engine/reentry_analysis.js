const fs=require('fs');
const RISKCAP=100,BETRIG=1.2,RR1=1.8,RR2=4,DISP_MULT=2.5,DISP_CLOSE_FRAC=0.6,OB_SCAN=10;
const LIQ_LEN=12,LIQ_TOL=4,LIQ_ACCUM=6,SL_BUFFER=2,ENTRY_BUFFER=12;
const PV=2,CT=3,COMM=2.22,SEG=4*24*3600,SLIP=0.25,LOCK=0.8;
const raw=JSON.parse(fs.readFileSync('C:/Users/diazl/Downloads/mnq-ict-smc-bot/data/mnq_15m_bars.json','utf-8'));
function segment(b){const s=[];let st=0;for(let i=1;i<b.length;i++)if(b[i][0]-b[i-1][0]>SEG){s.push(b.slice(st,i));st=i;}s.push(b.slice(st));return s.filter(x=>x.length>200);}
const fmt=new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',year:'numeric',month:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false,weekday:'short'});
function ny(b){const n=b.length,M=new Int32Array(n),D=new Array(n),Mo=new Array(n);for(let i=0;i<n;i++){const p={};fmt.formatToParts(new Date(b[i][0]*1000)).forEach(x=>p[x.type]=x.value);M[i]=(+p.hour%24)*60+(+p.minute);D[i]=p.weekday;Mo[i]=p.year+'-'+p.month;}return{M,D,Mo};}
// blockAfterLossSameZone: prohibe re-entrar en la MISMA zona si la anterior fue perdida total
function run(bars,nya,lockR,mode,cd){
 const n=bars.length,O=new Float64Array(n),H=new Float64Array(n),L=new Float64Array(n),C=new Float64Array(n);
 for(let i=0;i<n;i++){O[i]=bars[i][1];H[i]=bars[i][2];L[i]=bars[i][3];C[i]=bars[i][4];}
 const avg=new Float64Array(n);let s=0;
 for(let i=0;i<n;i++){s+=H[i]-L[i];if(i>=20)s-=H[i-20]-L[i-20];avg[i]=i>=19?s/20:NaN;}
 const {M,D,Mo}=nya;
 let bT=NaN,bB=NaN,bF=false,bC=false,sT=NaN,sB=NaN,sF=false,sC=false;
 let bZ=0,sZ=0,zc=0;
 let open=false,dir=0,ep=0,sl=0,rk=0,eI=0,tp1=false,mv=false,curZ=null;
 const tr=[]; let lastExit=-9999,lastKind=null,lastZ=null; const bannedZones=new Set();
 for(let i=45;i<n;i++){
  const rng=H[i]-L[i],isD=rng>=DISP_MULT*avg[i-1];
  const bD=isD&&C[i]>O[i]&&(C[i]-L[i])>=DISP_CLOSE_FRAC*rng, sD=isD&&C[i]<O[i]&&(H[i]-C[i])>=DISP_CLOSE_FRAC*rng;
  let bN=false,sN=false,k,j,idx,cand,mx,cu;
  if(bD){idx=-1;for(k=1;k<=OB_SCAN;k++)if(C[i-k]<O[i-k]){idx=k;break;}
   if(idx>0){cand=L[i-idx];mx=0;cu=0;for(j=idx+1;j<=idx+LIQ_LEN;j++){if(i-j<0)break;if(L[i-j]<=cand+LIQ_TOL){cu++;if(cu>mx)mx=cu;}else cu=0;}
    if(mx<LIQ_ACCUM){bT=H[i-idx];bB=cand;bF=true;bC=false;bN=true;bZ=++zc;}}}
  if(sD){idx=-1;for(k=1;k<=OB_SCAN;k++)if(C[i-k]>O[i-k]){idx=k;break;}
   if(idx>0){cand=H[i-idx];mx=0;cu=0;for(j=idx+1;j<=idx+LIQ_LEN;j++){if(i-j<0)break;if(H[i-j]>=cand-LIQ_TOL){cu++;if(cu>mx)mx=cu;}else cu=0;}
    if(mx<LIQ_ACCUM){sT=cand;sB=L[i-idx];sF=true;sC=false;sN=true;sZ=++zc;}}}
  if(!bN&&bF&&!bC&&!isNaN(bT)&&L[i]>bT)bC=true;
  if(!sN&&sF&&!sC&&!isNaN(sB)&&H[i]<sB)sC=true;
  const bTou=!bN&&bC&&bF,sTou=!sN&&sC&&sF;
  if(!bN&&bC&&bF&&!isNaN(bT)&&L[i]<=bT)bF=false;
  if(!sN&&sC&&sF&&!isNaN(sB)&&H[i]>=sB)sF=false;
  const lz=bTou&&!isNaN(bT)&&L[i]<=bT+ENTRY_BUFFER&&L[i]>=bB;
  const sz=sTou&&!isNaN(sB)&&H[i]>=sB-ENTRY_BUFFER&&H[i]<=sT;
  let ce=((M[i]>=1080)||(M[i]<660))&&!open;
  if(mode==='cooldown'&&(i-lastExit)<cd) ce=false;
  let jo=false;
  if(ce&&lz&&!(mode==='banloss'&&bannedZones.has(bZ))){const e=Math.max(L[i],bT),x=bB-SL_BUFFER,r=e-x;
    if(!(r<=0||r>RISKCAP)){ep=e;sl=x;rk=r;open=true;dir=1;eI=i;tp1=false;mv=false;jo=true;curZ=bZ;}}
  if(ce&&sz&&!(mode==='banloss'&&bannedZones.has(sZ))){const e=Math.min(H[i],sB),x=sT+SL_BUFFER,r=x-e;
    if(!(r<=0||r>RISKCAP)){ep=e;sl=x;rk=r;open=true;dir=-1;eI=i;tp1=false;mv=false;jo=true;curZ=sZ;}}
  if(open){
   const fav=jo?(dir===1?(C[i]>ep):(C[i]<ep)):true;
   const t1=dir===1?ep+rk*RR1:ep-rk*RR1,t2=dir===1?ep+rk*RR2:ep-rk*RR2;
   const hS=dir===1?L[i]<=sl:H[i]>=sl;let cl=null;
   if(!tp1){const h1=fav&&(dir===1?H[i]>=t1:L[i]<=t1);
    if(hS)cl=!mv?'full':'locked';
    else if(h1){tp1=true;const bl=dir===1?ep+rk*lockR:ep-rk*lockR;if(!mv||(dir===1?bl>sl:bl<sl))sl=bl;mv=true;}
    else if(!mv&&fav){const re=dir===1?(C[i]-ep)/rk:(ep-C[i])/rk;if(re>=BETRIG){sl=dir===1?ep+rk*lockR:ep-rk*lockR;mv=true;}}
   } else {const h2=fav&&(dir===1?H[i]>=t2:L[i]<=t2);
    if(hS)cl='be_or_locked_after_tp1'; else if(h2)cl='runner';}
   if(cl){tr.push({e:eI,x:i,r:rk,kind:cl,mo:Mo[eI],zone:curZ,sameZone:curZ===lastZ,gap:eI-lastExit,prev:lastKind});
    if(cl==='full') bannedZones.add(curZ);
    open=false;lastExit=i;lastKind=cl;lastZ=curZ;}
  }
 }
 return tr.filter(t=>D[t.e]!=='Sun');
}
function usd(t,lk){const r=t.r,c=t.kind,sF=SLIP*CT*PV,s1=SLIP*PV;
 if(c==='full')return -CT*r*PV-COMM-sF; if(c==='locked')return CT*(lk*r*PV)-COMM-sF;
 if(c==='be_or_locked_after_tp1')return 2*(RR1*r*PV)+1*(lk*r*PV)-COMM-s1;
 return 2*(RR1*r*PV)+1*(RR2*r*PV)-COMM;}
function agg(tr,lk){let eq=0,gp=0,gl=0,pk=0,md=0,w=0;const bm={};
 for(const t of tr.slice().sort((a,b)=>a.e-b.e)){const u=usd(t,lk);if(u>0){gp+=u;w++}else gl-=u;eq+=u;if(eq>pk)pk=eq;if(pk-eq>md)md=pk-eq;bm[t.mo]=(bm[t.mo]||0)+u;}
 const mk=Object.keys(bm);
 return{n:tr.length,usd:Math.round(eq),pf:+(gp/gl).toFixed(2),mdd:Math.round(md),wr:+(100*w/tr.length).toFixed(1),neg:mk.filter(k=>bm[k]<0).length};}
const segs=segment(raw.bars),nys=segs.map(ny);
function all(m,cd){let a=[];segs.forEach((s,i)=>{a=a.concat(run(s,nys[i],LOCK,m,cd));});return a;}
const base=all('orig',0);
function stat(arr,label){ if(!arr.length){console.log(label.padEnd(40)+'   (0 casos)');return;}
  const u=arr.map(t=>usd(t,LOCK)),tot=u.reduce((a,b)=>a+b,0),w=u.filter(x=>x>0).length,f=arr.filter(t=>t.kind==='full').length;
  console.log(label.padEnd(40)+String(arr.length).padStart(4)+' ops  $'+String(Math.round(tot).toLocaleString('en-US')).padStart(8)
    +'  WR '+String((100*w/arr.length).toFixed(0)).padStart(3)+'%  perd.total '+String((100*f/arr.length).toFixed(0)).padStart(3)+'%  $/op '+String((tot/arr.length).toFixed(0)).padStart(5));}
console.log('=== LA PREGUNTA CLAVE: re-entrada en la MISMA zona, segun como cerro la ANTERIOR ===');
stat(base.filter(t=>t.sameZone&&t.prev==='full'),        'Misma zona, la anterior fue PERDIDA TOTAL');
stat(base.filter(t=>t.sameZone&&t.prev==='locked'),      'Misma zona, la anterior cerro en +0.8R');
stat(base.filter(t=>t.sameZone&&t.prev==='be_or_locked_after_tp1'),'Misma zona, la anterior hizo TP1');
stat(base.filter(t=>t.sameZone&&t.prev==='runner'),      'Misma zona, la anterior hizo TP2');
console.log('');
stat(base.filter(t=>!t.sameZone),                         'Zona nueva (referencia)');
console.log('');
console.log('=== CLUSTER MUY PEGADO (<=2 velas) segun cierre anterior ===');
stat(base.filter(t=>t.gap<=2&&t.prev==='full'),          '<=2 velas tras PERDIDA TOTAL');
stat(base.filter(t=>t.gap<=2&&t.prev!=='full'),          '<=2 velas tras cierre en ganancia');
console.log('');
console.log('=== VARIANTES DE ARREGLO ===');
console.log('variante                              ops      neto     PF     maxDD    WR   meses(-)');
for(const [lab,m,cd] of [['Actual (v13)','orig',0],['Prohibir re-entrada tras perdida total','banloss',0],
  ['Cooldown 2 velas','cooldown',2],['Cooldown 3 velas','cooldown',3]]){
  const a=agg(all(m,cd),LOCK);
  console.log(lab.padEnd(38)+String(a.n).padStart(4)+('$'+a.usd.toLocaleString('en-US')).padStart(11)
   +String(a.pf).padStart(7)+('-$'+a.mdd.toLocaleString('en-US')).padStart(9)+(a.wr+'%').padStart(7)+(a.neg+'/71').padStart(9));}
