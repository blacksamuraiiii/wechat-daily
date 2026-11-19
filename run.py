"""
@Time : 2025/9/8 8:45
@Author : black_samurai
@File : run.py
@description : 微信每日消息推送主程序，处理企业微信消息接收和AI对话
"""

import os
import subprocess
import sys
import threading
from collections import deque

from dotenv import load_dotenv
from flask import Flask, request
import xml.etree.cElementTree as ET

from src.WXBizMsgCrypt3 import WXBizMsgCrypt
import src.chat_with_llm as chat_with_llm
from src.send_message import send_message

# 加载 .env 文件
load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 企业微信 / AI 配置
sToken = os.getenv("sToken")
sEncodingAESKey = os.getenv("sEncodingAESKey")
sCorpID = os.getenv("WEIXIN_CORP_ID")
wx_secret = os.getenv("WEIXIN_CORP_SECRET")
wx_agentid = os.getenv("WEIXIN_AGENT_ID")
base_url = os.getenv("AI_BASE_URL")
api_key = os.getenv("AI_API_KEY")
model_name = os.getenv("AI_MODEL_NAME")

# 用户单条输入上限（字符）
MAX_INPUT_CHARS = 1000

# 全局变量，用于过滤重复消息 (使用deque限制内存使用)
MsgId_list = deque(maxlen=1000)
MsgId_set = set()

# 全局变量，用于存放用户数据
user_model_data = {}

app = Flask(__name__)


def _run_task_async(script, user):
    """异步执行 src 下的任务脚本，不阻塞回调（企微要求 5 秒内响应，超时会重试）。"""
    path = os.path.join(BASE_DIR, "src", script)
    log_dir = os.path.join(BASE_DIR, "logs")
    os.makedirs(log_dir, exist_ok=True)
    # 子进程输出落到独立日志，便于按钮触发的任务排障
    log_file = open(os.path.join(log_dir, f"{script}.log"), "ab")
    try:
        subprocess.Popen([sys.executable, "-u", path, user], cwd=BASE_DIR,
                         stdout=log_file, stderr=subprocess.STDOUT,
                         start_new_session=True)
    finally:
        log_file.close()
    print(f"已异步启动 {script}")


def handle_text(text, from_user):
    """处理文本消息，返回回复内容。"""
    text = (text or "").strip()
    if not text:
        return "输入不能为空"
    if len(text) > MAX_INPUT_CHARS:
        return f"输入内容过长（最多 {MAX_INPUT_CHARS} 字）"
    if text == "/clr":
        user_model_data.clear()
        return "对话已清空"

    print(from_user, " 输入:", text)
    return chat_with_llm.chat_with_llm(
        base_url, api_key, model_name, from_user, text, user_model_data
    )


def _handle_text_async(text, from_user):
    """后台处理文本消息并用主动消息回复。

    企业微信要求回调 5 秒内响应，超时会重试；而 LLM 生成较慢，
    因此改为立即应答 + 异步主动推送（主动消息可自动分片，不受被动回复长度限制）。
    """
    try:
        reply = handle_text(text, from_user)
    except Exception as e:
        print(f"处理文本消息失败: {e}")
        reply = "处理消息时出错，请稍后重试"
    if reply:
        send_message(sCorpID, wx_secret, wx_agentid, from_user, reply)


@app.route('/wechat', methods=['GET', 'POST'])
def wechat():
    # 获取url验证时微信发送的相关参数
    sVerifyMsgSig = request.args.get('msg_signature')
    sVerifyTimeStamp = request.args.get('timestamp')
    sVerifyNonce = request.args.get('nonce')
    sVerifyEchoStr = request.args.get('echostr')

    # 初始化微信消息加解密器
    try:
        wxcpt = WXBizMsgCrypt(sToken, sEncodingAESKey, sCorpID)
    except Exception as e:
        print(f"初始化加解密器失败: {e}")
        return "config error", 500

    # 验证url
    if request.method == 'GET':
        ret, sEchoStr = wxcpt.VerifyURL(sVerifyMsgSig, sVerifyTimeStamp, sVerifyNonce, sVerifyEchoStr)
        if ret != 0:
            print("ERR: VerifyURL ret: " + str(ret))
            return "verify failed", 403
        return sEchoStr

    # 接收客户端消息
    ret, sMsg = wxcpt.DecryptMsg(request.data, sVerifyMsgSig, sVerifyTimeStamp, sVerifyNonce)
    if ret != 0:
        print("ERR: DecryptMsg ret: " + str(ret))
        return "decrypt failed", 400

    try:
        xml_tree = ET.fromstring(sMsg)
    except ET.ParseError as e:
        print(f"XML解析错误: {e}")
        return "消息格式错误", 400

    MsgType = xml_tree.findtext("MsgType", "")
    FromUserName = xml_tree.findtext("FromUserName", "")
    MsgId = xml_tree.findtext("MsgId")

    # 文本消息：立即应答，LLM 回复走异步主动消息
    if MsgType == 'text':
        if not MsgId:
            return ""
        if MsgId in MsgId_set:
            print("重复文本消息，忽略")
            return ""
        MsgId_list.append(MsgId)
        MsgId_set.add(MsgId)
        print('文本消息')
        threading.Thread(
            target=_handle_text_async,
            args=(xml_tree.findtext("Content", ""), FromUserName),
            daemon=True,
        ).start()

    # 菜单按钮事件：异步跑任务，不回复正文
    elif MsgType == 'event':
        Event = xml_tree.findtext("Event", "")
        EventKey = xml_tree.findtext("EventKey", "")
        if Event == 'click' and EventKey == '#sendmsg#_0#7599827067206067':
            print("开始执行天气推送...")
            _run_task_async("send_weather_message.py", FromUserName)
        elif Event == 'click' and EventKey == '#sendmsg#_1#7599827067206068':
            print("开始执行邮件总结...")
            _run_task_async("send_email_summary.py", FromUserName)

    # 统一返回空串：告知企微"已收到"，不再被动回复正文，
    # 避免 5 秒超时重试，也绕开被动回复的 2048 字节限制
    return ""


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=1111)
