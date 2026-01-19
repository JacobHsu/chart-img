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
GH_TOKEN = os.getenv("GH_TOKEN")
SYMBOL = os.getenv("SYMBOL", "ETHUSDT") # Default symbol
INTERVAL = os.getenv("INTERVAL", "1h")  # Default interval

def check_config():
    missing = []
    if not CHART_IMG_API_KEY: missing.append("CHART_IMG_API_KEY")
    if not TELEGRAM_BOT_TOKEN: missing.append("TELEGRAM_BOT_TOKEN")
    if not TELEGRAM_CHAT_ID: missing.append("TELEGRAM_CHAT_ID")
    if not GH_TOKEN: missing.append("GH_TOKEN")
    
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
    print("Analyzing chart with GitHub Models (gpt-4o)...")
    
    client = OpenAI(
        base_url="https://models.inference.ai.azure.com",
        api_key=GH_TOKEN,
    )

    prompt = f"""
你是一位專業的技術分析師，專門分析加密貨幣走勢。

我會提供你一張技術分析圖表，包含多條移動平均線（EMA）與 MACD 指標。請根據圖中走勢給出下列分析報告，語氣與格式請模仿 CoinAnk 行情分析風格，保持專業、條列清楚、簡潔易讀。

請依下列格式回覆：

---
【技術分析報告】
幣種代號：{symbol}
趨勢判斷：請根據 EMA 排列與 MACD 指標給出：「偏多 / 偏空 / 震盪整理」

技術解讀：
- 均線系統：根據 EMA 的排列關係，說明是否呈現多頭排列、空頭排列或均線糾結。
- MACD：說明目前是金叉或死叉，柱狀圖變化，是否顯示趨勢改變。

操作建議：
請從以下五項中選擇一個：「強力買入 / 買入 / 中立 / 賣出 / 強力賣出」，並簡要說明依據。

注意事項：
- 報告務必以條列清楚呈現，易讀性為優先
- 不需展開過程，只需給出結論與解讀
---
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
            model="gpt-4o", # Switched to gpt-4o for GitHub Models compatibility
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

def main():
    check_config()
    chart_url = get_chart_url(SYMBOL, INTERVAL)
    
    # 1. Send Chart First
    send_telegram_photo(chart_url)
    
    # 2. Analyze and Send Report
    analysis_report = analyze_chart_with_ai(chart_url, SYMBOL)
    send_telegram_message(analysis_report)
    
    print("Workflow completed successfully.")

if __name__ == "__main__":
    main()
