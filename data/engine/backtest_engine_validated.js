// Motor de backtest recuperado y auditado del log crudo de la sesión
// (bda8712a-..., líneas ~8594-8610, 2026-09-06 19:xx).
// Es el motor que generó los resultados citados como "definitivos" en el
// proyecto: $118.990 (baseline sin lock, TP1=1.8R/TP2=4R) y $127.834
// (config final adoptada: lockR=0.5).
//
// Requiere en window: __BARS (bars object keyed by unix ts -> [o,h,l,c]),
// __NYmin (Int32Array: minuto del día en hora NY por barra) y
// __NYd (array: abreviatura del día de la semana en NY, ej. "Sun").
// Esos tres arrays se reconstruyen con los scripts hermanos en esta misma
// carpeta (ver README de /data/engine).
//
// Verificado arquitectónicamente contra el código fuente real de
// "ICT 15M OB Entry v12": misma detección de OB (desplazamiento + filtro de
// liquidez), mismo ciclo de vida de zona "cleared -> touchable -> consumida"
// (bTou/sTou), misma exclusividad de un solo trade abierto a la vez
// (`ce = inSession && !open`), mismo modelo de entrada tipo límite en el
// borde del OB (`ep = max(low, bullTop)`), y mismo filtro de domingo.
//
// Diferencia frente al "TP1 grid" (usd()=118990 en TP1=1.8R): aquí se
// modela además el "breakeven anticipado" con lockR configurable (0 =
// breakeven puro, el baseline original; 0.5 = la config adoptada).

(function(){
  var B=window.__BARS;var ks=Object.keys(B).map(Number).sort(function(a,b){return a-b;});var n=ks.length;
  var O=new Float64Array(n),H=new Float64Array(n),L=new Float64Array(n),C=new Float64Array(n);
  for(var i=0;i<n;i++){var v=B[ks[i]];O[i]=v[0];H[i]=v[1];L[i]=v[2];C[i]=v[3];}
  var avg=new Float64Array(n),s=0;
  for(i=0;i<n;i++){s+=H[i]-L[i];if(i>=20)s-=H[i-20]-L[i-20];avg[i]=i>=19?s/20:NaN;}
  var NYmin=window.__NYmin, NYd=window.__NYd;
  var RISKCAP=100, BETRIG=1.2, RR1=1.8, RR2=4;

  // lockR: cuánto R de ganancia asegurar al llegar a BETRIG (0 = breakeven puro = baseline $118.990)
  function run(lockR){
   var bT=NaN,bB=NaN,bF=false,bC=false,sT=NaN,sB=NaN,sF=false,sC=false;
   var open=false,dir=0,ep=0,sl=0,origRisk=0,eIdx=0,tp1Hit=false,moved=false,tr=[];
   for(var i=45;i<n;i++){
    var rng=H[i]-L[i],isD=rng>=2.5*avg[i-1];
    var bD=isD&&C[i]>O[i]&&(C[i]-L[i])>=0.6*rng, sD=isD&&C[i]<O[i]&&(H[i]-C[i])>=0.6*rng;
    var bN=false,sN=false,k,j,idx,cand,mx,cu;
    if(bD){idx=-1;for(k=1;k<=10;k++){if(C[i-k]<O[i-k]){idx=k;break;}}
     if(idx>0){cand=L[i-idx];mx=0;cu=0;for(j=idx+1;j<=idx+12;j++){if(L[i-j]<=cand+4){cu++;if(cu>mx)mx=cu;}else cu=0;}
      if(mx<6){bT=H[i-idx];bB=cand;bF=true;bC=false;bN=true;}}}
    if(sD){idx=-1;for(k=1;k<=10;k++){if(C[i-k]>O[i-k]){idx=k;break;}}
     if(idx>0){cand=H[i-idx];mx=0;cu=0;for(j=idx+1;j<=idx+12;j++){if(H[i-j]>=cand-4){cu++;if(cu>mx)mx=cu;}else cu=0;}
      if(mx<6){sT=cand;sB=L[i-idx];sF=true;sC=false;sN=true;}}}
    if(!bN&&bF&&!bC&&!isNaN(bT)&&L[i]>bT)bC=true;
    if(!sN&&sF&&!sC&&!isNaN(sB)&&H[i]<sB)sC=true;
    var bTou=!bN&&bC&&bF, sTou=!sN&&sC&&sF;
    if(!bN&&bC&&bF&&!isNaN(bT)&&L[i]<=bT)bF=false;
    if(!sN&&sC&&sF&&!isNaN(sB)&&H[i]>=sB)sF=false;
    var lz=bTou&&!isNaN(bT)&&L[i]<=bT+12&&L[i]>=bB;
    var sz=sTou&&!isNaN(sB)&&H[i]>=sB-12&&H[i]<=sT;
    var inS=(NYmin[i]>=1080)||(NYmin[i]<660);
    var ce=inS&&!open;
    if(ce&&lz){var _ep=Math.max(L[i],bT),_sl=bB-2,_r=_ep-_sl; if(!(_r<=0||_r>RISKCAP)){ep=_ep;sl=_sl;origRisk=_r;open=true;dir=1;eIdx=i;tp1Hit=false;moved=false;}}
    if(ce&&sz){var _ep2=Math.min(H[i],sB),_sl2=sT+2,_r2=_sl2-_ep2; if(!(_r2<=0||_r2>RISKCAP)){ep=_ep2;sl=_sl2;origRisk=_r2;open=true;dir=-1;eIdx=i;tp1Hit=false;moved=false;}}
    if(open){
     var tp1=dir===1?ep+origRisk*RR1:ep-origRisk*RR1, tp2=dir===1?ep+origRisk*RR2:ep-origRisk*RR2;
     var hitSL=dir===1?L[i]<=sl:H[i]>=sl;
     if(!tp1Hit){
      var hT1=dir===1?H[i]>=tp1:L[i]<=tp1;
      if(hitSL){
        var code = !moved?'full':(lockR>0?'locked':'befirst');
        tr.push({e:eIdx,r:origRisk,kind:code});open=false;
      } else if(hT1){
        tp1Hit=true;
        var beLevel = dir===1? ep+origRisk*lockR : ep-origRisk*lockR;
        if(!moved || (dir===1? beLevel>sl : beLevel<sl)) sl=beLevel; // no bajar una proteccion ya mejor
        moved=true;
      } else if(!moved){
        var re=dir===1?(H[i]-ep)/origRisk:(ep-L[i])/origRisk;
        if(re>=BETRIG){ sl = dir===1? ep+origRisk*lockR : ep-origRisk*lockR; moved=true; }
      }
     } else {
      var hT2=dir===1?H[i]>=tp2:L[i]<=tp2;
      if(hitSL){ tr.push({e:eIdx,r:origRisk,kind:'be_or_locked_after_tp1', lockR:lockR}); open=false; }
      else if(hT2){ tr.push({e:eIdx,r:origRisk,kind:'runner'}); open=false; }
     }
    }
   }
   return tr.filter(function(t){return NYd[t.e]!=='Sun';});
  }
  function usd(t,lockR){var risk=t.r,c=t.kind;
   if(c==='full')return -3*risk*2-2.22;
   if(c==='befirst')return -2.22;
   if(c==='locked')return 3*(lockR*risk*2)-2.22; // los 3 contratos salen con lockR de ganancia
   if(c==='be_or_locked_after_tp1')return 2*(RR1*risk*2) + 1*(lockR*risk*2) -2.22; // 2 en TP1, 1 en el nivel asegurado
   return 2*(RR1*risk*2)+1*(RR2*risk*2)-2.22;
  }
  function agg(tr,lockR){var eq=0,peak=0,mdd=0,gp=0,gl=0,counts={};
   tr.forEach(function(t){var u=usd(t,lockR);if(u>0)gp+=u;else gl-=u;eq+=u;if(eq>peak)peak=eq;if(peak-eq>mdd)mdd=peak-eq;
    counts[t.kind]=(counts[t.kind]||0)+1;});
   return {n:tr.length,usd:Math.round(eq),pf:+(gp/gl).toFixed(2),maxDD:Math.round(mdd),counts:counts};}
  var out={};
  [0,0.2,0.3,0.4,0.5,0.6,0.8,0.9,1.0,1.1,1.2].forEach(function(lr){ out['lock='+lr+'R']=agg(run(lr),lr); });
  return JSON.stringify(out,null,0);
})()
