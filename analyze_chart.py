import os
import datetime
import requests
import base64
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

# Configuration
CHART_IMG_API_KEY = os.getenv("CHART_IMG_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")
SYMBOL = os.getenv("SYMBOL", "ETHUSDT") # Default symbol
INTERVAL = os.getenv("INTERVAL", "1h")  # Default interval

NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
NVIDIA_MODEL = "meta/llama-3.3-70b-instruct"

def check_config():
    missing = []
    if not CHART_IMG_API_KEY: missing.append("CHART_IMG_API_KEY")
    if not TELEGRAM_BOT_TOKEN: missing.append("TELEGRAM_BOT_TOKEN")
    if not TELEGRAM_CHAT_ID: missing.append("TELEGRAM_CHAT_ID")
    if not NVIDIA_API_KEY: missing.append("NVIDIA_API_KEY")

    if missing:
        print(f"Error: Missing environment variables: {', '.join(missing)}")
        print("Please check your .env file or GitHub Secrets.")
        exit(1)

def get_chart_url(symbol, interval):
    print(f"Generating chart for {symbol} ({interval})...")
    url = "https://api.chart-img.com/v2/tradingview/advanced-chart/storage"
    payload = {
        "theme": "dark",
        "interval": interval,
        "symbol": f"BINANCE:{symbol}",
        "override": {
            "showStudyLastValue": False
        },
        "studies": [
            {"name": "Volume", "forceOverlay": True},
            {
                "name": "Moving Average Multiple",
                "input": {
                    "firstPeriods": 5,
                    "secondPeriods": 10,
                    "thirdPeriods": 20,
                    "method": "Exponential"
                }
            },
            {"name": "MACD"}
        ]
    }
    headers = {
        "x-api-key": CHART_IMG_API_KEY,
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        chart_url = response.json().get('url')
        print(f"Chart URL: {chart_url}")
        
        # Save image locally for README display
        try:
            img_data = requests.get(chart_url).content
            with open("latest_chart.png", "wb") as f:
                f.write(img_data)
            print("Saved chart to latest_chart.png")
        except Exception as e:
            print(f"Failed to save local image: {e}")
            
        return chart_url
    except Exception as e:
        print(f"Failed to get chart: {e}")
        if response.text:
            print(f"Response: {response.text}")
        exit(1)

def get_binance_klines(symbol: str, interval: str, limit: int = 200) -> list[float]:
    url = "https://api.binance.us/api/v3/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    response = requests.get(url, params=params)
    response.raise_for_status()
    return [float(k[4]) for k in response.json()]  # close prices

def calculate_ema(prices: list[float], period: int) -> float:
    k = 2 / (period + 1)
    ema = prices[0]
    for price in prices[1:]:
        ema = price * k + ema * (1 - k)
    return ema

def get_indicators(symbol: str, interval: str) -> dict:
    print(f"Fetching Binance klines for {symbol} ({interval})...")
    closes = get_binance_klines(symbol, interval, limit=300)

    ema5   = calculate_ema(closes, 5)
    ema10  = calculate_ema(closes, 10)
    ema20  = calculate_ema(closes, 20)
    ema50  = calculate_ema(closes, 50)
    ema100 = calculate_ema(closes, 100)

    # MACD: EMA12 - EMA26, Signal: EMA9 of MACD line
    ema12_series, ema26_series = [], []
    k12, k26 = 2 / 13, 2 / 27
    e12 = e26 = closes[0]
    for price in closes:
        e12 = price * k12 + e12 * (1 - k12)
        e26 = price * k26 + e26 * (1 - k26)
        ema12_series.append(e12)
        ema26_series.append(e26)

    macd_series = [m - s for m, s in zip(ema12_series, ema26_series)]
    signal_val = calculate_ema(macd_series, 9)
    macd_val   = macd_series[-1]
    histogram  = macd_val - signal_val

    return {
        "close":   round(closes[-1], 2),
        "ema5":    round(ema5, 2),
        "ema10":   round(ema10, 2),
        "ema20":   round(ema20, 2),
        "ema50":   round(ema50, 2),
        "ema100":  round(ema100, 2),
        "macd":    round(macd_val, 4),
        "signal":  round(signal_val, 4),
        "histogram": round(histogram, 4),
    }

def encode_image_to_base64(image_path: str) -> str:
    with open(image_path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8")

def analyze_chart_with_ai(symbol: str, indicators: dict) -> str:
    print(f"Analyzing chart with NVIDIA NIM ({NVIDIA_MODEL})...")

    client = OpenAI(
        base_url=NVIDIA_BASE_URL,
        api_key=NVIDIA_API_KEY,
    )

    ind = indicators
    macd_cross = "金叉" if ind["macd"] > ind["signal"] else "死叉"
    hist_sign  = "正值（偏多動能）" if ind["histogram"] > 0 else "負值（偏空動能）"

    close = ind["close"]
    if close > ind["ema5"] and ind["ema5"] > ind["ema10"] and ind["ema10"] > ind["ema20"]:
        ema_arrangement = "多頭排列"
    elif close < ind["ema5"] and ind["ema5"] < ind["ema10"] and ind["ema10"] < ind["ema20"]:
        ema_arrangement = "空頭排列"
    else:
        ema_arrangement = "均線糾結"

    prompt = f"""
你是一位專業的加密貨幣技術分析師，請依據以下從幣安 API 取得的精確數值撰寫分析報告。

【精確指標數值（已由程式計算，請直接使用，勿更改）】
幣種：{symbol}
收盤價：{ind["close"]}
EMA5={ind["ema5"]} / EMA10={ind["ema10"]} / EMA20={ind["ema20"]} / EMA50={ind["ema50"]} / EMA100={ind["ema100"]}
MACD={ind["macd"]} / Signal={ind["signal"]} / Histogram={ind["histogram"]}

【已由程式判斷完成，請直接使用】
均線排列：{ema_arrangement}（收盤價={close} vs EMA5={ind["ema5"]} / EMA10={ind["ema10"]} / EMA20={ind["ema20"]}）
MACD 狀態：{macd_cross}（MACD={ind["macd"]} vs Signal={ind["signal"]}）
柱狀圖：{hist_sign}（Histogram={ind["histogram"]}）

【操作建議規則（請嚴格遵守）】
- 多頭排列 + 金叉 → 強力買入或買入
- 多頭排列 + 死叉 → 中立
- 均線糾結 → 中立
- 空頭排列 + 死叉 → 強力賣出或賣出
- 空頭排列 + 金叉 → 中立

請依下列 HTML 格式輸出（直接輸出 HTML，不要加其他說明）：

<b>📊 技術分析報告</b>

<b>幣種：</b>{symbol}　<b>收盤價：</b>{ind["close"]}

<b>均線數值</b>
EMA5={ind["ema5"]} | EMA10={ind["ema10"]} | EMA20={ind["ema20"]}
EMA50={ind["ema50"]} | EMA100={ind["ema100"]}

<b>MACD 數值</b>
MACD={ind["macd"]} | Signal={ind["signal"]} | Histogram={ind["histogram"]}

<b>趨勢判斷：</b>（偏多 / 偏空 / 震盪整理，依均線排列與MACD綜合判斷）

<b>技術解讀</b>
• <b>均線系統：</b>{ema_arrangement}，（補充說明均線支撐壓力與走勢含意，一句話）
• <b>MACD：</b>{macd_cross}，柱狀圖{hist_sign}，（補充說明動能趨勢，一句話）

<b>操作建議：</b>（強力買入 / 買入 / 中立 / 賣出 / 強力賣出）
<b>依據：</b>（依均線排列+MACD狀態，一句話說明判斷邏輯）
"""

    try:
        response = client.chat.completions.create(
            model=NVIDIA_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            temperature=0.1,
            max_tokens=1024,
        )
        analysis = response.choices[0].message.content
        print("Analysis complete.")
        return analysis
    except Exception as e:
        print(f"Failed to analyze chart: {e}")
        return "AI 分析失敗，請稍後再試。"

def send_telegram_photo(photo_url):
    print("Sending photo to Telegram...")
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "photo": photo_url
    }
    try:
        response = requests.post(url, data=payload)
        if response.status_code != 200:
            print(f"Failed to send photo: {response.text}")
    except Exception as e:
        print(f"Failed to send photo (Exception): {e}")

def send_telegram_message(text):
    print("Sending analysis report to Telegram...")
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
    }
    try:
        response = requests.post(url, data=payload)
        if response.status_code != 200:
            print(f"Failed to send message: {response.text}")
    except Exception as e:
        print(f"Failed to send message (Exception): {e}")

def update_readme_timestamp():
    readme_path = "README.md"
    try:
        with open(readme_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        current_time = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        new_lines = []
        updated = False
        for line in lines:
            if "*(此圖表會隨 GitHub Action" in line or "*Last Analysis:" in line:
                new_lines.append(f"*Last Analysis: {current_time}*\n")
                updated = True
            else:
                new_lines.append(line)
        if updated:
            with open(readme_path, "w", encoding="utf-8") as f:
                f.writelines(new_lines)
            print(f"Updated README timestamp to: {current_time}")
        else:
            print("Timestamp line not found in README.")
    except Exception as e:
        print(f"Failed to update README timestamp: {e}")

def main(analyze_only: bool = False):
    check_config()

    if analyze_only:
        if not os.path.exists("latest_chart.png"):
            print("Error: latest_chart.png not found. Run without --analyze-only first.")
            exit(1)
        print("Skipping chart fetch, using existing latest_chart.png")
    else:
        chart_url = get_chart_url(SYMBOL, INTERVAL)
        send_telegram_photo(chart_url)

    indicators = get_indicators(SYMBOL, INTERVAL)
    print(f"Indicators: {indicators}")
    analysis_report = analyze_chart_with_ai(SYMBOL, indicators)
    send_telegram_message(analysis_report)
    update_readme_timestamp()

    print("Workflow completed successfully.")

if __name__ == "__main__":
    import sys
    main(analyze_only="--analyze-only" in sys.argv)
