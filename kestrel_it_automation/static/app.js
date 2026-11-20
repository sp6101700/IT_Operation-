
const $ = id => document.getElementById(id);
let employees = [];
function toast(msg){const t=$("toast");t.textContent=msg;t.classList.add("show");setTimeout(()=>t.classList.remove("show"),3000)}
async function api(url, options={}){const r=await fetch(url,{headers:{"Content-Type":"application/json"},...options});let d={};try{d=await r.json()}catch{}if(!r.ok)throw new Error(d.detail||"Request failed");return d}
async function loadEmployees(){
 employees=await api("/api/employees");
 $("employeeRows").innerHTML=employees.length?employees.map(e=>`<tr><td><strong>${esc(e.first_name)} ${esc(e.last_name)}</strong><br><span class="muted">${esc(e.email||"No email")}</span></td><td>${esc(e.employee_code)}</td><td>${esc(e.department||"—")}</td><td>${esc(e.designation||"—")}</td><td>${new Date(e.created_at).toLocaleString()}</td></tr>`).join(""):`<tr><td colspan="5" class="empty">No employees yet. Add your first employee above.</td></tr>`;
 const old=$("employeeSelect").value;
 $("employeeSelect").innerHTML=employees.length?`<option value="">Choose employee…</option>`+employees.map(e=>`<option value="${e.id}">${esc(e.employee_code)} — ${esc(e.first_name)} ${esc(e.last_name)}</option>`).join(""):`<option value="">Add an employee first</option>`;
 if(old && employees.some(e=>String(e.id)===old))$("employeeSelect").value=old;
 updateHint();
}
function esc(v){return String(v??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]))}
function updateHint(){const e=employees.find(x=>String(x.id)===$("employeeSelect").value);$("selectedHint").textContent=e?`Selected: ${e.first_name} ${e.last_name} · ${e.employee_code}`:"Select an employee to enable automation"}
$("employeeSelect").addEventListener("change",updateHint);
$("employeeForm").addEventListener("submit",async ev=>{ev.preventDefault();const data=Object.fromEntries(new FormData(ev.target).entries());try{await api("/api/employees",{method:"POST",body:JSON.stringify(data)});ev.target.reset();await loadEmployees();await refreshStats();toast("Employee added successfully")}catch(e){toast(e.message)}});
async function runJob(type){
 const id=$("employeeSelect").value;if(!id){toast("Please add and select an employee first");return}
 const body={employee_id:Number(id),job_type:type,access_type:$("accessType").value,ticket_category:$("ticketCategory").value,issue:$("ticketIssue").value||"General support request"};
 try{const d=await api("/api/submit",{method:"POST",body:JSON.stringify(body)});toast("Message sent to RabbitMQ · "+d.job_id.slice(0,8));await refreshAll()}catch(e){toast(e.message);await refreshAll()}
}
function statusClass(s){if(s==="Completed")return"Completed";if(s==="Failed"||s==="Broker Error")return"Failed";if(s==="Queued"||s==="Processing")return s;return"Other"}
function resultText(j){if(j.error)return esc(j.error);if(!j.result)return "Waiting for consumer…";const r=j.result;return Object.entries(r).map(([k,v])=>`<b>${esc(k.replaceAll("_"," "))}:</b> ${esc(v)}`).join("<br>")}
async function loadJobs(){const jobs=await api("/api/jobs");$("jobRows").innerHTML=jobs.length?jobs.map(j=>`<tr><td><strong>${esc(j.employee_name)}</strong><br>${esc(j.employee_code)}</td><td>${esc(j.job_name)}</td><td><span title="${esc(j.id)}">${esc(j.id.slice(0,8))}…</span></td><td><span class="status ${statusClass(j.status)}">${esc(j.status)}</span></td><td class="result">${resultText(j)}</td><td>${new Date(j.created_at).toLocaleString()}</td></tr>`).join(""):`<tr><td colspan="6" class="empty">No messages yet. Run an automation job to get started.</td></tr>`}
async function refreshStats(){const s=await api("/api/stats");$("sEmployees").textContent=s.employees;$("sTotal").textContent=s.total;$("sCompleted").textContent=s.completed;$("sPending").textContent=s.pending;$("sFailed").textContent=s.failed}
async function loadStatus(){try{const s=await api("/api/status"),ok=s.rabbitmq.connected;$("rabbitDot").className="dot "+(ok?"good":"bad");$("sideDot").className="dot "+(ok?"good":"bad");$("rabbitTitle").textContent=ok?"RabbitMQ Connected":"RabbitMQ Disconnected";$("rabbitDetail").textContent=s.rabbitmq.message;$("sideStatus").textContent=ok?"Consumer listening":"Check local broker";$("queueName").textContent=s.queue.toUpperCase()}catch(e){$("rabbitTitle").textContent="Backend unavailable"}}
async function refreshAll(){try{await Promise.all([loadEmployees(),loadJobs(),refreshStats(),loadStatus()])}catch(e){console.error(e);toast("Cannot reach backend. Start the Python server.")}}
refreshAll();setInterval(refreshAll,2500);
