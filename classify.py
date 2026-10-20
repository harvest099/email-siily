#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
classify.py — LLM 分类器
读取 data/YYYY-MM-DD.json，调 NVIDIA NIM API（免费），输出 data/classified_YYYY-MM-DD.json

用法:
  python classify.py                       # 默认用 nemotron-3.5-super-vl-120b-a12b
  python classify.py <model>              # 指定模型
"""
import json, os, sys, re, datetime
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
PROMPT_FILE = ROOT / "prompts" / "classify.md"

DEFAULT_MODEL = "nvidia/nemotron-3.5-super-vl-120b-a12b"
FALLBACK_MODEL = "meta/llama-3.2-11b-vision-instruct"

# 代理端口（Clash 运行时用，不跑就直连）
PROXY_PORTS = ["7890", "7897", "7891", "1080", "10808"]
API_BASE = "https://integrate.api.nvidia.com/v1"

def _log(msg):
    print(msg, file=sys.stderr)

def find_proxy():
    """找一个开着的代理端口，没有就返回 None（直连）"""
    import socket
    for port in PROXY_PORTS:
        try:
            s = socket.create_connection(("127.0.0.1", int(port)), timeout=1)
            s.close()
            p = f"http://127.0.0.1:{port}"
            _log(f"[proxy] 使用 {p}")
            return p
        except Exception:
            continue
    _log("[proxy] 未检测到代理，走直连")
    return None

def get_key():
    """读取 NVIDIA API key：环境变量 > config.yaml 的 llm.api_key > pi 的 models.json"""
    key = os.environ.get("NVIDIA_API_KEY")
    if key:
        return key
    cfg = ROOT / "config.yaml"
    if cfg.exists():
        m = re.search(r'api_key:\s*"(nvapi-[A-Za-z0-9_-]+)"', open(cfg, encoding="utf-8").read())
        if m:
            return m.group(1)
    models_json = os.path.expanduser("~/.pi/agent/models.json")
    if not Path(models_json).exists():
        return None
    raw = open(models_json, encoding="utf-8").read()
    m = re.search(r'"apiKey"\s*:\s*"(nvapi-[A-Za-z0-9_-]+)"', raw)
    if m:
        return m.group(1)
    m = re.search(r"nvapi-[A-Za-z0-9_-]+", raw)
    return m.group(0) if m else None

def call_llm(model, messages, key, timeout=120, images=None, proxy=None):
    body = {"model": model, "messages": messages, "max_tokens": 4096}
    if images:
        img_content = []
        for b64 in images:
            img_content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
        img_content.append({"type": "text", "text": "请结合上面的图片和邮件内容进行分类。图片里如果有文字、截止日期、金额等关键信息，请优先采信图片中的内容。"})
        body["messages"] = list(messages) + [{"role": "user", "content": img_content}]
    data = json.dumps(body).encode()
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    url = API_BASE + "/chat/completions"
    req = urllib.request.Request(url, data=data, headers=headers)
    if proxy:
        ph = urllib.request.ProxyHandler({"http": proxy, "https": proxy})
        opener = urllib.request.build_opener(ph)
        r = json.load(opener.open(req, timeout=timeout))
    else:
        r = json.load(urllib.request.urlopen(req, timeout=timeout))
    return r["choices"][0]["message"]["content"]

def extract_json(text):
    """从 LLM 回复里抽 JSON（容错处理 ```json 包裹和前后废话）"""
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    if m:
        return json.loads(m.group(1))
    m = re.search(r"(\{.*\})", text, re.S)
    if m:
        return json.loads(m.group(1))
    raise ValueError("LLM 未返回 JSON: " + text[:200])

def find_mails_file():
    """找最近有邮件的 data/*.json（排除 classified_ 和 report_ 前缀的文件）。

    返回 (file, mails, is_fresh)：
      is_fresh=True 表示是当天新抓的邮件；False 表示当天为空、回退到了历史数据（应跳过分类）。
    """
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    today_file = DATA / f"{today}.json"
    if today_file.exists():
        try:
            mails = json.loads(today_file.read_text(encoding="utf-8"))
        except Exception:
            mails = []
        if mails:
            _log(f"[debug] 选中当天: {today_file.name}，{len(mails)} 封")
            return today_file, mails, True
        # 当天没有新邮件：不出简报（避免拿旧邮件冒充今天的），直接返回空
        _log(f"[debug] 当天 {today} 无新邮件，跳过分类")
        return today_file, [], False
    return None, None, False

def main():
    model = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_MODEL
    mails_file, mails, is_fresh = find_mails_file()
    if mails_file is None:
        _log("没有邮件数据，先跑 tool_imap.py")
        return 1
    if not is_fresh:
        _log("今天没有新邮件，不生成简报（避免用旧邮件充数）")
        return 0

    key = get_key()
    if not key:
        _log("找不到 NVIDIA API key（设置环境变量 NVIDIA_API_KEY 或配置 pi）")
        return 1

    # 发送给 LLM 时剥离超长 base64 图片字段（图片通过 images 参数单独传）
    mails_for_llm = []
    for m in mails:
        m2 = {k: v for k, v in m.items() if k != "images"}
        m2["image_count"] = len(m.get("images", []))
        mails_for_llm.append(m2)

    prompt = PROMPT_FILE.read_text(encoding="utf-8")
    user_msg = prompt + "\n\n## 邮件列表\n" + json.dumps(mails_for_llm, ensure_ascii=False, indent=2)

    all_images = []
    for m in mails:
        all_images.extend(m.get("images", []))

    _log(f"[1] 调用 LLM {model}，分类 {len(mails)} 封邮件（含 {len(all_images)} 张附件图）...")
    use_images = all_images or None
    proxy = find_proxy()

    try:
        if use_images and proxy:
            _log(f"[1] 视觉模式（代理 {proxy}），调用 {model} ...")
            raw = call_llm(model, [{"role": "user", "content": user_msg}], key, images=use_images, proxy=proxy)
        else:
            reason = "无图片" if not use_images else "无代理"
            _log(f"[1] 纯文本模式（{reason}），调用 {model} ...")
            raw = call_llm(model, [{"role": "user", "content": user_msg}], key, images=None, proxy=proxy)
    except Exception as e:
        _log(f"[1] LLM 调用失败: {e}")
        return 1

    try:
        result = extract_json(raw)
    except Exception:
        _log(f"[1] JSON 解析失败，保存原文以便排查")
        result = {"raw_llm_response": raw, "parse_error": True}

    day = mails_file.stem
    out = DATA / f"classified_{day}.json"
    meta = {"day": day, "model": model, "ts": datetime.datetime.now().isoformat(),
            "emails_count": len(mails), "result": result}
    out.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    _log(f"[2] 分类结果 → {out}")
    print(json.dumps(result, ensure_ascii=False, indent=2)[:2000])
    return 0

if __name__ == "__main__":
    sys.exit(main())
