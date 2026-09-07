// Reconstruye window.__NYmin y window.__NYd a partir de window.__BARS,
// requeridos por backtest_engine_validated.js. Recuperado del mismo log
// crudo de sesión (líneas ~6695-6832).
(function(){
  var B=window.__BARS;var ks=Object.keys(B).map(Number).sort(function(a,b){return a-b;});var n=ks.length;
  var fmt=new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false,weekday:'short'});
  var NYmin=new Int32Array(n),NYk=new Array(n),NYd=new Array(n);
  for(var i=0;i<n;i++){
    var p={};
    fmt.formatToParts(new Date(ks[i]*1000)).forEach(function(x){p[x.type]=x.value;});
    var hh=+p.hour%24;
    NYmin[i]=hh*60+(+p.minute);
    NYk[i]=p.year+'-'+p.month;
    NYd[i]=p.weekday;
  }
  window.__NYmin=NYmin; window.__NYk=NYk; window.__NYd=NYd;
  return {bars:n, sample_NYd:NYd.slice(0,5), sample_NYmin:Array.from(NYmin.slice(0,5))};
})()
