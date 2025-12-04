import sqlite3

def init_db():
    conn = sqlite3.connect('gym_data.db')
    c = conn.cursor()
    
    # Table for logging individual sets
    c.execute('''
        CREATE TABLE IF NOT EXISTS workout_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT DEFAULT CURRENT_DATE,
            muscle_target TEXT,
            exercise_name TEXT,
            weight REAL,
            reps INTEGER,
            sets INTEGER
        )
    ''')
    
    # Table for AI Feedback history
    c.execute('''
        CREATE TABLE IF NOT EXISTS ai_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT DEFAULT CURRENT_DATE,
            score INTEGER,
            feedback TEXT
        )
    ''')
    
    conn.commit()
    conn.close()
    print("Database initialized successfully.")

if __name__ == "__main__":
    init_db()
