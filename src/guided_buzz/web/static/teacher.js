// 搶答主控台：Token 與活動 ID 存在 sessionStorage，各視窗身分互不影響（002 research R3）。
const TOKEN_KEY = "guided_buzz_teacher_token";
const ACTIVITY_KEY = "guided_buzz_teacher_activity";
const $ = (id) => document.getElementById(id);
const PHASE = { preparing: "準備中", running: "搶答中", ended: "已結束", interrupted: "已中斷" };
const STATUS = { no_submission: "尚無人搶答", won: "已搶答", open: "開放中（成功者已判無效）", no_winner: "無人搶答" };
const OUTCOME = { success: "成功", not_won: "未搶到", invalidated: "無效" };
let socket = null;
let current = null;
let pendingInvalidate = null;

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
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  const token = sessionStorage.getItem(TOKEN_KEY);
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(path, { ...options, headers });
  if (res.status === 401 && token) {
    sessionStorage.removeItem(TOKEN_KEY);
    showLoggedIn(false);
  }
  return res;
}

function showLoggedIn(loggedIn) {
  $("login-section").hidden = loggedIn;
  $("app").hidden = !loggedIn;
  $("logout").hidden = !loggedIn;
  if (loggedIn) {
    loadWorksheets();
    connect();
  }
}

function cell(text) {
  const td = document.createElement("td");
  td.textContent = text ?? "—";
  return td;
}

function button(text, onClick, secondary = false) {
  const b = document.createElement("button");
  b.textContent = text;
  if (secondary) b.className = "secondary";
  b.addEventListener("click", onClick);
  return b;
}

async function loadWorksheets() {
  const res = await api("/api/worksheets");
  if (!res.ok) return;
  const select = $("worksheet");
  select.replaceChildren();
  for (const ws of (await res.json()).filter((w) => w.status === "confirmed")) {
    const option = document.createElement("option");
    option.value = ws.id;
    option.textContent = `${ws.spreadsheet_title}（${ws.question_count} 題、${ws.group_count} 個題組）`;
    select.appendChild(option);
  }
  if (!select.options.length) showMessage("尚無已確認的學習單，請先到「學習單與結果」頁匯入並確認。", "error");
}

function render(activity) {
  current = activity;
  $("activity-section").hidden = !activity;
  if (!activity) return;
  sessionStorage.setItem(ACTIVITY_KEY, activity.id);
  $("phase").textContent = PHASE[activity.phase];
  const f = activity.fairness;
  $("activity-meta").textContent = `活動 ID：${activity.id}　公平機制：${f.enabled ? `啟用（領先 ${f.cooldown_lead} 題冷卻 ${f.cooldown_seconds} 秒）` : "停用"}`;
  $("start-btn").disabled = activity.phase !== "preparing";
  $("end-btn").disabled = activity.phase !== "running";

  const live = activity.phase === "preparing" || activity.phase === "running";
  const teams = $("team-rows");
  teams.replaceChildren();
  for (const t of activity.teams) {
    const tr = document.createElement("tr");
    tr.append(cell(t.name), cell(t.code), cell(t.wins), cell(t.cooldown_remaining ? `冷卻中（${t.cooldown_remaining} 秒）` : "—"));
    const td = document.createElement("td");
    if (live) td.appendChild(button("重新產生代碼", () => regenerate(t.id), true));
    tr.appendChild(td);
    teams.appendChild(tr);
  }

  const names = Object.fromEntries(activity.teams.map((t) => [t.id, t.name]));
  const units = $("unit-rows");
  units.replaceChildren();
  for (const u of activity.units) {
    const tr = document.createElement("tr");
    tr.append(cell(u.display), cell(STATUS[u.status]));
    const td = document.createElement("td");
    for (const s of u.submissions) {
      const line = document.createElement("div");
      const answers = Object.entries(s.answers).map(([no, a]) => `${no}：${a}`).join("；");
      line.textContent = `${s.rank}．${names[s.team_id]}．${answers}．${OUTCOME[s.outcome]} `;
      if (s.outcome === "success" && activity.phase !== "preparing") {
        if (pendingInvalidate === u.key) {
          line.append(button("確定判定無效", () => invalidate(u.key)), button("取消", () => { pendingInvalidate = null; render(current); }, true));
        } else {
          line.appendChild(button("判定無效", () => { pendingInvalidate = u.key; render(current); }, true));
        }
      }
      td.appendChild(line);
    }
    tr.appendChild(td);
    units.appendChild(tr);
  }
}

async function refresh() {
  const id = current?.id || sessionStorage.getItem(ACTIVITY_KEY);
  if (!id) return;
  const res = await api(`/api/activities/${id}`);
  if (res.ok) render(await res.json());
}

async function action(path, done) {
  const res = await api(path, { method: "POST" });
  const body = await readJson(res);
  if (!res.ok) return showMessage(formatError(body), "error");
  showMessage(done(body));
  await refresh();
}

function regenerate(teamId) {
  action(`/api/activities/${current.id}/teams/${teamId}/regenerate-code`, (b) => `已重新產生代碼：${b.code}，舊代碼與已加入的視窗都已失效。`);
}

function invalidate(unitKey) {
  pendingInvalidate = null;
  action(`/api/activities/${current.id}/units/${unitKey}/invalidate`, (b) =>
    b.promoted_team_id ? "已判定無效，由下一順位遞補成功。" : b.unit_status === "open" ? "已判定無效，沒有下一順位，這題重新開放。" : "已判定無效，這題標示為無人搶答。");
}

function connect() {
  if (socket && socket.readyState <= 1) return;
  socket = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`);
  socket.onopen = () => socket.send(JSON.stringify({ type: "auth", token: sessionStorage.getItem(TOKEN_KEY) }));
  socket.onmessage = (e) => {
    const msg = JSON.parse(e.data);
    if (msg.type === "snapshot") render(msg.activity || null);
    else refresh();
  };
  socket.onclose = (e) => {
    if (e.code === 4401) return; // Token 無效：等重新登入
    setTimeout(connect, 1000); // 斷線自動重連，重連後會重新收到完整快照
  };
}

$("login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const res = await api("/api/auth/teacher-login", { method: "POST", body: JSON.stringify({ password: $("password").value }) });
  const body = await readJson(res);
  if (!res.ok) return showMessage(formatError(body), "error");
  sessionStorage.setItem(TOKEN_KEY, body.token);
  $("password").value = "";
  showLoggedIn(true);
  showMessage("登入成功。");
});

$("logout").addEventListener("click", () => {
  sessionStorage.removeItem(TOKEN_KEY);
  if (socket) socket.close();
  showLoggedIn(false);
});

$("create-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const body = {
    worksheet_id: $("worksheet").value,
    teams: $("teams").value.split("\n").map((t) => t.trim()).filter(Boolean),
    fairness_enabled: $("fairness").checked,
  };
  if ($("cooldown-seconds").value) body.cooldown_seconds = Number($("cooldown-seconds").value);
  if ($("cooldown-lead").value) body.cooldown_lead = Number($("cooldown-lead").value);
  const res = await api("/api/activities", { method: "POST", body: JSON.stringify(body) });
  const data = await readJson(res);
  if (!res.ok) return showMessage(formatError(data), "error");
  render(data);
  showMessage("活動已建立。請把各組的組別代碼私下告訴各組，再按「開始搶答」。");
});

$("start-btn").addEventListener("click", () => action(`/api/activities/${current.id}/start`, () => "已開始搶答。"));
$("end-btn").addEventListener("click", () => action(`/api/activities/${current.id}/end`, () => "已結束搶答，結果已保存。可到「學習單與結果」頁寫回學習單或匯出 CSV。"));

setInterval(() => { if (current && current.teams.some((t) => t.cooldown_remaining)) refresh(); }, 1000);

(async () => {
  if (!sessionStorage.getItem(TOKEN_KEY)) return showLoggedIn(false);
  const res = await api("/api/auth/session");
  showLoggedIn(res.ok);
})();
