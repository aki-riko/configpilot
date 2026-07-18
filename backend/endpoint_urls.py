# coding: utf-8
"""OpenAI 兼容接口基础地址的共享规范化逻辑。"""

from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit


def normalize_v1_base_url(value: str) -> str:
    """去除尾斜杠，并在路径末尾缺失时补充 ``/v1``。"""
    candidate = str(value or "").strip()
    if not candidate:
        return ""
    parsed = urlsplit(candidate)
    path = parsed.path.rstrip("/")
    if not path.lower().endswith("/v1"):
        path = f"{path}/v1" if path else "/v1"
    return urlunsplit(
        (parsed.scheme, parsed.netloc, path, parsed.query, parsed.fragment)
    )


def append_api_path(base_url: str, resource: str) -> str:
    """在规范化的 API 根路径后追加资源，同时保留 query/fragment。"""
    parsed = urlsplit(normalize_v1_base_url(base_url))
    resource_path = str(resource or "").strip().strip("/")
    path = parsed.path if not resource_path else f"{parsed.path}/{resource_path}"
    return urlunsplit(
        (parsed.scheme, parsed.netloc, path, parsed.query, parsed.fragment)
    )
