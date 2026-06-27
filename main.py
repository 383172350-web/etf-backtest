import os
import sys

os.environ['MPLBACKEND'] = 'Agg'
import matplotlib
matplotlib.use('Agg')

import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(layout="wide", page_title="ETF轮动策略回测系统")

st.title("ETF轮动策略回测系统")

st.sidebar.header("策略配置")

strategy_list = ["全品类DIFv轮动", "五斗米动量轮动", "定投+轮动组合", "RSRS动量轮动", "LOF轮动", "科技DIFv轮动"]
strategy = st.sidebar.selectbox("选择策略", strategy_list)

with st.sidebar:
    start_date = st.date_input("开始日期", value=pd.to_datetime("2020-03-12"))
    initial_capital = st.number_input("初始资金", value=1000000)
    max_holdings = st.number_input("最大持仓数", value=5, min_value=1)
    position_pct = st.number_input("单只仓位(%)", value=20, min_value=1)
    rebalance_days = st.number_input("轮动周期(天)", value=2, min_value=1)

run_btn = st.sidebar.button("开始回测", type="primary")

def get_config_summary(strategy_name, params):
    config = {
        "全品类DIFv轮动": {
            "股票池": "13只（创业板50, 有色ETF, 能源化工, 豆粕ETF, 沪深300, 科创50, 医疗ETF, 军工ETF, 券商ETF, 半导体, 新能源车, 光伏产业, 恒生科技）",
            "排序": "DIF指标 降序",
            "买入": f"close > ma20 AND close > ma5 AND ma10 > ma20 AND ma5 > ma10",
            "卖出": f"rank>{params['sell_rank_gt']} OR 日跌幅>{params['sell_daily_drop']}% OR 20日涨幅>{params['sell_return_20']}%",
            "持仓": f"等权{params['max_holdings']}只, {params['position_pct']}%比例, {params['rebalance_days']}日轮动"
        },
        "五斗米动量轮动": {
            "股票池": "5只（创业板50, 沪深300, 科创50, 医疗ETF, 半导体）",
            "排序": "五斗米动量 降序",
            "买入": "动量得分 > 阈值",
            "卖出": "动量得分 < 阈值 OR 排名靠后",
            "持仓": f"等权{params['max_holdings']}只, {params['position_pct']}%比例, {params['rebalance_days']}日轮动"
        },
        "定投+轮动组合": {
            "股票池": "13只（创业板50, 有色ETF, 能源化工, 豆粕ETF, 沪深300, 科创50, 医疗ETF, 军工ETF, 券商ETF, 半导体, 新能源车, 光伏产业, 恒生科技）",
            "排序": "DIF指标 降序",
            "买入": "定投+轮动双模式",
            "卖出": f"rank>{params['sell_rank_gt']} OR 日跌幅>{params['sell_daily_drop']}%",
            "持仓": f"等权{params['max_holdings']}只, {params['position_pct']}%比例, {params['rebalance_days']}日轮动"
        },
        "RSRS动量轮动": {
            "股票池": "5只（创业板50, 沪深300, 科创50, 医疗ETF, 半导体）",
            "排序": "RSRS强度 降序",
            "买入": "RSRS强度 > 阈值 AND 均线多头",
            "卖出": "RSRS强度 < 阈值 OR 止损",
            "持仓": f"等权{params['max_holdings']}只, {params['position_pct']}%比例, {params['rebalance_days']}日轮动"
        },
        "LOF轮动": {
            "股票池": "LOF标的池",
            "排序": "LOGBIAS指标 降序",
            "买入": "LOGBIAS > 阈值",
            "卖出": "LOGBIAS < 阈值 OR 排名靠后",
            "持仓": f"等权{params['max_holdings']}只, {params['position_pct']}%比例, {params['rebalance_days']}日轮动"
        },
        "科技DIFv轮动": {
            "股票池": "科技类ETF（半导体, 新能源车, 光伏产业, 科创50等）",
            "排序": "DIF指标 降序",
            "买入": f"close > ma20 AND close > ma5 AND ma10 > ma20",
            "卖出": f"rank>{params['sell_rank_gt']} OR 日跌幅>{params['sell_daily_drop']}%",
            "持仓": f"等权{params['max_holdings']}只, {params['position_pct']}%比例, {params['rebalance_days']}日轮动"
        }
    }
    return config.get(strategy_name, {})

if run_btn:
    st.info("正在初始化...")
    
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        
        st.info("正在导入回测模块...")
        
        from app import (
            app, run_difv_backtest_api, run_wdm_backtest_api, 
            run_combo_backtest_api, run_rsrs_backtest_api,
            run_lof_backtest_api, run_tech_difv_backtest_api
        )
        
        st.info("正在构建参数...")
        
        params = {
            'start_date': str(start_date),
            'initial_capital': initial_capital,
            'max_holdings': max_holdings,
            'position_pct': position_pct,
            'rebalance_days': rebalance_days,
            'buy_difv_max': 120,
            'sell_rank_gt': 6,
            'sell_daily_drop': 3,
            'sell_return_20': 25,
            'ma_close_gt_ma20': True,
            'ma_close_gt_ma5': True,
            'ma_ma10_gt_ma20': True,
            'ma_ma5_gt_ma10': True,
        }
        
        st.info(f"正在运行策略: {strategy}")
        
        with app.app_context():
            if strategy == "全品类DIFv轮动":
                result = run_difv_backtest_api(params)
            elif strategy == "五斗米动量轮动":
                result = run_wdm_backtest_api(params)
            elif strategy == "定投+轮动组合":
                result = run_combo_backtest_api(params)
            elif strategy == "RSRS动量轮动":
                result = run_rsrs_backtest_api(params)
            elif strategy == "LOF轮动":
                result = run_lof_backtest_api(params)
            elif strategy == "科技DIFv轮动":
                result = run_tech_difv_backtest_api(params)
        
        if hasattr(result, 'get_json'):
            result = result.get_json()
        
        if 'error' in result:
            st.error(f"回测失败: {result['error']}")
        else:
            st.success("回测完成!")
            
            config_summary = get_config_summary(strategy, params)
            
            with st.expander("📋 当前配置概要"):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"- **股票池**: {config_summary.get('股票池', '')}")
                    st.write(f"- **排序**: {config_summary.get('排序', '')}")
                with col2:
                    st.write(f"- **买入**: {config_summary.get('买入', '')}")
                    st.write(f"- **卖出**: {config_summary.get('卖出', '')}")
                st.write(f"- **持仓**: {config_summary.get('持仓', '')}")
                st.write(f"- **开始日期**: {params['start_date']}")
                st.write(f"- **初始资金**: {params['initial_capital']:,} 元")
            
            perf = result.get('performance', {})
            
            st.subheader("回测结果")
            col1, col2, col3, col4, col5 = st.columns(5)
            with col1:
                st.metric("总收益率", f"{perf.get('total_return', 0):.2f}%")
            with col2:
                st.metric("年化收益", f"{perf.get('annual_return', 0):.2f}%")
            with col3:
                st.metric("最大回撤", f"{perf.get('max_dd', 0):.2f}%")
            with col4:
                st.metric("夏普比率", f"{perf.get('sharpe', 0):.2f}")
            with col5:
                st.metric("胜率", f"{perf.get('win_rate', 0):.2f}%")
            
            nav_data = result.get('nav_curve', [])
            benchmark_data = result.get('benchmark', [])
            if nav_data:
                st.subheader("净值曲线")
                nav_df = pd.DataFrame(nav_data)
                nav_df['date'] = pd.to_datetime(nav_df['date'])
                nav_df = nav_df.rename(columns={'nav': '策略净值'})
                
                if benchmark_data:
                    bm_df = pd.DataFrame(benchmark_data)
                    bm_df['date'] = pd.to_datetime(bm_df['date'])
                    bm_df = bm_df.rename(columns={'nav': '基准净值'})
                    nav_df = pd.merge(nav_df, bm_df, on='date', how='outer')
                
                st.line_chart(nav_df.set_index('date'))
            
            drawdown = result.get('drawdown', [])
            if drawdown:
                st.subheader("回撤曲线")
                dd_df = pd.DataFrame(drawdown)
                dd_df['date'] = pd.to_datetime(dd_df['date'])
                st.line_chart(dd_df.set_index('date')[['dd']])
            
            yearly = result.get('yearly_returns', [])
            if yearly:
                st.subheader("年度收益")
                st.dataframe(pd.DataFrame(yearly))
            
            trades = result.get('trades', [])
            if trades:
                st.subheader("交易记录")
                st.dataframe(pd.DataFrame(trades))
            
            rankings = result.get('rankings', [])
            if rankings:
                st.subheader("当前排名")
                st.dataframe(pd.DataFrame(rankings))
            
            holdings = result.get('current_holdings', [])
            if holdings:
                st.subheader("当前持仓")
                st.dataframe(pd.DataFrame(holdings))
                
    except Exception as e:
        import traceback
        st.error(f"回测失败: {e}")
        st.code(traceback.format_exc())
