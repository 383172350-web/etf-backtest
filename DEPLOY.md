# ETF轮动策略回测系统 — 云端部署指南

> 本指南将帮助你将本地回测系统部署到**免费的**云平台上，随时随地访问。数据大小约 62MB，完全适合云端部署。

---

## 方案对比

| 平台 | 应用类型 | 免费额度 | 休眠策略 | 推荐度 |
|------|----------|----------|----------|--------|
| **Streamlit Cloud** | `streamlit_app.py` | 1GB内存/1CPU | 不限制 | ⭐⭐⭐ 首选 |
| **Render.com** | `app.py` (Flask) | 512MB/0.1CPU | 15分钟无访问休眠 | ⭐⭐ 备选 |
| **PythonAnywhere** | `app.py` (Flask) | 512MB | 持续运行 | ⭐⭐ 备选 |

> **推荐**：使用 **Streamlit Cloud** 部署 `streamlit_app.py`，界面更友好，免费额度充足，无需信用卡。

---

## 第一步：准备数据（关键！）

⚠️ 你的回测系统依赖本地 `D:\qmt_data\ETF\1d` 目录下的 pkl 数据文件（约62MB）。部署到云端前，需要将这些数据复制到项目中。

### 方法：一键复制数据

```bash
# 1. 进入部署目录
cd backtest_cloud

# 2. 运行数据准备脚本（自动将本地 pkl 数据复制到项目目录）
python prepare_data.py
```

如果脚本中的路径不对，你可以手动复制：

```bash
# 将 D:\qmt_data\ETF\1d 下的所有 .pkl 文件复制到 backtest_cloud/data/ETF/1d/
```

复制完成后，目录结构如下：

```
backtest_cloud/
├── app.py                    # Flask 版（API + 前端）
├── streamlit_app.py          # Streamlit 版（推荐）
├── requirements.txt          # Python 依赖
├── prepare_data.py           # 数据准备脚本
├── data/
│   └── ETF/
│       └── 1d/               # ← 你的 pkl 数据文件在这里
│           ├── 510300_SH_1d.pkl
│           ├── 159949_SZ_1d.pkl
│           └── ...
├── engine/                   # 回测引擎核心
│   ├── __init__.py
│   ├── data_loader.py
│   ├── indicators.py
│   ├── backtester.py
│   └── performance.py
└── .streamlit/
    └── config.toml           # Streamlit 配置
```

---

## 第二步：创建 GitHub 仓库

云端部署需要从 GitHub 仓库拉取代码。

1. 打开 https://github.com/new 创建一个新仓库
2. 仓库名：`etf-backtest-cloud`（或任意名称）
3. 选择 **Public**（公开）或 **Private**（私密，Streamlit Cloud 支持）
4. 不要初始化 README，不要添加 .gitignore

### 将本地代码推送到 GitHub

```bash
# 1. 进入部署目录
cd backtest_cloud

# 2. 初始化 Git 仓库
git init

# 3. 添加所有文件
git add .

# 4. 提交
git commit -m "Initial commit: ETF backtest cloud deployment"

# 5. 添加远程仓库（替换为你的实际地址）
git remote add origin https://github.com/你的用户名/etf-backtest-cloud.git

# 6. 推送代码
git branch -M main
git push -u origin main
```

> **注意**：如果数据文件太多导致 push 失败，GitHub 有 100MB 单文件限制。你的 pkl 文件都是小文件，通常没问题。如果总大小超过 100MB，建议删除不用的 ETF 数据，只保留你需要的品种。

---

## 方案 A：部署到 Streamlit Cloud（推荐）

Streamlit Cloud 是专为 Streamlit 应用设计的免费托管平台。

### 1. 注册 Streamlit Cloud

- 打开 https://streamlit.io/cloud
- 用 GitHub 账号登录（免费）

### 2. 创建新应用

1. 点击 **"New app"**
2. 选择你的 GitHub 仓库：`etf-backtest-cloud`
3. 分支选择：`main`
4. 主文件路径：`streamlit_app.py`
5. 点击 **Deploy**

### 3. 等待部署完成

- 首次部署需要 2-5 分钟（需要安装依赖）
- 部署成功后，你会获得一个 URL：`https://xxx-xxx.streamlit.app`

### 4. 访问你的回测系统

- 点击 URL 即可访问
- 支持手机、平板、电脑访问

### 5. 自定义域名（可选）

在 Streamlit Cloud 设置中可以绑定自定义域名。

---

## 方案 B：部署到 Render.com（Flask 版）

如果你更喜欢 Flask 版本，可以部署到 Render.com。

### 1. 注册 Render.com

- 打开 https://render.com
- 用 GitHub 账号注册（免费，不需要信用卡）

### 2. 创建 Web Service

1. 点击 **"New +" → "Web Service"**
2. 选择你的 GitHub 仓库：`etf-backtest-cloud`
3. 配置如下：
   - **Name**: `etf-backtest`
   - **Region**: 选择离你近的（如 Singapore）
   - **Branch**: `main`
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app --bind 0.0.0.0:$PORT`
4. 选择 **Free** 计划
5. 点击 **Create Web Service**

### 3. 添加 gunicorn 到依赖

修改 `requirements.txt`，添加 `gunicorn`：

```
# 添加这一行
gunicorn>=21.0.0
```

然后重新提交到 GitHub：

```bash
git add requirements.txt
git commit -m "Add gunicorn for Render.com"
git push
```

Render 会自动重新部署。

> ⚠️ **注意**：Render 免费版会在 15 分钟无访问后休眠，首次访问需要等待 30 秒唤醒。

---

## 方案 C：部署到 PythonAnywhere

PythonAnywhere 提供免费的持续运行环境。

### 1. 注册

- 打开 https://www.pythonanywhere.com
- 注册免费账号

### 2. 上传代码

1. 进入 **Files** 页面
2. 创建目录：`etf-backtest`
3. 上传所有文件（包括 data/ETF/1d/ 下的 pkl 文件）

### 3. 创建虚拟环境并安装依赖

在 Bash console 中执行：

```bash
cd ~/etf-backtest
python3.10 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 4. 创建 Web 应用

1. 进入 **Web** 页面
2. 点击 **Add a new web app**
3. 选择 **Flask** 和 **Python 3.10**
4. 配置 WSGI 文件，修改路径指向你的 `app.py`

---

## 更新数据的方法

云端部署后，你的数据是静态的。如果需要更新到最新行情：

### 方法 1：手动更新（推荐）

1. 在本地运行 QMT 下载最新数据
2. 运行 `python prepare_data.py` 复制新数据
3. 提交并推送：

```bash
git add data/ETF/1d/
git commit -m "Update data to $(date +%Y-%m-%d)"
git push
```

Streamlit Cloud / Render 会自动重新部署。

### 方法 2：使用 GitHub Actions 自动更新（高级）

可以配置 GitHub Actions 定时运行数据更新脚本（需要在线数据源支持）。

---

## 常见问题

### Q1: 部署后提示 "找不到数据文件"？

- 检查 `data/ETF/1d/` 目录是否已上传到 GitHub
- 在 GitHub 仓库页面确认文件存在
- 检查文件名是否正确（格式：`{code}_{suffix}_1d.pkl`）

### Q2: 部署失败，内存不足？

- Streamlit Cloud 免费版有 1GB 内存限制
- 如果数据太多，可以删除不用的 ETF 品种，只保留需要的
- 或者使用 `PKL_DIR` 环境变量指定数据目录（支持 Streamlit Cloud Secrets）

### Q3: 如何只保留需要的 ETF 数据？

根据你的策略配置，通常只需要保留以下品种（约20-30个文件）：

- 宽基：510300, 510500, 159915, 588000, 512100
- 跨境：513100, 513050, 513500, 513030, 513520
- 商品：518880, 501018, 159985, 159980, 159981
- 债券：511880
- 行业：根据你的策略选择

### Q4: 部署后访问很慢？

- Render 免费版需要唤醒时间（30秒左右），这是正常的
- Streamlit Cloud 通常不需要唤醒，但首次加载也需要安装依赖
- 建议绑定自定义域名并使用 CDN 加速

### Q5: 数据敏感不想公开？

- Streamlit Cloud 支持从 **Private** 仓库部署
- 或者使用 Streamlit Cloud 的 Secrets 功能存储数据路径

---

## 技术说明

### 代码修改内容

为了让项目能在云端运行，做了以下适配：

1. **engine/data_loader.py**：将硬编码路径 `D:\qmt_data\ETF\1d` 改为优先读取 `PKL_DIR` 环境变量，默认使用相对路径 `data/ETF/1d`
2. **app.py**：同上，数据路径改为环境变量 + 相对路径
3. **新增文件**：
   - `requirements.txt`：列出所有依赖
   - `.streamlit/config.toml`：Streamlit 主题配置
   - `prepare_data.py`：数据一键复制脚本

---

## 总结

| 步骤 | 操作 | 预计时间 |
|------|------|----------|
| 1 | 运行 `python prepare_data.py` 复制数据 | 1分钟 |
| 2 | 创建 GitHub 仓库并推送代码 | 5分钟 |
| 3 | 在 Streamlit Cloud 创建应用 | 3分钟 |
| 4 | 等待自动部署完成 | 2-5分钟 |
| **总计** | | **~15分钟** |

🎉 完成后，你就拥有一个随时随地可访问的 ETF 轮动策略回测系统了！

---

如有问题，请检查：
1. 数据文件是否正确复制到 `data/ETF/1d/`
2. GitHub 仓库是否包含所有文件
3. Streamlit Cloud 的部署日志（点击应用页面右下角的 "⋮" → "View logs"）
