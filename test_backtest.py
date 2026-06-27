# -*- coding: utf-8 -*-
import os
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

os.environ['MPLBACKEND'] = 'Agg'
import matplotlib
matplotlib.use('Agg')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    print("Test 1: Import app module")
    from app import app, run_difv_backtest_api
    print("OK: Import successful")
    
    print("\nTest 2: Run backtest with app context")
    params = {
        'start_date': '2020-03-12',
        'initial_capital': 1000000,
        'max_holdings': 5,
        'position_pct': 20,
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
    
    with app.app_context():
        result = run_difv_backtest_api(params)
    
    if hasattr(result, 'get_json'):
        result = result.get_json()
    
    if 'error' in result:
        print(f"FAIL: Backtest error: {result['error']}")
    else:
        perf = result.get('performance', {})
        print(f"OK: Backtest successful")
        print(f"  Total return: {perf.get('total_return', 0):.2%}")
        print(f"  Annual return: {perf.get('annual_return', 0):.2%}")
        print(f"  Max drawdown: {perf.get('max_drawdown', 0):.2%}")
        print(f"  Sharpe ratio: {perf.get('sharpe_ratio', 0):.2f}")
        print(f"  Win rate: {perf.get('win_rate', 0):.2%}")
        
        nav_data = result.get('nav_curve', [])
        print(f"  Nav curve points: {len(nav_data)}")
        
        trades = result.get('trades', [])
        print(f"  Trade count: {len(trades)}")
        
        print("\n✅ All tests passed!")
        
except Exception as e:
    print(f"FAIL: {e}")
    import traceback
    traceback.print_exc()
