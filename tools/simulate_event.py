#!/usr/bin/env python3
"""模拟企业微信菜单按钮（event/click）回调，验证 run.py 异步启动任务。
用法: simulate_event.py <EventKey>
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
from src.WXBizMsgCrypt3 import Prpcrypt, SHA1  # noqa: E402

sToken = os.getenv("sToken")
sAES = os.getenv("sEncodingAESKey")
corpid = os.getenv("WEIXIN_CORP_ID")
agentid = os.getenv("WEIXIN_AGENT_ID")
event_key = sys.argv[1] if len(sys.argv) > 1 else "#sendmsg#_0#7599827067206067"

ts = str(int(time.time()))
nonce = uuid.uuid4().hex

plain = (
    "<xml><ToUserName><![CDATA[%s]]></ToUserName>"
    "<FromUserName><![CDATA[HuangWeiShen]]></FromUserName>"
    "<CreateTime>%s</CreateTime><MsgType><![CDATA[event]]></MsgType>"
    "<Event><![CDATA[click]]></Event><EventKey><![CDATA[%s]]></EventKey>"
    "<AgentID><![CDATA[%s]]></AgentID></xml>" % (corpid, ts, event_key, agentid)
)

pc = Prpcrypt(base64.b64decode(sAES + "="))
_, enc = pc.encrypt(plain, corpid)
enc = enc.decode()
sha1 = SHA1()
_, sig = sha1.getSHA1(sToken, ts, nonce, enc)

body = ("<xml><ToUserName><![CDATA[%s]]></ToUserName><Encrypt><![CDATA[%s]]></Encrypt>"
        "<AgentID><![CDATA[%s]]></AgentID></xml>" % (corpid, enc, agentid))

t0 = time.time()
r = requests.post(f"http://127.0.0.1:1111/wechat?msg_signature={sig}&timestamp={ts}&nonce={nonce}",
                  data=body.encode("utf-8"), timeout=60)
print(f"HTTP {r.status_code}  耗时 {time.time()-t0:.2f}s  响应 {len(r.content)} 字节  EventKey={event_key}")
