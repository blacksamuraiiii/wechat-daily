"""
@Time : 2025/9/8 8:45
@Author : black_samurai
@File : send_message.py
@description : 企业微信消息推送模块（支持超长消息自动分片）
"""

import json
import os
import tempfile
import time

import requests

# 企业微信 text 消息 content 硬上限：2048 字节（UTF-8），超出部分被服务端静默截断，
# 接口仍返回 errcode=0，所以必须在客户端自己切分。
WECOM_TEXT_LIMIT = 2048
# 单片实际发送上限：给分片标记和编码边界留余量
DEFAULT_SEND_LIMIT = 1900


def byte_len(text):
    """UTF-8 字节长度（企业微信按字节计，不按字符计）。"""
    return len(text.encode("utf-8"))


def split_by_bytes(text, limit=DEFAULT_SEND_LIMIT):
    """
    按 UTF-8 字节把长文本切成多片，单片不超过 limit 字节。

    优先在换行处断开，保证邮件条目、段落不被腰斩；单行自身超限时才硬切。

    Args:
        text: 待切分文本
        limit: 单片字节上限

    Returns:
        list[str]: 切分后的文本片段
    """
    if not text:
        return [""]
    if byte_len(text) <= limit:
        return [text]

    parts = []
    buf = ""
    for line in text.split("\n"):
        if byte_len(line) > limit:
            # 单行超限：先落盘已攒内容，再把这一行按字节硬切
            if buf:
                parts.append(buf)
                buf = ""
            chunk = ""
            for ch in line:
                if byte_len(chunk + ch) > limit:
                    parts.append(chunk)
                    chunk = ch
                else:
                    chunk += ch
            buf = chunk
            continue

        candidate = line if not buf else buf + "\n" + line
        if byte_len(candidate) > limit:
            parts.append(buf)
            buf = line
        else:
            buf = candidate

    if buf:
        parts.append(buf)
    return parts


def _token_cache_path(wxid):
    return os.path.join(tempfile.gettempdir(), f"wecom_token_{wxid[:12]}.json")


def get_access_token(wxid, wxsecret):
    """
    获取 access_token，带本地文件缓存。

    企业微信 gettoken 有调用频次限制，且短期内重复获取会使旧 token 失效，
    缓存可避免每条消息都换一次 token。

    Returns:
        str|None: access_token，失败返回 None
    """
    cache = _token_cache_path(wxid)
    try:
        with open(cache, encoding="utf-8") as f:
            data = json.load(f)
        if data.get("secret") == wxsecret and data.get("expires_at", 0) > time.time() + 300:
            return data.get("access_token")
    except (OSError, ValueError):
        pass

    token_url = f"https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={wxid}&corpsecret={wxsecret}"
    try:
        resp = requests.get(token_url, timeout=10).json()
    except Exception as e:
        print(f"获取token异常: {e}")
        return None

    if resp.get("errcode") != 0:
        print(f"获取token失败: errcode={resp.get('errcode')} {resp.get('errmsg', '未知错误')}")
        return None

    token = resp.get("access_token")
    try:
        with open(cache, "w", encoding="utf-8") as f:
            json.dump({"access_token": token, "secret": wxsecret,
                       "expires_at": time.time() + int(resp.get("expires_in", 7200))}, f)
    except OSError:
        pass
    return token


def _send_one(token, agentid, touser, content):
    """发送一片文本。返回 (是否成功, 错误信息)。"""
    payload = {
        "agentid": agentid,
        "msgtype": "text",
        "touser": touser,
        "text": {"content": content},
        "safe": 0,
    }
    url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={token}"
    try:
        resp = requests.post(url, json=payload, timeout=15).json()
    except Exception as e:
        return False, f"请求异常: {e}"

    errcode = resp.get("errcode", 0)
    if errcode != 0:
        return False, f"errcode={errcode} {resp.get('errmsg', '未知错误')}"
    # invaliduser 表示部分收件人无效，消息对有效用户仍已投递
    if resp.get("invaliduser"):
        print(f"警告: 无效收件人 {resp['invaliduser']}")
    return True, ""


def send_message(wxid, wxsecret, agentid, touser, content, limit=DEFAULT_SEND_LIMIT):
    """
    发送消息到企业微信，超长内容自动切成多条按序发送。

    Args:
        wxid: 企业微信 CorpID
        wxsecret: 企业微信应用 Secret
        agentid: 企业微信应用 AgentID
        touser: 推送目标用户
        content: 要发送的消息内容
        limit: 单片字节上限（默认 1900，硬上限 2048）

    Returns:
        bool: 全部分片是否都发送成功
    """
    if not content:
        print("内容为空，跳过发送")
        return False

    limit = min(int(limit), WECOM_TEXT_LIMIT)
    # 先按 limit-16 切，给 "（1/9）\n" 这类分片标记留出字节
    parts = split_by_bytes(content, max(limit - 16, 200))
    total = len(parts)

    token = get_access_token(wxid, wxsecret)
    if not token:
        return False

    all_ok = True
    for idx, part in enumerate(parts, 1):
        body = f"（{idx}/{total}）\n{part}" if total > 1 else part
        ok, err = _send_one(token, agentid, touser, body)
        if not ok:
            # token 可能已失效，刷新后重试一次
            print(f"第 {idx}/{total} 片发送失败({err})，刷新 token 重试。")
            token = get_access_token(wxid, wxsecret) if "token" in err or "errcode=40014" in err \
                or "errcode=42001" in err else token
            ok, err = _send_one(token, agentid, touser, body)
        if ok:
            print(f"第 {idx}/{total} 片发送成功（{byte_len(body)} 字节）")
        else:
            all_ok = False
            print(f"第 {idx}/{total} 片发送失败: {err}")

    print("消息发送成功" if all_ok else "消息发送存在失败分片")
    return all_ok


if __name__ == '__main__':
    from dotenv import load_dotenv
    import sys

    load_dotenv(dotenv_path='../.env')
    wxid = os.getenv("WEIXIN_CORP_ID")
    wxsecret = os.getenv("WEIXIN_CORP_SECRET")
    agentid = os.getenv("WEIXIN_AGENT_ID")

    if len(sys.argv) > 1:
        touser = sys.argv[1]
    else:
        touser = os.getenv("WEIXIN_TO_USER")

    send_message(wxid, wxsecret, agentid, touser, 'hello,world!')
