import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from google.oauth2.service_account import Credentials

COLUMNS = ["日付", "場所", "時間帯", "種目", "重さ(kg)", "回数", "距離(km)"]

MACHINES = [
    "チェストプレス",
    "シーテッドロウ",
    "レッグプレス",
    "レッグエクステンション",
    "レッグカール",
    "ヒップアブダクション",
    "ヒップアダクション",
    "腹筋マシン",
    "アブドミナルクランチ",
    "バックエクステンション",
]
CARDIO = ["トレッドミル", "ジョギング"]
ALL_EXERCISES = MACHINES + CARDIO

LOCATIONS = ["ジム", "屋外", "自宅", "その他"]
TIME_SLOTS = ["朝（6〜9時）", "午前（9〜12時）", "昼（12〜15時）", "午後（15〜18時）", "夕方（18〜21時）", "夜（21時〜）"]


@st.cache_resource
def get_sheet():
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=[
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive",
        ],
    )
    gc = gspread.authorize(creds)
    ws = gc.open_by_key(st.secrets["spreadsheet_id"]).sheet1
    if not ws.get_all_values():
        ws.append_row(COLUMNS)
    return ws


def load_data():
    ws = get_sheet()
    all_values = ws.get_all_values()
    if len(all_values) <= 1:
        return pd.DataFrame(columns=COLUMNS)
    df = pd.DataFrame(all_values[1:], columns=all_values[0])
    for col in ["重さ(kg)", "回数", "距離(km)"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["日付"] = pd.to_datetime(df["日付"], errors="coerce")
    return df


def save_rows(rows):
    ws = get_sheet()
    clean = [["" if v is None else v for v in row] for row in rows]
    ws.append_rows(clean, value_input_option="USER_ENTERED")


def delete_last_session():
    ws = get_sheet()
    all_rows = ws.get_all_values()
    if len(all_rows) <= 1:
        return
    last_date = all_rows[-1][0]
    to_delete = []
    for i in range(len(all_rows) - 1, 0, -1):
        if all_rows[i][0] == last_date:
            to_delete.append(i + 1)
        else:
            break
    for row_idx in sorted(to_delete, reverse=True):
        ws.delete_rows(row_idx)


st.set_page_config(page_title="筋トレ記録", page_icon="💪", layout="wide")
st.title("💪 筋トレ記録")

tab1, tab2, tab3 = st.tabs(["📝 記録入力", "📋 記録一覧", "📊 統計"])

# ─── Tab1: 記録入力 ──────────────────────────────────────────────────────────
with tab1:
    st.subheader("トレーニング記録")

    from datetime import date
    c1, c2, c3 = st.columns(3)
    with c1:
        workout_date = st.date_input("日付", value=date.today())
    with c2:
        location = st.selectbox("場所", LOCATIONS)
    with c3:
        time_slot = st.selectbox("時間帯", TIME_SLOTS)

    st.markdown("---")

    selected = st.multiselect(
        "実施した種目を選択",
        options=ALL_EXERCISES,
        placeholder="種目を選んでください",
    )

    entries = {}

    if selected:
        st.markdown("---")
        machine_selected = [e for e in selected if e in MACHINES]
        cardio_selected = [e for e in selected if e in CARDIO]

        if machine_selected:
            st.markdown("**マシントレーニング**")
            cols = st.columns(min(len(machine_selected), 3))
            for i, machine in enumerate(machine_selected):
                with cols[i % 3]:
                    st.markdown(f"**{machine}**")
                    w = st.number_input("重さ (kg)", key=f"w_{machine}", min_value=0.0, step=2.5, format="%.1f")
                    r = st.number_input("回数", key=f"r_{machine}", min_value=0, step=1)
                    entries[machine] = ("machine", w, r)

        if cardio_selected:
            st.markdown("**有酸素運動**")
            cols = st.columns(min(len(cardio_selected), 3))
            for i, ex in enumerate(cardio_selected):
                with cols[i % 3]:
                    st.markdown(f"**{ex}**")
                    km = st.number_input("距離 (km)", key=f"km_{ex}", min_value=0.0, step=0.1, format="%.1f")
                    entries[ex] = ("cardio", km)

    st.markdown("---")
    if st.button("💾 保存", type="primary", use_container_width=True):
        if not selected:
            st.warning("種目を選択してください。")
        else:
            rows = []
            for ex, val in entries.items():
                if val[0] == "machine":
                    _, w, r = val
                    rows.append([str(workout_date), location, time_slot, ex,
                                 w if w > 0 else "", r if r > 0 else "", ""])
                else:
                    _, km = val
                    rows.append([str(workout_date), location, time_slot, ex, "", "", km if km > 0 else ""])
            with st.spinner("保存中..."):
                save_rows(rows)
            st.success(f"✅ {len(rows)} 種目を保存しました！")
            st.balloons()

# ─── Tab2: 記録一覧 ──────────────────────────────────────────────────────────
with tab2:
    df = load_data()

    if df.empty:
        st.info("まだ記録がありません。「記録入力」タブから登録してください。")
    else:
        c1, c2, c3 = st.columns(3)
        with c1:
            filter_loc = st.multiselect("場所で絞り込み", options=sorted(df["場所"].dropna().unique()))
        with c2:
            filter_ex = st.multiselect("種目で絞り込み", options=sorted(df["種目"].dropna().unique()))
        with c3:
            dates = df["日付"].dropna().sort_values()
            date_range = st.date_input(
                "期間", value=(dates.min().date(), dates.max().date()), key="date_range"
            )

        filtered = df.copy()
        if filter_loc:
            filtered = filtered[filtered["場所"].isin(filter_loc)]
        if filter_ex:
            filtered = filtered[filtered["種目"].isin(filter_ex)]
        if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
            start, end = date_range
            filtered = filtered[
                (filtered["日付"] >= pd.Timestamp(start)) & (filtered["日付"] <= pd.Timestamp(end))
            ]

        st.dataframe(filtered.sort_values("日付", ascending=False).reset_index(drop=True), use_container_width=True)
        st.caption(f"{len(filtered)} 件")

        with st.expander("⚠️ 最新セッションを削除"):
            if st.button("最新の記録を削除", type="secondary"):
                with st.spinner("削除中..."):
                    delete_last_session()
                st.success("削除しました。")
                st.rerun()

# ─── Tab3: 統計 ──────────────────────────────────────────────────────────────
with tab3:
    df = load_data()

    if df.empty:
        st.info("まだ記録がありません。")
    else:
        df["日付"] = pd.to_datetime(df["日付"])

        st.markdown("#### トレーニング頻度")
        freq = df.groupby(df["日付"].dt.date)["種目"].count().reset_index()
        freq.columns = ["日付", "種目数"]
        fig1 = px.bar(freq, x="日付", y="種目数", title="トレーニング頻度（日別）")
        st.plotly_chart(fig1, use_container_width=True)

        st.markdown("---")
        st.markdown("#### マシン重量の推移")
        machine_df = df[df["種目"].isin(MACHINES)].dropna(subset=["重さ(kg)"])
        if machine_df.empty:
            st.info("マシントレーニングの記録がありません。")
        else:
            sel_machine = st.selectbox("種目を選択", sorted(machine_df["種目"].unique()))
            m_df = machine_df[machine_df["種目"] == sel_machine].sort_values("日付")
            fig2 = px.line(m_df, x="日付", y="重さ(kg)", title=f"{sel_machine} 重量推移", markers=True)
            st.plotly_chart(fig2, use_container_width=True)

        st.markdown("---")
        st.markdown("#### 有酸素運動 距離")
        cardio_df = df[df["種目"].isin(CARDIO)].dropna(subset=["距離(km)"])
        if cardio_df.empty:
            st.info("有酸素運動の記録がありません。")
        else:
            fig3 = px.bar(
                cardio_df.sort_values("日付"), x="日付", y="距離(km)", color="種目", title="有酸素運動 距離推移"
            )
            st.plotly_chart(fig3, use_container_width=True)
            st.metric("累計距離", f"{cardio_df['距離(km)'].sum():.1f} km")
