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

# 从 dotenv 加载环境变量
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv(dotenv_path='../.env')

# 设置系统变量
os.environ["OPENAI_API_KEY"] = os.getenv("AI_API_KEY")
os.environ["OPENAI_API_BASE"] = os.getenv("AI_BASE_URL")


def chat_with_llm(FromUserName, question, user_model_data):
    """
    处理用户与AI的对话，支持多轮对话和记忆管理。

    Args:
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
        llm = ChatOpenAI(
            temperature=0.7,  # 控制回复的随机性，较低值更保守
            model=os.getenv("AI_MODEL"),  # 从环境变量获取模型名称
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