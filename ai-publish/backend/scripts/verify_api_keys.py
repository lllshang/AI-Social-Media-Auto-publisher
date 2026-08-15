#!/usr/bin/env python3
"""验证已配置的 AI 提供商 API Key 是否仍然有效。

调用各平台 OpenAI 兼容的 /v1/models 接口，只拉模型列表，不消耗额度。
用法：
    cd ai-publish/backend
    source .venv/bin/activate
    python scripts/verify_api_keys.py
"""

import asyncio
import sys
from pathlib import Path

# 把 backend 目录加入模块路径
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import httpx

from app.services.ai_provider_config_service import AiProviderConfigService

# provider_id -> (key_field, base_url_field, default_base_url, label)
PROVIDERS = {
    "tencent_maas": (
        "tencent_maas_api_key",
        "tencent_maas_base_url",
        "https://tokenhub.tencentmaas.com/v1",
        "腾讯 MaaS (TokenHub)",
    ),
    "minimax": (
        "minimax_api_key",
        "minimax_base_url",
        "https://api.minimax.io/v1",
        "MiniMax",
    ),
    "doubao": (
        "doubao_api_key",
        "doubao_base_url",
        "https://ark.cn-beijing.volces.com/api/v3",
        "字节豆包 (火山方舟)",
    ),
}


def mask_key(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return "*" * len(key)
    return key[:4] + "****" + key[-4:]


def detect_key_source(config: AiProviderConfigService, key_field: str) -> str:
    """判断 Key 来自环境变量还是运行时配置文件。"""
    from app.config import get_settings

    env_val = getattr(get_settings(), key_field, "") or ""
    raw = config._load_raw()
    stored = raw.get(key_field, "")
    if stored:
        return "runtime file (data/ai_provider_config.json)"
    if env_val:
        return ".env / environment"
    return "none"


async def check_provider(
    client: httpx.AsyncClient,
    config: AiProviderConfigService,
    label: str,
    key_field: str,
    base_url: str,
) -> dict:
    api_key = config.get_field_value(key_field)
    result = {
        "label": label,
        "configured": bool(api_key),
        "key_masked": mask_key(api_key),
        "base_url": base_url,
        "source": detect_key_source(config, key_field),
        "ok": False,
        "status": None,
        "models": 0,
        "error": None,
    }
    if not api_key:
        result["error"] = "未配置 API Key"
        return result

    url = base_url.rstrip("/") + "/models"
    # 先尝试标准 Bearer 格式
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    try:
        resp = await client.get(url, headers=headers, timeout=30)
        # MiniMax 某些场景下要求直接 Authorization: {key}，失败后重试
        if resp.status_code == 401 and label == "MiniMax":
            headers = {"Authorization": api_key, "Accept": "application/json"}
            resp = await client.get(url, headers=headers, timeout=30)

        result["status"] = resp.status_code
        if resp.status_code == 200:
            data = resp.json()
            models = data.get("data") or []
            result["ok"] = True
            result["models"] = len(models)
            result["sample_models"] = [m.get("id") for m in models[:5]]
        else:
            try:
                result["error"] = resp.json()
            except Exception:
                result["error"] = resp.text[:300]
    except httpx.TimeoutException:
        result["error"] = "请求超时"
    except Exception as e:
        result["error"] = str(e)
    return result


async def main() -> int:
    config = AiProviderConfigService()
    results = []

    async with httpx.AsyncClient() as client:
        tasks = []
        for provider_id, (key_field, base_field, default_url, label) in PROVIDERS.items():
            base_url = config.get_field_value(base_field) or default_url
            tasks.append(check_provider(client, config, label, key_field, base_url))
        results = await asyncio.gather(*tasks)

    print("=" * 60)
    print("API Key 连通性验证结果（仅拉模型列表，不消耗额度）")
    print("=" * 60)

    any_ok = False
    for r in results:
        print(f"\n提供商: {r['label']}")
        print(f"  配置 Key: {r['key_masked'] or '无'}")
        print(f"  Key 来源: {r['source']}")
        print(f"  Base URL: {r['base_url']}")
        if not r["configured"]:
            print("  状态: ❌ 未配置 API Key")
            continue
        if r["ok"]:
            any_ok = True
            print(f"  状态: ✅ 有效，可调用 /v1/models")
            print(f"  模型数量: {r['models']}")
            if r.get("sample_models"):
                print(f"  部分模型: {', '.join(r['sample_models'])}")
        else:
            print(f"  状态: ❌ 无效或请求失败 (HTTP {r['status']})")
            print(f"  错误: {r['error']}")

    print("\n" + "=" * 60)
    print("提示：")
    print("  - 本脚本只验证 Key 能否访问模型列表，不查询余额。")
    print("  - 余额/套餐是否过期，请登录对应官方控制台查看。")
    print("  - TokenHub 若不支持 /v1/models，可改用项目内的生图/生成功能实际测试一次。")
    print("=" * 60)
    return 0 if any_ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
