from lumibot.entities import Asset
from lumibot.backtesting import CcxtBacktesting
from lumibot.strategies.strategy import Strategy
from datetime import datetime
from colorama import Fore, init
import random
from timedelta import Timedelta

# Delete Ollama, prompt templates and json
# Add in REST and finbert utils
from alpaca_trade_api import REST
from finbert_utils import estimate_sentiment

import json
import os

from dotenv import load_dotenv
load_dotenv()

# Add in Alpaca API details
API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")
BASE_URL = os.getenv("BASE_URL")

ALPACA_CREDS = {"API_KEY": API_KEY, "API_SECRET": API_SECRET, "PAPER": True}


class MLTrader(Strategy):

    def initialize(
        self, coin: str = "LTC", coin_name: str = "litecoin", cash_at_risk: float = 0.2
    ):
        self.set_market("24/7")
        self.sleeptime = "1D"
        self.last_trade = None
        self.cash_at_risk = cash_at_risk
        self.coin = coin
        self.coin_name = coin_name
        # Add in sentiment api
        self.api = REST(base_url=BASE_URL, key_id=API_KEY, secret_key=API_SECRET)

    def position_sizing(self):
        cash = self.get_cash()
        last_price = self.get_last_price(
            Asset(symbol=self.coin, asset_type=Asset.AssetType.CRYPTO),
            quote=Asset(symbol="USD", asset_type="crypto"),
        )
        if last_price == None:
            quantity = 0
        else:
            quantity = cash * self.cash_at_risk / last_price
        return cash, last_price, quantity

    def get_dates(self):
        today = self.get_datetime()
        # Increase dates
        three_days_prior = today - Timedelta(days=3)
        return today.strftime("%Y-%m-%d"), three_days_prior.strftime("%Y-%m-%d")

    def get_sentiment(self):
        today, three_days_prior = self.get_dates()
        # Change sentiment to finbert workflow
        news = self.api.get_news(
            symbol=f"{self.coin}/USD", start=three_days_prior, end=today
        )
        news = [ev.__dict__["_raw"]["headline"] for ev in news]
        probability, sentiment = estimate_sentiment(news)
        return probability, sentiment

    def on_trading_iteration(self):
        cash, last_price, quantity = self.position_sizing()
        # Remove news data, recommendation and probability
        probability, sentiment = self.get_sentiment()

        if last_price != None:
            if cash > last_price:
                # Change back to sentiment and probability
                if sentiment == "positive" and probability > 0.999:
                    if self.last_trade == "sell" or self.last_trade == None:
                        self.sell_all()
                        order = self.create_order(
                            self.coin,
                            quantity,
                            "buy",
                            type="market",
                            quote=Asset(symbol="USD", asset_type="crypto"),
                        )
                        print(Fore.LIGHTMAGENTA_EX + str(order) + Fore.RESET)
                        self.submit_order(order)
                        self.last_trade = "buy"
                elif sentiment == "negative" and probability > 0.999:
                    if self.last_trade == "buy" or self.last_trade == None:
                        self.sell_all()
                        order = self.create_order(
                            self.coin,
                            quantity,
                            "sell",
                            type="market",
                            quote=Asset(symbol="USD", asset_type="crypto"),
                        )
                        print(Fore.LIGHTMAGENTA_EX + str(order) + Fore.RESET)
                        self.submit_order(order)
                        self.last_trade = "sell"



# Charger les dates depuis un fichier de configuration
def load_config(file_path="config.json"):
    with open(file_path, "r") as f:
        config = json.load(f)
    return config


if __name__ == "__main__":
    # Charger la configuration
    config = load_config()

    # Lire les dates depuis la configuration
    start_date = datetime.strptime(config["start_date"], "%Y-%m-%d")
    end_date = datetime.strptime(config["end_date"], "%Y-%m-%d")

    exchange_id = "kraken"
    kwargs = {
        "exchange_id": exchange_id,
    }
    CcxtBacktesting.MIN_TIMESTEP = "day"
    coin = "XRP"
    coin_name = "ripple"
    results, strat_obj = MLTrader.run_backtest(
        CcxtBacktesting,
        start_date,
        end_date,
        benchmark_asset=f"{coin}/USD",
        quote_asset=Asset(symbol="USD", asset_type="crypto"),
        parameters={
            "cash_at_risk": 0.50,
            "coin": coin,
        },
        **kwargs,
    )