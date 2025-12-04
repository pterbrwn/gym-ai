import ollama

# --- USER PROFILE (The "Context") ---
# We hardcode this so the AI knows who it's talking to every time.
USER_PROFILE = """
User Profile:
- Age: 28, Male.
- History: Former Division 1 Soccer Player.
- Current Status: 4x/week training, fit but wants to increase frequency.
- Goal: "Lean, Fit, Strong" (Athletic Aesthetic, not Bodybuilder bulk).
- Struggle: Diet/Nutrition.
"""

def generate_analysis(muscle_target, todays_data, history_df, model_name='llama3.2'):
    
    # 1. Calculate Data Context
    # We summarize the data in Python first so the AI doesn't have to do math
    total_vol = 0
    duration_est = 0
    
    # Rough math to give the AI a sense of scale
    for item in todays_data:
        # Volume = weight * sets * reps
        total_vol += (item['weight'] * item['reps'] * item['sets'])
        # Duration estimate: 2 mins per set (lifting) or actual time (cardio)
        if muscle_target == "Cardio":
            duration_est += item['reps'] # reps is time in min
        else:
            duration_est += (item['sets'] * 2.5) # approx 2.5 mins per set including rest

    # 2. Get previous volume for comparison
    prev_vol = 0
    if not history_df.empty:
        # Get the average volume of the last 3 workouts to smooth out data
        prev_vol = history_df.tail(3)['total_volume'].mean()

    # 3. THE PROMPT
    prompt = f"""
    You are an elite Strength & Conditioning Coach for high-level athletes. 
    You are speaking to a former D1 Soccer player (28yo). Do not coddle him.
    
    {USER_PROFILE}
    
    SESSION DATA:
    - Target: {muscle_target}
    - Total Volume/Load: {int(total_vol)} lbs (Previous Avg: {int(prev_vol)} lbs)
    - Est. Session Duration: {int(duration_est)} mins
    - Exercises: {[x['exercise_name'] for x in todays_data]}
    - Full Logs: {todays_data}

    INSTRUCTIONS:
    1. **The D1 Grade (1-10)**: 
       - 10 is a professional match-day effort. 
       - 5 is a "maintenance" gym session. 
       - Be harsh. Did he actually push intensity or just go through motions?
    
    2. **Tactical Analysis**: 
       - Compare today's volume to his previous average.
       - If Volume is up >10%: Praise the Progressive Overload.
       - If Volume is down: Ask if this is a deload or laziness.
       - Note: If target is Cardio, look at Pace (Distance/Time).

    3. **The Fuel (CRITICAL)**:
       - Based on the intensity and duration ({int(duration_est)} mins), estimate caloric burn.
       - Prescribe a SPECIFIC post-workout meal to match his "Lean/Strong" goal.
       - Example: "High intensity leg day. You burned ~600 cals. Eat 50g Carb / 40g Protein immediately. No fats."
       - Example: "Low intensity arm day. Keep carbs low. Stick to protein/veggies."

    4. **The Challenge**:
       - Give one specific goal for the next session based on today's weak point.

    Output Format: Markdown. Concise. Professional.
    """

    try:
        response = ollama.chat(model=model_name, messages=[{'role': 'user', 'content': prompt}])
        return response['message']['content']
    except Exception as e:
        return f"Coach is offline (Error: {e})"