import streamlit as st
import pandas as pd
import numpy as np
import json

st.set_page_config(layout="wide", page_title="ETF轮动策略回测系统")

st.title("ETF轮动策略回测系统")

strategy = st.sidebar.selectbox("选择策略", ["全品类DIFv轮动", "五斗米动量轮动", "定投+轮动组合", "RSRS动量轮动", "LOGBIAS轮动", "标准化动量轮动"])

col1, col2, col3, col4 = st.columns(4)
with col1:
    start_date = st.date_input("开始日期", value=pd.to_datetime("2020-03-12"))
with col2:
    initial_capital = st.number_input("初始资金", value=1000000)
with col3:
    max_holdings = st.number_input("最大持仓数", value=5, min_value=1)
with col4:
    position_pct = st.number_input("单只仓位(%)", value=20, min_value=1)

if st.button("🚀 开始回测", type="primary"):
    try:
        from app import run_difv_backtest_api, run_wdm_backtest_api, run_combo_backtest_api, run_rsrs_backtest_api, run_logbias_backtest_api, run_std_momentum_backtest_api
        
        params = {
            'start_date': str(start_date),
            'initial_capital': initial_capital,
            'max_holdings': max_holdings,
            'position_pct': position_pct,
            'rebalance_days': 2,
            'buy_difv_max': 120,
            'sell_rank_gt': 6,
            'sell_daily_drop': 3,
            'sell_return_20': 25,
            'ma_close_gt_ma20': True,
            'ma_close_gt_ma5': True,
            'ma_ma10_gt_ma20': True,
            'ma_ma5_gt_ma10': True,
        }
        
        with st.spinner("正在运行回测..."):
            if strategy == "全品类DIFv轮动":
                result = run_difv_backtest_api(params)
            elif strategy == "五斗米动量轮动":
                result = run_wdm_backtest_api(params)
            elif strategy == "定投+轮动组合":
                result = run_combo_backtest_api(params)
            elif strategy == "RSRS动量轮动":
                result = run_rsrs_backtest_api(params)
            elif strategy == "LOGBIAS轮动":
                result = run_logbias_backtest_api(params)
            elif strategy == "标准化动量轮动":
                result = run_std_momentum_backtest_api(params)
        
        if 'error' in result:
            st.error(f"回测失败: {result['error']}")
        else:
            perf = result.get('performance', {})
            st.subheader("📊 回测结果")
            
            col1, col2, col3, col4, col5 = st.columns(5)
            with col1:
                st.metric("总收益率", f"{perf.get('total_return', 0):.2%}")
            with col2:
                st.metric("年化收益", f"{perf.get('annual_return', 0):.2%}")
            with col3:
                st.metric("最大回撤", f"{perf.get('max_drawdown', 0):.2%}")
            with col4:
                st.metric("夏普比率", f"{perf.get('sharpe_ratio', 0):.2f}")
            with col5:
                st.metric("胜率", f"{perf.get('win_rate', 0):.2%}")
            
            st.subheader("📈 净值曲线")
            nav_data = result.get('nav_curve', [])
            if nav_data:
                nav_df = pd.DataFrame(nav_data)
                nav_df['date'] = pd.to_datetime(nav_df['date'])
                st.line_chart(nav_df.set_index('date')[['nav', 'benchmark']])
            
            st.subheader("📋 年度收益")
            yearly = result.get('yearly_returns', [])
            if yearly:
                yearly_df = pd.DataFrame(yearly)
                st.dataframe(yearly_df)
            
            st.subheader("📉 交易记录")
            trades = result.get('trades', [])
            if trades:
                trade_df = pd.DataFrame(trades)
                st.dataframe(trade_df)
            
            st.subheader("🏆 当前排名")
            rankings = result.get('rankings', [])
            if rankings:
                rank_df = pd.DataFrame(rankings)
                st.dataframe(rank_df)
            
            st.subheader("💰 当前持仓")
            holdings = result.get('holdings', [])
            if holdings:
                hold_df = pd.DataFrame(holdings)
                st.dataframe(hold_df)
                
    except Exception as e:
        import traceback
        st.error(f"回测失败: {e}")
        st.code(traceback.format_exc())
