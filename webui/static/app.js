// webui/static/app.js — dashboard: start a run, list runs. Talks to the Phase-4 API.
async function startRun(){
  const prompt=document.getElementById('prompt').value.trim();
  if(!prompt){document.getElementById('msg').textContent="enter a prompt first.";return;}
  document.getElementById('msg').textContent="starting…";
  const r=await fetch('/designs',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({prompt,interactive:true})});
  if(!r.ok){document.getElementById('msg').textContent="error: "+r.status;return;}
  location.href='/ui/run.html?id='+(await r.json()).run_id;
}
async function loadRuns(){
  try{const d=await (await fetch('/designs')).json();
    const tb=document.querySelector('#runs tbody'); tb.innerHTML="";
    d.runs.slice().reverse().forEach(r=>{const t=document.createElement('tr');
      t.innerHTML=`<td>${r.run_id}</td><td><span class="badge ${r.state}">${r.state}</span></td>`+
        `<td>${(r.prompt||'').slice(0,60)}</td><td><a href="/ui/run.html?id=${r.run_id}">open</a></td>`;
      tb.appendChild(t);});
  }catch(e){}
}
document.getElementById('go').onclick=startRun;
loadRuns(); setInterval(loadRuns,3000);
