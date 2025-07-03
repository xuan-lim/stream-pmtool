import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
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
    資料預處理：轉換日期格式、建立排序鍵。
    """
    # 轉換日期格式
    for col in ['Start', 'Finish', 'Completion_Date']:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')

    # 建立排序邏輯
    # 1. 母專案 -> 2. 子專案 -> 3. 里程碑
    type_order = {'母專案': 1, '子專案': 2, '里程碑': 3}
    df['TypeOrder'] = df['Type'].map(type_order).fillna(4) # 未定義的類型排最後

    # 排序：先依母專案，再依類型順序，最後依開始日期
    df = df.sort_values(by=['Project', 'TypeOrder', 'Start'], ascending=[True, True, True])

    # 將任務名稱設定為 Categorical，強制 Plotly 遵循此順序
    df['Task'] = pd.Categorical(df['Task'], categories=df['Task'].unique(), ordered=True)
    
    return df

def get_dynamic_tick_format(df, view_mode):
    """
    根據時間視野動態生成X軸的刻度位置與標籤
    """
    date_min = df['Start'].min()
    date_max = df['Finish'].max()
    
    # 確保有有效的日期範圍
    if pd.isna(date_min) or pd.isna(date_max):
        return None, None

    tickvals = []
    ticktext = []

    if view_mode == "每年":
        years = pd.date_range(start=date_min.to_period('Y').to_timestamp(), end=date_max, freq='YS')
        tickvals = years
        ticktext = [d.strftime('%Y') for d in years]
    
    elif view_mode == "每半年":
        half_years = pd.date_range(start=date_min, end=date_max, freq='6MS') # 每6個月的開始
        tickvals = half_years
        for d in half_years:
            half = "H1" if d.month <= 6 else "H2"
            ticktext.append(f"{d.year}-{half}")

    elif view_mode == "每季":
        quarters = pd.date_range(start=date_min, end=date_max, freq='QS') # 每季的開始
        tickvals = quarters
        ticktext = [f"{d.year}-Q{d.quarter}" for d in quarters]

    elif view_mode == "每周":
        mondays = pd.date_range(start=date_min - pd.to_timedelta(date_min.weekday(), unit='d'), end=date_max, freq='W-MON')
        tickvals = mondays
        ticktext = [d.strftime('%Y-%m-%d') for d in mondays]

    if not tickvals: # 如果列表為空 (例如時間範圍太短)，返回 None
        return None, None
        
    return tickvals, ticktext


def create_gantt_chart(df, view_mode):
    """
    生成甘特圖，並將里程碑以符號標示。
    """
    # 將資料分為任務(有時長)和里程碑(無時長)
    tasks_df = df[df['Type'] != '里程碑'].copy()
    milestones_df = df[df['Type'] == '里程碑'].copy()

    # 1. 繪製基本的時間軸圖 (只包含任務)
    fig = px.timeline(
        tasks_df,
        x_start="Start",
        x_end="Finish",
        y="Task",
        color="Project",
        hover_name="Task",
        title="專案時程甘特圖",
        text="Task"
    )
    fig.update_traces(textposition='inside')

    # 2. 在圖上增加里程碑的散佈圖標記
    if not milestones_df.empty:
        fig.add_trace(go.Scatter(
            x=milestones_df['Start'],
            y=milestones_df['Task'],
            mode='markers',
            marker=dict(
                symbol='diamond', # 使用鑽石符號
                color='red',      # 顏色設為紅色
                size=12,          # 符號大小
                line=dict(color='black', width=1) # 黑色外框
            ),
            name='里程碑',
            hoverinfo='text',
            hovertext=[f"<b>{row.Task}</b><br>日期: {row.Start.strftime('%Y-%m-%d')}<br>專案: {row.Project}" for index, row in milestones_df.iterrows()]
        ))

    # 更新整體圖表佈局
    fig.update_layout(
        xaxis_title="日期",
        yaxis_title="專案任務",
        yaxis={'categoryorder':'array', 'categoryarray': df['Task'].tolist()}, # 保持排序
        title_font_size=24,
        font_size=14,
        hoverlabel=dict(bgcolor="white", font_size=12),
        legend_title_text='圖例'
    )
    
    # 加上標示今天日期的紅色垂直線
    fig.add_shape(
        type="line",
        x0=datetime.now(), y0=0,
        x1=datetime.now(), y1=1,
        yref="paper",
        line=dict(color="Red", width=2, dash="dash"),
        name="今天"
    )
    
    # 應用動態時間軸格式
    tickvals, ticktext = get_dynamic_tick_format(df, view_mode)
    if tickvals is not None and ticktext is not None:
        fig.update_xaxes(
            rangeslider_visible=True,
            tickmode='array',
            tickvals=tickvals,
            ticktext=ticktext
        )
    else: # 如果沒有客製化格式，使用預設
        fig.update_xaxes(rangeslider_visible=True)

    return fig

# --- 主應用程式流程 ---

# 1. 檔案上傳
st.sidebar.header("1. 上傳您的 CSV 檔案")
uploaded_file = st.sidebar.file_uploader("請選擇一個 CSV 檔案", type=["csv"])

if uploaded_file is not None:
    try:
        df = pd.read_csv(uploaded_file)
        df_processed = preprocess_data(df)

        st.success("CSV 檔案上傳並處理成功！")
        st.dataframe(df_processed.head())

        # 2. 時間軸切換
        st.sidebar.header("2. 甘特圖設定")
        view_mode = st.sidebar.selectbox(
            "選擇時間軸視野",
            ["每日", "每周", "每月", "每季", "每半年", "每年"],
            index=1 # 預設為每周
        )

        # 3. 生成並顯示甘特圖
        if not df_processed.empty:
            gantt_chart = create_gantt_chart(df_processed, view_mode)
            st.plotly_chart(gantt_chart, use_container_width=True)
        else:
            st.warning("處理後的資料為空，無法生成甘特圖。")

        # 4. 顯示即將到期與超時的項目
        st.header("專案狀態追蹤")
        today = pd.to_datetime(datetime.now().date())
        
        # 即將到期 (未來 7 天內到期，且未完成)
        upcoming_tasks = df_processed[
            (df_processed['Finish'] >= today) & 
            (df_processed['Finish'] <= today + timedelta(days=7)) &
            (df_processed['Completion_Date'].isnull())
        ]

        # 超時 (已過期但未完成 或 遞交日晚於結束日)
        overdue_tasks = df_processed[
            ((df_processed['Finish'] < today) & (df_processed['Completion_Date'].isnull())) |
            (df_processed['Completion_Date'] > df_processed['Finish'])
        ].drop_duplicates()

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
        st.warning("請確認您的 CSV 檔案格式是否正確，特別是日期欄位 (YYYY-MM-DD) 以及 'Task', 'Start', 'Finish', 'Project', 'Type' 欄位是否存在。")
else:
    st.info("請在左側側邊欄上傳您的專案 CSV 檔案以開始。")
