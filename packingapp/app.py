import os
from flask import Flask, render_template, request, redirect, url_for, jsonify
import psycopg2
from psycopg2.extras import RealDictCursor
from urllib.parse import urlparse

app = Flask(__name__)

DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db():
    result = urlparse(DATABASE_URL)
    conn = psycopg2.connect(
        host=result.hostname,
        port=result.port,
        database=result.path[1:],
        user=result.username,
        password=result.password,
        sslmode='require'
    )
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            active INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS master_items (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS trips (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            trip_date TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS trip_items (
            id SERIAL PRIMARY KEY,
            trip_id INTEGER REFERENCES trips(id) ON DELETE CASCADE,
            master_item_id INTEGER REFERENCES master_items(id) ON DELETE CASCADE,
            packed_by TEXT DEFAULT NULL,
            packed_at TIMESTAMP DEFAULT NULL
        );
    ''')
    conn.commit()
    cur.close()
    conn.close()

init_db()

@app.route('/')
def index():
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute('SELECT * FROM trips ORDER BY created_at DESC')
    trips = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('index.html', trips=trips)

@app.route('/categories', methods=['GET', 'POST'])
def categories():
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    if request.method == 'POST':
        name = request.form['name'].strip()
        if name:
            cur.execute('INSERT INTO categories (name) VALUES (%s)', (name,))
            conn.commit()
    cur.execute('SELECT * FROM categories ORDER BY name')
    all_categories = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('categories.html', categories=all_categories)

@app.route('/categories/delete/<int:cat_id>', methods=['POST'])
def delete_category(cat_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute('DELETE FROM categories WHERE id = %s', (cat_id,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('categories'))

@app.route('/users', methods=['GET', 'POST'])
def users():
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    if request.method == 'POST':
        name = request.form['name'].strip()
        if name:
            cur.execute('INSERT INTO users (name, active) VALUES (%s, 1)', (name,))
            conn.commit()
    cur.execute('SELECT * FROM users ORDER BY name')
    all_users = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('users.html', users=all_users)

@app.route('/users/toggle/<int:user_id>', methods=['POST'])
def toggle_user(user_id):
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute('SELECT active FROM users WHERE id = %s', (user_id,))
    user = cur.fetchone()
    new_status = 0 if user['active'] else 1
    cur.execute('UPDATE users SET active = %s WHERE id = %s', (new_status, user_id))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('users'))

@app.route('/users/delete/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute('DELETE FROM users WHERE id = %s', (user_id,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('users'))

@app.route('/master')
def master():
    last_category = request.args.get('last_category', '')
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute('SELECT * FROM master_items ORDER BY category, name')
    items = cur.fetchall()
    cur.execute('SELECT * FROM categories ORDER BY name')
    cats = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('master.html', items=items, categories=cats, last_category=last_category)

@app.route('/master/add', methods=['POST'])
def add_master_item():
    name = request.form['name'].strip()
    category = request.form['category'].strip()
    if name and category:
        conn = get_db()
        cur = conn.cursor()
        cur.execute('INSERT INTO master_items (name, category) VALUES (%s, %s)', (name, category))
        conn.commit()
        cur.close()
        conn.close()
    return redirect(url_for('master', last_category=category))

@app.route('/master/delete/<int:item_id>', methods=['POST'])
def delete_master_item(item_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute('DELETE FROM master_items WHERE id = %s', (item_id,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('master'))

@app.route('/trip/new', methods=['GET', 'POST'])
def new_trip():
    if request.method == 'POST':
        name = request.form['name'].strip()
        trip_date = request.form['trip_date']
        selected_items = request.form.getlist('items')
        conn = get_db()
        cur = conn.cursor()
        cur.execute('INSERT INTO trips (name, trip_date) VALUES (%s, %s) RETURNING id', (name, trip_date))
        trip_id = cur.fetchone()[0]
        for item_id in selected_items:
            cur.execute('INSERT INTO trip_items (trip_id, master_item_id) VALUES (%s, %s)', (trip_id, item_id))
        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for('trip_detail', trip_id=trip_id))
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute('SELECT * FROM master_items ORDER BY category, name')
    items = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('new_trip.html', items=items)

@app.route('/trip/<int:trip_id>')
def trip_detail(trip_id):
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute('SELECT * FROM trips WHERE id = %s', (trip_id,))
    trip = cur.fetchone()
    cur.execute('''
        SELECT ti.id, ti.packed_by, ti.packed_at,
               mi.name, mi.category
        FROM trip_items ti
        JOIN master_items mi ON ti.master_item_id = mi.id
        WHERE ti.trip_id = %s
        ORDER BY mi.category, mi.name
    ''', (trip_id,))
    items = cur.fetchall()
    cur.execute('SELECT * FROM users WHERE active = 1 ORDER BY name')
    active_users = cur.fetchall()
    cur.close()
    conn.close()
    total = len(items)
    packed = sum(1 for i in items if i['packed_by'])
    pct = int((packed / total) * 100) if total > 0 else 0
    return render_template('trip.html', trip=trip, items=items, active_users=active_users,
                           total=total, packed=packed, pct=pct)

@app.route('/trip/<int:trip_id>/pack/<int:item_id>', methods=['POST'])
def pack_item(trip_id, item_id):
    packer = request.form.get('packer', 'Unknown')
    conn = get_db()
    cur = conn.cursor()
    cur.execute('UPDATE trip_items SET packed_by = %s, packed_at = NOW() WHERE id = %s', (packer, item_id))
    conn.commit()
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        cur.execute('SELECT COUNT(*) FROM trip_items WHERE trip_id = %s', (trip_id,))
        total = cur.fetchone()[0]
        cur.execute('SELECT COUNT(*) FROM trip_items WHERE trip_id = %s AND packed_by IS NOT NULL', (trip_id,))
        packed = cur.fetchone()[0]
        cur.close()
        conn.close()
        pct = int((packed / total) * 100) if total > 0 else 0
        return jsonify(success=True, packed_by=packer, packed=packed, total=total, pct=pct)
    cur.close()
    conn.close()
    return redirect(url_for('trip_detail', trip_id=trip_id))

@app.route('/trip/<int:trip_id>/unpack/<int:item_id>', methods=['POST'])
def unpack_item(trip_id, item_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute('UPDATE trip_items SET packed_by = NULL, packed_at = NULL WHERE id = %s', (item_id,))
    conn.commit()
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        cur.execute('SELECT COUNT(*) FROM trip_items WHERE trip_id = %s', (trip_id,))
        total = cur.fetchone()[0]
        cur.execute('SELECT COUNT(*) FROM trip_items WHERE trip_id = %s AND packed_by IS NOT NULL', (trip_id,))
        packed = cur.fetchone()[0]
        cur.close()
        conn.close()
        pct = int((packed / total) * 100) if total > 0 else 0
        return jsonify(success=True, packed_by=None, packed=packed, total=total, pct=pct)
    cur.close()
    conn.close()
    return redirect(url_for('trip_detail', trip_id=trip_id))

@app.route('/trip/<int:trip_id>/add_items', methods=['GET', 'POST'])
def add_trip_items(trip_id):
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    if request.method == 'POST':
        selected = request.form.getlist('items')
        for item_id in selected:
            cur.execute(
                'SELECT id FROM trip_items WHERE trip_id = %s AND master_item_id = %s', (trip_id, item_id)
            )
            if not cur.fetchone():
                cur.execute('INSERT INTO trip_items (trip_id, master_item_id) VALUES (%s, %s)', (trip_id, item_id))
        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for('trip_detail', trip_id=trip_id))
    cur.execute('SELECT * FROM trips WHERE id = %s', (trip_id,))
    trip = cur.fetchone()
    cur.execute('SELECT master_item_id FROM trip_items WHERE trip_id = %s', (trip_id,))
    existing = [r['master_item_id'] for r in cur.fetchall()]
    cur.execute('SELECT * FROM master_items ORDER BY category, name')
    all_items = cur.fetchall()
    available = [item for item in all_items if item['id'] not in existing]
    cur.close()
    conn.close()
    return render_template('add_trip_items.html', trip=trip, items=available)

@app.route('/trip/<int:trip_id>/delete', methods=['POST'])
def delete_trip(trip_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute('DELETE FROM trips WHERE id = %s', (trip_id,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=False)
