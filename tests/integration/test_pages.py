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
