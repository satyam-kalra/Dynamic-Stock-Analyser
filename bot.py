import os
import smtplib
import yfinance as yf
import pandas as pd
import requests
import nltk
from email.mime.text import MIMEText
from datetime import datetime, timedelta
from textblob import TextBlob

# --- SETUP ---
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt', quiet=True)

# --- CONFIGURATION ---
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASS = os.getenv("SENDER_PASS")

CORE_WATCHLIST = ["AAPL", "NVDA", "TSLA", "MSFT"]

class MarketAgent:
    def __init__(self):
        self.report_data = []
        # Start with the core list
        self.active_list = CORE_WATCHLIST.copy()
        # Keep track of which were discovered vs core
        self.discovery_tags = {ticker: "Core" for ticker in CORE_WATCHLIST}

    def get_sentiment(self, text):
        if not text: return 0
        return round(TextBlob(text).sentiment.polarity, 2)

    def get_trend_label(self, score):
        """Your custom 1 to 10 scale"""
        scaled = round(score * 10)
        if scaled >= 1: return f"Expect Profits (+{scaled})"
        if scaled <= -1: return f"Expect Decline ({scaled})"
        return f"Neutral (0)"

    def discover_movers(self):
        """Scans for 'Breakout' stocks and adds them to today's active list"""
        print("Scouting for market breakouts...")
        scout_pool = ["AMD", "META", "GOOGL", "AMZN", "NFLX", "AVGO", "ORCL", "CRM"]
        
        for ticker in scout_pool:
            try:
                stock = yf.Ticker(ticker)
                hist = stock.history(period="2d")
                if len(hist) < 2: continue
                
                prev_close = hist['Close'].iloc[-2]
                curr_close = hist['Close'].iloc[-1]
                pct_change = ((curr_close - prev_close) / prev_close) * 100
                
                # If a scouted stock is up > 2%, add it
                if pct_change > 2.0 and ticker not in self.active_list:
                    print(f"Discovery: {ticker} is surging (+{pct_change:.2f}%)")
                    self.active_list.append(ticker)
                    self.discovery_tags[ticker] = f"Surge (+{pct_change:.1f}%)"
            except: continue

    def run_analysis(self):
        # Step 1: Find the movers
        self.discover_movers()
        print(f"Analyzing {len(self.active_list)} total stocks...")
        
        for ticker in self.active_list:
            try:
                # 1. Price Check
                df = yf.download(ticker, period="5d", interval="1d", progress=False)
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                price = float(df['Close'].iloc[-1])

                # 2. News Sentiment
                end = datetime.now().strftime('%Y-%m-%d')
                start = (datetime.now() - timedelta(days=2)).strftime('%Y-%m-%d')
                url = f"https://finnhub.io/api/v1/company-news?symbol={ticker}&from={start}&to={end}&token={FINNHUB_API_KEY}"
                
                news = requests.get(url).json()
                headlines = [n.get('headline', '') for n in news[:5]]
                
                raw_score = sum([self.get_sentiment(h) for h in headlines]) / len(headlines) if headlines else 0

                # 3. Compile Data
                self.report_data.append({
                    "Ticker": ticker,
                    "Price": f"${price:.2f}",
                    "Status": self.discovery_tags.get(ticker, "Scanned"),
                    "Trend": self.get_trend_label(raw_score),
                    "Articles": len(headlines),
                    "Raw_Score": raw_score # Used for sorting later
                })
                print(f"{ticker} processed.")
            except Exception as e:
                print(f"Error on {ticker}: {e}")

    def send_report(self):
        if not self.report_data: return
        
        df = pd.DataFrame(self.report_data)
        # Sort so the most "Bullish" news is at the top
        df = df.sort_values(by="Raw_Score", ascending=False).drop(columns=["Raw_Score"])
        
        body = f"HYBRID MARKET INTELLIGENCE REPORT\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n{df.to_string(index=False)}"
        msg = MIMEText(body)
        msg['Subject'] = f" Market Intelligence: {len(self.active_list)} Stocks Analysed"
        msg['From'] = SENDER_EMAIL
        msg['To'] = SENDER_EMAIL

        try:
            with smtplib.SMTP('smtp.gmail.com', 587) as server:
                server.starttls()
                server.login(SENDER_EMAIL, SENDER_PASS)
                server.send_message(msg)
            print("Hybrid Report Sent successfully!")
        except Exception as e:
            print(f"Email failed: {e}")

if __name__ == "__main__":
    agent = MarketAgent()
    agent.run_analysis()
    agent.send_report()
