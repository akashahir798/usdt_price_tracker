import os
import time
import sqlite3
import requests
import pymysql
from datetime import datetime, date
from flask import (
    Flask, request, jsonify, session,
    render_template, redirect, url_for, flash, g
)
from werkzeug.security import generate_password_hash, check_password_hash
from config import Config

app = Flask(__name__)
app.config.from_object(Config)

USE_SQLITE = app.config.get('DB_TYPE', 'sqlite') == 'sqlite'

# Initialize MySQL tables on startup (for production platforms like Render)
if not USE_SQLITE:
    init_mysql_db()


# ============================================================
# SQLite compatibility layer (so the same %s-style queries work)
# ============================================================

class _SQLiteWrapper:
    """Thin wrapper so the rest of the code treats sqlite3 like pymysql."""

    def __init__(self, conn):
        self._conn = conn

    def cursor(self):
        cur = self._conn.cursor()
        return _CompatCursor(cur)

    def close(self):
        self._conn.close()


class _CompatCursor:
    """Converts %s → ? for SQLite, returns dicts."""

    def __init__(self, cursor):
        self._cursor = cursor

    def execute(self, query, args=()):
        if args:
            query = query.replace('%s', '?')
        self._cursor.execute(query, args)
        return self

    def fetchall(self):
        rows = self._cursor.fetchall()
        return [dict(r) if isinstance(r, sqlite3.Row) else r for r in rows]

    def fetchone(self):
        r = self._cursor.fetchone()
        return dict(r) if isinstance(r, sqlite3.Row) else r

    @property
    def lastrowid(self):
        return self._cursor.lastrowid

    def close(self):
        self._cursor.close()


def _sqlite_unix_timestamp(dt_str):
    """SQLite equivalent of MySQL's UNIX_TIMESTAMP()."""
    if dt_str and dt_str != 'now':
        try:
            return int(datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S').timestamp())
        except (ValueError, TypeError):
            pass
    return int(datetime.now().timestamp())


def init_sqlite_db(path):
    """Create SQLite tables with MySQL-compatible schema."""
    conn = sqlite3.connect(path)
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            transaction_type TEXT NOT NULL,
            amount REAL NOT NULL,
            buy_price REAL NOT NULL,
            transaction_date TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS price_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            price REAL NOT NULL,
            timestamp TEXT DEFAULT (datetime('now'))
        );
    ''')
    conn.commit()

    # Create default admin user if no users exist
    cur = conn.execute("SELECT COUNT(*) FROM users")
    if cur.fetchone()[0] == 0:
        conn.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
            ('admin', 'admin@example.com', generate_password_hash('pass123')),
        )
        conn.commit()
    conn.close()


def init_mysql_db():
    """Create MySQL tables and default admin user if they don't exist."""
    import pymysql
    try:
        conn = pymysql.connect(
            host=app.config['MYSQL_HOST'],
            user=app.config['MYSQL_USER'],
            password=app.config['MYSQL_PASSWORD'],
            database=app.config['MYSQL_DB'],
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=True,
        )
        cur = conn.cursor()

        # Create tables (IF NOT EXISTS is safe to run multiple times)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS `users` (
                id INT NOT NULL AUTO_INCREMENT,
                username VARCHAR(50) NOT NULL,
                email VARCHAR(255) NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (id),
                UNIQUE KEY username (username),
                UNIQUE KEY email (email)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS `transactions` (
                id INT NOT NULL AUTO_INCREMENT,
                user_id INT NOT NULL,
                transaction_type ENUM('BUY','SELL') NOT NULL,
                amount DECIMAL(20,8) NOT NULL,
                buy_price DECIMAL(20,8) NOT NULL,
                transaction_date DATE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (id),
                KEY idx_transactions_user_id (user_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS `price_history` (
                id INT NOT NULL AUTO_INCREMENT,
                price DECIMAL(20,8) NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (id),
                KEY idx_price_history_timestamp (timestamp)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)

        # Create default admin user if no users exist
        cur.execute("SELECT COUNT(*) as cnt FROM users")
        if cur.fetchone()['cnt'] == 0:
            cur.execute(
                "INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s)",
                ('admin', 'admin@tracker.com', generate_password_hash('pass123')),
            )

        conn.close()
    except Exception as e:
        app.logger.error(f'MySQL init error: {e}')


# ============================================================
# Database helpers
# ============================================================

def get_db():
    if 'db' not in g:
        if USE_SQLITE:
            db_path = app.config.get('SQLITE_PATH', 'usdt_tracker.db')
            if not os.path.isabs(db_path):
                db_path = os.path.join(app.instance_path or app.root_path, db_path)
            os.makedirs(os.path.dirname(db_path) or '.', exist_ok=True)
            init_sqlite_db(db_path)
            conn = sqlite3.connect(db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.isolation_level = None  # autocommit mode (matches pymysql autocommit=True)
            conn.create_function('UNIX_TIMESTAMP', 1, _sqlite_unix_timestamp)
            g.db = _SQLiteWrapper(conn)
        else:
            g.db = pymysql.connect(
                host=app.config['MYSQL_HOST'],
                user=app.config['MYSQL_USER'],
                password=app.config['MYSQL_PASSWORD'],
                database=app.config['MYSQL_DB'],
                charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor,
                autocommit=True,
            )
    return g.db


class _SQLiteWrapper:
    """Thin wrapper so the rest of the code treats sqlite3 like pymysql."""

    def __init__(self, conn):
        self._conn = conn

    def cursor(self):
        cur = self._conn.cursor()
        return _CompatCursor(cur)

    def close(self):
        self._conn.close()


class _CompatCursor:
    """Converts %s → ? for SQLite, returns dicts."""

    def __init__(self, cursor):
        self._cursor = cursor

    def execute(self, query, args=()):
        if args:
            query = query.replace('%s', '?')
        self._cursor.execute(query, args)
        return self

    def fetchall(self):
        rows = self._cursor.fetchall()
        return [dict(r) if isinstance(r, sqlite3.Row) else r for r in rows]

    def fetchone(self):
        r = self._cursor.fetchone()
        return dict(r) if isinstance(r, sqlite3.Row) else r

    @property
    def lastrowid(self):
        return self._cursor.lastrowid

    def close(self):
        self._cursor.close()


@app.teardown_appcontext
def close_db(exc):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def query_db(query, args=(), one=False):
    cur = get_db().cursor()
    cur.execute(query, args)
    result = cur.fetchall()
    cur.close()
    return (result[0] if result else None) if one else result


def execute_db(query, args=()):
    cur = get_db().cursor()
    cur.execute(query, args)
    last_id = cur.lastrowid
    cur.close()
    return last_id


# ============================================================
# API helpers
# ============================================================

COIN_ID = 'tether'
COINGECKO_PRICE_URL = f"{Config.COIN_API_URL}/simple/price"
COINGECKO_CHART_URL = f"{Config.COIN_API_URL}/coins/{COIN_ID}/market_chart"

# Supported currencies with symbols and locale tags
CURRENCY_MAP = {
    'usd':  {'symbol': '$',     'name': 'US Dollar'},
    'eur':  {'symbol': 'EUR',   'name': 'Euro'},
    'gbp':  {'symbol': 'GBP',    'name': 'British Pound'},
    'jpy':  {'symbol': 'JPY',    'name': 'Japanese Yen'},
    'inr':  {'symbol': '₹',     'name': 'Indian Rupee'},
    'cad':  {'symbol': 'C$',     'name': 'Canadian Dollar'},
    'aud':  {'symbol': 'A$',     'name': 'Australian Dollar'},
    'chf':  {'symbol': 'CHF',    'name': 'Swiss Franc'},
    'cny':  {'symbol': '¥',     'name': 'Chinese Yuan'},
    'krw':  {'symbol': '₩',     'name': 'South Korean Won'},
    'sgd':  {'symbol': 'S$',     'name': 'Singapore Dollar'},
    'hkd':  {'symbol': 'HK$',    'name': 'Hong Kong Dollar'},
}

def get_currency_symbol(currency):
    info = CURRENCY_MAP.get(currency, CURRENCY_MAP['usd'])
    return info['symbol']


_price_cache = {}
_price_cache_ts = 0


def fetch_live_price(currency='usd'):
    """Fetch real-time USDT price in a given currency via CoinGecko."""
    return _fetch_live_prices([currency]).get(currency)


def _fetch_live_prices(currencies):
    """Fetch real-time USDT prices for multiple currencies in a single API call.
    Results are cached for 30 seconds to avoid CoinGecko rate limits."""
    global _price_cache, _price_cache_ts
    now = time.time()

    # Check cache: use cached values for currencies already fetched,
    # only request the missing ones from the API
    missing = [c for c in currencies if c not in _price_cache]
    if not missing and now - _price_cache_ts < 30:
        return {c: _price_cache.get(c) for c in currencies}

    try:
        resp = requests.get(
            COINGECKO_PRICE_URL,
            params={'ids': COIN_ID, 'vs_currencies': ','.join(missing)},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        for c in missing:
            _price_cache[c] = round(float(data[COIN_ID][c]), 8)
        _price_cache_ts = now
        return {c: _price_cache.get(c) for c in currencies}
    except Exception:
        return {c: _price_cache.get(c) for c in currencies}


def get_price_in_currency(currency='usd'):
    """Fetch current USDT price in the target currency, with fallback."""
    return fetch_live_price(currency) or 1.0


def fetch_price_history(days=7, currency='usd'):
    """Fetch USDT price history (prices over the last *days* days)."""
    try:
        resp = requests.get(
            COINGECKO_CHART_URL,
            params={'vs_currency': currency, 'days': days, 'interval': 'hour'},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        prices = data.get('prices', [])
        return [
            {'timestamp': int(ts), 'price': round(float(p), 8)}
            for ts, p in prices
        ]
    except Exception:
        return []


def store_price_history(price):
    """Persist a price snapshot to the local price_history table."""
    execute_db(
        "INSERT INTO price_history (price) VALUES (%s)",
        (price,),
    )


def get_local_price_history(limit=200):
    rows = query_db(
        "SELECT price, UNIX_TIMESTAMP(timestamp) as ts FROM price_history "
        "ORDER BY timestamp DESC LIMIT %s",
        (limit,),
    )
    return [{'timestamp': r['ts'], 'price': float(r['price'])} for r in reversed(rows)] if rows else []


# ============================================================
# Auth middleware
# ============================================================

@app.before_request
def require_login():
    protected = {
        'dashboard', 'profile', 'transactions', 'portfolio', 'pl_calculator',
        'api_price', 'api_price_history', 'api_local_prices',
        'api_transactions', 'api_portfolio', 'api_performance',
        'api_currencies', 'api_set_currency', 'calculate_pl',
    }
    if request.endpoint in protected and 'user_id' not in session:
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Authentication required'}), 401
        return redirect(url_for('login'))


# ============================================================
# Routes — Public pages
# ============================================================

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')

        if not username or not email or not password:
            flash('All fields are required.', 'error')
            return render_template('register.html')
        if password != confirm:
            flash('Passwords do not match.', 'error')
            return render_template('register.html')

        existing = query_db(
            "SELECT id FROM users WHERE username=%s OR email=%s",
            (username, email),
            one=True,
        )
        if existing:
            flash('Username or email already exists.', 'error')
            return render_template('register.html')

        execute_db(
            "INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s)",
            (username, email, generate_password_hash(password)),
        )
        flash('Registration successful. Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        user = query_db(
            "SELECT * FROM users WHERE username=%s",
            (username,),
            one=True,
        )
        if user and check_password_hash(user['password_hash'], password):
            session.clear()
            session['user_id'] = user['id']
            session['username'] = user['username']
            session.permanent = True
            return redirect(url_for('dashboard'))
        flash('Invalid username or password.', 'error')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# ============================================================
# Routes — Authenticated pages
# ============================================================

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')


@app.route('/profile')
def profile():
    user = query_db(
        "SELECT id, username, email, created_at FROM users WHERE id=%s",
        (session['user_id'],),
        one=True,
    )
    return render_template('profile.html', user=user)


@app.route('/portfolio')
def portfolio():
    return render_template('portfolio.html')


@app.route('/pl-calculator')
def pl_calculator():
    return render_template('pl_calculator.html')


@app.route('/api/calculate-pl', methods=['POST'])
def calculate_pl():
    """Calculate profit/loss from buy price, sell price, and quantity."""
    data = request.get_json()
    buy_price = float(data.get('buy_price', 0))
    sell_price = float(data.get('sell_price', 0))
    quantity = float(data.get('quantity', 0))

    buy_cost = buy_price * quantity
    sell_revenue = sell_price * quantity
    pnl = sell_revenue - buy_cost
    pnl_percent = (pnl / buy_cost * 100) if buy_cost != 0 else 0

    response = {
        'buy_cost': round(buy_cost, 8),
        'sell_revenue': round(sell_revenue, 8),
        'pnl': round(pnl, 8),
        'pnl_percent': round(pnl_percent, 4),
        'break_even_price': buy_price,
    }

    target_price = data.get('target_price')
    if target_price:
        target_price = float(target_price)
        projected_pnl = (target_price - buy_price) * quantity
        projected_percent = ((target_price - buy_price) / buy_price * 100) if buy_price != 0 else 0
        response['target_price'] = target_price
        response['projected_pnl'] = round(projected_pnl, 8)
        response['projected_pnl_percent'] = round(projected_percent, 4)

    return jsonify(response)


# ============================================================
# Routes — Transaction CRUD
# ============================================================

@app.route('/transactions')
def transactions():
    return render_template('transactions.html')


@app.route('/api/transactions', methods=['GET', 'POST'])
def api_transactions():
    uid = session['user_id']

    if request.method == 'POST':
        data = request.get_json()
        t_type = data.get('transaction_type')
        amount = data.get('amount')
        buy_price = data.get('buy_price')
        t_date = data.get('transaction_date') or datetime.now().strftime('%Y-%m-%d')

        if t_type not in ('BUY', 'SELL'):
            return jsonify({'error': 'transaction_type must be BUY or SELL'}), 400
        try:
            amount = float(amount)
            buy_price = float(buy_price)
        except (TypeError, ValueError):
            return jsonify({'error': 'Invalid amount or price'}), 400

        tid = execute_db(
            "INSERT INTO transactions (user_id, transaction_type, amount, buy_price, transaction_date) "
            "VALUES (%s, %s, %s, %s, %s)",
            (uid, t_type, amount, buy_price, t_date),
        )
        return jsonify({'id': tid, 'message': 'Transaction recorded'}), 201

    rows = query_db(
        "SELECT id, transaction_type, amount, buy_price, transaction_date "
        "FROM transactions WHERE user_id=%s ORDER BY transaction_date DESC, id DESC",
        (uid,),
    )
    return jsonify([_serialize_transaction(r) for r in rows])


@app.route('/api/transactions/<int:tid>', methods=['PUT', 'DELETE'])
def api_transaction_detail(tid):
    uid = session['user_id']
    row = query_db(
        "SELECT id FROM transactions WHERE id=%s AND user_id=%s",
        (tid, uid),
        one=True,
    )
    if not row:
        return jsonify({'error': 'Transaction not found'}), 404

    if request.method == 'DELETE':
        execute_db("DELETE FROM transactions WHERE id=%s", (tid,))
        return jsonify({'message': 'Transaction deleted'}), 200

    data = request.get_json()
    t_type = data.get('transaction_type')
    amount = data.get('amount')
    buy_price = data.get('buy_price')
    t_date = data.get('transaction_date')

    if t_type not in ('BUY', 'SELL'):
        return jsonify({'error': 'transaction_type must be BUY or SELL'}), 400
    try:
        amount = float(amount)
        buy_price = float(buy_price)
    except (TypeError, ValueError):
        return jsonify({'error': 'Invalid amount or price'}), 400

    execute_db(
        "UPDATE transactions SET transaction_type=%s, amount=%s, buy_price=%s, transaction_date=%s "
        "WHERE id=%s AND user_id=%s",
        (t_type, amount, buy_price, t_date, tid, uid),
    )
    return jsonify({'message': 'Transaction updated'}), 200


def _serialize_transaction(r):
    txn_date = r['transaction_date']
    if isinstance(txn_date, date):
        date_str = txn_date.strftime('%Y-%m-%d')
    elif isinstance(txn_date, str):
        date_str = txn_date
    else:
        date_str = str(txn_date)
    return {
        'id': r['id'],
        'transaction_type': r['transaction_type'],
        'amount': float(r['amount']),
        'buy_price': float(r['buy_price']),
        'transaction_date': date_str,
    }


# ============================================================
# Routes — Live price & API endpoints
# ============================================================

@app.route('/api/price')
def api_price():
    currency = request.args.get('currency', 'usd')
    price = fetch_live_price(currency)
    if price is not None:
        store_price_history(price)
    return jsonify({'usdt_price': price, 'currency': currency, 'symbol': get_currency_symbol(currency)})


@app.route('/api/price-history')
def api_price_history():
    days = request.args.get('days', 7, type=int)
    currency = request.args.get('currency', 'usd')
    history = fetch_price_history(days=days, currency=currency)
    if history:
        return jsonify(history)
    local = get_local_price_history(limit=200)
    return jsonify(local)


@app.route('/api/local-prices')
def api_local_prices():
    local = get_local_price_history(limit=200)
    return jsonify(local)


@app.route('/api/currencies')
def api_currencies():
    """List all supported currencies with symbols."""
    return jsonify(CURRENCY_MAP)


@app.route('/api/set-currency', methods=['GET', 'POST'])
def api_set_currency():
    """Get or set the user's preferred currency in their session."""
    if request.method == 'GET':
        currency = session.get('currency', 'usd')
        return jsonify({'currency': currency, 'symbol': get_currency_symbol(currency)})
    data = request.get_json() or {}
    currency = data.get('currency', 'usd').lower()
    if currency not in CURRENCY_MAP:
        currency = 'usd'
    session['currency'] = currency
    return jsonify({'currency': currency, 'symbol': get_currency_symbol(currency)})


@app.route('/api/portfolio')
def api_portfolio():
    """Compute portfolio summary: total investment, current value, P/L."""
    uid = session['user_id']
    currency = session.get('currency', 'usd')

    agg = query_db(
        "SELECT transaction_type, SUM(amount) as total_amount, SUM(amount * buy_price) as total_value "
        "FROM transactions WHERE user_id=%s GROUP BY transaction_type",
        (uid,),
    )

    agg_map = {row['transaction_type']: row for row in agg} if agg else {}

    buy_amount = sum(float(r['total_amount']) for r in agg_map.values() if r['transaction_type'] == 'BUY') if 'BUY' in agg_map else 0.0
    sell_amount = sum(float(r['total_amount']) for r in agg_map.values() if r['transaction_type'] == 'SELL') if 'SELL' in agg_map else 0.0
    buy_value = sum(float(r['total_value']) for r in agg_map.values() if r['transaction_type'] == 'BUY') if 'BUY' in agg_map else 0.0
    sell_value = sum(float(r['total_value']) for r in agg_map.values() if r['transaction_type'] == 'SELL') if 'SELL' in agg_map else 0.0

    net_holding = buy_amount - sell_amount
    net_investment_usd = buy_value - sell_value

    # Fetch both prices in one API call (cached for 30s to avoid rate limits)
    prices = _fetch_live_prices([currency, 'usd'])
    current_price = prices.get(currency) or 1.0
    current_price_usd = prices.get('usd') or 1.0

    # Convert net_investment from USD to the selected currency
    # Since stored buy_price values are in USD, we convert using the exchange rate
    exchange_rate = current_price / current_price_usd if current_price_usd else 1.0
    net_investment = net_investment_usd * exchange_rate

    current_value = net_holding * current_price
    pnl = current_value - net_investment
    pnl_percent = (pnl / net_investment * 100) if net_investment != 0 else 0

    return jsonify({
        'total_buy_amount': round(buy_amount, 8),
        'total_sell_amount': round(sell_amount, 8),
        'net_holding': round(net_holding, 8),
        'total_investment': round(net_investment, 8),
        'current_value': round(current_value, 8),
        'pnl': round(pnl, 8),
        'pnl_percent': round(pnl_percent, 2),
        'current_price': current_price,
        'currency': currency,
        'symbol': get_currency_symbol(currency),
    })


@app.route('/api/performance')
def api_performance():
    """Return data for the performance chart — portfolio value over time."""
    uid = session['user_id']
    currency = session.get('currency', 'usd')

    # Fetch both prices in one API call (cached for 30s to avoid rate limits)
    prices = _fetch_live_prices([currency, 'usd'])
    current_price = prices.get(currency) or 1.0
    current_price_usd = prices.get('usd') or 1.0
    exchange_rate = current_price / current_price_usd if current_price_usd else 1.0

    txns = query_db(
        "SELECT transaction_type, amount, buy_price, transaction_date "
        "FROM transactions WHERE user_id=%s ORDER BY transaction_date ASC",
        (uid,),
    )

    timeline = []
    cumulative_cost = 0.0
    cumulative_holding = 0.0

    if txns:
        for t in txns:
            sign = 1 if t['transaction_type'] == 'BUY' else -1
            amt = float(t['amount'])
            cost = float(t['buy_price'])
            cumulative_holding += sign * amt
            cumulative_cost += sign * amt * cost * exchange_rate
            txn_date = t['transaction_date']
            if isinstance(txn_date, date):
                date_str = txn_date.strftime('%Y-%m-%d')
                day_ts = int(datetime.combine(txn_date, datetime.min.time()).timestamp())
            elif isinstance(txn_date, str):
                date_str = txn_date
                day_ts = int(datetime.strptime(txn_date, '%Y-%m-%d').timestamp())
            else:
                date_str = str(txn_date)
                day_ts = int(datetime.now().timestamp())
            value = cumulative_holding * current_price
            timeline.append({
                'date': date_str,
                'timestamp': day_ts,
                'holding': round(cumulative_holding, 8),
                'cost_basis': round(cumulative_cost, 8),
                'value': round(value, 8),
            })

    return jsonify({
        'current_price': current_price,
        'currency': currency,
        'symbol': get_currency_symbol(currency),
        'timeline': timeline,
    })


# ============================================================
# Error handlers
# ============================================================

@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404


@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500


if __name__ == '__main__':
    app.run(
        debug=app.config.get('DEBUG', False),
        host=app.config.get('HOST', '0.0.0.0'),
        port=int(app.config.get('PORT', 5000))
    )
