from flask import Flask, Blueprint, render_template, request, redirect, url_for
import sqlite3
import os

lifting_bp = Blueprint('lifting', __name__, template_folder='templates')
DB = os.path.join(os.path.dirname(__file__), 'lifting.db')

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS exercises (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            active INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS workouts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS workout_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workout_id INTEGER NOT NULL,
            exercise_id INTEGER NOT NULL,
            weight REAL NOT NULL,
            completed INTEGER NOT NULL DEFAULT 1,
            sets_completed INTEGER,
            reps_last_set INTEGER,
            FOREIGN KEY (workout_id) REFERENCES workouts(id),
            FOREIGN KEY (exercise_id) REFERENCES exercises(id)
        );
        INSERT OR IGNORE INTO exercises (id, name) VALUES
            (1, 'Bench Press'),
            (2, 'Squat'),
            (3, 'Dead Lift'),
            (4, 'Military Press'),
            (5, 'Bent Over Row');
    ''')
    conn.commit()
    conn.close()

@lifting_bp.route('/')
def index():
    conn = get_db()
    workouts = conn.execute('''
        SELECT w.* FROM workouts w
        WHERE EXISTS (SELECT 1 FROM workout_entries we WHERE we.workout_id = w.id)
        ORDER BY date DESC LIMIT 10
    ''').fetchall()
    exercises = conn.execute('SELECT * FROM exercises WHERE active=1 ORDER BY name').fetchall()
    best_weights = {}
    for ex in exercises:
        row = conn.execute('SELECT MAX(weight) as best FROM workout_entries WHERE exercise_id=? AND completed=1', (ex['id'],)).fetchone()
        best_weights[ex['id']] = row['best'] if row and row['best'] is not None else None
    conn.close()
    return render_template('lifting/index.html', workouts=workouts, exercises=exercises, best_weights=best_weights)

@lifting_bp.route('/workout/new', methods=['GET', 'POST'])
def new_workout():
    conn = get_db()
    exercises = conn.execute('SELECT * FROM exercises WHERE active=1 ORDER BY name').fetchall()
    ex_data = {}
    for ex in exercises:
        best = conn.execute('SELECT MAX(weight) as best FROM workout_entries WHERE exercise_id=? AND completed=1', (ex['id'],)).fetchone()
        last_row = conn.execute('''
            SELECT we.weight, we.completed, we.sets_completed, we.reps_last_set FROM workout_entries we
            JOIN workouts w ON we.workout_id = w.id
            WHERE we.exercise_id = ? ORDER BY w.date DESC LIMIT 1
        ''', (ex['id'],)).fetchone()
        last = last_row['weight'] if last_row else None
        last_done = last_row['completed'] if last_row else None
        current = (last + 5) if (last is not None and last_done) else last
        ex_data[ex['id']] = {
            'best': best['best'] if best and best['best'] is not None else None,
            'last': last,
            'current': current,
            'last_completed': last_done,
            'last_sets': last_row['sets_completed'] if last_row else None,
            'last_reps': last_row['reps_last_set'] if last_row else None
        }
    if request.method == 'POST':
        date = request.form['date']
        conn.execute('INSERT INTO workouts (date) VALUES (?)', (date,))
        workout_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
        for ex in exercises:
            val = request.form.get(f'weight_{ex["id"]}', '').strip()
            if val:
                completed = 1 if request.form.get(f'completed_{ex["id"]}') == 'yes' else 0
                sets_done = request.form.get(f'sets_{ex["id"]}') if not completed else None
                reps_done = request.form.get(f'reps_{ex["id"]}') if not completed else None
                conn.execute(
                    'INSERT INTO workout_entries (workout_id, exercise_id, weight, completed, sets_completed, reps_last_set) VALUES (?, ?, ?, ?, ?, ?)',
                    (workout_id, ex['id'], float(val), completed, sets_done, reps_done))
        conn.commit()
        conn.close()
        return redirect(url_for('.workout', id=workout_id))
    from datetime import date
    conn.close()
    return render_template('lifting/new_workout.html', exercises=exercises, ex_data=ex_data, today=date.today().isoformat())

@lifting_bp.route('/workout/<int:id>')
def workout(id):
    conn = get_db()
    w = conn.execute('SELECT * FROM workouts WHERE id=?', (id,)).fetchone()
    entries = conn.execute('''
        SELECT e.name, we.weight, we.completed, we.sets_completed, we.reps_last_set
        FROM workout_entries we
        JOIN exercises e ON we.exercise_id = e.id
        WHERE we.workout_id = ?
        ORDER BY e.name
    ''', (id,)).fetchall()
    conn.close()
    return render_template('lifting/workout.html', workout=w, entries=entries)

@lifting_bp.route('/workout/<int:id>/delete', methods=['POST'])
def delete_workout(id):
    conn = get_db()
    conn.execute('DELETE FROM workout_entries WHERE workout_id=?', (id,))
    conn.execute('DELETE FROM workouts WHERE id=?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('.index'))

@lifting_bp.route('/exercise/<int:id>')
def exercise_history(id):
    conn = get_db()
    ex = conn.execute('SELECT * FROM exercises WHERE id=?', (id,)).fetchone()
    history = conn.execute('''
        SELECT w.date, we.weight FROM workout_entries we
        JOIN workouts w ON we.workout_id = w.id
        WHERE we.exercise_id = ? AND we.completed = 1
        ORDER BY w.date ASC
    ''', (id,)).fetchall()
    conn.close()
    return render_template('lifting/exercise_history.html', exercise=ex, history=history)

@lifting_bp.route('/exercises', methods=['GET', 'POST'])
def exercises():
    conn = get_db()
    if request.method == 'POST':
        name = request.form['name'].strip()
        if name:
            conn.execute('INSERT INTO exercises (name) VALUES (?)', (name,))
            conn.commit()
    all_exercises = conn.execute('SELECT * FROM exercises ORDER BY name').fetchall()
    conn.close()
    return render_template('lifting/exercises.html', exercises=all_exercises)

@lifting_bp.route('/exercise/<int:id>/toggle', methods=['POST'])
def toggle_exercise(id):
    conn = get_db()
    ex = conn.execute('SELECT active FROM exercises WHERE id=?', (id,)).fetchone()
    conn.execute('UPDATE exercises SET active=? WHERE id=?', (0 if ex['active'] else 1, id))
    conn.commit()
    conn.close()
    return redirect(url_for('.exercises'))

init_db()

app = Flask(__name__)
app.register_blueprint(lifting_bp)

if __name__ == '__main__':
    app.run(debug=True)
