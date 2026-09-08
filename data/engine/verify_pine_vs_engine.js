const fs=require('fs');
const BETRIG=1.2,RR1=1.8,RR2=4,LOCK=0.8,DISP_MULT=2.5,DISP_CLOSE_FRAC=0.6;
const LIQ_LEN=12,LIQ_TOL=4,LIQ_ACCUM=6,SL_BUFFER=2,ENTRY_BUFFER=12,CAP=100,MAXAGE=300;
const SEG=4*24*3600;
const raw=JSON.parse(fs.readFileSync('C:/Users/diazl/Downloads/mnq-ict-smc-bot/data/mnq_15m_bars.json','utf-8'));
function segment(b){const s=[];let st=0;for(let i=1;i<b.length;i++)if(b[i][0]-b[i-1][0]>SEG){s.push(b.slice(st,i));st=i;}s.push(b.slice(st));return s.filter(x=>x.length>200);}
const fmt=new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false,weekday:'short'});
function ny(b){const n=b.length,M=new Int32Array(n),D=new Array(n),S=new Array(n);
 for(let i=0;i<n;i++){const p={};fmt.formatToParts(new Date(b[i][0]*1000)).forEach(x=>p[x.type]=x.value);
  M[i]=(+p.hour%24)*60+(+p.minute);D[i]=p.weekday;S[i]=p.year+'-'+p.month+'-'+p.day+' '+p.hour+':'+p.minute;}return{M,D,S};}
// intrabar=true reproduce EXACTAMENTE el Pine (disparo del 1.2R con el extremo de la vela)
function run(bars,nya,intrabar){
 const n=bars.length,O=new Float64Array(n),H=new Float64Array(n),L=new Float64Array(n),C=new Float64Array(n);
 for(let i=0;i<n;i++){O[i]=bars[i][1];H[i]=bars[i][2];L[i]=bars[i][3];C[i]=bars[i][4];}
 const avg=new Float64Array(n);let s=0;
 for(let i=0;i<n;i++){s+=H[i]-L[i];if(i>=20)s-=H[i-20]-L[i-20];avg[i]=i>=19?s/20:NaN;}
 const {M,D,S}=nya;
 let zones=[],open=false,dir=0,ep=0,sl=0,rk=0,eI=0,tp1=false,mv=false;const tr=[];
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
  for(const z of zones){
   if(z.born===i){alive.push(z);continue;}
   if(i-z.born>MAXAGE)continue;
   if(z.dir===1&&z.cleared&&L[i]<=z.top)continue;
   if(z.dir===-1&&z.cleared&&H[i]>=z.bot)continue;
   alive.push(z);}
  zones=alive;
  const inS=(M[i]>=1080)||(M[i]<660);
  if(inS&&!open&&best){ep=best.e;sl=best.x;rk=best.r;open=true;dir=best.dir;eI=i;tp1=false;mv=false;
    tr.push({t:S[i],ev:'ENTRADA '+(dir===1?'LONG ':'SHORT ')+ep.toFixed(2)+'  SL '+sl.toFixed(2)+'  riesgo '+rk.toFixed(2)});}
  if(open){
   const t1=dir===1?ep+rk*RR1:ep-rk*RR1,t2=dir===1?ep+rk*RR2:ep-rk*RR2;
   const hS=dir===1?L[i]<=sl:H[i]>=sl;
   if(!tp1){
    const h1=dir===1?H[i]>=t1:L[i]<=t1;
    if(hS){tr.push({t:S[i],ev:'   cierre: '+(mv?'= asegurado +0.8R':'PERDIDA TOTAL')});open=false;}
    else if(h1){tp1=true;const bl=dir===1?ep+rk*LOCK:ep-rk*LOCK;if(!mv||(dir===1?bl>sl:bl<sl))sl=bl;mv=true;
      tr.push({t:S[i],ev:'   TP1 alcanzado'});}
    else if(!mv){const re=intrabar?(dir===1?(H[i]-ep)/rk:(ep-L[i])/rk):(dir===1?(C[i]-ep)/rk:(ep-C[i])/rk);
      if(re>=BETRIG){sl=dir===1?ep+rk*LOCK:ep-rk*LOCK;mv=true;tr.push({t:S[i],ev:'   -> asegura +0.8R'});}}
   } else {const h2=dir===1?H[i]>=t2:L[i]<=t2;
    if(hS){tr.push({t:S[i],ev:'   cierre: TP1+BE'});open=false;}
    else if(h2){tr.push({t:S[i],ev:'   cierre: TP1+TP2'});open=false;}}
  }
 }
 return tr;
}
const segs=segment(raw.bars),nys=segs.map(ny);
for(const [lab,ib] of [['INTRABAR (lo que hace el Pine)',true]]){
  let ev=[];segs.forEach((s,i)=>{ev=ev.concat(run(s,nys[i],ib));});
  console.log('=== '+lab+' — eventos 2026-08-25 a 2026-09-03 ===');
  for(const e of ev.filter(x=>x.t>='2026-08-25'&&x.t<='2026-09-04')) console.log(e.t+'  '+e.ev);
}
