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
st.write("上傳您的專案管理 CSV 檔案，即可生成互動式甘特圖。可選欄位 `Status` (填入 Closed/In process/Not start) 來追蹤專案進度。")

# --- 函式定義 ---

def preprocess_data(df):
    """
    資料預處理：轉換日期格式、建立排序鍵、並計算進度。
    """
    for col in ['Start', 'Finish', 'Completion_Date']:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')

    if 'Status' in df.columns:
        df['Status'] = df['Status'].fillna('未定義')
    else:
        df['Status'] = '未定義'
    
    # --- 新增：將狀態 mapping 到百分比 ---
    progress_map = {'Closed': 1.0, 'In process': 0.5, 'Not start': 0.0, '未定義': 0.0}
    df['Progress'] = df['Status'].map(progress_map).fillna(0.0)

    # --- 新增：計算進度條的結束日期 ---
    # 確保 Start 和 Finish 是日期時間格式且非空才能計算
    mask = df['Start'].notna() & df['Finish'].notna() & (df['Type'] != '里程碑')
    # 使用 .loc 來避免 SettingWithCopyWarning
    df.loc[mask, 'Progress_Finish'] = df.loc[mask, 'Start'] + \
        (df.loc[mask, 'Finish'] - df.loc[mask, 'Start']) * df.loc[mask, 'Progress']

    type_order = {'母專案': 1, '子專案': 2, '里程碑': 3}
    df['TypeOrder'] = df['Type'].map(type_order).fillna(4)

    df = df.sort_values(by=['Project', 'TypeOrder', 'Start'], ascending=[True, True, True]).reset_index(drop=True)
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
        tickvals, ticktext = [d for d in half_years], [f"{d.year}-H{1 if d.month <= 6 else 2}" for d in half_years]
    elif view_mode == "每季":
        quarters = pd.date_range(start=date_min, end=date_max, freq='QS')
        tickvals, ticktext = [d for d in quarters], [f"{d.year}-Q{d.quarter}" for d in quarters]
    elif view_mode == "每周":
        mondays = pd.date_range(start=date_min - pd.to_timedelta(date_min.weekday(), unit='d'), end=date_max, freq='W-MON')
        tickvals, ticktext = [d for d in mondays], [d.strftime('%Y-%m-%d') for d in mondays]

    if len(tickvals) == 0:
        return None, None
    return tickvals, ticktext

# --- 主要修改：重構整個圖表生成函式 ---
def create_gantt_chart(df, view_mode):
    """
    生成帶有進度條的甘特圖。
    """
    if df.empty:
        st.warning("篩選後無資料可顯示。")
        return go.Figure()

    tasks_df = df[df['Type'] != '里程碑'].copy()
    milestones_df = df[df['Type'] == '里程碑'].copy()
    
    fig = go.Figure()
    
    # 1. 繪製底層的灰色背景長條 (代表完整工期)
    fig.add_trace(go.Bar(
        y=tasks_df['Task'],
        x=tasks_df['Finish'] - tasks_df['Start'],
        base=tasks_df['Start'],
        orientation='h',
        marker_color='#E0E0E0', # 淺灰色
        name='預計工期',
        hoverinfo='none',
        text="", # 避免顯示文字
    ))

    # 2. 繪製上層的彩色進度長條 (依專案分色)
    projects = tasks_df['Project'].unique()
    colors = px.colors.qualitative.Plotly

    for i, project in enumerate(projects):
        project_df = tasks_df[tasks_df['Project'] == project]
        progress_df = project_df[project_df['Progress'] > 0] # 只繪製有進度的部分

        if not progress_df.empty:
            fig.add_trace(go.Bar(
                y=progress_df['Task'],
                x=progress_df['Progress_Finish'] - progress_df['Start'],
                base=progress_df['Start'],
                orientation='h',
                marker_color=colors[i % len(colors)],
                name=project,
                text=progress_df.apply(lambda row: f"{row['Progress']:.0%}", axis=1),
                textposition='inside',
                insidetextanchor='middle',
                hovertemplate=(
                    "<b>%{y}</b><br>"
                    "專案: %{customdata[0]}<br>"
                    "狀態: %{customdata[1]}<br>"
                    "開始: %{customdata[2]|%Y-%m-%d}<br>"
                    "結束: %{customdata[3]|%Y-%m-%d}<br>"
                    "進度: %{text}"
                    "<extra></extra>"
                ),
                customdata=progress_df[['Project', 'Status', 'Start', 'Finish']]
            ))

    # 3. 加上里程碑
    if not milestones_df.empty:
        fig.add_trace(go.Scatter(
            x=milestones_df['Start'], y=milestones_df['Task'], mode='markers',
            marker=dict(symbol='diamond', color='red', size=12, line=dict(color='black', width=1)),
            name='里程碑',
            hovertemplate="<b>%{y}</b><br>日期: %{x|%Y-%m-%d}<extra></extra>"
        ))

    num_tasks = len(df['Task'].unique())
    chart_height = max(600, num_tasks * 35)

    # 4. 更新整體圖表佈局
    fig.update_layout(
        height=chart_height,
        title_text="專案時程進度甘特圖",
        xaxis_title="日期",
        yaxis_title="專案任務",
        yaxis={'categoryorder':'array', 'categoryarray': df['Task'].cat.categories.tolist(), 'autorange': 'reversed'},
        barmode='stack', # 堆疊模式，讓進度條疊在背景條之上
        legend_title_text='圖例',
        hoverlabel=dict(bgcolor="white", font_size=12),
        title_font_size=24,
        font_size=14,
    )
    
    try:
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
                    df_filtered['Task'] = df_filtered['Task'].cat.remove_unused_categories()
                else:
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
        
        # --- 移除：顏色模式選擇功能已移除 ---

        st.subheader("資料預覽 (根據篩選結果)")
        if not df_filtered.empty:
            preview_cols = ['Task', 'Project', 'Type', 'Status', 'Start', 'Finish']
            st.dataframe(df_filtered[[col for col in preview_cols if col in df_filtered.columns]].head())
        else:
            st.info("目前篩選條件下沒有資料可顯示。")
        
        # --- 修改：呼叫新的圖表函式 ---
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
                    st.dataframe(upcoming_tasks[['Task', 'Project', 'Status', 'Finish']].rename(columns={'Finish': '預計結束日'}))
                else:
                    st.info("目前沒有即將到期的項目。")
            with col2:
                st.subheader("🚨 已超時的項目")
                if not overdue_tasks.empty:
                    st.dataframe(overdue_tasks[['Task', 'Project', 'Status', 'Finish', 'Completion_Date']].rename(columns={'Finish': '預計結束日', 'Completion_Date': '實際遞交日'}))
                else:
                    st.info("恭喜！目前沒有超時的項目。")
        else:
            st.info("目前篩選條件下無項目可追蹤。")

    except Exception as e:
        st.error(f"處理檔案時發生錯誤：{e}")
        st.warning("請確認您的 CSV 檔案格式是否正確，特別是日期欄位 (YYYY-MM-DD) 以及 'Task', 'Start', 'Finish', 'Project', 'Type' 欄位是否存在。也請檢查選用的 `Status` 欄位。")
else:
    st.info("請在左側側邊欄上傳您的專案 CSV 檔案以開始。")
