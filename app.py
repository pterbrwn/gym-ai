import streamlit as st
import sqlite3
import ollama
import pandas as pd
from datetime import date
import time
import coach

# --- CONFIGURATION ---
DB_NAME = 'gym_data.db'
MODEL_NAME = 'llama3.2' 

# --- CUSTOM CSS ---
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
    conn.execute("INSERT INTO workout_logs (date, muscle_target, exercise_name, weight, reps, sets) VALUES (?, ?, ?, ?, ?, ?)",
              (date.today().isoformat(), target, exercise, weight, reps, sets))
    conn.commit()
    conn.close()

def update_log(row_id, weight, reps, sets):
    conn = get_db_connection()
    conn.execute("UPDATE workout_logs SET weight = ?, reps = ?, sets = ? WHERE id = ?", 
                 (weight, reps, sets, row_id))
    conn.commit()
    conn.close()

def delete_log(row_id):
    conn = get_db_connection()
    conn.execute("DELETE FROM workout_logs WHERE id = ?", (row_id,))
    conn.commit()
    conn.close()

def get_todays_workout_df():
    conn = get_db_connection()
    today_str = date.today().isoformat()
    df = pd.read_sql_query("SELECT id, muscle_target, exercise_name, weight, reps, sets FROM workout_logs WHERE date = ?", conn, params=(today_str,))
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

def get_cardio_unit(exercise_name):
    name = exercise_name.lower()
    if "row" in name: return "m"
    if "stair" in name: return "floors"
    return "mi"

# --- UI LAYOUT ---
st.title("⚡ Jetson Gym")

tab1, tab2, tab3 = st.tabs(["🏋️ WORKOUT", "📈 HISTORY", "🤖 COACH"])

# --- TAB 1: THE WORKOUT ---
with tab1:
    # 1. MUSCLE TARGET
    muscle_target = st.radio("Focus Area", ["Chest", "Back", "Legs", "Shoulders", "Arms", "Core", "Cardio"], horizontal=True)
    st.divider()

    # Logic flags
    is_cardio = (muscle_target == "Cardio")
    is_core = (muscle_target == "Core")
    
    # 2. EXERCISE SELECTION
    exercise_name = None
    
    if is_cardio:
        cardio_options = ["Incline Walk", "Treadmill Run", "Outdoor Run", "Row", "Stationary Bike", "Stair Master"]
        c_ex1, c_ex2 = st.columns([1, 2])
        mode = c_ex1.radio("Mode", ["List", "New"], label_visibility="collapsed")
        if mode == "List":
            exercise_name = c_ex2.selectbox("Exercise", cardio_options, label_visibility="collapsed")
        else:
            exercise_name = c_ex2.text_input("Name", placeholder="New Cardio", label_visibility="collapsed")
    else:
        known_exercises = get_unique_exercises(muscle_target)
        if known_exercises:
            c_ex1, c_ex2 = st.columns([1, 2])
            mode = c_ex1.radio("Mode", ["List", "New"], label_visibility="collapsed")
            if mode == "List":
                exercise_name = c_ex2.selectbox("Exercise", known_exercises, label_visibility="collapsed")
            else:
                exercise_name = c_ex2.text_input("Name", placeholder="New Exercise", label_visibility="collapsed")
        else:
            exercise_name = st.text_input("Exercise Name", placeholder="e.g. Plank")

    # 3. TYPE SELECTION (MOVED OUTSIDE FORM FOR INSTANT UPDATES)
    core_type = "Weighted / Reps" # Default
    if is_core:
        # This now triggers an immediate page refresh when clicked
        core_type = st.radio("Core Type", ["Weighted / Reps", "Timed (Plank)"], horizontal=True)

    # 4. CONTEXT & DEFAULTS
    last_perf = None
    if exercise_name:
        last_perf = get_last_performance(exercise_name)
        if last_perf:
            if is_cardio:
                unit = get_cardio_unit(exercise_name)
                st.info(f"📅 Last: **{last_perf['weight']} {unit}** in **{last_perf['reps']} mins**")
            elif is_core and last_perf['weight'] == 0:
                 st.info(f"📅 Last: **{last_perf['reps']} secs** (Timed)")
            else:
                st.info(f"📅 Last: **{last_perf['weight']} lbs** x **{last_perf['reps']}**")

    # 5. THE FORM
    with st.form("log_set_form"):
        c1, c2, c3 = st.columns(3)
        
        # Calculate Defaults
        def_w = float(last_perf['weight']) if last_perf else 0.0
        # If switching to Timed Core, default to 30s instead of rep count
        if is_core and core_type == "Timed (Plank)":
            def_r = int(last_perf['reps']) if last_perf and last_perf['weight'] == 0 else 30
        else:
            def_r = int(last_perf['reps']) if last_perf else 10
        
        # RENDER INPUTS BASED ON SELECTIONS
        if is_cardio:
            unit = get_cardio_unit(exercise_name) if exercise_name else "mi"
            with c1: weight = st.number_input(f"Dist ({unit})", value=def_w, step=0.1)
            with c2: reps = st.number_input("Time (min)", value=def_r, step=1)
            with c3: sets = st.number_input("Sets", value=1, disabled=True)
            
        elif is_core:
            if core_type == "Timed (Plank)":
                with c1: weight = st.number_input("Weight", value=0.0, disabled=True)
                # This label will now correctly show "Time (Secs)" immediately
                with c2: reps = st.number_input("Time (Secs)", value=def_r, step=5)
                with c3: sets = st.number_input("Sets", value=3, step=1)
            else:
                with c1: weight = st.number_input("Weight (lbs)", value=def_w, step=2.5)
                with c2: reps = st.number_input("Reps", value=def_r, step=1)
                with c3: sets = st.number_input("Sets", value=3, step=1)
        
        else:
            # Standard Lifting
            with c1: weight = st.number_input("Lbs", value=def_w, step=5.0)
            with c2: reps = st.number_input("Reps", value=def_r, step=1)
            with c3: sets = st.number_input("Sets", value=3, step=1)

        submitted = st.form_submit_button("LOG SET ➕", type="primary")
        
        if submitted:
            if exercise_name:
                add_set(muscle_target, exercise_name, weight, reps, sets)
                st.toast(f"Saved {exercise_name}!", icon="✅")
                time.sleep(0.5)
                st.rerun()
            else:
                st.error("Enter a name.")

    # 6. SESSION VIEW & MANAGER
    st.subheader("Today's Session")
    df_today = get_todays_workout_df() 
    
    if not df_today.empty:
        edit_mode = st.toggle("✏️ Manager Mode (Edit / Delete)")
        
        if edit_mode:
            st.caption("Edit values directly below. Uncheck to save/view.")
            edited_df = st.data_editor(
                df_today, 
                column_config={
                    "id": None,
                    "muscle_target": st.column_config.TextColumn(disabled=True),
                    "exercise_name": st.column_config.TextColumn(disabled=True),
                },
                num_rows="dynamic",
                key="editor"
            )
            
            if st.button("💾 Apply Changes"):
                original_ids = set(df_today['id'])
                current_ids = set(edited_df['id'])
                
                # Deletions
                deleted_ids = original_ids - current_ids
                for row_id in deleted_ids:
                    delete_log(row_id)
                
                # Updates
                for index, row in edited_df.iterrows():
                    update_log(row['id'], row['weight'], row['reps'], row['sets'])
                
                st.toast("Logs Updated!", icon="💾")
                time.sleep(0.5)
                st.rerun()
        
        else:
            # View Mode
            total_vol = (df_today['weight'] * df_today['reps'] * df_today['sets']).sum()
            c1, c2 = st.columns(2)
            c1.metric("Total Load", f"{int(total_vol):,}")
            c2.metric("Exercises", df_today['exercise_name'].nunique())
            
            st.markdown("---")
            unique_exercises = df_today['exercise_name'].unique()
            
            for ex_name in unique_exercises[::-1]:
                ex_data = df_today[df_today['exercise_name'] == ex_name]
                
                first_row = ex_data.iloc[0]
                is_ex_cardio = first_row['muscle_target'] == "Cardio"
                is_ex_core = first_row['muscle_target'] == "Core"
                unit = get_cardio_unit(ex_name) if is_ex_cardio else "lbs"
                
                total_sets_ex = ex_data['sets'].sum()

                set_rows_html = ""
                set_counter = 1
                
                for _, row in ex_data.iterrows():
                    current_sets = int(row['sets'])
                    for _ in range(current_sets):
                        
                        if is_ex_cardio:
                            display_text = f'{row["weight"]} {unit} <span style="color: #666;">in {row["reps"]} min</span>'
                        elif is_ex_core and row['weight'] == 0:
                            display_text = f'{row["reps"]} <span style="color: #666;">secs</span>'
                        else:
                            display_text = f'{row["weight"]} lbs <span style="color: #666;">x {row["reps"]}</span>'

                        set_rows_html += (
                            f'<div style="display: flex; justify-content: space-between; border-bottom: 1px solid #333; padding: 4px 0;">'
                            f'<span style="color: #888; font-size: 0.9em;">Set {set_counter}</span>'
                            f'<span style="color: #FFF; font-weight: bold;">{display_text}</span>'
                            f'</div>'
                        )
                        set_counter += 1

                st.markdown(f"""
                <div style="background-color: #1E1E1E; border-radius: 12px; padding: 15px; margin-bottom: 15px; border-left: 4px solid #FF4B4B;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                        <h3 style="margin: 0; color: #FAFAFA; font-size: 1.2rem;">{ex_name}</h3>
                        <span style="background: #333; color: #FFF; padding: 2px 8px; border-radius: 4px; font-size: 0.8em;">{total_sets_ex} Sets</span>
                    </div>
                    <div style="background: #262626; border-radius: 8px; padding: 10px;">{set_rows_html}</div>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.info("No logs today.")

# --- TAB 2: HISTORY ---
with tab2:
    # 1. Add a specific selector for History (Defaults to the one selected in Tab 1)
    # We use index matching to set the default value
    all_muscles = ["Chest", "Back", "Legs", "Shoulders", "Arms", "Core", "Cardio"]
    default_ix = all_muscles.index(muscle_target) if muscle_target in all_muscles else 0
    
    history_target = st.selectbox("Graph Focus Area", all_muscles, index=default_ix)
    
    # 2. Get Data for the SELECTED history target, not the Tab 1 target
    vol_df = get_volume_history(history_target)
    
    st.subheader(f"Volume Progression: {history_target}")
    
    if not vol_df.empty:
        # Check if we have enough data for a line
        if len(vol_df) < 2:
            st.warning("Not enough data to draw a line yet. (Need workouts on 2 different days).")
            # Show a bar chart instead if only 1 day exists, so it's not invisible
            st.bar_chart(vol_df.set_index('date'))
        else:
            st.area_chart(vol_df.set_index('date'))
    else:
        st.info(f"No history found for {history_target}.")

    st.divider()
    st.subheader("Raw Logbook")
    conn = get_db_connection()
    all_logs = pd.read_sql_query("SELECT * FROM workout_logs ORDER BY date DESC LIMIT 50", conn)
    st.dataframe(all_logs, hide_index=True)
    conn.close()

# --- TAB 3: COACH ---
with tab3:
    st.header("🧠 Performance Review")
    
    # Show a "Profile Badge" so you know the AI knows who you are
    st.caption("Athlete Profile: D1 Soccer / 28yo / Lean & Strong")
    
    if df_today.empty:
        st.warning("Training log empty. Complete the session first.")
    else:
        if st.button("Analyze Performance ⚡"):
            with st.spinner("Coach is reviewing the tapes..."):
                # Fetch history for context
                history_df = get_volume_history(muscle_target)
                
                # Convert DataFrame to list of dicts for the AI
                todays_data_list = df_today.to_dict('records')
                
                # CALL THE NEW BRAIN
                analysis = coach.generate_analysis(
                    muscle_target, 
                    todays_data_list, 
                    history_df, 
                    MODEL_NAME
                )
                
                st.markdown(analysis)