"""路由共用的相依函式。"""

from fastapi import Request

from guided_buzz.domain.errors import Unauthorized


def require_teacher(request: Request) -> str:
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    owner = request.app.state.auth.verify(token) if scheme == "Bearer" and token else None
    if owner is None:
        raise Unauthorized()
    return owner
