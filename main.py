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

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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

def get_stock_fundamentals(ticker):
    """
    Get fundamental data: PE, EPS, Dividend Yield.
    Returns dict or None.
    """
    try:
        t_str = str(ticker).strip()
        stock_ticker = f"{t_str}.TW" if "." not in t_str else t_str
        info = yf.Ticker(stock_ticker).info
        
        return {
            'pe': info.get('trailingPE'),
            'eps': info.get('trailingEps'),
            'yield': info.get('dividendYield') # usually float 0.012 for 1.2%
        }
    except Exception as e:
        logger.error(f"Error fetching fundamentals for {ticker}: {e}")
        return None

def check_kd_signal(ticker):
    """
    Check KD signal for a given ticker with robust MultiIndex handling.
    """
    try:
        # Handle stock ticker format
        t_str = str(ticker).strip()
        stock_ticker = f"{t_str}.TW" if "." not in t_str else t_str
        
        # Download data (Need 6mo for MA60)
        df = yf.download(stock_ticker, period="6mo", interval="1d", progress=False)
        
        if df.empty or len(df) < 60:
            logger.warning(f"Insufficient data for {stock_ticker}")
            return None, 0, 0, 0, 0.0

        # Flatten columns if MultiIndex (fix for recent yfinance)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # Calculate Indicators
        stoch = df.ta.stoch(k=14, d=3, smooth_k=3)
        sma60 = df.ta.sma(length=60)
        rsi = df.ta.rsi(length=14)

        # Calculate Volume SMA (5 days)
        if 'Volume' in df.columns:
            vol_sma = df.ta.sma(length=5, close='Volume')
            if not df['Volume'].empty and vol_sma is not None and not vol_sma.empty:
                vol_today = df['Volume'].iloc[-1]
                vol_avg = vol_sma.iloc[-1]
                vol_ratio = vol_today / vol_avg if vol_avg > 0 else 1.0
            else:
                vol_ratio = 1.0
        else:
            vol_ratio = 1.0
        
        if stoch is None or stoch.empty:
             return None, 0, 0, 0, 0.0
        
        # Get latest values
        # pandas-ta columns: STOCHk_14_3_3, STOCHd_14_3_3
        k_today = stoch['STOCHk_14_3_3'].iloc[-1]
        d_today = stoch['STOCHd_14_3_3'].iloc[-1]
        k_prev = stoch['STOCHk_14_3_3'].iloc[-2]
        d_prev = stoch['STOCHd_14_3_3'].iloc[-2]
        
        # New Indicators (Trend & Momentum)
        ma60_val = sma60.iloc[-1] if sma60 is not None else 0
        rsi_val = rsi.iloc[-1] if rsi is not None else 50
        
        # Get Price
        current_price = df['Close'].iloc[-1]
        
        signal = None
        
        # BUY Signal: K < 20 and Gold Cross AND Trend > 60MA
        if k_today < 20 and k_prev < d_prev and k_today > d_today:
            if current_price > ma60_val:
                signal = 'BUY'
            else:
                logger.info(f"{ticker}: BUY signal ignored (Downtrend: {current_price:.1f} < 60MA {ma60_val:.1f})")
            
        # SELL Signal: K > 80 and Dead Cross
        elif k_today > 80 and k_prev > d_prev and k_today < d_today:
            if rsi_val > 70:
                signal = 'HOLD' # Passivation - Hold
                logger.info(f"{ticker}: SELL signal -> HOLD (RSI {rsi_val:.1f} > 70)")
            else:
                signal = 'SELL'
            
        return signal, k_today, d_today, current_price, vol_ratio

    except Exception as e:
        logger.error(f"Error processing {ticker}: {e}")
        return None, 0, 0, 0, 0.0

def create_flex_message(ticker, signal, price, k, d, time_str, fundamentals=None, vol_ratio=1.0):
    """
    Create a detailed Flex Message for the signal.
    """
    # Color logic
    # Color logic
    if signal == 'BUY':
        color = "#E03E3E"
        signal_text = "強勢買進 🚀"
    elif signal == 'HOLD':
        color = "#FF9900"
        signal_text = "高檔鈍化 (續抱) 💎"
    else:
        color = "#2DB84D"
        signal_text = "高檔賣出 📉"
    
    # Fundamentals formatting
    fund_contents = []
    if fundamentals:
        pe = fundamentals.get('pe', 'N/A')
        eps = fundamentals.get('eps', 'N/A')
        dy = fundamentals.get('yield', 'N/A')
        
        pe_str = f"{pe:.1f}x" if isinstance(pe, (int, float)) else "-"
        eps_str = f"{eps:.2f}" if isinstance(eps, (int, float)) else "-"
        # Fix Yield: yfinance returns percentage (e.g. 1.2), not decimal
        dy_str = f"{dy:.1f}%" if isinstance(dy, (int, float)) else "-"
        
        fund_contents = [
             {
                "type": "box",
                "layout": "vertical",
                "margin": "md",
                "paddingAll": "12px",
                "backgroundColor": "#f7f7f7",
                "cornerRadius": "md",
                "contents": [
                     { "type": "text", "text": "基本面 (Fundamentals)", "size": "xxs", "color": "#aaaaaa", "weight": "bold", "margin": "none" },
                     { "type": "separator", "margin": "sm" },
                     {
                        "type": "box",
                        "layout": "horizontal",
                        "margin": "md",
                        "spacing": "xs",
                        "contents": [
                             # Stack 1: PE
                             { "type": "text", "text": "PE", "size": "xxs", "color": "#888888", "flex": 1, "gravity": "bottom" },
                             { "type": "text", "text": pe_str, "size": "xs", "color": "#333333", "flex": 2, "weight": "bold", "gravity": "bottom", "align": "end" },
                             
                             # Stack 2: EPS
                             { "type": "text", "text": "EPS", "size": "xxs", "color": "#888888", "flex": 1, "margin": "md", "gravity": "bottom" },
                             { "type": "text", "text": eps_str, "size": "xs", "color": "#333333", "flex": 2, "weight": "bold", "gravity": "bottom", "align": "end" }
                        ]
                     },
                     {
                        "type": "box",
                        "layout": "horizontal",
                        "margin": "sm",
                        "spacing": "xs",
                        "contents": [
                             # Stack 3: Yield
                             { "type": "text", "text": "Yield", "size": "xxs", "color": "#888888", "flex": 1, "gravity": "bottom" },
                             { "type": "text", "text": dy_str, "size": "xs", "color": "#333333", "flex": 2, "weight": "bold", "gravity": "bottom", "align": "end" },
                             
                             # Filler (Empty box or filler)
                             { "type": "filler", "flex": 3 } 
                        ]
                     }
                ]
             }
        ]

    # Volume Badge
    vol_badge = []
    if vol_ratio >= 2.0:
        vol_badge = [{
            "type": "text",
            "text": f"🔥 爆量攻擊 ({vol_ratio:.1f}x)",
            "weight": "bold",
            "size": "sm",
            "color": "#E03E3E", # Red
            "margin": "md"
        }]

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
          # Insert Volume Badge here
          *vol_badge,
          {
            "type": "separator",
            "margin": "lg"
          },
          # Insert Fundamentals here
          *fund_contents,
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

def check_market_trend():
    """
    Check Taiwan Weighted Index (^TWII) trend against 20MA (Month Line).
    Returns: 'UP' (Bullish) or 'DOWN' (Bearish), and a string message.
    """
    try:
        ticker = "^TWII"
        # Download roughly 2 months to get a valid 20MA
        df = yf.download(ticker, period="2mo", interval="1d", progress=False)
        
        if df.empty or len(df) < 20:
             logger.warning("Insufficient data for Market Trend.")
             return 'UP', "無法判定 (資料不足)" # Fail open (allow buys) or closed? Let's fail open but log.
             
        # Flatten columns if MultiIndex
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # Calculate SMA 20
        # pandas-ta usually adds a column like 'SMA_20'
        df.ta.sma(length=20, append=True)
        
        col_name = 'SMA_20'
        if col_name not in df.columns:
             # Fallback
             return 'UP', "無法判定 (MA計算失敗)"

        latest = df.iloc[-1]
        price = latest['Close']
        ma20 = latest[col_name]
        
        if pd.isna(ma20):
             return 'UP', "無法判定 (MA為空)"

        if price > ma20:
            return 'UP', f"大盤強勢 (指數 {price:.0f} > 月線 {ma20:.0f})"
        else:
            return 'DOWN', f"大盤弱勢 (指數 {price:.0f} < 月線 {ma20:.0f})"

    except Exception as e:
        logger.error(f"Error checking market trend: {e}")
        return 'UP', "無法判定 (發生錯誤)"

def main():
    logger.info("Starting Stock KD Bot (v2.0 Refined)...")
    
    # 0. Check Market Trend
    trend, trend_msg = check_market_trend()
    logger.info(f"Market Trend: {trend} - {trend_msg}")
    
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
            signal, k, d, price, vol_ratio = check_kd_signal(ticker) # Unpack vol_ratio
            if signal:
                # MARKET FILTER LOGIC
                if signal == 'BUY' and trend == 'DOWN':
                    logger.info(f"Signal detected for {ticker}: {signal}, but BLOCKED by Market Filter ({trend_msg})")
                    continue

                # Fetch Fundamentals only for signals
                fund_data = get_stock_fundamentals(ticker)

                logger.info(f"Signal detected for {ticker}: {signal}")
                ticker_signals[ticker] = {
                    'type': signal,
                    'k': k,
                    'd': d,
                    'price': price,
                    'vol_ratio': vol_ratio,
                    'fundamentals': fund_data
                }
            else:
                pass 

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
                    time_str=now_tw,
                    fundamentals=sig_data['fundamentals'],
                    vol_ratio=sig_data['vol_ratio']
                )
                
                push_flex_notification(uid, msg)

    except Exception as e:
        logger.error(f"Main loop error: {e}")

if __name__ == "__main__":
    main()
