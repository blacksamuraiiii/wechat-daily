import yfinance as yf
import time
import random
from yfinance.exceptions import YFRateLimitError

# 代理设置
# import os
# proxy = 'http://127.0.0.1:7890' 
# os.environ['HTTP_PROXY'] = proxy 
# os.environ['HTTPS_PROXY'] = proxy 

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
    financial_data = get_financial_data()
    print(f"今天日期: {time.strftime('%Y-%m-%d', time.localtime())}")
    print(f"标普PE: {round(financial_data['标普PE'], 2)}")
    print(f"纳指PE: {round(financial_data['纳指PE'], 2)}")
    print(f"国内金价: {round(financial_data['国内金价'], 2)}")

    # 写入文件 用utf8编码
    with open("./data.txt", "w", encoding='utf-8') as f:
        f.write(f"今天日期: {time.strftime('%Y-%m-%d', time.localtime())}\n")
        f.write(f"标普PE: {round(financial_data['标普PE'], 2)}\n")
        f.write(f"纳指PE: {round(financial_data['纳指PE'], 2)}\n")
        f.write(f"国内金价: {round(financial_data['国内金价'], 2)}\n")
