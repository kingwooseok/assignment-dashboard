"use strict";
const $ = (selector) => document.querySelector(selector);
let currentStatus = "all", currentDeadline = "all", assignments = [], editingId = null, deletingId = null;
let importItems = [], requestNumber = 0, toastTimer, searchTimer, importRequest = 0;

async function api(path, options = {}) {
  let response;
  try {
    response = await fetch(path, { ...options, headers: options.body instanceof FormData ? {} : {"Content-Type": "application/json"} });
  } catch { throw new Error("서버에 연결할 수 없습니다. 실행 창을 확인한 뒤 다시 시도해 주세요."); }
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "입력 내용을 확인해 주세요.");
  return data;
}
function element(tag, className, value) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (value !== undefined) node.textContent = value;
  return node;
}
function showError(selector, message = "") { const node = $(selector); node.textContent = message; node.hidden = !message; }
function toast(message) {
  clearTimeout(toastTimer); $("#toast").textContent = message; $("#toast").hidden = false;
  toastTimer = setTimeout(() => { $("#toast").hidden = true; }, 3500);
}
function dateLabel(value) { return value.slice(0, 10).replaceAll("-", ". "); }
function openDialog(id) { const dialog = $(id); if (!dialog.open) dialog.showModal(); }
document.querySelectorAll("[data-close]").forEach(button => button.addEventListener("click", () => $("#" + button.dataset.close).close()));

// 과제명과 메모는 textContent로 넣어 일반 텍스트로 표시한다.
function iconButton(kind, title, action) {
  const button = element("button", "icon-button " + kind);
  button.title = title; button.setAttribute("aria-label", title);
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 24 24"); svg.setAttribute("aria-hidden", "true");
  const path = document.createElementNS(svg.namespaceURI, "path");
  path.setAttribute("d", kind === "delete" ? "M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13M10 10v7M14 10v7" : "m15 4 5 5M4 20l5-1L20 8a2 2 0 0 0-5-5L4 14v6Z");
  svg.append(path); button.append(svg); button.addEventListener("click", action); return button;
}

async function loadDashboard() {
  const number = ++requestNumber;
  try {
    const params = new URLSearchParams({q: $("#search").value, subject: $("#subject-filter").value, status: currentStatus, deadline: currentDeadline});
    const data = await api("/api/dashboard?" + params);
    if (number !== requestNumber) return;
    showError("#load-error"); assignments = data.assignments;
    $("#today-label").textContent = new Intl.DateTimeFormat("ko-KR", {year:"numeric", month:"long", day:"numeric", weekday:"long", timeZone:"Asia/Seoul"}).format(new Date(data.today + "T12:00:00+09:00"));
    for (const key of ["today", "week", "overdue", "completed"]) $("#stat-" + key).textContent = data.summary[key];
    $("#week-range").textContent = dateLabel(data.today).slice(6) + " ~ " + dateLabel(data.week_end).slice(6) + " · 미완료";
    $("#completion-summary").textContent = "전체 " + data.summary.total + "개 중 완료";
    const percent = data.summary.total ? Math.round(data.summary.completed / data.summary.total * 100) : 0;
    $("#progress-percent").textContent = percent; $("#progress-bar").style.width = percent + "%";
    $(".progress-track").setAttribute("aria-valuenow", percent);
    $("#progress-copy").textContent = data.summary.total ? data.summary.completed + "개 완료 · " + (data.summary.total - data.summary.completed) + "개 남았어요" : "완료한 과제가 여기에 쌓여요.";
    $("#next-title").textContent = data.next?.title || "다가오는 미완료 과제가 없어요";
    $("#next-date").textContent = data.next ? data.next.subject + " · " + dateLabel(data.next.due_at) + (data.next.due_time ? " " + data.next.due_time : "") : "새로운 일정을 추가해 보세요.";
    const subjectSelect = $("#subject-filter"), selectedSubject = subjectSelect.value;
    subjectSelect.replaceChildren(new Option("모든 과목", ""));
    for (const subject of data.subjects) subjectSelect.add(new Option(subject, subject));
    if (selectedSubject && !data.subjects.includes(selectedSubject)) subjectSelect.add(new Option(selectedSubject, selectedSubject));
    subjectSelect.value = selectedSubject;
    renderTasks();
    $("#save-status").textContent = "저장된 내용을 불러왔어요 · " + new Intl.DateTimeFormat("ko-KR", {hour:"2-digit",minute:"2-digit",timeZone:"Asia/Seoul"}).format(new Date());
  } catch (error) { if (number === requestNumber) showError("#load-error", error.message); }
}

function renderTasks() {
  const body = $("#task-body"); body.replaceChildren();
  $("#visible-count").textContent = assignments.length;
  $("#table-container").hidden = assignments.length === 0;
  $("#empty-state").hidden = assignments.length !== 0;
  const filtered = currentStatus !== "all" || currentDeadline !== "all" || $("#search").value.trim() || $("#subject-filter").value;
  $("#empty-title").textContent = filtered ? "조건에 맞는 과제가 없어요" : "첫 과제를 등록해 보세요";
  $("#empty-description").textContent = filtered ? "검색어나 필터를 바꾸어 다른 과제를 찾아보세요." : "직접 추가하거나 캘린더 파일에서 한 번에 가져올 수 있어요.";
  $("#empty-create").hidden = !!filtered;
  for (const item of assignments) {
    const row = element("tr", item.completed ? "row-completed" : ""); row.dataset.id = item.id;
    const checkCell = element("td"), check = element("input"); check.type = "checkbox"; check.checked = item.completed;
    check.setAttribute("aria-label", item.title + " 완료 처리");
    check.addEventListener("change", async () => {
      check.disabled = true;
      try { await api(`/api/assignments/${item.id}/completion`, {method:"PATCH",body:JSON.stringify({completed:check.checked})}); toast(check.checked ? "완료한 과제로 표시했어요." : "미완료 과제로 되돌렸어요."); await loadDashboard(); }
      catch (error) { check.checked = item.completed; toast(error.message); }
      finally { check.disabled = false; }
    });
    checkCell.append(check);
    const titleCell = element("td"), subject = element("span", "task-subject", item.subject + (item.source_key ? " · 캘린더" : ""));
    const title = element(item.url ? "a" : "span", "task-title", item.title);
    if (item.url) { title.href = item.url; title.target = "_blank"; title.rel = "noopener noreferrer"; title.title = "과제 페이지 열기"; }
    titleCell.append(subject, title);
    if (item.note) { const note = element("span", "task-note", item.note); note.title = item.note; titleCell.append(note); }
    const dueCell = element("td"); dueCell.append(element("span","task-date",dateLabel(item.due_at)),element("span","task-time",item.due_time || "날짜만 지정"));
    const statusCell = element("td"); statusCell.append(element("span","badge " + item.status,item.status_label));
    const actionCell = element("td"), actions = element("div","row-actions");
    actions.append(iconButton("edit",item.title + " 수정",()=>openAssignment(item)),iconButton("delete",item.title + " 삭제",()=>{deletingId=item.id;$("#delete-name").textContent=item.title;openDialog("#delete-dialog");}));
    actionCell.append(actions); row.append(checkCell,titleCell,dueCell,statusCell,actionCell); body.append(row);
  }
}

function openAssignment(item = null) {
  editingId = item?.id ?? null; $("#assignment-form").reset(); showError("#form-error");
  $("#assignment-dialog-title").textContent = item ? "과제 수정" : "새 과제 추가";
  $("#save-assignment").textContent = item ? "변경 내용 저장" : "과제 추가";
  for (const key of ["subject","title","note","url"]) $("#field-" + key).value = item?.[key] || "";
  $("#field-date").value = item?.due_at.slice(0,10) || "";
  $("#field-time").value = item?.due_time || "";
  openDialog("#assignment-dialog"); $("#field-subject").focus();
}
$("#open-create").onclick = () => openAssignment(); $("#empty-create").onclick = () => openAssignment();
$("#assignment-form").addEventListener("submit", async event => {
  event.preventDefault(); const button = $("#save-assignment"); button.disabled = true; showError("#form-error");
  const values = Object.fromEntries(new FormData(event.currentTarget));
  const payload = {subject:values.subject,title:values.title,note:values.note,url:values.url,due_at:values.date + (values.time ? "T" + values.time + ":00+09:00" : "")};
  try { await api(editingId ? "/api/assignments/" + editingId : "/api/assignments",{method:editingId ? "PUT" : "POST",body:JSON.stringify(payload)}); $("#assignment-dialog").close(); toast(editingId ? "과제 내용을 수정했어요." : "새 과제를 추가했어요."); await loadDashboard(); }
  catch (error) { showError("#form-error",error.message); }
  finally { button.disabled = false; }
});
$("#confirm-delete").onclick = async () => {
  const button = $("#confirm-delete"); button.disabled = true;
  try { await api("/api/assignments/" + deletingId,{method:"DELETE"}); $("#delete-dialog").close(); toast("과제를 삭제했어요."); await loadDashboard(); }
  catch (error) { toast(error.message); }
  finally { button.disabled = false; }
};
document.querySelectorAll("[data-status]").forEach(button => button.onclick = () => {
  currentStatus = button.dataset.status;
  document.querySelectorAll("[data-status]").forEach(tab => {const active=tab===button;tab.classList.toggle("active",active);tab.setAttribute("aria-pressed",String(active));}); loadDashboard();
});
$("#subject-filter").onchange = loadDashboard;
document.querySelectorAll("[data-deadline]").forEach(button => button.onclick = () => {
  currentDeadline = button.dataset.deadline;
  document.querySelectorAll("[data-deadline]").forEach(tab => {const active=tab===button;tab.classList.toggle("active",active);tab.setAttribute("aria-pressed",String(active));});
  loadDashboard();
});
$("#search").oninput = () => { clearTimeout(searchTimer); searchTimer = setTimeout(loadDashboard,180); };
$("#refresh").onclick = loadDashboard;

function openImport() {
  ++importRequest; importItems = []; $("#ics-file").value=""; $("#import-filename").textContent="";
  $("#preview-container").hidden=true; $("#import-hint").hidden=false; $("#import-warnings").hidden=true;
  $("#preview-list").replaceChildren(); showError("#import-error"); $("#confirm-import").disabled=true; openDialog("#import-dialog");
}
$("#open-import").onclick = openImport;
$("#try-sample").onclick = async () => {
  openImport();
  try { const response=await fetch("/sample_assignments.ics"); if(!response.ok) throw new Error("예시 파일을 불러오지 못했습니다."); await previewFile(new File([await response.blob()],"sample_assignments.ics",{type:"text/calendar"})); }
  catch(error) {showError("#import-error",error.message);}
};
$("#ics-file").onchange = () => {if($("#ics-file").files[0]) previewFile($("#ics-file").files[0]);};
async function previewFile(file) {
  const number=++importRequest; importItems=[]; showError("#import-error"); $("#confirm-import").disabled=true;
  $("#preview-container").hidden=true; $("#import-warnings").hidden=true; $("#import-hint").hidden=true; $("#import-filename").textContent="파일을 읽고 있어요…";
  try {
    if(file.size>2*1024*1024) throw new Error("2MB 이하의 파일을 선택해 주세요.");
    const form=new FormData();form.append("file",file);
    const data=await api("/api/import/preview",{method:"POST",body:form}); if(number!==importRequest)return;
    importItems=data.items; $("#import-filename").textContent=file.name+" · "+importItems.length+"개 일정";
    const warnings=$("#import-warnings");warnings.hidden=!data.warnings.length;warnings.querySelector("ul").replaceChildren(...data.warnings.map(message=>element("li","",message)));
    renderPreview();
    if(!importItems.length) showError("#import-error","가져올 수 있는 일정이 없습니다. 가져오기 안내를 확인해 주세요.");
  } catch(error) {if(number===importRequest){$("#import-filename").textContent=file.name;showError("#import-error",error.message);}}
}
function renderPreview() {
  const list=$("#preview-list");list.replaceChildren();$("#preview-container").hidden=!importItems.length;
  importItems.forEach((item,index)=>{
    const row=element("div","preview-row"+(item.exists?" is-existing":""));
    const check=element("input");check.type="checkbox";check.checked=!item.exists;check.disabled=item.exists;check.dataset.index=index;check.setAttribute("aria-label",item.title+" 가져오기 선택");check.onchange=updateSelection;
    const details=element("div"),title=element("div","preview-title",item.title);
    if(item.exists) title.append(element("span","badge completed","이미 등록됨"));
    details.append(title,element("p","preview-date",dateLabel(item.due_at)+(item.due_at.includes("T")?" "+item.due_at.slice(11,16):" · 날짜만 지정")));
    const subject=element("input");subject.type="text";subject.value=item.subject;subject.placeholder="과목명 입력";subject.maxLength=80;subject.disabled=item.exists;subject.dataset.subjectIndex=index;subject.setAttribute("aria-label",item.title+" 과목명");
    row.append(check,details,subject);list.append(row);
  });updateSelection();
}
function updateSelection(){
  const available=[...document.querySelectorAll("#preview-list input[type=checkbox]:not(:disabled)")];
  const selected=available.filter(check=>check.checked).length;
  $("#selection-count").textContent=selected+"개 선택";$("#confirm-import").disabled=selected===0;
  $("#select-all").checked=selected>0&&selected===available.length;$("#select-all").indeterminate=selected>0&&selected<available.length;$("#select-all").disabled=!available.length;
}
$("#select-all").onchange = () => {document.querySelectorAll("#preview-list input[type=checkbox]:not(:disabled)").forEach(check=>check.checked=$("#select-all").checked);updateSelection();};
$("#confirm-import").onclick=async()=>{
  const button=$("#confirm-import");showError("#import-error");const items=[];
  for(const check of document.querySelectorAll("#preview-list input[type=checkbox]:checked:not(:disabled)")){
    const index=Number(check.dataset.index),input=$(`[data-subject-index="${index}"]`);
    if(!input.value.trim()){showError("#import-error","선택한 일정의 과목명을 입력해 주세요.");input.focus();return;}
    const {exists,...item}=importItems[index];items.push({...item,subject:input.value.trim()});
  }
  if(!items.length)return;button.disabled=true;
  try {const result=await api("/api/import",{method:"POST",body:JSON.stringify({items})});$("#import-dialog").close();toast(result.added+"개 일정을 가져왔어요."+(result.skipped?" 중복 "+result.skipped+"개 제외":""));await loadDashboard();}
  catch(error){showError("#import-error",error.message);}
  finally{updateSelection();}
};
loadDashboard();
// 열린 화면에서도 마감 상태를 매분 갱신한다.
setInterval(()=>{if(!document.hidden&&!document.querySelector("dialog[open]"))loadDashboard();},60000);
document.addEventListener("visibilitychange",()=>{if(!document.hidden)loadDashboard();});
