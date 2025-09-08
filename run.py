"""
@Time : 2025/9/8 8:45
@Author : black_samurai
@File : run.py
@description : 微信每日消息推送主程序，处理企业微信消息接收和AI对话
"""

from src.WXBizMsgCrypt3 import WXBizMsgCrypt
from flask import Flask, request
import xml.etree.cElementTree as ET
import sys
import os
from collections import deque
import src.chat_with_llm as chat_with_llm
# 从 dotenv 加载环境变量
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

# 全局变量，用于过滤重复消息 (使用deque限制内存使用)
MsgId_list = deque(maxlen=1000)

# 全局变量，用于存放用户数据
user_model_data = {}

# 初始化Flask应用
app = Flask(__name__)
@app.route('/wechat',methods=['GET','POST'])
def wechat():

    #获取url验证时微信发送的相关参数
    sVerifyMsgSig=request.args.get('msg_signature')
    sVerifyTimeStamp=request.args.get('timestamp')
    sVerifyNonce=request.args.get('nonce')
    sVerifyEchoStr=request.args.get('echostr')
    
    # 初始化微信消息加解密器
    wxcpt = WXBizMsgCrypt(sToken, sEncodingAESKey, sCorpID)
    
    #验证url
    if request.method == 'GET':
        ret,sEchoStr=wxcpt.VerifyURL(sVerifyMsgSig, sVerifyTimeStamp,sVerifyNonce,sVerifyEchoStr)
        if(ret!=0):
            print("ERR: VerifyURL ret: " + str(ret))
            sys.exit(1)
        else:
            return sEchoStr
            
    #接收客户端消息
    if request.method == 'POST':
        sReqMsgSig = sVerifyMsgSig
        sReqTimeStamp = sVerifyTimeStamp
        sReqNonce = sVerifyNonce
        sReqData = request.data
        ret,sMsg=wxcpt.DecryptMsg( sReqData, sReqMsgSig, sReqTimeStamp, sReqNonce)
        if( ret!=0 ):
            print("ERR: DecryptMsg ret: " + str(ret))
            sys.exit(1)
            
        #解析发送的内容并打印 (使用安全的XML解析)
        try:
            xml_tree = ET.fromstring(sMsg)
        except ET.ParseError as e:
            print(f"XML解析错误: {e}")
            return "消息格式错误"
        CreateTime = xml_tree.find("CreateTime").text
        MsgType = xml_tree.find("MsgType").text
        ToUserName = xml_tree.find("ToUserName").text
        FromUserName = xml_tree.find("FromUserName").text
        AgentID = xml_tree.find("AgentID").text
        MsgId_element = xml_tree.find("MsgId")
        MsgId = MsgId_element.text if MsgId_element is not None else None

        #构造回复文本
        content = ""
        # 文本消息
        if MsgType == 'text' and MsgId and MsgId not in MsgId_list:
            if MsgId:
                MsgId_list.append(MsgId)
            print('文本消息')
            text = xml_tree.find("Content").text
            
            # 输入验证
            if not text or len(text.strip()) == 0:
                content = "输入不能为空"
            elif len(text) > 1000:
                content = "输入内容过长"
            else:
                print(FromUserName," 输入:",text)
                  
            if text == "/clr":
                user_model_data.clear()
                content = "对话已清空"
            
            else:
                content = chat_with_llm.chat_with_llm(base_url, api_key, model_name, FromUserName,text,user_model_data)
            
        elif MsgType == 'event':
            Event = xml_tree.find("Event").text
            EventKey = xml_tree.find("EventKey").text
            # content = EventKey
            if Event=='click' and EventKey == '#sendmsg#_0#7599827067206067':
                    print("开始执行天气推送...")
                    os.system('python src/send_weather_message.py')
                    content = ""
                    print("天气推送执行成功");
            elif Event=='click' and EventKey == '#sendmsg#_1#7599827067206068':
                    print("开始执行邮件总结...")
                    os.system('python src/send_email_summary.py')
                    content = ""
                    print("邮件总结执行成功");

        else:
            content = "未找到对应项"
            
        print("输出:"+content)
        
    #被动响应消息，将微信端发送的消息返回给微信端
    if len(content) == 0:
        return "no data"
    else:
        sRespData ="<xml><ToUserName>"+ToUserName+"</ToUserName><FromUserName>"+FromUserName+"</FromUserName><CreateTime>"+CreateTime+"</CreateTime><MsgType>text</MsgType><Content>"+content+"</Content><AgentID>"+AgentID+"</AgentID></xml>"
        ret,sEncryptMsg=wxcpt.EncryptMsg(sRespData, sReqNonce, sReqTimeStamp)
        if( ret!=0 ):
            print ("ERR: EncryptMsg ret: " + str(ret))
            sys.exit(1)
        return sEncryptMsg


if __name__ == '__main__':

    #config
    global sToken, sEncodingAESKey, sCorpID, base_url, api_key, model_name
    sToken = os.getenv("sToken")
    sEncodingAESKey = os.getenv("sEncodingAESKey")
    sCorpID = os.getenv("WEIXIN_CORP_ID")

    # AI配置
    base_url = os.getenv("AI_BASE_URL")
    api_key = os.getenv("AI_API_KEY")
    model_name = os.getenv("AI_MODEL_NAME")


    app.run(host='0.0.0.0',port=1111)