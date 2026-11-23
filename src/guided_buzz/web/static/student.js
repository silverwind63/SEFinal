// 學生頁面：Token、活動 ID、視窗 ID 都存在 sessionStorage，每個視窗是獨立的身分（FR-005a）。
// 畫面上的資料全部來自伺服器依本組身分過濾後的內容（FR-014）。
const TOKEN_KEY = "guided_buzz_student_token";
const ACTIVITY_KEY = "guided_buzz_student_activity";
const WINDOW_KEY = "guided_buzz_window_id";
const $ = (id) => document.getElementById(id);
const PHASE = { preparing: "準備中（等待老師開始）", running: "搶答中", ended: "已結束", interrupted: "已中斷" };
const OUTCOME = { success: "搶答成功！", not_won: "未搶到", invalidated: "已被老師判定無效" };
let socket = null;
let view = null;

function windowId() {
  let id = sessionStorage.getItem(WINDOW_KEY);
  if (!id) {
    id = crypto.randomUUID();
    sessionStorage.setItem(WINDOW_KEY, id);
  }
  return id;
}

function showMessage(text, kind = "ok") {
  const box = $("message");
  box.className = kind;
  box.textContent = text;
}

function formatError(body) {
  const error = body && body.error;
  return error ? error.message : "系統發生錯誤，請稍後再試。";
}

async function readJson(res) {
  try { return await res.json(); } catch { return null; }
}

async function api(path, options = {}) {
  const headers = { "Content-Type": "application/json", "X-Window-Id": windowId(), ...(options.headers || {}) };
  const token = sessionStorage.getItem(TOKEN_KEY);
  if (token) headers.Authorization = `Bearer ${token}`;
  return fetch(path, { ...options, headers });
}

function leave(message) {
  sessionStorage.removeItem(TOKEN_KEY);
  if (socket) {
    socket.onclose = null;
    socket.close();
  }
  $("app").hidden = true;
  $("join-section").hidden = false;
  $("team-name").textContent = "";
  showMessage(message, "error");
}

function render(v) {
  view = v;
  $("join-section").hidden = true;
  $("app").hidden = false;
  $("team-name").textContent = v.team.name;
  $("phase").textContent = PHASE[v.phase];
  $("cooldown").hidden = !v.cooldown_remaining;
  $("cooldown").textContent = `本組領先其他組別，冷卻中：${v.cooldown_remaining} 秒後才能再送出。`;

  const mine = Object.fromEntries(v.my_submissions.map((s) => [s.unit_key, s]));
  const box = $("units");
  box.replaceChildren();
  for (const u of v.units) {
    const form = document.createElement("form");
    form.className = "unit";
    const title = document.createElement("h3");
    title.textContent = u.display;
    form.appendChild(title);
    const done = mine[u.key];
    for (const no of u.question_nos) {
      const label = document.createElement("label");
      label.textContent = `第 ${no} 題`;
      const input = document.createElement("input");
      input.name = `q${no}`;
      input.maxLength = 1000;
      input.disabled = Boolean(done) || v.phase !== "running";
      if (done) input.value = done.answers[String(no)] ?? "";
      label.appendChild(input);
      form.appendChild(label);
    }
    const status = document.createElement("p");
    if (done) {
      status.textContent = done.outcome === "not_won" ? `未搶到，第 ${done.rank} 順位` : OUTCOME[done.outcome];
    } else {
      const submit = document.createElement("button");
      submit.textContent = "送出";
      submit.disabled = v.phase !== "running";
      form.appendChild(submit);
    }
    form.appendChild(status);
    form.addEventListener("submit", (e) => { e.preventDefault(); send(u, form); });
    box.appendChild(form);
  }

  $("results-section").hidden = !v.results;
  if (v.results) {
    const rows = $("result-rows");
    rows.replaceChildren();
    for (const u of v.results.units) {
      const tr = document.createElement("tr");
      const answers = u.winner ? Object.entries(u.winner.answers).map(([no, a]) => `${no}：${a}`).join("；") : "—";
      for (const text of [u.display, u.winner ? u.winner.team_name : "無人搶答", answers]) {
        const td = document.createElement("td");
        td.textContent = text;
        tr.appendChild(td);
      }
      rows.appendChild(tr);
    }
    $("team-wins").replaceChildren(...v.results.teams.map((t) => Object.assign(document.createElement("li"), { textContent: `${t.name}：${t.wins} 題` })));
  }
}

async function send(unit, form) {
  const answers = {};
  for (const no of unit.question_nos) answers[String(no)] = form.querySelector(`input[name="q${no}"]`).value;
  const res = await api("/api/submissions", { method: "POST", body: JSON.stringify({ unit_key: unit.key, answers }) });
  const body = await readJson(res);
  if (res.status === 401) return leave(formatError(body));
  if (!res.ok) return showMessage(formatError(body), "error");
  showMessage(body.message, body.outcome === "success" ? "ok" : "error");
  refresh();
}

async function refresh() {
  const res = await api("/api/me");
  if (res.status === 401) return checkInterrupted();
  if (res.ok) render(await res.json());
}

async function checkInterrupted() {
  const id = sessionStorage.getItem(ACTIVITY_KEY);
  if (id) {
    const res = await fetch(`/api/activities/${id}/phase`);
    const body = await readJson(res);
    if (res.ok && body.phase === "interrupted") return leave("活動已中斷，請老師重新建立。");
  }
  leave("組別身分已失效，請重新輸入組別代碼。");
}

function connect() {
  socket = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`);
  socket.onopen = () => socket.send(JSON.stringify({ type: "auth", token: sessionStorage.getItem(TOKEN_KEY) }));
  socket.onmessage = (e) => {
    const msg = JSON.parse(e.data);
    if (msg.type === "snapshot") return render(msg);
    if (msg.type === "session_revoked") return leave("老師已重新產生本組代碼，請向老師取得新代碼後重新加入。");
    if (msg.type === "invalidated" || msg.type === "promoted") showMessage(msg.message, msg.type === "promoted" ? "ok" : "error");
    refresh();
  };
  socket.onclose = (e) => {
    if (e.code === 4401 || e.code === 4403) return checkInterrupted();
    setTimeout(connect, 1000); // 斷線自動重連，重連後會重新收到完整快照
  };
}

$("join-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const res = await api("/api/join", { method: "POST", body: JSON.stringify({ code: $("code").value }) });
  const body = await readJson(res);
  if (!res.ok) return showMessage(formatError(body), "error");
  sessionStorage.setItem(TOKEN_KEY, body.token);
  sessionStorage.setItem(ACTIVITY_KEY, body.activity_id);
  $("code").value = "";
  showMessage(`已加入「${body.team.name}」。`);
  await refresh();
  connect();
});

setInterval(() => { if (view && view.cooldown_remaining) refresh(); }, 1000);

if (sessionStorage.getItem(TOKEN_KEY)) {
  refresh().then(() => { if (sessionStorage.getItem(TOKEN_KEY)) connect(); });
}
