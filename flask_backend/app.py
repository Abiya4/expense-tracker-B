from flask import Flask, request, jsonify
from flask_cors import CORS
import mysql.connector
from datetime import datetime, timedelta, date as date_type
from decimal import Decimal
import re
import os
import traceback

app = Flask(__name__)
CORS(app)

# ---------------- DATABASE CONNECTION ----------------
mysql_conn = mysql.connector.connect(
    host="localhost",
    user="root",
    password="u2303044",
    database="mini_project_db"
)

# ---------------- RECONNECT HELPER ----------------
def get_cursor(dictionary=False):
    global mysql_conn
    try:
        mysql_conn.ping(reconnect=True, attempts=3, delay=2)
    except Exception:
        mysql_conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="u2303044",
            database="mini_project_db"
        )
    return mysql_conn.cursor(buffered=True, dictionary=dictionary)

# ---------------- MIGRATION ----------------
def run_migrations():
    print("Checking for database migrations...")
    cur = get_cursor()
    try:
        # ── expenses.status ──────────────────────────────────────
        cur.execute("SHOW COLUMNS FROM expenses LIKE 'status'")
        if not cur.fetchone():
            print("Adding 'status' column to expenses table...")
            cur.execute("ALTER TABLE expenses ADD COLUMN status VARCHAR(20) DEFAULT 'confirmed'")
            mysql_conn.commit()
            print("Migration successful: 'status' column added.")
        else:
            print("Migration check: 'status' column already exists.")

        # ── expenses.entry_method ────────────────────────────────
        cur.execute("SHOW COLUMNS FROM expenses LIKE 'entry_method'")
        if not cur.fetchone():
            print("Adding 'entry_method' column to expenses table...")
            cur.execute("ALTER TABLE expenses ADD COLUMN entry_method VARCHAR(20) DEFAULT 'manual'")
            mysql_conn.commit()
            print("Migration successful: 'entry_method' column added.")

        # ── budgets table ────────────────────────────────────────
        cur.execute("SHOW TABLES LIKE 'budgets'")
        if not cur.fetchone():
            print("Creating 'budgets' table...")
            cur.execute("""
                CREATE TABLE budgets (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    monthly_limit DECIMAL(10,2) NOT NULL,
                    month INT NOT NULL,
                    year  INT NOT NULL,
                    UNIQUE KEY unique_user_month_year (user_id, month, year),
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)
            mysql_conn.commit()
            print("Migration successful: 'budgets' table created.")
        else:
            # Table exists — make sure month & year columns are present
            cur.execute("SHOW COLUMNS FROM budgets LIKE 'month'")
            if not cur.fetchone():
                print("Adding 'month' column to budgets table...")
                cur.execute("ALTER TABLE budgets ADD COLUMN month INT NOT NULL DEFAULT 1")
                mysql_conn.commit()
                print("Migration successful: 'month' column added.")

            cur.execute("SHOW COLUMNS FROM budgets LIKE 'year'")
            if not cur.fetchone():
                print("Adding 'year' column to budgets table...")
                cur.execute("ALTER TABLE budgets ADD COLUMN year INT NOT NULL DEFAULT 2024")
                mysql_conn.commit()
                print("Migration successful: 'year' column added.")

            # Add unique constraint if missing (ignore error if already present)
            try:
                cur.execute("""
                    ALTER TABLE budgets
                    ADD UNIQUE KEY unique_user_month_year (user_id, month, year)
                """)
                mysql_conn.commit()
                print("Migration successful: unique constraint on budgets added.")
            except Exception:
                print("Migration check: unique constraint on budgets already exists.")

        # ── wishlist.previous_saved ──────────────────────────────
        cur.execute("SHOW COLUMNS FROM wishlist LIKE 'previous_saved'")
        if not cur.fetchone():
            print("Adding 'previous_saved' column to wishlist table...")
            cur.execute("ALTER TABLE wishlist ADD COLUMN previous_saved DECIMAL(10,2) DEFAULT 0.0")
            mysql_conn.commit()
            print("Migration successful: 'previous_saved' column added.")
        else:
            print("Migration check: 'previous_saved' column already exists.")

    except Exception as e:
        print(f"Migration error: {e}")
        traceback.print_exc()
    finally:
        cur.close()

run_migrations()

# ---------------- GLOBAL LOGIN STATE ----------------
logged_in_user = {
    "id": None,
    "role": None
}

def is_empty(value):
    return value is None or str(value).strip() == ""

# ---------------- AUTH MODULE ----------------

@app.route('/signup', methods=['POST'])
def signup():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    phone    = data.get('phone')
    balance  = data.get('balance')
    if is_empty(username) or is_empty(password) or is_empty(phone) or balance is None:
        return jsonify({"success": False, "message": "All fields required"}), 400
    cur = get_cursor()
    cur.execute("SELECT id FROM users WHERE username=%s", (username,))
    if cur.fetchone():
        cur.close()
        return jsonify({"success": False, "message": "Username exists"}), 409
    cur.execute(
        "INSERT INTO users(username, password, phone, balance, role) VALUES (%s, %s, %s, %s, 'user')",
        (username, password, phone, balance)
    )
    mysql_conn.commit()
    cur.close()
    return jsonify({"success": True}), 201

@app.route('/login', methods=['POST'])
def login():
    global logged_in_user
    data = request.json
    username = data.get('username')
    password = data.get('password')
    cur = get_cursor()
    cur.execute(
        "SELECT id, balance, role, is_active FROM users WHERE username=%s AND password=%s",
        (username, password)
    )
    user = cur.fetchone()
    cur.close()
    if not user:
        return jsonify({"success": False, "message": "Invalid credentials"}), 401
    if not user[3]:
        return jsonify({"success": False, "message": "Account deactivated"}), 403
    logged_in_user["id"]   = user[0]
    logged_in_user["role"] = user[2]
    return jsonify({
        "success": True,
        "id":      user[0],
        "role":    user[2],
        "balance": float(user[1]) if user[2] == 'user' else None
    })

@app.route('/logout', methods=['POST'])
def logout():
    logged_in_user["id"]   = None
    logged_in_user["role"] = None
    return jsonify({"success": True})

@app.route('/balance', methods=['GET'])
def get_balance():
    if logged_in_user["id"] is None or logged_in_user["role"] != 'user':
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    cur = get_cursor()
    cur.execute("SELECT balance FROM users WHERE id=%s", (logged_in_user["id"],))
    result = cur.fetchone()
    cur.close()
    if result:
        return jsonify({"balance": float(result[0])})
    return jsonify({"success": False, "message": "User not found"}), 404

# ================= USER MODULE =================

@app.route('/expenses', methods=['GET'])
def get_expenses():
    if logged_in_user["role"] != 'user':
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    status_filter = request.args.get('status')
    cur = get_cursor()
    if status_filter:
        query  = "SELECT id, amount, date, time, category, type, status, entry_method FROM expenses WHERE user_id=%s AND status=%s ORDER BY date DESC, time DESC"
        params = (logged_in_user["id"], status_filter)
    else:
        query  = "SELECT id, amount, date, time, category, type, status, entry_method FROM expenses WHERE user_id=%s ORDER BY date DESC, time DESC"
        params = (logged_in_user["id"],)
    cur.execute(query, params)
    rows = cur.fetchall()
    cur.close()
    return jsonify([{
        "id": r[0], "amount": float(r[1]), "date": str(r[2]),
        "time": str(r[3]), "category": r[4], "type": r[5],
        "status": r[6], "entry_method": r[7]
    } for r in rows])

@app.route('/expenses', methods=['POST'])
def add_expense():
    if logged_in_user["role"] != 'user':
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    data         = request.json
    amount       = data.get('amount')
    category     = data.get('category')
    t_type       = data.get('type', 'expense')
    status       = data.get('status', 'confirmed')
    entry_method = data.get('entry_method', 'manual')
    date_val     = data.get('date')
    time_val     = data.get('time')
    if amount is None or amount <= 0:
        return jsonify({"success": False, "message": "Invalid amount"}), 400
    now        = datetime.now()
    final_date = date_val if date_val else now.date()
    final_time = time_val if time_val else now.time()
    cur = get_cursor()
    cur.execute(
        "INSERT INTO expenses(amount, date, time, category, user_id, type, status, entry_method) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
        (amount, final_date, final_time, category, logged_in_user["id"], t_type, status, entry_method)
    )
    if status == 'confirmed':
        adj = amount if t_type == 'income' else -amount
        cur.execute("UPDATE users SET balance = balance + %s WHERE id=%s", (adj, logged_in_user["id"]))
    mysql_conn.commit()
    cur.close()
    return jsonify({"success": True}), 201

@app.route('/expenses/server_sync', methods=['POST'])
def sync_pending_expenses():
    if logged_in_user["role"] != 'user':
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    data          = request.json
    expenses_list = data.get('expenses', [])
    if not expenses_list:
        return jsonify({"success": True, "message": "No expenses to sync"}), 200
    cur   = get_cursor()
    count = 0
    for item in expenses_list:
        try:
            amount   = item.get('amount')
            date_str = item.get('date')
            time_str = item.get('time', '00:00:00')
            category = item.get('category', 'Uncategorized')
            t_type   = item.get('type', 'expense')
            cur.execute("""
                SELECT id FROM expenses
                WHERE user_id=%s AND amount=%s AND date=%s AND type=%s AND status='pending'
            """, (logged_in_user["id"], amount, date_str, t_type))
            if cur.fetchone():
                print(f"Skipping duplicate pending expense: {amount} on {date_str}")
                continue
            cur.execute(
                "INSERT INTO expenses(amount, date, time, category, user_id, type, status, entry_method) VALUES (%s, %s, %s, %s, %s, %s, 'pending', 'sms')",
                (amount, date_str, time_str, category, logged_in_user["id"], t_type)
            )
            count += 1
        except Exception as e:
            print(f"Error syncing item {item}: {e}")
    mysql_conn.commit()
    cur.close()
    return jsonify({"success": True, "synced_count": count}), 201

@app.route('/expenses/confirm_sms', methods=['POST'])
def confirm_sms_expense():
    if logged_in_user["role"] != 'user':
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    data       = request.json
    expense_id = data.get('expense_id')
    if not expense_id:
        return add_expense()
    cur = get_cursor()
    cur.execute(
        "SELECT amount, type, status FROM expenses WHERE id=%s AND user_id=%s",
        (expense_id, logged_in_user["id"])
    )
    row = cur.fetchone()
    if not row:
        cur.close()
        return jsonify({"success": False, "message": "Expense not found"}), 404
    amount, t_type, status = float(row[0]), row[1], row[2]
    if status == 'confirmed':
        cur.close()
        return jsonify({"success": False, "message": "Already confirmed"}), 400
    cur.execute(
        "UPDATE expenses SET status='confirmed' WHERE id=%s AND user_id=%s",
        (expense_id, logged_in_user["id"])
    )
    adj = amount if t_type == 'income' else -amount
    cur.execute(
        "UPDATE users SET balance = balance + %s WHERE id=%s",
        (adj, logged_in_user["id"])
    )
    mysql_conn.commit()
    cur.close()
    return jsonify({"success": True})

@app.route('/expenses/<int:expense_id>', methods=['DELETE'])
def delete_expense(expense_id):
    if logged_in_user["role"] != 'user':
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    cur = get_cursor()
    cur.execute(
        "SELECT amount, type, status FROM expenses WHERE id=%s AND user_id=%s",
        (expense_id, logged_in_user["id"])
    )
    row = cur.fetchone()
    if not row:
        cur.close()
        return jsonify({"success": False, "message": "Not found"}), 404
    amount, t_type, status = row[0], row[1], row[2]
    if status == 'confirmed':
        reversal = -amount if t_type == 'income' else amount
        cur.execute("UPDATE users SET balance = balance + %s WHERE id=%s",
                    (reversal, logged_in_user["id"]))
    cur.execute("DELETE FROM expenses WHERE id=%s", (expense_id,))
    mysql_conn.commit()
    cur.close()
    return jsonify({"success": True})

# ================= ADMIN MODULE =================

@app.route('/admin/users', methods=['GET'])
def admin_users():
    if logged_in_user["role"] != 'admin':
        return jsonify({"success": False, "message": "Admin only"}), 403
    q   = request.args.get('q', '').strip()
    cur = get_cursor()
    if q:
        cur.execute(
            "SELECT id, username, phone, balance, is_active FROM users WHERE role='user' AND (username LIKE %s OR phone LIKE %s)",
            (f"%{q}%", f"%{q}%")
        )
    else:
        cur.execute("SELECT id, username, phone, balance, is_active FROM users WHERE role='user'")
    rows = cur.fetchall()
    cur.close()
    return jsonify([{
        "id": r[0], "username": r[1], "phone": r[2],
        "balance": float(r[3]), "active": bool(r[4])
    } for r in rows])

@app.route('/admin/users/<int:user_id>', methods=['DELETE'])
def admin_delete_user(user_id):
    if logged_in_user["role"] != 'admin':
        return jsonify({"success": False, "message": "Admin only"}), 403
    cur = get_cursor()
    cur.execute("SELECT role FROM users WHERE id=%s", (user_id,))
    user = cur.fetchone()
    if not user:
        cur.close()
        return jsonify({"success": False, "message": "User not found"}), 404
    if user[0] == 'admin':
        cur.close()
        return jsonify({"success": False, "message": "Cannot delete admin"}), 403
    cur.execute("DELETE FROM users WHERE id=%s", (user_id,))
    mysql_conn.commit()
    cur.close()
    return jsonify({"success": True, "message": "User removed successfully"})

@app.route('/admin/expenses', methods=['GET'])
def admin_expenses():
    if logged_in_user["role"] != 'admin':
        return jsonify({"success": False, "message": "Admin only"}), 403
    cur = get_cursor()
    cur.execute("""
        SELECT u.username, e.amount, e.category, e.date, e.type
        FROM expenses e JOIN users u ON e.user_id = u.id
        ORDER BY e.date DESC, e.time DESC
    """)
    rows = cur.fetchall()
    cur.close()
    return jsonify([{
        "username": r[0], "amount": float(r[1]),
        "category": r[2], "date": str(r[3]), "type": r[4]
    } for r in rows])

@app.route('/admin/analytics', methods=['GET'])
def admin_analytics():
    if logged_in_user["role"] != 'admin':
        return jsonify({"success": False, "message": "Admin only"}), 403
    cur = get_cursor()
    cur.execute("SELECT COUNT(*) FROM users WHERE role='user'")
    u_count = cur.fetchone()[0]
    cur.execute("SELECT IFNULL(SUM(amount), 0) FROM expenses WHERE type='expense'")
    e_sum = cur.fetchone()[0]
    cur.close()
    return jsonify({"total_users": u_count, "total_expenses": float(e_sum)})

# ================= BUDGET MODULE =================

@app.route('/budget/set', methods=['POST'])
def set_budget():
    data          = request.json
    user_id       = data['user_id']
    monthly_limit = data['monthly_limit']
    cursor = get_cursor()
    cursor.execute("""
        INSERT INTO budgets (user_id, monthly_limit, month, year)
        VALUES (%s, %s, MONTH(CURDATE()), YEAR(CURDATE()))
        ON DUPLICATE KEY UPDATE monthly_limit = %s
    """, (user_id, monthly_limit, monthly_limit))
    mysql_conn.commit()
    cursor.close()
    return jsonify({"message": "Budget saved"})

@app.route('/budget/progress/<int:user_id>')
def budget_progress(user_id):
    cursor = get_cursor(dictionary=True)
    cursor.execute("""
        SELECT monthly_limit FROM budgets
        WHERE user_id=%s AND month=MONTH(CURDATE()) AND year=YEAR(CURDATE())
    """, (user_id,))
    budget = cursor.fetchone()
    if not budget:
        cursor.close()
        return jsonify({"monthly_limit": 0, "total_expense": 0, "progress": 0})
    monthly_limit = float(budget['monthly_limit'])
    cursor.execute("""
        SELECT COALESCE(SUM(amount), 0) AS spent FROM expenses
        WHERE user_id=%s AND type='expense'
        AND MONTH(date)=MONTH(CURDATE()) AND YEAR(date)=YEAR(CURDATE())
        AND status='confirmed'
    """, (user_id,))
    row   = cursor.fetchone()
    spent = float(row['spent']) if row and row['spent'] is not None else 0.0
    progress = min(spent / monthly_limit, 1) if monthly_limit > 0 else 0
    cursor.close()
    return jsonify({"monthly_limit": monthly_limit, "total_expense": spent, "progress": progress})

@app.route('/budget/check_alert/<int:user_id>')
def check_alert(user_id):
    cursor = get_cursor(dictionary=True)
    cursor.execute("""
        SELECT monthly_limit FROM budgets
        WHERE user_id=%s AND month=MONTH(CURDATE()) AND year=YEAR(CURDATE())
    """, (user_id,))
    budget = cursor.fetchone()
    if not budget:
        cursor.close()
        return jsonify({"alert": None})
    limit = float(budget['monthly_limit'])
    cursor.execute("""
        SELECT COALESCE(SUM(amount), 0) AS spent FROM expenses
        WHERE user_id=%s AND type='expense'
        AND MONTH(date)=MONTH(CURDATE()) AND YEAR(date)=YEAR(CURDATE())
        AND status='confirmed'
    """, (user_id,))
    spent   = float(cursor.fetchone()['spent'])
    percent = (spent / limit) * 100 if limit > 0 else 0
    alert   = None
    if percent >= 90:
        alert = "Critical: 90% of your budget used"
    elif percent >= 75:
        alert = "Warning: 75% of your budget used"
    elif percent >= 50:
        alert = "Notice: 50% of your budget used"
    cursor.close()
    return jsonify({"percent": percent, "alert": alert})

@app.route('/notifications/<int:user_id>')
def get_notifications(user_id):
    cursor = get_cursor(dictionary=True)
    cursor.execute("""
        SELECT id, message, created_at FROM notifications
        WHERE user_id=%s ORDER BY created_at DESC
    """, (user_id,))
    notifications = cursor.fetchall()
    cursor.close()
    return jsonify(notifications)

# ================= WISHLIST MODULE =================

@app.route('/wishlist', methods=['POST'])
def add_wishlist_item():
    data          = request.json
    user_id       = data.get("user_id", logged_in_user["id"])
    item_name     = data.get("item_name")
    target_amount = data.get("target_amount")
    if not item_name or not target_amount or not user_id:
        return jsonify({"success": False, "message": "Invalid data"}), 400
    cur = get_cursor()
    cur.execute("""
        INSERT INTO wishlist (user_id, item_name, target_amount, total_saved)
        VALUES (%s, %s, %s, 0.0)
    """, (user_id, item_name, target_amount))
    mysql_conn.commit()
    cur.close()
    return jsonify({"success": True}), 201

@app.route('/wishlist/<int:user_id>', methods=['GET'])
def get_wishlist(user_id):
    cur = get_cursor(dictionary=True)
    cur.execute("""
        SELECT id, item_name, target_amount, total_saved,
               COALESCE(previous_saved, 0.0) AS previous_saved
        FROM wishlist WHERE user_id=%s
    """, (user_id,))
    items = cur.fetchall()
    for item in items:
        for key in ('target_amount', 'total_saved', 'previous_saved'):
            if isinstance(item.get(key), Decimal):
                item[key] = float(item[key])
            elif item.get(key) is None:
                item[key] = 0.0
    cur.close()
    return jsonify(items)

@app.route('/wishlist/save', methods=['POST'])
def save_to_wishlist():
    data        = request.json
    user_id     = data.get("user_id", logged_in_user["id"])
    wishlist_id = data.get("wishlist_id")
    amount      = data.get("amount")
    if not wishlist_id or not amount or not user_id:
        return jsonify({"success": False, "message": "Invalid data"}), 400
    cur = get_cursor(dictionary=True)
    cur.execute("""
        INSERT INTO wishlist_savings (wishlist_id, user_id, amount, month, year)
        VALUES (%s, %s, %s, MONTH(CURDATE()), YEAR(CURDATE()))
    """, (wishlist_id, user_id, amount))
    cur.execute("""
        UPDATE wishlist SET total_saved = total_saved + %s, previous_saved = 0.0
        WHERE id = %s AND user_id = %s
    """, (amount, wishlist_id, user_id))
    cur.execute("SELECT balance FROM users WHERE id = %s", (user_id,))
    actual_balance = float(cur.fetchone()["balance"])
    cur.execute("""
        SELECT COALESCE(SUM(total_saved), 0) AS total_saved_sum
        FROM wishlist WHERE user_id = %s
    """, (user_id,))
    total_saved_sum = float(cur.fetchone()["total_saved_sum"])
    reset_triggered = False
    if actual_balance < total_saved_sum:
        cur.execute("""
            UPDATE wishlist SET previous_saved = total_saved, total_saved = 0
            WHERE user_id=%s AND total_saved > 0
        """, (user_id,))
        reset_triggered = True
    mysql_conn.commit()
    cur.close()
    return jsonify({"success": True, "reset_triggered": reset_triggered})

@app.route('/wishlist/dismiss_recovery', methods=['POST'])
def dismiss_recovery():
    data        = request.json
    user_id     = data.get("user_id", logged_in_user["id"])
    wishlist_id = data.get("wishlist_id")
    if not wishlist_id or not user_id:
        return jsonify({"success": False, "message": "Invalid data"}), 400
    cur = get_cursor()
    cur.execute(
        "UPDATE wishlist SET previous_saved = 0.0 WHERE id=%s AND user_id=%s",
        (wishlist_id, user_id)
    )
    mysql_conn.commit()
    cur.close()
    return jsonify({"success": True})

@app.route('/wishlist/<int:wishlist_id>', methods=['DELETE'])
def delete_wishlist_item(wishlist_id):
    data    = request.json or {}
    user_id = data.get("user_id", logged_in_user.get("id"))
    if not user_id:
        return jsonify({"success": False, "message": "Unauthorized or missing user_id"}), 401
    cur = get_cursor()
    cur.execute("DELETE FROM wishlist WHERE id=%s AND user_id=%s", (wishlist_id, user_id))
    if cur.rowcount == 0:
        cur.close()
        return jsonify({"success": False, "message": "Item not found or unauthorized"}), 404
    mysql_conn.commit()
    cur.close()
    return jsonify({"success": True, "message": "Wishlist item deleted successfully"})

@app.route('/balances/<int:user_id>')
def get_balances(user_id):
    cur = get_cursor(dictionary=True)
    cur.execute("SELECT balance FROM users WHERE id=%s", (user_id,))
    balance = float(cur.fetchone()["balance"])
    cur.execute("""
        SELECT COALESCE(SUM(total_saved), 0) AS saved FROM wishlist WHERE user_id=%s
    """, (user_id,))
    saved     = float(cur.fetchone()["saved"])
    spendable = balance - saved
    cur.close()
    return jsonify({"actual_balance": balance, "saved_amount": saved, "spendable_balance": spendable})

# ================= BUDGET CARD =================

@app.route('/budget/card', methods=['GET'])
def budget_card():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"success": False, "message": "Missing user_id"}), 400

    cur = get_cursor(dictionary=True)

    cur.execute("""
        SELECT monthly_limit FROM budgets
        WHERE user_id=%s AND month=MONTH(CURDATE()) AND year=YEAR(CURDATE())
    """, (user_id,))
    budget_row    = cur.fetchone()
    monthly_limit = float(budget_row['monthly_limit']) if budget_row else None

    cur.execute("""
        SELECT COALESCE(SUM(amount), 0) AS spent FROM expenses
        WHERE user_id=%s AND type='expense' AND status='confirmed'
        AND MONTH(date)=MONTH(CURDATE()) AND YEAR(date)=YEAR(CURDATE())
    """, (user_id,))
    month_spent = float(cur.fetchone()['spent'])

    cur.execute("""
        SELECT COALESCE(SUM(amount), 0) AS income FROM expenses
        WHERE user_id=%s AND type='income' AND status='confirmed'
        AND MONTH(date)=MONTH(CURDATE()) AND YEAR(date)=YEAR(CURDATE())
    """, (user_id,))
    month_income = float(cur.fetchone()['income'])

    cur.execute("""
        SELECT category AS name, SUM(amount) AS amount FROM expenses
        WHERE user_id=%s AND type='expense' AND status='confirmed'
        AND MONTH(date)=MONTH(CURDATE()) AND YEAR(date)=YEAR(CURDATE())
        GROUP BY category ORDER BY amount DESC LIMIT 4
    """, (user_id,))
    categories = [{"name": r['name'], "amount": float(r['amount'])} for r in cur.fetchall()]

    from calendar import monthrange
    today        = datetime.today()
    days_in_month = monthrange(today.year, today.month)[1]
    days_left    = days_in_month - today.day

    budget_pct       = None
    budget_remaining = None
    projected        = None
    if monthly_limit and monthly_limit > 0:
        budget_pct       = round((month_spent / monthly_limit) * 100, 1)
        budget_remaining = round(monthly_limit - month_spent, 2)
        daily_rate       = month_spent / max(today.day, 1)
        projected        = round(daily_rate * days_in_month, 2)

    savings_rate = 0
    if month_income > 0:
        savings_rate = round(((month_income - month_spent) / month_income) * 100, 1)

    if budget_pct is None:
        status         = 'info'
        status_message = f"You've spent ₹{month_spent:.0f} this month. Set a budget to track progress."
    elif budget_pct >= 100:
        status         = 'danger'
        status_message = f"Over budget! Spent ₹{month_spent:.0f} of ₹{monthly_limit:.0f}."
    elif budget_pct >= 75:
        status         = 'warning'
        status_message = f"75% of budget used. ₹{budget_remaining:.0f} left for {days_left} days."
    elif budget_pct >= 50:
        status         = 'warning'
        status_message = f"Halfway through budget. ₹{budget_remaining:.0f} remaining."
    else:
        status         = 'success'
        status_message = f"On track! ₹{budget_remaining:.0f} left for {days_left} days."

    top_category = categories[0]['name'] if categories else None

    cur.close()
    return jsonify({
        "success":         True,
        "budget":          monthly_limit,
        "budget_pct":      budget_pct,
        "budget_remaining": budget_remaining,
        "month_spent":     month_spent,
        "month_income":    month_income,
        "savings_rate":    savings_rate,
        "categories":      categories,
        "days_left":       days_left,
        "projected":       projected,
        "status":          status,
        "status_message":  status_message,
        "top_category":    top_category,
    })

# ================= SMART INSIGHTS =================

@app.route('/insights/smart', methods=['GET'])
def smart_insights():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"success": False, "message": "Missing user_id"}), 400

    cur      = get_cursor(dictionary=True)
    insights = []

    cur.execute("""
        SELECT monthly_limit FROM budgets
        WHERE user_id=%s AND month=MONTH(CURDATE()) AND year=YEAR(CURDATE())
    """, (user_id,))
    budget_row = cur.fetchone()
    if budget_row:
        limit = float(budget_row['monthly_limit'])
        cur.execute("""
            SELECT COALESCE(SUM(amount), 0) AS spent FROM expenses
            WHERE user_id=%s AND type='expense' AND status='confirmed'
            AND MONTH(date)=MONTH(CURDATE()) AND YEAR(date)=YEAR(CURDATE())
        """, (user_id,))
        spent = float(cur.fetchone()['spent'])
        pct   = (spent / limit * 100) if limit > 0 else 0
        if pct >= 90:
            insights.append({"type": "danger",  "message": f"You've used {pct:.0f}% of your monthly budget!"})
        elif pct >= 70:
            insights.append({"type": "warning", "message": f"Budget {pct:.0f}% used. Slow down spending."})
        else:
            insights.append({"type": "success", "message": f"Budget on track — {pct:.0f}% used so far."})

    cur.execute("""
        SELECT category, SUM(amount) AS total FROM expenses
        WHERE user_id=%s AND type='expense' AND status='confirmed'
        AND MONTH(date)=MONTH(CURDATE()) AND YEAR(date)=YEAR(CURDATE())
        GROUP BY category ORDER BY total DESC LIMIT 1
    """, (user_id,))
    top = cur.fetchone()
    if top:
        insights.append({"type": "info", "message": f"Top spend: {top['category']} (₹{float(top['total']):.0f} this month)"})

    cur.execute("""
        SELECT COALESCE(SUM(amount), 0) AS prev FROM expenses
        WHERE user_id=%s AND type='expense' AND status='confirmed'
        AND MONTH(date)=MONTH(CURDATE()-INTERVAL 1 MONTH)
        AND YEAR(date)=YEAR(CURDATE()-INTERVAL 1 MONTH)
    """, (user_id,))
    prev = float(cur.fetchone()['prev'])
    cur.execute("""
        SELECT COALESCE(SUM(amount), 0) AS curr FROM expenses
        WHERE user_id=%s AND type='expense' AND status='confirmed'
        AND MONTH(date)=MONTH(CURDATE()) AND YEAR(date)=YEAR(CURDATE())
    """, (user_id,))
    curr = float(cur.fetchone()['curr'])
    if prev > 0:
        diff_pct = ((curr - prev) / prev) * 100
        if diff_pct > 10:
            insights.append({"type": "warning", "message": f"Spending up {diff_pct:.0f}% vs last month."})
        elif diff_pct < -10:
            insights.append({"type": "success", "message": f"Spending down {abs(diff_pct):.0f}% vs last month. Great job!"})

    cur.close()
    return jsonify({"success": True, "insights": insights[:3]})

# ============================================================
# RULE-BASED AI FINANCE CHATBOT
# ============================================================

_conversation_ctx = {}


def _ctx(uid):
    if uid not in _conversation_ctx:
        _conversation_ctx[uid] = {"last_intent": None, "last_data": {}}
    return _conversation_ctx[uid]


def _set_ctx(uid, intent, data=None):
    _conversation_ctx[uid] = {"last_intent": intent, "last_data": data or {}}


# ── KEYWORD → SUGGESTION MENUS ─────────────────────────────
KEYWORD_MENUS = {
    "budget": {
        "label": "budget",
        "prompt": "Here are some things I can help with for 💰 Budget:",
        "suggestions": [
            "How much of my budget have I used this month?",
            "Am I over budget?",
            "How much budget is remaining?",
            "Set my monthly budget to 10000",
            "What is my projected spend for this month?",
        ],
    },
    "food": {
        "label": "Food",
        "prompt": "Here are some Food 🍔 expense queries:",
        "suggestions": [
            "How much did I spend on food this month?",
            "Show my food expenses this month",
            "How much did I spend on food last month?",
            "Compare food spending this month vs last month",
        ],
    },
    "transport": {
        "label": "Transport",
        "prompt": "Here are some Transport 🚗 expense queries:",
        "suggestions": [
            "How much did I spend on transport this month?",
            "Show my transport expenses this month",
            "How much did I spend on transport last month?",
        ],
    },
    "shopping": {
        "label": "Shopping",
        "prompt": "Here are some Shopping 🛍 expense queries:",
        "suggestions": [
            "How much did I spend on shopping this month?",
            "Show my shopping expenses this month",
            "How much did I spend on shopping last month?",
        ],
    },
    "entertainment": {
        "label": "Entertainment",
        "prompt": "Here are some Entertainment 🎬 expense queries:",
        "suggestions": [
            "How much did I spend on entertainment this month?",
            "Show my entertainment expenses this month",
            "How much on entertainment last month?",
        ],
    },
    "health": {
        "label": "Health",
        "prompt": "Here are some Health 🏥 expense queries:",
        "suggestions": [
            "How much did I spend on health this month?",
            "Show my health expenses this month",
            "How much on medicine last month?",
        ],
    },
    "bills": {
        "label": "Bills",
        "prompt": "Here are some Bills 📄 expense queries:",
        "suggestions": [
            "How much did I spend on bills this month?",
            "Show my bills this month",
            "How much on bills last month?",
        ],
    },
    "wishlist": {
        "label": "wishlist / goals",
        "prompt": "Here are some Wishlist 🎯 queries:",
        "suggestions": [
            "Show all my wishlist goals",
            "How much have I saved for iPhone?",
            "How much have I saved for laptop?",
            "When can I reach my goals?",
            "How much more do I need for my goals?",
        ],
    },
    "goal": {
        "label": "wishlist / goals",
        "prompt": "Here are some Goal 🎯 queries:",
        "suggestions": [
            "Show all my wishlist goals",
            "When can I reach my goals?",
            "How much more do I need for my goals?",
            "How much have I saved so far?",
        ],
    },
    "expense": {
        "label": "expenses",
        "prompt": "Here are some Expense 📊 queries:",
        "suggestions": [
            "How much did I spend this month?",
            "Show category wise spending breakdown",
            "Compare this month vs last month",
            "Show my recent transactions",
            "What are my top expense categories?",
        ],
    },
    "spending": {
        "label": "spending",
        "prompt": "Here are some Spending 📊 queries:",
        "suggestions": [
            "How much did I spend this month?",
            "Where am I spending the most?",
            "Show category wise spending breakdown",
            "Compare this month vs last month",
            "Show my recent transactions",
        ],
    },
    "save": {
        "label": "savings",
        "prompt": "Here are some Savings 💎 queries:",
        "suggestions": [
            "How much have I saved this month?",
            "What is my savings rate?",
            "How can I save more money?",
            "How can I save 50000 this month?",
            "Am I saving enough?",
        ],
    },
    "saving": {
        "label": "savings",
        "prompt": "Here are some Savings 💎 queries:",
        "suggestions": [
            "How much have I saved this month?",
            "What is my savings rate?",
            "How can I save more money?",
            "Am I saving enough?",
        ],
    },
    "savings": {
        "label": "savings",
        "prompt": "Here are some Savings 💎 queries:",
        "suggestions": [
            "How much have I saved this month?",
            "What is my savings rate?",
            "How can I save more money?",
            "Am I saving enough?",
        ],
    },
    "income": {
        "label": "income",
        "prompt": "Here are some Income 💵 queries:",
        "suggestions": [
            "What is my total income this month?",
            "How much did I earn this month?",
            "Show my income vs expenses",
            "What is my savings rate?",
        ],
    },
    "salary": {
        "label": "income / salary",
        "prompt": "Here are some Salary 💵 queries:",
        "suggestions": [
            "What is my total income this month?",
            "How much did I earn this month?",
            "Show my income vs expenses",
            "What is my savings rate?",
        ],
    },
    "tips": {
        "label": "financial tips",
        "prompt": "Here are some Financial Tips 📚 I can give you:",
        "suggestions": [
            "Give me financial tips",
            "How can I reduce my expenses?",
            "How to save more money?",
            "What is the 50/30/20 rule for my income?",
            "How should I manage my money?",
        ],
    },
    "advice": {
        "label": "financial advice",
        "prompt": "Here are some Advice 📚 queries:",
        "suggestions": [
            "Give me financial advice",
            "How can I save more money?",
            "How to reduce my expenses?",
            "What is the 50/30/20 rule for my income?",
        ],
    },
    "afford": {
        "label": "purchase advice",
        "prompt": "Here are some Purchase 🛒 advice queries:",
        "suggestions": [
            "Can I afford a phone for 15000?",
            "Should I buy a laptop for 60000?",
            "Can I afford a purchase of 5000?",
            "When can I afford my wishlist goals?",
        ],
    },
    "buy": {
        "label": "purchase advice",
        "prompt": "Here are some Purchase 🛒 queries:",
        "suggestions": [
            "Should I buy a laptop for 60000?",
            "Can I afford a phone for 15000?",
            "When can I buy my wishlist items?",
            "Can I afford a purchase of 5000?",
        ],
    },
    "balance": {
        "label": "balance",
        "prompt": "Here are some Balance 💳 queries:",
        "suggestions": [
            "What is my current balance?",
            "How much can I spend?",
            "How much have I saved in my wishlist goals?",
            "What is my spendable balance?",
        ],
    },
    "report": {
        "label": "report / summary",
        "prompt": "Here are some Report 📋 queries:",
        "suggestions": [
            "Show my spending summary this month",
            "Compare this month vs last month",
            "Show category wise spending breakdown",
            "What are my top expense categories?",
            "Show my recent transactions",
        ],
    },
    "summary": {
        "label": "summary",
        "prompt": "Here are some Summary 📋 queries:",
        "suggestions": [
            "Show my spending summary this month",
            "How much did I spend this month?",
            "Compare this month vs last month",
            "What is my savings rate?",
        ],
    },
}

_PURE_KEYWORDS = set(KEYWORD_MENUS.keys()) | {
    "food", "transport", "shopping", "entertainment",
    "health", "bills", "budget", "wishlist", "goal", "goals",
    "expense", "expenses", "spending", "save", "saving", "savings",
    "income", "salary", "tips", "advice", "afford", "buy",
    "balance", "report", "summary",
}


def _detect_keyword_menu(text):
    tl = text.lower().strip()
    question_signals = [
        "how much", "how many", "how long", "how can", "how do", "how will",
        "what is", "what are", "what was", "what did",
        "show me", "show my", "list my", "give me",
        "am i", "did i", "can i", "should i", "is my",
        "when can", "when will", "when did",
        "i spent", "i paid", "i bought", "i earned",
        "add ", "record ", "set my", "update my",
        "compare", "vs ", "versus",
    ]
    if any(tl.startswith(q) or q in tl for q in question_signals):
        return None
    if len(tl.split()) > 4:
        return None
    for keyword, menu in KEYWORD_MENUS.items():
        if tl == keyword or tl == keyword + "s" or tl == keyword + "ing":
            return menu
        words = tl.split()
        if len(words) <= 2 and keyword in words:
            return menu
    return None


CATEGORY_MAP = {
    "food": "Food", "lunch": "Food", "dinner": "Food", "breakfast": "Food",
    "snack": "Food", "snacks": "Food", "meal": "Food", "restaurant": "Food",
    "coffee": "Food", "tea": "Food", "eat": "Food", "eating": "Food",
    "grocery": "Food", "groceries": "Food", "vegetable": "Food", "vegetables": "Food",
    "swiggy": "Food", "zomato": "Food", "hotel": "Food",
    "transport": "Transport", "bus": "Transport", "auto": "Transport",
    "cab": "Transport", "uber": "Transport", "ola": "Transport",
    "petrol": "Transport", "fuel": "Transport", "metro": "Transport",
    "train": "Transport", "travel": "Transport",
    "rapido": "Transport", "rickshaw": "Transport",
    "shopping": "Shopping", "clothes": "Shopping", "shirt": "Shopping",
    "shoes": "Shopping", "amazon": "Shopping", "flipkart": "Shopping",
    "dress": "Shopping", "bag": "Shopping", "purchase": "Shopping",
    "entertainment": "Entertainment", "movie": "Entertainment",
    "movies": "Entertainment", "game": "Entertainment", "games": "Entertainment",
    "netflix": "Entertainment", "hotstar": "Entertainment", "prime": "Entertainment",
    "ott": "Entertainment", "party": "Entertainment", "concert": "Entertainment",
    "bills": "Bills", "bill": "Bills", "electricity": "Bills",
    "wifi": "Bills", "internet": "Bills", "phone": "Bills",
    "recharge": "Bills", "rent": "Bills", "water": "Bills",
    "insurance": "Bills", "emi": "Bills",
    "health": "Health", "medicine": "Health", "doctor": "Health",
    "hospital": "Health", "pharmacy": "Health", "gym": "Health",
    "medical": "Health", "clinic": "Health",
    "salary": "Salary", "wages": "Salary",
    "freelance": "Freelance", "freelancing": "Freelance",
    "business": "Business",
    "investment": "Investment", "invest": "Investment", "returns": "Investment",
    "gift": "Gift", "gifted": "Gift",
    "refund": "Other",
}

INCOME_KEYWORDS = {
    "salary", "credited", "received", "earned", "income",
    "freelance", "investment", "gift", "refund", "bonus", "got paid"
}

WISHLIST_TRIGGER_PHRASES = [
    "wishlist", "wish list", "my goals", "my goal",
    "saving for", "emergency fund",
    "when can i buy", "when will i afford", "how long till",
    "how much have i saved for", "how much more do i need",
    "how much more for", "progress on", "progress for",
    "my wishlist", "goal progress", "goals progress",
    "how far am i from", "when will i reach",
    "how much is left for", "still need for",
    "saved for my", "contributed to",
]

WISHLIST_ITEM_KEYWORDS = [
    "iphone", "laptop", "phone", "bike", "car", "vacation", "holiday",
    "tv", "watch", "tablet", "camera", "trip", "fund",
]

WISHLIST_ITEM_PROGRESS_PHRASES = [
    "how much have i saved for", "how much more do i need for",
    "how much more for", "progress on", "progress for",
    "how far am i from", "when will i reach my",
    "how much is left for", "still need for", "saved for",
    "contributed to", "how much toward", "how much for my",
]

WISHLIST_TIMELINE_KEYWORDS = [
    "how long", "when can", "when will", "afford",
    "reach my goal", "achieve", "timeline", "how many months"
]


def extract_amount(text):
    patterns = [
        r'(?:\u20b9|rs\.?|inr)\s*(\d+(?:,\d{3})*(?:\.\d{1,2})?)',
        r'(\d+(?:,\d{3})*(?:\.\d{1,2})?)\s*(?:rupees?|rs\.?|\u20b9)',
        r'\b(\d{3,}(?:\.\d{1,2})?)\b',
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            raw = m.group(1).replace(',', '')
            try:
                val = float(raw)
                if val > 0:
                    return val
            except Exception:
                pass
    return None


def extract_category(text):
    tl = text.lower()
    for keyword, category in CATEGORY_MAP.items():
        if re.search(r'\b' + re.escape(keyword) + r'\b', tl):
            return category
    if any(k in tl for k in ["iphone", "tablet", "tv", "watch"]):
        return "Shopping"
    if any(k in tl for k in ["taxi", "ride"]):
        return "Transport"
    return None


def extract_type(text):
    tl = text.lower()
    if any(k in tl for k in INCOME_KEYWORDS):
        return "income"
    return "expense"


def extract_date(text):
    tl    = text.lower()
    today = date_type.today()
    if "day before yesterday" in tl:
        return str(today - timedelta(days=2)), "day before yesterday"
    if "yesterday" in tl:
        return str(today - timedelta(days=1)), "yesterday"
    if "today" in tl:
        return str(today), "today"
    m = re.search(r'(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})', text)
    if m:
        day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if year < 100:
            year += 2000
        try:
            d = date_type(year, month, day)
            return str(d), str(d)
        except Exception:
            pass
    return str(today), "today"


def date_range_from_text(text):
    tl    = text.lower()
    today = date_type.today()
    if "last month" in tl:
        first = today.replace(day=1) - timedelta(days=1)
        return str(first.replace(day=1)), str(first), "last month"
    if "last week" in tl:
        start = today - timedelta(days=today.weekday() + 7)
        return str(start), str(start + timedelta(days=6)), "last week"
    if "this week" in tl:
        start = today - timedelta(days=today.weekday())
        return str(start), str(today), "this week"
    if "yesterday" in tl:
        d = today - timedelta(days=1)
        return str(d), str(d), "yesterday"
    if "today" in tl:
        return str(today), str(today), "today"
    return str(today.replace(day=1)), str(today), "this month"


def _get_top_category(uid, cur, start):
    cur.execute("""
        SELECT category, SUM(amount) AS total FROM expenses
        WHERE user_id=%s AND type='expense' AND status='confirmed' AND date >= %s
        GROUP BY category ORDER BY total DESC LIMIT 1
    """, (uid, start))
    row = cur.fetchone()
    if row:
        if isinstance(row, dict):
            return (row['category'], float(row['total']))
        return (row[0], float(row[1]))
    return (None, 0)


def _get_month_spent(uid, cur, start):
    cur.execute("""
        SELECT IFNULL(SUM(amount), 0) FROM expenses
        WHERE user_id=%s AND type='expense' AND status='confirmed' AND date >= %s
    """, (uid, start))
    row = cur.fetchone()
    if isinstance(row, dict):
        return float(list(row.values())[0])
    return float(row[0])


_ADD_PATTERNS = [
    r'\bi\s+(spent|paid|bought|ate|had|used)\b',
    r'\badd(ed)?\s+(expense|income|transaction)',
    r'\badd\s+(rs\.?|inr|\u20b9)?\s*\d',
    r'\brecord(ed)?\b.{0,30}\d',
    r'\blog(ged)?\b.{0,30}\d',
    r'\bjust\s+paid\b',
    r'\bpurchased\b.{0,30}\d',
    r'\b(received|got|earned|credited)\s+(rs\.?|inr|\u20b9)?\s*\d',
    r'\bsalary\b.{0,20}\d',
]


def classify_intent(text, ctx):
    tl = text.lower().strip()

    is_query = any(tl.startswith(w) for w in [
        "how", "what", "show", "list", "display", "when", "where",
        "am i", "did i", "do i", "is my", "compare", "give", "why", "which"
    ])

    _budget_quick = [
        "am i overspending", "am i over spending", "overspending",
        "overspent", "over spent", "am i spending too much",
        "spending too much this month", "is my spending too high",
        "are my expenses too high", "check my budget",
        "budget alert", "budget warning", "budget critical",
        "budget usage", "budget utilization", "budget utilisation",
        "what percent of my budget", "how much of my budget",
        "how much have i used", "how close am i to my limit",
        "hit my limit", "reached my limit", "crossed my limit",
        "crossed the limit", "crossed budget",
    ]
    if any(k in tl for k in _budget_quick):
        return "CHECK_BUDGET"

    if "when can i buy" in tl or "when will i buy" in tl:
        return "WISHLIST_TIMELINE"
    if any(k in tl for k in ["should i buy", "can i buy",
                               "is it worth buying", "afford to buy"]):
        return "PURCHASE_ADVICE"

    if any(k in tl for k in WISHLIST_TRIGGER_PHRASES):
        if any(k in tl for k in WISHLIST_TIMELINE_KEYWORDS):
            return "WISHLIST_TIMELINE"
        if any(k in tl for k in WISHLIST_ITEM_PROGRESS_PHRASES):
            return "WISHLIST_ITEM_PROGRESS"
        return "WISHLIST_STATUS"

    if any(k in tl for k in WISHLIST_ITEM_KEYWORDS):
        if any(k in tl for k in ["when can", "when will", "how long", "afford"]):
            return "WISHLIST_TIMELINE"
        if any(k in tl for k in WISHLIST_ITEM_PROGRESS_PHRASES + [
                "how much", "how far", "progress", "saved for", "still need"]):
            return "WISHLIST_ITEM_PROGRESS"

    if any(k in tl for k in ["can i afford", "is it worth", "should i spend",
                               "worth buying", "good buy"]):
        return "PURCHASE_ADVICE"

    if extract_amount(tl) and any(k in tl for k in [
            "how will i save", "how can i save", "able to save",
            "how do i save", "want to save", "need to save",
            "i want to save", "i need to save", "save up for",
            "to reach", "to achieve"]):
        return "SAVINGS_GOAL"

    financial_advice_phrases = [
        "how can i save more", "how to save more", "help me save",
        "save more money", "tips to save", "tips to reduce",
        "how to reduce", "reduce my expenses", "reduce spending",
        "manage my budget", "manage my money", "budgeting strategy",
        "budgeting tip", "financial tip", "why am i overspending",
        "overspending", "spending too much", "how should i manage",
        "give me tips", "give me advice", "suggest me", "any suggestions",
        "what is a good budget", "money management", "investment advice",
        "financial advice", "financial planning", "save money",
        "how to save", "how to manage",
    ]
    if any(k in tl for k in financial_advice_phrases):
        return "FINANCIAL_ADVICE"
    if any(k in tl for k in ["advice", "tips", "strategy", "improve finances"]):
        return "FINANCIAL_ADVICE"

    if any(k in tl for k in ["delete", "remove", "edit", "modify"]) and \
       any(k in tl for k in ["expense", "transaction", "record",
                               "last", "recent", "the"]):
        return "EDIT_EXPENSE"

    if any(k in tl for k in ["compare", "vs last", "versus last",
                               "more than last month", "less than last month",
                               "higher than last", "lower than last",
                               "did i spend more", "did i spend less",
                               "this week vs", "this month vs",
                               "how does this month", "how does this week"]):
        return "COMPARE_EXPENSES"

    analysis_phrases = [
        "where am i spending", "where is my money going",
        "where does my money go", "which category costs",
        "which category has", "which category is highest",
        "top expense", "top expenses", "biggest expense",
        "most money on", "spending the most",
        "highest spending", "highest expense category",
        "spending habits", "spending analysis", "spending breakdown",
        "analyse my", "analyze my", "show my biggest", "what are my top",
        "category wise", "categorywise", "by category",
        "category breakdown", "category wise spending",
        "show category", "category spending", "per category",
        "each category", "category-wise",
    ]
    if any(k in tl for k in analysis_phrases):
        return "SPENDING_ANALYSIS"

    set_budget_patterns = [
        r'\bset\b.{0,25}\bbudget\b',
        r'\bmy budget\b.{0,15}\bis\b',
        r'\bupdate\b.{0,20}\bbudget\b',
        r'\bchange\b.{0,20}\bbudget\b',
    ]
    if any(re.search(p, tl) for p in set_budget_patterns) and extract_amount(tl):
        return "SET_BUDGET"

    if any(k in tl for k in [
            "how much budget", "budget left", "budget remaining",
            "remaining budget", "budget status", "check budget",
            "am i exceeding", "did i cross", "exceeded my budget",
            "over budget", "within budget", "percentage of my budget",
            "how much is left", "how much money is remaining",
            "spending limit", "monthly limit", "money remaining",
            "am i overspending", "am i over spending", "overspending",
            "overspent", "over spent", "exceeded budget",
            "budget alert", "budget warning", "budget critical",
            "what percent", "what percentage", "how much percent",
            "how much of my budget", "how much have i used",
            "budget usage", "budget utilization", "budget utilisation",
            "crossed budget", "reached my limit", "hit my limit",
            "exceeded limit", "how close am i", "how far over",
            "spending limit reached", "crossed the limit",
            "are my expenses too high", "is my spending high",
            "too much this month",
    ]):
        return "CHECK_BUDGET"
    if "budget" in tl and any(k in tl for k in [
            "left", "remaining", "used", "status",
            "exceed", "cross", "how much", "percentage",
            "percent", "alert", "warning", "critical",
            "over", "limit", "utiliz", "usage"]):
        return "CHECK_BUDGET"
    if any(k in tl for k in [
            "am i overspending", "overspending", "overspent",
            "spending too much this month", "expenses too high",
            "am i spending too much"]):
        return "CHECK_BUDGET"

    savings_phrases = [
        "how much did i save", "how much have i saved",
        "what are my savings", "total savings",
        "savings this month", "savings this week",
        "am i saving enough", "how much can i save",
        "how much money did i save", "what did i save",
        "savings rate", "am i saving", "my savings",
    ]
    if any(k in tl for k in savings_phrases):
        return "SAVINGS_INFO"
    if ("saved" in tl or "saving" in tl) and any(k in tl for k in [
            "how much", "total", "this month", "this week", "today", "enough"]):
        return "SAVINGS_INFO"

    has_category = any(k in tl for k in CATEGORY_MAP)
    has_add_verb = any(re.search(p, tl) for p in _ADD_PATTERNS)

    if has_category and not has_add_verb:
        if any(k in tl for k in [
                "how much", "show", "list", "total", "what",
                "spending on", "spent on", "expense on", "expenses on",
                "my food", "my transport", "my shopping", "my health",
                "my bills", "my entertainment",
        ]):
            return "CATEGORY_EXPENSE"
        if any(k in tl for k in ["expense", "expenses", "spending", "spent"]):
            return "CATEGORY_EXPENSE"

    total_phrases = [
        "how much did i spend", "how much have i spent",
        "how much i spent", "how much i spend",
        "total expense", "total spending", "total spent",
        "how much this week", "how much this month",
        "how much today", "how much yesterday",
        "what is my total", "show my total",
        "how much money did i spend", "spending total",
        "what is my spending", "how much so far",
        "what was my spending", "overall spending",
        "total so far", "total for this", "total for last",
        "what is my total spending",
    ]
    if any(k in tl for k in total_phrases):
        return "GET_TOTAL_EXPENSE"
    if "how much" in tl and any(k in tl for k in [
            "today", "yesterday", "this week", "last week",
            "this month", "last month", "so far", "spent", "spend"]):
        return "GET_TOTAL_EXPENSE"

    show_phrases = [
        "show my expenses", "show expenses", "list expenses",
        "list my expenses", "list all expenses", "show all expenses",
        "show my transactions", "list transactions", "show recent",
        "recent expenses", "recent transactions", "display expenses",
        "show spending history", "spending history",
        "show today", "show this week", "show last week",
        "show this month", "show last month",
        "what did i spend today", "what did i spend this",
    ]
    if any(k in tl for k in show_phrases):
        return "SHOW_EXPENSES"

    if has_add_verb and not is_query:
        return "ADD_EXPENSE"
    if any(re.search(p, tl) for p in [
            r'\badd(ed)?\s+(expense|income|transaction)',
            r'\badd\s+(rs\.?|inr|\u20b9)?\s*\d',
            r'\brecord(ed)?\b.{0,30}\d',
            r'\blog(ged)?\b.{0,30}\d',
    ]):
        return "ADD_EXPENSE"
    if not is_query and re.search(r'\d+\s+(on|for)\s+\w+', tl):
        return "ADD_EXPENSE"

    if any(k in tl for k in [
            "yesterday", "last week", "this week",
            "last month", "this month", "today",
            "spending for", "what did i spend"]):
        return "TIME_BASED_QUERY"

    greeting_words = [
        "hi", "hello", "hey", "hii", "helo", "start", "help",
        "good morning", "good evening", "good afternoon",
        "yo", "hai", "hola", "what can you do", "how are you",
    ]
    if tl in greeting_words or any(tl.startswith(g) for g in greeting_words):
        return "GREETING"

    followup_triggers = [
        "what about", "how about", "and last", "and this",
        "add another", "one more", "also add",
        "only show", "just show", "left now", "what about now",
    ]
    if any(k in tl for k in followup_triggers):
        if ctx.get("last_intent") and ctx["last_intent"] != "UNKNOWN":
            return "FOLLOW_UP_QUERY"

    if ctx.get("last_intent") and ctx["last_intent"] not in (
            "UNKNOWN", "GREETING", "ADD_EXPENSE"):
        if any(k in tl for k in [
                "this week", "last week", "this month",
                "last month", "today", "yesterday"]):
            return ctx["last_intent"]

    return "UNKNOWN"


def handle_greeting(username, balance, uid, cur):
    today      = date_type.today()
    start      = str(today.replace(day=1))
    month_spent = _get_month_spent(uid, cur, start)
    top_cat, top_amt = _get_top_category(uid, cur, start)
    greeting   = f"Hey {username}! 👋 I'm FinBot, your personal finance assistant.\n\n"
    greeting  += f"💳 Balance: Rs.{balance:.2f}\n"
    if month_spent > 0:
        greeting += f"📊 Spent this month: Rs.{month_spent:.2f}\n"
        if top_cat:
            greeting += f"🏆 Top category: {top_cat} (Rs.{top_amt:.2f})\n"
    greeting += (
        "\n💡 Tip: Type a keyword to see suggested questions!\n\n"
        "Try these keywords:\n"
        "  • budget  — budget tracking & alerts\n"
        "  • expense — spending summaries\n"
        "  • wishlist — savings goals\n"
        "  • savings — how much you've saved\n"
        "  • food / transport / shopping — category spending\n"
        "  • tips — financial advice\n"
        "  • buy / afford — purchase advice\n\n"
        "Or just ask me directly:\n"
        "  'I spent 300 on food'\n"
        "  'How much did I spend this week?'\n"
        "  'Am I over budget?'"
    )
    return greeting


def handle_get_total_expense(text, uid, cur):
    tl = text.lower()
    if "so far" in tl or "overall" in tl or "all time" in tl:
        cur.execute("""
            SELECT IFNULL(SUM(CASE WHEN type='expense' THEN amount ELSE 0 END), 0),
                   IFNULL(SUM(CASE WHEN type='income'  THEN amount ELSE 0 END), 0),
                   COUNT(*) FROM expenses WHERE user_id=%s AND status='confirmed'
        """, (uid,))
        label = "All Time"
    else:
        start, end, label = date_range_from_text(text)
        cur.execute("""
            SELECT IFNULL(SUM(CASE WHEN type='expense' THEN amount ELSE 0 END), 0),
                   IFNULL(SUM(CASE WHEN type='income'  THEN amount ELSE 0 END), 0),
                   COUNT(*) FROM expenses
            WHERE user_id=%s AND status='confirmed' AND date BETWEEN %s AND %s
        """, (uid, start, end))
    row = cur.fetchone()
    if isinstance(row, dict):
        vals = list(row.values())
        spent, earned, count = float(vals[0]), float(vals[1]), int(vals[2])
    else:
        spent, earned, count = float(row[0]), float(row[1]), int(row[2])
    net      = earned - spent
    response = (
        f"Summary — {label}:\n\n"
        f"  Total Spent:  Rs.{spent:.2f}\n"
        f"  Total Earned: Rs.{earned:.2f}\n"
        f"  Net:          {'+' if net >= 0 else ''}Rs.{net:.2f}\n"
        f"  Transactions: {count}"
    )
    if earned > 0:
        ratio = (spent / earned) * 100
        if ratio > 90:
            response += f"\n\n⚠️ You've spent {ratio:.0f}% of income — very little left!"
        elif ratio > 70:
            response += f"\n\n💡 {ratio:.0f}% of income spent. Try keeping it under 70%."
        else:
            response += f"\n\n✅ Good — {ratio:.0f}% of income spent."
    return response


def handle_category_expense(text, uid, cur):
    category       = extract_category(text) or "Other"
    start, end, label = date_range_from_text(text)
    cur.execute("""
        SELECT IFNULL(SUM(amount), 0), COUNT(*) FROM expenses
        WHERE user_id=%s AND status='confirmed' AND type='expense'
        AND LOWER(category)=LOWER(%s) AND date BETWEEN %s AND %s
    """, (uid, category, start, end))
    row = cur.fetchone()
    if isinstance(row, dict):
        total, count = float(list(row.values())[0]), int(list(row.values())[1])
    else:
        total, count = float(row[0]), int(row[1])
    if total == 0:
        return f"No {category} expenses found for {label}."
    cur.execute("""
        SELECT IFNULL(SUM(amount), 0) FROM expenses
        WHERE user_id=%s AND status='confirmed' AND type='expense' AND date BETWEEN %s AND %s
    """, (uid, start, end))
    row2      = cur.fetchone()
    total_all = float(list(row2.values())[0]) if isinstance(row2, dict) else float(row2[0])
    pct       = (total / total_all * 100) if total_all > 0 else 0
    response  = (
        f"{category} spending — {label}:\n\n"
        f"  Total:         Rs.{total:.2f}\n"
        f"  Transactions:  {count}\n"
        f"  % of spending: {pct:.0f}%"
    )
    if category == "Food" and total > 4000:
        response += "\n\n💡 Food spending is high. Meal prepping can save Rs.1,000+/month."
    elif category == "Transport" and total > 3000:
        response += "\n\n💡 High transport costs. Metro or carpooling could cut this significantly."
    elif category == "Entertainment" and total > 2000:
        response += "\n\n💡 Entertainment is significant. Look for free or discounted options."
    elif pct > 40:
        response += f"\n\n⚠️ {category} is {pct:.0f}% of spending — consider setting a limit."
    return response


def _get_budget_this_month(cur, uid):
    cur.execute("""
        SELECT monthly_limit FROM budgets
        WHERE user_id=%s AND month=MONTH(CURDATE()) AND year=YEAR(CURDATE())
    """, (uid,))
    row = cur.fetchone()
    if row is None:
        return None
    return float(row['monthly_limit']) if isinstance(row, dict) else float(row[0])


def handle_check_budget(uid, cur):
    cur.execute("SELECT balance FROM users WHERE id=%s", (uid,))
    row     = cur.fetchone()
    balance = float(row['balance']) if isinstance(row, dict) else float(row[0])

    limit       = _get_budget_this_month(cur, uid)
    today       = date_type.today()
    start       = str(today.replace(day=1))
    month_spent = _get_month_spent(uid, cur, start)

    if limit is None:
        return (
            f"No budget set for this month yet.\n\n"
            f"  Balance:     Rs.{balance:.2f}\n"
            f"  Month spent: Rs.{month_spent:.2f}\n\n"
            f"Set one: 'Set my monthly budget to 10000'"
        )

    remaining  = limit - month_spent
    pct        = (month_spent / limit * 100) if limit > 0 else 0
    days_left  = max(1, 30 - today.day)
    daily_left = remaining / days_left

    filled = min(int(pct / 10), 10)
    bar    = '█' * filled + '░' * (10 - filled)

    top_cat, top_amt = _get_top_category(uid, cur, start)

    if pct >= 100:
        excess     = month_spent - limit
        alert_line = f"🚨 OVER BUDGET by Rs.{excess:.0f}!"
        emoji      = "🚨"
        title      = "Over Budget!"
    elif pct >= 90:
        alert_line = "🔴 Critical — 90%+ of budget used."
        emoji      = "🔴"
        title      = "Critical Alert"
    elif pct >= 75:
        alert_line = "🟡 Warning — 75%+ of budget used."
        emoji      = "🟡"
        title      = "Budget Warning"
    elif pct >= 50:
        alert_line = "🔵 Notice — 50%+ of budget used."
        emoji      = "🔵"
        title      = "Heads Up"
    else:
        alert_line = "✅ You're well within budget."
        emoji      = "✅"
        title      = "On Track"

    response = (
        f"{emoji} {title}\n\n"
        f"  [{bar}]  {pct:.1f}%\n\n"
        f"  Budget:     Rs.{limit:.2f}\n"
        f"  Spent:      Rs.{month_spent:.2f}\n"
        f"  Remaining:  Rs.{max(0, remaining):.2f}\n"
        f"  Days left:  {days_left} days\n"
    )
    if pct < 100:
        response += f"  Daily left: Rs.{max(0, daily_left):.2f}/day\n"
    response += f"\n{alert_line}\n"

    if top_cat:
        response += f"\n💡 Top category: {top_cat} (Rs.{top_amt:.0f})"
        response += " — cut this first." if pct >= 75 else "."

    days_elapsed = max(1, today.day)
    if month_spent > 0:
        projected  = (month_spent / days_elapsed) * 30
        response  += f"\n📈 Projected month-end spend: Rs.{projected:.0f}"
        if projected > limit:
            response += f" (Rs.{projected - limit:.0f} over budget at this rate)"

    return response


def handle_set_budget(text, uid, cur, conn):
    amount = extract_amount(text)
    if not amount:
        return "Please tell me the amount.\nExample: 'Set my budget to 10000'"

    cur.execute("""
        SELECT monthly_limit FROM budgets
        WHERE user_id=%s AND month=MONTH(CURDATE()) AND year=YEAR(CURDATE())
    """, (uid,))
    existing = cur.fetchone()

    if existing:
        old = float(existing['monthly_limit']) if isinstance(existing, dict) else float(existing[0])
        cur.execute("""
            UPDATE budgets SET monthly_limit=%s
            WHERE user_id=%s AND month=MONTH(CURDATE()) AND year=YEAR(CURDATE())
        """, (amount, uid))
        msg = f"✅ Budget updated: Rs.{old:.0f} → Rs.{amount:.0f}/month."
    else:
        cur.execute("""
            INSERT INTO budgets (user_id, monthly_limit, month, year)
            VALUES (%s, %s, MONTH(CURDATE()), YEAR(CURDATE()))
        """, (uid, amount))
        msg = f"✅ Monthly budget set to Rs.{amount:.0f}."

    conn.commit()

    today       = date_type.today()
    start       = str(today.replace(day=1))
    month_spent = _get_month_spent(uid, cur, start)
    pct         = (month_spent / amount * 100) if amount > 0 else 0

    msg += f"\n\nThis month so far: Rs.{month_spent:.2f} ({pct:.1f}% used)."
    if pct >= 90:
        msg += "\n🔴 Critical — almost all of this budget is already used!"
    elif pct >= 75:
        msg += "\n🟡 Warning — 75%+ already used this month."
    elif pct >= 50:
        msg += "\n🔵 Halfway through budget already."
    else:
        msg += "\n✅ You're well within your new budget."
    return msg


def handle_show_expenses(text, uid, cur):
    start, end, label = date_range_from_text(text)
    cur.execute("""
        SELECT date, category, type, amount FROM expenses
        WHERE user_id=%s AND status='confirmed' AND date BETWEEN %s AND %s
        ORDER BY date DESC, time DESC LIMIT 20
    """, (uid, start, end))
    rows = cur.fetchall()
    if not rows:
        return f"No transactions found for {label}."
    lines     = [f"Transactions — {label}:\n"]
    total_exp = 0
    total_inc = 0
    for r in rows:
        if isinstance(r, dict):
            sign = "+" if r['type'] == "income" else "-"
            amt  = float(r['amount'])
            lines.append(f"  {str(r['date'])}  {r['category']:<14}  {sign}Rs.{amt:.2f}")
            if r['type'] == "expense":
                total_exp += amt
            else:
                total_inc += amt
        else:
            sign = "+" if r[2] == "income" else "-"
            amt  = float(r[3])
            lines.append(f"  {str(r[0])}  {r[1]:<14}  {sign}Rs.{amt:.2f}")
            if r[2] == "expense":
                total_exp += amt
            else:
                total_inc += amt
    lines.append(f"\n  Expenses: Rs.{total_exp:.2f}  |  Income: Rs.{total_inc:.2f}")
    if len(rows) == 20:
        lines.append("  (Showing latest 20)")
    return "\n".join(lines)


def handle_spending_analysis(uid, cur):
    today = date_type.today()
    start = str(today.replace(day=1))
    cur.execute("""
        SELECT category, SUM(amount) AS total, COUNT(*) AS cnt FROM expenses
        WHERE user_id=%s AND type='expense' AND status='confirmed' AND date >= %s
        GROUP BY category ORDER BY total DESC
    """, (uid, start))
    rows = cur.fetchall()
    if not rows:
        return "No expense data this month yet."
    if isinstance(rows[0], dict):
        total_all = float(sum(float(r['total']) for r in rows))
        lines     = ["Spending analysis — this month:\n"]
        for i, r in enumerate(rows, 1):
            amt = float(r['total'])
            pct = (amt / total_all * 100) if total_all > 0 else 0
            lines.append(f"  {i}. {r['category']:<14} Rs.{amt:>8.2f}  {pct:.0f}%  ({r['cnt']} txns)")
        top_cat = rows[0]['category']
        top_pct = (float(rows[0]['total']) / total_all * 100) if total_all > 0 else 0
    else:
        total_all = float(sum(float(r[1]) for r in rows))
        lines     = ["Spending analysis — this month:\n"]
        for i, r in enumerate(rows, 1):
            amt = float(r[1])
            pct = (amt / total_all * 100) if total_all > 0 else 0
            lines.append(f"  {i}. {r[0]:<14} Rs.{amt:>8.2f}  {pct:.0f}%  ({r[2]} txns)")
        top_cat = rows[0][0]
        top_pct = (float(rows[0][1]) / total_all * 100) if total_all > 0 else 0
    lines.append(f"\n  Total: Rs.{total_all:.2f}")
    saving = total_all * 0.10
    lines.append(
        f"\n💡 {top_cat} is your top spend ({top_pct:.0f}%).\n"
        f"   Cutting all categories 10% saves Rs.{saving:.0f}/month."
    )
    return "\n".join(lines)


def handle_savings_info(uid, cur):
    today       = date_type.today()
    start_month = str(today.replace(day=1))
    cur.execute("""
        SELECT IFNULL(SUM(CASE WHEN type='income'  THEN amount ELSE 0 END), 0),
               IFNULL(SUM(CASE WHEN type='expense' THEN amount ELSE 0 END), 0)
        FROM expenses WHERE user_id=%s AND status='confirmed' AND date >= %s
    """, (uid, start_month))
    row = cur.fetchone()
    if isinstance(row, dict):
        vals = list(row.values())
        earned, spent = float(vals[0]), float(vals[1])
    else:
        earned, spent = float(row[0]), float(row[1])
    saved = earned - spent
    rate  = (saved / earned * 100) if earned > 0 else 0

    start_3m = str(today - timedelta(days=90))
    cur.execute("""
        SELECT IFNULL(SUM(CASE WHEN type='income'  THEN amount ELSE 0 END), 0),
               IFNULL(SUM(CASE WHEN type='expense' THEN amount ELSE 0 END), 0)
        FROM expenses WHERE user_id=%s AND status='confirmed' AND date >= %s
    """, (uid, start_3m))
    r3 = cur.fetchone()
    if isinstance(r3, dict):
        v3 = list(r3.values())
        avg_save_3m = (float(v3[0]) - float(v3[1])) / 3
    else:
        avg_save_3m = (float(r3[0]) - float(r3[1])) / 3
    # FIX: clamp to 0 so negative avg doesn't mislead wishlist messages
    avg_save_3m = max(0.0, avg_save_3m)

    reply = (
        f"Savings summary:\n\n"
        f"  Earned this month:   Rs.{earned:.2f}\n"
        f"  Spent this month:    Rs.{spent:.2f}\n"
        f"  Saved this month:    Rs.{saved:.2f}  ({rate:.1f}%)\n"
        f"  Avg savings/month:   Rs.{avg_save_3m:.2f}  (3-month avg)\n"
    )
    if earned == 0:
        reply += "\n💡 No income recorded. Add income to track savings properly."
    elif rate < 10:
        top_cat, top_amt = _get_top_category(uid, cur, start_month)
        reply += f"\n⚠️ Savings rate below 10% — quite low."
        if top_cat:
            reply += f"\n💡 Try cutting {top_cat} spending (Rs.{top_amt:.0f}) to save more."
    elif rate >= 30:
        reply += "\n🎯 Excellent saving rate — above 30%! Keep it up!"
    else:
        reply += f"\n💡 Aim for 20-30% savings rate. You're at {rate:.1f}%."

    cur.execute("SELECT COUNT(*) FROM wishlist WHERE user_id=%s", (uid,))
    wl_row   = cur.fetchone()
    wl_count = int(list(wl_row.values())[0]) if isinstance(wl_row, dict) else int(wl_row[0])
    if wl_count > 0 and avg_save_3m > 0:
        reply += f"\n\n📋 You have {wl_count} wishlist goal(s). Ask 'Show my wishlist' for progress."
    return reply


def handle_savings_goal(text, uid, cur):
    target_amount = extract_amount(text)
    if not target_amount:
        return handle_savings_info(uid, cur)

    today        = date_type.today()
    start_month  = str(today.replace(day=1))
    days_in_month = 30
    days_left    = max(1, days_in_month - today.day)

    cur.execute("""
        SELECT IFNULL(SUM(CASE WHEN type='income'  THEN amount ELSE 0 END), 0),
               IFNULL(SUM(CASE WHEN type='expense' THEN amount ELSE 0 END), 0)
        FROM expenses WHERE user_id=%s AND status='confirmed' AND date >= %s
    """, (uid, start_month))
    row = cur.fetchone()
    if isinstance(row, dict):
        v = list(row.values())
        income, spent = float(v[0]), float(v[1])
    else:
        income, spent = float(row[0]), float(row[1])
    current_savings = income - spent

    start_3m = str(today - timedelta(days=90))
    cur.execute("""
        SELECT IFNULL(SUM(CASE WHEN type='income'  THEN amount ELSE 0 END), 0),
               IFNULL(SUM(CASE WHEN type='expense' THEN amount ELSE 0 END), 0)
        FROM expenses WHERE user_id=%s AND status='confirmed' AND date >= %s
    """, (uid, start_3m))
    r3 = cur.fetchone()
    if isinstance(r3, dict):
        v3 = list(r3.values())
        avg_monthly_savings = max(0.0, (float(v3[0]) - float(v3[1])) / 3)
    else:
        avg_monthly_savings = max(0.0, (float(r3[0]) - float(r3[1])) / 3)

    cur.execute("""
        SELECT category, SUM(amount) AS total FROM expenses
        WHERE user_id=%s AND type='expense' AND status='confirmed' AND date >= %s
        GROUP BY category ORDER BY total DESC LIMIT 3
    """, (uid, start_month))
    top_cats = cur.fetchall()

    still_needed        = max(0, target_amount - current_savings)
    daily_spend_allowed = (income - target_amount) / days_in_month if income > 0 else 0

    reply = [f"Savings Goal: Rs.{target_amount:.0f}\n"]

    if income == 0:
        reply.append("No income recorded this month.")
        reply.append(f"Add your salary first so I can check if Rs.{target_amount:.0f} is reachable.\n")
        if avg_monthly_savings > 0:
            if avg_monthly_savings >= target_amount:
                reply.append(f"Based on your 3-month avg (Rs.{avg_monthly_savings:.0f}/mo) — looks achievable!")
            else:
                months = target_amount / avg_monthly_savings
                reply.append(f"Your 3-month avg savings: Rs.{avg_monthly_savings:.0f}/month.")
                reply.append(f"At this rate, Rs.{target_amount:.0f} takes ~{months:.1f} months.")
        return "\n".join(reply)

    reply.append(f"  Income this month:   Rs.{income:.0f}")
    reply.append(f"  Spent so far:        Rs.{spent:.0f}")
    reply.append(f"  Saved so far:        Rs.{current_savings:.0f}")
    reply.append(f"  Still need to save:  Rs.{still_needed:.0f}")
    reply.append(f"  Days remaining:      {days_left} days\n")

    if current_savings >= target_amount:
        reply.append(f"✅ You've already saved Rs.{current_savings:.0f} — goal achieved this month!")
        return "\n".join(reply)

    if income < target_amount:
        reply.append(f"⚠️ Your income (Rs.{income:.0f}) is less than the goal (Rs.{target_amount:.0f}).")
        reply.append("Consider spreading this goal across 2-3 months.\n")
    else:
        reply.append(f"To reach Rs.{target_amount:.0f} by month end:")
        reply.append(f"  • Spend max Rs.{max(0, daily_spend_allowed):.0f}/day for rest of month")
        reply.append(f"  • Save Rs.{still_needed / days_left:.0f}/day from now\n")

    if top_cats and still_needed > 0:
        reply.append("Where you can cut:")
        for cat_row in top_cats:
            if isinstance(cat_row, dict):
                cat, cat_amt = cat_row['category'], float(cat_row['total'])
            else:
                cat, cat_amt = cat_row[0], float(cat_row[1])
            reply.append(f"  • {cat} (Rs.{cat_amt:.0f}) — 20% cut saves Rs.{cat_amt * 0.2:.0f}")
        total_saveable = (
            sum(float(r['total']) * 0.2 for r in top_cats)
            if isinstance(top_cats[0], dict)
            else sum(float(r[1]) * 0.2 for r in top_cats)
        )
        reply.append("")
        if total_saveable >= still_needed:
            reply.append(f"Cutting 20% from top 3 categories saves Rs.{total_saveable:.0f} — enough!")
        else:
            reply.append(f"Cutting 20% from top categories saves Rs.{total_saveable:.0f}.")
            reply.append(f"Still Rs.{still_needed - total_saveable:.0f} short — delay non-essentials too.")

    return "\n".join(reply)


def handle_compare(uid, cur):
    today      = date_type.today()
    start_this = str(today.replace(day=1))
    cur.execute("""
        SELECT IFNULL(SUM(CASE WHEN type='expense' THEN amount ELSE 0 END), 0),
               IFNULL(SUM(CASE WHEN type='income'  THEN amount ELSE 0 END), 0)
        FROM expenses WHERE user_id=%s AND status='confirmed' AND date >= %s
    """, (uid, start_this))
    this = cur.fetchone()
    if isinstance(this, dict):
        v = list(this.values())
        this_exp, this_inc = float(v[0]), float(v[1])
    else:
        this_exp, this_inc = float(this[0]), float(this[1])

    last_end   = today.replace(day=1) - timedelta(days=1)
    last_start = last_end.replace(day=1)
    cur.execute("""
        SELECT IFNULL(SUM(CASE WHEN type='expense' THEN amount ELSE 0 END), 0),
               IFNULL(SUM(CASE WHEN type='income'  THEN amount ELSE 0 END), 0)
        FROM expenses WHERE user_id=%s AND status='confirmed' AND date BETWEEN %s AND %s
    """, (uid, str(last_start), str(last_end)))
    last = cur.fetchone()
    if isinstance(last, dict):
        v = list(last.values())
        last_exp, last_inc = float(v[0]), float(v[1])
    else:
        last_exp, last_inc = float(last[0]), float(last[1])

    diff  = this_exp - last_exp
    pct   = (diff / last_exp * 100) if last_exp > 0 else 0
    reply = (
        f"Month comparison:\n\n"
        f"                This Month   Last Month\n"
        f"  {'─' * 36}\n"
        f"  Spent:   Rs.{this_exp:>10.2f}  Rs.{last_exp:>10.2f}\n"
        f"  Earned:  Rs.{this_inc:>10.2f}  Rs.{last_inc:>10.2f}\n"
        f"  Net:     Rs.{this_inc - this_exp:>+10.2f}  Rs.{last_inc - last_exp:>+10.2f}\n\n"
        f"  Change: Rs.{abs(diff):.2f} ({abs(pct):.1f}% {'more' if diff > 0 else 'less'} than last month)"
    )
    if diff > 0:
        reply += f"\n\n⚠️ Spending increased by Rs.{diff:.0f} this month."
    elif diff < 0:
        reply += f"\n\n✅ Spending decreased by Rs.{abs(diff):.0f} this month. Great job!"
    else:
        reply += "\n\nSpending is the same as last month."
    return reply


def handle_wishlist_status(uid, cur):
    cur.execute("""
        SELECT item_name, target_amount, total_saved FROM wishlist WHERE user_id=%s
    """, (uid,))
    items = cur.fetchall()
    if not items:
        return "You have no wishlist goals yet. Add one from the Wishlist section!"
    lines = ["Your Wishlist Goals 🎯\n"]
    for item in items:
        if isinstance(item, dict):
            name, target, saved = item['item_name'], float(item['target_amount']), float(item['total_saved'])
        else:
            name, target, saved = item[0], float(item[1]), float(item[2])
        pct       = (saved / target * 100) if target > 0 else 0
        remaining = max(0, target - saved)
        filled    = min(int(pct / 10), 10)
        bar       = '█' * filled + '░' * (10 - filled)
        lines.append(f"  {name}")
        lines.append(f"  [{bar}] {pct:.0f}%")
        lines.append(f"  Saved: Rs.{saved:.0f} / Rs.{target:.0f}  (Rs.{remaining:.0f} left)\n")
    return "\n".join(lines)


def handle_wishlist_timeline(uid, cur):
    cur.execute("""
        SELECT item_name, target_amount, total_saved FROM wishlist WHERE user_id=%s
    """, (uid,))
    items = cur.fetchall()
    if not items:
        return "No wishlist goals found. Add goals from the Wishlist section!"

    today    = date_type.today()
    start_3m = str(today - timedelta(days=90))
    cur.execute("""
        SELECT IFNULL(SUM(CASE WHEN type='income'  THEN amount ELSE 0 END), 0),
               IFNULL(SUM(CASE WHEN type='expense' THEN amount ELSE 0 END), 0)
        FROM expenses WHERE user_id=%s AND status='confirmed' AND date >= %s
    """, (uid, start_3m))
    r = cur.fetchone()
    if isinstance(r, dict):
        v = list(r.values())
        avg_save = max(0.0, (float(v[0]) - float(v[1])) / 3)
    else:
        avg_save = max(0.0, (float(r[0]) - float(r[1])) / 3)

    lines = ["Wishlist Timeline 📅\n"]
    if avg_save <= 0:
        lines.append("No savings data to estimate timelines.")
        lines.append("Add income and keep expenses low to see projections.")
        return "\n".join(lines)

    for item in items:
        if isinstance(item, dict):
            name, target, saved = item['item_name'], float(item['target_amount']), float(item['total_saved'])
        else:
            name, target, saved = item[0], float(item[1]), float(item[2])
        remaining = max(0, target - saved)
        if remaining <= 0:
            lines.append(f"  ✅ {name} — Goal reached!")
        else:
            months_needed = remaining / avg_save
            lines.append(f"  🎯 {name}")
            lines.append(f"     Need Rs.{remaining:.0f} more")
            lines.append(f"     At Rs.{avg_save:.0f}/month → ~{months_needed:.1f} months")
        lines.append("")
    return "\n".join(lines)


def handle_wishlist_item_progress(text, uid, cur):
    cur.execute("""
        SELECT item_name, target_amount, total_saved FROM wishlist WHERE user_id=%s
    """, (uid,))
    items = cur.fetchall()
    if not items:
        return "No wishlist goals found."
    tl      = text.lower()
    matched = None
    for item in items:
        name = item['item_name'] if isinstance(item, dict) else item[0]
        if name.lower() in tl:
            matched = item
            break
    if not matched:
        for kw in WISHLIST_ITEM_KEYWORDS:
            if kw in tl:
                for item in items:
                    name = item['item_name'] if isinstance(item, dict) else item[0]
                    if kw in name.lower():
                        matched = item
                        break
            if matched:
                break
    if not matched:
        return handle_wishlist_status(uid, cur)
    if isinstance(matched, dict):
        name, target, saved = matched['item_name'], float(matched['target_amount']), float(matched['total_saved'])
    else:
        name, target, saved = matched[0], float(matched[1]), float(matched[2])
    remaining = max(0, target - saved)
    pct       = (saved / target * 100) if target > 0 else 0
    filled    = min(int(pct / 10), 10)
    bar       = '█' * filled + '░' * (10 - filled)
    return (
        f"Progress for {name}:\n\n"
        f"  [{bar}] {pct:.0f}%\n\n"
        f"  Target:    Rs.{target:.0f}\n"
        f"  Saved:     Rs.{saved:.0f}\n"
        f"  Remaining: Rs.{remaining:.0f}\n"
    )


def handle_financial_advice(text, uid, cur):
    today = date_type.today()
    start = str(today.replace(day=1))
    cur.execute("""
        SELECT IFNULL(SUM(CASE WHEN type='income'  THEN amount ELSE 0 END), 0),
               IFNULL(SUM(CASE WHEN type='expense' THEN amount ELSE 0 END), 0)
        FROM expenses WHERE user_id=%s AND status='confirmed' AND date >= %s
    """, (uid, start))
    row = cur.fetchone()
    if isinstance(row, dict):
        v = list(row.values())
        income, spent = float(v[0]), float(v[1])
    else:
        income, spent = float(row[0]), float(row[1])
    saved = income - spent
    rate  = (saved / income * 100) if income > 0 else 0

    advice = ["💡 Financial Tips for You:\n"]

    if income > 0:
        needs           = income * 0.50
        wants           = income * 0.30
        savings_target  = income * 0.20
        advice.append(f"50/30/20 Rule for your income (Rs.{income:.0f}):")
        advice.append(f"  • Needs (50%):   Rs.{needs:.0f}")
        advice.append(f"  • Wants (30%):   Rs.{wants:.0f}")
        advice.append(f"  • Savings (20%): Rs.{savings_target:.0f}\n")

    top_cat, top_amt = _get_top_category(uid, cur, start)
    if top_cat:
        advice.append(f"Your top spend is {top_cat} (Rs.{top_amt:.0f}).")
        advice.append(f"  → A 20% cut saves Rs.{top_amt * 0.2:.0f}/month\n")

    advice.append("General tips:")
    advice.append("  • Track every expense — awareness reduces spending")
    advice.append("  • Set category limits to avoid overspending")
    advice.append("  • Pay yourself first — move savings before spending")
    advice.append("  • Build an emergency fund of 3-6 months expenses")
    advice.append("  • Review subscriptions monthly — cancel unused ones")

    if rate < 10 and income > 0:
        advice.append(f"\n⚠️ Your savings rate is only {rate:.0f}%. Aim for at least 20%.")
    elif rate >= 20:
        advice.append(f"\n✅ Great savings rate of {rate:.0f}%! Consider investing the surplus.")

    return "\n".join(advice)


def handle_purchase_advice(text, uid, cur):
    amount = extract_amount(text)
    if not amount:
        return "Please mention the purchase amount.\nExample: 'Can I afford a laptop for 50000?'"
    cur.execute("SELECT balance FROM users WHERE id=%s", (uid,))
    row     = cur.fetchone()
    balance = float(row['balance']) if isinstance(row, dict) else float(row[0])

    today       = date_type.today()
    start       = str(today.replace(day=1))
    month_spent = _get_month_spent(uid, cur, start)
    limit       = _get_budget_this_month(cur, uid)

    lines = [f"Purchase Advice: Rs.{amount:.0f}\n"]
    lines.append(f"  Current balance:  Rs.{balance:.2f}")
    lines.append(f"  This month spent: Rs.{month_spent:.2f}")
    if limit:
        budget_left = max(0, limit - month_spent)
        lines.append(f"  Budget remaining: Rs.{budget_left:.2f}\n")
    else:
        lines.append("")

    after_purchase = balance - amount
    if after_purchase < 0:
        lines.append(f"❌ Cannot afford — would leave you Rs.{abs(after_purchase):.0f} short.")
    elif after_purchase < balance * 0.20:
        lines.append(f"⚠️ Risky — only Rs.{after_purchase:.0f} left after purchase (under 20% of balance).")
        lines.append("   Consider waiting or saving more first.")
    elif limit and amount > (limit - month_spent):
        lines.append(f"🟡 Affordable but exceeds remaining budget (Rs.{limit - month_spent:.0f}).")
        lines.append("   You may go over budget this month.")
    else:
        lines.append(f"✅ You can afford this! Rs.{after_purchase:.0f} left after purchase.")

    return "\n".join(lines)


def handle_time_based_query(text, uid, cur):
    return handle_get_total_expense(text, uid, cur)


def handle_edit_expense(uid, cur):
    return (
        "To edit or delete an expense, please use the Expenses section in the app.\n\n"
        "You can tap any transaction to edit or delete it directly."
    )


def handle_add_expense(text, uid, cur, conn):
    amount = extract_amount(text)
    if not amount:
        return "I couldn't find an amount. Try: 'I spent 200 on food'"
    category   = extract_category(text) or "Other"
    t_type     = extract_type(text)
    date_str, date_label = extract_date(text)
    now        = datetime.now()

    cur.execute(
        "INSERT INTO expenses(amount, date, time, category, user_id, type, status, entry_method) "
        "VALUES (%s, %s, %s, %s, %s, %s, 'confirmed', 'chatbot')",
        (amount, date_str, now.strftime('%H:%M:%S'), category, uid, t_type)
    )
    adj = amount if t_type == 'income' else -amount
    cur.execute("UPDATE users SET balance = balance + %s WHERE id=%s", (adj, uid))
    conn.commit()

    cur.execute("SELECT balance FROM users WHERE id=%s", (uid,))
    row         = cur.fetchone()
    new_balance = float(row['balance']) if isinstance(row, dict) else float(row[0])

    action = "Income" if t_type == 'income' else "Expense"
    sign   = "+" if t_type == 'income' else "-"
    reply  = (
        f"✅ {action} recorded!\n\n"
        f"  Amount:   {sign}Rs.{amount:.2f}\n"
        f"  Category: {category}\n"
        f"  Date:     {date_label}\n"
        f"  Balance:  Rs.{new_balance:.2f}"
    )

    if t_type == 'expense':
        limit = _get_budget_this_month(cur, uid)
        if limit:
            today       = date_type.today()
            start       = str(today.replace(day=1))
            month_spent = _get_month_spent(uid, cur, start)
            pct         = (month_spent / limit * 100) if limit > 0 else 0
            if pct >= 90:
                reply += f"\n\n🔴 Budget alert: {pct:.0f}% used this month!"
            elif pct >= 75:
                reply += f"\n\n🟡 Budget warning: {pct:.0f}% used this month."

    return reply


def handle_follow_up(text, uid, cur, ctx_data):
    last_intent = ctx_data.get("last_intent")
    if last_intent in ("GET_TOTAL_EXPENSE", "TIME_BASED_QUERY"):
        return handle_get_total_expense(text, uid, cur)
    if last_intent == "CATEGORY_EXPENSE":
        return handle_category_expense(text, uid, cur)
    if last_intent == "SHOW_EXPENSES":
        return handle_show_expenses(text, uid, cur)
    return handle_get_total_expense(text, uid, cur)


# ── CHATBOT ENDPOINT ────────────────────────────────────────
@app.route('/ai/chat', methods=['POST'])
def chatbot():
    data    = request.json
    user_id = data.get('user_id')
    message = (data.get('message') or '').strip()

    if not user_id or not message:
        return jsonify({"success": False, "message": "Missing user_id or message"}), 400

    cur = get_cursor(dictionary=True)

    cur.execute("SELECT username, balance FROM users WHERE id=%s", (user_id,))
    user_row = cur.fetchone()
    if not user_row:
        cur.close()
        return jsonify({"success": False, "message": "User not found"}), 404

    username = user_row['username']
    balance  = float(user_row['balance'])
    ctx_data = _ctx(user_id)

    menu = _detect_keyword_menu(message)
    if menu:
        cur.close()
        return jsonify({
            "success":     True,
            "response":    menu["prompt"],
            "suggestions": menu["suggestions"]
        })

    intent = classify_intent(message, ctx_data)
    _set_ctx(user_id, intent)

    try:
        if intent == "GREETING":
            reply = handle_greeting(username, balance, user_id, cur)
        elif intent == "ADD_EXPENSE":
            reply = handle_add_expense(message, user_id, cur, mysql_conn)
        elif intent == "GET_TOTAL_EXPENSE":
            reply = handle_get_total_expense(message, user_id, cur)
        elif intent == "CATEGORY_EXPENSE":
            reply = handle_category_expense(message, user_id, cur)
        elif intent == "CHECK_BUDGET":
            reply = handle_check_budget(user_id, cur)
        elif intent == "SET_BUDGET":
            reply = handle_set_budget(message, user_id, cur, mysql_conn)
        elif intent == "SHOW_EXPENSES":
            reply = handle_show_expenses(message, user_id, cur)
        elif intent == "SPENDING_ANALYSIS":
            reply = handle_spending_analysis(user_id, cur)
        elif intent == "SAVINGS_INFO":
            reply = handle_savings_info(user_id, cur)
        elif intent == "SAVINGS_GOAL":
            reply = handle_savings_goal(message, user_id, cur)
        elif intent == "COMPARE_EXPENSES":
            reply = handle_compare(user_id, cur)
        elif intent == "WISHLIST_STATUS":
            reply = handle_wishlist_status(user_id, cur)
        elif intent == "WISHLIST_TIMELINE":
            reply = handle_wishlist_timeline(user_id, cur)
        elif intent == "WISHLIST_ITEM_PROGRESS":
            reply = handle_wishlist_item_progress(message, user_id, cur)
        elif intent == "FINANCIAL_ADVICE":
            reply = handle_financial_advice(message, user_id, cur)
        elif intent == "PURCHASE_ADVICE":
            reply = handle_purchase_advice(message, user_id, cur)
        elif intent == "TIME_BASED_QUERY":
            reply = handle_time_based_query(message, user_id, cur)
        elif intent == "EDIT_EXPENSE":
            reply = handle_edit_expense(user_id, cur)
        elif intent == "FOLLOW_UP_QUERY":
            reply = handle_follow_up(message, user_id, cur, ctx_data)
        else:
            reply = (
                "I'm not sure how to help with that. Try asking:\n\n"
                "  • 'How much did I spend this month?'\n"
                "  • 'Am I over budget?'\n"
                "  • 'I spent 500 on food'\n"
                "  • 'Show my wishlist goals'\n\n"
                "Or type a keyword like: budget, expense, savings, wishlist, tips"
            )
    except Exception as e:
        traceback.print_exc()
        print(f"Chatbot error for user {user_id}: {e}")
        reply = f"Error: {str(e)}"

    cur.close()
    return jsonify({"success": True, "response": reply})


if __name__ == '__main__':
    app.run(debug=True, port=5000)
