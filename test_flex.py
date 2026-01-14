import os
import logging
import gspread
from dotenv import load_dotenv
from main import get_google_creds, create_flex_message, push_flex_notification

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load env
load_dotenv()

def get_test_user_id():
    """
    Try to get a user ID from Google Sheets to test with.
    """
    creds = get_google_creds()
    if not creds:
        return None
        
    try:
        gc = gspread.authorize(creds)
        sheet_url = os.getenv('GOOGLE_SHEET_URL')
        if not sheet_url:
            return None
            
        sh = gc.open_by_url(sheet_url)
        worksheet = sh.worksheet("Subscribers")
        records = worksheet.get_all_records()
        
        for r in records:
            if r.get('userId'):
                return r.get('userId')
                
    except Exception as e:
        logger.error(f"Error reading sheet: {e}")
        
    return None

def main():
    logger.info("Starting Flex Message Test...")
    
    # 1. Get Target User
    user_id = get_test_user_id()
    if not user_id:
        logger.warning("Could not find a user ID in Google Sheets.")
        user_id = input("Please enter your LINE User ID manually: ").strip()
        
    if not user_id:
        logger.error("No User ID provided. Aborting.")
        return

    logger.info(f"Sending test messages to: {user_id}")

    # 2. Mock Data for BUY Signal (Red)
    # 假設台積電強勢反彈
    buy_msg = create_flex_message(
        ticker="2330.TW",
        signal="BUY",
        price=1080.0,
        k=18.5,
        d=17.2,
        time_str="2026-05-20 13:30"
    )
    
    # 3. Mock Data for SELL Signal (Green)
    # 假設聯發科高檔鈍化
    sell_msg = create_flex_message(
        ticker="2454.TW",
        signal="SELL",
        price=1250.0,
        k=85.4,
        d=82.1,
        time_str="2026-05-20 13:35"
    )

    # 4. Send Messages
    logger.info("Sending BUY Signal Test...")
    push_flex_notification(user_id, buy_msg)
    
    logger.info("Sending SELL Signal Test...")
    push_flex_notification(user_id, sell_msg)
    
    logger.info("Test Completed. Check your LINE!")

if __name__ == "__main__":
    main()
