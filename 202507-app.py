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
    df = df.sort_values(by=['Project', 'TypeOrder', 'Start'], ascending=[True, True, True]).reset_index(drop=True)

    # 將任務名稱設定為 Categorical，強制 Plotly 遵循此順序
    df['Task'] = pd.Categorical(df['Task'], categories=df['Task'].unique(), ordered=True)
    
    return df

def get_dynamic_tick_format(df, view_mode):
    """
    根據時間視野動態生成X軸的刻度位置與標籤
    """
    valid_starts = df['Start'].dropna()
    valid_finishes = df['Finish'].dropna()
    
    if valid_starts.empty or valid_finishes.empty:
        return None, None

    date_min = valid_starts.min()
    date_max = valid_finishes.max()
    tickvals, ticktext = [], []

    if view_mode == "每年":
        years = pd.date_range(start=date_min.to_period('Y').to_timestamp(), end=date_max, freq='YS')
        tickvals, ticktext = years, [d.strftime('%Y') for d in years]
    elif view_mode == "每半年":
        half_years = pd.date_range(start=date_min, end=date_max, freq='6MS')
        tickvals = half_years
        ticktext = [f"{d.year}-H{1 if d.month <= 6 else 2}" for d in half_years]
    elif view_mode == "每季":
        quarters = pd.date_range(start=date_min, end=date_max, freq='QS')
        tickvals, ticktext = quarters, [f"{d.year}-Q{d.quarter}" for d in quarters]
    elif view_mode == "每周":
        mondays = pd.date_range(start=date_min - pd.to_timedelta(date_min.weekday(), unit='d'), end=date_max, freq='W-MON')
        tickvals, ticktext = mondays, [d.strftime('%Y-%m-%d') for d in mondays]

    if len(tickvals) == 0:
        return None, None
    return tickvals, ticktext

def create_gantt_chart(df, view_mode):
    """
    生成甘特圖，並將里程碑以符號標示。
    """
    if df.empty:
        # 即使是空的，也返回一個空的 Figure 物件，避免錯誤
        st.warning("篩選後無資料可顯示。")
        return go.Figure()

    tasks_df = df[df['Type'] != '里程碑'].copy()
    milestones_df = df[df['Type'] == '里程碑'].copy()

    fig = px.timeline(
        tasks_df, x_start="Start", x_end="Finish", y="Task",
        color="Project", hover_name="Task", title="專案時程甘特圖", text="Task"
    )
    fig.update_traces(textposition='inside')

    if not milestones_df.empty:
        fig.add_trace(go.Scatter(
            x=milestones_df['Start'], y=milestones_df['Task'], mode='markers',
            marker=dict(symbol='diamond', color='red', size=12, line=dict(color='black', width=1)),
            name='里程碑', hoverinfo='text',
            hovertext=[f"<b>{row.Task}</b><br>日期: {row.Start.strftime('%Y-%m-%d')}<br>專案: {row.Project}" for _, row in milestones_df.iterrows()]
        ))

    num_tasks = len(df['Task'].unique())
    chart_height = max(600, num_tasks * 35)

    fig.update_layout(
        height=chart_height, xaxis_title="日期", yaxis_title="專案任務",
        # 此處的 df['Task'].cat.categories 現在會是「清理過」的類別列表
        yaxis={'categoryorder':'array', 'categoryarray': df['Task'].cat.categories.tolist()},
        title_font_size=24, font_size=14, hoverlabel=dict(bgcolor="white", font_size=12),
        legend_title_text='圖例'
    )
    
    try:
        # 使用台灣時區
        today_date = datetime.now()
        fig.add_shape(type="line", x0=today_date, y0=0, x1=today_date, y1=1, yref="paper", line=dict(color="Red", width=2, dash="dash"))
    except Exception as e:
        st.warning(f"無法標示當天日期: {e}")
    
    tickvals, ticktext = get_dynamic_tick_format(df, view_mode)
    if tickvals is not None and ticktext is not None:
        fig.update_xaxes(rangeslider_visible=True, tickmode='array', tickvals=tickvals, ticktext=ticktext)
    else:
        fig.update_xaxes(rangeslider_visible=True)

    return fig

# --- 主應用程式流程 ---

st.sidebar.header("1. 上傳您的 CSV 檔案")
uploaded_file = st.sidebar.file_uploader("請選擇一個 CSV 檔案", type=["csv"])

if uploaded_file is not None:
    try:
        df_original = pd.read_csv(uploaded_file)
        df_processed = preprocess_data(df_original.copy())
        st.success("CSV 檔案上傳並處理成功！")

        st.sidebar.header("2. 篩選專案")
        filter_mode = st.sidebar.selectbox(
            "選擇顯示模式",
            ["顯示全部專案", "只顯示母專案", "依母專案篩選"],
            index=0
        )

        df_filtered = df_processed.copy()

        if filter_mode == "只顯示母專案":
            df_filtered = df_processed[df_processed['Type'] == '母專案'].copy()
            # --- 主要修正(1/2) ---
            # 移除 Task 類別中未使用的項目，確保 Y 軸只顯示母專案
            df_filtered['Task'] = df_filtered['Task'].cat.remove_unused_categories()
        
        elif filter_mode == "依母專案篩選":
            parent_projects = df_processed[df_processed['Type'] == '母專案']['Project'].unique().tolist()
            if parent_projects:
                selected_projects = st.sidebar.multiselect(
                    "請選擇要顯示的母專案",
                    options=parent_projects,
                    default=parent_projects[0] if parent_projects else None
                )
                if selected_projects:
                    df_filtered = df_processed[df_processed['Project'].isin(selected_projects)].copy()
                    # --- 主要修正(2/2) ---
                    # 同樣地，在此處也移除未使用的 Task 類別
                    df_filtered['Task'] = df_filtered['Task'].cat.remove_unused_categories()
                else:
                    # 使用空的 DataFrame 並定義欄位以避免後續出錯
                    df_filtered = pd.DataFrame(columns=df_processed.columns)
                    df_filtered['Task'] = pd.Categorical(df_filtered['Task'])
            else:
                st.sidebar.warning("檔案中沒有找到任何『母專案』。")
                df_filtered = pd.DataFrame(columns=df_processed.columns)

        st.sidebar.header("3. 甘特圖設定")
        view_mode = st.sidebar.selectbox(
            "選擇時間軸視野",
            ["每日", "每周", "每月", "每季", "每半年", "每年"],
            index=1
        )
        
        st.subheader("資料預覽 (根據篩選結果)")
        if not df_filtered.empty:
            st.dataframe(df_filtered[['Task', 'Project', 'Type', 'Start', 'Finish']].head())
        else:
            st.info("目前篩選條件下沒有資料可顯示。")

        gantt_chart = create_gantt_chart(df_filtered, view_mode)
        st.plotly_chart(gantt_chart, use_container_width=True)

        st.header("專案狀態追蹤 (根據篩選結果)")
        if not df_filtered.empty:
            today = pd.to_datetime(datetime.now().date())
            
            upcoming_tasks = df_filtered[
                (df_filtered['Finish'] >= today) & 
                (df_filtered['Finish'] <= today + timedelta(days=7)) &
                (df_filtered['Completion_Date'].isnull())
            ]

            overdue_tasks = df_filtered[
                ((df_filtered['Finish'] < today) & (df_filtered['Completion_Date'].isnull())) |
                (pd.notnull(df_filtered['Completion_Date']) & pd.notnull(df_filtered['Finish']) &
                 (df_filtered['Completion_Date'] > df_filtered['Finish']))
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
        else:
            st.info("目前篩選條件下無項目可追蹤。")

    except Exception as e:
        st.error(f"處理檔案時發生錯誤：{e}")
        st.warning("請確認您的 CSV 檔案格式是否正確，特別是日期欄位 (YYYY-MM-DD) 以及 'Task', 'Start', 'Finish', 'Project', 'Type' 欄位是否存在。")
else:
    st.info("請在左側側邊欄上傳您的專案 CSV 檔案以開始。")
