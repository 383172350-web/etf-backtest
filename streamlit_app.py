# -*- coding: utf-8 -*-
"""
ETF轮动策略回测系统 —— Streamlit 主界面
==========================================
五大模块：股票池选择、轮动排序规格、买入条件、卖出条件、基础配置
"""
from __future__ import print_function, division

import io
import os
import json
import datetime
import traceback

import streamlit as st
import pandas as pd
import numpy as np

from engine import (
    scan_pkl_dir,
    build_data_dict,
    ETF_NAMES,
    calc_all_indicators,
    run_backtest,
    compute_performance,
    plot_nav_curve,
    plot_drawdown,
    compute_yearly_returns,
)

# ============================================================
#  页面配置
# ============================================================
st.set_page_config(layout="wide", page_title="ETF轮动策略回测系统")

# ============================================================
#  缓存：扫描 pkl 目录
# ============================================================
@st.cache_data
def cached_scan_pkl_dir():
    return scan_pkl_dir()


# ============================================================
#  预设策略定义
# ============================================================
PRESET_STRATEGIES = {
    "自定义": {},
    "全品类DIFv轮动": {
        "stock_tickers": [
            "159949.SZ", "159980.SZ", "159981.SZ", "159985.SZ",
            "510300.SH", "513030.SH", "513050.SH", "513100.SH",
            "513500.SH", "513520.SH", "512100.SH", "501018.SH",
            "518880.SH",
        ],
        "bond_ticker": "511880.SH",
        "start_date": "2020-03-12",
        "sort": {
            "indicator": "difv",
            "direction": "desc",
            "ema_short": 12,
            "ema_long": 26,
            "atr_period": 26,
            "drop_penalty": False,
        },
        "buy": {
            "mode": "switch",
            "conditions": [
                {"indicator": "close", "op": ">", "value": "ma5", "enabled": True, "name": "close>ma5"},
                {"indicator": "close", "op": ">", "value": "ma20", "enabled": True, "name": "close>ma20"},
                {"indicator": "ma10", "op": ">", "value": "ma20", "enabled": True, "name": "ma10>ma20"},
                {"indicator": "ma5", "op": ">", "value": "ma10", "enabled": True, "name": "ma5>ma10"},
                {"indicator": "difv", "op": "<", "value": 120, "enabled": True, "name": "difv<120"},
            ],
        },
        "sell": {
            "mode": "switch",
            "conditions": [
                {"indicator": "rank", "op": ">", "value": 6, "enabled": True, "name": "rank>6"},
                {"indicator": "daily_return", "op": "<", "value": -0.03, "enabled": True, "name": "日跌幅>3%"},
                {"indicator": "return_20", "op": ">", "value": 0.25, "enabled": True, "name": "20日涨幅>25%"},
            ],
            "stop_loss": 0.0,
            "sell_if_buy_fails": False,
        },
        "position": {
            "mode": "equal_weight",
            "max_holdings": 5,
            "position_pct": 0.20,
            "rebalance_days": 2,
            "new_rank_limit": 0,
        },
    },
    "五斗米动量轮动": {
        "stock_tickers": [
            "510050.SH", "510300.SH", "588000.SH", "159915.SZ", "562500.SH",
        ],
        "start_date": "2020-03-01",
        "sort": {
            "indicator": "wdm_momentum",
            "direction": "desc",
            "shift": 12,
            "smooth": 3,
            "drop_penalty": False,
        },
        "buy": {
            "mode": "switch",
            "conditions": [
                {"indicator": "close", "op": ">", "value": "boll_upper", "enabled": True, "name": "above_band"},
                {"indicator": "wdm_momentum", "op": ">", "value": 0, "enabled": True, "name": "wdm_momentum>0"},
            ],
        },
        "sell": {
            "mode": "switch",
            "conditions": [
                {"indicator": "wdm_momentum", "op": "<", "value": 0, "enabled": True, "name": "wdm_momentum<0"},
            ],
            "stop_loss": 0.0,
            "sell_if_buy_fails": True,
        },
        "position": {
            "mode": "single",
            "max_holdings": 1,
            "position_pct": 1.0,
            "rebalance_days": 1,
            "new_rank_limit": 0,
        },
    },
    "科技成长DIFv轮动": {
        "stock_tickers": [
            "159509.SZ", "515070.SH", "515880.SH", "515000.SH", "159611.SZ",
            "515990.SH", "512480.SH", "159766.SH", "588250.SH", "159869.SZ",
            "159551.SZ", "512660.SH", "159967.SZ", "515120.SH", "159898.SZ",
            "159380.SZ", "159871.SZ", "515790.SH", "159806.SZ", "159995.SZ",
            "159566.SZ", "515400.SH", "560913.SH", "560200.SH", "159786.SZ",
            "159732.SZ",
        ],
        "start_date": "2024-02-08",
        "sort": {
            "indicator": "difv",
            "direction": "desc",
            "ema_short": 12,
            "ema_long": 26,
            "atr_period": 26,
            "drop_penalty": False,
        },
        "buy": {
            "mode": "switch",
            "conditions": [
                {"indicator": "difv", "op": ">", "value": 0, "enabled": True, "name": "difv>0"},
                {"indicator": "difv", "op": "<", "value": 120, "enabled": True, "name": "difv<120"},
                {"indicator": "close", "op": ">", "value": "ma5", "enabled": True, "name": "close>ma5"},
            ],
        },
        "sell": {
            "mode": "switch",
            "conditions": [
                {"indicator": "difv", "op": "<", "value": 0, "enabled": True, "name": "difv<0"},
            ],
            "stop_loss": 0.0,
            "sell_if_buy_fails": False,
        },
        "position": {
            "mode": "incremental",
            "max_holdings": 10,
            "position_pct": 0.10,
            "rebalance_days": 1,
            "new_rank_limit": 0,
        },
    },
    "DIFv动量轮动": {
        "stock_tickers": [
            "512690.SH", "515880.SH", "159605.SZ", "513100.SH", "513500.SH",
            "513520.SH", "513030.SH", "518880.SH",
        ],
        "start_date": "2020-03-12",
        "sort": {
            "indicator": "difv",
            "direction": "desc",
            "ema_short": 12,
            "ema_long": 26,
            "atr_period": 26,
            "drop_penalty": False,
        },
        "buy": {
            "mode": "switch",
            "conditions": [
                {"indicator": "difv", "op": ">", "value": 0, "enabled": True, "name": "difv>0"},
                {"indicator": "difv", "op": "<", "value": 120, "enabled": True, "name": "difv<120"},
                {"indicator": "close", "op": ">", "value": "ma5", "enabled": True, "name": "close>ma5"},
            ],
        },
        "sell": {
            "mode": "switch",
            "conditions": [
                {"indicator": "difv", "op": "<", "value": 0, "enabled": True, "name": "difv<0"},
            ],
            "stop_loss": 0.0,
            "sell_if_buy_fails": False,
        },
        "position": {
            "mode": "incremental",
            "max_holdings": 5,
            "position_pct": 0.20,
            "rebalance_days": 1,
            "new_rank_limit": 0,
        },
    },
    "RSRS动量轮动": {
        "stock_tickers": [
            "518880.SH", "513100.SH", "588000.SH", "159915.SZ", "511260.SH",
        ],
        "start_date": "2020-03-01",
        "sort": {
            "indicator": "momentum_score",
            "direction": "desc",
            "window": 20,
            "drop_penalty": False,
        },
        "buy": {
            "mode": "free",
            "condition_groups": [
                {
                    "logic": "AND",
                    "rules": [
                        {"indicator": "momentum_score", "op": ">", "value": 0},
                        {"indicator": "momentum_score", "op": "<", "value": 7},
                        {"indicator": "volume_ratio", "op": "<=", "value": 2},
                    ],
                },
                {
                    "logic": "AND",
                    "rules": [
                        {"indicator": "rsrs_pass", "op": "is_true", "value": 0},
                        {"indicator": "rsrs_strength", "op": ">", "value": 0.15},
                        {"indicator": "momentum_score", "op": ">", "value": 0},
                        {"indicator": "momentum_score", "op": "<", "value": 7},
                    ],
                },
                {
                    "logic": "AND",
                    "rules": [
                        {"indicator": "rsrs_pass", "op": "is_true", "value": 0},
                        {"indicator": "rsrs_strength", "op": ">", "value": 0.03},
                        {"indicator": "above_ma5", "op": "is_true", "value": 0},
                        {"indicator": "momentum_score", "op": ">", "value": 0},
                        {"indicator": "momentum_score", "op": "<", "value": 7},
                    ],
                },
                {
                    "logic": "AND",
                    "rules": [
                        {"indicator": "above_ma10", "op": "is_true", "value": 0},
                        {"indicator": "momentum_score", "op": ">", "value": 0},
                        {"indicator": "momentum_score", "op": "<", "value": 7},
                    ],
                },
            ],
        },
        "sell": {
            "mode": "switch",
            "conditions": [],
            "stop_loss": 0.03,
            "sell_if_buy_fails": True,
        },
        "position": {
            "mode": "single",
            "max_holdings": 1,
            "position_pct": 1.0,
            "rebalance_days": 1,
            "new_rank_limit": 0,
        },
    },
    "精选LOF轮动": {
        "stock_tickers": [
            "163402.SZ", "163417.SZ", "161903.SZ", "162703.SZ", "161005.SZ",
        ],
        "start_date": "2020-03-01",
        "sort": {
            "indicator": "std_momentum",
            "direction": "desc",
            "window": 20,
            "drop_penalty": True,
            "drop_threshold": 0.05,
        },
        "buy": {
            "mode": "switch",
            "conditions": [
                {"indicator": "return_20", "op": ">", "value": 0.05, "enabled": True, "name": "20日涨幅>5%"},
                {"indicator": "sort_value", "op": ">", "value": 0, "enabled": True, "name": "sort_value>0"},
            ],
        },
        "sell": {
            "mode": "switch",
            "conditions": [
                {"indicator": "return_20", "op": "<", "value": 0, "enabled": True, "name": "20日涨幅<0"},
                {"indicator": "rank", "op": ">", "value": 1, "enabled": True, "name": "rank>1"},
            ],
            "stop_loss": 0.0,
            "sell_if_buy_fails": True,
        },
        "position": {
            "mode": "single",
            "max_holdings": 1,
            "position_pct": 1.0,
            "rebalance_days": 1,
            "new_rank_limit": 0,
        },
    },
}

# 预设组合（股票池快捷按钮）
PRESET_POOLS = {
    "全品类(14只)": [
        "159949.SZ", "159980.SZ", "159981.SZ", "159985.SZ",
        "510300.SH", "513030.SH", "513050.SH", "513100.SH",
        "513500.SH", "513520.SH", "512100.SH", "501018.SH",
        "518880.SH", "511880.SH",
    ],
    "科技成长(26只)": [
        "159509.SZ", "515070.SH", "515880.SH", "515000.SH", "159611.SZ",
        "515990.SH", "512480.SH", "159766.SH", "588250.SH", "159869.SZ",
        "159551.SZ", "512660.SH", "159967.SZ", "515120.SH", "159898.SZ",
        "159380.SZ", "159871.SZ", "515790.SH", "159806.SZ", "159995.SZ",
        "159566.SZ", "515400.SH", "560913.SH", "560200.SH", "159786.SZ",
        "159732.SZ",
    ],
    "五斗米(5只)": [
        "510050.SH", "510300.SH", "588000.SH", "159915.SZ", "562500.SH",
    ],
    "RSRS(5只)": [
        "518880.SH", "513100.SH", "588000.SH", "159915.SZ", "511260.SH",
    ],
    "LOF(5只)": [
        "163402.SZ", "163417.SZ", "161903.SZ", "162703.SZ", "161005.SZ",
    ],
}

# ETF分组定义（用于分组选择）
ETF_GROUPS = {
    "全品类(13只)": ["159949.SZ","159980.SZ","159981.SZ","159985.SZ","510300.SH","513030.SH","513050.SH","513100.SH","513500.SH","513520.SH","512100.SH","501018.SH","518880.SH"],
    "科技成长(26只)": ["159509.SZ","515070.SH","515880.SH","515000.SH","159611.SZ","515990.SH","512480.SH","159766.SZ","588250.SH","159869.SZ","159551.SZ","512660.SH","159967.SZ","515120.SH","159898.SZ","159380.SZ","159871.SZ","515790.SH","159806.SZ","159995.SZ","159566.SZ","515400.SH","560913.SH","560200.SH","159786.SZ","159732.SZ"],
    "五斗米(5只)": ["510050.SH","510300.SH","588000.SH","159915.SZ","562500.SH"],
    "RSRS(5只)": ["518880.SH","513100.SH","588000.SH","159915.SZ","511260.SH"],
    "LOF(5只)": ["163402.SZ","163417.SZ","161903.SZ","162703.SZ","161005.SZ"],
}

# 买入条件预设（逐条开关模式）
BUY_SWITCH_PRESETS = [
    {"key": "close_gt_ma20", "label": "close > ma20", "indicator": "close", "op": ">", "value": "ma20", "default": True},
    {"key": "close_gt_ma5", "label": "close > ma5", "indicator": "close", "op": ">", "value": "ma5", "default": True},
    {"key": "close_gt_ma10", "label": "close > ma10", "indicator": "close", "op": ">", "value": "ma10", "default": False},
    {"key": "ma10_gt_ma20", "label": "ma10 > ma20", "indicator": "ma10", "op": ">", "value": "ma20", "default": True},
    {"key": "ma5_gt_ma10", "label": "ma5 > ma10", "indicator": "ma5", "op": ">", "value": "ma10", "default": True},
    {"key": "volume_ratio_exclude", "label": "量比排除 (>2)", "indicator": "volume_ratio", "op": ">", "value": 2, "default": False, "exclude": True},
    {"key": "return_n_lt_threshold", "label": "N日涨幅 < 阈值", "indicator": "return_21", "op": "<", "value": 0.25, "default": True, "has_param": True, "param_default": 0.25},
    {"key": "difv_lt_threshold", "label": "difv < 阈值", "indicator": "difv", "op": "<", "value": 120, "default": False, "has_param": True, "param_default": 120},
    {"key": "rank_le_n", "label": "rank <= N", "indicator": "rank", "op": "<=", "value": 5, "default": True, "has_param": True, "param_default": 5},
    {"key": "new_rank_limit", "label": "新入选排名限制", "indicator": "rank", "op": "<=", "value": 5, "default": False, "has_param": True, "param_default": 5},
]

# 卖出条件预设（逐条开关模式）
SELL_SWITCH_PRESETS = [
    {"key": "rank_gt_n", "label": "rank > N", "indicator": "rank", "op": ">", "value": 6, "default": True, "has_param": True, "param_default": 6},
    {"key": "daily_drop_gt", "label": "日跌幅 > 阈值", "indicator": "daily_return", "op": "<", "value": -0.03, "default": True, "has_param": True, "param_default": 3},
    {"key": "return_20_gt", "label": "20日涨幅 > 阈值", "indicator": "return_20", "op": ">", "value": 0.25, "default": True, "has_param": True, "param_default": 25},
    {"key": "difv_lt_0", "label": "difv < 0", "indicator": "difv", "op": "<", "value": 0, "default": False},
    {"key": "close_lt_ma5", "label": "close < ma5", "indicator": "close", "op": "<", "value": "ma5", "default": False},
    {"key": "close_lt_ma20", "label": "close < ma20", "indicator": "close", "op": "<", "value": "ma20", "default": False},
    {"key": "wdm_momentum_lt_0", "label": "wdm_momentum < 0", "indicator": "wdm_momentum", "op": "<", "value": 0, "default": False},
    {"key": "return_20_lt_0", "label": "20日涨幅 < 0", "indicator": "return_20", "op": "<", "value": 0, "default": False},
]

# 排序指标选项
SORT_INDICATOR_OPTIONS = {
    "N日涨幅": "return_n",
    "动量得分": "momentum_score",
    "DIF指标": "difv",
    "LOGBIAS指标": "logbias",
    "标准化动量": "std_momentum",
    "五斗米动量": "wdm_momentum",
}

# 自由组合模式可用的指标
FREE_INDICATOR_OPTIONS = [
    "close", "open", "high", "low", "volume",
    "ma5", "ma10", "ma20", "ma60",
    "ema12", "ema26",
    "difv", "dif", "atr26",
    "momentum_score", "std_momentum", "wdm_momentum", "logbias",
    "return_20", "return_21", "daily_return",
    "volume_ratio",
    "rsrs_strength", "rsrs_pass",
    "above_ma5", "above_ma10", "above_ma20",
    "boll_upper", "boll_mid", "boll_lower",
    "sort_value", "rank",
]

FREE_OPERATOR_OPTIONS = [">", ">=", "<", "<=", "==", "!=", "between", "is_true", "is_false"]


# ============================================================
#  策略持久化
# ============================================================
SAVED_STRATEGIES_FILE = os.path.join(os.path.dirname(__file__), 'saved_strategies.json')


def load_saved_strategies():
    """加载用户保存的策略"""
    if os.path.exists(SAVED_STRATEGIES_FILE):
        with open(SAVED_STRATEGIES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_strategy(name, config):
    """保存策略配置"""
    saved = load_saved_strategies()
    saved[name] = config
    with open(SAVED_STRATEGIES_FILE, 'w', encoding='utf-8') as f:
        json.dump(saved, f, ensure_ascii=False, indent=2)


def delete_strategy(name):
    """删除策略配置"""
    saved = load_saved_strategies()
    if name in saved:
        del saved[name]
        with open(SAVED_STRATEGIES_FILE, 'w', encoding='utf-8') as f:
            json.dump(saved, f, ensure_ascii=False, indent=2)


# ============================================================
#  辅助函数
# ============================================================
def format_ticker_label(thscode):
    """格式化代码显示为 '代码 名称' """
    name = ETF_NAMES.get(thscode, "")
    code = thscode.split(".")[0]
    return f"{code} {name}" if name else code


def parse_thscode_from_label(label):
    """从 '代码 名称' 标签解析出 thscode"""
    code = label.split(" ")[0]
    return code


def init_session_state_defaults():
    """初始化 session_state 中的默认值"""
    defaults = {
        "preset_name": "自定义",
        "selected_tickers": [],
        "start_date": datetime.date(2020, 1, 2),
        "initial_capital": 1000000,
        "fee_rate": 0.0001,
        "cash_substitute": "511880.SH",
        "position_mode": "等权",
        "max_holdings": 5,
        "position_pct": 0.20,
        "rebalance_days": 2,
        "sort_indicator_label": "N日涨幅",
        "sort_direction": "降序",
        "sort_window": 21,
        "sort_momentum_window": 20,
        "sort_ema_short": 12,
        "sort_ema_long": 26,
        "sort_atr_period": 26,
        "sort_logbias_ema": 20,
        "sort_logbias_multiplier": 100,
        "sort_std_window": 20,
        "sort_wdm_shift": 12,
        "sort_wdm_smooth": 3,
        "drop_penalty": False,
        "drop_threshold": 5.0,
        "buy_mode": "逐条开关",
        "sell_mode": "逐条开关",
        "sell_stop_loss": 3.0,
        "sell_if_buy_fails": False,
        "buy_free_groups": [{"logic": "AND", "rules": []}],
        "sell_free_groups": [{"logic": "AND", "rules": []}],
    }
    # 买入开关默认
    for preset in BUY_SWITCH_PRESETS:
        defaults[f"buy_switch_{preset['key']}"] = preset["default"]
        if preset.get("has_param"):
            defaults[f"buy_param_{preset['key']}"] = preset["param_default"]
    # 卖出开关默认
    for preset in SELL_SWITCH_PRESETS:
        defaults[f"sell_switch_{preset['key']}"] = preset["default"]
        if preset.get("has_param"):
            defaults[f"sell_param_{preset['key']}"] = preset["param_default"]

    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def apply_preset(name, config=None):
    """将预设策略的参数写入 session_state。可传入config用于加载保存的策略"""
    preset = config if config is not None else PRESET_STRATEGIES.get(name, {})
    if not preset:
        return

    st.session_state["preset_name"] = name

    # 股票池
    st.session_state["selected_tickers"] = list(preset.get("stock_tickers", []))

    # 排序
    sort_cfg = preset.get("sort", {})
    indicator = sort_cfg.get("indicator", "return_n")
    # 反查中文 label
    label_map = {v: k for k, v in SORT_INDICATOR_OPTIONS.items()}
    st.session_state["sort_indicator_label"] = label_map.get(indicator, "N日涨幅")
    st.session_state["sort_direction"] = "降序" if sort_cfg.get("direction", "desc") == "desc" else "升序"
    st.session_state["sort_window"] = sort_cfg.get("window", 21)
    st.session_state["sort_momentum_window"] = sort_cfg.get("window", 20)
    st.session_state["sort_ema_short"] = sort_cfg.get("ema_short", 12)
    st.session_state["sort_ema_long"] = sort_cfg.get("ema_long", 26)
    st.session_state["sort_atr_period"] = sort_cfg.get("atr_period", 26)
    st.session_state["sort_logbias_ema"] = sort_cfg.get("ema_period", 20)
    st.session_state["sort_logbias_multiplier"] = sort_cfg.get("multiplier", 100)
    st.session_state["sort_std_window"] = sort_cfg.get("window", 20)
    st.session_state["sort_wdm_shift"] = sort_cfg.get("shift", 12)
    st.session_state["sort_wdm_smooth"] = sort_cfg.get("smooth", 3)
    st.session_state["drop_penalty"] = sort_cfg.get("drop_penalty", False)
    st.session_state["drop_threshold"] = sort_cfg.get("drop_threshold", 0.05) * 100

    # 买入
    buy_cfg = preset.get("buy", {})
    buy_mode = buy_cfg.get("mode", "switch")
    st.session_state["buy_mode"] = "逐条开关" if buy_mode == "switch" else "自由组合"
    if buy_mode == "switch":
        conditions = buy_cfg.get("conditions", [])
        # 先重置所有开关
        for p in BUY_SWITCH_PRESETS:
            st.session_state[f"buy_switch_{p['key']}"] = False
        # 再根据 conditions 启用
        for cond in conditions:
            for p in BUY_SWITCH_PRESETS:
                if cond.get("indicator") == p["indicator"] and cond.get("op") == p["op"]:
                    if p.get("has_param"):
                        st.session_state[f"buy_param_{p['key']}"] = cond.get("value", p["param_default"])
                    st.session_state[f"buy_switch_{p['key']}"] = True
                    break
        st.session_state["buy_free_groups"] = [{"logic": "AND", "rules": []}]
    else:
        # free 模式
        for p in BUY_SWITCH_PRESETS:
            st.session_state[f"buy_switch_{p['key']}"] = False
        groups = buy_cfg.get("condition_groups", [])
        st.session_state["buy_free_groups"] = groups if groups else [{"logic": "AND", "rules": []}]

    # 卖出
    sell_cfg = preset.get("sell", {})
    sell_mode = sell_cfg.get("mode", "switch")
    st.session_state["sell_mode"] = "逐条开关" if sell_mode == "switch" else "自由组合"
    st.session_state["sell_stop_loss"] = sell_cfg.get("stop_loss", 0) * 100
    st.session_state["sell_if_buy_fails"] = sell_cfg.get("sell_if_buy_fails", False)
    if sell_mode == "switch":
        conditions = sell_cfg.get("conditions", [])
        for p in SELL_SWITCH_PRESETS:
            st.session_state[f"sell_switch_{p['key']}"] = False
        for cond in conditions:
            for p in SELL_SWITCH_PRESETS:
                if cond.get("indicator") == p["indicator"] and cond.get("op") == p["op"]:
                    if p.get("has_param"):
                        raw_val = cond.get("value", p["param_default"])
                        # 日跌幅/涨幅参数需要转为百分比
                        if p["key"] == "daily_drop_gt" and isinstance(raw_val, (int, float)) and raw_val < 1:
                            raw_val = abs(raw_val) * 100
                        elif p["key"] == "return_20_gt" and isinstance(raw_val, (int, float)) and raw_val < 1:
                            raw_val = raw_val * 100
                        st.session_state[f"sell_param_{p['key']}"] = raw_val
                    st.session_state[f"sell_switch_{p['key']}"] = True
                    break
        st.session_state["sell_free_groups"] = [{"logic": "AND", "rules": []}]
    else:
        for p in SELL_SWITCH_PRESETS:
            st.session_state[f"sell_switch_{p['key']}"] = False
        groups = sell_cfg.get("condition_groups", [])
        st.session_state["sell_free_groups"] = groups if groups else [{"logic": "AND", "rules": []}]

    # 持仓
    pos_cfg = preset.get("position", {})
    mode_map = {"equal_weight": "等权", "single": "单标的", "incremental": "增量式"}
    st.session_state["position_mode"] = mode_map.get(pos_cfg.get("mode", "equal_weight"), "等权")
    st.session_state["max_holdings"] = pos_cfg.get("max_holdings", 5)
    st.session_state["position_pct"] = pos_cfg.get("position_pct", 0.20)
    st.session_state["rebalance_days"] = pos_cfg.get("rebalance_days", 2)

    # 基础配置（保存的策略可能包含这些字段）
    if "bond_ticker" in preset:
        bond_ticker = preset["bond_ticker"]
        st.session_state["cash_substitute"] = bond_ticker if bond_ticker else "cash"
    if "initial_capital" in preset:
        st.session_state["initial_capital"] = preset["initial_capital"]
    if "fee_rate" in preset:
        st.session_state["fee_rate"] = preset["fee_rate"]
    if "start_date" in preset:
        try:
            date_str = str(preset["start_date"])
            st.session_state["start_date"] = datetime.date.fromisoformat(date_str)
        except (ValueError, TypeError):
            pass

    st.session_state["_auto_run_backtest"] = True


def build_sort_config():
    """从 session_state 构建排序配置"""
    indicator = SORT_INDICATOR_OPTIONS.get(st.session_state.sort_indicator_label, "return_n")
    direction = "desc" if st.session_state.sort_direction == "降序" else "asc"

    config = {
        "indicator": indicator,
        "direction": direction,
        "drop_penalty": st.session_state.drop_penalty,
    }

    if indicator == "return_n":
        config["window"] = st.session_state.sort_window
    elif indicator == "momentum_score":
        config["window"] = st.session_state.sort_momentum_window
    elif indicator == "difv":
        config["ema_short"] = st.session_state.sort_ema_short
        config["ema_long"] = st.session_state.sort_ema_long
        config["atr_period"] = st.session_state.sort_atr_period
    elif indicator == "logbias":
        config["ema_period"] = st.session_state.sort_logbias_ema
        config["multiplier"] = st.session_state.sort_logbias_multiplier
    elif indicator == "std_momentum":
        config["window"] = st.session_state.sort_std_window
    elif indicator == "wdm_momentum":
        config["shift"] = st.session_state.sort_wdm_shift
        config["smooth"] = st.session_state.sort_wdm_smooth

    if st.session_state.drop_penalty:
        config["drop_threshold"] = st.session_state.drop_threshold / 100.0

    return config


def build_buy_config():
    """从 session_state 构建买入配置"""
    mode = "switch" if st.session_state.buy_mode == "逐条开关" else "free"

    if mode == "switch":
        conditions = []
        for preset in BUY_SWITCH_PRESETS:
            enabled = st.session_state.get(f"buy_switch_{preset['key']}", False)
            if not enabled:
                continue
            value = preset["value"]
            if preset.get("has_param"):
                value = st.session_state.get(f"buy_param_{preset['key']}", preset["param_default"])
            cond = {
                "indicator": preset["indicator"],
                "op": preset["op"],
                "value": value,
                "enabled": True,
                "name": preset["label"],
            }
            if preset.get("exclude"):
                cond["exclude"] = True
            conditions.append(cond)
        return {"mode": "switch", "conditions": conditions}
    else:
        groups = st.session_state.get("buy_free_groups", [])
        return {"mode": "free", "condition_groups": groups}


def build_sell_config():
    """从 session_state 构建卖出配置"""
    mode = "switch" if st.session_state.sell_mode == "逐条开关" else "free"

    if mode == "switch":
        conditions = []
        for preset in SELL_SWITCH_PRESETS:
            enabled = st.session_state.get(f"sell_switch_{preset['key']}", False)
            if not enabled:
                continue
            value = preset["value"]
            if preset.get("has_param"):
                value = st.session_state.get(f"sell_param_{preset['key']}", preset["param_default"])
                # 特殊处理：日跌幅阈值输入的是百分比，需要转小数
                if preset["key"] == "daily_drop_gt":
                    value = -value / 100.0
                elif preset["key"] == "return_20_gt":
                    value = value / 100.0
            cond = {
                "indicator": preset["indicator"],
                "op": preset["op"],
                "value": value,
                "enabled": True,
                "name": preset["label"],
            }
            if preset.get("exclude"):
                cond["exclude"] = True
            conditions.append(cond)
        return {
            "mode": "switch",
            "conditions": conditions,
            "stop_loss": st.session_state.sell_stop_loss / 100.0,
            "sell_if_buy_fails": st.session_state.sell_if_buy_fails,
        }
    else:
        groups = st.session_state.get("sell_free_groups", [])
        return {
            "mode": "free",
            "condition_groups": groups,
            "stop_loss": st.session_state.sell_stop_loss / 100.0,
            "sell_if_buy_fails": st.session_state.sell_if_buy_fails,
        }


def build_position_config():
    """从 session_state 构建持仓配置"""
    mode_map = {"等权": "equal_weight", "单标的": "single", "增量式": "incremental"}
    return {
        "mode": mode_map.get(st.session_state.position_mode, "equal_weight"),
        "max_holdings": st.session_state.max_holdings,
        "position_pct": st.session_state.position_pct,
        "rebalance_days": st.session_state.rebalance_days,
        "new_rank_limit": 0,
    }


def build_backtest_config():
    """从 session_state 构建完整回测配置"""
    selected = st.session_state.get("selected_tickers", [])
    cash_sub = st.session_state.get("cash_substitute", "511880.SH")
    bond_ticker = cash_sub if cash_sub != "cash" else None

    config = {
        "stock_tickers": selected,
        "bond_ticker": bond_ticker,
        "initial_capital": st.session_state.initial_capital,
        "fee_rate": st.session_state.fee_rate,
        "start_date": str(st.session_state.start_date),
        "sort": build_sort_config(),
        "buy": build_buy_config(),
        "sell": build_sell_config(),
        "position": build_position_config(),
    }
    return config


def collect_current_config():
    """收集当前界面上的所有配置（格式与PRESET_STRATEGIES中的配置一致）"""
    cash_sub = st.session_state.get("cash_substitute", "511880.SH")
    bond_ticker = cash_sub if cash_sub != "cash" else None
    return {
        "stock_tickers": list(st.session_state.get("selected_tickers", [])),
        "bond_ticker": bond_ticker,
        "initial_capital": st.session_state.get("initial_capital", 1000000),
        "fee_rate": st.session_state.get("fee_rate", 0.0001),
        "start_date": str(st.session_state.get("start_date", "2020-01-02")),
        "sort": build_sort_config(),
        "buy": build_buy_config(),
        "sell": build_sell_config(),
        "position": build_position_config(),
    }


def _summarize_buy_conditions():
    """生成买入条件摘要文本"""
    if st.session_state.get("buy_mode") == "逐条开关":
        parts = []
        for preset in BUY_SWITCH_PRESETS:
            enabled = st.session_state.get(f"buy_switch_{preset['key']}", False)
            if not enabled:
                continue
            label = preset["label"]
            if preset.get("has_param"):
                param_val = st.session_state.get(f"buy_param_{preset['key']}", preset["param_default"])
                if preset["key"] == "return_n_lt_threshold":
                    label = f"N日涨幅<{param_val*100:.0f}%"
                elif preset["key"] == "difv_lt_threshold":
                    label = f"difv<{param_val}"
                elif preset["key"] == "rank_le_n":
                    label = f"rank<={param_val}"
                elif preset["key"] == "new_rank_limit":
                    label = f"新入选排名<={param_val}"
            parts.append(label)
        return " AND ".join(parts) if parts else "无"
    else:
        groups = st.session_state.get("buy_free_groups", [])
        if not groups or all(len(g.get("rules", [])) == 0 for g in groups):
            return "无"
        return f"自由组合({len(groups)}组)"


def _summarize_sell_conditions():
    """生成卖出条件摘要文本"""
    parts = []
    stop_loss = st.session_state.get("sell_stop_loss", 0)
    if stop_loss > 0:
        parts.append(f"止损{stop_loss:.1f}%")
    if st.session_state.get("sell_if_buy_fails"):
        parts.append("不满足买入则卖出")
    if st.session_state.get("sell_mode") == "逐条开关":
        for preset in SELL_SWITCH_PRESETS:
            enabled = st.session_state.get(f"sell_switch_{preset['key']}", False)
            if not enabled:
                continue
            label = preset["label"]
            if preset.get("has_param"):
                param_val = st.session_state.get(f"sell_param_{preset['key']}", preset["param_default"])
                if preset["key"] == "rank_gt_n":
                    label = f"rank>{param_val}"
                elif preset["key"] == "daily_drop_gt":
                    label = f"日跌幅>{param_val}%"
                elif preset["key"] == "return_20_gt":
                    label = f"20日涨幅>{param_val}%"
            parts.append(label)
    else:
        groups = st.session_state.get("sell_free_groups", [])
        if groups and any(len(g.get("rules", [])) > 0 for g in groups):
            parts.append(f"自由组合({len(groups)}组)")
    return " OR ".join(parts) if parts else "无"


def get_config_summary():
    """生成当前配置的文本摘要"""
    lines = []
    # 股票池
    tickers = st.session_state.get("selected_tickers", [])
    names = [ETF_NAMES.get(t, t.split(".")[0]) for t in tickers]
    lines.append(f"- 股票池: {len(tickers)}只 ({', '.join(names[:5])}{'...' if len(names) > 5 else ''})")
    # 排序
    sort_ind = st.session_state.get("sort_indicator_label", "N日涨幅")
    sort_dir = st.session_state.get("sort_direction", "降序")
    lines.append(f"- 排序: {sort_ind} {sort_dir}")
    # 买入条件摘要
    buy_summary = _summarize_buy_conditions()
    lines.append(f"- 买入: {buy_summary}")
    # 卖出条件摘要
    sell_summary = _summarize_sell_conditions()
    lines.append(f"- 卖出: {sell_summary}")
    # 持仓
    pos_mode = st.session_state.get("position_mode", "等权")
    max_h = st.session_state.get("max_holdings", 5)
    pos_pct = st.session_state.get("position_pct", 0.20)
    rebal = st.session_state.get("rebalance_days", 2)
    lines.append(f"- 持仓: {pos_mode}{max_h}只, {pos_pct:.0%}比例, {rebal}日轮动")
    return "\n".join(lines)


def run_backtest_from_config(config):
    """执行回测并返回结果"""
    stock_tickers = config.get("stock_tickers", [])
    if not stock_tickers:
        return None

    # 构建 ticker 列表用于 build_data_dict
    ticker_dicts = []
    for thscode in stock_tickers:
        parts = thscode.split(".")
        if len(parts) == 2:
            ticker_dicts.append({"code": parts[0], "suffix": parts[1]})

    bond_ticker = config.get("bond_ticker")
    if bond_ticker:
        parts = bond_ticker.split(".")
        if len(parts) == 2:
            ticker_dicts.append({"code": parts[0], "suffix": parts[1]})

    start_date = config.get("start_date")

    with st.spinner("正在加载数据..."):
        data_dict = build_data_dict(ticker_dicts, start_date=start_date)

    if not data_dict:
        st.error("无法加载任何数据，请检查 pkl 目录和数据文件。")
        return None

    with st.spinner("正在计算指标..."):
        signals = calc_all_indicators(data_dict, config)

    with st.spinner("正在运行回测..."):
        result = run_backtest(data_dict, signals, config)

    return result


# ============================================================
#  初始化 session_state
# ============================================================
init_session_state_defaults()

# ============================================================
#  页面标题
# ============================================================
st.title("ETF轮动策略回测系统")

# ============================================================
#  侧边栏
# ============================================================
# 获取所有可用的 pkl 文件（提前构建映射，侧边栏和主区域都用）
_all_pkl_items = cached_scan_pkl_dir()
_thscode_to_label = {}
_label_to_thscode = {}
for _item in _all_pkl_items:
    _thscode = _item["thscode"]
    _label = format_ticker_label(_thscode)
    _thscode_to_label[_thscode] = _label
    _label_to_thscode[_label] = _thscode

with st.sidebar:
    st.header("策略配置")

    # ---- 1. 预设策略选择 ----
    st.subheader("预设策略")
    saved_strategies = load_saved_strategies()
    saved_names = list(saved_strategies.keys())
    # 构建选项列表：预设策略 + 分隔线 + 保存的策略
    preset_keys = list(PRESET_STRATEGIES.keys())
    if saved_names:
        all_preset_options = preset_keys + ["── 保存的策略 ──"] + saved_names
    else:
        all_preset_options = preset_keys
    current_preset_idx = all_preset_options.index(st.session_state.preset_name) if st.session_state.preset_name in all_preset_options else 0
    selected_preset = st.selectbox(
        "选择预设策略",
        all_preset_options,
        index=current_preset_idx,
        key="preset_selectbox",
    )
    if selected_preset != st.session_state.get("_last_preset", "自定义"):
        if selected_preset == "── 保存的策略 ──":
            st.session_state["_last_preset"] = selected_preset
        elif selected_preset != "自定义":
            if selected_preset in PRESET_STRATEGIES:
                apply_preset(selected_preset)
            elif selected_preset in saved_strategies:
                apply_preset(selected_preset, saved_strategies[selected_preset])
            st.session_state["_last_preset"] = selected_preset
            
            config = build_backtest_config()
            if config.get("stock_tickers"):
                with st.spinner("正在运行回测..."):
                    try:
                        result = run_backtest_from_config(config)
                        if result is not None:
                            st.session_state["backtest_result"] = result
                            st.session_state["backtest_config"] = config
                    except Exception as e:
                        st.error(f"回测出错：{e}")
            
            st.rerun()
        else:
            st.session_state["_last_preset"] = selected_preset
            st.rerun()

    st.divider()

    # ---- 2. 股票池选择（分组优化） ----
    st.subheader("股票池选择")

    # 分组选择 → 一键添加
    group_names = list(ETF_GROUPS.keys())
    selected_group = st.selectbox(
        "选择分组",
        ["（选择分组后点击添加）"] + group_names,
        key="etf_group_select",
    )
    col_add_group, col_clear_group = st.columns(2)
    with col_add_group:
        if st.button("➕ 添加该组", use_container_width=True, key="btn_add_group"):
            if selected_group in ETF_GROUPS:
                current_set = set(st.session_state.get("selected_tickers", []))
                new_tickers = current_set | set(ETF_GROUPS[selected_group])
                st.session_state.selected_tickers = sorted(new_tickers)
                st.rerun()
    with col_clear_group:
        if st.button("🗑️ 清空已选", use_container_width=True, key="btn_clear_group"):
            st.session_state.selected_tickers = []
            st.rerun()

    # 搜索框
    search_text = st.text_input("搜索ETF", value="", key="etf_search")

    # 当前已选标的用multiselect展示（可逐个增删）
    all_labels = list(_label_to_thscode.keys())
    if search_text:
        filtered_labels = [l for l in all_labels if search_text.upper() in l.upper()]
    else:
        filtered_labels = all_labels

    current_selected_labels = []
    for thscode in st.session_state.selected_tickers:
        label = _thscode_to_label.get(thscode, "")
        if label and label in filtered_labels:
            current_selected_labels.append(label)
    # 已选但不在filtered中的也要保留显示
    for thscode in st.session_state.selected_tickers:
        label = _thscode_to_label.get(thscode, "")
        if label and label not in current_selected_labels:
            current_selected_labels.append(label)

    selected_labels = st.multiselect(
        f"已选标的 ({len(st.session_state.selected_tickers)}只)",
        filtered_labels,
        default=current_selected_labels,
        key="stock_multiselect",
    )

    # 更新 session_state 中的选中 thscode
    st.session_state.selected_tickers = [_label_to_thscode[l] for l in selected_labels if l in _label_to_thscode]

    st.divider()

    # ---- 3. 基础配置 ----
    st.subheader("基础配置")

    st.session_state.start_date = st.date_input(
        "起始日期",
        value=st.session_state.start_date,
        key="start_date_input",
    )

    col_capital, col_fee = st.columns(2)
    with col_capital:
        st.session_state.initial_capital = st.number_input(
            "初始资金",
            min_value=10000,
            max_value=100000000,
            value=st.session_state.initial_capital,
            step=100000,
            key="initial_capital_input",
        )
    with col_fee:
        st.session_state.fee_rate = st.number_input(
            "手续费率",
            min_value=0.0,
            max_value=0.01,
            value=st.session_state.fee_rate,
            format="%.4f",
            key="fee_rate_input",
        )

    cash_sub_options = {"银华日利511880": "511880.SH", "纯现金": "cash"}
    cash_sub_labels = list(cash_sub_options.keys())
    current_cash_sub_label = "纯现金" if st.session_state.cash_substitute == "cash" else "银华日利511880"
    cash_sub_idx = cash_sub_labels.index(current_cash_sub_label) if current_cash_sub_label in cash_sub_labels else 0
    selected_cash_sub = st.selectbox(
        "空仓替代",
        cash_sub_labels,
        index=cash_sub_idx,
        key="cash_substitute_select",
    )
    st.session_state.cash_substitute = cash_sub_options[selected_cash_sub]

    st.divider()

    # ---- 4. 持仓配置 ----
    st.subheader("持仓配置")

    col_pos_mode, col_holdings = st.columns(2)
    with col_pos_mode:
        position_modes = ["等权", "单标的", "增量式"]
        pos_mode_idx = position_modes.index(st.session_state.position_mode) if st.session_state.position_mode in position_modes else 0
        st.session_state.position_mode = st.selectbox(
            "持仓模式",
            position_modes,
            index=pos_mode_idx,
            key="position_mode_select",
        )
    with col_holdings:
        st.session_state.max_holdings = st.number_input(
            "最大持仓数",
            min_value=1,
            max_value=20,
            value=st.session_state.max_holdings,
            key="max_holdings_input",
        )

    col_pct, col_rebal = st.columns(2)
    with col_pct:
        st.session_state.position_pct = st.number_input(
            "仓位比例",
            min_value=0.01,
            max_value=1.0,
            value=st.session_state.position_pct,
            step=0.05,
            format="%.2f",
            key="position_pct_input",
        )
    with col_rebal:
        st.session_state.rebalance_days = st.number_input(
            "轮动周期(日)",
            min_value=1,
            max_value=20,
            value=st.session_state.rebalance_days,
            key="rebalance_days_input",
        )

    st.divider()

    # ---- 5. 策略管理（折叠） ----
    with st.expander("策略管理（保存/加载/删除）"):
        strategy_save_name = st.text_input("策略名称（用于保存）", value="", key="strategy_save_name")

        if st.button("💾 保存当前策略", use_container_width=True):
            if not strategy_save_name.strip():
                st.warning("请输入策略名称！")
            else:
                config = collect_current_config()
                save_strategy(strategy_save_name.strip(), config)
                st.success(f"策略「{strategy_save_name.strip()}」已保存！")
                st.session_state["_last_preset"] = strategy_save_name.strip()
                st.rerun()

        saved_strategies_for_manage = load_saved_strategies()
        saved_strategy_names = list(saved_strategies_for_manage.keys())

        if saved_strategy_names:
            selected_saved_strategy = st.selectbox(
                "已保存的策略",
                saved_strategy_names,
                key="saved_strategy_select",
            )

            col_load, col_del = st.columns(2)
            with col_load:
                if st.button("📂 加载选中策略", use_container_width=True):
                    if selected_saved_strategy in saved_strategies_for_manage:
                        apply_preset(selected_saved_strategy, saved_strategies_for_manage[selected_saved_strategy])
                        st.session_state["_last_preset"] = selected_saved_strategy
                        st.rerun()
            with col_del:
                if st.button("🗑️ 删除选中策略", use_container_width=True):
                    delete_strategy(selected_saved_strategy)
                    st.success(f"策略「{selected_saved_strategy}」已删除！")
                    if st.session_state.get("preset_name") == selected_saved_strategy:
                        st.session_state["preset_name"] = "自定义"
                        st.session_state["_last_preset"] = "自定义"
                    st.rerun()
        else:
            st.info("暂无保存的策略")

# ============================================================
#  主区域 —— Tabs
# ============================================================
tab1, tab2, tab3, tab4 = st.tabs(["轮动排序规格", "买入条件", "卖出条件", "回测结果"])

# ============================================================
#  Tab1: 轮动排序规格
# ============================================================
with tab1:
    st.header("轮动排序规格")

    col_sort_1, col_sort_2 = st.columns(2)

    with col_sort_1:
        sort_labels = list(SORT_INDICATOR_OPTIONS.keys())
        current_sort_idx = sort_labels.index(st.session_state.sort_indicator_label) if st.session_state.sort_indicator_label in sort_labels else 0
        st.session_state.sort_indicator_label = st.selectbox(
            "排序指标",
            sort_labels,
            index=current_sort_idx,
            key="sort_indicator_select",
        )

        direction_options = ["降序", "升序"]
        dir_idx = direction_options.index(st.session_state.sort_direction) if st.session_state.sort_direction in direction_options else 0
        st.session_state.sort_direction = st.radio(
            "排序方向",
            direction_options,
            index=dir_idx,
            horizontal=True,
            key="sort_direction_radio",
        )

    with col_sort_2:
        # 根据排序指标动态显示参数
        indicator = SORT_INDICATOR_OPTIONS.get(st.session_state.sort_indicator_label, "return_n")

        if indicator == "return_n":
            st.session_state.sort_window = st.number_input(
                "窗口天数",
                min_value=2,
                max_value=250,
                value=st.session_state.sort_window,
                key="sort_window_input",
            )
        elif indicator == "momentum_score":
            st.session_state.sort_momentum_window = st.number_input(
                "计算天数",
                min_value=5,
                max_value=250,
                value=st.session_state.sort_momentum_window,
                key="sort_momentum_window_input",
            )
        elif indicator == "difv":
            st.session_state.sort_ema_short = st.number_input(
                "EMA短周期",
                min_value=2,
                max_value=100,
                value=st.session_state.sort_ema_short,
                key="sort_ema_short_input",
            )
            st.session_state.sort_ema_long = st.number_input(
                "EMA长周期",
                min_value=5,
                max_value=200,
                value=st.session_state.sort_ema_long,
                key="sort_ema_long_input",
            )
            st.session_state.sort_atr_period = st.number_input(
                "ATR周期",
                min_value=5,
                max_value=200,
                value=st.session_state.sort_atr_period,
                key="sort_atr_period_input",
            )
        elif indicator == "logbias":
            st.session_state.sort_logbias_ema = st.number_input(
                "EMA周期",
                min_value=2,
                max_value=200,
                value=st.session_state.sort_logbias_ema,
                key="sort_logbias_ema_input",
            )
            st.session_state.sort_logbias_multiplier = st.number_input(
                "乘数",
                min_value=1,
                max_value=1000,
                value=st.session_state.sort_logbias_multiplier,
                key="sort_logbias_multiplier_input",
            )
        elif indicator == "std_momentum":
            st.session_state.sort_std_window = st.number_input(
                "窗口",
                min_value=2,
                max_value=250,
                value=st.session_state.sort_std_window,
                key="sort_std_window_input",
            )
        elif indicator == "wdm_momentum":
            st.session_state.sort_wdm_shift = st.number_input(
                "shift",
                min_value=1,
                max_value=100,
                value=st.session_state.sort_wdm_shift,
                key="sort_wdm_shift_input",
            )
            st.session_state.sort_wdm_smooth = st.number_input(
                "smooth",
                min_value=1,
                max_value=20,
                value=st.session_state.sort_wdm_smooth,
                key="sort_wdm_smooth_input",
            )

    # 大跌惩罚
    st.divider()
    col_penalty_1, col_penalty_2 = st.columns([1, 3])
    with col_penalty_1:
        st.session_state.drop_penalty = st.checkbox(
            "大跌惩罚",
            value=st.session_state.drop_penalty,
            key="drop_penalty_checkbox",
        )
    with col_penalty_2:
        if st.session_state.drop_penalty:
            st.session_state.drop_threshold = st.number_input(
                "大跌阈值(%)",
                min_value=1.0,
                max_value=20.0,
                value=st.session_state.drop_threshold,
                step=0.5,
                format="%.1f",
                key="drop_threshold_input",
            )


# ============================================================
#  Tab2: 买入条件
# ============================================================
with tab2:
    st.header("买入条件")

    buy_mode_options = ["逐条开关", "自由组合"]
    buy_mode_idx = buy_mode_options.index(st.session_state.buy_mode) if st.session_state.buy_mode in buy_mode_options else 0
    st.session_state.buy_mode = st.radio(
        "模式切换",
        buy_mode_options,
        index=buy_mode_idx,
        horizontal=True,
        key="buy_mode_radio",
    )

    if st.session_state.buy_mode == "逐条开关":
        st.subheader("逐条开关模式")
        st.write("勾选启用对应条件，所有启用条件取 AND 逻辑")

        for preset in BUY_SWITCH_PRESETS:
            c1, c2 = st.columns([4, 1])
            with c1:
                enabled = st.checkbox(
                    preset['label'],
                    value=st.session_state.get(f"buy_switch_{preset['key']}", preset["default"]),
                    key=f"buy_switch_cb_{preset['key']}",
                )
                st.session_state[f"buy_switch_{preset['key']}"] = enabled
            with c2:
                if preset.get("has_param") and enabled:
                    param_val = st.number_input(
                        "阈值",
                        value=st.session_state.get(f"buy_param_{preset['key']}", preset["param_default"]),
                        key=f"buy_param_input_{preset['key']}",
                        format="%.4f" if isinstance(preset["param_default"], float) else "%d",
                        label_visibility="collapsed",
                    )
                    st.session_state[f"buy_param_{preset['key']}"] = param_val

    else:
        # 自由组合模式
        st.subheader("自由组合模式")
        st.write("组内规则按逻辑(AND/OR)求值，组间OR。即：任一组满足即通过。")

        # 初始化 free groups
        if "buy_free_groups" not in st.session_state or not st.session_state.buy_free_groups:
            st.session_state.buy_free_groups = [{"logic": "AND", "rules": []}]

        groups = st.session_state.buy_free_groups

        for g_idx, group in enumerate(groups):
            st.markdown(f"#### 条件组 {g_idx + 1}")

            col_logic, col_del_group = st.columns([3, 1])
            with col_logic:
                logic_options = ["AND", "OR"]
                logic_val = group.get("logic", "AND")
                logic_idx = logic_options.index(logic_val) if logic_val in logic_options else 0
                group["logic"] = st.selectbox(
                    f"组内逻辑",
                    logic_options,
                    index=logic_idx,
                    key=f"buy_group_logic_{g_idx}",
                )
            with col_del_group:
                if len(groups) > 1:
                    if st.button("删除此组", key=f"buy_del_group_{g_idx}"):
                        groups.pop(g_idx)
                        st.session_state.buy_free_groups = groups
                        st.rerun()

            # 规则列表
            rules = group.get("rules", [])
            for r_idx, rule in enumerate(rules):
                col_rule, col_del_rule = st.columns([5, 1])
                with col_rule:
                    r_cols = st.columns(3)
                    with r_cols[0]:
                        indicator_val = rule.get("indicator", "close")
                        ind_idx = FREE_INDICATOR_OPTIONS.index(indicator_val) if indicator_val in FREE_INDICATOR_OPTIONS else 0
                        rule["indicator"] = st.selectbox(
                            "指标",
                            FREE_INDICATOR_OPTIONS,
                            index=ind_idx,
                            key=f"buy_rule_ind_{g_idx}_{r_idx}",
                        )
                    with r_cols[1]:
                        op_val = rule.get("op", ">")
                        op_idx = FREE_OPERATOR_OPTIONS.index(op_val) if op_val in FREE_OPERATOR_OPTIONS else 0
                        rule["op"] = st.selectbox(
                            "运算符",
                            FREE_OPERATOR_OPTIONS,
                            index=op_idx,
                            key=f"buy_rule_op_{g_idx}_{r_idx}",
                        )
                    with r_cols[2]:
                        if rule["op"] in ("is_true", "is_false"):
                            rule["value"] = 0
                            st.write("(布尔判断，无需阈值)")
                        else:
                            rule["value"] = st.number_input(
                                "阈值",
                                value=float(rule.get("value", 0)),
                                key=f"buy_rule_val_{g_idx}_{r_idx}",
                                format="%.4f",
                            )
                with col_del_rule:
                    if st.button("×", key=f"buy_del_rule_{g_idx}_{r_idx}"):
                        rules.pop(r_idx)
                        group["rules"] = rules
                        st.rerun()

            # 添加规则按钮
            if st.button("+ 添加规则", key=f"buy_add_rule_{g_idx}"):
                rules.append({"indicator": "close", "op": ">", "value": 0})
                group["rules"] = rules
                st.rerun()

            st.divider()

        # 添加条件组按钮
        if st.button("+ 添加条件组", key="buy_add_group"):
            groups.append({"logic": "AND", "rules": []})
            st.session_state.buy_free_groups = groups
            st.rerun()


# ============================================================
#  Tab3: 卖出条件
# ============================================================
with tab3:
    st.header("卖出条件")

    sell_mode_options = ["逐条开关", "自由组合"]
    sell_mode_idx = sell_mode_options.index(st.session_state.sell_mode) if st.session_state.sell_mode in sell_mode_options else 0
    st.session_state.sell_mode = st.radio(
        "模式切换",
        sell_mode_options,
        index=sell_mode_idx,
        horizontal=True,
        key="sell_mode_radio",
    )

    # 止损 + 不满足买入条件则卖出
    col_extra1, col_extra2 = st.columns(2)
    with col_extra1:
        st.session_state.sell_stop_loss = st.number_input(
            "止损比例(%)",
            min_value=0.0,
            max_value=50.0,
            value=st.session_state.sell_stop_loss,
            step=0.5,
            format="%.1f",
            key="sell_stop_loss_input",
        )
    with col_extra2:
        st.session_state.sell_if_buy_fails = st.checkbox(
            "不满足买入条件则卖出",
            value=st.session_state.sell_if_buy_fails,
            key="sell_if_buy_fails_checkbox",
        )

    st.divider()

    if st.session_state.sell_mode == "逐条开关":
        st.subheader("逐条开关模式")
        st.write("勾选启用对应条件，任一启用条件满足即卖出（OR 逻辑）")

        for preset in SELL_SWITCH_PRESETS:
            c1, c2 = st.columns([4, 1])
            with c1:
                enabled = st.checkbox(
                    preset['label'],
                    value=st.session_state.get(f"sell_switch_{preset['key']}", preset["default"]),
                    key=f"sell_switch_cb_{preset['key']}",
                )
                st.session_state[f"sell_switch_{preset['key']}"] = enabled
            with c2:
                if preset.get("has_param") and enabled:
                    param_val = st.session_state.get(f"sell_param_{preset['key']}", preset["param_default"])
                    # 如果param_val是原始小数(如-0.03)，转为百分比(如3.0)
                    if preset["key"] == "daily_drop_gt" and isinstance(param_val, (int, float)) and param_val < 1:
                        param_val = abs(param_val) * 100
                    # 日跌幅和涨幅的参数显示为百分比
                    if preset["key"] == "daily_drop_gt":
                        param_val = max(0.5, min(20.0, float(param_val)))
                        st.session_state[f"sell_param_{preset['key']}"] = st.number_input(
                            "跌幅阈值(%)",
                            min_value=0.5,
                            max_value=20.0,
                            value=param_val,
                            step=0.5,
                            format="%.1f",
                            key=f"sell_param_input_{preset['key']}",
                            label_visibility="collapsed",
                        )
                    elif preset["key"] == "return_20_gt":
                        if isinstance(param_val, (int, float)) and param_val < 1:
                            param_val = param_val * 100
                        param_val = max(1.0, min(100.0, float(param_val)))
                        st.session_state[f"sell_param_{preset['key']}"] = st.number_input(
                            "涨幅阈值(%)",
                            min_value=1.0,
                            max_value=100.0,
                            value=param_val,
                            step=1.0,
                            format="%.1f",
                            key=f"sell_param_input_{preset['key']}",
                            label_visibility="collapsed",
                        )
                    else:
                        st.session_state[f"sell_param_{preset['key']}"] = st.number_input(
                            "阈值",
                            value=float(param_val),
                            key=f"sell_param_input_{preset['key']}",
                            format="%.4f" if isinstance(preset["param_default"], float) else "%d",
                            label_visibility="collapsed",
                        )

    else:
        # 自由组合模式
        st.subheader("自由组合模式")
        st.write("组内规则按逻辑(AND/OR)求值，组间OR。即：任一组满足即卖出。")

        if "sell_free_groups" not in st.session_state or not st.session_state.sell_free_groups:
            st.session_state.sell_free_groups = [{"logic": "AND", "rules": []}]

        groups = st.session_state.sell_free_groups

        for g_idx, group in enumerate(groups):
            st.markdown(f"#### 条件组 {g_idx + 1}")

            col_logic, col_del_group = st.columns([3, 1])
            with col_logic:
                logic_options = ["AND", "OR"]
                logic_val = group.get("logic", "AND")
                logic_idx = logic_options.index(logic_val) if logic_val in logic_options else 0
                group["logic"] = st.selectbox(
                    f"组内逻辑",
                    logic_options,
                    index=logic_idx,
                    key=f"sell_group_logic_{g_idx}",
                )
            with col_del_group:
                if len(groups) > 1:
                    if st.button("删除此组", key=f"sell_del_group_{g_idx}"):
                        groups.pop(g_idx)
                        st.session_state.sell_free_groups = groups
                        st.rerun()

            rules = group.get("rules", [])
            for r_idx, rule in enumerate(rules):
                col_rule, col_del_rule = st.columns([5, 1])
                with col_rule:
                    r_cols = st.columns(3)
                    with r_cols[0]:
                        indicator_val = rule.get("indicator", "close")
                        ind_idx = FREE_INDICATOR_OPTIONS.index(indicator_val) if indicator_val in FREE_INDICATOR_OPTIONS else 0
                        rule["indicator"] = st.selectbox(
                            "指标",
                            FREE_INDICATOR_OPTIONS,
                            index=ind_idx,
                            key=f"sell_rule_ind_{g_idx}_{r_idx}",
                        )
                    with r_cols[1]:
                        op_val = rule.get("op", ">")
                        op_idx = FREE_OPERATOR_OPTIONS.index(op_val) if op_val in FREE_OPERATOR_OPTIONS else 0
                        rule["op"] = st.selectbox(
                            "运算符",
                            FREE_OPERATOR_OPTIONS,
                            index=op_idx,
                            key=f"sell_rule_op_{g_idx}_{r_idx}",
                        )
                    with r_cols[2]:
                        if rule["op"] in ("is_true", "is_false"):
                            rule["value"] = 0
                            st.write("(布尔判断，无需阈值)")
                        else:
                            rule["value"] = st.number_input(
                                "阈值",
                                value=float(rule.get("value", 0)),
                                key=f"sell_rule_val_{g_idx}_{r_idx}",
                                format="%.4f",
                            )
                with col_del_rule:
                    if st.button("×", key=f"sell_del_rule_{g_idx}_{r_idx}"):
                        rules.pop(r_idx)
                        group["rules"] = rules
                        st.rerun()

            if st.button("+ 添加规则", key=f"sell_add_rule_{g_idx}"):
                rules.append({"indicator": "close", "op": "<", "value": 0})
                group["rules"] = rules
                st.rerun()

            st.divider()

        if st.button("+ 添加条件组", key="sell_add_group"):
            groups.append({"logic": "AND", "rules": []})
            st.session_state.sell_free_groups = groups
            st.rerun()


# ============================================================
#  Tab4: 回测结果
# ============================================================
with tab4:
    st.header("回测结果")

    # 配置概要
    with st.expander("📋 当前配置概要", expanded=True):
        st.code(get_config_summary())

    # 醒目的运行按钮（主区域顶部）
    run_btn_main = st.button("🚀 运行回测", type="primary", use_container_width=True, key="run_backtest_main")

    # 检查是否需要自动运行回测
    auto_run = st.session_state.get("_auto_run_backtest", False)
    if auto_run:
        st.session_state["_auto_run_backtest"] = False

    # 运行回测（主区域按钮或自动触发）
    if run_btn_main or auto_run:
        config = build_backtest_config()
        if not config.get("stock_tickers"):
            st.warning("请先选择股票池中的标的！")
        else:
            try:
                result = run_backtest_from_config(config)
                if result is not None:
                    st.session_state["backtest_result"] = result
                    st.session_state["backtest_config"] = config
            except Exception as e:
                st.error(f"回测出错：{e}")
                st.code(traceback.format_exc())

    # 显示结果
    if "backtest_result" in st.session_state:
        result = st.session_state["backtest_result"]
        nav_df = result.get("nav_df", pd.DataFrame())
        trade_log = result.get("trade_log", [])

        if nav_df.empty:
            st.warning("回测结果为空，请检查参数设置。")
        else:
            # 绩效卡片
            perf = compute_performance(nav_df)

            col1, col2, col3, col4, col5 = st.columns(5)
            with col1:
                st.metric("总收益率", f"{perf['total_return']:.2f}%")
            with col2:
                st.metric("年化收益率", f"{perf['annual_return']:.2f}%")
            with col3:
                st.metric("最大回撤", f"{perf['max_dd']:.2f}%")
            with col4:
                st.metric("夏普比率", f"{perf['sharpe']:.2f}")
            with col5:
                st.metric("卡尔玛比率", f"{perf['calmar']:.2f}")

            st.divider()

            # 净值曲线图
            st.subheader("净值曲线")
            try:
                fig_nav = plot_nav_curve(nav_df)
                st.pyplot(fig_nav)
            except Exception as e:
                st.error(f"绘制净值曲线失败：{e}")

            # 回撤图
            st.subheader("回撤图")
            try:
                fig_dd = plot_drawdown(nav_df)
                st.pyplot(fig_dd)
            except Exception as e:
                st.error(f"绘制回撤图失败：{e}")

            st.divider()

            # 年度收益表
            st.subheader("年度收益表")
            try:
                yearly_df = compute_yearly_returns(nav_df)
                if not yearly_df.empty:
                    # 格式化显示
                    display_df = yearly_df.copy()
                    display_df.columns = ["年份", "收益率(%)", "最大回撤(%)"]
                    st.dataframe(display_df, use_container_width=True, hide_index=True)
                else:
                    st.info("无年度收益数据")
            except Exception as e:
                st.error(f"计算年度收益失败：{e}")

            st.divider()

            # 交易记录表
            st.subheader("交易记录")
            if trade_log:
                trade_df = pd.DataFrame(trade_log)

                # 格式化显示
                display_trade = trade_df.copy()
                if 'date' in display_trade.columns:
                    display_trade['date'] = display_trade['date'].astype(str)
                if 'price' in display_trade.columns:
                    display_trade['price'] = display_trade['price'].round(4)
                if 'value' in display_trade.columns:
                    display_trade['value'] = display_trade['value'].round(2)
                if 'fee' in display_trade.columns:
                    display_trade['fee'] = display_trade['fee'].round(2)
                if 'pnl_pct' in display_trade.columns:
                    display_trade['pnl_pct'] = display_trade['pnl_pct'].round(2)
                if 'shares' in display_trade.columns:
                    display_trade['shares'] = display_trade['shares'].round(0)

                # 中文列名映射
                col_rename = {
                    'date': '日期',
                    'ticker': '代码',
                    'name': '名称',
                    'action': '操作',
                    'price': '价格',
                    'shares': '数量',
                    'value': '金额',
                    'fee': '手续费',
                    'pnl_pct': '盈亏(%)',
                    'hold_days': '持仓天数',
                    'reason': '原因',
                }
                display_trade = display_trade.rename(columns={k: v for k, v in col_rename.items() if k in display_trade.columns})

                st.dataframe(display_trade, use_container_width=True, hide_index=True)

                # CSV 下载
                csv_buffer = io.StringIO()
                trade_df.to_csv(csv_buffer, index=False, encoding='utf-8-sig')
                csv_data = csv_buffer.getvalue()

                st.download_button(
                    label="📥 下载交易记录 CSV",
                    data=csv_data,
                    file_name="trade_log.csv",
                    mime="text/csv",
                )
            else:
                st.info("暂无交易记录")

            # ====== 生成QMT实盘文件 ======
            st.divider()
            st.subheader("生成QMT实盘文件")
            st.caption("将当前策略配置生成可直接在QMT中运行的完整双模式py文件（回测+实盘一体化）")

            col_q1, col_q2 = st.columns(2)
            with col_q1:
                qmt_name = st.text_input("策略名称", value="自定义轮动策略", key="qmt_name")
                qmt_account = st.text_input("QMT账号", value="520000249836", key="qmt_account")
                qmt_capital = st.number_input("实盘资金(元)", value=10000.0, min_value=1000.0, key="qmt_capital")
            with col_q2:
                qmt_dir = st.text_input("输出目录", value=r"C:\自定义策略", key="qmt_dir")
                qmt_run_mode = st.selectbox("运行模式", ["live", "backtest"], index=0,
                                            format_func=lambda x: "实盘(live)" if x == "live" else "回测(backtest)",
                                            key="qmt_run_mode")

            if st.button("生成QMT实盘文件", type="primary", use_container_width=True):
                config = st.session_state.get("backtest_config", {})
                if not config.get("stock_tickers"):
                    st.warning("请先运行回测！")
                else:
                    with st.spinner("正在生成QMT文件..."):
                        try:
                            from qmt_generator import generate_qmt_file
                            os.makedirs(qmt_dir, exist_ok=True)
                            output_path = os.path.join(qmt_dir, f"{qmt_name}.py")
                            generate_qmt_file(config, output_path, qmt_name,
                                              account_id=qmt_account,
                                              real_capital=qmt_capital,
                                              script_dir=qmt_dir,
                                              run_mode=qmt_run_mode)
                            st.success(f"QMT文件已生成: {output_path}")

                            with open(output_path, 'r', encoding='utf-8') as f:
                                file_content = f.read()
                            st.download_button(
                                label="下载py文件",
                                data=file_content,
                                file_name=f"{qmt_name}.py",
                                mime="text/x-python",
                                use_container_width=True,
                            )
                            st.info(f"文件大小: {len(file_content)} 字符 | {file_content.count(chr(10))} 行")
                        except Exception as e:
                            st.error(f"生成失败: {e}")

            # 附加信息
            st.divider()
            with st.expander("回测配置详情"):
                if "backtest_config" in st.session_state:
                    config = st.session_state["backtest_config"]
                    st.json(config, expanded=False)
    else:
        st.info("请配置参数后点击上方 **🚀 运行回测** 按钮开始回测")
