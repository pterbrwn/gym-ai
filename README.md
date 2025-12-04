# Gym AI

A Streamlit-based gym workout tracker with AI-powered coaching using Ollama.

## Features

- Track workouts by muscle group (Chest, Back, Legs, Shoulders, Arms, Cardio)
- Log exercises with weight, reps, sets
- View today's session summary
- Progress history with volume charts
- AI coach for post-workout analysis

## Prerequisites

- Python 3.x
- Ollama installed with llama3.2 model
- Streamlit

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/pterbrwn/gym-ai.git
   cd gym-ai
   ```

2. Install dependencies:
   ```bash
   pip install streamlit pandas ollama
   ```

3. Initialize the database:
   ```bash
   python init_db.py
   ```

4. Ensure Ollama is running with the llama3.2 model:
   ```bash
   ollama pull llama3.2
   ```

## Usage

Run the app:
```bash
streamlit run app.py --server.address=0.0.0.0
```

Open your browser to the provided URL and start tracking your workouts!

## Database

The app uses SQLite (`gym_data.db`) to store workout logs and AI feedback.