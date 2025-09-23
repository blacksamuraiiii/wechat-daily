"""
@Time : 2025/9/8 8:45
@Author : black_samurai
@File : send_weather_message.py
@description : 天气推送模块，获取天气、新闻和每日金句并推送至企业微信
"""

import requests
import json
from datetime import datetime


def weather_info(cookie, city_code, timestamps):
    """
    获取天气信息。

    Args:
        cookie: 天气API的Cookie
        city_code: 城市代码
        timestamps: 时间戳

    Returns:
        str: 格式化的天气信息
    """
    print("--- 正在获取天气信息 ---")
    w_headers = {
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Cookie": cookie,
        "DNT": "1",
        "Host": "d1.weather.com.cn",
        "Pragma": "no-cache",
        "Referer": "http://www.weather.com.cn/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.71 Safari/537.36 Edg/94.0.992.38"
    }
    weather_url = f'http://d1.weather.com.cn/dingzhi/{city_code}.html?_={timestamps}'
    weather_req = requests.get(url=weather_url,headers=w_headers, timeout=30).content.decode('utf-8')
    try:
        weather_data = json.loads(weather_req.replace(f"var cityDZ{city_code} =", "").split(f";var alarmDZ{city_code} =")[0])
        weather_info = weather_data['weatherinfo']
    except (json.JSONDecodeError, KeyError) as e:
        print(f"天气信息解析失败: {e}")
        weather_info = {}
    
    try:
        warning_json = json.loads(weather_req.replace(f"var cityDZ{city_code} =", "").split(f";var alarmDZ{city_code} =")[1])
        warning = json.loads(str(warning_json).replace("'",'"'))['w'][0]
        warning_info = warning['w5'] + warning['w7']
    except:
        warning_info = "当前无预警信息"
    weather_messages = (
        f"城市名称：{weather_info['cityname']}\n"
        f"当前温度：{weather_info['temp']}\n"
        f"最低温度：{weather_info['tempn']}\n"
        f"天气情况：{weather_info['weather']}\n"
        f"风力风向：{weather_info['wd']}{weather_info['ws']}\n"
        f"预警信息：{warning_info}"
    )
    return weather_messages

def get_news(news_type, news_time):
    """
    获取新闻信息。

    Args:
        news_type: 新闻类型
        news_time: 新闻时间

    Returns:
        list: 新闻列表
    """
    print("--- 正在获取新闻信息 ---")
    news_headers = {
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "DNT": "1",
        "Host": "top.news.sina.com.cn",
        "Pragma": "no-cache",
        "Referer": "http://news.sina.com.cn/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.71 Safari/537.36 Edg/94.0.992.38"
    }
    news_url = f'http://top.news.sina.com.cn/ws/GetTopDataList.php?top_type=day&top_cat={news_type}&top_time={news_time}&top_show_num=20&top_order=DESC&js_var=news_'
    news_req = requests.get(url=news_url,headers=news_headers, timeout=30).text.replace("var news_ = ","").replace(r"\/\/","//").replace(";","")
    try:
        news_data = json.loads(news_req)
        news_sub = news_data.get('data', [])
    except (json.JSONDecodeError, KeyError) as e:
        print(f"新闻数据解析失败: {e}")
        news_sub = []
    
    news_list = []
    for item in news_sub:
        if str(item['url']).split(".")[0] == "https://video": #新浪的视频新闻总会提示下载APP，直接过滤掉，选择不看
            continue
        else:
            news = f"{item['title']} <a href=\"{item['url']}\">详情</a>"
            news_list.append(news)
    return news_list

def get_sentence():
    """
    获取每日金句。

    Returns:
        str: 格式化的金句内容
    """
    print("--- 正在获取每日金句 ---")
    sen_url = 'https://v1.hitokoto.cn?c=d&c=h&c=i&c=k'
    try:
        get_sen = requests.get(url=sen_url, timeout=10).json()
        sentence = f"{get_sen['hitokoto']}\n\n出自：{get_sen['from']}"
    except:
        sentence = "今日无金句，请继续努力！"

    return sentence

def get_financial_data():
    """获取金融数据"""
    print("--- 正在获取金融数据 ---")
    url = "https://www.blacksamurai.top/finance/data.txt" 
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
    }
    response = requests.get(url, headers=headers)
    response.encoding = 'utf-8'
    
    # 跳过第一行，并保留后续所有行
    lines = response.text.splitlines()
    filtered_lines = [line.strip() for line in lines[1:]]
    return '\n'.join(filtered_lines)

def message_content(city_code, timestamps, info_time, news_list, financial, sentence):
    """
    组装消息内容。

    Args:
        city_code: 城市代码
        timestamps: 时间戳
        info_time: 信息时间
        news_list: 新闻列表
        financial: 金融数据
        sentence: 每日金句

    Returns:
        str: 完整的消息内容
    """
    week_dict = {
        0:"星期一",
        1:"星期二",
        2:"星期三",
        3:"星期四",
        4:"星期五",
        5:"星期六",
        6:"星期日"
    }
    day = info_time.strftime("%Y-%m-%d") + " " + week_dict[info_time.weekday()]
    content = (
        f"{day}\n\n"
        "********天气********\n\n"
        f"{weather_info(cookie, city_code, timestamps)}\n\n"
        "******热点新闻******\n\n"
        f"{chr(10).join(news_list[:3])}\n\n"  # 只截取前3条新闻，微信推送有长度限制
        "******投资风向******\n\n"
        f"{financial}\n\n"
        "******每日金句******\n\n"
        f"{sentence}"
    )
    print(content)
    return content

if __name__ == '__main__':
    # 添加防止重复执行的机制
    import sys
    import os
    
    # 检查是否已经有实例在运行
    lock_file = "/tmp/send_weather_message.lock"
    if sys.platform.startswith("win"):
        lock_file = os.path.join(os.environ.get("TEMP", "C:\\temp"), "send_weather_message.lock")
    
    if os.path.exists(lock_file):
        print("天气推送任务已在运行中，退出当前实例。")
        sys.exit(0)
    
    # 创建锁文件
    try:
        with open(lock_file, 'w') as f:
            f.write(str(os.getpid()))
            
        print("--- 开始获取信息 ---")

        # 加载环境变量
        from dotenv import load_dotenv
        import os
        load_dotenv(dotenv_path='../.env')

        # 用户名入参
        if len(sys.argv) > 1:
            touser = sys.argv[1]
        else:
            # 如果没有提供命令行参数，则使用默认用户
            touser = "HuangWeiShen"  # 默认用户

        # 获取配置参数
        city_code = os.getenv('WEATHER_CITY_CODE', '101190601')
        cookie = os.getenv('WEATHER_COOKIE')
        news_type = os.getenv('NEWS_TYPE', 'www_www_all_suda_suda')
        wxid = os.getenv("WEIXIN_CORP_ID")
        wxsecret = os.getenv("WEIXIN_CORP_SECRET")
        agentid = os.getenv("WEIXIN_AGENT_ID")
        # touser = os.getenv("WEIXIN_TO_USER")

        # 获取当前时间和时间戳
        info_time = datetime.now()
        timestamps = round(datetime.timestamp(info_time) * 1000)
        news_time = info_time.strftime("%Y%m%d")

        # 生成并发送消息
        content = message_content(city_code, timestamps, info_time, get_news(news_type, news_time), get_financial_data(), get_sentence())
        from send_message import send_message
        send_message(wxid, wxsecret, agentid, touser, content)
    
    finally:
        # 删除锁文件
        if os.path.exists(lock_file):
            os.remove(lock_file)