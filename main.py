import os
import json
import logging
from datetime import datetime, timedelta, timezone
import pandas as pd
import yfinance as yf
import pandas_ta as ta
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from linebot import LineBotApi
from linebot.models import FlexSendMessage
from linebot.exceptions import LineBotApiError
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def get_google_creds():
    """
    Get Google Credentials from local file or environment variable.
    Returns a ServiceAccountCredentials object or None.
    """
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    
    # Priority 1: Local file
    local_creds_path = 'service-account.json'
    if os.path.exists(local_creds_path):
        logger.info("Loading credentials from local file.")
        return ServiceAccountCredentials.from_json_keyfile_name(local_creds_path, scope)
    
    # Priority 2: Environment Variable (for GitHub Actions)
    env_creds = os.getenv('GOOGLE_CREDS')
    if env_creds:
        logger.info("Loading credentials from environment variable.")
        try:
            creds_dict = json.loads(env_creds)
            return ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        except json.JSONDecodeError:
            logger.error("Failed to decode GOOGLE_CREDS environment variable.")
            return None
            
    logger.error("No credentials found.")
    return None

def check_kd_signal(ticker):
    """
    Check KD signal for a given ticker with robust MultiIndex handling.
    """
    try:
        # Handle stock ticker format
        t_str = str(ticker).strip()
        stock_ticker = f"{t_str}.TW" if "." not in t_str else t_str
        
        # Download data (1mo is sufficient for recent KD)
        df = yf.download(stock_ticker, period="1mo", interval="1d", progress=False)
        
        if df.empty or len(df) < 14:
            logger.warning(f"Insufficient data for {stock_ticker}")
            return None, 0, 0, 0

        # Flatten columns if MultiIndex (fix for recent yfinance)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # Calculate KD (14, 3, 3)
        stoch = df.ta.stoch(k=14, d=3, smooth_k=3)
        
        if stoch is None or stoch.empty:
             return None, 0, 0, 0
        
        # Get latest values
        # pandas-ta columns: STOCHk_14_3_3, STOCHd_14_3_3
        k_today = stoch['STOCHk_14_3_3'].iloc[-1]
        d_today = stoch['STOCHd_14_3_3'].iloc[-1]
        k_prev = stoch['STOCHk_14_3_3'].iloc[-2]
        d_prev = stoch['STOCHd_14_3_3'].iloc[-2]
        
        # Get Price
        current_price = df['Close'].iloc[-1]
        
        signal = None
        
        # BUY Signal: K < 20 and K crosses above D
        if k_today < 20 and k_prev < d_prev and k_today > d_today:
            signal = 'BUY'
            
        # SELL Signal: K > 80 and K crosses below D
        elif k_today > 80 and k_prev > d_prev and k_today < d_today:
            signal = 'SELL'
            
        return signal, k_today, d_today, current_price

    except Exception as e:
        logger.error(f"Error processing {ticker}: {e}")
        return None, 0, 0, 0

def create_flex_message(ticker, signal, price, k, d, time_str):
    """
    Create a detailed Flex Message for the signal.
    """
    # Color logic: Red for Buy (Taiwan stock up), Green for Sell (Taiwan stock down)
    color = "#E03E3E" if signal == 'BUY' else "#2DB84D"
    signal_text = "強勢買進 🚀" if signal == 'BUY' else "高檔賣出 📉"
    
    bubble = {
      "type": "bubble",
      "size": "mega",
      "header": {
        "type": "box",
        "layout": "vertical",
        "contents": [
          {
            "type": "box",
            "layout": "vertical",
            "contents": [
              {
                "type": "text",
                "text": signal_text,
                "color": "#ffffff",
                "weight": "bold",
                "size": "xl"
              }
            ]
          }
        ],
        "paddingAll": "20px",
        "backgroundColor": color,
        "spacing": "md",
        "height": "100px",
        "paddingTop": "22px"
      },
      "body": {
        "type": "box",
        "layout": "vertical",
        "contents": [
          {
            "type": "text",
            "text": f"{ticker}",
            "weight": "bold",
            "size": "xxl",
            "margin": "md"
          },
          {
            "type": "text",
            "text": f"{price:.2f}",
            "size": "xl",
            "weight": "bold",
            "color": color
          },
          {
            "type": "separator",
            "margin": "lg"
          },
          {
            "type": "box",
            "layout": "vertical",
            "margin": "lg",
            "spacing": "sm",
            "contents": [
              {
                "type": "box",
                "layout": "baseline",
                "spacing": "sm",
                "contents": [
                  {
                    "type": "text",
                    "text": "K 值 (Fast)",
                    "color": "#aaaaaa",
                    "size": "sm",
                    "flex": 2
                  },
                  {
                    "type": "text",
                    "text": f"{k:.2f}",
                    "wrap": True,
                    "color": "#666666",
                    "size": "sm",
                    "flex": 4,
                    "weight": "bold"
                  }
                ]
              },
              {
                "type": "box",
                "layout": "baseline",
                "spacing": "sm",
                "contents": [
                  {
                    "type": "text",
                    "text": "D 值 (Slow)",
                    "color": "#aaaaaa",
                    "size": "sm",
                    "flex": 2
                  },
                  {
                    "type": "text",
                    "text": f"{d:.2f}",
                    "wrap": True,
                    "color": "#666666",
                    "size": "sm",
                    "flex": 4,
                    "weight": "bold"
                  }
                ]
              },
               {
                "type": "box",
                "layout": "baseline",
                "spacing": "sm",
                "contents": [
                  {
                    "type": "text",
                    "text": "偵測時間",
                    "color": "#aaaaaa",
                    "size": "sm",
                    "flex": 2
                  },
                  {
                    "type": "text",
                    "text": time_str,
                    "wrap": True,
                    "color": "#666666",
                    "size": "xs",
                    "flex": 4
                  }
                ]
              }
            ]
          }
        ]
      },
      "footer": {
        "type": "box",
        "layout": "vertical",
        "contents": [
            {
            "type": "button",
            "action": {
              "type": "uri",
              "label": "查看詳細技術線圖",
              "uri": f"https://tw.stock.yahoo.com/quote/{ticker}"
            },
            "style": "link",
            "height": "sm"
          }
        ]
      }
    }
    return FlexSendMessage(alt_text=f"{signal} Signal for {ticker}", contents=bubble)

def push_flex_notification(user_id, flex_message):
    """
    Send LINE Flex message.
    """
    token = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
    if not token:
        logger.error("LINE_CHANNEL_ACCESS_TOKEN not found.")
        return

    try:
        line_bot_api = LineBotApi(token)
        line_bot_api.push_message(user_id, flex_message)
        logger.info(f"Sent Flex Message to {user_id}")
    except LineBotApiError as e:
        logger.error(f"LINE API Error: {e}")

def main():
    logger.info("Starting Stock KD Bot (v2.0 Refined)...")
    
    # 1. Connect to Google Sheets
    creds = get_google_creds()
    if not creds:
        logger.error("Skipping Google Sheets operations due to missing credentials.")
        return

    try:
        gc = gspread.authorize(creds)
        sheet_url = os.getenv('GOOGLE_SHEET_URL')
        if not sheet_url:
             logger.error("GOOGLE_SHEET_URL not set.")
             return
             
        sh = gc.open_by_url(sheet_url)
        worksheet = sh.worksheet("Subscribers")
        
        # Get all records
        records = worksheet.get_all_records()
        
        if not records:
            logger.info("No subscribers found.")
            return

        # 2. Get unique tickers
        tickers = list(set([str(r['ticker']) for r in records if r['ticker']]))
        logger.info(f"Processing {len(tickers)} unique tickers: {tickers}")
        
        ticker_signals = {}
        
        # 3. Check signals
        for ticker in tickers:
            signal, k, d, price = check_kd_signal(ticker)
            if signal:
                logger.info(f"Signal detected for {ticker}: {signal}")
                ticker_signals[ticker] = {
                    'type': signal,
                    'k': k,
                    'd': d,
                    'price': price
                }
            else:
                pass # Silent logs for no signal to reduce noise
        
        # 4. Notify subscribers
        if not ticker_signals:
            logger.info("No signals detected today.")
            return

        # Set Timezone to Taipei
        tz = timezone(timedelta(hours=8))
        now_tw = datetime.now(tz).strftime('%Y-%m-%d %H:%M')

        for record in records:
            uid = record.get('userId')
            t = str(record.get('ticker'))
            
            if t in ticker_signals and uid:
                sig_data = ticker_signals[t]
                
                # Create Flex Message
                msg = create_flex_message(
                    ticker=t,
                    signal=sig_data['type'],
                    price=sig_data['price'],
                    k=sig_data['k'],
                    d=sig_data['d'],
                    time_str=now_tw
                )
                
                push_flex_notification(uid, msg)

    except Exception as e:
        logger.error(f"Main loop error: {e}")

if __name__ == "__main__":
    main()
