const $ = (id) => document.getElementById(id);
const views = { form: $("viewForm"), loading: $("viewLoading"), results: $("viewResults") };
const errorEl = $("error"), submitBtn = $("submit"), statusEl = $("status"), barFill = $("barFill");
let stepEls = [];
const navBtns = [...document.querySelectorAll("#nav button")];

const PANELS = {
  job_insights: ["Job insights", "A breakdown of the role, the company and what they are looking for."],
  candidate_profile: ["Profile", "Your skills, experience and projects, summarized from your inputs."],
  tailored_resume: ["Tailored resume", "An ATS-friendly resume written for this role, after the fact-check below."],
  fact_check: ["Fact check", "A reviewer compared every claim in the draft resume with your own data and fixed anything unsupported."],
  cover_letter: ["Cover letter", "A short letter that connects your real experience to this role. Review it and add the hiring manager's name if you have it."],
  interview_materials: ["Interview prep", "Likely questions, talking points and questions to ask."],
  skills: ["Skills to develop", "Skills the role asks for that your profile doesn't clearly show, with places to start learning."],
};

const VERDICT_TEXT = { pass: "Passed, no changes", corrected: "Corrected", unknown: "Review not applied" };
let data = null, currentKey = "job_insights", resumeFile = null;

function show(name) {
  Object.entries(views).forEach(([k, el]) => (el.hidden = k !== name));
  $("newBtn").hidden = name !== "results";
  window.scrollTo({ top: 0 });
}
function esc(t) { const d = document.createElement("div"); d.textContent = t ?? ""; return d.innerHTML; }

/* ---------- results ---------- */
function setGauge(score) {
  const arc = $("gaugeArc"), len = 157.08;
  const val = typeof score === "number" ? score : 0;
  arc.style.strokeDashoffset = len * (1 - val / 100);
  arc.style.stroke = val >= 75 ? "#2fbf8d" : val >= 50 ? "#f08a1c" : "#e5484d";
  $("scoreText").textContent = typeof score === "number" ? score : "--";
}

function selectPanel(key) {
  currentKey = key;
  navBtns.forEach((b) => b.classList.toggle("active", b.dataset.key === key));
  $("panelTitle").textContent = PANELS[key][0];
  $("panelDesc").textContent = PANELS[key][1];
  const body = $("panelBody");
  if (key === "skills") {
    const gaps = data.skill_gaps || [];
    $("panelBadge").textContent = gaps.length ? `${gaps.length} to review` : "No gaps";
    $("panelActions").hidden = true;
    body.className = "gaps";
    body.innerHTML = gaps.length ? gaps.map((g) => `
      <div class="gap ${esc(g.priority)}">
        <h3>${esc(g.skill)} <span class="badge">${esc(g.priority)}</span></h3>
        <p>${esc(g.why)}</p>
        <div class="links">${g.links.map((l) => `<a href="${esc(l.url)}" target="_blank" rel="noopener noreferrer">${esc(l.label)}</a>`).join("")}</div>
      </div>`).join("") : '<p class="muted">No clear skill gaps found. Great match!</p>';
  } else {
    $("panelBadge").textContent = key === "fact_check" ? VERDICT_TEXT[data.resume_verdict] || "Ready" : "Ready";
    $("panelActions").hidden = false;
    body.className = "viewer";
    const md = data.files[key] || "";
    body.innerHTML = window.marked ? marked.parse(md) : `<pre>${esc(md)}</pre>`;
  }
}

function showResults(d) {
  data = d;
  setGauge(d.match_score);
  const n = (d.skill_gaps || []).length;
  const gb = $("gapBadge");
  gb.textContent = n ? `${n} to review` : "No gaps";
  gb.classList.toggle("warn", n > 0);
  const cb = $("checkBadge"), v = d.resume_verdict;
  cb.textContent = v === "pass" ? "Passed" : v === "corrected" ? "Corrected" : "Not applied";
  cb.classList.toggle("warn", v !== "pass");
  selectPanel("job_insights");
  show("results");
}
navBtns.forEach((b) => b.addEventListener("click", () => selectPanel(b.dataset.key)));
$("newBtn").addEventListener("click", () => show("form"));

/* ---------- progress (driven by server events) ---------- */
function buildSteps(labels) {
  $("agents").innerHTML = labels.map((l, i) => `<li><i>${i + 1}</i>${esc(l)}</li>`).join("");
  stepEls = [...document.querySelectorAll("#agents li")];
  barFill.style.width = "0";
}
function setStep(index, status) {
  const el = stepEls[index];
  if (!el) return;
  el.classList.toggle("active", status === "active");
  el.classList.toggle("done", status === "done");
  const done = stepEls.filter((s) => s.classList.contains("done")).length;
  barFill.style.width = `${Math.round(((done + (status === "active" ? 0.4 : 0)) / stepEls.length) * 100)}%`;
}
function handleEvent(ev) {
  if (ev.type === "plan") buildSteps(ev.steps);
  else if (ev.type === "step") setStep(ev.index, ev.status);
}
async function streamGenerate(fd) {
  const res = await fetch("/api/generate/stream", { method: "POST", body: fd });
  if (!res.ok) {
    const d = await res.json().catch(() => ({}));
    throw new Error(d.detail || "Request failed");
  }
  const reader = res.body.getReader(), dec = new TextDecoder();
  let buf = "", result = null;
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let i;
    while ((i = buf.indexOf("\n\n")) >= 0) {
      const chunk = buf.slice(0, i);
      buf = buf.slice(i + 2);
      const line = chunk.split("\n").find((l) => l.startsWith("data:"));
      if (!line) continue; // keep-alive comment
      const ev = JSON.parse(line.slice(5));
      if (ev.type === "error") throw new Error(ev.message);
      if (ev.type === "result") result = ev.data;
      else handleEvent(ev);
    }
  }
  if (!result) throw new Error("The connection closed before the result arrived. Please try again.");
  return result;
}

/* ---------- resume upload ---------- */
const drop = $("drop"), fileInput = $("resume");
function setFileLabel(name) {
  $("fileName").textContent = name || "";
  $("fileChip").hidden = !name;
  $("dropIdle").hidden = !!name;
}
function pickFile(f) {
  if (!f) return;
  if (!/\.(pdf|docx|txt|md)$/i.test(f.name) || f.size > 5 * 1024 * 1024) {
    errorEl.textContent = "Please upload a PDF, DOCX, TXT or MD file up to 5 MB.";
    errorEl.hidden = false;
    return;
  }
  errorEl.hidden = true;
  resumeFile = f;
  setFileLabel(f.name);
}
drop.addEventListener("click", (e) => { if (e.target.id !== "removeFile") fileInput.click(); });
drop.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); fileInput.click(); } });
fileInput.addEventListener("change", () => pickFile(fileInput.files[0]));
["dragenter", "dragover"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.add("over"); }));
["dragleave", "drop"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.remove("over"); }));
drop.addEventListener("drop", (e) => pickFile(e.dataTransfer.files[0]));
$("removeFile").addEventListener("click", (e) => { e.stopPropagation(); resumeFile = null; fileInput.value = ""; setFileLabel(""); });

/* ---------- submit ---------- */
$("form").addEventListener("submit", async (e) => {
  e.preventDefault();
  errorEl.hidden = true;
  if (!$("job_url").value.trim() && $("job_text").value.trim().length < 100) {
    errorEl.textContent = "Add the job posting URL, or paste the job description (at least 100 characters).";
    errorEl.hidden = false;
    return;
  }
  if (!resumeFile && $("writeup").value.trim().length < 20) {
    errorEl.textContent = "Upload your resume or write at least 20 characters about yourself.";
    errorEl.hidden = false;
    return;
  }
  show("loading");
  buildSteps(["Starting…"]);
  try {
    const fd = new FormData();
    fd.append("job_url", $("job_url").value.trim());
    fd.append("job_text", $("job_text").value.trim());
    fd.append("github_url", $("github_url").value.trim());
    fd.append("writeup", $("writeup").value.trim());
    if (resumeFile) fd.append("resume", resumeFile);
    const d = await streamGenerate(fd);
    barFill.style.width = "100%";
    showResults(d);
  } catch (err) {
    errorEl.textContent = err.message;
    errorEl.hidden = false;
    show("form");
  }
});

/* ---------- copy / download ---------- */
function download(name, text) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([text], { type: "text/markdown" }));
  a.download = name;
  a.click();
  URL.revokeObjectURL(a.href);
}
$("copy").onclick = async (e) => {
  const t = data?.files[currentKey];
  if (!t) return;
  await navigator.clipboard.writeText(t);
  const label = e.currentTarget.querySelector("span");
  label.textContent = "Copied ✓";
  setTimeout(() => (label.textContent = "Copy"), 1400);
};
async function exportAs(fmt, btn) {
  const md = data?.files[currentKey];
  if (!md) return;
  const label = btn.querySelector("span"), old = label.textContent;
  label.textContent = "Preparing…";
  btn.disabled = true;
  try {
    const res = await fetch("/api/export", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ markdown: md, format: fmt, filename: currentKey }),
    });
    if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || "Export failed");
    const a = document.createElement("a");
    a.href = URL.createObjectURL(await res.blob());
    a.download = `${currentKey}.${fmt}`;
    a.click();
    URL.revokeObjectURL(a.href);
  } catch (err) {
    alert(err.message);
  } finally {
    label.textContent = old;
    btn.disabled = false;
  }
}
document.querySelectorAll("#panelActions [data-fmt]").forEach((b) => (b.onclick = () => exportAs(b.dataset.fmt, b)));
$("download").onclick = () => data?.files[currentKey] && download(`${currentKey}.md`, data.files[currentKey]);
$("downloadAll").onclick = () => data && Object.entries(data.files).forEach(([k, v]) => download(`${k}.md`, v));
