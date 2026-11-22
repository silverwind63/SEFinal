// 老師頁面：Token 存在 sessionStorage，各視窗身分互不影響（research R9）
const TOKEN_KEY = "guided_buzz_teacher_token";
const $ = (id) => document.getElementById(id);
let currentWorksheet = null;

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

async function readJson(res) {
  try { return await res.json(); } catch { return null; }
}

function showLoggedIn(loggedIn) {
  $("login-section").hidden = loggedIn;
  $("app").hidden = !loggedIn;
  $("logout").hidden = !loggedIn;
}

function renderPreview(ws) {
  currentWorksheet = ws;
  $("writeback-worksheet").value = ws.id;
  $("preview").hidden = false;
  $("preview-title").textContent = `${ws.spreadsheet_title}（${{ pending: "待確認", confirmed: "已確認", cancelled: "已取消" }[ws.status]}）`;
  $("preview-summary").textContent = `題數 ${ws.question_count}、題組 ${ws.group_count}　學習單 ID：${ws.id}`;
  const tbody = $("preview-rows");
  tbody.replaceChildren();
  for (const q of ws.questions) {
    const tr = document.createElement("tr");
    for (const value of [q.question_no, q.source_label, q.sub_label, q.sheet, q.cell, q.group_no]) {
      const td = document.createElement("td");
      td.textContent = value ?? "—";
      tr.appendChild(td);
    }
    tbody.appendChild(tr);
  }
  const pending = ws.status === "pending";
  $("confirm-btn").disabled = !pending;
  $("cancel-btn").disabled = !pending;
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

for (const [id, action, done] of [["confirm-btn", "confirm", "已確認，這份學習單可以用來進行搶答。"], ["cancel-btn", "cancel", "已取消，可以重新輸入網址匯入。"]]) {
  $(id).addEventListener("click", async () => {
    if (!currentWorksheet) return;
    const res = await api(`/api/worksheets/${currentWorksheet.id}/${action}`, { method: "POST" });
    const body = await readJson(res);
    if (!res.ok) return showMessage(formatError(body), "error");
    renderPreview(action === "confirm" ? body : { ...currentWorksheet, status: body.status });
    showMessage(done);
  });
}

$("writeback-btn").addEventListener("click", async () => {
  const worksheetId = $("writeback-worksheet").value.trim();
  const activityId = $("activity-id").value.trim();
  if (!worksheetId || !activityId) return showMessage("請輸入學習單 ID 與活動 ID。", "error");
  showMessage("正在寫回 Google Sheets…");
  const res = await api(`/api/worksheets/${encodeURIComponent(worksheetId)}/writeback`, { method: "POST", body: JSON.stringify({ activity_id: activityId }) });
  const body = await readJson(res);
  if (!res.ok) return showMessage(formatError(body), "error");
  const list = (nos) => (nos.length ? `第 ${nos.join("、")} 題` : "無");
  showMessage(
    `寫回完成，請到 Google Sheets 查看。\n已填入：${list(body.filled)}\n沒有成功答案（維持空白）：${list(body.unfilled)}\n已有內容、未覆蓋：${list(body.skipped_non_empty)}`
  );
});

$("export-btn").addEventListener("click", async () => {
  const activityId = $("activity-id").value.trim();
  if (!activityId) return showMessage("請輸入活動 ID。", "error");
  const res = await api(`/api/activities/${encodeURIComponent(activityId)}/results.csv`);
  if (!res.ok) return showMessage(formatError(await readJson(res)), "error");
  const count = Number(res.headers.get("X-Record-Count"));
  const link = document.createElement("a");
  link.href = URL.createObjectURL(await res.blob());
  link.download = `搶答結果_${activityId}.csv`;
  link.click();
  URL.revokeObjectURL(link.href);
  showMessage(count === 0 ? "目前無紀錄，已下載只含標題列的 CSV。" : `已匯出 ${count} 筆紀錄。`);
});

(async () => {
  if (!sessionStorage.getItem(TOKEN_KEY)) return showLoggedIn(false);
  const res = await api("/api/auth/session");
  showLoggedIn(res.ok);
})();
