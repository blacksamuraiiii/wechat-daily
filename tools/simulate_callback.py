#!/usr/bin/env python3
"""模拟企业微信回调，端到端验证 run.py：解密 -> 处理 -> CDATA 加密回复。
用法: simulate_callback.py "用户问题"
"""
import base64
import sys
import time
import uuid

import requests
from dotenv import load_dotenv
import os

sys.path.insert(0, "/www/py_project/wechat-daily")
load_dotenv("/www/py_project/wechat-daily/.env")
from src.WXBizMsgCrypt3 import WXBizMsgCrypt, Prpcrypt, SHA1  # noqa: E402
import xml.etree.cElementTree as ET  # noqa: E402

sToken = os.getenv("sToken")
sAES = os.getenv("sEncodingAESKey")
corpid = os.getenv("WEIXIN_CORP_ID")
agentid = os.getenv("WEIXIN_AGENT_ID")
user = "HuangWeiShen"
question = sys.argv[1] if len(sys.argv) > 1 else "你好"

ts = str(int(time.time()))
nonce = uuid.uuid4().hex
msgid = str(uuid.uuid4().int)[:19]

plain = (
    "<xml><ToUserName><![CDATA[%s]]></ToUserName>"
    "<FromUserName><![CDATA[%s]]></FromUserName>"
    "<CreateTime>%s</CreateTime><MsgType><![CDATA[text]]></MsgType>"
    "<Content><![CDATA[%s]]></Content><MsgId>%s</MsgId>"
    "<AgentID><![CDATA[%s]]></AgentID></xml>" % (corpid, user, ts, question, msgid, agentid)
)

key = base64.b64decode(sAES + "=")
pc = Prpcrypt(key)
ret, enc = pc.encrypt(plain, corpid)
if ret != 0:
    sys.exit(f"加密失败 ret={ret}")
enc = enc.decode()

sha1 = SHA1()
_, sig = sha1.getSHA1(sToken, ts, nonce, enc)

body = ("<xml><ToUserName><![CDATA[%s]]></ToUserName><Encrypt><![CDATA[%s]]></Encrypt>"
        "<AgentID><![CDATA[%s]]></AgentID></xml>" % (corpid, enc, agentid))

t0 = time.time()
r = requests.post(f"http://127.0.0.1:1111/wechat?msg_signature={sig}&timestamp={ts}&nonce={nonce}",
                  data=body.encode("utf-8"), timeout=120)
cost = time.time() - t0
print(f"HTTP {r.status_code}  耗时 {cost:.1f}s  响应 {len(r.content)} 字节")

if r.status_code != 200:
    print("响应体:", r.text[:300])
    sys.exit(1)

if not r.content:
    # 异步模式：回调立即应答，回复通过主动消息推送
    print("回调耗时 %.2fs，响应为空（异步模式，回复将通过主动消息推送）" % cost)
    print("等待 20 秒后查看服务端日志...")
    time.sleep(20)
    log = open("/www/py_project/wechat-daily/logs/run.log", encoding="utf-8", errors="ignore").read()
    tail = [l for l in log.split("\n") if l.strip()][-12:]
    print("\n".join(tail))
    sys.exit(0)

root = ET.fromstring(r.content)
enc_resp = root.findtext("Encrypt")
sig_resp = root.findtext("MsgSignature")
ts_resp = root.findtext("TimeStamp")
nonce_resp = root.findtext("Nonce")
_, calc = sha1.getSHA1(sToken, ts_resp, nonce_resp, enc_resp)
print("响应签名校验:", "通过" if calc == sig_resp else f"失败 {calc} != {sig_resp}")

ret, dec = pc.decrypt(enc_resp, corpid)
print("解密:", "成功" if ret == 0 else f"失败 ret={ret}")
text = dec.decode("utf-8")
content = ET.fromstring(text).findtext("Content") or ""
print(f"回复长度: {len(content)} 字符 / {len(content.encode('utf-8'))} 字节")
print("回复内容:\n" + content)
