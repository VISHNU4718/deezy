"""Vercel entry point: exposes the FastAPI app as a serverless function.

vercel.json rewrites /api/<path> to /api/index?p=<path>, so the original path is
restored here before the request reaches FastAPI's router.
"""

from urllib.parse import parse_qsl, urlencode

from deezy.interface.web.api import app as fastapi_app


async def app(scope, receive, send):
    if scope["type"] == "http" and scope["path"].rstrip("/") == "/api/index":
        query = dict(parse_qsl(scope.get("query_string", b"").decode()))
        rest = [(k, v) for k, v in parse_qsl(scope.get("query_string", b"").decode()) if k != "p"]
        path = "/api/" + query.get("p", "")
        scope = dict(scope, path=path, raw_path=path.encode(), query_string=urlencode(rest).encode())
    await fastapi_app(scope, receive, send)
