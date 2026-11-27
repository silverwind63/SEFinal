"""頁面網址、導向與畫面結構（specs/003-align-entry-pages/contracts/pages.md）。"""

import pytest

PAGE_ROUTES = {"/", "/teacher", "/student.html", "/teacher.html"}


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
