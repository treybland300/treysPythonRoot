from flask import Flask, Blueprint, render_template, request, redirect, url_for, jsonify
import sqlite3
import os

todo_bp = Blueprint('todo', __name__, template_folder='templates')
DB = os.path.join(os.path.dirname(__file__), 'todo.db')
LISTS = ['Breakfast', 'Drive In', 'Lunch', 'Drive Out', 'Dinner']

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS todo_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            label TEXT NOT NULL,
            description TEXT,
            active INTEGER DEFAULT 1,
            list_name TEXT NOT NULL,
            sort_order INTEGER DEFAULT 0
        );
    ''')
    conn.commit()
    conn.close()

@todo_bp.route('/')
def index():
    conn = get_db()
    items = {}
    for lst in LISTS:
        items[lst] = conn.execute(
            'SELECT * FROM todo_items WHERE list_name=? ORDER BY sort_order, id', (lst,)
        ).fetchall()
    conn.close()
    return render_template('todo/index.html', lists=LISTS, items=items)

@todo_bp.route('/item/new', methods=['GET', 'POST'])
def new_item():
    preselect = request.args.get('list', LISTS[0])
    if request.method == 'POST':
        label = request.form['label'].strip()
        description = request.form.get('description', '').strip()
        active = 1 if request.form.get('active') else 0
        list_name = request.form['list_name']
        conn = get_db()
        max_order = conn.execute('SELECT MAX(sort_order) as m FROM todo_items WHERE list_name=?', (list_name,)).fetchone()['m'] or 0
        conn.execute(
            'INSERT INTO todo_items (label, description, active, list_name, sort_order) VALUES (?, ?, ?, ?, ?)',
            (label, description, active, list_name, max_order + 1)
        )
        conn.commit()
        conn.close()
        return redirect(url_for('.index'))
    return render_template('todo/item_form.html', item=None, lists=LISTS, preselect=preselect)

@todo_bp.route('/item/<int:id>/edit', methods=['GET', 'POST'])
def edit_item(id):
    conn = get_db()
    item = conn.execute('SELECT * FROM todo_items WHERE id=?', (id,)).fetchone()
    if request.method == 'POST':
        label = request.form['label'].strip()
        description = request.form.get('description', '').strip()
        active = 1 if request.form.get('active') else 0
        list_name = request.form['list_name']
        conn.execute(
            'UPDATE todo_items SET label=?, description=?, active=?, list_name=? WHERE id=?',
            (label, description, active, list_name, id)
        )
        conn.commit()
        conn.close()
        return redirect(url_for('.index'))
    conn.close()
    return render_template('todo/item_form.html', item=item, lists=LISTS, preselect=None)

@todo_bp.route('/item/<int:id>/delete', methods=['POST'])
def delete_item(id):
    conn = get_db()
    conn.execute('DELETE FROM todo_items WHERE id=?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('.index'))

@todo_bp.route('/item/<int:id>/toggle', methods=['POST'])
def toggle_item(id):
    conn = get_db()
    item = conn.execute('SELECT active FROM todo_items WHERE id=?', (id,)).fetchone()
    conn.execute('UPDATE todo_items SET active=? WHERE id=?', (0 if item['active'] else 1, id))
    conn.commit()
    conn.close()
    return ('', 204)

@todo_bp.route('/reorder', methods=['POST'])
def reorder():
    data = request.get_json()
    conn = get_db()
    for entry in data:
        conn.execute('UPDATE todo_items SET sort_order=? WHERE id=?', (entry['order'], entry['id']))
    conn.commit()
    conn.close()
    return jsonify(success=True)

init_db()

app = Flask(__name__)
app.register_blueprint(todo_bp)

if __name__ == '__main__':
    app.run(debug=True)
