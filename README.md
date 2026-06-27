# ETF轮动策略回测系统（云端版）

> 基于 Flask + Streamlit 的 ETF/LOF 轮动策略回测 Web 系统，支持 DIFv 轮动、五斗米轮动、定投组合、LOF 轮动等 10+ 种策略。

## 快速开始

### 1. 本地运行（数据已准备好的情况下）

```bash
# Streamlit 版（推荐）
streamlit run streamlit_app.py

# Flask 版
python app.py
# 浏览器打开 http://localhost:8001
```

### 2. 部署到云端

详见 [DEPLOY.md](./DEPLOY.md) 部署指南，推荐部署到 **Streamlit Cloud**（完全免费）。

**快速步骤：**
1. `python prepare_data.py` — 复制本地数据到项目目录
2. 推送到 GitHub 仓库
3. 在 [Streamlit Cloud](https://streamlit.io/cloud) 一键部署

## 项目结构

```
backtest_cloud/
├── app.py                    # Flask 版（含 API + 内嵌前端）
├── streamlit_app.py          # Streamlit 版（推荐部署）
├── requirements.txt          # Python 依赖
├── prepare_data.py           # 数据准备脚本
├── DEPLOY.md                 # 云端部署详细指南
├── data/ETF/1d/             # ← 你的 pkl 数据文件
└── engine/                   # 回测引擎核心
    ├── data_loader.py        # 数据加载（支持环境变量路径）
    ├── indicators.py         # 技术指标计算
    ├── backtester.py         # 回测逻辑
    └── performance.py        # 绩效分析与可视化
```

## 支持的策略

| 策略 | 说明 |
|------|------|
| 全品类 DIFv 轮动 | 多标的等权轮动，DIF/ATR 动量排名 |
| 五斗米动量轮动 | 单标的轮动，动量+布林带突破 |
| 定投+轮动组合 | 定投5品种+全品类轮动 |
| 自定义策略 | 自选标的+参数 |
| 懂懂定投 | 5品种周定投，单笔50%止盈 |
| 价值平均定投 | 目标市值线性增长 |
| 精选 LOF 轮动 | 5只LOF单标的轮动 |
| 科技成长 DIFv 轮动 | 26只科技ETF增量式轮动 |
| DIFv 动量轮动 | 8只ETF增量式轮动 |
| RSRS 动量轮动 | 对数价格回归+RSRS强度 |

## 数据来源

- 本地 pkl 数据（通过 QMT 系统下载）
- 支持环境变量 `PKL_DIR` 自定义数据路径

## 部署平台

- [Streamlit Cloud](https://streamlit.io/cloud) ⭐ 推荐
- [Render.com](https://render.com)
- [PythonAnywhere](https://www.pythonanywhere.com)

## License

个人自用，欢迎 fork 改造。
