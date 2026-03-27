import os
import smtplib
import yfinance as yf
import pandas as pd
import requests
import nltk
from email.mime.text import MIMEText
from datetime import datetime, timedelta
from textblob import TextBlob

# --- INITIALIZATION ---
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt', quiet=True)

# --- CONFIGURATION (Codespaces/Actions Secrets) ---
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASS = os.getenv("SENDER_PASS")

# Your core "Project Controls"
CORE_WATCHLIST = ["AAPL", "NVDA", "TSLA", "MSFT"]

class MarketAgent:
    def __init__(self):
        self.report_data = []
        self.active_list = CORE_WATCHLIST.copy()

    def get_sentiment(self, text):
        if not text: return 0
        return round(TextBlob(text).sentiment.polarity, 2)

    def get_trend_icon(self, score):
        if score > 0.15: return "Expect profits"
        if score < -0.15: return "Expect a decline"
        return "Neutral"

    def discover_movers(self):
        """Scans extra tech giants to find 'Breakout' stocks not in core list"""
        print(" Scanning for market breakouts...")
        scout_list = ["AMD", "META", "GOOGL", "AMZN", "NFLX", "AVGO", "ORCL", "CRM"]
        
        for ticker in scout_list:
            try:
                stock = yf.Ticker(ticker)
                hist = stock.history(period="2d")
                if len(hist) < 2: continue
                
                prev_close = hist['Close'].iloc[-2]
                curr_close = hist['Close'].iloc[-1]
                pct_change = ((curr_close - prev_close) / prev_close) * 100
                
                # If a scouted stock is up > 2%, add it to today's analysis
                if pct_change > 2.0 and ticker not in self.active_list:
                    print(f" Discovery: {ticker} is surging (+{pct_change:.2f}%)")
                    self.active_list.append(ticker)
            except: continue

    def run_analysis(self):
        self.discover_movers()
        print(f" Analyzing {len(self.active_list)} stocks...")
        
        for ticker in self.active_list:
            try:
                # 1. Price
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
                avg_sent = sum([self.get_sentiment(h) for h in headlines]) / len(headlines) if headlines else 0

                self.report_data.append({
                    "Ticker": ticker,
                    "Price": f"${price:.2f}",
                    "Trend": self.get_trend_icon(avg_sent),
                    "Score": avg_sent,
                    "Alerts": len(headlines)
                })
                print(f" {ticker} processed.")
            except Exception as e:
                print(f" Error on {ticker}: {e}")

    def send_report(self):
        if not self.report_data: return
        
        df = pd.DataFrame(self.report_data)
        # Sort by Sentiment Score so you see the most important news first
        df = df.sort_values(by="Score", ascending=False)
        
        body = f"Daily Market Intelligence Report\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n{df.to_string(index=False)}"
        msg = MIMEText(body)
        msg['Subject'] = f" Market Intelligence: {datetime.now().strftime('%Y-%m-%d')}"
        msg['From'] = SENDER_EMAIL
        msg['To'] = SENDER_EMAIL

        try:
            with smtplib.SMTP('smtp.gmail.com', 587) as server:
                server.starttls()
                server.login(SENDER_EMAIL, SENDER_PASS)
                server.send_message(msg)
            print("📧 Report sent successfully!")
        except Exception as e:
            print(f" Email failed: {e}")

if __name__ == "__main__":
    agent = MarketAgent()
    agent.run_analysis()
    agent.send_report()
