import datetime
import requests
import os
import time


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
        time.sleep(1)
    return False

start_date = datetime.date(2010, 1, 1)
end_date = datetime.date(2020, 12, 31)

current_year = None
save_dir = None

failed_images = []
current_date = start_date

while current_date <= end_date:
    year = current_date.year
    if year != current_year:
        current_year = year
        save_dir = f"bing_{year}_4k"
        os.makedirs(save_dir, exist_ok=True)

    date_str_url = current_date.strftime("%Y%m%d")
    date_str_file = current_date.strftime("%Y-%m-%d")

    url = f"https://bing.ee123.net/img/?date={date_str_url}&size=UHD"
    filename = f"bing_pic_{date_str_file}-4k.jpg"
    filepath = os.path.join(save_dir, filename)
    if not os.path.exists(filepath):
        success = download_image(url, filepath, max_retries=5)
        if not success:
            failed_images.append((date_str_file, url))
    else:
        print(f"{filename} 已存在，跳过下载")

    current_date += datetime.timedelta(days=1)

if failed_images:
    print("\n以下图片下载失败：")
    for date, url in failed_images:
        print(f"日期：{date}，下载链接：{url}")
else:
    print("\n所有图片下载成功！")