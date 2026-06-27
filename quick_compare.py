# -*- coding: utf-8 -*-
"""快速对比 app.py vs engine 回测结果"""
import sys
sys.path.insert(0, '.')
from app import (load_pkl_data, build_data_dict, calc_difv_signals, calc_wdm_signals,
                 calc_rsrs_signals, calc_lof_signals,
                 run_difv_backtest, run_wdm_backtest,
                 run_tech_difv_backtest, run_rsrs_backtest, run_lof_backtest,
                 ETF_CONFIG_DIFV, ETF_CONFIG_WDM, ETF_CONFIG_RSRS,
                 ETF_CONFIG_LOF, ETF_CONFIG_TECH_DIFV, ETF_CONFIG_DIFV_MOM,
                 FEE_RATE, BOND_TICKER, PKL_DIR)
from engine import run_backtest, build_data_dict as engine_build_data_dict
from engine.indicators import calc_all_indicators

results = []

# 1. 全品类DIFv
ec = ETF_CONFIG_DIFV; bt = BOND_TICKER
raw = load_pkl_data(PKL_DIR, ec); dd, dates = build_data_dict(raw)
stk = [v['thscode'] for v in ec.values() if v['thscode'] != bt]
sig = calc_difv_signals(dd, stk)
nv,_,_,_,_ = run_difv_backtest(dd,sig,stk,bt,list(dd.keys()),dates,1000000,'2020-03-12',5,0.20,2,6,0.03,0.25,120,len(stk),{'close_gt_ma20':True,'close_gt_ma5':True,'ma10_gt_ma20':True,'ma5_gt_ma10':True},ec)
app_nav = nv['nav'].iloc[-1]
cfg = {'stock_tickers':stk,'bond_ticker':bt,'start_date':'2020-03-12','initial_capital':1000000,'fee_rate':0.0001,
  'sort':{'indicator':'difv','direction':'desc','ema_short':12,'ema_long':26,'atr_period':26,'drop_penalty':False},
  'buy':{'mode':'switch','conditions':[
    {'indicator':'close','op':'>','value':'ma5','enabled':True,'name':'close>ma5'},
    {'indicator':'close','op':'>','value':'ma20','enabled':True,'name':'close>ma20'},
    {'indicator':'ma10','op':'>','value':'ma20','enabled':True,'name':'ma10>ma20'},
    {'indicator':'ma5','op':'>','value':'ma10','enabled':True,'name':'ma5>ma10'},
    {'indicator':'difv','op':'<','value':120,'enabled':True,'name':'difv<120'}]},
  'sell':{'mode':'switch','conditions':[
    {'indicator':'rank','op':'>','value':6,'enabled':True,'name':'rank>6'},
    {'indicator':'daily_return','op':'<','value':-0.03,'enabled':True,'name':'日跌>3%'},
    {'indicator':'return_20','op':'>','value':0.25,'enabled':True,'name':'20日涨>25%'}],
    'stop_loss':0.0,'sell_if_buy_fails':False},
  'position':{'mode':'equal_weight','max_holdings':5,'position_pct':0.20,'rebalance_days':2,'new_rank_limit':0}}
dd2 = engine_build_data_dict(stk+[bt]); sig2 = calc_all_indicators(dd2,cfg); r = run_backtest(dd2,sig2,cfg)
eng_nav = r['nav_df']['nav'].iloc[-1]
results.append(('全品类DIFv', app_nav, eng_nav))
print(f'全品类DIFv: app={app_nav:.4f} eng={eng_nav:.4f} diff={((eng_nav-app_nav)/app_nav*100):+.2f}%')

# 2. 五斗米
ec=ETF_CONFIG_WDM; raw=load_pkl_data(PKL_DIR,ec); dd,dates=build_data_dict(raw)
stk=[v['thscode'] for v in ec.values()]
sig=calc_wdm_signals(dd,stk)
nv,_,_,_=run_wdm_backtest(dd,sig,stk,dates,1000000,'2020-03-01',ec)
app_nav=nv['nav'].iloc[-1]
cfg={'stock_tickers':stk,'start_date':'2020-03-01','initial_capital':1000000,'fee_rate':0.0001,
  'sort':{'indicator':'wdm_momentum','direction':'desc','shift':12,'smooth':3,'drop_penalty':False},
  'buy':{'mode':'switch','conditions':[
    {'indicator':'close','op':'>','value':'boll_upper','enabled':True,'name':'above_band'},
    {'indicator':'wdm_momentum','op':'>','value':0,'enabled':True,'name':'wdm>0'}]},
  'sell':{'mode':'switch','conditions':[
    {'indicator':'wdm_momentum','op':'<','value':0,'enabled':True,'name':'wdm<0'}],
    'stop_loss':0.0,'sell_if_buy_fails':False},
  'position':{'mode':'single','max_holdings':1,'position_pct':1.0,'rebalance_days':1,'new_rank_limit':0}}
dd2=engine_build_data_dict(stk); sig2=calc_all_indicators(dd2,cfg); r=run_backtest(dd2,sig2,cfg)
eng_nav=r['nav_df']['nav'].iloc[-1]
results.append(('五斗米', app_nav, eng_nav))
print(f'五斗米: app={app_nav:.4f} eng={eng_nav:.4f} diff={((eng_nav-app_nav)/app_nav*100):+.2f}%')

# 3. RSRS
ec=ETF_CONFIG_RSRS; raw=load_pkl_data(PKL_DIR,ec); dd,dates=build_data_dict(raw)
stk=[v['thscode'] for v in ec.values()]
sig=calc_rsrs_signals(dd,stk)
nv,_,_,_=run_rsrs_backtest(dd,sig,stk,dates,1000000,'2020-03-01',0.03,ec)
app_nav=nv['nav'].iloc[-1]
cfg={'stock_tickers':stk,'start_date':'2020-03-01','initial_capital':1000000,'fee_rate':0.0001,
  'sort':{'indicator':'momentum_score','direction':'desc','window':20,'drop_penalty':False},
  'buy':{'mode':'free','condition_groups':[
    {'logic':'AND','rules':[{'indicator':'momentum_score','op':'>','value':0},{'indicator':'momentum_score','op':'<','value':7},{'indicator':'volume_ratio','op':'<=','value':2},{'indicator':'rsrs_pass','op':'is_true','value':0},{'indicator':'rsrs_strength','op':'>','value':0.15}]},
    {'logic':'AND','rules':[{'indicator':'momentum_score','op':'>','value':0},{'indicator':'momentum_score','op':'<','value':7},{'indicator':'volume_ratio','op':'<=','value':2},{'indicator':'rsrs_pass','op':'is_true','value':0},{'indicator':'rsrs_strength','op':'>','value':0.03},{'indicator':'above_ma5','op':'is_true','value':0}]},
    {'logic':'AND','rules':[{'indicator':'momentum_score','op':'>','value':0},{'indicator':'momentum_score','op':'<','value':7},{'indicator':'volume_ratio','op':'<=','value':2},{'indicator':'above_ma10','op':'is_true','value':0}]}]},
  'sell':{'mode':'switch','conditions':[],'stop_loss':0.03,'sell_if_buy_fails':True},
  'position':{'mode':'single','max_holdings':1,'position_pct':1.0,'rebalance_days':1,'new_rank_limit':0}}
dd2=engine_build_data_dict(stk); sig2=calc_all_indicators(dd2,cfg); r=run_backtest(dd2,sig2,cfg)
eng_nav=r['nav_df']['nav'].iloc[-1]
results.append(('RSRS', app_nav, eng_nav))
print(f'RSRS: app={app_nav:.4f} eng={eng_nav:.4f} diff={((eng_nav-app_nav)/app_nav*100):+.2f}%')

# 4. LOF
ec=ETF_CONFIG_LOF; raw=load_pkl_data(PKL_DIR,ec); dd,dates=build_data_dict(raw)
stk=[v['thscode'] for v in ec.values()]
sig=calc_lof_signals(dd,stk)
nv,_,_,_=run_lof_backtest(dd,sig,stk,dates,1000000,'2020-03-01',0.05,0,0,1,ec)
app_nav=nv['nav'].iloc[-1]
cfg={'stock_tickers':stk,'start_date':'2020-03-01','initial_capital':1000000,'fee_rate':0.0001,
  'sort':{'indicator':'std_momentum','direction':'desc','window':20,'drop_penalty':True,'drop_penalty_score':8,'drop_threshold':0.05},
  'buy':{'mode':'switch','conditions':[
    {'indicator':'return_20','op':'>','value':0.05,'enabled':True,'name':'20日涨>5%'},
    {'indicator':'raw_sort_value','op':'>','value':0,'enabled':True,'name':'sort>0'}]},
  'sell':{'mode':'switch','conditions':[
    {'indicator':'return_20','op':'<','value':0,'enabled':True,'name':'20日涨<0'},
    {'indicator':'rank','op':'>','value':1,'enabled':True,'name':'rank>1'}],
    'stop_loss':0.0,'sell_if_buy_fails':True},
  'position':{'mode':'single','max_holdings':1,'position_pct':1.0,'rebalance_days':1,'new_rank_limit':0}}
dd2=engine_build_data_dict(stk); sig2=calc_all_indicators(dd2,cfg); r=run_backtest(dd2,sig2,cfg)
eng_nav=r['nav_df']['nav'].iloc[-1]
results.append(('精选LOF', app_nav, eng_nav))
print(f'精选LOF: app={app_nav:.4f} eng={eng_nav:.4f} diff={((eng_nav-app_nav)/app_nav*100):+.2f}%')

# 5. 科技成长DIFv
ec=ETF_CONFIG_TECH_DIFV; raw=load_pkl_data(PKL_DIR,ec); dd,dates=build_data_dict(raw)
stk=[v['thscode'] for v in ec.values()]
sig=calc_difv_signals(dd,stk)
nv,_,_,_,_=run_tech_difv_backtest(dd,sig,stk,dates,1000000,'2024-02-08',10,0.10,120,ec)
app_nav=nv['nav'].iloc[-1]
cfg={'stock_tickers':stk,'start_date':'2024-02-08','initial_capital':1000000,'fee_rate':0.0001,
  'sort':{'indicator':'difv','direction':'desc','ema_short':12,'ema_long':26,'atr_period':26,'drop_penalty':False},
  'buy':{'mode':'switch','conditions':[
    {'indicator':'difv','op':'>','value':0,'enabled':True,'name':'difv>0'},
    {'indicator':'difv','op':'<','value':120,'enabled':True,'name':'difv<120'},
    {'indicator':'close','op':'>','value':'ma5','enabled':True,'name':'close>ma5'}]},
  'sell':{'mode':'switch','conditions':[
    {'indicator':'difv','op':'<','value':0,'enabled':True,'name':'difv<0'}],
    'stop_loss':0.0,'sell_if_buy_fails':False},
  'position':{'mode':'incremental','max_holdings':10,'position_pct':0.10,'rebalance_days':1,'new_rank_limit':0}}
dd2=engine_build_data_dict(stk); sig2=calc_all_indicators(dd2,cfg); r=run_backtest(dd2,sig2,cfg)
eng_nav=r['nav_df']['nav'].iloc[-1]
results.append(('科技DIFv', app_nav, eng_nav))
print(f'科技DIFv: app={app_nav:.4f} eng={eng_nav:.4f} diff={((eng_nav-app_nav)/app_nav*100):+.2f}%')

# 6. DIFv动量
ec=ETF_CONFIG_DIFV_MOM; raw=load_pkl_data(PKL_DIR,ec); dd,dates=build_data_dict(raw)
stk=[v['thscode'] for v in ec.values()]
sig=calc_difv_signals(dd,stk)
nv,_,_,_,_=run_tech_difv_backtest(dd,sig,stk,dates,1000000,'2020-03-12',5,0.20,120,ec)
app_nav=nv['nav'].iloc[-1]
cfg={'stock_tickers':stk,'start_date':'2020-03-12','initial_capital':1000000,'fee_rate':0.0001,
  'sort':{'indicator':'difv','direction':'desc','ema_short':12,'ema_long':26,'atr_period':26,'drop_penalty':False},
  'buy':{'mode':'switch','conditions':[
    {'indicator':'difv','op':'>','value':0,'enabled':True,'name':'difv>0'},
    {'indicator':'difv','op':'<','value':120,'enabled':True,'name':'difv<120'},
    {'indicator':'close','op':'>','value':'ma5','enabled':True,'name':'close>ma5'}]},
  'sell':{'mode':'switch','conditions':[
    {'indicator':'difv','op':'<','value':0,'enabled':True,'name':'difv<0'}],
    'stop_loss':0.0,'sell_if_buy_fails':False},
  'position':{'mode':'incremental','max_holdings':5,'position_pct':0.20,'rebalance_days':1,'new_rank_limit':0}}
dd2=engine_build_data_dict(stk); sig2=calc_all_indicators(dd2,cfg); r=run_backtest(dd2,sig2,cfg)
eng_nav=r['nav_df']['nav'].iloc[-1]
results.append(('DIFv动量', app_nav, eng_nav))
print(f'DIFv动量: app={app_nav:.4f} eng={eng_nav:.4f} diff={((eng_nav-app_nav)/app_nav*100):+.2f}%')

print()
print('=' * 60)
print(f'{"策略":<10} {"app.py":>8} {"engine":>8} {"差异%":>8}')
print('-' * 60)
for name, a, e in results:
    diff = (e - a) / a * 100 if a else 0
    print(f'{name:<10} {a:>8.4f} {e:>8.4f} {diff:>+7.2f}%')
print('=' * 60)
