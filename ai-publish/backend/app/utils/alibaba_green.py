"""阿里云内容安全 Green 图片同步检测（经典 ACS 签名）。"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import uuid
from datetime import datetime, timezone

import httpx


def _content_md5(body: str) -> str:
    digest = hashlib.md5(body.encode("utf-8")).digest()
    return base64.b64encode(digest).decode("utf-8")


def _acs_authorization(
    *,
    access_key_id: str,
    access_key_secret: str,
    method: str,
    accept: str,
    content_type: str,
    date_str: str,
    content_md5: str,
    path: str,
) -> str:
    string_to_sign = f"{method}\n{accept}\n{content_md5}\n{content_type}\n{date_str}\n{path}"
    signature = base64.b64encode(
        hmac.new(access_key_secret.encode("utf-8"), string_to_sign.encode("utf-8"), hashlib.sha1).digest()
    ).decode("utf-8")
    return f"acs {access_key_id}:{signature}"


async def post_green_image_scan(
    *,
    access_key_id: str,
    access_key_secret: str,
    region: str,
    image_base64: str,
    timeout: float = 30.0,
) -> dict:
    host = f"green.{region}.aliyuncs.com"
    path = "/green/image/scan"
    url = f"https://{host}{path}"
    payload = {
        "scenes": ["porn", "terrorism", "ad", "qrcode"],
        "tasks": [{"dataId": str(uuid.uuid4()), "content": image_base64}],
    }
    body = json.dumps(payload, ensure_ascii=False)
    accept = "application/json"
    content_type = "application/json"
    date_str = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
    content_md5 = _content_md5(body)
    authorization = _acs_authorization(
        access_key_id=access_key_id,
        access_key_secret=access_key_secret,
        method="POST",
        accept=accept,
        content_type=content_type,
        date_str=date_str,
        content_md5=content_md5,
        path=path,
    )
    headers = {
        "Accept": accept,
        "Content-Type": content_type,
        "Content-MD5": content_md5,
        "Date": date_str,
        "Authorization": authorization,
        "x-acs-version": "2018-05-09",
    }
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(url, content=body, headers=headers)
        response.raise_for_status()
        return response.json()
