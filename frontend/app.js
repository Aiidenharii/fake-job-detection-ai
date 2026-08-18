const API="/api";

async function loadStats(){
  try{
    const r=await fetch(API+"/dashboard/stats"); const s=await r.json();
    document.querySelector("#total").textContent=s.total;
    document.querySelector("#high").textContent=s.high;
    document.querySelector("#medium").textContent=s.medium;
    document.querySelector("#average").textContent=s.average;
  }catch(e){console.error(e)}
}
async function analyze(){
  const desc=document.querySelector("#description").value.trim();
  if(!desc){alert("Please enter a job description.");return}
  const loading=document.querySelector("#loading"); loading.classList.remove("hidden");
  document.querySelector("#result").innerHTML="";
  const body={
    title:val("title"), company:val("company"), salary:val("salary"), location:val("location"),
    recruiter_email:val("email"), company_website:val("website"), application_url:val("url"), description:desc
  };
  try{
    const r=await fetch(API+"/analyze-job",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
    const x=await r.json(); if(!r.ok) throw new Error(x.detail||"Analysis failed");
    renderResult(x); loadStats(); loadHistory();
  }catch(e){document.querySelector("#result").innerHTML=`<div class="result-card">❌ ${escapeHtml(e.message)}</div>`}
  finally{loading.classList.add("hidden")}
}
function val(id){return document.querySelector("#"+id).value}
function renderResult(x){
  const factors=(x.factors||[]).map(f=>`<div class="factor"><b>${escapeHtml(f.name)}</b> <span class="tag">${f.severity}</span> <span class="tag">+${f.points}</span></div>`).join("");
  const keys=(x.suspicious_keywords||[]).map(k=>`<span class="tag">${escapeHtml(k)}</span>`).join("")||"<span>No suspicious phrases detected</span>";
  document.querySelector("#result").innerHTML=`
  <div class="result-card result">
    <small>AI PREDICTION • ${escapeHtml(x.model_name)}</small>
    <div class="risk ${x.risk_level}">${x.risk_score}/100</div>
    <h2>${escapeHtml(x.risk_level)} RISK</h2>
    <p><b>${escapeHtml(x.prediction)}</b> • Fake probability: ${x.fake_probability}% • Legitimate probability: ${x.legitimate_probability}%</p>
    <h3>Suspicious Indicators</h3>${factors||"<p>No major factors detected.</p>"}
    <h3>Detected Keywords</h3><div>${keys}</div>
    <h3>Company Signals</h3>${(x.company_signals||[]).map(f=>`<div class="factor">${escapeHtml(f.name)} <span class="tag">${f.severity}</span></div>`).join("")||"<p>No company signals.</p>"}
    <h3>Safety Recommendation</h3><p>${escapeHtml(x.recommendation)}</p>
    <hr><small>⚠️ ${escapeHtml(x.disclaimer)}</small>
  </div>`;
}
async function loadHistory(){
  const box=document.querySelector("#historyList");
  try{
    const r=await fetch(API+"/analyses"); const rows=await r.json();
    if(!rows.length){box.innerHTML="<p>No analyses yet.</p>";return}
    box.innerHTML=`<table><tr><th>Job</th><th>Company</th><th>Risk</th><th>Prediction</th><th>Date</th></tr>
    ${rows.map(x=>`<tr><td>${escapeHtml(x.title||"-")}</td><td>${escapeHtml(x.company||"-")}</td><td class="${x.risk_level}">${x.risk_score}</td><td>${escapeHtml(x.prediction)}</td><td>${new Date(x.created_at).toLocaleString()}</td></tr>`).join("")}</table>`
  }catch(e){box.innerHTML="<p>Could not load history.</p>"}
}
function escapeHtml(s){return String(s??"").replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[m]))}
loadStats(); loadHistory();