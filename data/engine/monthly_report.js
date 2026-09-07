const fs=require('fs');
const RISKCAP=100,BETRIG=1.2,RR1=1.8,RR2=4,DISP_MULT=2.5,DISP_CLOSE_FRAC=0.6,OB_SCAN=10;
const LIQ_LEN=12,LIQ_TOL=4,LIQ_ACCUM=6,SL_BUFFER=2,ENTRY_BUFFER=12;
const PV=2,CT=3,COMM=2.22,SEG=4*24*3600,SLIP=0.25,LOCK=0.8;
const raw=JSON.parse(fs.readFileSync('C:/Users/diazl/Downloads/mnq-ict-smc-bot/data/mnq_15m_bars.json','utf-8'));
function segment(b){const s=[];let st=0;for(let i=1;i<b.length;i++)if(b[i][0]-b[i-1][0]>SEG){s.push(b.slice(st,i));st=i;}s.push(b.slice(st));return s.filter(x=>x.length>200);}
const fmt=new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',year:'numeric',month:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false,weekday:'short'});
function ny(b){const n=b.length,M=new Int32Array(n),D=new Array(n),Mo=new Array(n);for(let i=0;i<n;i++){const p={};fmt.formatToParts(new Date(b[i][0]*1000)).forEach(x=>p[x.type]=x.value);M[i]=(+p.hour%24)*60+(+p.minute);D[i]=p.weekday;Mo[i]=p.year+'-'+p.month;}return{M,D,Mo};}
function run(bars,nya,lockR){
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
  const ce=((M[i]>=1080)||(M[i]<660))&&!open;let jo=false;
  if(ce&&lz){const e=Math.max(L[i],bT),x=bB-SL_BUFFER,r=e-x;if(!(r<=0||r>RISKCAP)){ep=e;sl=x;rk=r;open=true;dir=1;eI=i;tp1=false;mv=false;jo=true;}}
  if(ce&&sz){const e=Math.min(H[i],sB),x=sT+SL_BUFFER,r=x-e;if(!(r<=0||r>RISKCAP)){ep=e;sl=x;rk=r;open=true;dir=-1;eI=i;tp1=false;mv=false;jo=true;}}
  if(open){
   const fav = jo ? (dir===1?(C[i]>ep):(C[i]<ep)) : true;
   const t1=dir===1?ep+rk*RR1:ep-rk*RR1, t2=dir===1?ep+rk*RR2:ep-rk*RR2;
   const hS=dir===1?L[i]<=sl:H[i]>=sl;
   if(!tp1){
    const h1=fav&&(dir===1?H[i]>=t1:L[i]<=t1);
    if(hS){tr.push({e:eI,r:rk,kind:!mv?'full':'locked',mo:Mo[eI]});open=false;}
    else if(h1){tp1=true;const bl=dir===1?ep+rk*lockR:ep-rk*lockR;if(!mv||(dir===1?bl>sl:bl<sl))sl=bl;mv=true;}
    else if(!mv&&fav){const re=dir===1?(C[i]-ep)/rk:(ep-C[i])/rk;
      if(re>=BETRIG){sl=dir===1?ep+rk*lockR:ep-rk*lockR;mv=true;}}
   } else {
    const h2=fav&&(dir===1?H[i]>=t2:L[i]<=t2);
    if(hS){tr.push({e:eI,r:rk,kind:'be_or_locked_after_tp1',mo:Mo[eI]});open=false;}
    else if(h2){tr.push({e:eI,r:rk,kind:'runner',mo:Mo[eI]});open=false;}}
  }
 }
 return tr.filter(t=>D[t.e]!=='Sun');
}
function usd(t,lk){const r=t.r,c=t.kind,sF=SLIP*CT*PV,s1=SLIP*PV;
 if(c==='full')return -CT*r*PV-COMM-sF; if(c==='befirst')return -COMM-sF;
 if(c==='locked')return CT*(lk*r*PV)-COMM-sF;
 if(c==='be_or_locked_after_tp1')return 2*(RR1*r*PV)+1*(lk*r*PV)-COMM-s1;
 return 2*(RR1*r*PV)+1*(RR2*r*PV)-COMM;}
const segs=segment(raw.bars),nys=segs.map(ny);
let all=[];segs.forEach((s,i)=>{all=all.concat(run(s,nys[i],LOCK));});
const bm={},bc={};
for(const t of all){const u=usd(t,LOCK);bm[t.mo]=(bm[t.mo]||0)+u;bc[t.mo]=(bc[t.mo]||0)+1;}
const MN=['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic'];
const years=[...new Set(Object.keys(bm).map(k=>k.slice(0,4)))].sort();
console.log('RESULTADOS MENSUALES - lock=0.8R, modelo realista (bot por cierre de vela, slippage 1 tick, comision incluida)');
console.log('MNQ 3 contratos, capital 50k');
console.log('');
let hdr='Mes   '; for(const y of years) hdr+=y.padStart(11); console.log(hdr+'   TOTAL mes');
for(let m=1;m<=12;m++){
  const mm=String(m).padStart(2,'0');
  let line=MN[m-1].padEnd(6); let rowTot=0, any=false;
  for(const y of years){ const k=y+'-'+mm; if(bm[k]!==undefined){ line+=('$'+Math.round(bm[k]).toLocaleString('en-US')).padStart(11); rowTot+=bm[k]; any=true;} else line+='-'.padStart(11); }
  console.log(line+(any?('$'+Math.round(rowTot).toLocaleString('en-US')).padStart(12):''));
}
let tl='TOTAL '; let g=0;
for(const y of years){ let ty=0; for(let m=1;m<=12;m++){const k=y+'-'+String(m).padStart(2,'0'); if(bm[k])ty+=bm[k];} tl+=('$'+Math.round(ty).toLocaleString('en-US')).padStart(11); g+=ty; }
console.log(''.padEnd(80,'-'));
console.log(tl+('$'+Math.round(g).toLocaleString('en-US')).padStart(12));
console.log('');
const negs=Object.keys(bm).filter(k=>bm[k]<0).sort();
console.log('Meses negativos ('+negs.length+' de '+Object.keys(bm).length+'):');
for(const k of negs) console.log('   '+k+'  $'+Math.round(bm[k]).toLocaleString('en-US')+'   ('+bc[k]+' operaciones)');
const vals=Object.keys(bm).map(k=>bm[k]).sort((a,b)=>a-b);
console.log('');
console.log('Mejor mes:  $'+Math.round(vals[vals.length-1]).toLocaleString('en-US'));
console.log('Peor mes:   $'+Math.round(vals[0]).toLocaleString('en-US'));
console.log('Mediana:    $'+Math.round(vals[Math.floor(vals.length/2)]).toLocaleString('en-US'));
console.log('Promedio:   $'+Math.round(vals.reduce((a,b)=>a+b,0)/vals.length).toLocaleString('en-US')+'/mes');
