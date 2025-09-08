"""
@Time : 2025/9/8 8:45
@Author : black_samurai
@File : chat_with_llm.py
@description : AI多轮对话模块，使用LangChain实现基于ChatOpenAI的对话功能，支持记忆管理
"""

import os
from langchain_openai import ChatOpenAI
from langchain.chains import ConversationChain
from langchain.memory import ConversationBufferWindowMemory
from langchain.prompts import PromptTemplate


def chat_with_llm(base_url, api_key, model_name, FromUserName, question, user_model_data):
    """
    处理用户与AI的对话，支持多轮对话和记忆管理。

    Args:
        base_url: AI API的基础URL
        api_key: AI API的密钥
        model_name: AI模型名称
        FromUserName: 用户标识符，用于区分不同用户的对话
        question: 用户输入的问题
        user_model_data: 全局用户模型数据字典

    Returns:
        str: AI的回复内容
    """
    print("开始调用ChatGPT")

    # 检查是否新用户
    if FromUserName not in user_model_data:
        # 初始化ChatGPT模型
        if not api_key:
            return "错误：API密钥未设置，请检查环境变量 AI_API_KEY"
        if not model_name:
            return "错误：模型名称未设置，请检查环境变量 AI_MODEL_NAME"

        if api_key:
            os.environ["OPENAI_API_KEY"] = api_key
        if base_url:
            os.environ["OPENAI_API_BASE"] = base_url

        llm = ChatOpenAI(
            temperature=0.7,  # 控制回复的随机性，较低值更保守
            model=model_name,  # 从环境变量获取模型名称
        )

        # 初始化提示词模板
        template = """
        system: 'You are a helpful, smart, kind, and efficient AI assistant.'
        current conversation: {history}
        user: {input}
        """
        prompt = PromptTemplate(input_variables=["history", "input"], template=template)

        # 初始化记忆缓冲区（默认k=3，保持最近3轮对话）
        conversation = ConversationChain(
            llm=llm,
            prompt=prompt,
            memory=ConversationBufferWindowMemory(k=3),
            verbose=True  # 启用详细输出
        )

        # 将模型及记忆存储到用户数据字典
        user_model_data[FromUserName] = conversation

    else:
        # 老用户调取已存在的模型
        conversation = user_model_data[FromUserName]

    # 输入问题并获取回复
    try:
        message = conversation.predict(input=question)
        print(f"AI回复: {message}")
        return message
    except Exception as e:
        print(f"AI API调用失败: {e}")
        return "抱歉，AI服务暂时不可用，请稍后再试。"
    


if __name__ == '__main__':
    # 添加防止重复执行的机制
    import sys
    import os
    
    # 检查是否已经有实例在运行
    lock_file = "/tmp/chat_with_llm.lock"
    if sys.platform.startswith("win"):
        lock_file = os.path.join(os.environ.get("TEMP", "C:\\temp"), "chat_with_llm.lock")
    
    if os.path.exists(lock_file):
        print("AI对话任务已在运行中，退出当前实例。")
        sys.exit(0)
    
    # 创建锁文件
    try:
        with open(lock_file, 'w') as f:
            f.write(str(os.getpid()))
            
        # 加载 .env 文件
        from dotenv import load_dotenv
        load_dotenv(dotenv_path='../.env')

        # 设置系统变量
        wxid = os.getenv("WEIXIN_CORP_ID")
        wxsecret = os.getenv("WEIXIN_CORP_SECRET")
        agentid = os.getenv("WEIXIN_AGENT_ID")
        touser = os.getenv("WEIXIN_TO_USER")
        api_key = os.getenv("AI_API_KEY")
        base_url = os.getenv("AI_BASE_URL")
        model_name = os.getenv("AI_MODEL_NAME")

        # 调用
        user_model_data = {}
        content = chat_with_llm(base_url, api_key, model_name, touser, "nihao", user_model_data)
    
        # 测试
        from send_message import send_message
        send_message(wxid, wxsecret, agentid, touser, content)
    
    finally:
        # 删除锁文件
        if os.path.exists(lock_file):
            os.remove(lock_file)