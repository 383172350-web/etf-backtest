import streamlit as st
import sys

st.title("ETF轮动策略回测系统")
st.write("简化版入口")
st.write(f"Python版本: {sys.version}")

try:
    from engine import scan_pkl_dir, build_data_dict, ETF_NAMES
    items = scan_pkl_dir()
    st.write(f"✅ 导入成功 - 找到 {len(items)} 个标的")
    st.write(f"ETF_NAMES 数量: {len(ETF_NAMES)}")
except Exception as e:
    st.error(f"❌ 导入失败: {e}")
    import traceback
    st.code(traceback.format_exc())
