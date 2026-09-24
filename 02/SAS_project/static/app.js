"use strict";
/* 校務行政系統 SPA */

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (t) => String(t ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const groupBy = (arr, fn) => arr.reduce((m, x) => ((m[fn(x)] = m[fn(x)] || []).push(x), m), {});

let me = null;
let charts = {};

const WD = ["", "一", "二", "三", "四", "五", "六", "日"];
const PERIODS = ["", "第1節 08:10", "第2節 09:10", "第3節 10:10", "第4節 11:10", "第5節 13:10", "第6節 14:10", "第7節 15:10", "第8節 16:10", "第9節 17:10", "夜間A 18:30", "夜間B 19:30", "夜間C 20:30"];

const GRADE_LETTERS = {
  "A+": 4.3, A: 4.0, "A-": 3.7, "B+": 3.3, B: 3.0, "B-": 2.7,
  "C+": 2.3, C: 2.0, "C-": 1.7, "D+": 1.3, D: 1.0, "D-": 0.7, F: 0,
};

function badge(t) {
  const map = {
    出席: "green", 已繳: "green", 核准: "green", 錄取: "green", 開課: "green", 在學: "green", 大功: "green",
    遲到: "yellow", 撤銷: "yellow", "A-": "blue", "B+": "blue", B: "blue", "B-": "blue", "C+": "blue",
    病假: "blue", 審核中: "blue", 候補: "blue", 公假: "blue",
    曠課: "red", 未繳: "red", 未錄取: "red", 停開: "red", 休學: "red", 小過: "red", 大過: "red", 退學: "red", 申誡: "red",
  };
  const bg = map[t] || "gray";
  return `<span class="badge ${bg}">${esc(t)}</span>`;
}

function toast(msg, isErr = false) {
  const t = $("#toast");
  t.textContent = msg;
  t.classList.toggle("err", isErr);
  t.classList.remove("hidden");
  clearTimeout(t._h);
  t._h = setTimeout(() => t.classList.add("hidden"), 2600);
}

async function api(path, method = "GET", body = null) {
  const opts = { method, headers: {}, credentials: "same-origin" };
  if (body) { opts.headers["Content-Type"] = "application/json"; opts.body = JSON.stringify(body); }
  const res = await fetch(path, opts);
  const ct = res.headers.get("content-type") || "";
  if (ct.includes("text/csv")) return res; // 由呼叫者處理 blob
  let j = null;
  try { j = await res.json(); } catch (e) { j = { ok: false, error: "伺服器回應異常" }; }
  if (!res.ok || j.ok === false) { const e = new Error(j.error || j.message || "請求失敗"); e.status = res.status; throw e; }
  return j;
}

function openModal(title, body, foot) {
  $("#modalRoot").innerHTML = `
    <div class="modal-mask" onclick="if(event.target===this)closeModal()">
      <div class="modal">
        <div class="modal-head">${esc(title)}</div>
        <div class="modal-body">${body}</div>
        ${foot ? `<div class="modal-foot">${foot}</div>` : ""}
      </div>
    </div>`;
  return $("#modalRoot > .modal");
}
function closeModal() { $("#modalRoot").innerHTML = ""; }
function field(label, inner, extra) {
  return `<div class="field">${label ? `<label>${esc(label)}</label>` : ""}${inner}${extra || ""}</div>`;
}
function formField(fields, cols = 2) {
  const grid = cols > 1 ? " style='display:grid;grid-template-columns:1fr 1fr;gap:0 14px'" : "";
  return `<div${grid}>${fields.map((f) => field(f.label, f.control, f.hint)).join("")}</div>`;
}

function table(cols, rows, emptyText = "尚無資料") {
  if (!rows || !rows.length) return `<div class="empty">${emptyText}</div>`;
  return `<div class="timetable-wrap" style="overflow-x:auto">
    <table>
      <thead><tr>${cols.map((c) => `<th>${esc(c.name)}</th>`).join("")}</tr></thead>
      <tbody>${rows.map((r) => `<tr>${cols.map((c) => `<td>${c.render ? c.render(r, r[c.key], c) : esc(r[c.key])}</td>`).join("")}</tr>`).join("")}</tbody>
    </table></div>`;
}

function downloadCsv(url) {
  fetch(url, { credentials: "same-origin" })
    .then(async (r) => {
      if (!r.ok) { const j = await r.json().catch(() => null); throw new Error(j && j.error ? j.error : "下載失敗"); }
      const blob = await r.blob();
      const a = document.createElement("a");
      const dis = r.headers.get("content-disposition") || "";
      let fn = "report.csv";
      const m = dis.match(/filename\*=UTF-8''([^;]+)/);
      if (m) fn = decodeURIComponent(m[1]);
      else { const m2 = dis.match(/filename="([^"]+)"/); if (m2) fn = m2[1]; }
      a.href = URL.createObjectURL(blob);
      a.download = fn;
      a.click();
      setTimeout(() => URL.revokeObjectURL(a.href), 3000);
    })
    .catch((e) => toast(e.message, true));
}

/* ============================ 登入 ============================ */
function renderLogin() {
  const ls = $("#loginScreen");
  ls.classList.remove("hidden");
  $("#app").classList.add("hidden");
  ls.innerHTML = `
    <form class="card login-box" id="loginForm">
      <div class="login-logo">國立海嶼大學</div>
      <div class="login-sub">校務行政系統 113-1</div>
      <div class="field"><label>帳號</label><input name="username" required autocomplete="username" placeholder="admin / student / teacher / clerk"></div>
      <div class="field"><label>密碼</label><input name="password" type="password" required autocomplete="current-password" placeholder="預設 123456"></div>
      <button class="btn primary" style="width:100%;justify-content:center">登入</button>
      <div style="margin-top:14px;color:var(--muted);font-size:12px;line-height:1.7">示範帳號：<br>admin/admin123（系統管理員）<br>clerk/clerk123（行政人員）<br>teacher/teacher123（教師）<br>student/student123（學生）<br>其餘教師與學生帳號密碼為 123456</div>
    </form>`;
  $("#loginForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    try {
      await api("/api/login", "POST", { username: fd.get("username"), password: fd.get("password") });
      location.hash = "#/dashboard";
      await boot();
    } catch (err) { toast(err.message, true); }
  });
}

/* ============================ 選單 ============================ */
function menu() {
  const items = [
    { sec: "主要", role: "*" },
    { r: "dashboard", t: "儀表板", i: "📊", role: "*" },
    { r: "timetable", t: "課表查詢", i: "🗓️", role: "*" },
    { r: "announcements", t: "公告欄", i: "📢", role: "*" },
    { sec: "教務", role: "admin,clerk,teacher" },
    { r: "students", t: "學生管理", i: "🧑‍🎓", role: "admin,clerk" },
    { r: "faculties", t: "教職員管理", i: "👩‍🏫", role: "admin" },
    { r: "courses", t: "課程管理", i: "📚", role: "admin,clerk,teacher" },
    { r: "attendance", t: "點名管理", i: "✅", role: "admin,clerk,teacher" },
    { r: "grades", t: "成績管理", i: "📝", role: "admin,clerk,teacher" },
    { r: "leaves", t: "請假管理", i: "📋", role: "admin,clerk,teacher" },
    { sec: "選課", role: "admin,student,clerk" },
    { r: "selection", t: "選課系統", i: "🎯", role: "admin,student" },
    { sec: "學務/總務", role: "admin,clerk,student" },
    { r: "rewards", t: "獎懲紀錄", i: "🏅", role: "admin,clerk,student" },
    { r: "counseling", t: "諮商輔導", i: "💬", role: "admin,teacher,student" },
    { r: "invoices", t: "學雜費", i: "💰", role: "admin,clerk,student" },
    { r: "scholarships", t: "獎學金", i: "🏆", role: "admin,student" },
    { sec: "報表", role: "admin,clerk,teacher" },
    { r: "reports", t: "報表中心", i: "🧾", role: "admin,clerk,teacher" },
    { sec: "系統", role: "admin" },
    { r: "settings", t: "系統設定", i: "⚙️", role: "admin" },
  ];
  const show = (m) => m.role === "*" || m.role.split(",").includes(me.role);
  return items.filter(show);
}

function renderShell() {
  $("#loginScreen").classList.add("hidden");
  $("#app").classList.remove("hidden");
  const deptName = me.dept_name || "";
  $("#sidebar").innerHTML = `
    <div style="padding:18px 16px;border-bottom:1px solid var(--border)">
      <div style="font-weight:800;color:var(--accent);font-size:17px">校務行政系統</div>
      <div style="color:var(--muted);font-size:12px;margin-top:2px">${esc(deptName)}</div>
    </div>
    <nav class="sidebar-menu">${menu().map((m) =>
      m.sec ? `<div class="menu-sec">${esc(m.sec)}</div>`
        : `<a class="menu-item" data-r="${m.r}" href="#/${m.r}">${m.i}<span>${esc(m.t)}</span></a>`).join("")}
    </nav>
    <div style="padding:12px 16px;border-top:1px solid var(--border)">
      <div style="font-weight:600">${esc(me.name)}</div>
      <div style="color:var(--muted);font-size:12px">${esc(roleName())}｜${esc(me.username)}</div>
      <button class="btn sm" style="margin-top:8px" onclick="logout()">登出</button>
    </div>`;
  $("#topbar").innerHTML = `
    <div style="font-weight:700">${esc($("title").textContent)}</div>
    <div style="color:var(--muted);font-size:12px">國立海嶼大學 113-1 學期</div>`;
  $$(".menu-item").forEach((el) => el.classList.toggle("active", el.dataset.r === currentRoute()));
}

function roleName() {
  return { admin: "系統管理員", clerk: "行政人員", teacher: "教師", student: "學生" }[me.role] || me.role;
}

/* ============================ ROUTER ============================ */
function currentRoute() { return location.hash.replace(/^#\/?/, "").split("/")[0] || "dashboard"; }

function navigate() {
  const parts = location.hash.replace(/^#\/?/, "").split("/");
  let r = parts[0] || "dashboard";
  const p = parts[1];
  $$(".menu-item").forEach((el) => el.classList.toggle("active", el.dataset.r === r));
  const can = menu().filter((m) => m.r).map((m) => m.r);
  if (!can.includes(r)) { r = "dashboard"; }
  const views = {
    dashboard: vDashboard, timetable: vTimetable, announcements: vAnnouncements,
    students: () => vStudents(p), faculties: vFaculties, courses: () => (p && !isNaN(+p) ? vCourseRoster() : vCourses(p)),
    attendance: vAttendance, grades: vGrades, leaves: vLeaves, selection: vSelection,
    rewards: vRewards, counseling: vCounseling, invoices: vInvoices, scholarships: vScholarships,
    reports: vReports, settings: vSettings,
  };
  (views[r] || vDashboard)(p);
}

/* ============================ 儀表板 ============================ */
async function vDashboard() {
  const content = $("#content");
  content.innerHTML = `<div style="text-align:center;padding:60px">載入中…</div>`;
  try {
    const d = await api("/api/dashboard");
    let html = "";
    if (me.role === "student") {
      const tt = await api(`/api/timetable?who=student&id=${me.ref_id}`);
      const inv = await api("/api/invoices/me");
      const unpaid = inv.data.filter((x) => !x.paid).length;
      html += `<div class="stats-grid" style="margin-bottom:16px">`;
      html += `<div class="stat"><div class="num">${d.base.gpa}</div><div class="lab">累計 GPA</div></div>
        <div class="stat"><div class="num">${d.base.credits}<span style="font-size:14px;color:var(--muted)">/${d.base.credits_max}</span></div><div class="lab">已選學分</div></div>
        <div class="stat"><div class="num">${d.base.enrolled}</div><div class="lab">修習門數</div></div>
        <div class="stat"><div class="num">${unpaid}</div><div class="lab">未繳帳單</div></div></div>`;
      html += `<div class="two-col">
        <div class="card"><h2>我的課表（${tt.courses.length} 門）</h2>${buildGrid(tt.courses)}</div>
        <div class="card"><h2>成績分布</h2><div class="chart-box"><canvas id="chAtt"></canvas></div>
          <div style="color:var(--muted);font-size:12px;margin-top:8px">出缺勤：${Object.entries(d.attendance || {}).map(([k, v]) => `${k} ${v}`).join("｜")}</div></div>
      </div>`;
      content.innerHTML = html;
      charts.att = new Chart($("#chAtt"), {
        type: "doughnut",
        data: { labels: ["80分以上", "60-79分", "60分以下"], datasets: [{ data: [d.grade_dist.hi, d.grade_dist.mid, d.grade_dist.lo], backgroundColor: ["#3fb950", "#58a6ff", "#f85149"] }] },
        options: { plugins: { legend: { position: "bottom" } } },
      });
      return;
    }
    const paid = d.payment.paid, unpaid = d.payment.unpaid;
    const rate = paid + unpaid ? Math.round((paid / (paid + unpaid)) * 100) : 0;
    html += `<div class="stats-grid" style="margin-bottom:16px">`;
    html += `<div class="stat"><div class="num">${d.base.students}</div><div class="lab">在籍學生</div></div>
      <div class="stat"><div class="num">${d.base.faculties}</div><div class="lab">教職員</div></div>
      <div class="stat"><div class="num">${d.base.courses}</div><div class="lab">開課</div></div>
      <div class="stat"><div class="num">${rate}%</div><div class="lab">繳費率（${paid}/${paid + unpaid}）</div></div></div>`;
    html += `<div class="two-col">
      <div class="card"><h2>各系在籍人數</h2><div class="chart-box"><canvas id="chDept"></canvas></div></div>
      <div class="card"><h2>出缺勤統計</h2><div class="chart-box"><canvas id="chAtt"></canvas></div></div>
    </div>`;
    content.innerHTML = html;
    if (charts.dept) charts.dept.destroy();
    if (charts.att) charts.att.destroy();
    charts.dept = new Chart($("#chDept"), { type: "bar", data: { labels: d.dept_counts.map((x) => x.name), datasets: [{ label: "人數", data: d.dept_counts.map((x) => x.n), backgroundColor: "#58a6ff" }] }, options: { plugins: { legend: { display: false } }, scales: { x: { ticks: { color: "#8b949e" } }, y: { ticks: { color: "#8b949e" } } } } });
    charts.att = new Chart($("#chAtt"), { type: "doughnut", data: { labels: d.attendance.map((x) => x.status), datasets: [{ data: d.attendance.map((x) => x.n), backgroundColor: ["#d29922", "#58a6ff", "#8b949e", "#f85149", "#3fb950"] }] }, options: { plugins: { legend: { position: "bottom" } } } });
  } catch (e) { content.innerHTML = `<div class="card"><h2>儀表板無法載入</h2><p style="color:var(--red)">${esc(e.message)}</p></div>`; }
}

function miniTimetable(courses) {
  if (!courses || !courses.length) return { html: `<div class="empty">本學期無課程</div>` };
  const grid = buildGrid(courses);
  return { html: grid };
}
function buildGrid(courses) {
  const cellOf = new Map();
  courses.forEach((c) => {
    if (!c.weekday || !c.period_start) return;
    const key = `${c.weekday}_${c.period_start}`;
    const p = (cellOf.get(key) || []);
    if (p.length < 3) p.push(c);
    cellOf.set(key, p);
  });
  let out = `<div class="timetable-wrap"><table class="timetable"><thead><tr><th></th>`;
  for (let w = 1; w <= 5; w++) out += `<th>週${WD[w]}</th>`;
  out += `</tr></thead><tbody>`;
  for (let p = 1; p <= 12; p++) {
    out += `<tr><td class="slot">${PERIODS[p].split(" ")[1] || PERIODS[p]}</td>`;
    for (let w = 1; w <= 5; w++) {
      const cs = cellOf.get(`${w}_${p}`) || [];
      if (!cs.length) { out += `<td></td>`; continue; }
      out += `<td>${cs.map((c) => `<div class="cell-course"><div class="cn">${esc(c.name)}</div><div>${esc(c.room || "")}</div></div>`).join("")}</td>`;
    }
    out += `</tr>`;
  }
  return out += `</tbody></table></div>`;
}

/* ============================ 課表 ============================ */
async function vTimetable() {
  const content = $("#content");
  let sel = "";
  if (me.role === "student") {
    sel = `<div class="toolbar"><button class="btn primary" id="btnMe">我的課表</button> <button class="btn" id="btnDept">系所課表</button></div>`;
  } else if (me.role === "teacher") {
    sel = `<div class="toolbar"><button class="btn primary" id="btnMe">我的課表</button></div>`;
  } else {
    sel = `<div class="toolbar">
      <select id="dpDept"></select>
      <select id="dpGrade"><option value="">全部年級</option><option>1</option><option>2</option><option>3</option><option>4</option></select>
      <button class="btn primary" id="btnGrade">系所課表</button>
    </div>`;
  }
  content.innerHTML = `<h1>課表查詢</h1>${sel}<div id="ttArea"></div>`;
  const area = $("#ttArea");
  const showGrid = (d, h) => { area.innerHTML = `<div class="card"><h2>${h}（${d.courses.length} 門）</h2>${buildGrid(d.courses)}</div>`; };
  const btnMe = $("#btnMe");
  if (btnMe) btnMe.onclick = async () => {
    area.innerHTML = "載入中…";
    const q = me.role === "teacher" ? `who=teacher&id=${me.ref_id}` : `who=student&id=${me.ref_id}`;
    showGrid(await api(`/api/timetable?${q}`), me.role === "teacher" ? "我的授課" : "我的課表");
  };
  const btnDept = $("#btnDept");
  if (btnDept) btnDept.onclick = async () => {
    area.innerHTML = "載入中…";
    showGrid(await api(`/api/timetable?who=deptgrade&dept=${me.dept_id}&grade=`), "系所課表");
  };
  const dpDept = $("#dpDept");
  if (dpDept) {
    const depts = await api("/api/departments");
    dpDept.innerHTML = depts.data.map((d) => `<option value="${d.id}" ${me.role === "clerk" && d.id === me.dept_id ? "selected" : ""}>${esc(d.name)}</option>`).join("");
  }
  if (me.role === "student") $("#btnMe").onclick && $("#btnMe").click();
  if (me.role === "teacher") $("#btnMe").onclick && $("#btnMe").click();
  const btnGrade = $("#btnGrade");
  if (btnGrade) {
    btnGrade.onclick = async () => {
      area.innerHTML = "載入中…";
      showGrid(await api(`/api/timetable?who=deptgrade&dept=${$("#dpDept").value}&grade=${$("#dpGrade").value}`), "系所課表");
    };
    if (me.role === "clerk") btnGrade.click();
  }
}

/* ============================ 學生管理 ============================ */
async function vStudents(editingId) {
  const content = $("#content");
  const depts = await api("/api/departments");
  const opts = `<option value="">全部系所</option>` + depts.data.map((d) => `<option value="${d.id}">${esc(d.name)}</option>`).join("");
  content.innerHTML = `<h1>學生管理</h1>
    <div class="toolbar">
      <select id="fDept">${opts}</select>
      <select id="fGrade"><option value="">全部年級</option>${[1, 2, 3, 4].map((g) => `<option>${g}</option>`).join("")}</select>
      <input id="fQ" placeholder="姓名 / 學號搜尋" style="min-width:160px">
      <button class="btn" id="btnQ">🔍 查詢</button>
      <span style="flex:1"></span>
      <button class="btn primary" id="btnAdd">＋ 新增學生</button>
      <button class="btn" id="btnCsv">⬇ CSV</button>
    </div>
    <div class="card" id="stuArea"></div>`;
  const load = async () => {
    const dept = $("#fDept").value, grade = $("#fGrade").value, q = $("#fQ").value;
    const area = $("#stuArea");
    area.innerHTML = "載入中…";
    const d = await api(`/api/students?dept=${dept}&grade=${grade}&q=${encodeURIComponent(q)}`);
    const rows = d.data.map((s) => ({
      student_no: s.student_no, name: s.name, gender: s.gender, dept_name: s.dept_name, grade: s.grade, class_no: s.class_no, status: s.status,
      act: `<button class="btn sm" onclick="viewStudent(${s.id})">詳細</button>
            <button class="btn sm" onclick="editStudent(${s.id})">編輯</button>
            <button class="btn sm danger" onclick="delStudent(${s.id})">刪除</button>`,
    }));
    area.innerHTML = table(
      [{ name: "學號", key: "student_no" }, { name: "姓名", key: "name" }, { name: "性別", key: "gender" },
       { name: "系所", key: "dept_name" }, { name: "年級", key: "grade" }, { name: "座號", key: "class_no" },
       { name: "狀態", key: "status", render: (r, v) => badge(v) }, { name: "操作", key: "act", render: (r) => r.act }],
      rows);
  };
  $("#fDept").addEventListener("change", load);
  $("#fGrade").addEventListener("change", load);
  $("#fQ").addEventListener("keydown", (e) => e.key === "Enter" && load());
  $("#btnQ").addEventListener("click", load);
  $("#btnCsv").onclick = () => downloadCsv("/api/reports/students.csv");
  $("#btnAdd").onclick = () => openStudentModal(null);
  await load();
  if (editingId && !isNaN(parseInt(editingId))) openStudentModal(parseInt(editingId));
}

async function viewStudent(id) {
  const r = await api(`/api/students/${id}`);
  const d = r.profile;
  const t = { rows: (r.transcript || []).map((x) => ({ name: x.cname, credits: x.credits, midterm: x.midterm, final: x.final, total: x.total, grade_letter: x.grade_letter })), summary: r.summary || {} };
  openModal("學生資訊", `
    <div class="two-col">
      <div>
        <div style="font-weight:800;font-size:20px">${esc(d.name)}</div>
        <div style="color:var(--muted)">${esc(d.student_no)}｜${esc(d.dept_name)} ${d.grade}年級｜座號 ${d.class_no}</div>
        <div style="margin-top:8px">性別 ${esc(d.gender)}｜狀態 ${badge(d.status)}<br>電話 ${esc(d.phone || "–")}<br>Email ${esc(d.email || "–")}</div>
      </div>
      <div class="card" style="text-align:center">
        <div class="num" style="font-size:30px;color:var(--accent);font-weight:800">${(t.summary.gpa ?? "–")}</div>
        <div style="color:var(--muted)">GPA</div>
        <div style="color:var(--muted);font-size:12px">已得 ${t.summary.pass_credits ?? "–"}/${t.summary.total_credits ?? "–"} 學分</div>
      </div>
    </div>
    <div class="card" style="margin-top:14px"><h2>本學期成績</h2>
      ${table([{ name: "課程", key: "name" }, { name: "學分", key: "credits" }, { name: "期中", key: "midterm" }, { name: "期末", key: "final" }, { name: "總分", key: "total" }, { name: "等第", key: "grade_letter" }], t.rows, "尚無成績")}
    </div>`,
    `<button class="btn" onclick="closeModal()">關閉</button>
     <button class="btn primary" onclick="downloadCsv('/api/reports/transcript.csv?student_id=${id}')">下載成績單</button>
     <a class="btn" href="#/timetable" onclick="closeModal()">查看課表</a>`);
}
function editable() { return ["admin", "clerk"].includes(me.role); }

async function openStudentModal(id) {
  let s = null;
  if (id) s = (await api(`/api/students/${id}`)).profile;
  const depts = (await api("/api/departments")).data;
  const gOpts = (v) => [1, 2, 3, 4].map((x) => `<option value="${x}" ${String(v) === String(x) ? "selected" : ""}>${x}</option>`).join("");
  const dOpts = depts.map((d) => `<option value="${d.id}" ${s && s.dept_id === d.id ? "selected" : ""}>${esc(d.name)}</option>`).join("");
  openModal(id ? "編輯學生" : "新增學生", `
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:0 14px">
      <div class="field"><label>姓名</label><input id="fName" value="${esc(s?.name || "")}"></div>
      <div class="field"><label>性別</label><select id="fSex"><option>男</option><option>女</option></select></div>
      <div class="field"><label>系所</label><select id="fDept">${dOpts}</select></div>
      <div class="field"><label>年級</label><select id="fGrade">${gOpts(s?.grade || 1)}</select></div>
      <div class="field"><label>座號</label><input id="fNo" type="number" value="${s?.class_no ?? ""}"></div>
      <div class="field"><label>狀態</label><select id="fSt"><option ${s?.status === "在學" ? "selected" : ""}>在學</option><option ${s?.status === "休學" ? "selected" : ""}>休學</option><option ${s?.status === "退學" ? "selected" : ""}>退學</option></select></div>
      <div class="field"><label>電話</label><input id="fPhone" value="${esc(s?.phone || "")}"></div>
      <div class="field"><label>Email</label><input id="fMail" value="${esc(s?.email || "")}"></div>
    </div>
    ${id ? `<div style="color:var(--muted);font-size:12px">學號 ${esc(s.student_no)}（不可修改）</div>` : ""}`,
    `<button class="btn" onclick="closeModal()">取消</button><button class="btn primary" id="btnSave">儲存</button>`);
  if (id) $("#fSex").value = s.gender || "男";
  $("#btnSave").onclick = async () => {
    const body = {
      name: $("#fName").value.trim(), gender: $("#fSex").value, dept_id: +$("#fDept").value,
      grade: +$("#fGrade").value, class_no: +$("#fNo").value, status: $("#fSt").value,
      phone: $("#fPhone").value.trim(), email: $("#fMail").value.trim(),
    };
    try {
      await api(id ? `/api/students/${id}` : "/api/students", id ? "PUT" : "POST", body);
      toast("已儲存");
      closeModal(); vStudents();
    } catch (e) { toast(e.message, true); }
  };
}
function backToList(r) { vStudents(); }

async function editStudent(id) { openStudentModal(id); }
async function delStudent(id) {
  if (!confirm("確定刪除該學生？")) return;
  try { await api(`/api/students/${id}`, "DELETE"); toast("已刪除"); vStudents(); } catch (e) { toast(e.message, true); }
}

/* ============================ 教職員 ============================ */
async function vFaculties() {
  const content = $("#content");
  content.innerHTML = `<h1>教職員管理</h1>
    <div class="toolbar">
      <select id="fDept"></select>
      <span style="flex:1"></span>
      <button class="btn primary" id="btnAdd">＋ 新增教職員</button>
    </div>
    <div class="card" id="fcArea"></div>`;
  await loadDeptOptions("#fDept", true);
  const load = async () => {
    const d = await api(`/api/faculties?dept=${$("#fDept").value}`);
    d.data = d.data.map((f) => ({ ...f, act: `<button class="btn sm" onclick="editF(${f.id})">編輯</button><button class="btn sm danger" onclick="delF(${f.id})">刪除</button>` }));
    $("#fcArea").innerHTML = table(
      [{ name: "姓名", key: "name" }, { name: "性別", key: "gender" }, { name: "系所", key: "dept_name" },
       { name: "職稱", key: "title" }, { name: "專業領域", key: "expertise" }, { name: "電話", key: "phone" }, { name: "操作", key: "act", render: (r) => r.act }], d.data);
  };
  $("#fDept").addEventListener("change", load);
  $("#btnAdd").onclick = () => openFModal(null);
  await load();
}
async function loadDeptOptions(sel, includeAll = true) {
  const depts = await api("/api/departments");
  $(sel).innerHTML = (includeAll ? `<option value="">全部</option>` : "") + depts.data.map((d) => `<option value="${d.id}">${esc(d.name)}</option>`).join("");
}
async function openFModal(f) {
  const depts = (await api("/api/departments")).data;
  const dOpts = (f ? [f.dept_id] : []).concat(depts.map((d) => d.id).filter((x) => !f || x !== f.dept_id));
  const opt = depts.map((d) => `<option value="${d.id}" ${f && f.dept_id === d.id ? "selected" : ""}>${esc(d.name)}</option>`).join("");
  openModal(f ? "編輯教職員" : "新增教職員", `
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:0 14px">
      <div class="field"><label>姓名</label><input id="fName" value="${esc(f?.name || "")}"></div>
      <div class="field"><label>性別</label><select id="fSex"><option>男</option><option>女</option></select></div>
      <div class="field"><label>系所</label><select id="fDept">${opt}</select></div>
      <div class="field"><label>職稱</label><input id="fTitle" value="${esc(f?.title || "")}" placeholder="教授 / 副教授 / 行政助理"></div>
      <div class="field"><label>領域</label><input id="fExp" value="${esc(f?.expertise || "")}"></div>
      <div class="field"><label>電話</label><input id="fPhone" value="${esc(f?.phone || "")}"></div>
      <div class="field"><label>Email</label><input id="fMail" value="${esc(f?.email || "")}"></div>
    </div>`,
    `<button class="btn" onclick="closeModal()">取消</button><button class="btn primary" id="btnSave">儲存</button>`);
  if (f) $("#fSex").value = f.gender || "男";
  $("#btnSave").onclick = async () => {
    try {
      await api(f ? `/api/faculties/${f.id}` : "/api/faculties", f ? "PUT" : "POST", {
        name: $("#fName").value.trim(), gender: $("#fSex").value, dept_id: +$("#fDept").value,
        title: $("#fTitle").value.trim(), expertise: $("#fExp").value.trim(), phone: $("#fPhone").value.trim(), email: $("#fMail").value.trim(),
      });
      toast("已儲存"); closeModal(); vFaculties();
    } catch (e) { toast(e.message, true); }
  };
}
async function editF(id) { const d = (await api("/api/faculties")).data.find((x) => x.id === id); openFModal(d); }
async function delF(id) {
  if (!confirm("確定刪除？")) return;
  try { await api(`/api/faculties/${id}`, "DELETE"); toast("已刪除"); vFaculties(); } catch (e) { toast(e.message, true); }
}

/* ============================ 課程 ============================ */
async function vCourses(editingId) {
  const content = $("#content");
  const types = ["", "系必修", "系選修", "通識", "體育", "核心通識"];
  content.innerHTML = `<h1>課程管理</h1>
    <div class="toolbar">
      <select id="fType">${types.map((t) => `<option value="${t}">${t === "" ? "全部類別" : t}</option>`).join("")}</select>
      <select id="fDept"></select>
      <input id="fQ" placeholder="課程名稱搜尋" style="min-width:150px">
      <button class="btn primary" id="btnQ">🔍 查詢</button>
      <span style="flex:1"></span>
      ${["admin", "clerk"].includes(me.role) ? `<button class="btn primary" id="btnAdd">＋ 開設課程</button>` : ""}
      <button class="btn" id="btnCsv">⬇ CSV</button>
    </div>
    <div class="card" id="courseArea"></div>`;
  await loadDeptOptions("#fDept");
  const load = async () => {
    const d = await api(`/api/courses?type=${encodeURIComponent($("#fType").value)}&dept=${$("#fDept").value}&q=${encodeURIComponent($("#fQ").value)}`);
    const rows = d.data.map((c) => ({
      code: c.code, name: c.name, course_type: c.course_type, credits: c.credits,
      teacher_name: c.teacher_name, room: c.room, occupied: `${c.enrolled}/${c.max_students}`,
      status: c.status,
      act: `${["admin", "clerk"].includes(me.role) ? `<button class="btn sm" onclick="editCourse(${c.id})">編輯</button><button class="btn sm danger" onclick="delCourse(${c.id})">刪除</button>` : ""}
        <a class="btn sm" href="#/courses/${c.id}">名單</a><a class="btn sm" href="#/grades?c=${c.id}">成績</a>`,
    }));
    $("#courseArea").innerHTML = table(
      [{ name: "代碼", key: "code" }, { name: "課程", key: "name" }, { name: "類別", key: "course_type", render: (r, v) => badge(v) },
       { name: "學分", key: "credits" }, { name: "教師", key: "teacher_name" }, { name: "教室", key: "room" },
       { name: "選修", key: "occupied" }, { name: "狀態", key: "status", render: (r, v) => badge(v) }, { name: "操作", key: "act", render: (r) => r.act }], rows);
  };
  $("#btnQ").onclick = load;
  $("#fType").addEventListener("change", load);
  $("#fDept").addEventListener("change", load);
  $("#fQ").addEventListener("keydown", (e) => e.key === "Enter" && load());
  $("#btnCsv") && ($("#btnCsv").onclick = () => downloadCsv("/api/reports/courses.csv"));
  $("#btnAdd") && ($("#btnAdd").onclick = () => openCourseModal());
  await load();
}

async function vCourseRoster() {
  const cid = +location.hash.split("/")[2];
  const content = $("#content");
  const c = (await api(`/api/courses/${cid}`)).data;
  const d = await api(`/api/courses/${cid}/roster`);
  content.innerHTML = `<h1>修課名單：${esc(c.name)}</h1>
    <div style="color:var(--muted);margin-bottom:12px">${esc(c.code)}｜${esc(c.course_type)}｜${c.enrolled}/${c.max_students} 人｜教師 ${esc(c.teacher_name)}</div>
    <div class="toolbar">
      <button class="btn" onclick="history.back()">返回</button>
      <span style="flex:1"></span>
      <button class="btn" onclick="downloadCsv('/api/reports/grades.csv?course_id=${cid}')">成績報表 CSV</button>
    </div>
    <div class="card">${table([{ name: "學號", key: "student_no" }, { name: "姓名", key: "name" }, { name: "系所", key: "dept_name" }, { name: "年級", key: "grade" }, { name: "修課來源", key: "source" }], d.data)}</div>`;
}

async function openCourseModal(cid) {
  let c = null;
  if (cid) c = (await api(`/api/courses/${cid}`)).data;
  const depts = (await api("/api/departments")).data;
  const fac = (await api("/api/faculties")).data;
  const dOpts = depts.map((d) => `<option value="${d.id}" ${c && c.dept_id === d.id ? "selected" : ""}>${esc(d.name)}</option>`).join("");
  const fOpts = fac.map((f) => `<option value="${f.id}" ${c && c.teacher_id === f.id ? "selected" : ""}>${esc(f.name)}（${esc(f.title || "")}）</option>`).join("");
  const wOpts = [1, 2, 3, 4, 5, 6, 7].map((w) => `<option value="${w}" ${c && c.weekday === w ? "selected" : ""}>週${WD[w]}</option>`).join("");
  openModal(cid ? "編輯課程" : "開設課程", `
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:0 14px">
      <div class="field"><label>課程名稱 *</label><input id="fName" value="${esc(c?.name || "")}"></div>
      <div class="field"><label>學分 *</label><input id="fCred" type="number" value="${c?.credits ?? 2}"></div>
      <div class="field"><label>類別 *</label><select id="fType"><option ${c?.course_type === "系必修" ? "selected" : ""}>系必修</option><option ${c?.course_type === "系選修" ? "selected" : ""}>系選修</option><option ${c?.course_type === "通識" ? "selected" : ""}>通識</option><option ${c?.course_type === "體育" ? "selected" : ""}>體育</option><option ${c?.course_type === "核心通識" ? "selected" : ""}>核心通識</option></select></div>
      <div class="field"><label>系所</label><select id="fDept">${dOpts}</select></div>
      <div class="field"><label>授課教師 *</label><select id="fTeacher"><option value="">選擇教師</option>${fOpts}</select></div>
      <div class="field"><label>星期 *</label><select id="fW">${wOpts}</select></div>
      <div class="field"><label>起始節次 *</label><select id="fPs">${PERIODS.map((p, i) => i ? `<option value="${i}">${p}</option>` : "").join("").replace(/第(\d)節/g, "第$1節")}</select></div>
      <div class="field"><label>結束節次 *</label><select id="fPe">${PERIODS.map((p, i) => i ? `<option value="${i}">${p}</option>` : "").join("")}</select></div>
      <div class="field"><label>教室</label><input id="fRoom" value="${esc(c?.room || "")}"></div>
      <div class="field"><label>上限人數</label><input id="fMax" type="number" value="${c?.max_students ?? 30}"></div>
      <div class="field"><label>限制年級</label><select id="fGr"><option value="">不限</option>${[1, 2, 3, 4].map((g) => `<option ${String(c?.restriction_grade) === String(g) ? "selected" : ""}>${g}</option>`).join("")}</select></div>
      <div class="field"><label>課程代碼</label><input id="fCode" placeholder="自動產生" value="${esc(c?.code || "")}"></div>
    </div>`,
    `<button class="btn" onclick="closeModal()">取消</button><button class="btn primary" id="btnSave">儲存</button>`);
  if (c) { $("#fPs").value = c.period_start; $("#fPe").value = c.period_end; }
  $("#btnSave").onclick = async () => {
    const body = {
      name: $("#fName").value.trim(), credits: +$("#fCred").value, course_type: $("#fType").value,
      dept_id: +$("#fDept").value || null, teacher_id: +$("#fTeacher").value || null,
      weekday: +$("#fW").value, period_start: +$("#fPs").value, period_end: +$("#fPe").value,
      room: $("#fRoom").value.trim(), max_students: +$("#fMax").value || 30,
      restriction_grade: $("#fGr").value || null, code: $("#fCode").value.trim() || undefined,
    };
    try {
      if (cid) await api(`/api/courses/${cid}`, "PUT", body);
      else await api("/api/courses", "POST", body);
      toast("已儲存"); closeModal(); vCourses();
    } catch (e) { toast(e.message, true); }
  };
}
async function editCourse(id) { openCourseModal(id); }
async function delCourse(id) {
  if (!confirm("確定刪除課程？")) return;
  try { await api(`/api/courses/${id}`, "DELETE"); toast("已刪除"); vCourses(); } catch (e) { toast(e.message, true); }
}

/* ============================ 點名 ============================ */
async function vAttendance() {
  const content = $("#content");
  let myCourses = [];
  if (me.role === "teacher") {
    const d = await api("/api/courses");
    myCourses = d.data;
    const cOpts = myCourses.map((c) => `<option value="${c.id}">${esc(c.name)}（${c.weekday ? "週" + WD[c.weekday] : "?"} ${c.period_start || ""}）</option>`).join("");
    content.innerHTML = `<h1>點名管理</h1>
      <div class="toolbar">
        <select id="cSel" style="min-width:230px">${cOpts}</select>
        <input id="pDate" type="date" value="${new Date().toISOString().slice(0, 10)}">
        <button class="btn primary" id="btnLoad">載入點名表</button>
        <button class="btn primary" id="btnSave">儲存</button>
      </div>
      <div class="card" id="attArea"></div>`;
    const load = async () => {
      const cid = $("#cSel").value;
      if (!cid) return;
      const roster = (await api(`/api/courses/${cid}/roster`)).data;
      const date = $("#pDate").value;
      const existing = {};
      const att = await api(`/api/attendance?course_id=${cid}`);
      att.data.forEach((r) => { existing[r.student_id] = r.status; });
      const rows = roster.map((s) => {
        const st = existing[s.id] || "";
        return { student_no: s.student_no, name: s.name, status: st,
          ctrl: `<select class="attSel" data-sid="${s.id}" style="min-width:110px">${["", "出席", "遲到", "病假", "事假", "公假", "曠課"].map((x) => `<option ${st === x ? "selected" : ""}>${x}</option>`).join("")}</select>` };
      });
      $("#attArea").innerHTML = table([{ name: "學號", key: "student_no" }, { name: "姓名", key: "name" }, { name: "點名狀態", key: "ctrl", render: (r) => r.ctrl }], rows);
    };
    $("#btnLoad").onclick = load;
    $("#btnSave").onclick = async () => {
      const cid = $("#cSel").value, date = $("#pDate").value;
      const rows = $$(".attSel").map((sel) => ({ student_id: +sel.dataset.sid, status: sel.value || "出席" }));
      try { await api("/api/attendance/save", "POST", { course_id: +cid, date, rows }); toast("點名已儲存"); } catch (e) { toast(e.message, true); }
    };
    if (myCourses.length) load();
  } else if (me.role === "student") {
    const att = await api(`/api/attendance?student_id=${me.ref_id}`);
    content.innerHTML = `<h1>我的出缺勤</h1>
      <div class="card">${table([{ name: "日期", key: "date" }, { name: "課程", key: "cname" }, { name: "學分", key: "credits" }, { name: "教師", key: "teacher_name" }, { name: "狀態", key: "status", render: (r, v) => badge(v) }], att.data)}</div>`;
  } else {
    // admin/clerk overview
    content.innerHTML = `<h1>點名管理</h1>
      <div class="toolbar"><span style="color:var(--muted)">選擇課程進入點名／補登</span></div>
      <div class="card" id="attArea"></div>`;
    const d = await api("/api/courses");
    $("#attArea").innerHTML = table(
      [{ name: "課程", key: "name" }, { name: "類別", key: "course_type" }, { name: "教師", key: "teacher_name" }, { name: "已選課", key: "enrolled" },
       { name: "操作", key: "act", render: (r) => `<button class="btn sm" onclick="vAttendanceGoto(${r.id})">點名</button>` }], d.data);
  }
}
async function vAttendanceGoto(cid) {
  const date = new Date().toISOString().slice(0, 10);
  const roster = (await api(`/api/courses/${cid}/roster`)).data;
  const existing = {};
  (await api(`/api/attendance?course_id=${cid}`)).data.forEach((r) => { existing[r.student_id] = r.status; });
  const rows = roster.map((s) => ({ student_no: s.student_no, name: s.name, ctrl: `<select class="attSel" data-sid="${s.id}">${["出席", "遲到", "病假", "事假", "公假", "曠課"].map((x) => `<option ${existing[s.id] === x ? "selected" : ""}>${x}</option>`).join("")}</select>` }));
  content2(`
    <h1>點名（課程 #${cid}）</h1>
    <div class="toolbar"><input id="pDate" type="date" value="${date}"><button class="btn primary" onclick="saveAtt(${cid})">儲存</button></div>
    <div class="card">${table([{ name: "學號", key: "student_no" }, { name: "姓名", key: "name" }, { name: "狀態", key: "ctrl", render: (r) => r.ctrl }], rows)}</div>`);
}
function content2(html) { $("#content").innerHTML = html; }
async function saveAtt(cid) {
  const rows = $$(".attSel").map((s) => ({ student_id: +s.dataset.sid, status: s.value || "出席" }));
  try { await api("/api/attendance/save", "POST", { course_id: cid, date: $("#pDate").value, rows }); toast("已儲存"); vAttendance(); } catch (e) { toast(e.message, true); }
}

/* ============================ 成績 ============================ */
async function vGrades() {
  const content = $("#content");
  const qc = new URLSearchParams(location.hash.split("?")[1] || "").get("c");
  content.innerHTML = `<h1>成績管理</h1>
    <div class="toolbar"><select id="cSel"></select><button class="btn primary" id="btnLoad">載入</button></div>
    <div class="two-col">
      <div class="card" id="gArea"></div>
      <div class="card"><h2>成績分布</h2><div class="chart-box"><canvas id="chDist"></canvas></div><div id="gStats" style="margin-top:10px"></div></div>
    </div>`;
  const cids = new Set();
  if (me.role === "teacher") {
    const d = await api("/api/courses");
    d.data.forEach((c) => { if (me.role === "teacher") cids.add(c.id); });
    loadSel(d.data);
  } else {
    const d = await api("/api/courses");
    loadSel(d.data);
  }
  function loadSel(courses) {
    const sel = $("#cSel");
    sel.innerHTML = courses.map((c) => `<option value="${c.id}">${esc(c.name)}｜${esc(c.teacher_name)}</option>`).join("");
    if (qc) sel.value = qc;
  }
  const load = async () => {
    const cid = $("#cSel").value;
    if (!cid) return;
    const d = await api(`/api/grades?course_id=${cid}`);
    const rows = d.data.map((g) => ({
      student_no: g.student_no, name: g.name,
      mid: `<input type="number" step="0.5" class="gMid" data-sid="${g.student_id}" value="${g.midterm ?? ""}">`,
      fin: `<input type="number" step="0.5" class="gFin" data-sid="${g.student_id}" value="${g.final ?? ""}">`,
      total: g.total ?? "–", letter: g.grade_letter ? badge(g.grade_letter) : "–",
    }));
    $("#gArea").innerHTML = `<div class="toolbar"><div style="font-weight:700">課程成績</div><span style="flex:1"></span><button class="btn primary" onclick="saveGrades(${cid})">儲存成績</button><button class="btn" onclick="downloadCsv('/api/reports/grades.csv?course_id=${cid}')">CSV</button></div>` + table(
      [{ name: "學號", key: "student_no" }, { name: "姓名", key: "name" }, { name: "期中", key: "mid", render: (r) => r.mid },
       { name: "期末", key: "fin", render: (r) => r.fin }, { name: "總分", key: "total" }, { name: "等第", key: "letter", render: (r) => r.letter }], rows);
    const st = await api(`/api/grades/statistics?course_id=${cid}`);
    if (charts.dist) charts.dist.destroy();
    charts.dist = new Chart($("#chDist"), {
      type: "bar",
      data: { labels: Object.keys(st.dist || {}), datasets: [{ label: "人數", data: Object.values(st.dist || {}), backgroundColor: "#58a6ff" }] },
      options: { plugins: { legend: { display: false } } },
    });
    $("#gStats").innerHTML = st.stat ? `平均 ${st.stat.avg}｜最高 ${st.stat.mx}｜最低 ${st.stat.mn}｜共 ${st.stat.n} 人` : "";
  };
  $("#btnLoad").onclick = load;
  await load();
}
async function saveGrades(cid) {
  const rows = $$(".gMid").map((m) => ({ student_id: +m.dataset.sid, midterm: m.value ? +m.value : null, final: $(`.gFin[data-sid="${m.dataset.sid}"]`).value ? +$(`.gFin[data-sid="${m.dataset.sid}"]`).value : null }));
  try { await api("/api/grades/save", "POST", { course_id: cid, rows }); toast("成績已儲存"); vGrades(); } catch (e) { toast(e.message, true); }
}

/* ============================ 請假 ============================ */
async function vLeaves() {
  const content = $("#content");
  if (me.role === "student") {
    const d = await api("/api/leaves");
    content.innerHTML = `<h1>我的請假</h1>
      <div class="toolbar"><button class="btn primary" id="btnNew">＋ 申請請假</button></div>
      <div class="card">${table([{ name: "日期", key: "date" }, { name: "假別", key: "leave_type" }, { name: "事由", key: "reason" }, { name: "狀態", key: "status", render: (r, v) => badge(v) }], d.data)}</div>`;
    $("#btnNew").onclick = async () => {
      const tt = await api(`/api/timetable?who=student&id=${me.ref_id}`);
      const cOpts = tt.courses.map((c) => `<option value="${c.course_id}">${esc(c.name)}（週${WD[c.weekday]} ${c.period_start}~${c.period_end}節）</option>`).join("");
      openModal("申請請假", `
        <div class="field"><label>課程</label><select id="lc">${cOpts || `<option value="">無（事由假）</option>`}</select></div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:0 14px">
          <div class="field"><label>假別</label><select id="lt"><option>事假</option><option>病假</option><option>公假</option></select></div>
          <div class="field"><label>日期</label><input id="ld" type="date"></div>
          <div class="field"><label>節次（逗號分隔）</label><input id="lp" placeholder="1,2,3"></div>
        </div>
        <div class="field"><label>事由</label><textarea id="lr" rows="3"></textarea></div>`,
        `<button class="btn" onclick="closeModal()">取消</button><button class="btn primary" id="btnSave">送出</button>`);
      $("#btnSave").onclick = async () => {
        try {
          await api("/api/leaves", "POST", { course_id: +$("#lc").value || null, leave_type: $("#lt").value, date: $("#ld").value, periods: $("#lp").value.split(",").map((x) => +x).filter(Boolean), reason: $("#lr").value });
          toast("已送出申請"); closeModal(); vLeaves();
        } catch (e) { toast(e.message, true); }
      };
    };
  } else {
    const d = await api("/api/leaves");
    content.innerHTML = `<h1>請假管理</h1>
      <div class="card">${table(
        [{ name: "日期", key: "date" }, { name: "學生", key: "sname" }, { name: "假別", key: "leave_type" }, { name: "事由", key: "reason" }, { name: "狀態", key: "status", render: (r, v) => badge(v) },
         { name: "操作", key: "act", render: (r) => r.status === "審核中" ? `<button class="btn sm" onclick="lv(${r.id},'核准')">核准</button><button class="btn sm danger" onclick="lv(${r.id},'駁回')">駁回</button>` : "–" }], d.data)}</div>`;
  }
}
async function lv(id, st) {
  try { await api(`/api/leaves/${id}`, "PUT", { status: st }); toast("已處理"); vLeaves(); } catch (e) { toast(e.message, true); }
}

/* ============================ 選課 ============================ */
async function vSelection() {
  const content = $("#content");
  const st = await api("/api/selection/status");
  const phase = st.phase;
  const phaseTxt = { closed: "已關閉", initial: "初選（志願登記）", add_drop: "加退選" }[phase] || phase;

  if (me.role === "student") {
    content.innerHTML = `<h1>選課系統</h1>
      <div class="toolbar"><span class="badge ${phase === "closed" ? "red" : "blue"}">目前階段：${esc(phaseTxt)}</span>
        <span style="color:var(--muted)">｜上限 28 學分｜最多填 ${st.student_max} 個志願</span><span style="flex:1"></span></div>
      <div id="selArea"></div>`;
    const area = $("#selArea");
    if (phase === "initial") {
      const cat = await api("/api/selection/catalog");
      const mine = (await api("/api/selection/me")).selections;
      const mineIds = mine.filter((m) => m.status === "錄取").map((m) => m.course_id);
      const rows = cat.items.map((x) => ({
        name: x.name, course_type: x.course_type, credits: x.credits, dept_name: x.dept_name,
        time: x.weekday ? `週${WD[x.weekday]} ${x.period_start}~${x.period_end}節` : "–", seats: x.seats,
        flag: x.clash ? badge("衝堂") : x.full ? badge("額滿") : mineIds.includes(x.id) ? badge("已選") : "",
        val: `<input class="pk" type="checkbox" data-id="${x.id}" ${mineIds.includes(x.id) ? "checked" : ""}>`,
      }));
      area.innerHTML = `<div class="card"><h2>選課清單（點選志願，志願序依勾選順序）</h2>${table([{ name: "", key: "val", render: (r) => r.val }, { name: "課程", key: "name" }, { name: "類別", key: "course_type" }, { name: "學分", key: "credits" }, { name: "開課系", key: "dept_name" }, { name: "時間", key: "time" }, { name: "餘額", key: "seats" }, { name: "狀態", key: "flag", render: (r) => r.flag }], rows)}</div>
        <div class="toolbar" style="margin-top:12px"><button class="btn primary" id="btnApply">送出志願</button></div>`;
      $("#btnApply").onclick = async () => {
        const picks = $$(".pk:checked").map((cb, i) => ({ course_id: +cb.dataset.id, priority: i + 1 }));
        try { await api("/api/selection/apply", "POST", { selections: picks }); toast("志願已送出"); vSelection(); } catch (e) { toast(e.message, true); }
      };
    } else if (phase === "add_drop") {
      const cat = await api("/api/selection/catalog");
      const me0 = (await api("/api/selection/me")).selections;
      const enr = mineIdsOf(me0);
      const rows = cat.items.map((x) => ({
        name: x.name, course_type: x.course_type, credits: x.credits, time: x.weekday ? `週${WD[x.weekday]} ${x.period_start}~${x.period_end}` : "–", seats: x.seats,
        state: enr.has(x.id) ? badge("已修") : x.clash ? badge("衝堂") : x.full ? badge("額滿") : "",
        act: enr.has(x.id) ? `<button class="btn sm danger" onclick="selDrop(${x.id})">退選</button>` : (x.clash || x.full ? "–" : `<button class="btn sm" onclick="selAdd(${x.id})">加選</button>`),
      }));
      area.innerHTML = `<div class="card"><h2>加退選（可加選亦可知退選）</h2>${table([{ name: "課程", key: "name" }, { name: "類別", key: "course_type" }, { name: "學分", key: "credits" }, { name: "時間", key: "time" }, { name: "餘額", key: "seats" }, { name: "", key: "state", render: (r) => r.state }, { name: "操作", key: "act", render: (r) => r.act }], rows)}</div>`;
    } else {
      const cat = await api("/api/selection/catalog");
      const rows = cat.items.map((x) => ({
        name: x.name, course_type: x.course_type, credits: x.credits, time: x.weekday ? `週${WD[x.weekday]} ${x.period_start}~${x.period_end}` : "–", seats: x.seats,
      }));
      area.innerHTML = `<div class="card"><h2>課程一覽（選課系統已關閉目前僅供查詢）</h2>${table([{ name: "課程", key: "name" }, { name: "類別", key: "course_type" }, { name: "學分", key: "credits" }, { name: "時間", key: "time" }, { name: "餘額", key: "seats" }], rows)}</div>`;
    }
  } else {
    // admin
    const p = await api("/api/selection/popularity");
    content.innerHTML = `<h1>選課管理</h1>
      <div class="toolbar">
        <span class="badge ${phase === "closed" ? "red" : phase === "initial" ? "blue" : "green"}">${esc(phaseTxt)}</span>
        <button class="btn" id="bInit">切換到 <b>初選</b></button>
        <button class="btn" id="bAdd">切換到 <b>加退選</b></button>
        <button class="btn danger" id="bClose">關閉選課</button>
        ${phase === "initial" ? `<button class="btn primary" id="bSettle">▶ 執行結算</button>` : ""}
      </div>
      <div class="two-col">
        <div class="card"><h2>熱門課程排行（申請人次）</h2><div class="chart-box"><canvas id="chPop"></canvas></div></div>
        <div class="card"><h2>詳情</h2>
          ${table([{ name: "課程", key: "name" }, { name: "學分", key: "credits" }, { name: "申請", key: "apply_count" }, { name: "已選", key: "enrolled_count" }, { name: "上限", key: "max_students" }], p.data)}</div>
      </div>`;
    $("#bInit").onclick = () => api("/api/selection/open", "POST", { phase: "initial" }).then(() => { toast("已切換初選"); vSelection(); }).catch((e) => toast(e.message, true));
    $("#bAdd").onclick = () => api("/api/selection/open", "POST", { phase: "add_drop" }).then(() => { toast("已切換加退選"); vSelection(); }).catch((e) => toast(e.message, true));
    $("#bClose").onclick = () => api("/api/selection/open", "POST", { phase: "closed" }).then(() => { toast("已關閉選課"); vSelection(); }).catch((e) => toast(e.message, true));
    $("#bSettle") && ($("#bSettle").onclick = async () => { if (!confirm("執行志願結算？依志願序與名額錄取。")) return; try { await api("/api/selection/settle", "POST"); toast("結算完成"); vSelection(); } catch (e) { toast(e.message, true); } });
    if (charts.pop) charts.pop.destroy();
    charts.pop = new Chart($("#chPop"), { type: "bar", data: { labels: p.data.slice(0, 10).map((x) => x.name), datasets: [{ label: "申請人次", data: p.data.slice(0, 10).map((x) => x.apply_count), backgroundColor: "#58a6ff" }] }, options: { plugins: { legend: { display: false } }, indexAxis: "y" } });
  }
}
function mineIdsOf(mine) { return new Set(mine.map((m) => m.course_id)); }
async function selAdd(cid) { try { await api("/api/selection/add", "POST", { course_id: cid }); toast("已加選"); vSelection(); } catch (e) { toast(e.message, true); } }
async function selDrop(cid) { try { await api("/api/selection/drop", "POST", { course_id: cid }); toast("已退選"); vSelection(); } catch (e) { toast(e.message, true); } }

/* ============================ 獎懲 ============================ */
async function vRewards() {
  const content = $("#content");
  if (me.role === "student") {
    const d = await api("/api/rewards");
    content.innerHTML = `<h1>我的獎懲紀錄</h1><div class="card">${table([{ name: "日期", key: "date" }, { name: "類別", key: "rtype" }, { name: "事由", key: "reason" }, { name: "記錄人", key: "recorder_name" }], d.data)}</div>`;
  } else {
    content.innerHTML = `<h1>獎懲紀錄</h1>
      <div class="toolbar">
        <select id="fDept"></select><select id="fGrade"><option value="">全部年級</option>${[1, 2, 3, 4].map((g) => `<option>${g}</option>`).join("")}</select>
        <button class="btn" id="btnQ">查詢</button><span style="flex:1"></span>
        <button class="btn primary" id="btnAdd">＋ 新增紀錄</button>
      </div><div class="card" id="rwArea"></div>`;
    await loadDeptOptions("#fDept");
    const load = async () => {
      const d = await api(`/api/rewards?dept=${$("#fDept").value}&grade=${$("#fGrade").value}`);
      const rows = d.data.map((r) => ({ ...r, rtype: badge(r.rtype),
        act: `<button class="btn sm danger" onclick="delReward(${r.id})">刪除</button>` }));
      $("#rwArea").innerHTML = table(
        [{ name: "日期", key: "date" }, { name: "學號", key: "student_no" }, { name: "姓名", key: "name" }, { name: "系所", key: "dept_name" },
         { name: "類別", key: "rtype", render: (r) => r.rtype }, { name: "事由", key: "reason" }, { name: "操作", key: "act", render: (r) => r.act }], rows);
    };
    $("#btnQ").onclick = load;
    $("#btnAdd").onclick = async () => {
      const d = await api("/api/students");
      const sOpts = d.data.map((s) => `<option value="${s.id}">${esc(s.student_no)} ${esc(s.name)}（${esc(s.dept_name)} ${s.grade}年）</option>`).join("");
      openModal("新增獎懲紀錄", `
        <div class="field"><label>學生</label><select id="fStu">${sOpts}</select></div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:0 14px">
          <div class="field"><label>類別</label><select id="fType">${["大功", "小功", "嘉獎", "申誡", "小過", "大過"].map((x) => `<option>${x}</option>`).join("")}</select></div>
        </div>
        <div class="field"><label>事由</label><textarea id="fReason" rows="3"></textarea></div>`,
        `<button class="btn" onclick="closeModal()">取消</button><button class="btn primary" id="btnSave">儲存</button>`);
      $("#btnSave").onclick = async () => {
        try { await api("/api/rewards", "POST", { student_id: +$("#fStu").value, rtype: $("#fType").value, reason: $("#fReason").value }); toast("已新增"); closeModal(); load(); } catch (e) { toast(e.message, true); }
      };
    };
    await load();
  }
}
async function delReward(id) { if (!confirm("確定刪除？")) return; try { await api(`/api/rewards/${id}`, "DELETE"); toast("已刪除"); vRewards(); } catch (e) { toast(e.message, true); } }

/* ============================ 諮商 ============================ */
async function vCounseling() {
  const content = $("#content");
  const d = await api("/api/counseling");
  if (me.role === "student") {
    content.innerHTML = `<h1>諮商輔導</h1>
      <div class="toolbar"><button class="btn primary" id="btnAsk">＋ 發送求助訊息</button></div>
      <div class="card"><h2>我的紀錄</h2>${table([{ name: "日期", key: "date" }, { name: "輔導教師", key: "tname" }, { name: "主題", key: "topic" }, { name: "內容", key: "content" }], d.data)}</div>`;
    $("#btnAsk").onclick = () => {
      openModal("發送諮商訊息", `<div class="field"><label>想聊聊什麼？</label><textarea id="fMsg" rows="4"></textarea></div>`,
        `<button class="btn" onclick="closeModal()">取消</button><button class="btn primary" id="btnSave">送出</button>`);
      $("#btnSave").onclick = async () => { try { await api("/api/counseling", "POST", { message: $("#fMsg").value }); toast("已送出"); closeModal(); vCounseling(); } catch (e) { toast(e.message, true); } };
    };
  } else {
    const rows = d.data.map((m) => ({ date: m.date, student_no: m.student_no, sname: m.sname, content: m.content, topic: m.topic }));
    content.innerHTML = `<h1>諮商輔導中心</h1><div class="card">${table([{ name: "日期", key: "date" }, { name: "學號", key: "student_no" }, { name: "姓名", key: "sname" }, { name: "主題", key: "topic" }, { name: "訊息", key: "content" }], rows, "尚無訊息")}</div>`;
  }
}

/* ============================ 學雜費 ============================ */
async function vInvoices() {
  const content = $("#content");
  if (me.role === "student") {
    const d = await api("/api/invoices/me");
    const rows = d.data.map((x) => ({
      semester: x.semester, base: x.base_fee, cc: x.credit_count, cf: x.credit_fee, dorm: x.dorm_fee, total: x.total,
      paid: x.paid ? badge("已繳") : badge("未繳"), method: x.method || "–",
      act: x.paid ? "–" : `<button class="btn sm primary" onclick="payInv(${x.id})">立即繳費</button>`,
    }));
    content.innerHTML = `<h1>我要繳費</h1><div class="card">${table(
      [{ name: "學期", key: "semester" }, { name: "學雜費", key: "base" }, { name: "學分費", key: "cf" }, { name: "學分數", key: "cc" },
       { name: "住宿費", key: "dorm" }, { name: "總額", key: "total" }, { name: "狀態", key: "paid", render: (r) => r.paid }, { name: "方式", key: "method" }, { name: "操作", key: "act", render: (r) => r.act }], rows)}</div>`;
  } else {
    const d = await api("/api/invoices");
    const rows = d.data.map((x) => ({
      student_no: x.student_no, name: x.name, total: x.total, paid: x.paid ? badge("已繳") : badge("未繳"), method: x.method || "–",
      act: x.paid ? "–" : `<button class="btn sm" onclick="markPaid(${x.id})">標記已繳</button>`,
    }));
    content.innerHTML = `<h1>學雜費管理</h1>
      <div class="toolbar"><span style="flex:1"></span><button class="btn" onclick="downloadCsv('/api/reports/invoices.csv')">繳費清單 CSV</button></div>
      <div class="card">${table([{ name: "學號", key: "student_no" }, { name: "姓名", key: "name" }, { name: "總額", key: "total" }, { name: "狀態", key: "paid", render: (r) => r.paid }, { name: "方式", key: "method" }, { name: "操作", key: "act", render: (r) => r.act }], rows)}</div>`;
  }
}
async function payInv(id) {
  if (!confirm("確認完成繳費？")) return;
  try { await api(`/api/invoices/${id}`, "PUT", { status: "paid", method: "ATM" }); toast("繳費成功"); vInvoices(); } catch (e) { toast(e.message, true); }
}
async function markPaid(id) { try { await api(`/api/invoices/${id}`, "PUT", { status: "paid", method: "臨櫃" }); toast("已標記"); vInvoices(); } catch (e) { toast(e.message, true); } }

/* ============================ 獎學金 ============================ */
async function vScholarships() {
  const content = $("#content");
  if (me.role === "student") {
    const d = await api("/api/scholarships/me");
    content.innerHTML = `<h1>我的獎學金</h1><div class="card">${table([{ name: "學期", key: "semester" }, { name: "獎項", key: "name" }, { name: "金額", key: "amount" }, { name: "日期", key: "date" }], d.data, "目前無獲獎紀錄")}</div>`;
  } else {
    const d = await api("/api/scholarships");
    const rows = d.data.map((s) => ({ sname: s.sname, student_no: s.student_no, name: s.name, amount: s.amount, semester: s.semester, status: badge(s.status) }));
    content.innerHTML = `<h1>書卷獎與獎學金</h1><div class="card">${table([{ name: "學生", key: "sname" }, { name: "學號", key: "student_no" }, { name: "獎項", key: "name" }, { name: "金額", key: "amount" }, { name: "學期", key: "semester" }, { name: "狀態", key: "status", render: (r) => r.status }], rows)}</div>`;
  }
}

/* ============================ 公告 ============================ */
async function vAnnouncements() {
  const content = $("#content");
  const d = await api("/api/announcements");
  const list = d.data.map((a) => `
    <div class="card" style="margin-bottom:10px">
      <div style="display:flex;justify-content:space-between;gap:10px;align-items:center">
        <div><span class="badge ${a.pinned ? "yellow" : "blue"}">${esc(a.category || a.scope || "公告")}</span> <span style="font-weight:700">${esc(a.title)}</span></div>
        <div style="color:var(--muted);font-size:12px">${esc((a.created_at || "").slice(0, 10))}</div>
      </div>
      <div style="margin-top:8px;color:var(--text);white-space:pre-line">${esc(a.content)}</div>
      ${["admin", "clerk"].includes(me.role) ? `<div style="margin-top:8px"><button class="btn sm danger" onclick="delAnn(${a.id})">刪除</button></div>` : ""}
    </div>`).join("");
  content.innerHTML = `<h1>公告欄</h1>
    ${["admin", "clerk"].includes(me.role) ? `<div class="toolbar"><button class="btn primary" id="btnNew">＋ 發布公告</button></div>` : ""}
    ${list || `<div class="empty">尚無公告</div>`}`;
  $("#btnNew") && ($("#btnNew").onclick = () => {
    openModal("發布公告", `
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:0 14px">
        <div class="field"><label>標題</label><input id="fTitle"></div>
        <div class="field"><label>類別</label><select id="fCat"><option>校系公告</option><option>系辦公告</option><option>教務公告</option><option>課輔訊息</option></select></div>
      </div>
      <div class="field"><label>內容</label><textarea id="fBody" rows="4"></textarea></div>`,
      `<button class="btn" onclick="closeModal()">取消</button><button class="btn primary" id="btnSave">發布</button>`);
    $("#btnSave").onclick = async () => {
      try { await api("/api/announcements", "POST", { title: $("#fTitle").value, content: $("#fBody").value, category: $("#fCat").value }); toast("已發布"); closeModal(); vAnnouncements(); } catch (e) { toast(e.message, true); }
    };
  });
}
async function delAnn(id) { if (!confirm("確定刪除？")) return; try { await api(`/api/announcements/${id}`, "DELETE"); toast("已刪除"); vAnnouncements(); } catch (e) { toast(e.message, true); } }

/* ============================ 報表中心 ============================ */
async function vReports() {
  const content = $("#content");
  const rpt = [];
  if (["admin", "clerk"].includes(me.role)) {
    rpt.push(["學生名冊", "/api/reports/students.csv"], ["課程清單", "/api/reports/courses.csv"], ["學雜費繳費清單", "/api/reports/invoices.csv"]);
  }
  rpt.push(["我的課程資料（教師用）", "/api/reports/courses.csv"]);
  let html = `<h1>報表中心</h1><div class="two-col">`;
  rpt.forEach(([name, url]) => {
    html += `<div class="card" style="display:flex;justify-content:space-between;align-items:center;gap:10px">
      <div><div style="font-weight:700">${esc(name)}</div><div style="color:var(--muted);font-size:12px">下載 CSV</div></div>
      <button class="btn primary" onclick="downloadCsv('${url}')">⬇ 下載</button></div>`;
  });
  html += `</div>`;
  content.innerHTML = html;
}

/* ============================ 系統設定 ============================ */
async function vSettings() {
  const content = $("#content");
  const st = await api("/api/settings");
  content.innerHTML = `<h1>系統設定</h1>
    <div class="two-col">
      <div class="card"><h2>學校資訊</h2>
        <p>學校：${esc(st.school)}<br>目前學期：${esc(st.semester)}<br>選課上限：${esc(st.credit_cap ?? 28)} 學分<br>目前選課階段：${esc(st.phase)}</p>
      </div>
      <div class="card"><h2>選課階段控制</h2>
        <p style="color:var(--muted)">由「選課管理」頁切換階段並執行結算。</p>
      </div>
    </div>`;
}

/* ============================ 流程 ============================ */
async function boot() {
  try {
    me = (await api("/api/me")).user;
  } catch (e) {
    me = null;
  }
  if (!me) { renderLogin(); return; }
  renderShell();
  navigate();
}

async function logout() {
  try { await api("/api/logout", "POST"); } catch (e) {}
  location.hash = "";
  me = null;
  renderLogin();
}

window.addEventListener("hashchange", () => me && navigate());
boot();