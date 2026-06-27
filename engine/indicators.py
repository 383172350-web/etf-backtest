# -*- coding: utf-8 -*-
"""
技术指标计算模块 —— 根据配置按需计算所有排序/买卖条件指标
"""
from __future__ import print_function, division

import numpy as np
import pandas as pd


# ============================================================
#  辅助函数
# ============================================================

def calc_macd_dif(close, ema_short=12, ema_long=26):
    """计算 MACD DIF = EMA(short) - EMA(long)"""
    ema_s = close.ewm(span=ema_short, adjust=False).mean()
    ema_l = close.ewm(span=ema_long, adjust=False).mean()
    return ema_s - ema_l


def calc_atr(high, low, close, period=26):
    """计算 ATR（Average True Range）"""
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs()
    ], axis=1).max(axis=1)
    return tr.rolling(period).mean()


# ============================================================
#  排序指标
# ============================================================

def _calc_return_n(df, window=20):
    """return_N: close.pct_change(N)"""
    df['return_{}'.format(window)] = df['close'].pct_change(window)
    return df


def _calc_momentum_score(df, window=20):
    """
    对数价格加权回归斜率年化 * R²
    参考 v7 / app.py 的 _momentum_score_window 逻辑
    """
    close = df['close']
    n = len(df)
    momentum_scores = np.full(n, np.nan)
    log_prices = np.log(close.values)
    x_vals = np.arange(window, dtype=float)
    weights = np.linspace(1, 2, window)
    w_mean = np.average(x_vals, weights=weights)
    w_std = np.sqrt(np.average((x_vals - w_mean) ** 2, weights=weights))
    w_x_centered = (x_vals - w_mean) / w_std if w_std > 0 else x_vals - w_mean

    for i in range(window - 1, n):
        y = log_prices[i - window + 1:i + 1]
        if np.any(np.isnan(y)) or np.any(np.isinf(y)):
            continue
        y_mean = np.average(y, weights=weights)
        y_centered = y - y_mean
        slope = (np.sum(weights * w_x_centered * y_centered)
                 / np.sum(weights * w_x_centered ** 2) / w_std) if w_std > 0 else 0
        intercept = y_mean - slope * w_mean
        predicted = slope * x_vals + intercept
        ss_res = np.sum(weights * (y - predicted) ** 2)
        ss_tot = np.sum(weights * (y - y_mean) ** 2)
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0
        annualized_return = np.exp(slope * 250) - 1
        ms = annualized_return * r2
        # 连跌惩罚
        prices = close.values[i - window + 1:i + 1]
        if len(prices) >= 4:
            if min(prices[-1] / prices[-2],
                   prices[-2] / prices[-3],
                   prices[-3] / prices[-4]) < 0.95:
                ms = -8
        momentum_scores[i] = ms
    df['momentum_score'] = momentum_scores
    return df


def _calc_difv(df, ema_short=12, ema_long=26, atr_period=26):
    """difv: (EMA12 - EMA26) / ATR26 * 100"""
    close = df['close']
    dif = calc_macd_dif(close, ema_short, ema_long)
    atr = calc_atr(df['high'], df['low'], close, atr_period)
    df['difv'] = (dif / atr * 100).replace([np.inf, -np.inf], np.nan)
    # 同时保存中间指标，供其他条件复用
    df['ema{}'.format(ema_short)] = close.ewm(span=ema_short, adjust=False).mean()
    df['ema{}'.format(ema_long)] = close.ewm(span=ema_long, adjust=False).mean()
    df['atr{}'.format(atr_period)] = atr
    df['dif'] = dif
    return df


def _calc_logbias(df, ema_period=20, multiplier=100):
    """logbias: (ln(close) - EMA(ln(close), N)) * multiplier"""
    close = df['close']
    log_close = np.log(close)
    ema_log = log_close.ewm(span=ema_period, adjust=False).mean()
    df['logbias'] = (log_close - ema_log) * multiplier
    return df


def _calc_std_momentum(df, window=20):
    """std_momentum: (close - MA20) / std20"""
    close = df['close']
    ma = close.rolling(window).mean()
    std = close.rolling(window).std()
    df['std_momentum'] = ((close - ma) / std).replace([np.inf, -np.inf], np.nan)
    df['ma{}'.format(window)] = ma
    df['std{}'.format(window)] = std
    return df


def _calc_wdm_momentum(df, shift=12, smooth=3):
    """wdm_momentum: close / mean(close.shift(N-2)..shift(N)) * 100 - 100"""
    close = df['close']
    # close.shift(shift).rolling(smooth).mean() 等价于
    # mean(close.shift(shift), close.shift(shift+1), ..., close.shift(shift+smooth-1))
    # 但用户要求的是 shift(N-2), shift(N-1), shift(N)，即最近shift期之前的smooth期均值
    # 实际 app.py 中 momentum_shift=12, momentum_smooth=3:
    #   ref_avg = close.shift(momentum_shift).rolling(window=momentum_smooth).mean()
    # 这意味着取 shift(12), shift(13), shift(14) 三日的均值
    ref_avg = close.shift(shift).rolling(window=smooth).mean()
    df['wdm_momentum'] = (close / ref_avg * 100 - 100).replace([np.inf, -np.inf], np.nan)
    return df


# ============================================================
#  基础指标
# ============================================================

def _calc_ma(df, period):
    """计算 MA 并存为 ma{period}"""
    col = 'ma{}'.format(period)
    if col not in df.columns:
        df[col] = df['close'].rolling(period).mean()
    return df


def _calc_ema(df, period):
    """计算 EMA 并存为 ema{period}"""
    col = 'ema{}'.format(period)
    if col not in df.columns:
        df[col] = df['close'].ewm(span=period, adjust=False).mean()
    return df


def _calc_daily_return(df):
    df['daily_return'] = df['close'].pct_change()
    return df


def _calc_return_20(df):
    df['return_20'] = df['close'].pct_change(20)
    return df


def _calc_atr_col(df, period=26):
    """计算 ATR 并存为 atr{period}"""
    col = 'atr{}'.format(period)
    if col not in df.columns:
        df[col] = calc_atr(df['high'], df['low'], df['close'], period)
    return df


def _calc_volume_ratio(df, period=7):
    df['volume_ratio'] = (df['volume'] / df['volume'].rolling(period).mean()).replace(
        [np.inf, -np.inf], np.nan)
    return df


def _calc_std(df, period):
    col = 'std{}'.format(period)
    if col not in df.columns:
        df[col] = df['close'].rolling(period).std()
    return df


def _calc_boll(df, boll_period=17, boll_std=2):
    """布林带: boll_upper / boll_mid / boll_lower"""
    ma = df['close'].rolling(boll_period).mean()
    std = df['close'].rolling(boll_period).std()
    df['boll_mid'] = ma
    df['boll_upper'] = ma + boll_std * std
    df['boll_lower'] = ma - boll_std * std
    return df


def _calc_bias(df, period):
    """乖离率: close / maN - 1"""
    ma_col = 'ma{}'.format(period)
    if ma_col not in df.columns:
        df[ma_col] = df['close'].rolling(period).mean()
    df['bias{}'.format(period)] = df['close'] / df[ma_col] - 1
    return df


# ============================================================
#  RSRS 指标
# ============================================================

def _calc_rsrs(df, rsrs_days=18, rsrs_window=20, lookback_days=250):
    """
    RSRS 标准化强度指标
    1. 预计算所有 rsrs_window 日窗口的 low->high 回归斜率
    2. 滚动统计计算强度和 pass
    """
    n = len(df)
    low_vals = df['low'].values
    high_vals = df['high'].values

    # 预计算所有窗口斜率
    all_slopes = np.full(n, np.nan)
    for i in range(rsrs_window - 1, n):
        lv = low_vals[i - rsrs_window + 1:i + 1]
        hv = high_vals[i - rsrs_window + 1:i + 1]
        if np.std(lv) == 0 or np.std(hv) == 0:
            continue
        try:
            all_slopes[i] = np.polyfit(lv, hv, 1)[0]
        except Exception:
            pass

    # 滚动均值/标准差计算 RSRS 强度
    rsrs_strengths = np.full(n, np.nan)
    rsrs_pass_list = np.zeros(n, dtype=bool)

    for i in range(n):
        if i < rsrs_days - 1:
            continue
        cur_slope = all_slopes[i]
        if np.isnan(cur_slope):
            continue
        start_j = max(rsrs_window - 1, i - lookback_days + 1)
        slope_window = all_slopes[start_j:i + 1]
        valid_slopes = slope_window[~np.isnan(slope_window)]
        if len(valid_slopes) < 2:
            continue
        mean_slope = np.mean(valid_slopes)
        std_slope = np.std(valid_slopes)
        beta = mean_slope - 2 * std_slope
        strength = (cur_slope - beta) / abs(beta) if beta != 0 else 0
        rsrs_pass = cur_slope > beta
        rsrs_pass_list[i] = rsrs_pass
        if rsrs_pass:
            rsrs_strengths[i] = strength

    df['rsrs_strength'] = rsrs_strengths
    df['rsrs_pass'] = rsrs_pass_list
    return df


def _calc_above_ma(df, period):
    """above_ma{period}: close > ma{period}"""
    ma_col = 'ma{}'.format(period)
    if ma_col not in df.columns:
        df[ma_col] = df['close'].rolling(period).mean()
    if period == 10:
        df['above_ma{}'.format(period)] = (df['close'] >= df[ma_col]).fillna(False)
    else:
        df['above_ma{}'.format(period)] = (df['close'] > df[ma_col]).fillna(False)
    return df


# ============================================================
#  大跌惩罚
# ============================================================

def _calc_big_drop_penalty(df, threshold=-0.03, penalty_days=3):
    """
    big_drop_penalty: 近3日任一日跌幅 > threshold
    """
    if 'daily_return' not in df.columns:
        df['daily_return'] = df['close'].pct_change()
    df['big_drop_penalty'] = (
        (df['daily_return'] < threshold)
        .rolling(window=penalty_days, min_periods=1)
        .max()
        .fillna(0)
        .astype(bool)
    )
    return df


# ============================================================
#  按需分析 config 引用的指标
# ============================================================

def _collect_required_indicators(config):
    """
    分析 config 中 buy/sell/sort 引用了哪些指标，
    返回需要计算的指标集合。
    """
    required = set()

    # 排序指标
    sort_cfg = config.get('sort', {})
    sort_indicator = sort_cfg.get('indicator', '')
    if sort_indicator:
        required.add(sort_indicator)

    # 大跌惩罚
    if sort_cfg.get('drop_penalty', False):
        required.add('big_drop_penalty')
        required.add('daily_return')

    # 从 conditions / condition_groups 中提取 indicator 和 value（如果是列名引用）
    _BASE_INDICATORS = {'close', 'open', 'high', 'low', 'volume'}  # 原始列，无需计算

    def _extract_from_conditions(conditions):
        for cond in conditions:
            ind = cond.get('indicator', '')
            val = cond.get('value', '')
            if ind and ind not in _BASE_INDICATORS and ind != 'rank':
                required.add(ind)
            # value 可能是列名引用（如 'ma20'），也可能是数值
            if isinstance(val, str) and val not in _BASE_INDICATORS:
                # 判断是否是已知指标列名
                _KNOWN_INDICATOR_PREFIXES = (
                    'ma', 'ema', 'atr', 'std', 'boll_', 'bias', 'above_ma',
                    'return_', 'daily_return', 'volume_ratio', 'difv', 'dif',
                    'sort_value', 'momentum_score', 'rsrs_', 'wdm_momentum',
                    'big_drop_penalty', 'logbias',
                )
                if any(val.startswith(p) for p in _KNOWN_INDICATOR_PREFIXES):
                    required.add(val)

    # 买入条件
    buy_cfg = config.get('buy', {})
    if buy_cfg.get('mode') == 'switch':
        _extract_from_conditions(buy_cfg.get('conditions', []))
    elif buy_cfg.get('mode') == 'free':
        for group in buy_cfg.get('condition_groups', []):
            _extract_from_conditions(group.get('rules', []))
    # 兼容旧格式（key=指标名的字典）
    for key in buy_cfg:
        if key not in ('mode', 'conditions', 'condition_groups'):
            required.add(key)

    # 卖出条件
    sell_cfg = config.get('sell', {})
    if sell_cfg.get('mode') == 'switch':
        _extract_from_conditions(sell_cfg.get('conditions', []))
    elif sell_cfg.get('mode') == 'free':
        for group in sell_cfg.get('condition_groups', []):
            _extract_from_conditions(group.get('rules', []))
    for key in sell_cfg:
        if key not in ('mode', 'conditions', 'condition_groups', 'stop_loss', 'sell_if_buy_fails'):
            required.add(key)

    # 移除空串和原始列
    required.discard('')
    required -= _BASE_INDICATORS
    return required


# ============================================================
#  排序指标分发
# ============================================================

_SORT_INDICATOR_MAP = {
    'return_n': _calc_return_n,
    'momentum_score': _calc_momentum_score,
    'difv': _calc_difv,
    'logbias': _calc_logbias,
    'std_momentum': _calc_std_momentum,
    'wdm_momentum': _calc_wdm_momentum,
}


def _apply_sort_indicator(df, indicator_name, config):
    """根据排序指标名称，调用对应计算函数并返回 sort_value 列"""
    sort_cfg = config.get('sort', {})

    if indicator_name == 'return_n':
        window = sort_cfg.get('window', 20)
        _calc_return_n(df, window=window)
        df['sort_value'] = df['return_{}'.format(window)]

    elif indicator_name == 'momentum_score':
        window = sort_cfg.get('window', 20)
        _calc_momentum_score(df, window=window)
        df['sort_value'] = df['momentum_score']

    elif indicator_name == 'difv':
        ema_short = sort_cfg.get('ema_short', 12)
        ema_long = sort_cfg.get('ema_long', 26)
        atr_period = sort_cfg.get('atr_period', 26)
        _calc_difv(df, ema_short=ema_short, ema_long=ema_long, atr_period=atr_period)
        df['sort_value'] = df['difv']

    elif indicator_name == 'logbias':
        ema_period = sort_cfg.get('ema_period', 20)
        multiplier = sort_cfg.get('multiplier', 100)
        _calc_logbias(df, ema_period=ema_period, multiplier=multiplier)
        df['sort_value'] = df['logbias']

    elif indicator_name == 'std_momentum':
        window = sort_cfg.get('window', 20)
        _calc_std_momentum(df, window=window)
        df['sort_value'] = df['std_momentum']

    elif indicator_name == 'wdm_momentum':
        shift = sort_cfg.get('shift', 12)
        smooth = sort_cfg.get('smooth', 3)
        _calc_wdm_momentum(df, shift=shift, smooth=smooth)
        df['sort_value'] = df['wdm_momentum']

    else:
        raise ValueError("未知的排序指标: {}".format(indicator_name))

    return df


# ============================================================
#  按需计算买卖条件指标
# ============================================================

def _apply_conditional_indicators(df, required, config):
    """根据 required 集合，按需计算买卖条件引用的指标"""

    # ---- MA 系列 ----
    for period in [5, 10, 20, 60, 120, 250]:
        name = 'ma{}'.format(period)
        if name in required or 'above_ma{}'.format(period) in required or 'bias{}'.format(period) in required:
            _calc_ma(df, period)

    # ---- EMA 系列 ----
    for period in [12, 26]:
        name = 'ema{}'.format(period)
        if name in required:
            _calc_ema(df, period)

    # ---- daily_return ----
    if 'daily_return' in required:
        _calc_daily_return(df)

    # ---- return_N 系列（支持 return_1d, return_5d, return_20, return_21, return_60 等）----
    import re
    for ind in required:
        m = re.match(r'^return_(\d+)d?$', ind)
        if m:
            n = int(m.group(1))
            if ind not in df.columns:
                df[ind] = df['close'].pct_change(n)

    # ---- ATR ----
    for period in [26]:
        name = 'atr{}'.format(period)
        if name in required:
            _calc_atr_col(df, period)

    # ---- volume_ratio ----
    if 'volume_ratio' in required:
        _calc_volume_ratio(df)

    # ---- std 系列 ----
    for period in [20, 60]:
        name = 'std{}'.format(period)
        if name in required:
            _calc_std(df, period)

    # ---- boll ----
    if any(k in required for k in ('boll_upper', 'boll_mid', 'boll_lower')):
        boll_cfg = config.get('boll', {})
        _calc_boll(df,
                   boll_period=boll_cfg.get('period', 17),
                   boll_std=boll_cfg.get('std', 2))

    # ---- bias 系列 ----
    for period in [5, 10, 20, 60]:
        name = 'bias{}'.format(period)
        if name in required:
            _calc_bias(df, period)

    # ---- above_ma 系列 ----
    for period in [5, 10, 20]:
        name = 'above_ma{}'.format(period)
        if name in required:
            _calc_above_ma(df, period)

    # ---- RSRS ----
    if 'rsrs_strength' in required or 'rsrs_pass' in required:
        rsrs_cfg = config.get('rsrs', {})
        _calc_rsrs(df,
                   rsrs_days=rsrs_cfg.get('days', 18),
                   rsrs_window=rsrs_cfg.get('window', 20),
                   lookback_days=rsrs_cfg.get('lookback', 250))

    # ---- momentum_score (非排序场景，如 RSRS 买入条件) ----
    if 'momentum_score' in required and 'momentum_score' not in df.columns:
        mom_cfg = config.get('sort', {})
        window = mom_cfg.get('window', 20)
        _calc_momentum_score(df, window=window)

    # ---- big_drop_penalty ----
    if 'big_drop_penalty' in required:
        drop_cfg = config.get('sort', {})
        _calc_big_drop_penalty(df,
                               threshold=drop_cfg.get('drop_threshold', -0.03),
                               penalty_days=drop_cfg.get('penalty_days', 3))

    return df


# ============================================================
#  主入口
# ============================================================

def calc_all_indicators(data_dict, config):
    """
    根据配置计算所有技术指标

    Parameters
    ----------
    data_dict : dict
        {thscode: DataFrame(open/high/low/close/volume)}
    config : dict
        包含 sort/buy/sell 配置的字典，示例:
        {
            'sort': {
                'indicator': 'difv',    # 排序指标名
                'ema_short': 12,
                'ema_long': 26,
                'atr_period': 26,
                'drop_penalty': True,
                'drop_threshold': -0.03,
                'penalty_days': 3,
            },
            'buy': {
                'above_ma5': True,
                'rsrs_pass': True,
                ...
            },
            'sell': {
                'daily_return': True,
                ...
            },
            'rsrs': {
                'days': 18,
                'window': 20,
                'lookback': 250,
            },
            'boll': {
                'period': 17,
                'std': 2,
            },
        }

    Returns
    -------
    dict
        {thscode: DataFrame(含所有新增指标列)}
    """
    # 收集需要计算的指标
    required = _collect_required_indicators(config)

    # 排序指标名称
    sort_cfg = config.get('sort', {})
    sort_indicator = sort_cfg.get('indicator', '')

    signals = {}
    for thscode, df in data_dict.items():
        df = df.copy()

        # 1. 计算排序指标 -> sort_value
        if sort_indicator and sort_indicator in _SORT_INDICATOR_MAP:
            _apply_sort_indicator(df, sort_indicator, config)

        # 2. 按需计算买卖条件指标
        _apply_conditional_indicators(df, required, config)

        # 3. 大跌惩罚: 修改 sort_value
        if sort_cfg.get('drop_penalty', False) and 'sort_value' in df.columns:
            if 'big_drop_penalty' not in df.columns:
                _calc_big_drop_penalty(df,
                                       threshold=sort_cfg.get('drop_threshold', -0.03),
                                       penalty_days=sort_cfg.get('penalty_days', 3))
            df.loc[df['big_drop_penalty'], 'sort_value'] = -300

        signals[thscode] = df

    return signals
