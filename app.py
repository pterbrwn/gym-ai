import streamlit as st
import sqlite3
import pandas as pd
from datetime import date, timedelta
import time
import coach  # Ensure coach.py is in your directory
import re

# --- CONFIGURATION ---
st.set_page_config(
    page_title="JETSON ELITE", 
    page_icon="💎", 
    layout="wide", 
    initial_sidebar_state="collapsed"
)

# --- ELITE UI STYLING ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;700;900&family=JetBrains+Mono:wght@400;700&display=swap');

    html, body, [class*="css"] { font-family: 'Inter', sans-serif; color: #FFFFFF; }
    .stApp { background-color: #080808; }
    
    ::-webkit-scrollbar { width: 4px; }
    ::-webkit-scrollbar-track { background: #080808; }
    ::-webkit-scrollbar-thumb { background: #333; }

    h1 { font-weight: 900 !important; letter-spacing: -3px !important; text-transform: uppercase; margin-top: -40px !important; }
    .sub-brand { color: #444; font-size: 0.75rem; letter-spacing: 5px; text-transform: uppercase; margin-bottom: 30px; }

    .stTabs [data-baseweb="tab-list"] { gap: 24px; border-bottom: 1px solid #111; }
    .stTabs [data-baseweb="tab"] {
        background-color: transparent !important;
        color: #444 !important;
        font-weight: 700;
        text-transform: uppercase;
        font-size: 0.75rem;
        letter-spacing: 1px;
    }
    .stTabs [aria-selected="true"] { color: #FFFFFF !important; border-bottom: 2px solid #FFFFFF !important; }

    div[data-testid="stForm"] { border: 1px solid #1a1a1a !important; border-radius: 4px !important; background-color: #0c0c0c !important; }
    
    .stButton>button {
        width: 100%; border-radius: 4px; height: 3.5em; background: #FFFFFF !important; color: #000 !important;
        font-weight: 900; text-transform: uppercase; letter-spacing: 2px; border: none; transition: 0.3s ease;
    }
    
    [data-testid="stMetric"] { background: #0c0c0c; border: 1px solid #1a1a1a; padding: 15px; border-radius: 4px; }
    div[data-testid="stDataEditor"] { border: 1px solid #1a1a1a !important; }

    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# --- DATABASE ENGINE ---
DB_NAME = 'gym_data.db'
MODEL_NAME = 'qwen2.5:7b' 

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def get_unique_exercises(muscle_group):
    conn = get_db_connection()
    data = conn.execute("SELECT DISTINCT exercise_name FROM workout_logs WHERE muscle_target = ?", (muscle_group,)).fetchall()
    conn.close()
    return [row['exercise_name'] for row in data]

def get_last_performance(exercise_name):
    conn = get_db_connection()
    data = conn.execute("SELECT weight, reps, date FROM workout_logs WHERE exercise_name = ? ORDER BY date DESC LIMIT 1", (exercise_name,)).fetchone()
    conn.close()
    return data

def add_set(target, exercise, weight, reps, sets, log_date):
    conn = get_db_connection()
    date_str = log_date.isoformat() if isinstance(log_date, date) else log_date
    conn.execute("INSERT INTO workout_logs (date, muscle_target, exercise_name, weight, reps, sets) VALUES (?, ?, ?, ?, ?, ?)",
              (date_str, target, exercise, weight, reps, sets))
    conn.commit()
    conn.close()

def update_log(row_id, weight, reps, sets):
    conn = get_db_connection()
    conn.execute("UPDATE workout_logs SET weight = ?, reps = ?, sets = ? WHERE id = ?", (weight, reps, sets, row_id))
    conn.commit()
    conn.close()

def delete_log(row_id):
    conn = get_db_connection()
    conn.execute("DELETE FROM workout_logs WHERE id = ?", (row_id,))
    conn.commit()
    conn.close()

def get_workout_df(start_date, end_date=None):
    conn = get_db_connection()
    if end_date:
        query = "SELECT id, date, muscle_target, exercise_name, weight, reps, sets FROM workout_logs WHERE date BETWEEN ? AND ?"
        df = pd.read_sql_query(query, conn, params=(start_date.isoformat(), end_date.isoformat()))
    else:
        query = "SELECT id, date, muscle_target, exercise_name, weight, reps, sets FROM workout_logs WHERE date = ?"
        df = pd.read_sql_query(query, conn, params=(start_date.isoformat(),))
    conn.close()
    return df

def get_volume_history(muscle_target):
    conn = get_db_connection()
    if muscle_target == "All":
        query = "SELECT date, SUM(weight * reps * sets) as total_volume FROM workout_logs GROUP BY date ORDER BY date ASC"
        df = pd.read_sql_query(query, conn)
    else:
        query = "SELECT date, SUM(weight * reps * sets) as total_volume FROM workout_logs WHERE muscle_target = ? GROUP BY date ORDER BY date ASC"
        df = pd.read_sql_query(query, conn, params=(muscle_target,))
    conn.close()
    return df

# --- THE ELITE ANALYTICS PARSER ---
def display_elite_analysis(analysis, range_label="SESSION"):
    # CLEANING: Remove any markdown code blocks the AI might have wrapped the text in
    analysis = analysis.replace("```markdown", "").replace("```", "").strip()

    st.markdown(f"""
        <div style="text-align: center; margin: 40px 0;">
            <h1 style="font-size: 3rem; color: #fff;">THE VERDICT</h1>
            <p style="color: #444; letter-spacing: 5px;">{range_label} INTELLIGENCE REPORT</p>
        </div>
    """, unsafe_allow_html=True)

    # Statistical Extraction
    grade = re.search(r'Intensity:\s*\**(\d+)/10\**', analysis)
    load = re.search(r'Load:\*\*\s*([\d,]+)', analysis)
    delta = re.search(r'Increase:\s*~?(\d+)%', analysis)

    c1, c2, c3 = st.columns(3)
    c1.metric("KPI: INTENSITY", f"{grade.group(1)}/10" if grade else "8/10")
    c2.metric("KPI: TOTAL LOAD", f"{load.group(1)} LBS" if load else "---")
    c3.metric("KPI: PROGRESS", f"+{delta.group(1)}%" if delta else "+0%")

    # Robust String Splitting for the Briefing
    # We split by 'Tactical Analysis' or fallback to the second half of the response
    if "Tactical Analysis" in analysis:
        parts = analysis.split("Tactical Analysis")
        summary_raw = parts[0]
        tactical_raw = parts[1]
    else:
        summary_raw = analysis
        tactical_raw = ""

    # Clean the summary: strip the "Intensity: X/10" line which looks messy in the briefing
    summary_clean = re.sub(r'Intensity:.*?\n', '', summary_raw).strip()
    # Remove any stray leading hashes/headers
    summary_clean = re.sub(r'^#+.*?\n', '', summary_clean).strip()

    st.markdown(f"""
        <div style="background: #0c0c0c; border-left: 2px solid #fff; padding: 2.5rem; margin: 2rem 0; border-radius: 0 4px 4px 0;">
            <p style="color: #444; font-size: 0.7rem; text-transform: uppercase; margin-bottom: 15px; letter-spacing: 2px;">Executive Briefing</p>
            <p style="font-size: 1.3rem; line-height: 1.6; font-style: italic; color: #FAFAFA;">"{summary_clean}"</p>
        </div>
    """, unsafe_allow_html=True)

    if tactical_raw:
        # Sanitize Markdown artifacts for a Billionaire look
        tactical_html = tactical_raw.replace("- **", "<strong>").replace("**", "</strong>").replace("\n- ", "<br>• ")
        # Ensure we don't have stray hashes
        tactical_html = tactical_html.replace("#", "")
        
        st.markdown(f"""
            <div style="background: #050505; border: 1px solid #111; padding: 2rem; border-radius: 4px;">
                <p style="color: #444; font-weight: 700; text-transform: uppercase; font-size: 0.7rem; margin-bottom: 15px; letter-spacing: 1px;">Tactical Drilldown</p>
                <div style="color: #888; font-size: 1rem; line-height: 1.8; font-family: 'JetBrains Mono';">{tactical_html}</div>
            </div>
        """, unsafe_allow_html=True)

# --- UI LOGIC ---
st.markdown("<h1>JETSON ELITE</h1>", unsafe_allow_html=True)
st.markdown("<p class='sub-brand'>Tier 1 Human Performance System</p>", unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(["MANIFEST", "ANALYTICS", "COACH"])

with tab1:
    col_date, col_spacer = st.columns([1, 2])
    target_date = col_date.date_input("LOGGING WINDOW", value=date.today())
    
    with st.form("set_entry", clear_on_submit=True):
        col_target, col_ex, col_w, col_r, col_s = st.columns([1.2, 2, 1, 1, 1])
        with col_target: 
            target = st.selectbox("PROTOCOL", ["Chest", "Back", "Legs", "Shoulders", "Arms", "Core", "Cardio"])
        with col_ex:
            known = get_unique_exercises(target)
            is_new = st.toggle("NEW", key="new_ex_toggle")
            ex_name = st.text_input("NAME", placeholder="Exercise Name") if is_new else st.selectbox("NAME", known if known else ["Register New"])
        
        last = get_last_performance(ex_name) if ex_name else None
        with col_w: weight = st.number_input("LBS", value=float(last['weight']) if last else 0.0, step=5.0)
        with col_r: reps = st.number_input("REPS", value=int(last['reps']) if last else 10, step=1)
        with col_s: sets = st.number_input("SETS", value=3, step=1)
        
        if st.form_submit_button("COMMIT PERFORMANCE"):
            if ex_name and ex_name != "Register New":
                add_set(target, ex_name, weight, reps, sets, target_date)
                st.rerun()

    st.write("")
    
    df_manifest = get_workout_df(target_date)
    if not df_manifest.empty:
        st.markdown(f"### SESSION MANIFEST: {target_date.strftime('%d %b %Y')}")
        edited = st.data_editor(
            df_manifest,
            column_config={
                "id": None, "date": None,
                "muscle_target": st.column_config.TextColumn("AREA", disabled=True),
                "exercise_name": st.column_config.TextColumn("PROTOCOL", disabled=True),
                "weight": st.column_config.NumberColumn("LBS"),
                "reps": st.column_config.NumberColumn("REPS"),
                "sets": st.column_config.NumberColumn("SETS"),
            },
            num_rows="dynamic", use_container_width=True, key="manifest_editor"
        )
        
        if st.button("SAVE CHANGES"):
            orig_ids = set(df_manifest['id'])
            curr_ids = set(edited['id'])
            for rid in (orig_ids - curr_ids): delete_log(rid)
            for _, row in edited.iterrows():
                if row['id'] in orig_ids: update_log(row['id'], row['weight'], row['reps'], row['sets'])
            st.toast("Database Synchronized.", icon="💎")
            time.sleep(0.5)
            st.rerun()
    else:
        st.caption(f"No records found for selected window: {target_date}")

with tab2:
    st.markdown("### PERFORMANCE TRENDS")
    hist_target = st.selectbox("FOCUS AREA", ["Chest", "Back", "Legs", "Shoulders", "Arms", "Core", "Cardio"], key="hist_select")
    v_df = get_volume_history(hist_target)
    if not v_df.empty:
        st.area_chart(v_df.set_index('date'), color="#ffffff")
    else:
        st.info("Insufficient longitudinal data for plotting.")

with tab3:
    st.markdown("### BOARDROOM REVIEW")
    review_window = st.date_input("SELECT REVIEW WINDOW", value=(date.today() - timedelta(days=6), date.today()))
    
    if len(review_window) == 2:
        start, end = review_window
        df_range = get_workout_df(start, end)
        
        if df_range.empty:
            st.warning("No performance data found in selected window.")
        else:
            if st.button("GENERATE EXECUTIVE ANALYSIS"):
                with st.spinner("Synthesizing Training Camp Data..."):
                    analysis_report = coach.generate_analysis(
                        "Training Period", 
                        df_range.to_dict('records'), 
                        get_volume_history("All"), 
                        MODEL_NAME
                    )
                    display_elite_analysis(analysis_report, range_label="PERIODIC")