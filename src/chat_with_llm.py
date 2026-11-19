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

# 对话回复的输出上限（tokens）。企业微信单条文本 2048 字节，超长部分由
# run.py 自动分片补发，这里给足余量，避免长回答被模型自己截断。
MAX_REPLY_TOKENS = 1000


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
        if not api_key:
            return "错误：API密钥未设置，请检查环境变量 AI_API_KEY"
        if not model_name:
            return "错误：模型名称未设置，请检查环境变量 AI_MODEL_NAME"

        llm = ChatOpenAI(
            temperature=0.7,      # 控制回复的随机性，较低值更保守
            model=model_name,     # 从环境变量获取模型名称
            api_key=api_key,
            base_url=base_url,
            max_tokens=MAX_REPLY_TOKENS,
            timeout=60,
        )

        # 初始化提示词模板
        template = """
        system: 'You are a helpful, smart, kind, and efficient AI assistant.'
        current conversation: {history}
        user: {input}
        """
        prompt = PromptTemplate(input_variables=["history", "input"], template=template)

        # 初始化记忆缓冲区（k=3，保持最近3轮对话）
        conversation = ConversationChain(
            llm=llm,
            prompt=prompt,
            memory=ConversationBufferWindowMemory(k=3),
            verbose=False,
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
    from dotenv import load_dotenv

    load_dotenv(dotenv_path='../.env')

    api_key = os.getenv("AI_API_KEY")
    base_url = os.getenv("AI_BASE_URL")
    model_name = os.getenv("AI_MODEL_NAME")

    # 自测：跑一轮对话并打印结果
    user_model_data = {}
    content = chat_with_llm(base_url, api_key, model_name, "selftest", "nihao", user_model_data)
    print(content)
