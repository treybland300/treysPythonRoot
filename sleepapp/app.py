from flask import Flask, Blueprint, render_template, request, redirect, url_for, jsonify
import sqlite3
import os
from datetime import date, datetime, timedelta

sleep_bp = Blueprint('sleep', __name__, template_folder='templates')
DB = os.path.join(os.path.dirname(__file__), 'sleep.db')

ALLOWED_FIELDS = {
    'wake_time', 'out_of_crib_time', 'morning_feed_done',
    'morning_bottle_time', 'morning_bottle_oz',
    'breakfast_items', 'breakfast_time',
    'topoff_time', 'topoff_oz',
    'lunch_items', 'lunch_time',
    'snack_items', 'snack_time',
    'dinner_items', 'dinner_time',
    'nap1_routine_done', 'nap1_sleep_time', 'nap1_wake_time',
    'nap1_soothing_rounds', 'nap1_feed_after', 'nap1_solids',
    'nap2_routine_done', 'nap2_sleep_time', 'nap2_wake_time',
    'nap2_soothing_rounds', 'nap2_feed_after', 'nap2_solids',
    'catnap_routine_done', 'catnap_sleep_time', 'catnap_wake_time',
    'catnap_soothing_rounds', 'catnap_feed_after', 'catnap_solids',
    'bedtime_routine_done', 'bedtime_bottle_time', 'bedtime_bottle_oz',
    'night_sleep_time', 'night_wake_time',
    'waking1_time', 'waking1_rounds', 'waking1_fed', 'waking1_return',
    'waking2_time', 'waking2_rounds', 'waking2_fed', 'waking2_return',
    'waking3_time', 'waking3_rounds', 'waking3_fed', 'waking3_return',
    'waking4_time', 'waking4_rounds', 'waking4_fed', 'waking4_return',
    'waking5_time', 'waking5_rounds', 'waking5_fed', 'waking5_return',
}


def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS daily_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL UNIQUE,
            wake_time TEXT,
            out_of_crib_time TEXT,
            morning_feed_done INTEGER DEFAULT 0,
            morning_bottle_time TEXT,
            morning_bottle_oz REAL,
            breakfast_items TEXT,
            breakfast_time TEXT,
            topoff_time TEXT,
            topoff_oz REAL,
            lunch_items TEXT,
            lunch_time TEXT,
            snack_items TEXT,
            snack_time TEXT,
            dinner_items TEXT,
            dinner_time TEXT,
            nap1_routine_done INTEGER DEFAULT 0,
            nap1_sleep_time TEXT,
            nap1_wake_time TEXT,
            nap1_soothing_rounds INTEGER,
            nap1_feed_after INTEGER DEFAULT 0,
            nap1_solids TEXT,
            nap2_routine_done INTEGER DEFAULT 0,
            nap2_sleep_time TEXT,
            nap2_wake_time TEXT,
            nap2_soothing_rounds INTEGER,
            nap2_feed_after INTEGER DEFAULT 0,
            nap2_solids TEXT,
            catnap_routine_done INTEGER DEFAULT 0,
            catnap_sleep_time TEXT,
            catnap_wake_time TEXT,
            catnap_soothing_rounds INTEGER,
            catnap_feed_after INTEGER DEFAULT 0,
            catnap_solids TEXT,
            bedtime_routine_done INTEGER DEFAULT 0,
            bedtime_bottle_time TEXT,
            bedtime_bottle_oz REAL,
            night_sleep_time TEXT,
            night_wake_time TEXT,
            waking1_time TEXT, waking1_rounds INTEGER, waking1_fed INTEGER DEFAULT 0, waking1_return TEXT,
            waking2_time TEXT, waking2_rounds INTEGER, waking2_fed INTEGER DEFAULT 0, waking2_return TEXT,
            waking3_time TEXT, waking3_rounds INTEGER, waking3_fed INTEGER DEFAULT 0, waking3_return TEXT,
            waking4_time TEXT, waking4_rounds INTEGER, waking4_fed INTEGER DEFAULT 0, waking4_return TEXT,
            waking5_time TEXT, waking5_rounds INTEGER, waking5_fed INTEGER DEFAULT 0, waking5_return TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS field_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            field_name TEXT NOT NULL,
            old_value TEXT,
            new_value TEXT,
            changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    conn.commit()
    conn.close()


def add_minutes(time_str, total_minutes):
    try:
        t = datetime.strptime(time_str, '%H:%M')
        t += timedelta(minutes=total_minutes)
        return t.strftime('%H:%M')
    except Exception:
        return None


def fmt_12(time_str):
    if not time_str:
        return ''
    try:
        t = datetime.strptime(time_str, '%H:%M')
        h = t.hour % 12 or 12
        am_pm = 'AM' if t.hour < 12 else 'PM'
        return f"{h}:{t.strftime('%M')} {am_pm}"
    except Exception:
        return time_str


def nap_duration_min(sleep_time, wake_time):
    if not sleep_time or not wake_time:
        return None
    try:
        s = datetime.strptime(sleep_time, '%H:%M')
        w = datetime.strptime(wake_time, '%H:%M')
        delta = (w - s).seconds // 60
        return delta if delta > 0 else None
    except Exception:
        return None


def compute_hints(row):
    hints = {}

    # --- Morning / Nap 1 target ---
    if row['wake_time']:
        wt = row['wake_time']
        nap1_target = add_minutes(wt, 120)
        if nap1_target:
            hints['nap1_target'] = (
                f"Target ~{fmt_12(nap1_target)} "
                f"(2-hr wake window from wake-up at {fmt_12(wt)})"
            )
        if wt < '06:30':
            hints['wake_note'] = "Before 6:30 AM — treat this as a nighttime waking. Use soothing rounds."
        elif wt < '07:00':
            hints['wake_note'] = "6:30–7:00 AM: if upset you can start the day; if calm, let her rest until 7:00."
        else:
            hints['wake_note'] = "Wake Stella at 7:00 AM daily — even after a rough night. Feed immediately in a bright, sunlit room."

    # --- After Nap 1 / Nap 2 target ---
    if row['nap1_wake_time']:
        nw = row['nap1_wake_time']
        nap2_target = add_minutes(nw, 150)
        if nap2_target:
            hints['nap2_target'] = (
                f"Target ~{fmt_12(nap2_target)} "
                f"(2.5-hr wake window from Nap 1 end at {fmt_12(nw)})"
            )
        hints['post_nap1_note'] = f"Give a full bottle immediately after Nap 1. Lunch around 12:00 PM."

    # --- After Nap 2 / Catnap target ---
    if row['nap2_wake_time']:
        nw = row['nap2_wake_time']
        catnap_target = add_minutes(nw, 120)
        if catnap_target:
            hints['catnap_target'] = (
                f"Target ~{fmt_12(catnap_target)} "
                f"(2-hr wake window from Nap 2 end at {fmt_12(nw)}). Max 45 min — do NOT extend."
            )

    # --- After Catnap / Bedtime target ---
    if row['catnap_wake_time']:
        cw = row['catnap_wake_time']
        routine_start = add_minutes(cw, 105)
        crib_target = add_minutes(cw, 120)
        if crib_target:
            hints['bedtime_target'] = (
                f"Start bedtime routine ~{fmt_12(routine_start)}. "
                f"In crib by ~{fmt_12(crib_target)} (earliest 6:00 PM if overtired)."
            )
    elif not row['catnap_wake_time'] and not row['catnap_sleep_time']:
        hints['catnap_skipped'] = "If catnap is skipped, move bedtime earlier (as early as 6:00 PM) to compensate."

    # --- Nap 1 duration / extension hint ---
    dur1 = nap_duration_min(row['nap1_sleep_time'], row['nap1_wake_time'])
    if dur1 is not None:
        if dur1 <= 45:
            hints['nap1_short'] = (
                f"Short nap ({dur1} min). Attempt 20–30 min of soothing rounds to extend. "
                f"If successful, wake at the 30-min mark after she fell back asleep."
            )
        else:
            hints['nap1_duration'] = f"Nap 1 length: {dur1} min"

    # --- Nap 2 duration / extension hint ---
    dur2 = nap_duration_min(row['nap2_sleep_time'], row['nap2_wake_time'])
    if dur2 is not None:
        if dur2 <= 45:
            hints['nap2_short'] = (
                f"Short nap ({dur2} min). Continue soothing rounds until 90 min total crib time. "
                f"If she can't be extended, get her up and start a new wake window."
            )
        else:
            hints['nap2_duration'] = f"Nap 2 length: {dur2} min"

    # --- Catnap duration hint ---
    durc = nap_duration_min(row['catnap_sleep_time'], row['catnap_wake_time'])
    if durc is not None:
        if durc > 45:
            hints['catnap_long'] = f"Catnap ran {durc} min — aim for 45 min max next time."
        else:
            hints['catnap_duration'] = f"Catnap: {durc} min"

    # --- Total daytime sleep vs goal ---
    total_nap_min = sum(d for d in [dur1, dur2, durc] if d is not None)
    if total_nap_min > 0:
        total_h = total_nap_min // 60
        total_m = total_nap_min % 60
        goal_low, goal_high = 180, 210
        if total_nap_min < goal_low:
            deficit = goal_low - total_nap_min
            hints['sleep_total'] = (
                f"Daytime sleep: {total_h}h {total_m}m — "
                f"{deficit} min below the 3-hr minimum. Consider early bedtime."
            )
        elif total_nap_min > goal_high:
            hints['sleep_total'] = (
                f"Daytime sleep: {total_h}h {total_m}m — above 3.5-hr goal. "
                f"Watch bedtime — may be harder to fall asleep."
            )
        else:
            hints['sleep_total'] = f"Daytime sleep: {total_h}h {total_m}m — on target (goal: 3–3.5 hrs)"

    # --- Bottle total vs 24 oz minimum ---
    total_oz = 0.0
    for field in ('morning_bottle_oz', 'topoff_oz', 'bedtime_bottle_oz'):
        try:
            v = row[field]
            if v:
                total_oz += float(v)
        except Exception:
            pass
    if total_oz > 0:
        remaining = max(0, 24.0 - total_oz)
        if remaining > 0:
            hints['bottle_total'] = f"Bottles: {total_oz:.0f} oz logged — {remaining:.0f} oz remaining to hit 24 oz minimum"
        else:
            hints['bottle_total'] = f"Bottles: {total_oz:.0f} oz — 24 oz minimum met"

    return hints


def ensure_day(log_date, conn):
    conn.execute('INSERT OR IGNORE INTO daily_logs (date) VALUES (?)', (log_date,))
    conn.commit()


@sleep_bp.route('/')
def index():
    today = date.today().isoformat()
    return redirect(url_for('.day', log_date=today))


@sleep_bp.route('/<log_date>')
def day(log_date):
    conn = get_db()
    ensure_day(log_date, conn)
    row = conn.execute('SELECT * FROM daily_logs WHERE date=?', (log_date,)).fetchone()
    recent_history = conn.execute(
        'SELECT * FROM field_history WHERE date=? ORDER BY changed_at DESC LIMIT 25',
        (log_date,)
    ).fetchall()
    logged_dates = conn.execute(
        'SELECT date FROM daily_logs ORDER BY date DESC LIMIT 30'
    ).fetchall()
    conn.close()

    hints = compute_hints(row)

    prev_date = (datetime.strptime(log_date, '%Y-%m-%d') - timedelta(days=1)).strftime('%Y-%m-%d')
    next_date = (datetime.strptime(log_date, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')
    today = date.today().isoformat()

    return render_template(
        'sleep/index.html',
        row=dict(row),
        hints=hints,
        log_date=log_date,
        prev_date=prev_date,
        next_date=next_date,
        today=today,
        recent_history=recent_history,
        logged_dates=[d['date'] for d in logged_dates],
    )


@sleep_bp.route('/<log_date>/save', methods=['POST'])
def save_field(log_date):
    data = request.get_json()
    field = data.get('field', '')
    value = data.get('value', '')

    if field not in ALLOWED_FIELDS:
        return jsonify({'success': False, 'error': 'Invalid field'}), 400

    conn = get_db()
    ensure_day(log_date, conn)
    row = conn.execute('SELECT * FROM daily_logs WHERE date=?', (log_date,)).fetchone()
    old_value = str(row[field]) if row[field] is not None else ''

    if old_value != str(value):
        conn.execute(
            'INSERT INTO field_history (date, field_name, old_value, new_value) VALUES (?, ?, ?, ?)',
            (log_date, field, old_value, str(value))
        )

    store_value = value if value != '' else None
    conn.execute(
        f'UPDATE daily_logs SET {field}=?, updated_at=CURRENT_TIMESTAMP WHERE date=?',
        (store_value, log_date)
    )
    conn.commit()

    row = conn.execute('SELECT * FROM daily_logs WHERE date=?', (log_date,)).fetchone()
    conn.close()

    return jsonify({'success': True, 'hints': compute_hints(row)})


@sleep_bp.route('/history')
def history():
    conn = get_db()
    days = conn.execute(
        '''SELECT d.date, COUNT(h.id) as changes
           FROM daily_logs d
           LEFT JOIN field_history h ON d.date = h.date
           GROUP BY d.date ORDER BY d.date DESC'''
    ).fetchall()
    conn.close()
    return render_template('sleep/history.html', days=days)


@sleep_bp.route('/history/<log_date>')
def day_history(log_date):
    conn = get_db()
    changes = conn.execute(
        'SELECT * FROM field_history WHERE date=? ORDER BY changed_at DESC',
        (log_date,)
    ).fetchall()
    conn.close()
    return render_template('sleep/day_history.html', changes=changes, log_date=log_date)


init_db()

app = Flask(__name__)
app.register_blueprint(sleep_bp)

if __name__ == '__main__':
    app.run(debug=True)
