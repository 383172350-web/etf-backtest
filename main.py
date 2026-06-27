import os
import sys

os.environ['MPLBACKEND'] = 'Agg'

import matplotlib
matplotlib.use('Agg')

import streamlit as st
import pandas as pd
import numpy as np
import json

st.set_page_config(layout="wide", page_title="ETF轮动策略回测系统")

st.title("ETF轮动策略回测系统")

st.sidebar.header("策略配置")

strategy_list = ["全品类DIFv轮动", "五斗米动量轮动", "定投+轮动组合", "RSRS动量轮动", "LOGBIAS轮动", "标准化动量轮动"]
strategy = st.sidebar.selectbox("选择策略", strategy_list)

with st.sidebar:
    start_date = st.date_input("开始日期", value=pd.to_datetime("2020-03-12"))
    initial_capital = st.number_input("初始资金", value=1000000)
    max_holdings = st.number_input("最大持仓数", value=5, min_value=1)
    position_pct = st.number_input("单只仓位(%)", value=20, min_value=1)
    rebalance_days = st.number_input("轮动周期(天)", value=2, min_value=1)

run_btn = st.sidebar.button("开始回测", type="primary")

if run_btn:
    st.info("正在初始化...")
    
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        
        st.info("正在导入回测模块...")
        
        from engine import scan_pkl_dir, build_data_dict, calc_all_indicators, run_backtest
        from engine.performance import compute_performance, compute_yearly_returns
        
        st.info("正在加载数据...")
        items = scan_pkl_dir()
        st.info(f"找到 {len(items)} 个标的")
        
        data_dict = build_data_dict()
        st.info("数据加载完成")
        
        st.info("正在计算指标...")
        indicators_dict = calc_all_indicators(data_dict)
        st.info("指标计算完成")
        
        st.info(f"正在运行策略: {strategy}")
        
        strategy_config = {
            "全品类DIFv轮动": {"sort_field": "difv_raw", "buy_difv_max": 120, "sell_rank_gt": 6, "sell_daily_drop": 3, "sell_return_20": 25},
            "五斗米动量轮动": {"sort_field": "wdm_score", "buy_difv_max": 120, "sell_rank_gt": 6, "sell_daily_drop": 3, "sell_return_20": 25},
            "RSRS动量轮动": {"sort_field": "rsrs_score", "buy_difv_max": 120, "sell_rank_gt": 6, "sell_daily_drop": 3, "sell_return_20": 25},
            "LOGBIAS轮动": {"sort_field": "logbias", "buy_difv_max": 120, "sell_rank_gt": 6, "sell_daily_drop": 3, "sell_return_20": 25},
            "标准化动量轮动": {"sort_field": "std_momentum", "buy_difv_max": 120, "sell_rank_gt": 6, "sell_daily_drop": 3, "sell_return_20": 25},
            "定投+轮动组合": {"sort_field": "difv_raw", "buy_difv_max": 120, "sell_rank_gt": 6, "sell_daily_drop": 3, "sell_return_20": 25},
        }
        
        config = strategy_config.get(strategy, strategy_config["全品类DIFv轮动"])
        
        params = {
            'start_date': str(start_date),
            'initial_capital': initial_capital,
            'max_holdings': max_holdings,
            'position_pct': position_pct / 100,
            'rebalance_days': rebalance_days,
            'sort_field': config['sort_field'],
            'buy_difv_max': config['buy_difv_max'],
            'sell_rank_gt': config['sell_rank_gt'],
            'sell_daily_drop': config['sell_daily_drop'],
            'sell_return_20': config['sell_return_20'],
            'ma_close_gt_ma20': True,
            'ma_close_gt_ma5': True,
            'ma_ma10_gt_ma20': True,
            'ma_ma5_gt_ma10': True,
        }
        
        result = run_backtest(data_dict, indicators_dict, params)
        
        st.success("回测完成!")
        
        perf = result.get('performance', {})
        
        st.subheader("回测结果")
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
        
        nav_df = result.get('nav_df', pd.DataFrame())
        if not nav_df.empty:
            st.subheader("净值曲线")
            st.line_chart(nav_df[['nav', 'benchmark']])
        
        yearly_returns = compute_yearly_returns(nav_df)
        if yearly_returns:
            st.subheader("年度收益")
            yearly_df = pd.DataFrame(list(yearly_returns.items()), columns=['年份', '收益率'])
            st.dataframe(yearly_df)
        
        trades = result.get('trades', [])
        if trades:
            st.subheader("交易记录")
            trade_df = pd.DataFrame(trades)
            st.dataframe(trade_df)
        
        holdings = result.get('holdings', [])
        if holdings:
            st.subheader("当前持仓")
            hold_df = pd.DataFrame(holdings)
            st.dataframe(hold_df)
            
    except Exception as e:
        import traceback
        st.error(f"回测失败: {e}")
        st.code(traceback.format_exc())
