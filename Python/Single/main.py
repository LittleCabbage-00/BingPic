import datetime
import requests
import os
import time

date = datetime.date(2019, 1, 1)

def download_image(url, filepath, max_retries=5):
    for attempt in range(1, max_retries + 1):
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                with open(filepath, 'wb') as f:
                    f.write(response.content)
                print(f"已下载 {filepath}")
                return True
            else:
                print(f"下载 {filepath} 失败，状态码：{response.status_code}，尝试次数：{attempt}")
        except requests.exceptions.RequestException as e:
            print(f"下载 {filepath} 时出错：{e}，尝试次数：{attempt}")
        time.sleep(1)  # 每次重试前等待1秒
    return False

date_str_url = date.strftime("%Y%m%d")  # 用于URL：YYYYMMDD
date_str_file = date.strftime("%Y-%m-%d")  # 用于文件名：YYYY-MM-DD

url = f"https://bing.ee123.net/img/?date={date_str_url}&size=1920x1080"

filename = f"bing_pic_{date_str_file}.jpg"
filepath = filename  # 直接使用文件名，不使用子文件夹

if not os.path.exists(filepath):
    success = download_image(url, filepath, max_retries=5)
    if not success:
        print(f"\n下载失败：\n日期：{date_str_file}\n下载链接：{url}")
else:
    print(f"{filename} 已存在，跳过下载")