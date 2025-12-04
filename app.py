import streamlit as st
import sqlite3
import ollama
import pandas as pd
from datetime import date
import time

# --- CONFIGURATION ---
DB_NAME = 'gym_data.db'
MODEL_NAME = 'llama3.2' 

# --- CUSTOM CSS (MOBILE OPTIMIZATION) ---
st.set_page_config(page_title="Jetson Gym", page_icon="⚡", layout="centered")
st.markdown("""
    <style>
    .stButton>button {
        width: 100%;
        height: 3.5em;
        font-weight: bold; 
        border-radius: 12px;
    }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# --- DATABASE ENGINE ---
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
    data = conn.execute("""
        SELECT weight, reps, date FROM workout_logs 
        WHERE exercise_name = ? 
        ORDER BY date DESC LIMIT 1
    """, (exercise_name,)).fetchone()
    conn.close()
    return data

def add_set(target, exercise, weight, reps, sets):
    conn = get_db_connection()
    # SAVE AS ISO FORMAT (YYYY-MM-DD) to match python date
    conn.execute("INSERT INTO workout_logs (date, muscle_target, exercise_name, weight, reps, sets) VALUES (?, ?, ?, ?, ?, ?)",
              (date.today().isoformat(), target, exercise, weight, reps, sets))
    conn.commit()
    conn.close()

def get_todays_workout_df():
    conn = get_db_connection()
    # QUERY WITH ISO FORMAT
    today_str = date.today().isoformat()
    df = pd.read_sql_query("SELECT * FROM workout_logs WHERE date = ?", conn, params=(today_str,))
    conn.close()
    return df

def get_volume_history(muscle_target):
    conn = get_db_connection()
    query = """
    SELECT date, SUM(weight * reps * sets) as total_volume 
    FROM workout_logs 
    WHERE muscle_target = ? 
    GROUP BY date 
    ORDER BY date ASC
    LIMIT 20
    """
    df = pd.read_sql_query(query, conn, params=(muscle_target,))
    conn.close()
    return df

# --- UI LAYOUT ---
st.title("⚡ Jetson Gym")

# --- HELPER: CARDIO UNITS ---
def get_cardio_unit(exercise_name):
    name = exercise_name.lower()
    if "row" in name: return "m"
    if "stair" in name: return "floors"
    return "mi"

tab1, tab2, tab3 = st.tabs(["🏋️ WORKOUT", "📈 HISTORY", "🤖 COACH"])

# --- TAB 1: THE WORKOUT ---
with tab1:
    muscle_target = st.radio("Focus Area", ["Chest", "Back", "Legs", "Shoulders", "Arms", "Cardio"], horizontal=True)
    st.divider()

    # 1. PREPARE DATA & EXERCISE LIST
    exercise_name = None
    last_perf = None
    is_cardio = (muscle_target == "Cardio")

    if is_cardio:
        # Fixed Cardio List
        cardio_options = ["Incline Walk", "Treadmill Run", "Outdoor Run", "Row", "Stationary Bike", "Stair Master"]
        c_ex1, c_ex2 = st.columns([1, 2])
        mode = c_ex1.radio("Mode", ["List", "New"], label_visibility="collapsed")
        if mode == "List":
            exercise_name = c_ex2.selectbox("Exercise", cardio_options, label_visibility="collapsed")
        else:
            exercise_name = c_ex2.text_input("Name", placeholder="New Cardio", label_visibility="collapsed")
    else:
        # Standard Weightlifting List
        known_exercises = get_unique_exercises(muscle_target)
        if known_exercises:
            c_ex1, c_ex2 = st.columns([1, 2])
            mode = c_ex1.radio("Mode", ["List", "New"], label_visibility="collapsed")
            if mode == "List":
                exercise_name = c_ex2.selectbox("Exercise", known_exercises, label_visibility="collapsed")
            else:
                exercise_name = c_ex2.text_input("Name", placeholder="New Exercise", label_visibility="collapsed")
        else:
            exercise_name = st.text_input("Exercise Name", placeholder="e.g. Squat")

    # Get Previous Data
    if exercise_name:
        last_perf = get_last_performance(exercise_name)
        if last_perf:
            if is_cardio:
                unit = get_cardio_unit(exercise_name)
                st.info(f"📅 Last: **{last_perf['weight']} {unit}** in **{last_perf['reps']} mins**")
            else:
                st.info(f"📅 Last: **{last_perf['weight']} lbs** x **{last_perf['reps']}**")

    # 2. INPUT FORM (Smart Switching)
    with st.form("log_set_form"):
        c1, c2, c3 = st.columns(3)
        
        # Defaults
        def_val_1 = float(last_perf['weight']) if last_perf else 0.0
        def_val_2 = int(last_perf['reps']) if last_perf else (30 if is_cardio else 8)
        
        if is_cardio:
            # CARDIO INPUTS
            unit = get_cardio_unit(exercise_name) if exercise_name else "mi"
            
            with c1: 
                # Map Distance -> Weight Column
                weight = st.number_input(f"Dist ({unit})", value=def_val_1, step=0.5)
            with c2: 
                # Map Time -> Reps Column
                reps = st.number_input("Time (min)", value=def_val_2, step=1)
            with c3: 
                # Sets usually 1 for cardio
                sets = st.number_input("Sets", value=1, disabled=True)
        else:
            # LIFTING INPUTS
            with c1: weight = st.number_input("Lbs", value=def_val_1, step=5.0)
            with c2: reps = st.number_input("Reps", value=def_val_2, step=1)
            with c3: sets = st.number_input("Sets", value=3, step=1)

        submitted = st.form_submit_button("LOG ACTIVITY ➕", type="primary")
        
        if submitted:
            if exercise_name:
                add_set(muscle_target, exercise_name, weight, reps, sets)
                st.toast(f"Saved {exercise_name}!", icon="🏃" if is_cardio else "🏋️")
                time.sleep(0.5)
                st.rerun()
            else:
                st.error("Enter a name.")

    # 3. LIVE SESSION VIEW
    st.subheader("Today's Session")
    df_today = get_todays_workout_df() 
    
    if not df_today.empty:
        # Calculate Volume (Logic depends on type)
        # We just sum generic volume for the top metric, specific cards handle display
        total_vol = (df_today['weight'] * df_today['reps'] * df_today['sets']).sum()
        exercises_count = df_today['exercise_name'].nunique()
        
        c1, c2 = st.columns(2)
        c1.metric("Total Load", f"{int(total_vol):,}")
        c2.metric("Exercises", exercises_count)
        
        st.markdown("---")

        unique_exercises = df_today['exercise_name'].unique()
        
        for ex_name in unique_exercises[::-1]:  # Reverse order for recent first
            ex_data = df_today[df_today['exercise_name'] == ex_name]
            
            # Check if this specific exercise row is cardio
            # We check the first row of this group to determine type
            is_ex_cardio = ex_data.iloc[0]['muscle_target'] == "Cardio"
            unit = get_cardio_unit(ex_name) if is_ex_cardio else "lbs"
            
            total_sets_ex = ex_data['sets'].sum()
            best_stat = ex_data['weight'].max() # Max Distance or Max Weight

            set_rows_html = ""
            set_counter = 1
            
            for _, row in ex_data.iterrows():
                current_sets = int(row['sets'])
                for _ in range(current_sets):
                    
                    # FORMATTING LOGIC
                    if is_ex_cardio:
                        # Cardio Format: "3.5 mi in 30 mins"
                        display_text = f'{row["weight"]} {unit} <span style="color: #666; font-weight: normal;">in {row["reps"]} mins</span>'
                    else:
                        # Lifting Format: "135 lbs x 10"
                        display_text = f'{row["weight"]} lbs <span style="color: #666; font-weight: normal;">x {row["reps"]}</span>'

                    set_rows_html += (
                        f'<div style="display: flex; justify-content: space-between; border-bottom: 1px solid #333; padding: 4px 0;">'
                        f'<span style="color: #888; font-size: 0.9em;">Set {set_counter}</span>'
                        f'<span style="color: #FFF; font-weight: bold;">{display_text}</span>'
                        f'</div>'
                    )
                    set_counter += 1

            st.markdown(f"""
            <div style="background-color: #1E1E1E; border-radius: 12px; padding: 15px; margin-bottom: 15px; border-left: 4px solid #FF4B4B; box-shadow: 0 4px 6px rgba(0,0,0,0.3);">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                    <h3 style="margin: 0; padding: 0; color: #FAFAFA; font-size: 1.2rem;">{ex_name}</h3>
                    <span style="background: #333; color: #FFF; padding: 2px 8px; border-radius: 4px; font-size: 0.8em;">{total_sets_ex} Sets</span>
                </div>
                <div style="background: #262626; border-radius: 8px; padding: 10px;">{set_rows_html}</div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("Workout empty. Go lift something.")

# --- TAB 2: HISTORY ---
with tab2:
    st.subheader(f"Progress: {muscle_target}")
    vol_df = get_volume_history(muscle_target)
    
    if not vol_df.empty:
        st.area_chart(vol_df.set_index('date'))
    else:
        st.info("Log more workouts to see charts!")

    st.subheader("Raw Data")
    conn = get_db_connection()
    all_logs = pd.read_sql_query("SELECT * FROM workout_logs ORDER BY date DESC LIMIT 50", conn)
    st.dataframe(all_logs, hide_index=True)
    conn.close()

# --- TAB 3: COACH ---
with tab3:
    st.header("🧠 Post-Workout Analysis")
    if df_today.empty:
        st.warning("Log a workout first.")
    else:
        if st.button("Generate Report ✨"):
            with st.spinner("Analyzing..."):
                history_df = get_volume_history(muscle_target)
                prev_volume = history_df.iloc[-2]['total_volume'] if len(history_df) > 1 else 0
                
                # Update prompt to explain Cardio data mapping
                prompt = f"""
                Act as a strength and conditioning coach. 
                
                Target: {muscle_target}
                Today's Workout Data: {df_today.to_dict('records')}
                
                NOTE ON DATA:
                - If Target is 'Cardio': 'weight' = Distance, 'reps' = Minutes.
                - If Target is 'Weightlifting': 'weight' = Lbs, 'reps' = Reps.
                
                Provide in Markdown:
                1. **Efficiency Score** (1-10)
                2. **Analysis**: (Pacing/Intensity/Volume)
                3. **Recommendation**: (Specific adjustment for next time)
                Keep it under 100 words.
                """
                
                try:
                    response = ollama.chat(model=MODEL_NAME, messages=[{'role': 'user', 'content': prompt}])
                    st.markdown(response['message']['content'])
                except Exception as e:
                    st.error(f"AI Error: {e}")