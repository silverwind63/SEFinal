// 老師頁 /teacher：老師的所有功能都在這一頁（003）。
// Token 與「目前活動」的 ID 存在 sessionStorage，各視窗身分互不影響（003 data-model 第 2 節）。
const TOKEN_KEY = "guided_buzz_teacher_token";
const ACTIVITY_KEY = "guided_buzz_teacher_activity";
const $ = (id) => document.getElementById(id);
const PHASE = { preparing: "準備中", running: "搶答中", ended: "已結束", interrupted: "已中斷" };
const STATUS = { no_submission: "尚無人搶答", won: "已搶答", open: "開放中（成功者已判無效）", no_winner: "無人搶答" };
const OUTCOME = { success: "成功", not_won: "未搶到", invalidated: "無效" };
const WORKSHEET_STATUS = { pending: "待確認", confirmed: "已確認", cancelled: "已取消" };
let socket = null;
let current = null; // 「目前活動」區塊顯示的活動（002 的老師檢視資料，含 worksheet_id）
let worksheets = []; // GET /api/worksheets
let activities = []; // GET /api/activities
let preview = null; // 剛匯入、等待確認的學習單
let pendingInvalidate = null;

function showMessage(text, kind = "ok") {
  const box = $("message");
  box.className = kind;
  box.textContent = text;
}

function formatError(body) {
  const error = body && body.error;
  if (!error) return "系統發生錯誤，請稍後再試。";
  const lines = [error.message];
  for (const item of error.issues || []) {
    if (item.message !== error.message) lines.push("・" + item.message);
  }
  return lines.join("\n");
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

const shortId = (id) => id.slice(0, 8);
const time = (iso) => (iso ? new Date(iso).toLocaleString() : "—");

function cell(text) {
  const td = document.createElement("td");
  td.textContent = text ?? "—";
  return td;
}

function row(...values) {
  const tr = document.createElement("tr");
  tr.append(...values.map(cell));
  return tr;
}

function button(text, onClick, secondary = false) {
  const b = document.createElement("button");
  b.textContent = text;
  if (secondary) b.className = "secondary";
  b.addEventListener("click", onClick);
  return b;
}

// ---------- 登入與連線 ----------

function showLoggedIn(loggedIn) {
  $("login-section").hidden = loggedIn;
  $("app").hidden = !loggedIn;
  $("logout").hidden = !loggedIn;
  if (!loggedIn) return disconnect();
  loadWorksheets().then(loadActivities); // 活動清單要用學習單名稱
  refresh();
  connect();
}

function connect() {
  if (socket && socket.readyState <= 1) return;
  socket = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`);
  socket.onopen = () => socket.send(JSON.stringify({ type: "auth", token: sessionStorage.getItem(TOKEN_KEY) }));
  socket.onmessage = (e) => {
    const msg = JSON.parse(e.data);
    if (msg.type === "snapshot") {
      // 伺服器的快照固定是本次啟動後最近建立的活動：只在沒有檢視中的活動或同一場時更新畫面（research R7）
      if (msg.activity && (!current || msg.activity.id === current.id)) render(msg.activity);
      loadActivities();
      return;
    }
    if (msg.type === "phase_changed") loadActivities();
    refresh();
  };
  socket.onclose = (e) => {
    if (e.code === 4401) return; // Token 無效：等重新登入
    setTimeout(connect, 1000); // 斷線自動重連，重連後會重新收到快照
  };
}

function disconnect() {
  if (!socket) return;
  socket.onclose = null; // 登出後不自動重連（research R6）
  socket.close();
  socket = null;
}

// ---------- 匯入學習單、已確認的學習單 ----------

function renderPreview(ws) {
  preview = ws;
  $("preview").hidden = false;
  $("preview-title").textContent = `${ws.spreadsheet_title}（${WORKSHEET_STATUS[ws.status]}）`;
  $("preview-summary").textContent = `題數 ${ws.question_count}、題組 ${ws.group_count}　編號 ${shortId(ws.id)}`;
  $("preview-rows").replaceChildren(
    ...ws.questions.map((q) => row(q.question_no, q.source_label, q.sub_label, q.sheet, q.cell, q.group_no)),
  );
  const pending = ws.status === "pending";
  $("confirm-btn").disabled = !pending;
  $("cancel-btn").disabled = !pending;
}

async function loadWorksheets() {
  const res = await api("/api/worksheets");
  if (!res.ok) return;
  worksheets = await res.json();
  const confirmed = worksheets.filter((w) => w.status === "confirmed");
  $("no-worksheets").hidden = confirmed.length > 0;
  $("worksheet-rows").replaceChildren(
    ...confirmed.map((w) => row(shortId(w.id), w.spreadsheet_title, w.question_count, w.group_count, time(w.confirmed_at))),
  );
  const select = $("worksheet");
  const selected = select.value;
  select.replaceChildren(...confirmed.map((w) => new Option(`${w.spreadsheet_title}（${w.question_count} 題、${w.group_count} 個題組）`, w.id)));
  if (confirmed.some((w) => w.id === selected)) select.value = selected;
}

// ---------- 目前活動 ----------

// 在活動清單標出「目前活動」那一列：同一份學習單有多場活動時，才不會認錯要寫回的是哪一場
function markCurrentRow() {
  for (const tr of $("activity-rows").children) {
    const isCurrent = tr.dataset.id === current?.id;
    tr.classList.toggle("current", isCurrent);
    tr.querySelector("button").textContent = isCurrent ? "目前檢視中" : "檢視";
  }
}

function render(activity) {
  current = activity;
  markCurrentRow();
  $("no-activity").hidden = Boolean(activity);
  $("activity-detail").hidden = !activity;
  $("phase").textContent = activity ? PHASE[activity.phase] : "";
  if (!activity) return;
  sessionStorage.setItem(ACTIVITY_KEY, activity.id);
  const f = activity.fairness;
  const title = worksheets.find((w) => w.id === activity.worksheet_id)?.spreadsheet_title ?? shortId(activity.worksheet_id);
  const created = activities.find((a) => a.id === activity.id)?.created_at;
  $("activity-meta").textContent =
    `學習單：${title}　建立時間：${time(created)}　活動編號 ${shortId(activity.id)}\n` +
    `公平機制：${f.enabled ? `啟用（領先 ${f.cooldown_lead} 題冷卻 ${f.cooldown_seconds} 秒）` : "停用"}`;
  $("start-btn").disabled = activity.phase !== "preparing";
  $("end-btn").disabled = activity.phase !== "running";
  $("ended-actions").hidden = activity.phase !== "ended"; // 寫回與下載只在結束後出現（FR-015）

  const live = activity.phase === "preparing" || activity.phase === "running";
  $("team-rows").replaceChildren(
    ...activity.teams.map((t) => {
      const tr = row(t.name, t.code, t.wins, t.cooldown_remaining ? `冷卻中（${t.cooldown_remaining} 秒）` : "—");
      const td = document.createElement("td");
      if (live) td.appendChild(button("重新產生代碼", () => regenerate(t.id), true));
      tr.appendChild(td);
      return tr;
    }),
  );

  const names = Object.fromEntries(activity.teams.map((t) => [t.id, t.name]));
  $("unit-rows").replaceChildren(
    ...activity.units.map((u) => {
      const tr = row(u.display, STATUS[u.status]);
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
      return tr;
    }),
  );
}

async function refresh() {
  const id = current?.id || sessionStorage.getItem(ACTIVITY_KEY);
  if (!id) return render(null);
  const res = await api(`/api/activities/${id}`);
  if (res.ok) return render(await res.json());
  if (!current) {
    // 例如伺服器重啟後，之前檢視的活動已中斷：不再自動顯示它
    sessionStorage.removeItem(ACTIVITY_KEY);
    render(null);
  }
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

// ---------- 活動清單 ----------

async function loadActivities() {
  const res = await api("/api/activities");
  if (!res.ok) return;
  activities = await res.json();
  const titles = Object.fromEntries(worksheets.map((w) => [w.id, w.spreadsheet_title]));
  $("no-activities").hidden = activities.length > 0;
  $("activity-rows").replaceChildren(
    ...activities.map((a) => {
      const tr = row(shortId(a.id), titles[a.worksheet_id] ?? shortId(a.worksheet_id), PHASE[a.phase], time(a.created_at), time(a.ended_at));
      tr.dataset.id = a.id;
      const td = document.createElement("td");
      td.appendChild(button("檢視", () => view(a.id), true));
      tr.appendChild(td);
      return tr;
    }),
  );
  if (current) render(current); // 補上目前活動的建立時間，並標出目前那一列
  else markCurrentRow();
}

async function view(id) {
  const res = await api(`/api/activities/${id}`);
  const body = await readJson(res);
  if (!res.ok) return showMessage(formatError(body), "error"); // 例如已中斷：目前活動維持原樣（FR-019）
  pendingInvalidate = null;
  render(body);
  $("activity-section").scrollIntoView({ behavior: "smooth" });
  showMessage(`正在檢視活動 ${shortId(id)}（${PHASE[body.phase]}）。`);
}

// ---------- 事件 ----------

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
  showLoggedIn(false);
  showMessage("已登出。");
});

$("import-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  showMessage("正在從 Google Sheets 讀取學習單…");
  const res = await api("/api/worksheets", { method: "POST", body: JSON.stringify({ spreadsheet_url: $("sheet-url").value }) });
  const body = await readJson(res);
  if (!res.ok) {
    $("preview").hidden = true;
    return showMessage(formatError(body), "error");
  }
  renderPreview(body);
  showMessage("匯入成功，請核對題數與填空格位置後按「確認」。");
});

for (const [id, path, done] of [["confirm-btn", "confirm", "已確認，可以在「建立搶答活動」選擇這份學習單。"], ["cancel-btn", "cancel", "已取消，可以重新輸入網址匯入。"]]) {
  $(id).addEventListener("click", async () => {
    if (!preview) return;
    const res = await api(`/api/worksheets/${preview.id}/${path}`, { method: "POST" });
    const body = await readJson(res);
    if (!res.ok) return showMessage(formatError(body), "error");
    renderPreview(path === "confirm" ? body : { ...preview, status: body.status });
    await loadWorksheets(); // 已確認清單與建立活動的選單立即更新（FR-012）
    if (path === "confirm") $("worksheet").value = body.id;
    showMessage(done);
  });
}

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
  pendingInvalidate = null;
  render(data);
  loadActivities();
  showMessage("活動已建立。請把各組的組別代碼私下告訴各組，再按「開始搶答」。");
});

$("start-btn").addEventListener("click", () => action(`/api/activities/${current.id}/start`, () => "已開始搶答。").then(loadActivities));
$("end-btn").addEventListener("click", () =>
  action(`/api/activities/${current.id}/end`, () => "已結束搶答，結果已保存。可以按「寫回答案」或「下載 CSV」。").then(loadActivities));

$("writeback-btn").addEventListener("click", async () => {
  if (!current) return;
  showMessage("正在寫回 Google Sheets…");
  const res = await api(`/api/worksheets/${current.worksheet_id}/writeback`, { method: "POST", body: JSON.stringify({ activity_id: current.id }) });
  const body = await readJson(res);
  if (!res.ok) return showMessage(formatError(body), "error"); // 按鈕保持可用，處理好原因後可以再按（FR-016）
  const list = (nos) => (nos.length ? `第 ${nos.join("、")} 題` : "無");
  showMessage(`寫回完成，請到 Google Sheets 查看。\n已填入：${list(body.filled)}\n沒有成功答案（維持空白）：${list(body.unfilled)}\n已有內容、未覆蓋：${list(body.skipped_non_empty)}`);
});

$("export-btn").addEventListener("click", async () => {
  if (!current) return;
  const res = await api(`/api/activities/${current.id}/results.csv`);
  if (!res.ok) return showMessage(formatError(await readJson(res)), "error");
  const count = Number(res.headers.get("X-Record-Count"));
  const link = document.createElement("a");
  link.href = URL.createObjectURL(await res.blob());
  link.download = `搶答結果_${current.id}.csv`;
  link.click();
  URL.revokeObjectURL(link.href);
  showMessage(count === 0 ? "此活動沒有任何送出紀錄（已下載只含標題列的 CSV）。" : `已下載 CSV，共 ${count} 筆紀錄。`);
});

setInterval(() => { if (current && current.teams.some((t) => t.cooldown_remaining)) refresh(); }, 1000);

(async () => {
  if (!sessionStorage.getItem(TOKEN_KEY)) return showLoggedIn(false);
  const res = await api("/api/auth/session");
  showLoggedIn(res.ok);
})();
