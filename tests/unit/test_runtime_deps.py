"""實際啟動的 uvicorn 需要 WebSocket 函式庫；TestClient 不需要，所以要另外確認（002 即時同步）。"""

import importlib.util


def test_websocket_library_installed_for_uvicorn():
    assert importlib.util.find_spec("websockets") is not None, "請安裝 websockets，否則 /ws 會回 404，畫面無法即時同步"
