"""
@Time : 2025/9/8 8:45
@Author : black_samurai
@File : send_email_summary.py
@description : 每日邮件总结功能模块，负责从IMAP服务器获取邮件，进行AI分析总结，并推送至企业微信
"""

import os
import imaplib
import email
import socket
import re
import sys
import json
from email.header import decode_header
from email.utils import parsedate_to_datetime
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup
from openai import OpenAI


# --- 辅助函数 ---

def decode_str(s):
    """
    解码邮件头中的编码字符串。

    Args:
        s: 待解码的字符串

    Returns:
        str: 解码后的字符串
    """
    if not s:
        return ""
    try:
        value, charset = decode_header(s)[0]
        if isinstance(value, bytes):
            return value.decode(charset if charset else 'utf-8', errors='ignore')
        return value
    except Exception:
        return str(s) # 如果解码失败，返回原始字符串

def safe_id_str(n):
    """
    安全地将邮件ID转换为字符串。

    Args:
        n: 邮件ID（可能是bytes或str）

    Returns:
        str: 字符串形式的邮件ID
    """
    return n.decode() if isinstance(n, bytes) else str(n)

def extract_main_body(text):
    """
    智能提取邮件正文，移除引用和签名。

    Args:
        text: 原始邮件正文

    Returns:
        str: 清理后的邮件正文
    """
    if not text:
        return ""
    # 移除HTML实体，以防它们干扰正则匹配
    text = text.replace('&nbsp;', ' ').strip()
    
    # 使用常见分割线切分
    text = re.split(r'\n-+\s*Original Message\s*-+|\n-+\s*Forwarded message\s*-+|On.*?wrote:|在.*?写道：', text, maxsplit=1)[0]
    
    # 移除逐行引用
    lines = text.split('\n')
    cleaned_lines = [line for line in lines if not line.strip().startswith('>')]
    text = '\n'.join(cleaned_lines)
    
    # 移除常见签名档分割线
    text = text.split('\n-- \n')[0].strip()
    
    # 清理多余的空行
    return re.sub(r'\n\s*\n', '\n\n', text)

def get_body_from_msg(msg):
    """
    从email.message对象中提取正文（优先纯文本）。

    Args:
        msg: email.message对象

    Returns:
        str: 邮件正文内容
    """
    body_plain = ""
    body_html = ""

    if msg.is_multipart():
        for part in msg.walk():
            # 跳过附件
            if part.get_filename() or part.get('Content-Disposition', '').startswith('attachment'):
                continue
            
            content_type = part.get_content_type()
            charset = part.get_content_charset() or 'utf-8'

            if content_type == 'text/plain' and not body_plain:
                try:
                    body_plain = part.get_payload(decode=True).decode(charset, errors='ignore')
                except Exception:
                    continue
            elif content_type == 'text/html' and not body_html:
                try:
                    body_html = part.get_payload(decode=True).decode(charset, errors='ignore')
                except Exception:
                    continue
    else: # 非 multipart 邮件
        charset = msg.get_content_charset() or 'utf-8'
        try:
            body_plain = msg.get_payload(decode=True).decode(charset, errors='ignore')
        except Exception:
            pass
            
    # 优先返回纯文本，如果纯文本为空，则从HTML中提取文本
    if body_plain:
        return body_plain
    elif body_html:
        soup = BeautifulSoup(body_html, 'html.parser')
        # 移除脚本和样式，避免干扰
        for script_or_style in soup(['script', 'style']):
            script_or_style.decompose()
        return soup.get_text(separator='\n', strip=True)
    return ""

def get_emails(imap_server, imap_port, user_email, password, start_date, end_date, MAX_EMAILS_TO_SCAN=50, blacklist_emails=None):
    """
    通过IMAP获取并解析指定日期范围内的邮件。
    采用两阶段获取策略，避免下载大型邮件导致卡死。
    返回收到的邮件列表和统计信息（收到的邮件数、发送的邮件数）。
    (已最终修复日期获取逻辑)
    
    Args:
        imap_server: IMAP服务器地址
        imap_port: IMAP服务器端口
        user_email: 用户邮箱地址
        password: 邮箱密码
        start_date: 开始日期
        end_date: 结束日期
        MAX_EMAILS_TO_SCAN: 最大扫描邮件数量
        blacklist_emails: 发件人黑名单列表，如果包含则过滤掉
    """

    print(f"正在连接到IMAP服务器 {imap_server}...")
    original_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(60)
    
    # 处理黑名单配置
    if blacklist_emails is None:
        blacklist_emails = []
    elif isinstance(blacklist_emails, str):
        # 如果是字符串，按逗号分割
        blacklist_emails = [email.strip().lower() for email in blacklist_emails.split(',') if email.strip()]
    
    if blacklist_emails:
        print(f"已配置发件人黑名单: {', '.join(blacklist_emails)}")

    emails_data = []
    mail = None
    try:
        mail = imaplib.IMAP4_SSL(imap_server, imap_port)
        mail.login(user_email, password)
        mail.select('INBOX')
        print("IMAP连接成功。")
 
        # --- 第一阶段：快速筛选符合日期的邮件ID ---
        print("\n--- 阶段1: 开始快速筛选邮件日期 ---")
        
        search_criteria = 'ALL' 
        status, messages = mail.search(None, search_criteria)
        if status != 'OK':
            print("搜索邮件失败!")
            return []
 
        email_ids = messages[0].split()
        if not email_ids:
            print("收件箱中没有任何邮件。")
            return []

        target_ids_to_scan = email_ids[-MAX_EMAILS_TO_SCAN:]
        print(f"收件箱共有{len(email_ids)}封邮件, 准备扫描最近的 {len(target_ids_to_scan)} 封。")
        
        filtered_ids = []
        for num in reversed(target_ids_to_scan):
            try:
                # =================== 核心修正部分 ===================
                # 直接、高效地只获取邮件的Date标头，这是最可靠的方法
                fetch_command = '(BODY[HEADER.FIELDS (DATE)])'
                status, data = mail.fetch(num, fetch_command)
                if status != 'OK' or not data or not data[0]:
                    print(f"  - 警告: 获取邮件ID {safe_id_str(num)} 的Date标头失败, 跳过。")
                    continue
                
                # data[0][1] 包含了 'Date: ...' 的字节串
                header_bytes = data[0][1]
                msg_header = email.message_from_bytes(header_bytes)
                date_str = msg_header['Date']
                
                # 如果Date标头为空或无法获取 (极少数情况)
                if not date_str:
                    print(f"  - 警告: 邮件ID {safe_id_str(num)} 的Date标头内容为空, 跳过。")
                    continue
                # ====================================================
 
                email_date = parsedate_to_datetime(date_str).date()
 
                if start_date <= email_date <= end_date:
                    filtered_ids.append(num)
                    print(f"  - 匹配成功: ID {safe_id_str(num)}, 日期 {email_date.strftime('%Y-%m-%d')}")
                elif email_date < start_date:
                    print(f"邮件日期({email_date.strftime('%Y-%m-%d')})已早于目标日期, 停止扫描。")
                    break
            except Exception as e:
                print(f"  - 警告: 解析邮件ID {safe_id_str(num)} 的日期时出错, 跳过。错误: {type(e).__name__}: {e}")
                continue
 
        if not filtered_ids:
            print("\n在指定日期范围内没有找到符合条件的邮件。")
            return []
            
        print(f"\n--- 阶段1完成: 找到 {len(filtered_ids)} 封符合条件的邮件 ---\n")
 
        # --- 第二阶段：获取筛选后邮件的完整内容 ---
        print("--- 阶段2: 开始获取邮件正文内容 ---")
        for i, num in enumerate(filtered_ids):
            print(f"正在处理第 {i+1}/{len(filtered_ids)} 封邮件 (ID: {safe_id_str(num)})...")
            try:
                status, data = mail.fetch(num, '(RFC822)')
                if status != 'OK' or not data[0]:
                    print(f"  - 获取邮件ID {safe_id_str(num)} 失败, 跳过。")
                    continue
                
                msg = email.message_from_bytes(data[0][1])
                body_text = get_body_from_msg(msg)
                main_content = extract_main_body(body_text)
 
                email_content = {
                    'from': decode_str(msg['from']),
                    'to': decode_str(msg['to']),
                    'subject': decode_str(msg['subject']),
                    'date': msg['date'],
                    'content': main_content,
                }
                
                # 检查发件人是否在黑名单中
                from_email = email_content['from'].lower()
                is_blacklisted = any(black_email in from_email for black_email in blacklist_emails)
                
                if is_blacklisted:
                    print(f"  - 跳过黑名单发件人邮件: {email_content['from']} (主题: {email_content['subject']})")
                    continue
                
                emails_data.append(email_content)
                print(f"  - 已处理邮件: 主题='{email_content['subject']}'")
            except Exception as e:
                print(f"  - 处理邮件ID {safe_id_str(num)} 时发生严重错误, 跳过。错误: {e}")
                continue
 
        print(f"\n--- 阶段2完成: 成功处理了 {len(emails_data)} 封邮件。---")

        # 统计邮件数
        received_data = [mail for mail in emails_data if user_email.lower() not in mail.get('from', '').lower()]
        total_received = len(received_data)
        total_sent = len(emails_data) - total_received

        return received_data, total_received, total_sent
 
    except imaplib.IMAP4.error as e:
        print(f"[错误] IMAP 错误: {e}")
        return [], 0, 0
    except socket.timeout:
        print("[错误] 连接超时，IMAP服务器长时间无响应。")
        return [], 0, 0
    except Exception as e:
        print(f"[错误] 发生未知错误: {e}")
        return [], 0, 0
    finally:
        if mail:
            try:
                mail.close()
                mail.logout()
                print("IMAP连接已关闭。")
            except Exception:
                pass
        socket.setdefaulttimeout(original_timeout)

# --- AI 与推送 ---
def summarize_with_ai(emails_list,total_received, total_sent):
    """调用AI API总结邮件内容。"""
    if not emails_list:
        return f"今日共发送 {total_sent} 封邮件，收到 {total_received} 封邮件。无需要分析的外部邮件。"

    print("正在准备内容并调用AI进行总结...")

    formatted_emails = []
    for i, mail in enumerate(emails_list):
        content_snippet = mail.get('content', '')[:200]
        if len(mail.get('content', '')) > 200:
            content_snippet += '...'

        formatted_emails.append(
            f"邮件 {i+1}:\n"
            f"发件人: {mail.get('from', '未知')}\n"
            f"主题: {mail.get('subject', '无主题')}\n"
            f"概要: {content_snippet}\n"
        )
    ai_input_content = "\n\n".join(formatted_emails)

    # 获取AI配置
    ai_api_key = os.getenv("AI_API_KEY")
    ai_base_url = os.getenv("AI_BASE_URL")
    AI_MODEL_NAME = os.getenv("AI_MODEL_NAME")

    client = OpenAI(api_key=ai_api_key, base_url=ai_base_url)
    system_prompt = (
        f"你是一个专业的邮件摘要助手。请根据以下邮件内容，为我生成一份今日（{datetime.now().date().strftime('%Y-%m-%d')}）的邮件摘要报告。"
        "报告格式如下：\n\n"
        f"今日共发送 {total_sent} 封邮件，收到 {total_received} 封邮件，其中x封需回复\n\n"
        "******邮件内容******\n\n"
        "1. 【邮件主题】\n   - 发件人: [发件人姓名]\n   - 核心内容: [对邮件内容的1-2句话精炼总结，突出要点和待办事项]\n\n"
        "2. 【另一封邮件主题】\n   - 发件人: [发件人姓名]\n   - 核心内容: [总结...]\n\n"
        "如果邮件内容需要回复或处理，请在核心内容最后加上提醒，例如 '(需回复)'。"
        "请确保总结简明扼要，严格遵循以上格式。"
    )

    try:
        response = client.chat.completions.create(
            model=AI_MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": ai_input_content},
            ],
            stream=False,
            timeout=120, # 改进点：为API调用设置超时
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"[错误] 调用AI API时发生错误: {e}")
        return f"AI总结失败：{e}"

# --- 测试 ---

if __name__ == '__main__':
    # 添加防止重复执行的机制
    import sys
    import os
    import ast
    
    # 检查是否已经有实例在运行
    lock_file = "/tmp/send_email_summary.lock"
    if sys.platform.startswith("win"):
        lock_file = os.path.join(os.environ.get("TEMP", "C:\\temp"), "send_email_summary.lock")
    
    if os.path.exists(lock_file):
        print("邮件总结任务已在运行中，退出当前实例。")
        sys.exit(0)
    
    # 创建锁文件
    try:
        with open(lock_file, 'w') as f:
            f.write(str(os.getpid()))
        
        print("--- 每日邮件总结任务开始 ---")   

        # 1. 获取邮件
        # 邮箱配置,默认只收今天的邮件
        from dotenv import load_dotenv
        load_dotenv(dotenv_path='../.env')
        
        # 用户名入参
        if len(sys.argv) > 1:
            touser = sys.argv[1]
        else:
            # 如果没有提供命令行参数，则使用默认用户
            touser = "HuangWeiShen"  # 默认用户
        
        # 从环境变量中获取邮箱配置字典
        email_dict_str = os.getenv("EMAIL_DICT")
        email_dict = json.loads(email_dict_str) if email_dict_str else {}
        
        # 根据用户名获取对应的邮箱配置
        if touser in email_dict:
            email_config = email_dict[touser]
            imap_server = email_config["IMAP_SERVER"]
            imap_port = email_config["IMAP_PORT"]
            user_email = email_config["USER_EMAIL"]
            password = email_config["PASSWORD"]
        else:
            print(f"未找到用户 {touser} 的邮箱配置，退出。")
            exit(1)

        max_emails = int(os.getenv("MAX_EMAILS_TO_SCAN", 200))
        today = datetime.now().date()
        # 获取发件人黑名单配置
        blacklist_emails = os.getenv("EMAIL_BLACKLIST", "")
        emails, total_received, total_sent = get_emails(imap_server, imap_port, user_email, password, start_date=today, end_date=today,  MAX_EMAILS_TO_SCAN=max_emails, blacklist_emails=blacklist_emails)

        # 2. 生成总结
        week_dict = {
            0:"星期一",
            1:"星期二",
            2:"星期三",
            3:"星期四",
            4:"星期五",
            5:"星期六",
            6:"星期日"
        }
        day = today.strftime("%Y-%m-%d") + " " + week_dict[today.weekday()]


        if not emails:
            content = f"{day} 未收到新邮件。"
        else:
            content = (
                f"{day}\n\n"
                "********总结********\n\n"
                f"{summarize_with_ai(emails, total_received, total_sent)}"
            )

        print("\n--- 生成的总结内容 ---\n")
        print(content)
        print("\n---------------------\n")

        # 3. 推送消息
        from send_message import send_message
        # 加载微信配置
        wxid = os.getenv("WEIXIN_CORP_ID")
        wxsecret = os.getenv("WEIXIN_CORP_SECRET")
        agentid = os.getenv("WEIXIN_AGENT_ID")
        # touser = os.getenv("WEIXIN_TO_USER")
        send_message(wxid, wxsecret, agentid, touser, content)
    
    finally:
        # 删除锁文件
        if os.path.exists(lock_file):
            os.remove(lock_file)