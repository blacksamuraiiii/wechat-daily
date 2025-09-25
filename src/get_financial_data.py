"""
@Time : 2025/9/24 8:45
@Author : black_samurai
@File : send_weather_message.py
@description : 获取财经类指标
"""


import yfinance as yf
import time
import random
from yfinance.exceptions import YFRateLimitError

#代理设置
import os
proxy = 'http://127.0.0.1:7890'
os.environ['HTTP_PROXY'] = proxy
os.environ['HTTPS_PROXY'] = proxy

def read_yesterday_data(file_path):
    """
    读取data.txt文件获取昨天的金融数据

    返回:
    dict: 包含昨天金融数据的字典
    """
    yesterday_data = {}
    try:
        with open(file_path, "r", encoding='utf-8') as f:
            lines = f.readlines()
            for line in lines:
                if "标普PE:" in line:
                    yesterday_data["标普PE"] = float(line.split(":")[1].strip())
                elif "纳指PE:" in line:
                    yesterday_data["纳指PE"] = float(line.split(":")[1].strip())
                elif "国内金价:" in line:
                    yesterday_data["国内金价"] = float(line.split(":")[1].strip())
    except FileNotFoundError:
        print("未找到data.txt文件，将使用默认值")
    except ValueError:
        print("数据格式错误，将使用默认值")

    return yesterday_data

def calculate_change_percentage(today_value, yesterday_value):
    """
    计算增幅百分比

    参数:
    today_value (float): 今天的值
    yesterday_value (float): 昨天的值

    返回:
    str: 格式化的增幅百分比字符串
    """
    if yesterday_value == 0 or yesterday_value is None:
        return "(+0.00%)"

    change = today_value - yesterday_value
    percentage = (change / yesterday_value) * 100
    sign = "+" if percentage >= 0 else ""
    return f"({sign}{percentage:.2f}%)"

def get_financial_data(max_retries=3, base_delay=1):
    """
    获取金融数据，包含重试机制以避免API限制
    
    参数:
    max_retries (int): 最大重试次数
    base_delay (int): 基础延迟时间（秒）
    
    返回:
    dict: 包含金融数据的字典
    """
    data = {}
    retries = 0
    
    while retries <= max_retries:
        try:
            # 获取标普500市盈率
            # 使用VOO ETF作为标普500的代理
            sp500_etf = yf.Ticker("VOO")
            data["标普PE"] = sp500_etf.info.get("trailingPE", "数据不可用")
            
            # 使用QQQ ETF作为纳斯达克100的代理
            nasdaq100_etf = yf.Ticker("QQQ")
            data["纳指PE"] = nasdaq100_etf.info.get("trailingPE", "数据不可用")
            
            # 获取黄金价格（美元/盎司）
            gold = yf.Ticker("GC=F")
            gold_price_usd = gold.info.get("regularMarketPrice", "数据不可用")
            
            # 获取美元兑人民币汇率
            usdcny = yf.Ticker("USDCNY=X")
            exchange_rate = usdcny.info.get("regularMarketPrice", "数据不可用")
            
            # 计算人民币/克金价 (1盎司=31.1035克)
            if isinstance(gold_price_usd, float) and isinstance(exchange_rate, float):
                data["国内金价"] = (gold_price_usd * exchange_rate) / 31.1035
            else:
                data["国内金价"] = "数据不可用"
            
            return data
            
        except YFRateLimitError:
            retries += 1
            if retries <= max_retries:
                # 指数退避策略：每次重试增加延迟时间
                delay = base_delay * (2 ** retries) + random.uniform(0, 1)
                print(f"遇到请求限制，将在 {delay:.2f} 秒后重试 ({retries}/{max_retries})")
                time.sleep(delay)
            else:
                print("达到最大重试次数，无法获取数据")
                return {
                    "标普PE": "请求失败",
                    "纳指PE": "请求失败",
                    "国内金价": "请求失败"
                }

if __name__ == "__main__":
    # 文件路径
    file_path = "./data.txt"

    # 获取今天的金融数据
    financial_data = get_financial_data()

    # 读取昨天的数据
    yesterday_data = read_yesterday_data(file_path)

    # 获取今天日期
    today_date = time.strftime('%Y-%m-%d', time.localtime())

    # 计算增幅并输出
    print(f"今天日期: {today_date}")

    # 标普PE
    sp500_today = round(financial_data['标普PE'], 2) if isinstance(financial_data['标普PE'], float) else financial_data['标普PE']
    sp500_change = calculate_change_percentage(financial_data['标普PE'], yesterday_data.get('标普PE'))
    print(f"标普PE: {sp500_today}{sp500_change}")

    # 纳指PE
    nasdaq_today = round(financial_data['纳指PE'], 2) if isinstance(financial_data['纳指PE'], float) else financial_data['纳指PE']
    nasdaq_change = calculate_change_percentage(financial_data['纳指PE'], yesterday_data.get('纳指PE'))
    print(f"纳指PE: {nasdaq_today}{nasdaq_change}")

    # 国内金价
    gold_today = round(financial_data['国内金价'], 2) if isinstance(financial_data['国内金价'], float) else financial_data['国内金价']
    gold_change = calculate_change_percentage(financial_data['国内金价'], yesterday_data.get('国内金价'))
    print(f"国内金价: {gold_today}{gold_change}")

    # 写入文件 用utf8编码
    with open(file_path, "w", encoding='utf-8') as f:
        f.write(f"今天日期: {today_date}\n")
        f.write(f"标普PE: {sp500_today}{sp500_change}\n")
        f.write(f"纳指PE: {nasdaq_today}{nasdaq_change}\n")
        f.write(f"国内金价: {gold_today}{gold_change}\n")
