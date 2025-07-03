import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date

st.set_page_config(page_title="專案甘特圖", layout="wide")
st.title("📊 專案管理甘特圖儀表板")

# 上傳 CSV
uploaded_file = st.file_uploader("請上傳專案管理 CSV 檔案", type="csv")

# 時間單位選擇
time_unit = st.selectbox("選擇時間顯示單位", ["每日", "每週", "每月", "每季", "每半年", "每年"])

if uploaded_file:
    df = pd.read_csv(uploaded_file, parse_dates=["開始日", "結束日", "遞交日"])

    # 結構準備與排序
    df["排序碼"] = (
        df["母專案"].astype(str) + "-" +
        df["子專案"].astype(str).fillna("") + "-" +
        df["里程碑"].astype(str).fillna("")
    )
    df["專案顯示名稱"] = (
        df["母專案"] + " / " +
        df["子專案"].fillna("") + " / " +
        df["里程碑"].fillna("")
    )
    df["專案顯示名稱"] = df["專案顯示名稱"].str.replace(" /  / ", "")
    df.sort_values("排序碼", inplace=True)

    # 繪製 Gantt 圖
    fig = px.timeline(
        df,
        x_start="開始日",
        x_end="結束日",
        y="專案顯示名稱",
        color="母專案",
        title="📆 專案進度 Gantt 圖"
    )

    # 時間格式調整
    tickformat_dict = {
        "每日": "%Y-%m-%d",
        "每週": "%Y-%m-%d",
        "每月": "%Y-%m",
        "每季": "%Y-Q%q",
        "每半年": "%Y-%m",
        "每年": "%Y"
    }
    fig.update_layout(
        xaxis=dict(
            tickformat=tickformat_dict.get(time_unit, "%Y-%m-%d")
        ),
        height=600
    )

    # 畫紅色今日線
    fig.add_vline(
        x=date.today(),
        line_color="red",
        line_width=2,
        annotation_text="Today",
        annotation_position="top right"
    )

    st.plotly_chart(fig, use_container_width=True)

    # 狀態判斷
    today = pd.Timestamp.today()
    df["狀態"] = df["遞交日"].apply(
        lambda x: "逾期" if x < today else ("即將到期" if (x - today).days <= 7 else "正常")
    )

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("⚠️ 即將到期項目（7日內）")
        st.dataframe(df[df["狀態"] == "即將到期"][["專案顯示名稱", "開始日", "結束日", "遞交日"]])

    with col2:
        st.subheader("❌ 已逾期項目")
        st.dataframe(df[df["狀態"] == "逾期"][["專案顯示名稱", "開始日", "結束日", "遞交日"]])
