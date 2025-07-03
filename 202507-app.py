import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta

# --- 頁面基本設定 ---
st.set_page_config(
    page_title="專案管理甘特圖",
    page_icon="📊",
    layout="wide"
)

st.title("📊 互動式專案管理甘特圖")
st.write("上傳您的專案管理 CSV 檔案，即可生成互動式甘特圖，並追蹤專案進度。")

# --- 函式定義 ---

def preprocess_data(df):
    """
    資料預處理：轉換日期格式、排序。
    """
    # 確保日期欄位為 datetime 物件
    for col in ['Start', 'Finish', 'Completion_Date']:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')

    # 排序邏輯：先依據 'Project'，再依據 'Start'
    # 這樣可以確保同一個母專案的任務會被群組在一起
    df = df.sort_values(by=['Project', 'Start'], ascending=[True, True])
    
    # 將任務名稱設定為索引，這有助於 Plotly 保持排序
    df['Task'] = pd.Categorical(df['Task'], categories=df['Task'].unique(), ordered=True)
    
    return df

def create_gantt_chart(df, view_mode):
    """
    根據選擇的時間軸模式生成甘特圖。
    """
    fig = px.timeline(
        df,
        x_start="Start",
        x_end="Finish",
        y="Task",
        color="Project", # 以母專案來區分顏色
        hover_name="Task",
        title="專案時程甘特圖",
        text="Task" # 在長條圖上顯示任務名稱
    )

    # 更新圖表佈局
    fig.update_layout(
        xaxis_title="日期",
        yaxis_title="專案任務",
        yaxis={'categoryorder':'array', 'categoryarray': df['Task'].tolist()}, # 保持排序
        title_font_size=24,
        font_size=14,
        hoverlabel=dict(
            bgcolor="white",
            font_size=12,
            font_family="Rockwell"
        )
    )
    
    # 在今天日期加上紅色垂直線
    fig.add_shape(
        type="line",
        x0=datetime.now(),
        y0=0,
        x1=datetime.now(),
        y1=1,
        yref="paper", # 參考整個 y 軸的高度
        line=dict(color="Red", width=2, dash="dash"),
        name="今天"
    )
    
    # 設定時間軸範圍
    if view_mode == "每日":
        tick_format = "%Y-%m-%d"
    elif view_mode == "每周":
        tick_format = "%Y-W%W"
    elif view_mode == "每月":
        tick_format = "%Y-%m"
    elif view_mode == "每季":
        # Plotly 沒有直接的季度格式，這裡使用每月並在視覺上以三個月為單位
        tick_format = "%Y-%m"
    elif view_mode == "每半年":
        tick_format = "%Y-%m"
    elif view_mode == "每年":
        tick_format = "%Y"
    else:
        tick_format = "%Y-%m-%d"

    fig.update_xaxes(tickformat=tick_format, rangeslider_visible=True)
    fig.update_traces(textposition='inside')

    return fig

# --- 主應用程式流程 ---

# 1. 檔案上傳
st.sidebar.header("1. 上傳您的 CSV 檔案")
uploaded_file = st.sidebar.file_uploader("請選擇一個 CSV 檔案", type=["csv"])

if uploaded_file is not None:
    try:
        # 讀取 CSV
        df = pd.read_csv(uploaded_file)
        
        # 進行資料預處理
        df = preprocess_data(df)

        st.success("CSV 檔案上傳並處理成功！")
        st.dataframe(df.head()) # 顯示前幾筆資料讓使用者確認

        # 2. 時間軸切換
        st.sidebar.header("2. 甘特圖設定")
        view_mode = st.sidebar.selectbox(
            "選擇時間軸視野",
            ["每日", "每周", "每月", "每季", "每半年", "每年"],
            index=2 # 預設為每月
        )

        # 3. 生成並顯示甘特圖
        gantt_chart = create_gantt_chart(df, view_mode)
        st.plotly_chart(gantt_chart, use_container_width=True)

        # --- 4. 顯示即將到期與超時的項目 ---
        st.header("專案狀態追蹤")
        
        today = pd.to_datetime(datetime.now().date())
        
        # 即將到期的項目 (未來 7 天內到期，且尚未完成)
        upcoming_tasks = df[
            (df['Finish'] >= today) & 
            (df['Finish'] <= today + timedelta(days=7)) &
            (df['Completion_Date'].isnull()) # 假設未填寫遞交日代表未完成
        ]

        # 超時的項目 (已過結束日期，但尚未完成)
        overdue_tasks = df[
            (df['Finish'] < today) & 
            (df['Completion_Date'].isnull())
        ]
        
        # 針對有遞交日的項目，判斷是否超時
        if 'Completion_Date' in df.columns:
            overdue_by_completion = df[
                df['Completion_Date'].notnull() & (df['Completion_Date'] > df['Finish'])
            ]
            # 合併兩種超時情況
            overdue_tasks = pd.concat([overdue_tasks, overdue_by_completion]).drop_duplicates()


        col1, col2 = st.columns(2)

        with col1:
            st.subheader("⚠️ 即將到期的項目 (未來7天)")
            if not upcoming_tasks.empty:
                st.dataframe(upcoming_tasks[['Task', 'Project', 'Finish']].rename(columns={'Finish': '預計結束日'}))
            else:
                st.info("目前沒有即將到期的項目。")

        with col2:
            st.subheader("🚨 已超時的項目")
            if not overdue_tasks.empty:
                st.dataframe(overdue_tasks[['Task', 'Project', 'Finish', 'Completion_Date']].rename(columns={'Finish': '預計結束日', 'Completion_Date': '實際遞交日'}))
            else:
                st.info("恭喜！目前沒有超時的項目。")

    except Exception as e:
        st.error(f"處理檔案時發生錯誤：{e}")
        st.warning("請確認您的 CSV 檔案格式是否正確，特別是日期欄位 (YYYY-MM-DD)。")

else:
    st.info("請在左側側邊欄上傳您的專案 CSV 檔案以開始。")
    st.image("https://streamlit.io/images/brand/streamlit-logo-primary-colormark-darktext.png", width=300)
