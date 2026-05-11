from flask import Flask, Blueprint, render_template, request, redirect, url_for
import sqlite3
import os

packing_bp = Blueprint('packing', __name__, template_folder='templates')
DB = os.path.join(os.path.dirname(__file__), 'packing.db')

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS master_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS trips (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            date TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS trip_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trip_id INTEGER,
            master_item_id INTEGER,
            packed_by TEXT DEFAULT NULL,
            FOREIGN KEY (trip_id) REFERENCES trips(id),
            FOREIGN KEY (master_item_id) REFERENCES master_items(id)
        );
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            active INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL
        );
    ''')
    conn.commit()
    conn.close()

@packing_bp.route('/')
def index():
    conn = get_db()
    trips = conn.execute('SELECT * FROM trips ORDER BY date DESC').fetchall()
    conn.close()
    return render_template('packing/index.html', trips=trips)

@packing_bp.route('/master', methods=['GET', 'POST'])
def master():
    conn = get_db()
    last_category = ''
    if request.method == 'POST':
        name = request.form['name']
        last_category = request.form['category']
        conn.execute('INSERT INTO master_items (name, category) VALUES (?, ?)', (name, last_category))
        conn.commit()
    items = conn.execute('SELECT * FROM master_items ORDER BY category, name').fetchall()
    categories = conn.execute('SELECT * FROM categories ORDER BY name').fetchall()
    conn.close()
    return render_template('packing/master.html', items=items, categories=categories, last_category=last_category)

@packing_bp.route('/master/delete/<int:id>')
def delete_master_item(id):
    conn = get_db()
    conn.execute('DELETE FROM master_items WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('.master'))

@packing_bp.route('/categories', methods=['GET', 'POST'])
def categories():
    conn = get_db()
    if request.method == 'POST':
        name = request.form['name'].strip()
        if name:
            conn.execute('INSERT INTO categories (name) VALUES (?)', (name,))
            conn.commit()
    all_categories = conn.execute('SELECT * FROM categories ORDER BY name').fetchall()
    conn.close()
    return render_template('packing/categories.html', categories=all_categories)

@packing_bp.route('/categories/delete/<int:id>')
def delete_category(id):
    conn = get_db()
    conn.execute('DELETE FROM categories WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('.categories'))

@packing_bp.route('/users', methods=['GET', 'POST'])
def users():
    conn = get_db()
    if request.method == 'POST':
        name = request.form['name'].strip()
        if name:
            conn.execute('INSERT INTO users (name, active) VALUES (?, 1)', (name,))
            conn.commit()
    all_users = conn.execute('SELECT * FROM users ORDER BY name').fetchall()
    conn.close()
    return render_template('packing/users.html', users=all_users)

@packing_bp.route('/users/toggle/<int:id>')
def toggle_user(id):
    conn = get_db()
    user = conn.execute('SELECT active FROM users WHERE id = ?', (id,)).fetchone()
    new_status = 0 if user['active'] else 1
    conn.execute('UPDATE users SET active = ? WHERE id = ?', (new_status, id))
    conn.commit()
    conn.close()
    return redirect(url_for('.users'))

@packing_bp.route('/users/delete/<int:id>')
def delete_user(id):
    conn = get_db()
    conn.execute('DELETE FROM users WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('.users'))

@packing_bp.route('/trips/new', methods=['GET', 'POST'])
def new_trip():
    conn = get_db()
    if request.method == 'POST':
        name = request.form['name']
        date = request.form['date']
        selected = request.form.getlist('items')
        conn.execute('INSERT INTO trips (name, date) VALUES (?, ?)', (name, date))
        trip_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
        for item_id in selected:
            conn.execute('INSERT INTO trip_items (trip_id, master_item_id) VALUES (?, ?)', (trip_id, item_id))
        conn.commit()
        conn.close()
        return redirect(url_for('.trip', id=trip_id))
    items = conn.execute('SELECT * FROM master_items ORDER BY category, name').fetchall()
    conn.close()
    return render_template('packing/new_trip.html', items=items)

@packing_bp.route('/trip/<int:id>')
def trip(id):
    conn = get_db()
    trip = conn.execute('SELECT * FROM trips WHERE id = ?', (id,)).fetchone()
    items = conn.execute('''
        SELECT ti.id, mi.name, mi.category, ti.packed_by
        FROM trip_items ti
        JOIN master_items mi ON ti.master_item_id = mi.id
        WHERE ti.trip_id = ?
        ORDER BY mi.category, mi.name
    ''', (id,)).fetchall()
    active_users = conn.execute('SELECT * FROM users WHERE active = 1 ORDER BY name').fetchall()
    conn.close()
    return render_template('packing/trip.html', trip=trip, items=items, active_users=active_users)

@packing_bp.route('/trip/<int:trip_id>/pack/<int:item_id>/<user>')
def pack_item(trip_id, item_id, user):
    conn = get_db()
    conn.execute('UPDATE trip_items SET packed_by = ? WHERE id = ?', (user, item_id))
    conn.commit()
    conn.close()
    from flask import jsonify
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        conn2 = get_db()
        total = conn2.execute('SELECT COUNT(*) FROM trip_items WHERE trip_id = ?', (trip_id,)).fetchone()[0]
        packed = conn2.execute('SELECT COUNT(*) FROM trip_items WHERE trip_id = ? AND packed_by IS NOT NULL', (trip_id,)).fetchone()[0]
        conn2.close()
        pct = int((packed / total) * 100) if total > 0 else 0
        return jsonify(success=True, packed_by=user, packed=packed, total=total, pct=pct)
    return redirect(url_for('.trip', id=trip_id))

@packing_bp.route('/trip/<int:trip_id>/unpack/<int:item_id>')
def unpack_item(trip_id, item_id):
    conn = get_db()
    conn.execute('UPDATE trip_items SET packed_by = NULL WHERE id = ?', (item_id,))
    conn.commit()
    conn.close()
    from flask import jsonify
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        conn2 = get_db()
        total = conn2.execute('SELECT COUNT(*) FROM trip_items WHERE trip_id = ?', (trip_id,)).fetchone()[0]
        packed = conn2.execute('SELECT COUNT(*) FROM trip_items WHERE trip_id = ? AND packed_by IS NOT NULL', (trip_id,)).fetchone()[0]
        conn2.close()
        pct = int((packed / total) * 100) if total > 0 else 0
        return jsonify(success=True, packed_by=None, packed=packed, total=total, pct=pct)
    return redirect(url_for('.trip', id=trip_id))

@packing_bp.route('/trip/<int:id>/add_items', methods=['GET', 'POST'])
def add_trip_items(id):
    conn = get_db()
    if request.method == 'POST':
        selected = request.form.getlist('items')
        for item_id in selected:
            exists = conn.execute(
                'SELECT id FROM trip_items WHERE trip_id = ? AND master_item_id = ?', (id, item_id)
            ).fetchone()
            if not exists:
                conn.execute('INSERT INTO trip_items (trip_id, master_item_id) VALUES (?, ?)', (id, item_id))
        conn.commit()
        conn.close()
        return redirect(url_for('.trip', id=id))
    trip = conn.execute('SELECT * FROM trips WHERE id = ?', (id,)).fetchone()
    existing = [r['master_item_id'] for r in conn.execute('SELECT master_item_id FROM trip_items WHERE trip_id = ?', (id,)).fetchall()]
    all_items = conn.execute('SELECT * FROM master_items ORDER BY category, name').fetchall()
    available = [item for item in all_items if item['id'] not in existing]
    conn.close()
    return render_template('packing/add_trip_items.html', trip=trip, items=available)

@packing_bp.route('/trip/<int:id>/delete')
def delete_trip(id):
    conn = get_db()
    conn.execute('DELETE FROM trip_items WHERE trip_id = ?', (id,))
    conn.execute('DELETE FROM trips WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('.index'))

init_db()

app = Flask(__name__)
app.register_blueprint(packing_bp)

if __name__ == '__main__':
    app.run(debug=True)
