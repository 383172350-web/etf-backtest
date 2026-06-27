# -*- coding: utf-8 -*-
import os
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

os.environ['MPLBACKEND'] = 'Agg'
import matplotlib
matplotlib.use('Agg')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from app import (
    run_difv_backtest_api, run_wdm_backtest_api,
    run_combo_backtest_api, run_rsrs_backtest_api,
    run_lof_backtest_api, run_tech_difv_backtest_api
)

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

strategies = {
    "全品类DIFv轮动": run_difv_backtest_api,
    "五斗米动量轮动": run_wdm_backtest_api,
    "定投+轮动组合": run_combo_backtest_api,
    "RSRS动量轮动": run_rsrs_backtest_api,
    "LOF轮动": run_lof_backtest_api,
    "科技DIFv轮动": run_tech_difv_backtest_api,
}

print("=" * 70)
print("ETF轮动策略回测系统 - 全策略测试")
print("=" * 70)

results = {}
all_passed = True

with app.app_context():
    for name, func in strategies.items():
        print(f"\n{'=' * 70}")
        print(f"测试策略: {name}")
        print(f"{'=' * 70}")
        
        try:
            result = func(params)
            
            if hasattr(result, 'get_json'):
                result = result.get_json()
            
            if 'error' in result:
                print(f"❌ 测试失败: {result['error']}")
                all_passed = False
            else:
                perf = result.get('performance', {})
                nav_data = result.get('nav_curve', [])
                trades = result.get('trades', [])
                rankings = result.get('rankings', [])
                holdings = result.get('holdings', [])
                
                print(f"✅ 测试通过")
                print(f"  总收益率: {perf.get('total_return', 0):.2%}")
                print(f"  年化收益: {perf.get('annual_return', 0):.2%}")
                print(f"  最大回撤: {perf.get('max_drawdown', 0):.2%}")
                print(f"  夏普比率: {perf.get('sharpe_ratio', 0):.2f}")
                print(f"  胜率: {perf.get('win_rate', 0):.2%}")
                print(f"  净值曲线点数: {len(nav_data)}")
                print(f"  交易次数: {len(trades)}")
                print(f"  当前排名数: {len(rankings)}")
                print(f"  当前持仓数: {len(holdings)}")
                
                results[name] = {
                    'performance': perf,
                    'nav_points': len(nav_data),
                    'trade_count': len(trades),
                }
                
        except Exception as e:
            print(f"❌ 测试异常: {e}")
            import traceback
            traceback.print_exc()
            all_passed = False

print(f"\n{'=' * 70}")
print("测试结果汇总")
print(f"{'=' * 70}")

if all_passed:
    print("✅ 所有策略测试通过!")
    
    print("\n策略对比表:")
    print(f"{'策略名称':<12} {'总收益率':<12} {'年化收益':<12} {'最大回撤':<12} {'交易次数':<10}")
    print("-" * 70)
    for name, data in results.items():
        perf = data['performance']
        print(f"{name:<12} {perf.get('total_return', 0):<12.2%} {perf.get('annual_return', 0):<12.2%} {perf.get('max_drawdown', 0):<12.2%} {data['trade_count']:<10}")
else:
    print("❌ 部分策略测试失败")

print(f"\n{'=' * 70}")
print("测试完成")
print(f"{'=' * 70}")
