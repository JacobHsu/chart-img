---
name: Crypto Technical Analysis
description: Analyze cryptocurrency trends using technical charts and AI (Grok-2/OpenAI).
---

# Crypto Technical Analysis Skill

This skill allows you to perform technical analysis on cryptocurrency pairs (e.g., ETHUSDT) by generating a chart with indicators (EMA, MACD) and using AI to interpret the trend.

## Capabilities

1.  **Generate Chart**: Fetches a technical chart from `chart-img.com` with pre-configured indicators (Volume, EMA Ribbon, MACD).
2.  **Analyze Trend**: Uses GitHub Models (Grok-2 Vision) to analyze the chart image.
3.  **Notify**: Sends the chart and analysis report to a configured Telegram chat.

## Usage

### 1. Local Execution (Direct)

To run the analysis directly from the terminal (requires Python environment setup):

```bash
# Ensure dependencies are installed
pip install -r requirements.txt

# Run the analysis (Uses .env configuration)
# Default: ETHUSDT, 1h interval
python analyze_chart.py
```

To specify a different symbol or interval, set the environment variables:

```powershell
$env:SYMBOL="BTCUSDT"; $env:INTERVAL="4h"; python analyze_chart.py
```

### 2. Trigger via GitHub Actions (Remote)

To trigger the analysis remotely via GitHub Actions:

```bash
gh workflow run "Crypto Analysis Bot"
```

## Configuration

Ensure the following environment variables are set in `.env` (local) or GitHub Secrets (remote):

*   `CHART_IMG_API_KEY`: API key for chart generation.
*   `TELEGRAM_BOT_TOKEN`: Telegram Bot Token.
*   `TELEGRAM_CHAT_ID`: Target Chat ID.
*   `GH_TOKEN`: GitHub Token for AI Model access.
