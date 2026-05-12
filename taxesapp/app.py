from flask import Flask, Blueprint, render_template, request, redirect, url_for
import sqlite3
import os

taxes_bp = Blueprint('taxes', __name__, template_folder='templates')
DB = os.path.join(os.path.dirname(__file__), 'taxes.db')
PEOPLE = ['Mom', 'Shannon', 'Trey']

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS taxes_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            label TEXT NOT NULL,
            added_by TEXT NOT NULL,
            completed INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS taxes_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER NOT NULL,
            note TEXT NOT NULL,
            added_by TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    conn.commit()
    conn.close()

@taxes_bp.route('/')
def index():
    conn = get_db()
    items = conn.execute('SELECT * FROM taxes_items ORDER BY completed, id').fetchall()
    notes = {}
    for item in items:
        notes[item['id']] = conn.execute(
            'SELECT * FROM taxes_notes WHERE item_id=? ORDER BY created_at', (item['id'],)
        ).fetchall()
    conn.close()
    return render_template('taxes/index.html', items=items, notes=notes, people=PEOPLE)

@taxes_bp.route('/item/new', methods=['GET', 'POST'])
def new_item():
    if request.method == 'POST':
        label = request.form['label'].strip()
        added_by = request.form['added_by']
        conn = get_db()
        conn.execute('INSERT INTO taxes_items (label, added_by) VALUES (?, ?)', (label, added_by))
        conn.commit()
        conn.close()
        return redirect(url_for('.index'))
    return render_template('taxes/item_form.html', people=PEOPLE)

@taxes_bp.route('/item/<int:id>/complete', methods=['POST'])
def complete_item(id):
    conn = get_db()
    item = conn.execute('SELECT completed FROM taxes_items WHERE id=?', (id,)).fetchone()
    conn.execute('UPDATE taxes_items SET completed=? WHERE id=?', (0 if item['completed'] else 1, id))
    conn.commit()
    conn.close()
    return redirect(url_for('.index'))

@taxes_bp.route('/item/<int:id>/note', methods=['POST'])
def add_note(id):
    note = request.form['note'].strip()
    added_by = request.form['added_by']
    if note:
        conn = get_db()
        conn.execute(
            'INSERT INTO taxes_notes (item_id, note, added_by) VALUES (?, ?, ?)',
            (id, note, added_by)
        )
        conn.commit()
        conn.close()
    return redirect(url_for('.index'))

@taxes_bp.route('/item/<int:id>/delete', methods=['POST'])
def delete_item(id):
    conn = get_db()
    conn.execute('DELETE FROM taxes_notes WHERE item_id=?', (id,))
    conn.execute('DELETE FROM taxes_items WHERE id=?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('.index'))

init_db()

app = Flask(__name__)
app.register_blueprint(taxes_bp)

if __name__ == '__main__':
    app.run(debug=True)
