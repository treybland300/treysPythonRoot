import os
from flask import Flask, render_template, request, redirect, url_for
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

@app.route('/')
def index():
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute('SELECT * FROM trips ORDER BY created_at DESC')
    trips = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('index.html', trips=trips)

@app.route('/master')
def master():
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute('SELECT * FROM master_items ORDER BY category, name')
    items = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('master.html', items=items)

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
    return redirect(url_for('master'))

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
    cur.close()
    conn.close()
    total = len(items)
    packed = sum(1 for i in items if i['packed_by'])
    progress = int((packed / total) * 100) if total > 0 else 0
    return render_template('trip.html', trip=trip, items=items, total=total, packed=packed, progress=progress)

@app.route('/trip/<int:trip_id>/pack/<int:item_id>', methods=['POST'])
def pack_item(trip_id, item_id):
    packer = request.form.get('packer', 'Trey')
    conn = get_db()
    cur = conn.cursor()
    cur.execute('UPDATE trip_items SET packed_by = %s, packed_at = NOW() WHERE id = %s', (packer, item_id))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('trip_detail', trip_id=trip_id))

@app.route('/trip/<int:trip_id>/unpack/<int:item_id>', methods=['POST'])
def unpack_item(trip_id, item_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute('UPDATE trip_items SET packed_by = NULL, packed_at = NULL WHERE id = %s', (item_id,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('trip_detail', trip_id=trip_id))

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
    init_db()
    app.run(debug=False)
