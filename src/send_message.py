"""
@Time : 2025/9/8 8:45
@Author : black_samurai
@File : send_message.py
@description : 企业微信消息推送模块
"""

import requests

def send_message(wxid, wxsecret, agentid, touser, content):
    """
    发送消息到企业微信。

    Args:
        wxid: 企业微信CorpID
        wxsecret: 企业微信应用Secret
        agentid: 企业微信应用AgentID
        touser: 推送目标用户
        content: 要发送的消息内容
    """
    # 获取access_token
    token_url = f'https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={wxid}&corpsecret={wxsecret}'
    wx_push_token = requests.post(url=token_url, data="").json()['access_token']

    # 构建推送数据
    wx_push_data = {
        "agentid": agentid,
        "msgtype": "text",
        "touser": touser,
        "text": {
            "content": content
        },
        "safe": 0
    }

    # 发送消息
    push_url = f'https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={wx_push_token}'
    requests.post(push_url, json=wx_push_data)



if __name__ == '__main__':
    from dotenv import load_dotenv
    import os       
    # 加载 .env 文件
    load_dotenv(dotenv_path='../.env')
    wxid = os.getenv("WEIXIN_CORP_ID")
    wxsecret = os.getenv("WEIXIN_CORP_SECRET")
    agentid = os.getenv("WEIXIN_AGENT_ID")
    touser = os.getenv("WEIXIN_TO_USER")

    # 发送消息测试
    send_message('hello,world!')