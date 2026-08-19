"""
Technical Analysis Indicators
==============================
All indicators used for trade signal generation.
"""
import numpy as np
import pandas as pd
from typing import Tuple
from config import config


class Indicators:
    """Calculate technical indicators for trading signals"""

    @staticmethod
    def rsi(df: pd.DataFrame, period: int = None) -> pd.Series:
        """Relative Strength Index"""
        period = period or config.indicators.rsi_period
        delta = df["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    @staticmethod
    def ema(series: pd.Series, period: int) -> pd.Series:
        """Exponential Moving Average"""
        return series.ewm(span=period, adjust=False).mean()

    @staticmethod
    def sma(series: pd.Series, period: int) -> pd.Series:
        """Simple Moving Average"""
        return series.rolling(window=period).mean()

    @staticmethod
    def macd(df: pd.DataFrame) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """MACD indicator"""
        ema_fast = Indicators.ema(df["close"], config.indicators.ema_fast)
        ema_slow = Indicators.ema(df["close"], config.indicators.ema_slow)
        macd_line = ema_fast - ema_slow
        signal_line = Indicators.ema(macd_line, config.indicators.macd_signal)
        histogram = macd_line - signal_line
        return macd_line, signal_line, histogram

    @staticmethod
    def bollinger_bands(df: pd.DataFrame) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """Bollinger Bands"""
        middle = Indicators.sma(df["close"], config.indicators.bb_period)
        std = df["close"].rolling(window=config.indicators.bb_period).std()
        upper = middle + (std * config.indicators.bb_std)
        lower = middle - (std * config.indicators.bb_std)
        return upper, middle, lower

    @staticmethod
    def atr(df: pd.DataFrame, period: int = None) -> pd.Series:
        """Average True Range"""
        period = period or config.indicators.atr_period
        high_low = df["high"] - df["low"]
        high_close = np.abs(df["high"] - df["close"].shift())
        low_close = np.abs(df["low"] - df["close"].shift())
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        return true_range.rolling(window=period).mean()

    @staticmethod
    def adx(df: pd.DataFrame, period: int = None) -> pd.Series:
        """Average Directional Index"""
        period = period or config.indicators.adx_period
        plus_dm = df["high"].diff()
        minus_dm = -df["low"].diff()
        plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
        minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)

        atr_val = Indicators.atr(df, period)
        plus_di = 100 * (plus_dm.rolling(window=period).mean() / atr_val)
        minus_di = 100 * (minus_dm.rolling(window=period).mean() / atr_val)
        dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di)
        return dx.rolling(window=period).mean()

    @staticmethod
    def stochastic(df: pd.DataFrame, k_period: int = 14, d_period: int = 3) -> Tuple[pd.Series, pd.Series]:
        """Stochastic Oscillator"""
        low_min = df["low"].rolling(window=k_period).min()
        high_max = df["high"].rolling(window=k_period).max()
        k = 100 * (df["close"] - low_min) / (high_max - low_min)
        d = k.rolling(window=d_period).mean()
        return k, d

    @staticmethod
    def obv(df: pd.DataFrame) -> pd.Series:
        """On-Balance Volume"""
        obv = pd.Series(0.0, index=df.index)
        for i in range(1, len(df)):
            if df["close"].iloc[i] > df["close"].iloc[i - 1]:
                obv.iloc[i] = obv.iloc[i - 1] + df["volume"].iloc[i]
            elif df["close"].iloc[i] < df["close"].iloc[i - 1]:
                obv.iloc[i] = obv.iloc[i - 1] - df["volume"].iloc[i]
            else:
                obv.iloc[i] = obv.iloc[i - 1]
        return obv

    @staticmethod
    def supertrend(df: pd.DataFrame, period: int = 10, multiplier: float = 3.0) -> pd.Series:
        """Supertrend indicator"""
        atr_val = Indicators.atr(df, period)
        hl2 = (df["high"] + df["low"]) / 2
        upper_band = hl2 + (multiplier * atr_val)
        lower_band = hl2 - (multiplier * atr_val)

        supertrend = pd.Series(index=df.index, dtype=float)
        direction = pd.Series(index=df.index, dtype=float)

        supertrend.iloc[0] = upper_band.iloc[0]
        direction.iloc[0] = 1

        for i in range(1, len(df)):
            if df["close"].iloc[i] > upper_band.iloc[i - 1]:
                direction.iloc[i] = 1
            elif df["close"].iloc[i] < lower_band.iloc[i - 1]:
                direction.iloc[i] = -1
            else:
                direction.iloc[i] = direction.iloc[i - 1]

            if direction.iloc[i] == 1:
                supertrend.iloc[i] = lower_band.iloc[i]
            else:
                supertrend.iloc[i] = upper_band.iloc[i]

        return supertrend, direction

    @staticmethod
    def calculate_all(df: pd.DataFrame) -> pd.DataFrame:
        """Calculate all indicators and add to dataframe"""
        df = df.copy()

        df["rsi"] = Indicators.rsi(df)
        df["ema_fast"] = Indicators.ema(df["close"], config.indicators.ema_fast)
        df["ema_slow"] = Indicators.ema(df["close"], config.indicators.ema_slow)
        df["macd"], df["macd_signal"], df["macd_hist"] = Indicators.macd(df)
        df["bb_upper"], df["bb_middle"], df["bb_lower"] = Indicators.bollinger_bands(df)
        df["atr"] = Indicators.atr(df)
        df["adx"] = Indicators.adx(df)
        df["stoch_k"], df["stoch_d"] = Indicators.stochastic(df)
        df["obv"] = Indicators.obv(df)
        df["supertrend"], df["supertrend_dir"] = Indicators.supertrend(df)

        # Derived signals
        df["rsi_signal"] = 0
        df.loc[df["rsi"] < config.indicators.rsi_oversold, "rsi_signal"] = 1
        df.loc[df["rsi"] > config.indicators.rsi_overbought, "rsi_signal"] = -1

        df["macd_signal_val"] = 0
        df.loc[df["macd"] > df["macd_signal"], "macd_signal_val"] = 1
        df.loc[df["macd"] < df["macd_signal"], "macd_signal_val"] = -1

        df["bb_signal"] = 0
        df.loc[df["close"] < df["bb_lower"], "bb_signal"] = 1
        df.loc[df["close"] > df["bb_upper"], "bb_signal"] = -1

        df["trend_strength"] = np.abs(df["ema_fast"] - df["ema_slow"]) / df["close"]

        return df
