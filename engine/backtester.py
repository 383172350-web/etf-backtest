# -*- coding: utf-8 -*-
"""
通用回测引擎 —— 支持高度自定义的轮动策略
==========================================
核心函数: run_backtest(data_dict, signals, config) -> dict

与 v7 策略回测逻辑完全一致：
  - 每日检查卖出条件，T+1 开盘价执行卖出
  - 每轮动日检查买入条件，补充到 max_holdings 只
  - 有新标的买入时全量再平衡，无新标的时清理非目标持仓
  - 非轮动日卖出后资金转债券替代
  - nav 归一化为 1.0 起始
"""

from __future__ import print_function, division

import pandas as pd
import numpy as np

from .data_loader import ETF_NAMES


# ============================================================
#  辅助函数
# ============================================================

def get_ticker_name(ticker):
    """从 ETF_NAMES 获取 ticker 中文名，找不到则返回 ticker 本身"""
    return ETF_NAMES.get(ticker, ticker)


# ============================================================
#  条件评估引擎
# ============================================================

def _resolve_value(row, value):
    """解析条件值：如果是字符串则从 row 取对应列，否则直接返回数值"""
    if isinstance(value, str):
        v = row.get(value, np.nan)
        return float(v) if pd.notna(v) else np.nan
    return value


def _eval_single_condition(row, indicator, op, value):
    """
    评估单条条件。
    indicator: 行中的列名
    op: 运算符 (>/>=/</<=/==/!=/between/is_true/is_false)
    value: 数值或字符串(引用列名)

    返回 True/False/None，若数据缺失返回 None（表示跳过该条件）
    """
    left = row.get(indicator, np.nan)

    # is_true / is_false 特殊处理，布尔指标专用，NaN视为False
    if op == 'is_true':
        return bool(left) if pd.notna(left) else False
    if op == 'is_false':
        return not bool(left) if pd.notna(left) else True

    if pd.isna(left):
        return None
    left = float(left)

    right = _resolve_value(row, value)
    if pd.isna(right):
        return None  # NaN时跳过

    # between 需要 value 为 [lo, hi] 列表
    if op == 'between':
        if not isinstance(value, (list, tuple)) or len(value) < 2:
            return False
        lo = _resolve_value(row, value[0])
        hi = _resolve_value(row, value[1])
        if pd.isna(lo) or pd.isna(hi):
            return False
        return lo <= left <= hi

    if op == '>':
        return left > right
    if op == '>=':
        return left >= right
    if op == '<':
        return left < right
    if op == '<=':
        return left <= right
    if op == '==':
        return abs(left - right) < 1e-10
    if op == '!=':
        return abs(left - right) >= 1e-10

    return False


def _eval_switch_conditions(row, conditions):
    """
    switch 模式：遍历所有 enabled 的 condition，全部满足(AND)才算通过。
    exclude=True 的条件是排除条件（满足则拒绝）。
    NaN条件(返回None)视为跳过，不影响判断（与v7的pd.notna保护一致）。
    """
    for cond in conditions:
        if not cond.get('enabled', True):
            continue
        indicator = cond['indicator']
        op = cond['op']
        value = cond['value']
        is_exclude = cond.get('exclude', False)

        result = _eval_single_condition(row, indicator, op, value)

        # None 表示数据缺失，跳过该条件（不影响结果）
        if result is None:
            continue

        if is_exclude:
            # 排除条件：满足则拒绝
            if result:
                return False
        else:
            # 普通条件：不满足则拒绝
            if not result:
                return False

    return True


def _eval_free_conditions(row, condition_groups):
    """
    free 模式：遍历 condition_groups，组内按 logic(AND/OR) 求值，组间 OR。
    NaN条件(返回None)：AND时视为不满足(与app.py一致，NaN表示数据缺失应拒绝)，
    OR时视为False（数据缺失不能使条件成立）。
    is_true/is_false 不返回None，已在_eval_single_condition中处理NaN。
    """
    if not condition_groups:
        return True

    for group in condition_groups:
        logic = group.get('logic', 'AND').upper()
        rules = group.get('rules', [])

        if not rules:
            continue

        group_result = True if logic == 'AND' else False
        for rule in rules:
            indicator = rule['indicator']
            op = rule['op']
            value = rule['value']
            r = _eval_single_condition(row, indicator, op, value)

            # None=数据缺失，AND时视为False(数据缺失应拒绝)，OR时视为False
            if r is None:
                r = False

            if logic == 'AND':
                group_result = group_result and r
            else:  # OR
                group_result = group_result or r

        # 组间 OR
        if group_result:
            return True

    return False


def eval_buy_conditions(row, buy_config):
    """评估买入条件，返回 True/False"""
    mode = buy_config.get('mode', 'switch')

    if mode == 'switch':
        conditions = buy_config.get('conditions', [])
        return _eval_switch_conditions(row, conditions)
    elif mode == 'free':
        condition_groups = buy_config.get('condition_groups', [])
        return _eval_free_conditions(row, condition_groups)

    return True


def eval_sell_conditions(row, sell_config, rank):
    """
    评估卖出条件，返回 (should_sell, reasons) 。
    switch 模式：任何 enabled 条件满足即卖出（OR）。
    free 模式：组间 OR。
    """
    mode = sell_config.get('mode', 'switch')
    reasons = []

    if mode == 'switch':
        conditions = sell_config.get('conditions', [])
        for cond in conditions:
            if not cond.get('enabled', True):
                continue
            indicator = cond['indicator']
            op = cond['op']
            value = cond['value']
            name = cond.get('name', f"{indicator}{op}{value}")

            # rank 是特殊指标，实时计算
            if indicator == 'rank':
                left = rank
                right = value if not isinstance(value, str) else value
                if isinstance(right, str):
                    try:
                        right = float(right)
                    except (ValueError, TypeError):
                        continue
                result = _eval_single_condition({'rank': float(left)}, 'rank', op, right)
            else:
                result = _eval_single_condition(row, indicator, op, value)

            if result is True:
                reasons.append(name)

    elif mode == 'free':
        condition_groups = sell_config.get('condition_groups', [])
        # free 模式下，组间 OR，只要有一组成立就卖出
        for group in condition_groups:
            logic = group.get('logic', 'AND').upper()
            rules = group.get('rules', [])
            group_pass = True if logic == 'AND' else False

            for rule in rules:
                indicator = rule['indicator']
                op = rule['op']
                value = rule['value']

                if indicator == 'rank':
                    left = rank
                    right = value if not isinstance(value, str) else value
                    if isinstance(right, str):
                        try:
                            right = float(right)
                        except (ValueError, TypeError):
                            continue
                    r = _eval_single_condition({'rank': float(left)}, 'rank', op, right)
                else:
                    r = _eval_single_condition(row, indicator, op, value)

                if logic == 'AND':
                    group_pass = group_pass and (r if r is not None else True)
                else:
                    group_pass = group_pass or (r if r is not None else False)

            if group_pass:
                reasons.append('free条件触发')

    # 止损检查
    stop_loss = sell_config.get('stop_loss', 0)
    if stop_loss and stop_loss > 0:
        # row 中需包含 buy_price 字段用于止损计算
        buy_price = row.get('buy_price', np.nan)
        current_price = row.get('close', np.nan)
        if pd.notna(buy_price) and buy_price > 0 and pd.notna(current_price):
            loss_pct = (current_price - buy_price) / buy_price
            if loss_pct < -stop_loss:
                reasons.append(f'止损{loss_pct*100:.1f}%')

    # 不满足买入条件则卖出
    if sell_config.get('sell_if_buy_fails', False):
        # 需要在外部判断买入条件后传入标记，此处用简化逻辑
        pass

    return len(reasons) > 0, reasons


# ============================================================
#  大跌惩罚
# ============================================================

def _apply_drop_penalty(signals, stock_tickers, sort_config):
    """对 signals 中的 sort_value 应用大跌惩罚"""
    drop_penalty = sort_config.get('drop_penalty', False)
    if not drop_penalty:
        return

    threshold = sort_config.get('drop_threshold', 0.03)
    drop_penalty_score = sort_config.get('drop_penalty_score', 8)

    for ticker in stock_tickers:
        if ticker not in signals:
            continue
        df = signals[ticker]
        if 'close' not in df.columns:
            continue

        # 保存原始排序值（不受penalty影响），供买入条件使用
        if 'sort_value' in df.columns and 'raw_sort_value' not in df.columns:
            df['raw_sort_value'] = df['sort_value']

        close = df['close']
        # 最近3日任一日跌幅 > 阈值
        has_big_drop = (
            (close / close.shift(1) < 1 - threshold) |
            (close.shift(1) / close.shift(2) < 1 - threshold) |
            (close.shift(2) / close.shift(3) < 1 - threshold)
        )
        # 减去penalty_score，而非设为-300
        df.loc[has_big_drop, 'sort_value'] = (
            df.loc[has_big_drop, 'sort_value'] - drop_penalty_score
        )


# ============================================================
#  排名计算
# ============================================================

def _calc_rank_map(signals, stock_tickers, date, sort_config):
    """
    计算某日的排名映射。
    返回 {ticker: rank}，rank 从 1 开始。
    始终使用 sort_value 列（已含penalty），而非原始indicator列。
    """
    indicator = 'sort_value'
    direction = sort_config.get('direction', 'desc')
    descending = (direction == 'desc')

    sort_values = {}
    for ticker in stock_tickers:
        if ticker not in signals:
            continue
        df = signals[ticker]
        if date not in df.index:
            continue
        v = df.loc[date, indicator] if indicator in df.columns else np.nan
        if pd.notna(v):
            sort_values[ticker] = v

    ranked = sorted(sort_values.items(), key=lambda x: x[1], reverse=descending)
    rank_map = {t: i + 1 for i, (t, _) in enumerate(ranked)}
    return rank_map, sort_values


# ============================================================
#  主回测函数
# ============================================================

def run_backtest(data_dict, signals, config):
    """
    通用回测引擎。

    Parameters
    ----------
    data_dict : dict[str, DataFrame]
        ticker -> DataFrame(index=datetime, columns=[open,high,low,close,volume,...])
    signals : dict[str, DataFrame]
        ticker -> DataFrame(index=datetime, 含 sort_value/ma5/ma10/ma20/daily_return/return_20/... 等指标列)
    config : dict
        回测配置，结构见模块文档。

    Returns
    -------
    dict
        nav_df: DataFrame(date, nav)，nav 归一化为 1.0 起始
        trade_log: list of dict，交易记录
        hold_history: list of dict，每日持仓
        final_holdings: dict，最终持仓
        final_cash: float，最终现金
    """
    # ---- 解析配置 ----
    stock_tickers = config['stock_tickers']
    bond_ticker = config.get('bond_ticker')
    initial_capital = config.get('initial_capital', 1000000)
    fee_rate = config.get('fee_rate', 0.0001)
    start_date_str = config.get('start_date')
    sort_config = config.get('sort', {'indicator': 'sort_value', 'direction': 'desc'})
    buy_config = config.get('buy', {'mode': 'switch', 'conditions': []})
    sell_config = config.get('sell', {'mode': 'switch', 'conditions': []})
    position_config = config.get('position', {
        'mode': 'equal_weight', 'max_holdings': 5,
        'position_pct': 0.20, 'rebalance_days': 2, 'new_rank_limit': 0
    })

    max_holdings = position_config.get('max_holdings', 5)
    position_pct = position_config.get('position_pct', 0.20)
    rebalance_days = position_config.get('rebalance_days', 2)
    new_rank_limit = position_config.get('new_rank_limit', 0)
    position_mode = position_config.get('mode', 'equal_weight')

    stop_loss_pct = sell_config.get('stop_loss', 0)
    sell_if_buy_fails = sell_config.get('sell_if_buy_fails', False)

    # ---- 大跌惩罚已由 calc_all_indicators 处理，此处不再重复 ----

    # ---- 确定交易日期 ----
    all_tickers = list(stock_tickers)
    if bond_ticker:
        all_tickers.append(bond_ticker)

    # 取所有标的的日期交集
    date_sets = []
    for ticker in all_tickers:
        if ticker in signals and not signals[ticker].empty:
            date_sets.append(set(signals[ticker].index))
        elif ticker in data_dict and not data_dict[ticker].empty:
            date_sets.append(set(data_dict[ticker].index))

    if not date_sets:
        return {
            'nav_df': pd.DataFrame(columns=['nav']),
            'trade_log': [],
            'hold_history': [],
            'final_holdings': {},
            'final_cash': 0.0,
        }

    common_dates = sorted(list(set.intersection(*date_sets)))

    # 起始日期过滤
    if start_date_str:
        start_ts = pd.Timestamp(start_date_str)
        common_dates = [d for d in common_dates if d >= start_ts]
        if not common_dates:
            return {
                'nav_df': pd.DataFrame(columns=['nav']),
                'trade_log': [],
                'hold_history': [],
                'final_holdings': {},
                'final_cash': 0.0,
            }

    # ---- 对齐起始：从所有 stock_tickers 的 close > 0 且非 NaN 的第一天开始 ----
    valid_start = None
    for d in common_dates:
        ok = True
        for t in stock_tickers:
            if t in signals and d in signals[t].index:
                c = signals[t].loc[d, 'close']
                if pd.isna(c) or c <= 0:
                    ok = False
                    break
            else:
                ok = False
                break
        if ok:
            valid_start = d
            break
    if valid_start:
        common_dates = [d for d in common_dates if d >= valid_start]
    if not common_dates:
        return {
            'nav_df': pd.DataFrame(columns=['nav']),
            'trade_log': [],
            'hold_history': [],
            'final_holdings': {},
            'final_cash': 0.0,
        }

    # ---- 确定轮动日集合 ----
    rebalance_dates = set([common_dates[i] for i in range(0, len(common_dates), rebalance_days)])

    # ---- 初始化 ----
    cash = float(initial_capital)
    holdings = {}  # ticker -> {shares, cost, buy_date}
    nav_history = []
    trade_log = []
    hold_history = []

    # ============================================================
    #  主循环：逐日回测
    # ============================================================
    for i, date in enumerate(common_dates):
        # ---- 0. 跳过不在 signals 中的 ticker ----
        # （signals 中如果某 ticker 不在或 date 不在，跳过）

        # ---- 1. 计算当日净值（收盘价） ----
        nav = cash
        for t, pos in holdings.items():
            t_df = signals.get(t, data_dict.get(t))
            if t_df is not None and date in t_df.index:
                nav += pos['shares'] * t_df.loc[date, 'close']
        nav_history.append({'date': date, 'nav': nav})

        # 记录每日持仓
        active_tickers = [t for t in holdings if t != bond_ticker]
        hold_history.append({
            'date': date,
            'holdings': len(active_tickers),
            'hold_tickers': active_tickers,
        })

        # ---- 检查是否有下一个交易日（T+1） ----
        if i + 1 >= len(common_dates):
            continue
        next_date = common_dates[i + 1]

        # ---- 2. 计算当日排名 ----
        rank_map, sort_values = _calc_rank_map(signals, stock_tickers, date, sort_config)

        # ---- 3. 每日检查卖出（所有交易日） ----
        sell_list = []
        for ticker in list(holdings.keys()):
            if ticker == bond_ticker:
                continue
            t_df = signals.get(ticker)
            if t_df is None or date not in t_df.index:
                continue

            row = t_df.loc[date]
            rank = rank_map.get(ticker, 99)

            # 构造带 buy_price 的行用于止损
            row_dict = row.to_dict() if isinstance(row, pd.Series) else dict(row)
            row_dict['buy_price'] = holdings[ticker]['cost']
            row_dict['rank'] = rank

            should_sell, reasons = eval_sell_conditions(row_dict, sell_config, rank)

            # sell_if_buy_fails: 不满足买入条件则卖出（仅在轮动日检查）
            if sell_if_buy_fails and not should_sell and date in rebalance_dates:
                buy_ok = eval_buy_conditions(row_dict, buy_config)
                # 如果 rank 限制不满足，也视为买入条件不满足
                if new_rank_limit > 0 and rank > new_rank_limit:
                    buy_ok = False
                if not buy_ok:
                    should_sell = True
                    reasons.append('不满足买入条件')

            if should_sell:
                sell_list.append((ticker, "; ".join(reasons)))

        # single模式换仓：轮动日找到满足买入条件的最佳候选，若与当前持仓不同则换仓
        # 注意：仅在当前持仓未被卖出时才执行换仓（与app.py的elif逻辑一致）
        if position_mode == 'single' and date in rebalance_dates:
            sold_tickers = set(t for t, _ in sell_list)
            holding_tickers = [t for t in holdings if t != bond_ticker and t not in sold_tickers]
            if holding_tickers:
                holding_ticker = holding_tickers[0]
                # 找满足买入条件中排名最优的候选（包含当前持仓）
                best_candidate = None
                best_rank = 999
                for t in stock_tickers:
                    t_df = signals.get(t)
                    if t_df is None or date not in t_df.index:
                        continue
                    row = t_df.loc[date]
                    row_dict = row.to_dict() if isinstance(row, pd.Series) else dict(row)
                    t_rank = rank_map.get(t, 999)
                    row_dict['rank'] = t_rank
                    row_dict['sort_value'] = row_dict.get('sort_value', np.nan)
                    buy_ok = eval_buy_conditions(row_dict, buy_config)
                    if new_rank_limit > 0 and t_rank > new_rank_limit:
                        buy_ok = False
                    if buy_ok and t_rank < best_rank:
                        best_rank = t_rank
                        best_candidate = t
                # 如果最优候选不是当前持仓，才换仓
                if best_candidate is not None and best_candidate != holding_ticker:
                    sell_list.append((holding_ticker, "轮动换仓"))

        # T+1 开盘价执行卖出
        for ticker, reason in sell_list:
            if ticker not in holdings:
                continue
            t_df = signals.get(ticker, data_dict.get(ticker))
            if t_df is None or next_date not in t_df.index:
                continue

            open_price = t_df.loc[next_date, 'open']
            if open_price <= 0:
                continue
            pos = holdings[ticker]
            sell_value = pos['shares'] * open_price
            fee = sell_value * fee_rate if ticker != bond_ticker else 0.0
            cash += (sell_value - fee)

            buy_price = pos['cost']
            pnl_pct = (open_price - buy_price) / buy_price * 100 if buy_price > 0 else 0
            hold_days = (date - pos['buy_date']).days if hasattr(date, '__sub__') else 0

            trade_log.append({
                'date': next_date,
                'ticker': ticker,
                'name': get_ticker_name(ticker),
                'action': 'SELL',
                'price': open_price,
                'shares': pos['shares'],
                'value': sell_value,
                'fee': fee,
                'pnl_pct': pnl_pct,
                'hold_days': hold_days,
                'reason': reason,
            })
            del holdings[ticker]

        # ---- 4. 非轮动日：卖出后资金转债券替代 ----
        if date not in rebalance_dates:
            if bond_ticker and cash > 1e-6:
                b_df = signals.get(bond_ticker, data_dict.get(bond_ticker))
                if b_df is not None and next_date in b_df.index:
                    open_price = b_df.loc[next_date, 'open']
                    if open_price <= 0:
                        pass
                    elif bond_ticker in holdings:
                        old = holdings[bond_ticker]
                        add_value = cash
                        fee = 0.0  # 债券替代免手续费
                        add_shares = add_value / open_price
                        new_shares = old['shares'] + add_shares
                        old_value = old['shares'] * old['cost']
                        old['shares'] = new_shares
                        old['cost'] = (old_value + add_value) / new_shares if new_shares > 0 else old['cost']
                        trade_log.append({
                            'date': next_date,
                            'ticker': bond_ticker,
                            'name': get_ticker_name(bond_ticker),
                            'action': 'ADD_BOND',
                            'price': open_price,
                            'shares': add_shares,
                            'value': add_value,
                            'fee': fee,
                            'pnl_pct': 0,
                            'hold_days': (next_date - old['buy_date']).days if hasattr(next_date, '__sub__') else 0,
                            'reason': '非轮动日资金归集',
                        })
                        cash = 0.0
                    else:
                        buy_value = cash
                        fee = 0.0
                        shares = buy_value / open_price
                        holdings[bond_ticker] = {
                            'shares': shares,
                            'cost': open_price,
                            'buy_date': next_date,
                        }
                        trade_log.append({
                            'date': next_date,
                            'ticker': bond_ticker,
                            'name': get_ticker_name(bond_ticker),
                            'action': 'BUY_BOND',
                            'price': open_price,
                            'shares': shares,
                            'value': buy_value,
                            'fee': fee,
                            'pnl_pct': 0,
                            'hold_days': 0,
                            'reason': '非轮动日空仓替代',
                        })
                        cash = 0.0
            continue

        # ============================================================
        #  5. 轮动日：买入 / 再平衡逻辑
        # ============================================================

        # 5.1 确定当前持仓（卖出后的剩余，不含债券替代）
        target_stocks = []
        for ticker in holdings:
            if ticker == bond_ticker:
                continue
            target_stocks.append(ticker)

        # 5.2 找新的买入候选
        candidates = []
        for ticker in stock_tickers:
            if ticker in target_stocks:
                continue
            t_df = signals.get(ticker)
            if t_df is None or date not in t_df.index:
                continue

            row = t_df.loc[date]
            row_dict = row.to_dict() if isinstance(row, pd.Series) else dict(row)
            rank = rank_map.get(ticker, 99)
            row_dict['rank'] = rank

            # 买入条件检查
            buy_ok = eval_buy_conditions(row_dict, buy_config)

            # 排名条件（新入选可单独限制）
            if new_rank_limit > 0:
                rank_ok = rank <= new_rank_limit
            else:
                rank_ok = True

            if buy_ok and rank_ok:
                sort_val = sort_values.get(ticker, np.nan)
                if pd.notna(sort_val):
                    candidates.append((ticker, sort_val, rank))

        # 按排序指标降序/升序排列候选
        direction = sort_config.get('direction', 'desc')
        candidates.sort(key=lambda x: x[1], reverse=(direction == 'desc'))

        # 补充到最多 max_holdings 只
        slots = max_holdings - len(target_stocks)

        # incremental满仓换仓：卖最弱买最强
        if position_mode == 'incremental' and slots <= 0 and candidates:
            # 找最弱持仓（sort_value最差的）
            weakest_ticker = None
            if direction == 'desc':
                weakest_sv = float('inf')
            else:
                weakest_sv = float('-inf')
            for t in target_stocks:
                if t in signals and date in signals[t].index:
                    sv = signals[t].loc[date, 'sort_value']
                    if pd.notna(sv):
                        if (direction == 'desc' and sv < weakest_sv) or \
                           (direction == 'asc' and sv > weakest_sv):
                            weakest_sv = sv
                            weakest_ticker = t
            # 找最强候选（已按sort_value排序，candidates[0]最强）
            best_ticker, best_sv, best_rank = candidates[0]
            # 比较最强候选是否优于最弱持仓
            is_better = (best_sv > weakest_sv) if direction == 'desc' else (best_sv < weakest_sv)
            if weakest_ticker and pd.notna(best_sv) and is_better:
                # 卖最弱持仓
                if weakest_ticker in holdings:
                    t_df = signals.get(weakest_ticker, data_dict.get(weakest_ticker))
                    if t_df is not None and next_date in t_df.index:
                        open_price = t_df.loc[next_date, 'open']
                        if open_price > 0:
                            pos = holdings[weakest_ticker]
                            sell_value = pos['shares'] * open_price
                            fee = sell_value * fee_rate
                            cash += (sell_value - fee)
                            buy_price = pos['cost']
                            pnl_pct = (open_price - buy_price) / buy_price * 100 if buy_price > 0 else 0
                            hold_days = (date - pos['buy_date']).days if hasattr(date, '__sub__') else 0
                            trade_log.append({
                                'date': next_date,
                                'ticker': weakest_ticker,
                                'name': get_ticker_name(weakest_ticker),
                                'action': 'SELL',
                                'price': open_price,
                                'shares': pos['shares'],
                                'value': sell_value,
                                'fee': fee,
                                'pnl_pct': pnl_pct,
                                'hold_days': hold_days,
                                'reason': '增量换仓',
                            })
                            del holdings[weakest_ticker]
                target_stocks.remove(weakest_ticker)
                slots = 1  # 腾出一个位置

        for ticker, sort_val, rank in candidates[:slots]:
            if ticker not in target_stocks:
                target_stocks.append(ticker)

        # 5.3 判断是否需要再平衡（目标中有新标的，当前未持有）
        need_rebalance = any(t not in holdings for t in target_stocks)

        # 5.4 根据持仓模式执行
        if need_rebalance:
            if position_mode == 'incremental':
                # ---- 增量式：不卖出已有持仓，只买入新标的 ----
                for ticker in target_stocks:
                    if ticker in holdings:
                        continue  # 已持有，跳过
                    if cash <= 0:
                        break
                    target_value = cash * position_pct
                    t_df = signals.get(ticker, data_dict.get(ticker))
                    if t_df is None or next_date not in t_df.index:
                        continue
                    fee = target_value * fee_rate
                    open_price = t_df.loc[next_date, 'open']
                    if open_price <= 0:
                        continue
                    shares = target_value / open_price
                    buy_value = shares * open_price
                    if cash < buy_value + fee:
                        # 余额不足，用剩余资金买入
                        buy_value = cash / (1 + fee_rate)
                        if buy_value <= 0:
                            continue
                        fee = buy_value * fee_rate
                        shares = buy_value / open_price
                    cash -= (buy_value + fee)
                    holdings[ticker] = {
                        'shares': shares,
                        'cost': open_price,
                        'buy_date': next_date,
                    }
                    trade_log.append({
                        'date': next_date,
                        'ticker': ticker,
                        'name': get_ticker_name(ticker),
                        'action': 'BUY',
                        'price': open_price,
                        'shares': shares,
                        'value': buy_value,
                        'fee': fee,
                        'pnl_pct': 0,
                        'hold_days': 0,
                        'reason': '增量建仓',
                    })

            else:
                # ---- 全量再平衡（equal_weight / single） ----
                # 先卖出所有持仓（与app.py一致：再平衡卖出不收手续费）
                for t in list(holdings.keys()):
                    t_df = signals.get(t, data_dict.get(t))
                    if t_df is not None and next_date in t_df.index:
                        open_price = t_df.loc[next_date, 'open']
                        if open_price > 0:
                            cash += holdings[t]['shares'] * open_price
                    del holdings[t]

                total_value = cash

                if position_mode == 'equal_weight':
                    # 等权分配
                    for ticker in target_stocks:
                        target_value = total_value * position_pct
                        t_df = signals.get(ticker, data_dict.get(ticker))
                        if t_df is None or next_date not in t_df.index:
                            continue
                        fee = target_value * fee_rate
                        open_price = t_df.loc[next_date, 'open']
                        if open_price <= 0:
                            continue
                        shares = target_value / open_price
                        buy_value = shares * open_price
                        cash -= (buy_value + fee)
                        holdings[ticker] = {
                            'shares': shares,
                            'cost': open_price,
                            'buy_date': next_date,
                        }
                        trade_log.append({
                            'date': next_date,
                            'ticker': ticker,
                            'name': get_ticker_name(ticker),
                            'action': 'BUY',
                            'price': open_price,
                            'shares': shares,
                            'value': buy_value,
                            'fee': fee,
                            'pnl_pct': 0,
                            'hold_days': 0,
                            'reason': '建仓/再平衡',
                        })

                elif position_mode == 'single':
                    # 100% 单标的，只持最强的
                    if target_stocks:
                        ticker = target_stocks[0]
                        t_df = signals.get(ticker, data_dict.get(ticker))
                        if t_df is not None and next_date in t_df.index:
                            target_value = total_value
                            fee = target_value * fee_rate
                            open_price = t_df.loc[next_date, 'open']
                            if open_price <= 0:
                                pass
                            else:
                                shares = target_value / open_price
                                buy_value = shares * open_price
                                cash -= (buy_value + fee)
                                holdings[ticker] = {
                                    'shares': shares,
                                    'cost': open_price,
                                    'buy_date': next_date,
                            }
                            trade_log.append({
                                'date': next_date,
                                'ticker': ticker,
                                'name': get_ticker_name(ticker),
                                'action': 'BUY',
                                'price': open_price,
                                'shares': shares,
                                'value': buy_value,
                                'fee': fee,
                                'pnl_pct': 0,
                                'hold_days': 0,
                                'reason': '单标的建仓',
                            })

            # 余款买债券替代
            if bond_ticker and cash > 1e-6:
                b_df = signals.get(bond_ticker, data_dict.get(bond_ticker))
                if b_df is not None and next_date in b_df.index:
                    open_price = b_df.loc[next_date, 'open']
                    if open_price <= 0:
                        pass
                    else:
                        buy_value = cash
                        fee = 0.0  # 债券替代免手续费
                        shares = buy_value / open_price
                        holdings[bond_ticker] = {
                            'shares': shares,
                            'cost': open_price,
                            'buy_date': next_date,
                        }
                        trade_log.append({
                            'date': next_date,
                            'ticker': bond_ticker,
                            'name': get_ticker_name(bond_ticker),
                            'action': 'BUY_BOND',
                            'price': open_price,
                            'shares': shares,
                            'value': buy_value,
                            'fee': fee,
                            'pnl_pct': 0,
                            'hold_days': 0,
                            'reason': '空仓替代',
                        })
                        cash = 0.0

        else:
            # ---- 不需要再平衡：清理非目标持仓，资金转债券替代 ----
            for t in list(holdings.keys()):
                if t != bond_ticker and t not in target_stocks:
                    t_df = signals.get(t, data_dict.get(t))
                    if t_df is None or next_date not in t_df.index:
                        continue
                    open_price = t_df.loc[next_date, 'open']
                    if open_price <= 0:
                        continue
                    sell_value = holdings[t]['shares'] * open_price
                    fee = sell_value * fee_rate if t != bond_ticker else 0.0
                    cash += (sell_value - fee)
                    trade_log.append({
                        'date': next_date,
                        'ticker': t,
                        'name': get_ticker_name(t),
                        'action': 'SELL_CLEAR',
                        'price': open_price,
                        'shares': holdings[t]['shares'],
                        'value': sell_value,
                        'fee': fee,
                        'pnl_pct': (open_price - holdings[t]['cost']) / holdings[t]['cost'] * 100 if holdings[t]['cost'] > 0 else 0,
                        'hold_days': (next_date - holdings[t]['buy_date']).days if hasattr(next_date, '__sub__') else 0,
                        'reason': '轮动调出',
                    })
                    del holdings[t]

            # 剩余资金转债券替代
            if bond_ticker and cash > 1e-6:
                b_df = signals.get(bond_ticker, data_dict.get(bond_ticker))
                if b_df is not None and next_date in b_df.index:
                    open_price = b_df.loc[next_date, 'open']
                    if open_price <= 0:
                        pass
                    elif bond_ticker in holdings:
                        old = holdings[bond_ticker]
                        add_value = cash
                        fee = 0.0
                        add_shares = add_value / open_price
                        new_shares = old['shares'] + add_shares
                        old_value = old['shares'] * old['cost']
                        old['shares'] = new_shares
                        old['cost'] = (old_value + add_value) / new_shares if new_shares > 0 else old['cost']
                        trade_log.append({
                            'date': next_date,
                            'ticker': bond_ticker,
                            'name': get_ticker_name(bond_ticker),
                            'action': 'ADD_BOND',
                            'price': open_price,
                            'shares': add_shares,
                            'value': add_value,
                            'fee': fee,
                            'pnl_pct': 0,
                            'hold_days': (next_date - old['buy_date']).days if hasattr(next_date, '__sub__') else 0,
                            'reason': '轮动归集',
                        })
                        cash = 0.0
                    else:
                        buy_value = cash
                        fee = 0.0
                        shares = buy_value / open_price
                        holdings[bond_ticker] = {
                            'shares': shares,
                            'cost': open_price,
                            'buy_date': next_date,
                        }
                        trade_log.append({
                            'date': next_date,
                            'ticker': bond_ticker,
                            'name': get_ticker_name(bond_ticker),
                            'action': 'BUY_BOND',
                            'price': open_price,
                            'shares': shares,
                            'value': buy_value,
                            'fee': fee,
                            'pnl_pct': 0,
                            'hold_days': 0,
                            'reason': '空仓替代',
                        })
                        cash = 0.0

    # ============================================================
    #  构造返回值
    # ============================================================
    nav_df = pd.DataFrame(nav_history)
    if not nav_df.empty:
        nav_df = nav_df.set_index('date')
        # nav 归一化：nav_df['nav'] = nav_df['nav'] / nav_df['nav'].iloc[0]
        first_nav = nav_df['nav'].iloc[0]
        if first_nav > 0:
            nav_df['nav'] = nav_df['nav'] / first_nav
    else:
        nav_df = pd.DataFrame(columns=['nav'])

    return {
        'nav_df': nav_df,
        'trade_log': trade_log,
        'hold_history': hold_history,
        'final_holdings': holdings,
        'final_cash': cash,
    }
