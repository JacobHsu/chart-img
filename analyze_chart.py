import os
import requests
import json
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

def analyze_chart_with_ai(image_url, symbol):
    print("Analyzing chart with NVIDIA NIM (llama-3.2-90b-vision)...")

    client = OpenAI(
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=NVIDIA_API_KEY,
    )

    prompt = f"""
你是世界級的加密貨幣技術分析師，擅長價格行為 (Price Action) 與趨勢交易。

圖表中包含：
1. K線圖 ({symbol})
2. EMA 指標 (多條移動平均線)
3. 成交量 (Volume)
4. MACD 指標 (底部副圖)

請綜合分析圖表資訊，並嚴格依照下方格式產出報告（模仿 CoinAnk 專業簡報風格）：

---
【全方位技術分析報告】
標的：{symbol}
時間週期：{INTERVAL if 'INTERVAL' in globals() else '自訂'} 

1. 趨勢訊號
• 趨勢方向：[ 強力看多 | 偏多 | 震盪 | 偏空 | 強力看空 ]
• 關鍵價位：
  - 壓力位 (Resistance): [請觀察圖中前高或密集區估算]
  - 支撐位 (Support): [請觀察圖中前低或密集區估算]

2. 技術指標解讀
• K線型態：[若是明顯反轉/延續型態請指出，如吞噬、十字星、W底/M頭...等，若無則填「無特殊型態」]
• 均線系統：[說明 EMA 排列狀態，如多頭排列、空頭排列、糾結]
• 資金動能：[觀察成交量 Volume 變化與 MACD 柱狀圖趨勢]

3. 交易策略建議
• 操作建議：[ 買入 | 賣出 | 觀望 ]
• 策略理由：[一句話總結進出場邏輯]

---
請注意：
- 輸出內容必須「言之有物」，避免模糊兩可的廢話。
- 專注於圖表呈現的客觀事實。
- 價位請根據圖片右側座標軸進行估算。
"""

    try:
        response = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ],
                }
            ],
            model="nvidia/llama-3.2-90b-vision-instruct",
            temperature=0.1,
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
        "text": text, # Using 'text' instead of 'caption' for sendMessage
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, data=payload)
        if response.status_code != 200:
            print(f"Failed to send message: {response.text}")
    except Exception as e:
        print(f"Failed to send message (Exception): {e}")

import datetime

# ... (existing imports)

def update_readme_timestamp():
    readme_path = "README.md"
    try:
        with open(readme_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        current_time = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        new_lines = []
        updated = False
        
        for line in lines:
            # Check for the specific line to replace
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

def main():
    check_config()
    chart_url = get_chart_url(SYMBOL, INTERVAL)
    
    # 1. Send Chart First
    send_telegram_photo(chart_url)
    
    # 2. Analyze and Send Report
    analysis_report = analyze_chart_with_ai(chart_url, SYMBOL)
    send_telegram_message(analysis_report)
    
    # 3. Update Timestamp
    update_readme_timestamp()
    
    print("Workflow completed successfully.")

if __name__ == "__main__":
    main()
