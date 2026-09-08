const fs=require('fs');
const DISP_MULT=2.5,DISP_CLOSE_FRAC=0.6,LIQ_LEN=12,LIQ_TOL=4,LIQ_ACCUM=6,SL_BUFFER=2,ENTRY_BUFFER=12;
const SEG=4*24*3600, MAXAGE=300;
const raw=JSON.parse(fs.readFileSync('C:/Users/diazl/Downloads/mnq-ict-smc-bot/data/mnq_15m_bars.json','utf-8'));
function segment(b){const s=[];let st=0;for(let i=1;i<b.length;i++)if(b[i][0]-b[i-1][0]>SEG){s.push(b.slice(st,i));st=i;}s.push(b.slice(st));return s.filter(x=>x.length>200);}
const segs=segment(raw.bars);
let hist={},total=0,bars=0,maxSeen=0,created=0;
for(const bs of segs){
  const n=bs.length;
  const O=new Float64Array(n),H=new Float64Array(n),L=new Float64Array(n),C=new Float64Array(n);
  for(let i=0;i<n;i++){O[i]=bs[i][1];H[i]=bs[i][2];L[i]=bs[i][3];C[i]=bs[i][4];}
  const avg=new Float64Array(n);let s=0;
  for(let i=0;i<n;i++){s+=H[i]-L[i];if(i>=20)s-=H[i-20]-L[i-20];avg[i]=i>=19?s/20:NaN;}
  let zones=[];
  for(let i=45;i<n;i++){
    const rng=H[i]-L[i],isD=rng>=DISP_MULT*avg[i-1];
    const bD=isD&&C[i]>O[i]&&(C[i]-L[i])>=DISP_CLOSE_FRAC*rng;
    const sD=isD&&C[i]<O[i]&&(H[i]-C[i])>=DISP_CLOSE_FRAC*rng;
    let k,j,idx,cand,mx,cu;
    if(bD){idx=-1;for(k=1;k<=10;k++){if(i-k<0)break;if(C[i-k]<O[i-k]){idx=k;break;}}
      if(idx>0){cand=L[i-idx];mx=0;cu=0;for(j=idx+1;j<=idx+LIQ_LEN;j++){if(i-j<0)break;if(L[i-j]<=cand+LIQ_TOL){cu++;if(cu>mx)mx=cu;}else cu=0;}
        if(mx<LIQ_ACCUM){zones.push({dir:1,top:H[i-idx],bot:cand,cleared:false,born:i});created++;}}}
    if(sD){idx=-1;for(k=1;k<=10;k++){if(i-k<0)break;if(C[i-k]>O[i-k]){idx=k;break;}}
      if(idx>0){cand=H[i-idx];mx=0;cu=0;for(j=idx+1;j<=idx+LIQ_LEN;j++){if(i-j<0)break;if(H[i-j]>=cand-LIQ_TOL){cu++;if(cu>mx)mx=cu;}else cu=0;}
        if(mx<LIQ_ACCUM){zones.push({dir:-1,top:cand,bot:L[i-idx],cleared:false,born:i});created++;}}}
    for(const z of zones){if(z.born===i)continue;
      if(z.dir===1){if(!z.cleared&&L[i]>z.top)z.cleared=true;}else{if(!z.cleared&&H[i]<z.bot)z.cleared=true;}}
    const alive=[];
    for(const z of zones){
      if(z.born===i){alive.push(z);continue;}
      if(i-z.born>MAXAGE)continue;
      if(z.dir===1&&z.cleared&&L[i]<=z.top)continue;
      if(z.dir===-1&&z.cleared&&H[i]>=z.bot)continue;
      alive.push(z);}
    zones=alive;
    const c=zones.length; hist[c]=(hist[c]||0)+1; total+=c; bars++; if(c>maxSeen)maxSeen=c;
  }
}
console.log('Zonas creadas en total:', created);
console.log('Promedio de zonas vivas por vela:', (total/bars).toFixed(2));
console.log('Maximo simultaneo:', maxSeen);
console.log('');
console.log('Distribucion de zonas vivas:');
const ks=Object.keys(hist).map(Number).sort((a,b)=>a-b);
for(const k of ks.slice(0,12)){
  console.log('  '+String(k).padStart(2)+' zonas vivas: '+String(hist[k]).padStart(6)+' velas  ('+(100*hist[k]/bars).toFixed(1)+'%)');
}
const zero=hist[0]||0;
console.log('');
console.log('Velas con CERO zonas vivas: '+zero+' de '+bars+' ('+(100*zero/bars).toFixed(1)+'%)');
