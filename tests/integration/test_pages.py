"""頁面網址、導向與畫面結構（specs/003-align-entry-pages/contracts/pages.md）。"""

import re

import pytest

PAGE_ROUTES = {"/", "/teacher", "/student.html", "/teacher.html"}
JOIN_HINT = "每個瀏覽器視窗各自保有自己的身分，可以在不同視窗分別開啟老師與各組畫面。"


def scripts(html: str) -> list[str]:
    return re.findall(r'<script[^>]*\bsrc="([^"]+)"', html)


def test_home_is_student_page(client):
    r = client.get("/")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    assert "加入組別" in r.text


def test_teacher_page(client):
    r = client.get("/teacher")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    assert "老師登入" in r.text


@pytest.mark.parametrize(("old", "new"), [("/student.html", "/"), ("/teacher.html", "/teacher")])
def test_old_urls_redirect(client, old, new):
    r = client.get(old, follow_redirects=False)
    assert r.status_code == 307
    assert r.headers["location"] == new


def test_page_routes_not_in_openapi(client):
    assert not PAGE_ROUTES & set(client.get("/openapi.json").json()["paths"])


@pytest.mark.parametrize("asset", ["/student.js", "/teacher.js", "/style.css"])
def test_static_assets_still_served(client, asset):
    assert client.get(asset).status_code == 200


# ---- 學生頁（FR-001、FR-002、FR-026）----


def test_student_page_join_section(client):
    html = client.get("/").text
    assert "<h2>加入組別</h2>" in html
    assert JOIN_HINT in html
    assert 'id="code"' in html
    assert re.search(r'<button[^>]*type="submit"[^>]*>加入</button>', html)
    assert re.search(r'<a[^>]*href="/teacher"[^>]*>我是老師</a>', html)


def test_student_page_has_no_teacher_parts(client):
    html = client.get("/").text
    assert 'type="password"' not in html
    assert scripts(html) == ["/student.js"]


# ---- 老師頁（FR-007～FR-009、FR-020、FR-026）----

TEACHER_SECTIONS = ["匯入學習單", "已確認的學習單", "建立搶答活動", "目前活動", "活動清單"]


def test_teacher_page_login_and_scripts(client):
    html = client.get("/teacher").text
    assert "<h2>老師登入</h2>" in html
    assert 'type="password"' in html
    assert scripts(html) == ["/teacher.js"]
    assert "<a " not in html  # 頁首與內容都沒有連到其他頁面的連結


def test_teacher_page_sections_in_order(client):
    headings = re.findall(r"<h2[^>]*>([^<]+)", client.get("/teacher").text)
    positions = [next(i for i, h in enumerate(headings) if h.startswith(name)) for name in TEACHER_SECTIONS]
    assert positions == sorted(positions)


def test_teacher_page_has_no_manual_id_inputs(client):
    html = client.get("/teacher").text
    assert "寫回答案與匯出結果" not in html
    assert "學習單 ID" not in html
    assert 'id="activity-id"' not in html


@pytest.mark.parametrize("path", ["/index.html", "/app.js"])
def test_old_teacher_entry_removed(client, path):
    assert client.get(path).status_code == 404
