import yfinance as yf
import pandas as pd
import pandas_ta as ta
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

TICKERS = ["2330.TW", "0050.TW", "2454.TW", "2603.TW", "2317.TW"] # TSMC, 0050, MTK, Evergreen, Foxconn
START_FUNDS = 100000

def run_backtest(ticker):
    logger.info(f"\n📈 Backtesting {ticker} (1 Year)...")
    
    # 1. Get Data
    df = yf.download(ticker, period="1y", interval="1d", progress=False)
    if df.empty:
        logger.error("No data found.")
        return None

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    # 2. Indicators
    stoch = df.ta.stoch(k=14, d=3, smooth_k=3)
    if stoch is None:
        logger.error("Failed to calc KD.")
        return
        
    df = pd.concat([df, stoch], axis=1)
    
    df.ta.sma(length=60, append=True) # SMA_60
    df.ta.rsi(length=14, append=True) # RSI_14
    df.ta.macd(append=True)           # MACD_12_26_9, MACDh_12_26_9, MACDs_12_26_9

    # 3. Simulate
    position = 0 # 0 or 1 (shares)
    entry_price = 0
    cash = START_FUNDS
    trades = 0
    wins = 0
    total_profit = 0
    
    # Iterate
    # col names: STOCHk_14_3_3, STOCHd_14_3_3, SMA_60, RSI_14, MACDh_12_26_9
    k_col = 'STOCHk_14_3_3'
    d_col = 'STOCHd_14_3_3'
    ma_col = 'SMA_60'
    rsi_col = 'RSI_14'
    hist_col = 'MACDh_12_26_9'
    
    # Drop NaN
    df = df.dropna()
    
    history = []

    for i in range(1, len(df)):
        date = df.index[i]
        today = df.iloc[i]
        prev = df.iloc[i-1]
        
        price = today['Close']
        k = today[k_col]
        d = today[d_col]
        k_prev = prev[k_col]
        d_prev = prev[d_col]
        
        # New Indicators
        ma60 = today.get(ma_col, 0)
        rsi = today.get(rsi_col, 50)
        hist = today.get(hist_col, 0)
        hist_prev = prev.get(hist_col, 0)
        
        # LOGIC V3:
        # 1. Trend Filter: Price > 60MA
        trend_up = price > ma60
        
        # 2. Momentum Filter: MACD Histogram is INCREASING (Green bar growing or Red bar shrinking)
        momentum_up = hist > hist_prev
        
        # BUY: K < 20 (Low) AND Gold Cross AND Trend UP AND Momentum UP
        base_buy = k < 20 and k_prev < d_prev and k > d
        buy_signal = base_buy and trend_up and momentum_up
        
        # SELL: K > 80 (High) AND Dead Cross
        # Passivation Filter: If RSI > 70, hold! (Don't sell yet)
        base_sell = k > 80 and k_prev > d_prev and k < d
        strong_momentum = rsi > 70
        sell_signal = base_sell and not strong_momentum
        
        # Execute
        if position == 0 and buy_signal:
            # Buy max shares
            shares = int(cash // price)
            if shares > 0:
                cost = shares * price
                cash -= cost
                position = shares
                entry_price = price
                logger.info(f"   [{date.date()}] BUY  @ {price:.2f} | K={k:.1f} (Shares: {shares})")
                
        elif position > 0 and sell_signal:
            # Sell all
            revenue = position * price
            profit = revenue - (position * entry_price)
            cash += revenue
            trades += 1
            if profit > 0: wins += 1
            total_profit += profit
            
            logger.info(f"   [{date.date()}] SELL @ {price:.2f} | K={k:.1f} | PnL: {profit:.0f}")
            position = 0
            
    # End Value
    final_value = cash + (position * df.iloc[-1]['Close'])
    roi = ((final_value - START_FUNDS) / START_FUNDS) * 100
    win_rate = (wins / trades * 100) if trades > 0 else 0
    
    logger.info(f"📊 Result for {ticker}:")
    logger.info(f"   Trades: {trades}, Wins: {wins} ({win_rate:.1f}%)")
    logger.info(f"   Final Value: {final_value:.0f} (ROI: {roi:.2f}%)")
    
    return {
        'ticker': ticker,
        'roi': roi,
        'win_rate': win_rate,
        'trades': trades
    }

if __name__ == "__main__":
    results = []
    for t in TICKERS:
        res = run_backtest(t)
        if res: results.append(res)
        
    print("\n" + "="*40)
    print(f"{'Ticker':<10} {'ROI':<10} {'WinRate':<10} {'Trades'}")
    print("-" * 40)
    for r in results:
        print(f"{r['ticker']:<10} {r['roi']:<9.2f}% {r['win_rate']:<9.1f}% {r['trades']}")
    print("="*40)
