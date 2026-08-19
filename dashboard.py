"""
AI Trading Bot - Web Dashboard
===============================
Streamlit-based dashboard for users to manage their bots.
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import time

from database import init_db, UserModel, TradeModel
from auth import auth
from config import config
from data_fetcher import DataFetcher
from signals import SignalGenerator
from risk_manager import RiskManager
from backtester import Backtester

# Initialize database
init_db()

# Page config
st.set_page_config(
    page_title="AI Trading Bot",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if "user" not in st.session_state:
    st.session_state.user = None
if "token" not in st.session_state:
    st.session_state.token = None


def login_page():
    """Login/Register page"""
    st.title("📈 AI Trading Bot")
    st.subheader("Login or Create Account")

    tab1, tab2 = st.tabs(["Login", "Register"])

    with tab1:
        with st.form("login_form"):
            username = st.text_input("Username or Email")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Login")

            if submit:
                result = auth.login(username, password)
                if "error" in result:
                    st.error(result["error"])
                else:
                    st.session_state.user = result["user"]
                    st.session_state.token = result["token"]
                    st.rerun()

    with tab2:
        with st.form("register_form"):
            new_username = st.text_input("Username", key="reg_user")
            new_email = st.text_input("Email", key="reg_email")
            new_password = st.text_input("Password", type="password", key="reg_pass")
            confirm_password = st.text_input("Confirm Password", type="password", key="reg_confirm")
            submit_reg = st.form_submit_button("Create Account")

            if submit_reg:
                if new_password != confirm_password:
                    st.error("Passwords don't match")
                elif len(new_password) < 6:
                    st.error("Password must be at least 6 characters")
                else:
                    result = auth.register(new_username, new_email, new_password)
                    if "error" in result:
                        st.error(result["error"])
                    else:
                        st.session_state.user = result["user"]
                        st.session_state.token = result["token"]
                        st.success("Account created!")
                        st.rerun()


def dashboard():
    """Main dashboard"""
    user = st.session_state.user

    # Sidebar
    with st.sidebar:
        st.title("🤖 AI Trading Bot")
        st.write(f"Welcome, **{user['username']}**")
        st.write(f"Plan: **{user.get('tier', 'free').upper()}**")

        if st.button("Logout"):
            st.session_state.user = None
            st.session_state.token = None
            st.rerun()

        st.divider()

        # Navigation
        page = st.radio(
            "Navigation",
            ["Dashboard", "Signals", "Trade History", "Backtest", "Settings"]
        )

    # Main content
    if page == "Dashboard":
        show_dashboard(user)
    elif page == "Signals":
        show_signals(user)
    elif page == "Trade History":
        show_trade_history(user)
    elif page == "Backtest":
        show_backtest(user)
    elif page == "Settings":
        show_settings(user)


def show_dashboard(user):
    """Show main dashboard"""
    st.title("📊 Dashboard")

    stats = TradeModel.get_user_stats(user["id"])

    # Metrics row
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Trades", stats.get("total_trades", 0))
    with col2:
        st.metric("Win Rate", f"{stats.get('win_rate', 0):.1f}%")
    with col3:
        st.metric("Total PnL", f"${stats.get('total_pnl', 0):,.2f}")
    with col4:
        st.metric("Avg Trade", f"${stats.get('avg_pnl', 0):,.2f}")

    st.divider()

    # Recent trades
    st.subheader("Recent Trades")
    trades = TradeModel.get_user_trades(user["id"], limit=10)

    if trades:
        df = pd.DataFrame(trades)
        st.dataframe(
            df[["symbol", "direction", "entry_price", "exit_price", "pnl", "status", "opened_at"]],
            use_container_width=True
        )
    else:
        st.info("No trades yet. Start by analyzing signals!")

    # Quick action
    st.divider()
    st.subheader("Quick Trade")

    col1, col2 = st.columns(2)
    with col1:
        symbol = st.selectbox("Symbol", config.trading.pairs)
    with col2:
        timeframe = st.selectbox("Timeframe", ["1h", "4h", "1d"])

    if st.button("Analyze & Trade", type="primary"):
        with st.spinner("Analyzing..."):
            fetcher = DataFetcher()
            rm = RiskManager(config.initial_capital)
            sg = SignalGenerator(rm)

            df = fetcher.fetch_klines(symbol, timeframe)
            signal = sg.analyze(df, symbol)

            if signal:
                direction_color = "green" if signal.direction == "long" else "red"
                st.success(f"**{signal.direction.upper()} signal found!**")
                st.write(f"- Entry: ${signal.entry_price:,.2f}")
                st.write(f"- Stop Loss: ${signal.stop_loss:,.2f}")
                st.write(f"- Take Profit: ${signal.take_profit:,.2f}")
                st.write(f"- Confidence: {signal.confidence:.1%}")

                st.write("**Reasons:**")
                for reason in signal.reasons:
                    st.write(f"  - {reason}")
            else:
                st.warning("No clear signal found")


def show_signals(user):
    """Show live signals"""
    st.title("📡 Live Signals")

    if st.button("Refresh Signals"):
        st.rerun()

    fetcher = DataFetcher()
    rm = RiskManager(config.initial_capital)
    sg = SignalGenerator(rm)

    progress = st.progress(0)
    status = st.empty()

    signals = []

    for i, symbol in enumerate(config.trading.pairs):
        progress.progress((i + 1) / len(config.trading.pairs))
        status.text(f"Analyzing {symbol}...")

        df = fetcher.fetch_klines(symbol)
        signal = sg.analyze(df, symbol)

        if signal:
            signals.append(signal)

    progress.empty()
    status.empty()

    if signals:
        st.success(f"Found {len(signals)} signals!")

        for signal in signals:
            with st.expander(f"{'🟢' if signal.direction == 'long' else '🔴'} {signal.symbol} - {signal.direction.upper()}"):
                col1, col2 = st.columns(2)

                with col1:
                    st.write(f"**Entry:** ${signal.entry_price:,.2f}")
                    st.write(f"**Stop Loss:** ${signal.stop_loss:,.2f}")
                    st.write(f"**Take Profit:** ${signal.take_profit:,.2f}")

                with col2:
                    st.write(f"**Confidence:** {signal.confidence:.1%}")
                    st.write(f"**Risk/Reward:** 1:{abs(signal.take_profit - signal.entry_price) / abs(signal.entry_price - signal.stop_loss):.1f}")

                st.write("**Reasons:**")
                for reason in signal.reasons:
                    st.write(f"  - {reason}")
    else:
        st.info("No signals found at this time")


def show_trade_history(user):
    """Show trade history"""
    st.title("📜 Trade History")

    trades = TradeModel.get_user_trades(user["id"], limit=100)

    if trades:
        df = pd.DataFrame(trades)

        # Filter
        col1, col2, col3 = st.columns(3)
        with col1:
            status_filter = st.selectbox("Status", ["All", "Open", "Closed"])
        with col2:
            symbol_filter = st.selectbox("Symbol", ["All"] + df["symbol"].unique().tolist())
        with col3:
            direction_filter = st.selectbox("Direction", ["All", "Long", "Short"])

        # Apply filters
        if status_filter != "All":
            df = df[df["status"] == status_filter.lower()]
        if symbol_filter != "All":
            df = df[df["symbol"] == symbol_filter]
        if direction_filter != "All":
            df = df[df["direction"] == direction_filter.lower()]

        st.dataframe(df, use_container_width=True)

        # PnL chart
        if "pnl" in df.columns:
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=df.index,
                y=df["pnl"],
                marker_color=["green" if p > 0 else "red" for p in df["pnl"]]
            ))
            fig.update_layout(title="Trade PnL", xaxis_title="Trade", yaxis_title="PnL ($)")
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No trades yet")


def show_backtest(user):
    """Show backtest results"""
    st.title("🧪 Backtest")

    col1, col2 = st.columns(2)
    with col1:
        symbol = st.selectbox("Symbol", config.trading.pairs, key="bt_symbol")
    with col2:
        days = st.slider("Days of History", 30, 365, 180)

    if st.button("Run Backtest", type="primary"):
        with st.spinner("Running backtest..."):
            bt = Backtester()
            fetcher = DataFetcher()

            limit = days * 24  # Assuming 1h candles
            df = fetcher.fetch_klines(symbol, limit=min(limit, 1000))
            results = bt.run(df)

        st.success("Backtest complete!")

        # Metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Return", f"{results['total_return']:+.2f}%")
        with col2:
            st.metric("Win Rate", f"{results['win_rate']:.1f}%")
        with col3:
            st.metric("Max Drawdown", f"{results['max_drawdown']:.1f}%")
        with col4:
            st.metric("Sharpe Ratio", f"{results['sharpe_ratio']:.2f}")

        # Equity curve
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            y=results["equity_curve"],
            mode="lines",
            name="Equity",
            line=dict(color="blue", width=2)
        ))
        fig.update_layout(
            title=f"Equity Curve - {symbol}",
            xaxis_title="Period",
            yaxis_title="Capital ($)"
        )
        st.plotly_chart(fig, use_container_width=True)

        # Trade details
        if results["trades"]:
            st.subheader("Trade Details")
            trades_df = pd.DataFrame(results["trades"])
            st.dataframe(trades_df, use_container_width=True)


def show_settings(user):
    """Show settings page"""
    st.title("⚙️ Settings")

    tab1, tab2, tab3 = st.tabs(["Exchange API", "Bot Config", "Account"])

    with tab1:
        st.subheader("Exchange API Keys")
        st.write("Connect your Binance account to enable live trading.")

        api_key = st.text_input("API Key", type="password")
        api_secret = st.text_input("API Secret", type="password")

        if st.button("Save API Keys"):
            if api_key and api_secret:
                UserModel.update_api_keys(user["id"], api_key, api_secret)
                st.success("API keys saved!")
            else:
                st.error("Please enter both keys")

    with tab2:
        st.subheader("Bot Configuration")

        pairs = st.text_area(
            "Trading Pairs (one per line)",
            value="\n".join(config.trading.pairs)
        )

        timeframe = st.selectbox("Timeframe", ["1m", "5m", "15m", "1h", "4h", "1d"],
                                index=3)

        risk_per_trade = st.slider("Risk per Trade (%)", 0.5, 5.0, 2.0)

        if st.button("Save Config"):
            st.success("Configuration saved!")

    with tab3:
        st.subheader("Account")

        st.write(f"**Username:** {user['username']}")
        st.write(f"**Email:** {user.get('email', 'N/A')}")
        st.write(f"**Plan:** {user.get('tier', 'free').upper()}")

        st.divider()
        st.subheader("Upgrade Plan")

        col1, col2, col3 = st.columns(3)
        with col1:
            st.write("**Free**")
            st.write("- 3 trades/day")
            st.write("- Basic indicators")
            st.write("- Paper trading only")
        with col2:
            st.write("**Pro - $29/mo**")
            st.write("- Unlimited trades")
            st.write("- All indicators")
            st.write("- ML predictions")
            st.write("- Live trading")
        with col3:
            st.write("**VIP - $99/mo**")
            st.write("- Everything in Pro")
            st.write("- Priority signals")
            st.write("- Custom strategies")
            st.write("- API access")


# Run app
if st.session_state.user:
    dashboard()
else:
    login_page()
