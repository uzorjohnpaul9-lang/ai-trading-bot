"""
ML Prediction Module
====================
Uses scikit-learn for price direction prediction with enhanced features.
"""
import numpy as np
import pandas as pd
from sklearn.ensemble import (
    RandomForestClassifier,
    GradientBoostingClassifier,
    AdaBoostClassifier,
    ExtraTreesClassifier,
    VotingClassifier
)
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score
from typing import Tuple, Optional
from config import config


class MLPredictor:
    """Machine learning predictor for price direction"""

    def __init__(self):
        self.scaler = StandardScaler()
        self.feature_selector = None
        self.trained = False
        self.accuracy = 0.0
        self.feature_names = []

        # Individual models
        self.rf_model = RandomForestClassifier(
            n_estimators=150,
            max_depth=12,
            min_samples_split=5,
            min_samples_leaf=2,
            random_state=42,
            n_jobs=-1
        )
        self.gb_model = GradientBoostingClassifier(
            n_estimators=120,
            max_depth=6,
            learning_rate=0.1,
            subsample=0.8,
            random_state=42
        )
        self.et_model = ExtraTreesClassifier(
            n_estimators=100,
            max_depth=10,
            random_state=42,
            n_jobs=-1
        )
        self.lr_model = LogisticRegression(
            max_iter=1000,
            random_state=42
        )

    def _prepare_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Extract enhanced features for ML model"""
        features = pd.DataFrame(index=df.index)

        # === Price-based features ===
        features["price_change_1"] = df["close"].pct_change(1)
        features["price_change_3"] = df["close"].pct_change(3)
        features["price_change_5"] = df["close"].pct_change(5)
        features["price_change_10"] = df["close"].pct_change(10)

        # === Volatility features ===
        features["volatility_5"] = df["close"].pct_change().rolling(5).std()
        features["volatility_10"] = df["close"].pct_change().rolling(10).std()
        features["volatility_20"] = df["close"].pct_change().rolling(20).std()
        features["atr_pct"] = df.get("atr", pd.Series(0, index=df.index)) / df["close"]

        # === Trend features ===
        features["ema_fast"] = df.get("ema_fast", df["close"].ewm(span=12).mean())
        features["ema_slow"] = df.get("ema_slow", df["close"].ewm(span=26).mean())
        features["trend_strength"] = (features["ema_fast"] - features["ema_slow"]) / features["ema_slow"]
        features["trend_direction"] = np.sign(features["trend_strength"])

        # === Momentum features ===
        features["rsi"] = df.get("rsi", 50)
        features["rsi_diff"] = features["rsi"] - 50
        features["stoch_k"] = df.get("stoch_k", 50)
        features["stoch_d"] = df.get("stoch_d", 50)
        features["stoch_diff"] = features["stoch_k"] - features["stoch_d"]

        # === MACD features ===
        features["macd"] = df.get("macd", 0)
        features["macd_signal"] = df.get("macd_signal", 0)
        features["macd_hist"] = df.get("macd_hist", 0)
        features["macd_divergence"] = features["macd"] - features["macd_signal"]
        features["macd_hist_change"] = features["macd_hist"].diff()

        # === Bollinger Band features ===
        bb_upper = df.get("bb_upper", df["close"])
        bb_lower = df.get("bb_lower", df["close"])
        bb_middle = df.get("bb_middle", df["close"])
        bb_width = bb_upper - bb_lower
        features["bb_position"] = (df["close"] - bb_lower) / bb_width.replace(0, np.nan)
        features["bb_width_pct"] = bb_width / bb_middle
        features["bb_signal"] = df.get("bb_signal", 0)

        # === Volume features ===
        features["volume"] = df["volume"]
        features["volume_change"] = df["volume"].pct_change()
        features["volume_sma_ratio"] = df["volume"] / df["volume"].rolling(20).mean()
        features["price_volume_corr"] = df["close"].rolling(20).corr(df["volume"])

        # === Support/Resistance features ===
        features["high_20"] = df["high"].rolling(20).max()
        features["low_20"] = df["low"].rolling(20).min()
        features["price_to_high"] = (df["close"] - features["low_20"]) / (features["high_20"] - features["low_20"]).replace(0, np.nan)
        features["range_position"] = (df["close"] - features["low_20"]) / (features["high_20"] - features["low_20"]).replace(0, np.nan)

        # === Candle patterns ===
        features["body_size"] = abs(df["close"] - df["open"]) / df["close"]
        features["upper_shadow"] = (df["high"] - df[["close", "open"]].max(axis=1)) / df["close"]
        features["lower_shadow"] = (df[["close", "open"]].min(axis=1) - df["low"]) / df["close"]
        features["is_bullish"] = (df["close"] > df["open"]).astype(int)

        # === Supertrend ===
        features["supertrend_dir"] = df.get("supertrend_dir", 0)

        # === ADX ===
        features["adx"] = df.get("adx", 0)
        features["adx_strong"] = (features["adx"] > 25).astype(int)

        # === Derived features ===
        features["returns_1h"] = df["close"].pct_change(1)
        features["returns_4h"] = df["close"].pct_change(4)
        features["returns_12h"] = df["close"].pct_change(12)
        features["momentum_5"] = df["close"] / df["close"].shift(5) - 1
        features["momentum_10"] = df["close"] / df["close"].shift(10) - 1

        # Drop NaN
        features = features.replace([np.inf, -np.inf], np.nan)
        features = features.dropna()

        self.feature_names = features.columns.tolist()
        return features

    def _prepare_labels(self, df: pd.DataFrame, lookahead: int = 5) -> pd.Series:
        """Create labels: 1 if price goes up, 0 if down"""
        future_returns = df["close"].shift(-lookahead) / df["close"] - 1
        labels = (future_returns > 0).astype(int)
        return labels

    def _select_features(self, X_train, y_train, X_test):
        """Simple feature selection based on importance"""
        # Use Random Forest for feature importance
        selector = RandomForestClassifier(n_estimators=50, max_depth=8, random_state=42)
        selector.fit(X_train, y_train)

        importances = selector.feature_importances_
        threshold = np.percentile(importances, 30)  # Keep top 70% features

        mask = importances >= threshold
        self.feature_mask = mask

        return X_train[:, mask], X_test[:, mask]

    def train(self, df: pd.DataFrame) -> float:
        """Train the ML models with enhanced approach"""
        features = self._prepare_features(df)
        labels = self._prepare_labels(df)

        # Align indices
        common_idx = features.index.intersection(labels.index)
        features = features.loc[common_idx]
        labels = labels.loc[common_idx]

        if len(features) < 100:
            return 0.0

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            features, labels,
            test_size=1 - config.ml.train_split,
            shuffle=False
        )

        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)

        # Feature selection
        X_train_selected, X_test_selected = self._select_features(
            X_train_scaled, y_train, X_test_scaled
        )

        # Train models
        self.rf_model.fit(X_train_selected, y_train)
        self.gb_model.fit(X_train_selected, y_train)
        self.et_model.fit(X_train_selected, y_train)
        self.lr_model.fit(X_train_selected, y_train)

        # Ensemble prediction (weighted voting)
        rf_pred = self.rf_model.predict(X_test_selected)
        gb_pred = self.gb_model.predict(X_test_selected)
        et_pred = self.et_model.predict(X_test_selected)
        lr_pred = self.lr_model.predict(X_test_selected)

        # Weighted ensemble
        ensemble_pred = (
            rf_pred * 0.3 +
            gb_pred * 0.3 +
            et_pred * 0.25 +
            lr_pred * 0.15
        )
        ensemble_pred = (ensemble_pred >= 0.5).astype(int)

        self.accuracy = accuracy_score(y_test, ensemble_pred)
        self.trained = True

        return self.accuracy

    def predict(self, df: pd.DataFrame) -> Tuple[float, float]:
        """
        Predict price direction.

        Returns:
            signal: -1 (sell), 0 (hold), 1 (buy)
            confidence: 0.0 to 1.0
        """
        if not self.trained:
            return 0, 0.0

        features = self._prepare_features(df)
        if features.empty:
            return 0, 0.0

        latest = features.iloc[[-1]]
        latest_scaled = self.scaler.transform(latest)

        # Apply feature selection
        latest_selected = latest_scaled[:, self.feature_mask]

        # Get predictions from all models
        rf_prob = self.rf_model.predict_proba(latest_selected)[0]
        gb_prob = self.gb_model.predict_proba(latest_selected)[0]
        et_prob = self.et_model.predict_proba(latest_selected)[0]
        lr_prob = self.lr_model.predict_proba(latest_selected)[0]

        # Weighted ensemble probability
        avg_prob = (
            rf_prob * 0.3 +
            gb_prob * 0.3 +
            et_prob * 0.25 +
            lr_prob * 0.15
        )

        buy_prob = avg_prob[1]
        sell_prob = avg_prob[0]
        confidence = max(buy_prob, sell_prob)

        # Generate signal with higher thresholds
        if buy_prob > 0.6 and confidence > config.ml.min_accuracy:
            signal = 1
        elif sell_prob > 0.6 and confidence > config.ml.min_accuracy:
            signal = -1
        else:
            signal = 0

        return signal, confidence

    def get_feature_importance(self) -> dict:
        """Get feature importance from models"""
        if not self.trained or not self.feature_names:
            return {}

        # Get selected feature names
        selected_names = [n for n, m in zip(self.feature_names, self.feature_mask) if m]

        rf_imp = self.rf_model.feature_importances_
        gb_imp = self.gb_model.feature_importances_
        et_imp = self.et_model.feature_importances_
        avg_imp = (rf_imp + gb_imp + et_imp) / 3

        return dict(sorted(
            zip(selected_names, avg_imp),
            key=lambda x: x[1],
            reverse=True
        ))
