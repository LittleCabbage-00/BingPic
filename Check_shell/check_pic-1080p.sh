#!/bin/zsh

# 检查参数数量
if [ $# -gt 1 ]; then
    echo "Usage: $0 [year]"
    exit 1
fi

# 获取年份参数或当前年份（强制转换为十进制）
if [ $# -eq 1 ]; then
    YEAR=$((10#$1)) 
    CURRENT_YEAR=$(date +%Y)
    if [ $YEAR -gt $CURRENT_YEAR ]; then
        echo "oops"
        exit 1
    fi
else
    YEAR=$(date +%Y)
fi

# 确定需要检查的天数
is_leap_year() {
    local year=$1
    if (( (year % 400 == 0) )) || { (( (year % 4 == 0) )) && (( (year % 100 != 0) )); }; then
        return 0
    else
        return 1
    fi
}

if [ $# -eq 0 ]; then
    DAYS=$(date +%j)
else
    if is_leap_year $YEAR; then
        DAYS=366
    else
        DAYS=365
    fi
fi

# 新增计数器 [[3]][[10]]
missing_count=0

for ((d=1; d<=DAYS; d++)); do
    DATE_STR=$(date -d "$YEAR-01-01 +$((d-1)) days" +"%m-%d")
    FILENAME="bing_pic_${YEAR}-${DATE_STR}.jpg"
    if [ ! -e "$FILENAME" ]; then
        echo "$FILENAME"
        missing_count=$((missing_count + 1))  # 计数缺失文件 [[10]]
    fi
done

# 最终检查 [[3]][[10]]
if [ $missing_count -eq 0 ]; then
    echo "no pic"
fi
