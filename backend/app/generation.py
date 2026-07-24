"""生成：OpenAI 兼容流式客户端。连接地址、密钥、模型、参数、提示词均由后台配置。"""
import json
import time

import httpx

from . import config


class GenerationError(Exception):
    def __init__(self, message: str, retryable: bool = False):
        super().__init__(message)
        self.retryable = retryable


def resolve_config(settings: dict) -> dict:
    def _f(key, default):
        try:
            return float(settings.get(key) or default)
        except (TypeError, ValueError):
            return default

    def _i(key, default):
        try:
            return int(float(settings.get(key) or default))
        except (TypeError, ValueError):
            return default

    try:
        extra = json.loads(settings.get("gen_extra_params") or "{}")
        if not isinstance(extra, dict):
            extra = {}
    except json.JSONDecodeError:
        extra = {}

    base_url = (settings.get("llm_base_url") or "").rstrip("/")
    return {
        "base_url": base_url,
        "api_key": settings.get("llm_api_key") or "",
        "model": settings.get("llm_model") or "",
        "temperature": _f("gen_temperature", 0.3),
        "top_p": _f("gen_top_p", 0.8),
        "max_tokens": _i("gen_max_tokens", 2000),
        "enable_thinking": str(settings.get("gen_enable_thinking", "0")).strip() in ("1", "true", "yes", "on"),
        "extra": extra,
        "is_dashscope": "dashscope" in base_url.lower(),
    }


def is_configured(cfg: dict) -> bool:
    return bool(cfg["base_url"] and cfg["api_key"] and cfg["model"])


def build_user_prompt(complaint: str, materials: list[dict], service_area: str = "") -> str:
    lines = []
    if service_area:
        area = service_area if service_area.endswith("市") else service_area + "市"
        lines.append(f"【办理地域】{area}（回答须面向本地域，涉及具体经办部门、渠道时按本地域表述；不得引用其他地市的材料或做法）")
    lines += [f"【诉求】{complaint}", "", "【政策材料】"]
    for m in materials:
        meta = m.get("source") or "来源不详"
        if m.get("date"):
            meta += f"，{m['date']}"
        if m.get("doc_no"):
            meta += f"，{m['doc_no']}"
        body = "\n".join(
            (f"（{s['title']}）" if s.get("title") else "") + s["content"] for s in m.get("segments", [])
        )
        lines.append(f"材料{m['n']}（来源：{m['title']}；{meta}）：{body}")
    return "\n".join(lines)


def build_experience_prompt(complaint: str, cases: list[dict]) -> str:
    lines = [f"【当前诉求】{complaint}", "", "【历史案例】"]
    for i, c in enumerate(cases, 1):
        outcome = "、".join(x for x in (c.get("is_resolved"), c.get("is_satisfied")) if x) or "结果未记录"
        lines.append(
            f"案例{i}（{c.get('entry_date','')}，{c.get('location','')}，分类：{c.get('category','')}，办理结果：{outcome}）\n"
            f"诉求：{c.get('complaint','')}\n办理情况：{c.get('handling') or '未记录'}"
        )
    return "\n\n".join(lines)


def _build_body(cfg: dict, system: str, user: str, stream: bool, max_tokens: int | None = None) -> dict:
    body = {
        "model": cfg["model"],
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "temperature": cfg["temperature"],
        "top_p": cfg["top_p"],
        "max_tokens": max_tokens if max_tokens is not None else cfg["max_tokens"],
        "stream": stream,
    }
    if cfg["is_dashscope"] and not stream:
        body["enable_thinking"] = False
    elif cfg["is_dashscope"]:
        body["enable_thinking"] = cfg["enable_thinking"]
    if cfg.get("extra"):
        body.update(cfg["extra"])
    return body


def _raise_for_status(code: int):
    if code in (401, 403):
        raise GenerationError("生成接口鉴权失败，请检查后台配置的 API Key", retryable=False)
    if code == 402:
        raise GenerationError("生成接口账户余额不足，请充值或更换 API Key", retryable=False)
    if code == 404:
        raise GenerationError("生成接口地址或模型不存在，请检查调用地址与模型型号", retryable=False)
    if code == 429:
        raise GenerationError("生成接口限流，请稍后重试", retryable=True)
    if code >= 400:
        raise GenerationError(f"生成服务异常（HTTP {code}），请稍后重试", retryable=True)


def stream_chat(cfg: dict, system: str, user: str):
    if not is_configured(cfg):
        raise GenerationError("尚未配置生成模型，请在后台管理 → 生成模型接入 中完成配置并测试连接", retryable=False)
    headers = {"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"}
    url = cfg["base_url"] + "/chat/completions"
    try:
        with httpx.stream("POST", url, json=_build_body(cfg, system, user, True),
                          headers=headers, timeout=config.GEN_TIMEOUT) as resp:
            _raise_for_status(resp.status_code)
            for line in resp.iter_lines():
                if not line or not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                    piece = chunk["choices"][0].get("delta", {}).get("content") or ""
                except (KeyError, IndexError, json.JSONDecodeError):
                    continue
                if piece:
                    yield piece
    except httpx.TimeoutException:
        raise GenerationError("生成超时，请稍后重试", retryable=True)
    except httpx.HTTPError as e:
        raise GenerationError(f"生成网络异常：{e.__class__.__name__}", retryable=True)


def test_connection(base_url: str, api_key: str, model: str) -> dict:
    """后台「测试连接」：一次最小非流式调用，返回 {ok, message, latency_ms}。"""
    base_url = (base_url or "").rstrip("/")
    if not (base_url and api_key and model):
        return {"ok": False, "message": "调用地址、API Key、模型型号均需填写"}
    cfg = {"base_url": base_url, "api_key": api_key, "model": model,
           "temperature": 0.1, "top_p": 0.8, "max_tokens": 8, "enable_thinking": False,
           "extra": {}, "is_dashscope": "dashscope" in base_url.lower()}
    body = _build_body(cfg, "你是连接测试助手。", "回复两个字：正常", stream=False, max_tokens=8)
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    t0 = time.time()
    try:
        resp = httpx.post(base_url + "/chat/completions", json=body, headers=headers, timeout=config.GEN_TEST_TIMEOUT)
    except httpx.TimeoutException:
        return {"ok": False, "message": "连接超时，请检查调用地址与网络"}
    except httpx.HTTPError as e:
        return {"ok": False, "message": f"网络异常：{e.__class__.__name__}（请检查调用地址）"}
    latency = int((time.time() - t0) * 1000)
    try:
        _raise_for_status(resp.status_code)
    except GenerationError as e:
        return {"ok": False, "message": str(e), "latency_ms": latency}
    try:
        content = resp.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, json.JSONDecodeError):
        return {"ok": False, "message": "接口返回格式异常，可能不是 OpenAI 兼容端点", "latency_ms": latency}
    return {"ok": True, "message": f"连接正常，模型响应：{content.strip()[:20]}", "latency_ms": latency}
