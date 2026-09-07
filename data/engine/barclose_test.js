// Variante: el disparador de 1.2R solo se detecta al CIERRE de vela (bot que
// actua por cierre de vela, como las alertas configuradas), no al tick.
const fs=require('fs'), path=require('path');
const RISKCAP=100,BETRIG=1.2,RR1=1.8,RR2=4,DISP_MULT=2.5,DISP_CLOSE_FRAC=0.6,OB_SCAN=10;
const LIQ_LEN=12,LIQ_TOL=4,LIQ_ACCUM=6,SL_BUFFER=2,ENTRY_BUFFER=12;
const PV=2,CT=3,COMM=2.22,SEG=4*24*3600,SLIP=0.25;
const raw=JSON.parse(fs.readFileSync('C:/Users/diazl/Downloads/mnq-ict-smc-bot/data/mnq_15m_bars.json','utf-8'));
function segment(b){const s=[];let st=0;for(let i=1;i<b.length;i++)if(b[i][0]-b[i-1][0]>SEG){s.push(b.slice(st,i));st=i;}s.push(b.slice(st));return s.filter(x=>x.length>200);}
const fmt=new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',year:'numeric',month:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false,weekday:'short'});
function ny(b){const n=b.length,M=new Int32Array(n),D=new Array(n),Mo=new Array(n);for(let i=0;i<n;i++){const p={};fmt.formatToParts(new Date(b[i][0]*1000)).forEach(x=>p[x.type]=x.value);M[i]=(+p.hour%24)*60+(+p.minute);D[i]=p.weekday;Mo[i]=p.year+'-'+p.month;}return{M,D,Mo};}
function run(bars,nya,lockR,closeTrigger){
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
    if(hS){tr.push({e:eI,r:rk,kind:!mv?'full':(lockR>0?'locked':'befirst'),mo:Mo[eI]});open=false;}
    else if(h1){tp1=true;const bl=dir===1?ep+rk*lockR:ep-rk*lockR;if(!mv||(dir===1?bl>sl:bl<sl))sl=bl;mv=true;}
    else if(!mv&&fav){
      // AQUI la diferencia: el disparador usa el CIERRE en vez del extremo
      const re = closeTrigger ? (dir===1?(C[i]-ep)/rk:(ep-C[i])/rk) : (dir===1?(H[i]-ep)/rk:(ep-L[i])/rk);
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
function agg(tr,lk){let eq=0,gp=0,gl=0,pk=0,md=0,w=0;const bm={};
 for(const t of tr.slice().sort((a,b)=>a.e-b.e)){const u=usd(t,lk);if(u>0){gp+=u;w++}else gl-=u;eq+=u;if(eq>pk)pk=eq;if(pk-eq>md)md=pk-eq;bm[t.mo]=(bm[t.mo]||0)+u;}
 const mk=Object.keys(bm);
 return{n:tr.length,usd:Math.round(eq),pf:+(gp/gl).toFixed(2),mdd:Math.round(md),wr:+(100*w/tr.length).toFixed(1),neg:mk.filter(k=>bm[k]<0).length,mo:mk.length};}
const segs=segment(raw.bars),nys=segs.map(ny);
function all(lk,ct){let a=[];segs.forEach((s,i)=>{a=a.concat(run(s,nys[i],lk,ct));});return a;}
console.log('=== BOT POR CIERRE DE VELA vs BOT AL TICK (modo intra-vela realista + slippage) ===');
console.log('lock     al tick    por cierre    diferencia');
for(const l of [0,0.5,0.6,0.8,0.9,1.0,1.2]){
 const a=agg(all(l,false),l), b=agg(all(l,true),l);
 console.log(String(l).padEnd(6)+('$'+a.usd.toLocaleString('en-US')).padStart(11)+('$'+b.usd.toLocaleString('en-US')).padStart(13)+((((b.usd-a.usd)/a.usd*100).toFixed(1))+'%').padStart(13));
}
console.log('');
console.log('=== DETALLE - bot por cierre de vela (lo que realmente puede ejecutar tu setup) ===');
console.log('lock   trades      neto     PF     maxDD   winRate  meses(-)');
for(const l of [0,0.5,0.6,0.8,0.9,1.0]){
 const b=agg(all(l,true),l);
 console.log(String(l).padEnd(6)+String(b.n).padStart(6)+('$'+b.usd.toLocaleString('en-US')).padStart(11)+String(b.pf).padStart(7)+('-$'+b.mdd.toLocaleString('en-US')).padStart(10)+((b.wr)+'%').padStart(9)+(b.neg+'/'+b.mo).padStart(10));
}
