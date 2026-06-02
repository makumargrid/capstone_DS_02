// webui/static/run.js — run page: live status (WS), live LOG (poll), error panel,
// report + 3D viewer revealed only when their artifacts exist.
const id=new URLSearchParams(location.search).get('id');
document.getElementById('rid').textContent=id||'?';
const stateEl=document.getElementById('state');
const logEl=document.getElementById('log');
const errEl=document.getElementById('errPanel');
let terminal=false, reportShown=false, viewerShown=false, artifacts=[];
let pendingQuestion=null;

function setState(s){stateEl.textContent=s; stateEl.className="badge "+s; terminal=["approved","completed","failed"].includes(s);}

// tabs
document.querySelectorAll('.tabs button').forEach(b=>b.onclick=()=>{
  document.querySelectorAll('.tabs button').forEach(x=>x.classList.remove('active')); b.classList.add('active');
  ['summary','edit','actions'].forEach(p=>document.getElementById(p).classList.toggle('hidden',p!==b.dataset.tab));
});

const ERR=/(ERROR|Traceback|RuntimeError|❌|HALT|Out of attempts|REDESIGN)/;
function renderLog(text){
  logEl.textContent=text||"(no log yet)"; logEl.scrollTop=logEl.scrollHeight;
  const errs=(text||"").split("\n").filter(l=>ERR.test(l));
  if(errs.length){ errEl.classList.remove('hidden'); errEl.textContent="Issues detected in this run:\n"+errs.slice(-12).join("\n"); }
}
function renderQuestion(q){
  const panel=document.getElementById('questionPanel');
  if(q && q.id){
    pendingQuestion=q;
    panel.classList.remove('hidden');
    document.getElementById('questionText').textContent=q.question||"Planner needs clarification.";
    document.getElementById('questionMsg').textContent="";
  }else{
    pendingQuestion=null;
    panel.classList.add('hidden');
    document.getElementById('questionAnswer').value="";
  }
}
function reveal(){
  if(!reportShown && artifacts.includes("report.html")){
    document.getElementById('reportFrame').src='/designs/'+id+'/report';
    document.getElementById('reportFrame').classList.remove('hidden');
    document.getElementById('reportWait').classList.add('hidden'); reportShown=true;
  }
  if(!viewerShown && artifacts.includes("forgecad_handoff")){
    document.getElementById('viewerFrame').src='/designs/'+id+'/viewer';
    document.getElementById('viewerFrame').classList.remove('hidden');
    document.getElementById('editWait').classList.add('hidden'); viewerShown=true;
  } else if(terminal && !artifacts.includes("forgecad_handoff")){
    document.getElementById('editWait').textContent="No editable model: this run did not reach an APPROVED design. See the live log / report for why.";
  }
}
async function tick(){
  try{
	    const s=await (await fetch('/designs/'+id+'/log')).json();
	    setState(s.state); renderLog(s.log);
	    const st=await (await fetch('/designs/'+id+'/status')).json(); artifacts=st.artifacts||[];
	    renderQuestion(st.pending_question||s.pending_question);
	    if(s.error){ errEl.classList.remove('hidden'); errEl.textContent="Run error: "+s.error; }
    reveal();
  }catch(e){}
  if(!terminal) setTimeout(tick,1500); else setTimeout(tick,1500); // one more pass after terminal
  if(terminal && reportShown){ return; }
}
// WS for snappy state badge; log/report via tick()
try{ const proto=location.protocol==='https:'?'wss':'ws';
	  const ws=new WebSocket(`${proto}://${location.host}/ws/designs/${id}/stream`);
	  ws.onmessage=e=>{const f=JSON.parse(e.data); if(f.state)setState(f.state); if(f.artifacts)artifacts=f.artifacts; renderQuestion(f.pending_question);};
	}catch(e){}

// actions
document.getElementById('iterate').onclick=async()=>{
  const fb=document.getElementById('feedback').value.trim();
  const r=await fetch('/designs/'+id+'/iterate',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({feedback:fb})});
  if(r.ok)location.href='/ui/run.html?id='+(await r.json()).run_id;
};
function decide(accepted){return async()=>{
  const note=accepted?null:(window.prompt("Reason for rejection (optional):")||null);
  const r=await fetch('/designs/'+id+'/approve',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({accepted,note})});
  document.getElementById('actMsg').textContent=r.ok?("recorded: "+(accepted?"ACCEPTED":"REJECTED")):("error "+r.status);
};}
document.getElementById('accept').onclick=decide(true);
document.getElementById('reject').onclick=decide(false);
document.getElementById('sendAnswer').onclick=async()=>{
  if(!pendingQuestion)return;
  const answer=document.getElementById('questionAnswer').value.trim();
  if(!answer){document.getElementById('questionMsg').textContent="enter an answer first.";return;}
  const r=await fetch('/designs/'+id+'/answer',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({question_id:pendingQuestion.id,answer})});
  document.getElementById('questionMsg').textContent=r.ok?"answer sent.":"error "+r.status;
};
tick();
