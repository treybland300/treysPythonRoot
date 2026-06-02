import os
from flask import Flask, render_template, request, redirect, url_for
import psycopg2
from psycopg2.extras import RealDictCursor
from urllib.parse import urlparse

app = Flask(__name__)

DATABASE_URL = os.environ.get('DATABASE_URL')
PEOPLE = ['Mom', 'Shannon', 'Trey']

def get_db():
    result = urlparse(DATABASE_URL)
    return psycopg2.connect(
        host=result.hostname,
        port=result.port,
        database=result.path[1:],
        user=result.username,
        password=result.password,
        sslmode='require'
    )

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS taxes_items (
            id SERIAL PRIMARY KEY,
            label TEXT NOT NULL,
            added_by TEXT NOT NULL,
            completed INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT NOW()
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS taxes_notes (
            id SERIAL PRIMARY KEY,
            item_id INTEGER NOT NULL REFERENCES taxes_items(id) ON DELETE CASCADE,
            note TEXT NOT NULL,
            added_by TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT NOW()
        )
    ''')
    conn.commit()
    cur.close()
    conn.close()

init_db()

@app.route('/')
def index():
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute('SELECT * FROM taxes_items ORDER BY completed, id')
    items = cur.fetchall()
    notes = {}
    for item in items:
        cur.execute(
            'SELECT * FROM taxes_notes WHERE item_id=%s ORDER BY created_at', (item['id'],)
        )
        notes[item['id']] = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('taxes/index.html', items=items, notes=notes, people=PEOPLE)

@app.route('/item/new', methods=['GET', 'POST'])
def new_item():
    if request.method == 'POST':
        label = request.form['label'].strip()
        added_by = request.form['added_by']
        conn = get_db()
        cur = conn.cursor()
        cur.execute('INSERT INTO taxes_items (label, added_by) VALUES (%s, %s)', (label, added_by))
        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for('index'))
    return render_template('taxes/item_form.html', people=PEOPLE)

@app.route('/item/<int:id>/complete', methods=['POST'])
def complete_item(id):
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute('SELECT completed FROM taxes_items WHERE id=%s', (id,))
    item = cur.fetchone()
    cur.execute('UPDATE taxes_items SET completed=%s WHERE id=%s', (0 if item['completed'] else 1, id))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('index'))

@app.route('/item/<int:id>/note', methods=['POST'])
def add_note(id):
    note = request.form['note'].strip()
    added_by = request.form['added_by']
    if note:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            'INSERT INTO taxes_notes (item_id, note, added_by) VALUES (%s, %s, %s)',
            (id, note, added_by)
        )
        conn.commit()
        cur.close()
        conn.close()
    return redirect(url_for('index'))

@app.route('/item/<int:id>/delete', methods=['POST'])
def delete_item(id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute('DELETE FROM taxes_items WHERE id=%s', (id,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=False)
