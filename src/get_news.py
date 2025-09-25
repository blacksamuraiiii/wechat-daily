"""
@Time : 2025/9/25 14:45
@Author : black_samurai
@File : get_news.py
@description : 获取新浪新闻
"""

import requests
import json
from datetime import datetime

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

if __name__ == '__main__':

    # 获取当前时间和时间戳
    info_time = datetime.now()
    timestamps = round(datetime.timestamp(info_time) * 1000)
    news_time = info_time.strftime("%Y%m%d")

    # 设定新闻时间（当天）与类型
    #财经：finance_0_suda 社会：news_society_suda 国内：news_china_suda 国际：news_world_suda
    #科技：tech_news_suda 军事：news_mil_suda 娱乐：ent_suda 体育：sports_suda 总排行：www_www_all_suda_suda
    NEWS_TYPE = "news_world_suda"  # 新闻类型
    news_type = NEWS_TYPE

    print(get_news(news_type, news_time))