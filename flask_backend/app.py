from flask import Flask, request, jsonify
from flask_cors import CORS
import mysql.connector
from datetime import datetime, timedelta, date as date_type
from decimal import Decimal
import re
import os


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
        cur.execute("SHOW COLUMNS FROM expenses LIKE 'status'")
        result = cur.fetchone()
        if not result:
            print("Adding 'status' column to expenses table...")
            cur.execute("ALTER TABLE expenses ADD COLUMN status VARCHAR(20) DEFAULT 'confirmed'")
            mysql_conn.commit()
            print("Migration successful: 'status' column added.")
        else:
            print("Migration check: 'status' column already exists.")

        cur.execute("SHOW COLUMNS FROM expenses LIKE 'entry_method'")
        result = cur.fetchone()
        if not result:
            print("Adding 'entry_method' column to expenses table...")
            cur.execute("ALTER TABLE expenses ADD COLUMN entry_method VARCHAR(20) DEFAULT 'manual'")
            mysql_conn.commit()
            print("Migration successful: 'entry_method' column added.")

        cur.execute("SHOW TABLES LIKE 'budgets'")
        result = cur.fetchone()
        if not result:
            print("Creating 'budgets' table...")
            cur.execute("""
                CREATE TABLE budgets (
                    user_id INT PRIMARY KEY,
                    monthly_limit DECIMAL(10,2) NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)
            mysql_conn.commit()
            print("Migration successful: 'budgets' table created.")
        else:
            print("Migration check: 'budgets' table already exists.")

        # FIX: Add previous_saved column to wishlist if missing
        cur.execute("SHOW COLUMNS FROM wishlist LIKE 'previous_saved'")
        result = cur.fetchone()
        if not result:
            print("Adding 'previous_saved' column to wishlist table...")
            cur.execute("ALTER TABLE wishlist ADD COLUMN previous_saved DECIMAL(10,2) DEFAULT 0.0")
            mysql_conn.commit()
            print("Migration successful: 'previous_saved' column added.")
        else:
            print("Migration check: 'previous_saved' column already exists.")

    except Exception as e:
        print(f"Migration error: {e}")
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
    username, password, phone, balance = data.get('username'), data.get('password'), data.get('phone'), data.get('balance')
    if is_empty(username) or is_empty(password) or is_empty(phone) or balance is None:
        return jsonify({"success": False, "message": "All fields required"}), 400
    cur = get_cursor()
    cur.execute("SELECT id FROM users WHERE username=%s", (username,))
    if cur.fetchone():
        cur.close()
        return jsonify({"success": False, "message": "Username exists"}), 409
    cur.execute("INSERT INTO users(username, password, phone, balance, role) VALUES (%s, %s, %s, %s, 'user')",
                (username, password, phone, balance))
    mysql_conn.commit()
    cur.close()
    return jsonify({"success": True}), 201

@app.route('/login', methods=['POST'])
def login():
    global logged_in_user
    data = request.json
    username, password = data.get('username'), data.get('password')
    cur = get_cursor()
    cur.execute("SELECT id, balance, role, is_active FROM users WHERE username=%s AND password=%s", (username, password))
    user = cur.fetchone()
    cur.close()
    if not user:
        return jsonify({"success": False, "message": "Invalid credentials"}), 401
    if not user[3]:
        return jsonify({"success": False, "message": "Account deactivated"}), 403
    logged_in_user["id"], logged_in_user["role"] = user[0], user[2]
    return jsonify({"success": True, "id": user[0], "role": user[2], "balance": float(user[1]) if user[2] == 'user' else None})

@app.route('/logout', methods=['POST'])
def logout():
    logged_in_user["id"], logged_in_user["role"] = None, None
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
        query = "SELECT id, amount, date, time, category, type, status, entry_method FROM expenses WHERE user_id=%s AND status=%s ORDER BY date DESC, time DESC"
        params = (logged_in_user["id"], status_filter)
    else:
        query = "SELECT id, amount, date, time, category, type, status, entry_method FROM expenses WHERE user_id=%s ORDER BY date DESC, time DESC"
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
    data = request.json
    amount = data.get('amount')
    category = data.get('category')
    t_type = data.get('type', 'expense')
    status = data.get('status', 'confirmed')
    entry_method = data.get('entry_method', 'manual')
    date_val = data.get('date')
    time_val = data.get('time')
    if amount is None or amount <= 0:
        return jsonify({"success": False, "message": "Invalid amount"}), 400
    now = datetime.now()
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
    data = request.json
    expenses_list = data.get('expenses', [])
    if not expenses_list:
        return jsonify({"success": True, "message": "No expenses to sync"}), 200
    cur = get_cursor()
    count = 0
    for item in expenses_list:
        try:
            amount = item.get('amount')
            date_str = item.get('date')
            time_str = item.get('time', '00:00:00')
            category = item.get('category', 'Uncategorized')
            t_type = item.get('type', 'expense')
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
    return add_expense()

@app.route('/expenses/<int:expense_id>', methods=['PUT'])
def edit_expense(expense_id):
    if logged_in_user["role"] != 'user':
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    data = request.json
    cur = get_cursor()
    cur.execute("SELECT amount, type, category, status FROM expenses WHERE id=%s AND user_id=%s",
                (expense_id, logged_in_user["id"]))
    row = cur.fetchone()
    if not row:
        cur.close()
        return jsonify({"success": False, "message": "Not found"}), 404
    old_amt, old_type, old_category, old_status = float(row[0]), row[1], row[2], row[3]
    new_amt = float(data.get('amount', old_amt))
    new_type = data.get('type', old_type)
    new_category = data.get('category', old_category)
    new_status = data.get('status', old_status)
    if old_status == 'confirmed':
        undo = -old_amt if old_type == 'income' else old_amt
        cur.execute("UPDATE users SET balance = balance + %s WHERE id=%s", (undo, logged_in_user["id"]))
    if new_status == 'confirmed':
        apply = new_amt if new_type == 'income' else -new_amt
        cur.execute("UPDATE users SET balance = balance + %s WHERE id=%s", (apply, logged_in_user["id"]))
    cur.execute("UPDATE expenses SET amount=%s, category=%s, type=%s, status=%s WHERE id=%s",
                (new_amt, new_category, new_type, new_status, expense_id))
    mysql_conn.commit()
    cur.close()
    return jsonify({"success": True})

@app.route('/expenses/<int:expense_id>', methods=['DELETE'])
def delete_expense(expense_id):
    if logged_in_user["role"] != 'user':
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    cur = get_cursor()
    cur.execute("SELECT amount, type, status FROM expenses WHERE id=%s AND user_id=%s",
                (expense_id, logged_in_user["id"]))
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
    q = request.args.get('q', '').strip()
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
    return jsonify([{"id": r[0], "username": r[1], "phone": r[2], "balance": float(r[3]), "active": bool(r[4])} for r in rows])

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
    return jsonify([{"username": r[0], "amount": float(r[1]), "category": r[2], "date": str(r[3]), "type": r[4]} for r in rows])

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


#budget limit set stuff
@app.route('/budget/set', methods=['POST'])
def set_budget():
    data = request.json
    user_id = data['user_id']
    monthly_limit = data['monthly_limit']
    cursor = get_cursor()
    cursor.execute("""
    INSERT INTO budgets (user_id, monthly_limit, month, year)
    VALUES (%s,%s,MONTH(CURDATE()),YEAR(CURDATE()))
    ON DUPLICATE KEY UPDATE monthly_limit = %s
    """,(user_id, monthly_limit, monthly_limit))
    mysql_conn.commit()
    cursor.close()
    return jsonify({"message":"Budget saved"})

@app.route('/budget/progress/<int:user_id>')
def budget_progress(user_id):
    cursor = get_cursor(dictionary=True)
    cursor.execute("""
    SELECT monthly_limit FROM budgets
    WHERE user_id=%s AND month=MONTH(CURDATE()) AND year=YEAR(CURDATE())
    """,(user_id,))
    budget = cursor.fetchone()
    if not budget:
        cursor.close()
        return jsonify({"monthly_limit":0,"total_expense":0,"progress":0})
    monthly_limit = float(budget['monthly_limit'])
    cursor.execute("""
    SELECT COALESCE(SUM(amount),0) as spent FROM expenses
    WHERE user_id=%s AND type='expense'
    AND MONTH(date)=MONTH(CURDATE()) AND YEAR(date)=YEAR(CURDATE())
    """,(user_id,))
    row = cursor.fetchone()
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
    """,(user_id,))
    budget = cursor.fetchone()
    if not budget:
        cursor.close()
        return jsonify({"alert":None})
    limit = float(budget['monthly_limit'])
    cursor.execute("""
    SELECT COALESCE(SUM(amount),0) as spent FROM expenses
    WHERE user_id=%s AND type='expense'
    AND MONTH(date)=MONTH(CURDATE()) AND YEAR(date)=YEAR(CURDATE())
    """,(user_id,))
    spent = float(cursor.fetchone()['spent'])
    percent = (spent / limit) * 100 if limit > 0 else 0
    alert = None
    if percent >= 90:
        alert = "Critical: 90% of your budget used"
    elif percent >= 75:
        alert = "Warning: 75% of your budget used"
    elif percent >= 50:
        alert = "Notice: 50% of your budget used"
    cursor.close()
    return jsonify({"percent":percent,"alert":alert})

@app.route('/notifications/<int:user_id>')
def get_notifications(user_id):
    cursor = get_cursor(dictionary=True)
    cursor.execute("""
    SELECT id, message, created_at FROM notifications
    WHERE user_id=%s ORDER BY created_at DESC
    """,(user_id,))
    notifications = cursor.fetchall()
    cursor.close()
    return jsonify(notifications)

@app.route('/wishlist', methods=['POST'])
def add_wishlist_item():
    data = request.json
    user_id = data.get("user_id", logged_in_user["id"])
    item_name = data.get("item_name")
    target_amount = data.get("target_amount")
    if not item_name or not target_amount or not user_id:
        return jsonify({"success": False, "message": "Invalid data"}), 400
    cur = get_cursor()
    cur.execute("""
        INSERT INTO wishlist (user_id, item_name, target_amount, total_saved)
        VALUES (%s,%s,%s, 0.0)
    """,(user_id, item_name, target_amount))
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
    """,(user_id,))
    items = cur.fetchall()
    for item in items:
        if isinstance(item.get('target_amount'), Decimal):
            item['target_amount'] = float(item['target_amount'])
        if isinstance(item.get('total_saved'), Decimal):
            item['total_saved'] = float(item['total_saved'])
        if isinstance(item.get('previous_saved'), Decimal):
            item['previous_saved'] = float(item['previous_saved'])
        elif item.get('previous_saved') is None:
            item['previous_saved'] = 0.0
    cur.close()
    return jsonify(items)

@app.route('/wishlist/save', methods=['POST'])
def save_to_wishlist():
    data = request.json
    user_id = data.get("user_id", logged_in_user["id"])
    wishlist_id = data.get("wishlist_id")
    amount = data.get("amount")
    if not wishlist_id or not amount or not user_id:
        return jsonify({"success": False, "message": "Invalid data"}), 400
    cur = get_cursor(dictionary=True)
    cur.execute("""
        INSERT INTO wishlist_savings (wishlist_id, user_id, amount, month, year)
        VALUES (%s,%s,%s,MONTH(CURDATE()),YEAR(CURDATE()))
    """,(wishlist_id, user_id, amount))
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
    data = request.json
    user_id = data.get("user_id", logged_in_user["id"])
    wishlist_id = data.get("wishlist_id")
    if not wishlist_id or not user_id:
        return jsonify({"success": False, "message": "Invalid data"}), 400
    cur = get_cursor()
    cur.execute("UPDATE wishlist SET previous_saved = 0.0 WHERE id=%s AND user_id=%s",
                (wishlist_id, user_id))
    mysql_conn.commit()
    cur.close()
    return jsonify({"success": True})

@app.route('/wishlist/<int:wishlist_id>', methods=['DELETE'])
def delete_wishlist_item(wishlist_id):
    data = request.json or {}
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
        SELECT COALESCE(SUM(total_saved),0) AS saved FROM wishlist WHERE user_id=%s
    """,(user_id,))
    saved = float(cur.fetchone()["saved"])
    spendable = balance - saved
    cur.close()
    return jsonify({"actual_balance": balance, "saved_amount": saved, "spendable_balance": spendable})


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
    budget_row = cur.fetchone()
    monthly_limit = float(budget_row['monthly_limit']) if budget_row else None

    cur.execute("""
        SELECT COALESCE(SUM(amount),0) AS spent FROM expenses
        WHERE user_id=%s AND type='expense'
        AND MONTH(date)=MONTH(CURDATE()) AND YEAR(date)=YEAR(CURDATE())
    """, (user_id,))
    month_spent = float(cur.fetchone()['spent'])

    cur.execute("""
        SELECT COALESCE(SUM(amount),0) AS income FROM expenses
        WHERE user_id=%s AND type='income'
        AND MONTH(date)=MONTH(CURDATE()) AND YEAR(date)=YEAR(CURDATE())
    """, (user_id,))
    month_income = float(cur.fetchone()['income'])

    cur.execute("""
        SELECT category AS name, SUM(amount) AS amount FROM expenses
        WHERE user_id=%s AND type='expense'
        AND MONTH(date)=MONTH(CURDATE()) AND YEAR(date)=YEAR(CURDATE())
        GROUP BY category ORDER BY amount DESC LIMIT 4
    """, (user_id,))
    categories = [{"name": r['name'], "amount": float(r['amount'])} for r in cur.fetchall()]

    from calendar import monthrange
    today = datetime.today()
    days_in_month = monthrange(today.year, today.month)[1]
    days_left = days_in_month - today.day

    budget_pct = None
    budget_remaining = None
    projected = None
    if monthly_limit and monthly_limit > 0:
        budget_pct = round((month_spent / monthly_limit) * 100, 1)
        budget_remaining = round(monthly_limit - month_spent, 2)
        daily_rate = month_spent / max(today.day, 1)
        projected = round(daily_rate * days_in_month, 2)

    savings_rate = 0
    if month_income > 0:
        savings_rate = round(((month_income - month_spent) / month_income) * 100, 1)

    if budget_pct is None:
        status = 'info'
        status_message = f"You've spent ₹{month_spent:.0f} this month. Set a budget to track progress."
    elif budget_pct >= 100:
        status = 'danger'
        status_message = f"Over budget! Spent ₹{month_spent:.0f} of ₹{monthly_limit:.0f}."
    elif budget_pct >= 75:
        status = 'warning'
        status_message = f"75% of budget used. ₹{budget_remaining:.0f} left for {days_left} days."
    elif budget_pct >= 50:
        status = 'warning'
        status_message = f"Halfway through budget. ₹{budget_remaining:.0f} remaining."
    else:
        status = 'success'
        status_message = f"On track! ₹{budget_remaining:.0f} left for {days_left} days."

    top_category = categories[0]['name'] if categories else None

    cur.close()
    return jsonify({
        "success": True,
        "budget": monthly_limit,
        "budget_pct": budget_pct,
        "budget_remaining": budget_remaining,
        "month_spent": month_spent,
        "month_income": month_income,
        "savings_rate": savings_rate,
        "categories": categories,
        "days_left": days_left,
        "projected": projected,
        "status": status,
        "status_message": status_message,
        "top_category": top_category,
    })


@app.route('/insights/smart', methods=['GET'])
def smart_insights():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"success": False, "message": "Missing user_id"}), 400

    cur = get_cursor(dictionary=True)
    insights = []

    cur.execute("""
        SELECT monthly_limit FROM budgets
        WHERE user_id=%s AND month=MONTH(CURDATE()) AND year=YEAR(CURDATE())
    """, (user_id,))
    budget_row = cur.fetchone()
    if budget_row:
        limit = float(budget_row['monthly_limit'])
        cur.execute("""
            SELECT COALESCE(SUM(amount),0) AS spent FROM expenses
            WHERE user_id=%s AND type='expense'
            AND MONTH(date)=MONTH(CURDATE()) AND YEAR(date)=YEAR(CURDATE())
        """, (user_id,))
        spent = float(cur.fetchone()['spent'])
        pct = (spent / limit * 100) if limit > 0 else 0
        if pct >= 90:
            insights.append({"type": "danger", "message": f"You've used {pct:.0f}% of your monthly budget!"})
        elif pct >= 70:
            insights.append({"type": "warning", "message": f"Budget {pct:.0f}% used. Slow down spending."})
        else:
            insights.append({"type": "success", "message": f"Budget on track — {pct:.0f}% used so far."})

    cur.execute("""
        SELECT category, SUM(amount) AS total FROM expenses
        WHERE user_id=%s AND type='expense'
        AND MONTH(date)=MONTH(CURDATE()) AND YEAR(date)=YEAR(CURDATE())
        GROUP BY category ORDER BY total DESC LIMIT 1
    """, (user_id,))
    top = cur.fetchone()
    if top:
        insights.append({"type": "info", "message": f"Top spend: {top['category']} (₹{float(top['total']):.0f} this month)"})

    cur.execute("""
        SELECT COALESCE(SUM(amount),0) AS prev FROM expenses
        WHERE user_id=%s AND type='expense'
        AND MONTH(date)=MONTH(CURDATE()-INTERVAL 1 MONTH)
        AND YEAR(date)=YEAR(CURDATE()-INTERVAL 1 MONTH)
    """, (user_id,))
    prev = float(cur.fetchone()['prev'])
    cur.execute("""
        SELECT COALESCE(SUM(amount),0) AS curr FROM expenses
        WHERE user_id=%s AND type='expense'
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
    tl = text.lower()
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
    tl = text.lower()
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
        SELECT category, SUM(amount) as total FROM expenses
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
        SELECT IFNULL(SUM(amount),0) FROM expenses
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
    today = date_type.today()
    start = str(today.replace(day=1))
    month_spent = _get_month_spent(uid, cur, start)
    top_cat, top_amt = _get_top_category(uid, cur, start)
    greeting = f"Hey {username}! I'm FinBot, your personal finance assistant.\n\n"
    greeting += f"Balance: Rs.{balance:.2f}\n"
    if month_spent > 0:
        greeting += f"Spent this month: Rs.{month_spent:.2f}\n"
        if top_cat:
            greeting += f"Top category: {top_cat} (Rs.{top_amt:.2f})\n"
    greeting += (
        "\nWhat can I help you with?\n\n"
        "  'I spent 300 on food'\n"
        "  'How much did I spend this week?'\n"
        "  'Show category wise spending'\n"
        "  'Am I over budget?'\n"
        "  'How can I save 50000 this month?'\n"
        "  'Show my wishlist progress'\n"
        "  'How much more for my iPhone goal?'\n"
        "  'Give me financial tips'"
    )
    return greeting


def handle_add_expense(text, uid, cur, conn):
    amount = extract_amount(text)
    category = extract_category(text) or "Other"
    t_type = extract_type(text)
    date_str, date_label = extract_date(text)
    if not amount:
        return "I couldn't find an amount.\n\nTry: 'I spent 300 on food' or 'Add 500 for transport'", False
    now = datetime.now()
    time_str = f"{now.hour:02d}:{now.minute:02d}:{now.second:02d}"
    cur.execute(
        "INSERT INTO expenses(amount, date, time, category, user_id, type, status, entry_method) "
        "VALUES (%s,%s,%s,%s,%s,%s,'confirmed','manual')",
        (amount, date_str, time_str, category, uid, t_type)
    )
    adj = amount if t_type == "income" else -amount
    cur.execute("UPDATE users SET balance = balance + %s WHERE id=%s", (adj, uid))
    conn.commit()
    sign = "+" if t_type == "income" else "-"
    verb = "Income" if t_type == "income" else "Expense"
    today = date_type.today()
    start = str(today.replace(day=1))
    cur.execute("""
        SELECT IFNULL(SUM(amount),0), COUNT(*) FROM expenses
        WHERE user_id=%s AND type='expense' AND status='confirmed'
        AND LOWER(category)=LOWER(%s) AND date >= %s
    """, (uid, category, start))
    cat_row = cur.fetchone()
    if isinstance(cat_row, dict):
        cat_total = float(list(cat_row.values())[0])
        cat_count = int(list(cat_row.values())[1])
    else:
        cat_total = float(cat_row[0])
        cat_count = int(cat_row[1])
    response = (
        f"✅ {verb} recorded!\n\n"
        f"  Amount:   Rs.{amount:.2f}\n"
        f"  Category: {category}\n"
        f"  Date:     {date_label}\n"
        f"  Balance:  {sign}Rs.{amount:.2f}\n"
    )
    if t_type == "expense" and cat_total > 0:
        response += f"\n💡 {category} this month: Rs.{cat_total:.2f} ({cat_count} transactions)."
        if category == "Food" and cat_total > 3000:
            response += "\n   Try cooking at home a few days to cut costs."
        elif category == "Transport" and cat_total > 3000:
            response += "\n   Consider public transport to reduce travel costs."
        elif category == "Shopping" and cat_total > 5000:
            response += "\n   Watch out — shopping is getting high this month!"
    return response, True


def handle_get_total_expense(text, uid, cur):
    tl = text.lower()
    if "so far" in tl or "overall" in tl or "all time" in tl:
        cur.execute("""
            SELECT IFNULL(SUM(CASE WHEN type='expense' THEN amount ELSE 0 END),0),
                   IFNULL(SUM(CASE WHEN type='income'  THEN amount ELSE 0 END),0),
                   COUNT(*) FROM expenses WHERE user_id=%s AND status='confirmed'
        """, (uid,))
        label = "All Time"
    else:
        start, end, label = date_range_from_text(text)
        cur.execute("""
            SELECT IFNULL(SUM(CASE WHEN type='expense' THEN amount ELSE 0 END),0),
                   IFNULL(SUM(CASE WHEN type='income'  THEN amount ELSE 0 END),0),
                   COUNT(*) FROM expenses
            WHERE user_id=%s AND status='confirmed' AND date BETWEEN %s AND %s
        """, (uid, start, end))
    row = cur.fetchone()
    if isinstance(row, dict):
        vals = list(row.values())
        spent, earned, count = float(vals[0]), float(vals[1]), int(vals[2])
    else:
        spent, earned, count = float(row[0]), float(row[1]), int(row[2])
    net = earned - spent
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
    category = extract_category(text) or "Other"
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
        SELECT IFNULL(SUM(amount),0) FROM expenses
        WHERE user_id=%s AND status='confirmed' AND type='expense' AND date BETWEEN %s AND %s
    """, (uid, start, end))
    row2 = cur.fetchone()
    total_all = float(list(row2.values())[0]) if isinstance(row2, dict) else float(row2[0])
    pct = (total / total_all * 100) if total_all > 0 else 0
    response = (
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
        WHERE user_id=%s
          AND month  = MONTH(CURDATE())
          AND year   = YEAR(CURDATE())
    """, (uid,))
    row = cur.fetchone()
    if row is None:
        return None
    return float(row['monthly_limit']) if isinstance(row, dict) else float(row[0])


def handle_check_budget(uid, cur):
    cur.execute("SELECT balance FROM users WHERE id=%s", (uid,))
    row = cur.fetchone()
    balance = float(row['balance']) if isinstance(row, dict) else float(row[0])

    limit = _get_budget_this_month(cur, uid)
    today = date_type.today()
    start = str(today.replace(day=1))
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
        excess = month_spent - limit
        alert_line = f"🚨 OVER BUDGET by Rs.{excess:.0f}!"
        emoji = "🚨"
        title = "Over Budget!"
    elif pct >= 90:
        alert_line = "🔴 Critical — 90%+ of budget used."
        emoji = "🔴"
        title = "Critical Alert"
    elif pct >= 75:
        alert_line = "🟠 Warning — 75%+ of budget used."
        emoji = "🟠"
        title = "Budget Warning"
    elif pct >= 50:
        alert_line = "🟡 Notice — 50%+ of budget used."
        emoji = "🟡"
        title = "Heads Up"
    else:
        alert_line = "✅ You're well within budget."
        emoji = "✅"
        title = "On Track"

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
        if pct >= 75:
            response += f" — cut this first."
        else:
            response += "."

    days_elapsed = max(1, today.day)
    if days_elapsed > 0 and month_spent > 0:
        projected = (month_spent / days_elapsed) * 30
        response += f"\n📊 Projected month-end spend: Rs.{projected:.0f}"
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

    today = date_type.today()
    start = str(today.replace(day=1))
    month_spent = _get_month_spent(uid, cur, start)
    pct = (month_spent / amount * 100) if amount > 0 else 0

    msg += f"\n\nThis month so far: Rs.{month_spent:.2f} ({pct:.1f}% used)."
    if pct >= 90:
        msg += "\n🔴 Critical — almost all of this budget is already used!"
    elif pct >= 75:
        msg += "\n🟠 Warning — 75%+ already used this month."
    elif pct >= 50:
        msg += "\n🟡 Halfway through budget already."
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
    lines = [f"Transactions — {label}:\n"]
    for r in rows:
        if isinstance(r, dict):
            sign = "+" if r['type'] == "income" else "-"
            lines.append(f"  {str(r['date'])}  {r['category']:<14}  {sign}Rs.{float(r['amount']):.2f}")
            total_exp = sum(float(r['amount']) for r in rows if r['type'] == "expense")
            total_inc = sum(float(r['amount']) for r in rows if r['type'] == "income")
        else:
            sign = "+" if r[2] == "income" else "-"
            lines.append(f"  {str(r[0])}  {r[1]:<14}  {sign}Rs.{float(r[3]):.2f}")
    if not isinstance(rows[0], dict):
        total_exp = sum(float(r[3]) for r in rows if r[2] == "expense")
        total_inc = sum(float(r[3]) for r in rows if r[2] == "income")
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
        lines = ["Spending analysis — this month:\n"]
        for i, r in enumerate(rows, 1):
            amt = float(r['total'])
            pct = (amt / total_all * 100) if total_all > 0 else 0
            lines.append(f"  {i}. {r['category']:<14} Rs.{amt:>8.2f}  {pct:.0f}%  ({r['cnt']} txns)")
        top_cat = rows[0]['category']
        top_pct = (float(rows[0]['total']) / total_all * 100) if total_all > 0 else 0
    else:
        total_all = float(sum(float(r[1]) for r in rows))
        lines = ["Spending analysis — this month:\n"]
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
    today = date_type.today()
    start_month = str(today.replace(day=1))
    cur.execute("""
        SELECT IFNULL(SUM(CASE WHEN type='income'  THEN amount ELSE 0 END), 0),
               IFNULL(SUM(CASE WHEN type='expense' THEN amount ELSE 0 END), 0)
        FROM expenses WHERE user_id=%s AND status='confirmed' AND date >= %s
    """, (uid, start_month))
    row = cur.fetchone()
    if isinstance(row, dict):
        vals = list(row.values()); earned, spent = float(vals[0]), float(vals[1])
    else:
        earned, spent = float(row[0]), float(row[1])
    saved = earned - spent
    rate = (saved / earned * 100) if earned > 0 else 0
    start_3m = str(today - timedelta(days=90))
    cur.execute("""
        SELECT IFNULL(SUM(CASE WHEN type='income'  THEN amount ELSE 0 END), 0),
               IFNULL(SUM(CASE WHEN type='expense' THEN amount ELSE 0 END), 0)
        FROM expenses WHERE user_id=%s AND status='confirmed' AND date >= %s
    """, (uid, start_3m))
    r3 = cur.fetchone()
    if isinstance(r3, dict):
        v3 = list(r3.values()); avg_save_3m = (float(v3[0]) - float(v3[1])) / 3
    else:
        avg_save_3m = (float(r3[0]) - float(r3[1])) / 3
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
        reply += "\n🌟 Excellent saving rate — above 30%! Keep it up!"
    else:
        reply += f"\n💡 Aim for 20-30% savings rate. You're at {rate:.1f}%."
    cur.execute("SELECT COUNT(*) FROM wishlist WHERE user_id=%s", (uid,))
    wl_row = cur.fetchone()
    wl_count = int(list(wl_row.values())[0]) if isinstance(wl_row, dict) else int(wl_row[0])
    if wl_count > 0 and avg_save_3m > 0:
        reply += f"\n\n📋 You have {wl_count} wishlist goal(s). Ask 'Show my wishlist' for progress."
    return reply


def handle_savings_goal(text, uid, cur):
    target_amount = extract_amount(text)
    if not target_amount:
        return handle_savings_info(uid, cur)

    today = date_type.today()
    start_month = str(today.replace(day=1))
    days_in_month = 30
    days_left = max(1, days_in_month - today.day)

    cur.execute("""
        SELECT
          IFNULL(SUM(CASE WHEN type='income'  THEN amount ELSE 0 END),0),
          IFNULL(SUM(CASE WHEN type='expense' THEN amount ELSE 0 END),0)
        FROM expenses
        WHERE user_id=%s AND status='confirmed' AND date >= %s
    """, (uid, start_month))
    row = cur.fetchone()
    if isinstance(row, dict):
        v = list(row.values()); income, spent = float(v[0]), float(v[1])
    else:
        income, spent = float(row[0]), float(row[1])
    current_savings = income - spent

    start_3m = str(today - timedelta(days=90))
    cur.execute("""
        SELECT
          IFNULL(SUM(CASE WHEN type='income'  THEN amount ELSE 0 END),0),
          IFNULL(SUM(CASE WHEN type='expense' THEN amount ELSE 0 END),0)
        FROM expenses WHERE user_id=%s AND status='confirmed' AND date >= %s
    """, (uid, start_3m))
    r3 = cur.fetchone()
    if isinstance(r3, dict):
        v3 = list(r3.values()); avg_monthly_savings = max(0.0, (float(v3[0]) - float(v3[1])) / 3)
    else:
        avg_monthly_savings = max(0.0, (float(r3[0]) - float(r3[1])) / 3)

    cur.execute("""
        SELECT category, SUM(amount) as total FROM expenses
        WHERE user_id=%s AND type='expense' AND status='confirmed' AND date >= %s
        GROUP BY category ORDER BY total DESC LIMIT 3
    """, (uid, start_month))
    top_cats = cur.fetchall()

    still_needed = max(0, target_amount - current_savings)
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
        reply.append(f"  • Save Rs.{still_needed/days_left:.0f}/day from now\n")

    if top_cats and still_needed > 0:
        reply.append("Where you can cut:")
        for cat_row in top_cats:
            if isinstance(cat_row, dict):
                cat, cat_amt = cat_row['category'], float(cat_row['total'])
            else:
                cat, cat_amt = cat_row[0], float(cat_row[1])
            reply.append(f"  • {cat} (Rs.{cat_amt:.0f}) — 20% cut saves Rs.{cat_amt*0.2:.0f}")
        if isinstance(top_cats[0], dict):
            total_saveable = sum(float(r['total']) * 0.2 for r in top_cats)
        else:
            total_saveable = sum(float(r[1]) * 0.2 for r in top_cats)
        reply.append("")
        if total_saveable >= still_needed:
            reply.append(f"Cutting 20% from top 3 categories saves Rs.{total_saveable:.0f} — enough!")
        else:
            reply.append(f"Cutting 20% from top categories saves Rs.{total_saveable:.0f}.")
            reply.append(f"Still Rs.{still_needed - total_saveable:.0f} short — delay non-essentials too.")

    return "\n".join(reply)


def handle_compare(uid, cur):
    today = date_type.today()
    start_this = str(today.replace(day=1))
    cur.execute("""
        SELECT IFNULL(SUM(CASE WHEN type='expense' THEN amount ELSE 0 END), 0),
               IFNULL(SUM(CASE WHEN type='income'  THEN amount ELSE 0 END), 0)
        FROM expenses WHERE user_id=%s AND status='confirmed' AND date >= %s
    """, (uid, start_this))
    this = cur.fetchone()
    if isinstance(this, dict):
        v = list(this.values()); this_exp, this_inc = float(v[0]), float(v[1])
    else:
        this_exp, this_inc = float(this[0]), float(this[1])
    last_end = today.replace(day=1) - timedelta(days=1)
    last_start = last_end.replace(day=1)
    cur.execute("""
        SELECT IFNULL(SUM(CASE WHEN type='expense' THEN amount ELSE 0 END), 0),
               IFNULL(SUM(CASE WHEN type='income'  THEN amount ELSE 0 END), 0)
        FROM expenses WHERE user_id=%s AND status='confirmed' AND date BETWEEN %s AND %s
    """, (uid, str(last_start), str(last_end)))
    last = cur.fetchone()
    if isinstance(last, dict):
        v = list(last.values()); last_exp, last_inc = float(v[0]), float(v[1])
    else:
        last_exp, last_inc = float(last[0]), float(last[1])
    diff = this_exp - last_exp
    pct = (diff / last_exp * 100) if last_exp > 0 else 0
    reply = (
        f"Month comparison:\n\n"
        f"                This Month   Last Month\n"
        f"  {'─'*36}\n"
        f"  Spent:   Rs.{this_exp:>10.2f}  Rs.{last_exp:>10.2f}\n"
        f"  Earned:  Rs.{this_inc:>10.2f}  Rs.{last_inc:>10.2f}\n"
        f"  Net:     Rs.{this_inc-this_exp:>+10.2f}  Rs.{last_inc-last_exp:>+10.2f}\n\n"
        f"  Change: Rs.{abs(diff):.2f}  ({abs(pct):.1f}% {'more' if diff > 0 else 'less'})\n"
    )
    if diff > 0:
        top_cat, top_amt = _get_top_category(uid, cur, start_this)
        reply += f"\n⚠️ Spending up by Rs.{diff:.0f}."
        if top_cat:
            reply += f" {top_cat} (Rs.{top_amt:.0f}) is your biggest category this month."
    else:
        reply += f"\n✅ Spending down by Rs.{abs(diff):.0f} vs last month. Great job!"
    return reply


def handle_wishlist_status(uid, cur):
    cur.execute("""
        SELECT id, item_name, target_amount, total_saved, COALESCE(previous_saved, 0)
        FROM wishlist WHERE user_id=%s ORDER BY item_name ASC
    """, (uid,))
    rows = cur.fetchall()
    if not rows:
        return "You have no wishlist goals yet.\n\nAdd goals from the Wishlist section of the app!"

    cur.execute("SELECT balance FROM users WHERE id=%s", (uid,))
    bal_row = cur.fetchone()
    actual_balance = float(bal_row['balance']) if isinstance(bal_row, dict) else float(bal_row[0])
    cur.execute("""
        SELECT COALESCE(SUM(total_saved),0) FROM wishlist WHERE user_id=%s
    """, (uid,))
    alloc_row = cur.fetchone()
    total_allocated = float(list(alloc_row.values())[0]) if isinstance(alloc_row, dict) else float(alloc_row[0])
    spendable = actual_balance - total_allocated

    today = date_type.today()
    start_3m = str(today - timedelta(days=90))
    cur.execute("""
        SELECT IFNULL(SUM(CASE WHEN type='income'  THEN amount ELSE 0 END), 0),
               IFNULL(SUM(CASE WHEN type='expense' THEN amount ELSE 0 END), 0)
        FROM expenses WHERE user_id=%s AND status='confirmed' AND date >= %s
    """, (uid, start_3m))
    r3 = cur.fetchone()
    if isinstance(r3, dict):
        v3 = list(r3.values()); monthly_savings = max(0.0, (float(v3[0]) - float(v3[1])) / 3)
    else:
        monthly_savings = max(0.0, (float(r3[0]) - float(r3[1])) / 3)

    lines = ["Your Wishlist Goals:\n"]
    total_needed = 0

    for r in rows:
        if isinstance(r, dict):
            wid, name, target, saved, prev_saved = r['id'], r['item_name'], float(r['target_amount']), float(r['total_saved']), float(r.get('previous_saved') or 0)
        else:
            wid, name, target, saved, prev_saved = r[0], r[1], float(r[2]), float(r[3]), float(r[4])
        remaining = max(0.0, target - saved)
        pct = min(100.0, (saved / target * 100)) if target > 0 else 0
        total_needed += remaining

        filled = min(int(pct / 10), 10)
        bar = "█" * filled + "░" * (10 - filled)

        if remaining <= 0:
            eta = "Done!"
        elif monthly_savings > 0:
            mo = remaining / monthly_savings
            eta = f"~{mo:.1f} months at current savings rate"
        else:
            eta = "N/A (no savings history)"

        icon = "✅" if saved >= target else "⏳"

        lines.append(f"  {icon} {name}")
        lines.append(f"     [{bar}]  {pct:.0f}%")
        lines.append(f"     Saved: Rs.{saved:.0f}  /  Target: Rs.{target:.0f}")
        if remaining > 0:
            lines.append(f"     Still need: Rs.{remaining:.0f}")
            lines.append(f"     ETA: {eta}")
        else:
            lines.append(f"     🎉 Goal reached!")
        if prev_saved > 0:
            lines.append(f"     ⚠️ Reset triggered (prev saved: Rs.{prev_saved:.0f}) — re-save when balance allows.")
        lines.append("")

    lines.append(f"  Total remaining across all goals: Rs.{total_needed:.0f}")
    lines.append(f"  Spendable balance (after allocations): Rs.{spendable:.0f}")
    if monthly_savings > 0 and total_needed > 0:
        all_done_in = total_needed / monthly_savings
        lines.append(f"  All goals complete in ~{all_done_in:.1f} months at current savings rate.")
    elif monthly_savings == 0 and total_needed > 0:
        lines.append(f"  ⚠️ No savings history — add income records to see timelines.")
    return "\n".join(lines)


def handle_wishlist_timeline(text, uid, cur):
    cur.execute("""
        SELECT id, item_name, target_amount, total_saved
        FROM wishlist WHERE user_id=%s ORDER BY item_name ASC
    """, (uid,))
    rows = cur.fetchall()
    if not rows:
        return "No wishlist goals found. Add some from the Wishlist section of the app!"

    tl = text.lower()

    matched = None
    for r in rows:
        name = r['item_name'] if isinstance(r, dict) else r[1]
        item_words = name.lower().split()
        if name.lower() in tl or any(w in tl for w in item_words if len(w) > 3):
            matched = r
            break

    today = date_type.today()
    start_3m = str(today - timedelta(days=90))
    cur.execute("""
        SELECT IFNULL(SUM(CASE WHEN type='income'  THEN amount ELSE 0 END), 0),
               IFNULL(SUM(CASE WHEN type='expense' THEN amount ELSE 0 END), 0)
        FROM expenses WHERE user_id=%s AND status='confirmed' AND date >= %s
    """, (uid, start_3m))
    r3 = cur.fetchone()
    if isinstance(r3, dict):
        v3 = list(r3.values()); monthly_savings = max(0.0, (float(v3[0]) - float(v3[1])) / 3.0)
    else:
        monthly_savings = max(0.0, (float(r3[0]) - float(r3[1])) / 3.0)

    cur.execute("""
        SELECT wishlist_id, COALESCE(SUM(amount),0) as this_month
        FROM wishlist_savings
        WHERE user_id=%s AND month=MONTH(CURDATE()) AND year=YEAR(CURDATE())
        GROUP BY wishlist_id
    """, (uid,))
    monthly_contrib_rows = cur.fetchall()
    monthly_contrib = {}
    for mc in monthly_contrib_rows:
        if isinstance(mc, dict):
            monthly_contrib[mc['wishlist_id']] = float(mc['this_month'])
        else:
            monthly_contrib[mc[0]] = float(mc[1])

    if matched:
        if isinstance(matched, dict):
            wid, name, target, saved = matched['id'], matched['item_name'], float(matched['target_amount']), float(matched['total_saved'])
        else:
            wid, name, target, saved = matched[0], matched[1], float(matched[2]), float(matched[3])
        remaining = max(0.0, target - saved)
        pct = min(100.0, (saved / target * 100)) if target > 0 else 0
        this_month_saved = monthly_contrib.get(wid, 0.0)

        filled = min(int(pct / 10), 10)
        bar = "█" * filled + "░" * (10 - filled)

        if remaining <= 0:
            return (
                f"🎉 Goal complete: {name}\n\n"
                f"  [{bar}]  100%\n"
                f"  Target: Rs.{target:.0f}  |  Saved: Rs.{saved:.0f}\n\n"
                f"You've reached this goal! Well done!"
            )

        reply = (
            f"Goal: {name}\n\n"
            f"  [{bar}]  {pct:.0f}%\n\n"
            f"  Target:           Rs.{target:.0f}\n"
            f"  Already saved:    Rs.{saved:.0f}\n"
            f"  Still needed:     Rs.{remaining:.0f}\n"
            f"  Saved this month: Rs.{this_month_saved:.0f}\n"
        )

        if monthly_savings <= 0:
            reply += (
                f"\n⚠️ No savings history yet.\n"
                f"Start saving regularly to see your timeline."
            )
        else:
            months_needed = remaining / monthly_savings
            reply += f"  ETA (at Rs.{monthly_savings:.0f}/mo): ~{months_needed:.1f} months\n"
            reply += f"\nTo finish in:"
            for target_months in [3, 6, 12]:
                needed_per_month = remaining / target_months
                reply += f"\n  • {target_months} months → save Rs.{needed_per_month:.0f}/month"

        return reply

    else:
        if monthly_savings <= 0:
            lines = ["Wishlist Timelines:\n",
                     "⚠️ No savings history found.\n",
                     "Add income to your tracker to calculate timelines.\n"]
        else:
            lines = [f"Wishlist Timelines (saving Rs.{monthly_savings:.0f}/mo avg):\n"]

        for r in rows:
            if isinstance(r, dict):
                wid, name, target, saved = r['id'], r['item_name'], float(r['target_amount']), float(r['total_saved'])
            else:
                wid, name, target, saved = r[0], r[1], float(r[2]), float(r[3])
            remaining = max(0.0, target - saved)
            pct = min(100.0, (saved / target * 100)) if target > 0 else 0
            filled = min(int(pct / 10), 10)
            bar = "█" * filled + "░" * (10 - filled)

            if remaining <= 0:
                lines.append(f"  ✅ {name} — Done!")
                continue

            this_month_saved = monthly_contrib.get(wid, 0.0)
            if monthly_savings > 0:
                mo = remaining / monthly_savings
                lines.append(f"  ⏳ {name}")
                lines.append(f"     [{bar}]  {pct:.0f}%  (Rs.{saved:.0f} / Rs.{target:.0f})")
                lines.append(f"     Still need: Rs.{remaining:.0f}  →  ~{mo:.1f} months")
                if this_month_saved > 0:
                    lines.append(f"     Saved this month: Rs.{this_month_saved:.0f}")
            else:
                lines.append(f"  ⏳ {name}  —  Rs.{saved:.0f} / Rs.{target:.0f}  (Rs.{remaining:.0f} more needed)")
            lines.append("")

        return "\n".join(lines)


def handle_wishlist_item_progress(text, uid, cur):
    cur.execute("""
        SELECT id, item_name, target_amount, total_saved, COALESCE(previous_saved, 0)
        FROM wishlist WHERE user_id=%s
    """, (uid,))
    rows = cur.fetchall()
    if not rows:
        return "You have no wishlist goals yet.\n\nAdd some from the Wishlist section!"

    tl = text.lower()

    matched = None
    best_score = 0
    for r in rows:
        name = r['item_name'] if isinstance(r, dict) else r[1]
        words = name.lower().split()
        score = sum(1 for w in words if len(w) > 3 and w in tl)
        if name.lower() in tl:
            score += 5
        if score > best_score:
            best_score = score
            matched = r

    today = date_type.today()
    start_3m = str(today - timedelta(days=90))
    cur.execute("""
        SELECT IFNULL(SUM(CASE WHEN type='income'  THEN amount ELSE 0 END), 0),
               IFNULL(SUM(CASE WHEN type='expense' THEN amount ELSE 0 END), 0)
        FROM expenses WHERE user_id=%s AND status='confirmed' AND date >= %s
    """, (uid, start_3m))
    r3 = cur.fetchone()
    if isinstance(r3, dict):
        v3 = list(r3.values()); monthly_savings = max(0.0, (float(v3[0]) - float(v3[1])) / 3.0)
    else:
        monthly_savings = max(0.0, (float(r3[0]) - float(r3[1])) / 3.0)

    if not matched or best_score == 0:
        return handle_wishlist_status(uid, cur)

    if isinstance(matched, dict):
        wid, name, target, saved, prev_saved = matched['id'], matched['item_name'], float(matched['target_amount']), float(matched['total_saved']), float(matched.get('previous_saved') or 0)
    else:
        wid, name, target, saved, prev_saved = matched[0], matched[1], float(matched[2]), float(matched[3]), float(matched[4])

    remaining  = max(0.0, target - saved)
    pct        = min(100.0, (saved / target * 100)) if target > 0 else 0
    filled     = min(int(pct / 10), 10)
    bar        = "█" * filled + "░" * (10 - filled)

    cur.execute("""
        SELECT COALESCE(SUM(amount),0)
        FROM wishlist_savings
        WHERE wishlist_id=%s AND user_id=%s
          AND month=MONTH(CURDATE()) AND year=YEAR(CURDATE())
    """, (wid, uid))
    tm_row = cur.fetchone()
    this_month = float(list(tm_row.values())[0]) if isinstance(tm_row, dict) else float(tm_row[0])

    cur.execute("""
        SELECT month, year, SUM(amount) as amt
        FROM wishlist_savings
        WHERE wishlist_id=%s AND user_id=%s
        GROUP BY year, month ORDER BY year DESC, month DESC LIMIT 6
    """, (wid, uid))
    history = cur.fetchall()

    if remaining <= 0:
        return (
            f"🎉 Goal complete: {name}\n\n"
            f"  [{bar}]  100%\n"
            f"  Target: Rs.{target:.0f}  |  Saved: Rs.{saved:.0f}\n\n"
            f"You\'ve fully funded this goal — well done!"
        )

    reply = (
        f"📊 Progress: {name}\n\n"
        f"  [{bar}]  {pct:.1f}%\n\n"
        f"  Target:           Rs.{target:.0f}\n"
        f"  Saved so far:     Rs.{saved:.0f}\n"
        f"  Still needed:     Rs.{remaining:.0f}\n"
        f"  Saved this month: Rs.{this_month:.0f}\n"
    )

    if prev_saved > 0:
        reply += f"  ⚠️ Reset pending: Rs.{prev_saved:.0f} previously saved (balance was insufficient)\n"

    if monthly_savings > 0:
        months_needed = remaining / monthly_savings
        reply += f"\n  ETA (at Rs.{monthly_savings:.0f}/mo): ~{months_needed:.1f} months\n"
        reply += f"\nTo complete faster:"
        for mo in [1, 3, 6]:
            reply += f"\n  • {mo} month{'s' if mo>1 else ''}  → save Rs.{remaining/mo:.0f}/month"
    else:
        reply += "\n⚠️ No income/savings history. Add income to see your timeline."

    if history:
        reply += "\n\nSavings history (last 6 months):"
        month_names = ["","Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
        for row in history:
            if isinstance(row, dict):
                mo, yr, amt = row['month'], row['year'], float(row['amt'])
            else:
                mo, yr, amt = row[0], row[1], float(row[2])
            reply += f"\n  • {month_names[mo]} {yr}: Rs.{amt:.0f}"

    return reply


def handle_financial_advice(uid, cur):
    today = date_type.today()
    start = str(today.replace(day=1))
    cur.execute("""
        SELECT IFNULL(SUM(CASE WHEN type='expense' THEN amount ELSE 0 END),0),
               IFNULL(SUM(CASE WHEN type='income'  THEN amount ELSE 0 END),0)
        FROM expenses WHERE user_id=%s AND status='confirmed' AND date >= %s
    """, (uid, start))
    row = cur.fetchone()
    if isinstance(row, dict):
        v = list(row.values()); spent, income = float(v[0]), float(v[1])
    else:
        spent, income = float(row[0]), float(row[1])
    savings = income - spent
    rate = (savings / income * 100) if income > 0 else 0
    top_cat, top_amt = _get_top_category(uid, cur, start)
    advice = ["Financial Advice:\n"]
    if income == 0:
        advice.append(
            "No income recorded this month.\n"
            "Add your salary/income to get personalised advice.\n\n"
            "General tips:\n"
            "  • Track every expense, even small ones\n"
            "  • Set a monthly budget\n"
            "  • Aim to save at least 20% of income"
        )
        return "\n".join(advice)
    if rate < 10:
        advice.append(f"⚠️ Savings rate: {rate:.1f}% — quite low.")
        advice.append("Cut down non-essential expenses this month.")
    elif rate < 20:
        advice.append(f"💡 Savings rate: {rate:.1f}% — moderate.")
        advice.append("Push towards 20% for better financial health.")
    else:
        advice.append(f"✅ Savings rate: {rate:.1f}% — strong! Keep it up.")
    if top_cat:
        advice.append(
            f"\nBiggest spend: {top_cat} (Rs.{top_amt:.0f})\n"
            f"Cutting it 20% saves Rs.{top_amt * 0.2:.0f} extra/month."
        )
    needs = income * 0.50
    wants = income * 0.30
    target_save = income * 0.20
    advice.append(
        f"\n50/30/20 rule for Rs.{income:.0f} income:\n"
        f"  50% Needs:   Rs.{needs:.0f}\n"
        f"  30% Wants:   Rs.{wants:.0f}\n"
        f"  20% Savings: Rs.{target_save:.0f}"
    )
    advice.append(
        "\nQuick wins:\n"
        "  • Cancel unused subscriptions\n"
        "  • Pack lunch 2-3 days/week\n"
        "  • Use UPI cashbacks & offers\n"
        "  • Review your top category monthly"
    )
    return "\n".join(advice)


def handle_purchase_advice(text, uid, cur):
    amount = extract_amount(text)
    if not amount:
        return "Tell me the price.\nExample: 'Can I afford a phone for 15000?'"

    cur.execute("SELECT balance FROM users WHERE id=%s", (uid,))
    bal_row = cur.fetchone()
    balance = float(bal_row['balance']) if isinstance(bal_row, dict) else float(bal_row[0])
    today = date_type.today()
    start = str(today.replace(day=1))
    month_spent = _get_month_spent(uid, cur, start)
    budget = _get_budget_this_month(cur, uid)
    remaining_budget = (budget - month_spent) if budget is not None else None

    cur.execute("SELECT COALESCE(SUM(total_saved),0) FROM wishlist WHERE user_id=%s", (uid,))
    wl_row = cur.fetchone()
    wl_allocated = float(list(wl_row.values())[0]) if isinstance(wl_row, dict) else float(wl_row[0])
    spendable = max(0.0, balance - wl_allocated)

    cur.execute("""
        SELECT IFNULL(SUM(CASE WHEN type='income' THEN amount ELSE 0 END),0),
               IFNULL(SUM(CASE WHEN type='expense' THEN amount ELSE 0 END),0)
        FROM expenses WHERE user_id=%s AND status='confirmed' AND date >= %s
    """, (uid, str(today - timedelta(days=90))))
    r = cur.fetchone()
    if isinstance(r, dict):
        v = list(r.values()); avg_monthly_savings = max(0.0, (float(v[0]) - float(v[1])) / 3)
    else:
        avg_monthly_savings = max(0.0, (float(r[0]) - float(r[1])) / 3)

    cur.execute("""
        SELECT id, item_name, target_amount, total_saved
        FROM wishlist WHERE user_id=%s
    """, (uid,))
    wl_rows = cur.fetchall()

    tl = text.lower()
    stopwords = {"should","would","could","will","want","need","buy","get","afford",
                 "purchase","spend","money","much","that","this","for","the","and"}
    query_words = [w for w in re.findall(r'[a-z]+', tl) if len(w) > 3 and w not in stopwords]

    best_item = None
    best_score = 0
    for row in wl_rows:
        if isinstance(row, dict):
            wid, name, target, saved = row['id'], row['item_name'], float(row['target_amount']), float(row['total_saved'])
        else:
            wid, name, target, saved = row[0], row[1], float(row[2]), float(row[3])
        name_lower = name.lower()
        score = sum(1 for w in query_words if w in name_lower)
        for nw in re.findall(r'[a-z]+', name_lower):
            if len(nw) > 3 and nw in tl:
                score += 2
        if score > best_score:
            best_score = score
            best_item = (wid, name, float(target), float(saved))

    if best_item and best_score >= 2:
        wid, goal_name, goal_target, goal_saved = best_item
        goal_remaining = max(0.0, goal_target - goal_saved)
        pct = min(100.0, (goal_saved / goal_target * 100)) if goal_target > 0 else 0
        filled = min(int(pct / 10), 10)
        bar = "█" * filled + "░" * (10 - filled)

        cur.execute("""
            SELECT COALESCE(SUM(amount),0) FROM wishlist_savings
            WHERE wishlist_id=%s AND user_id=%s
            AND MONTH(CURDATE())-month BETWEEN 0 AND 2
        """, (wid, uid))
        gs_row = cur.fetchone()
        goal_monthly_save = float(list(gs_row.values())[0]) if isinstance(gs_row, dict) else float(gs_row[0])
        goal_monthly_save = goal_monthly_save / 3 if avg_monthly_savings > 0 else 0
        if goal_monthly_save <= 0:
            goal_monthly_save = avg_monthly_savings

        eta_months = (goal_remaining / goal_monthly_save) if goal_monthly_save > 0 else None

        lines = []
        lines.append(f"Your {goal_name} goal is Rs.{goal_target:.0f} and you have saved Rs.{goal_saved:.0f}.")
        lines.append(f"  [{bar}]  {pct:.0f}% complete\n")

        if amount >= goal_target:
            lines.append(f"Buying a {goal_name.lower()} now for Rs.{amount:.0f} would use your entire goal budget.")
            lines.append(f"You would need to start saving from scratch (Rs.{goal_target:.0f} target).\n")
        elif amount > goal_saved:
            delay = (amount - goal_saved) / goal_monthly_save if goal_monthly_save > 0 else None
            lines.append(f"Buying a {goal_name.lower()} now for Rs.{amount:.0f} would delay your savings goal significantly.")
            if delay:
                lines.append(f"It would set you back by roughly {delay:.0f} months of saving.\n")
            else:
                lines.append("")
        else:
            lines.append(f"Rs.{amount:.0f} is within your current savings of Rs.{goal_saved:.0f} for this goal.")
            lines.append(f"But it would reduce your progress to {max(0, goal_saved - amount):.0f} / {goal_target:.0f}.\n")

        if goal_monthly_save > 0 and goal_remaining > 0:
            lines.append(f"If you continue saving Rs.{goal_monthly_save:.0f} per month,")
            if eta_months:
                lines.append(f"you can reach your goal in about {eta_months:.0f} months.\n")
        elif goal_remaining <= 0:
            lines.append("You have already reached your savings goal! 🎉\n")

        if amount > spendable:
            lines.append("Recommendation: You don't have enough spendable balance right now.")
            lines.append("Keep saving and revisit this in a few months.")
        elif pct >= 80:
            lines.append("Recommendation: You're very close to your goal — wait a little longer!")
        elif goal_monthly_save > 0 and eta_months and eta_months <= 6:
            lines.append(f"Recommendation: Continue saving for a few months instead.")
            lines.append(f"You'll hit your goal in ~{eta_months:.0f} months.")
        else:
            lines.append("Recommendation: Consider saving more aggressively to reach your goal sooner.")

        return "\n".join(lines)

    if amount > spendable:
        months_needed = ((amount - spendable) / avg_monthly_savings) if avg_monthly_savings > 0 else 0
        response = (
            f"⚠️ Not affordable right now.\n\n"
            f"  Item price:       Rs.{amount:.0f}\n"
            f"  Spendable bal.:   Rs.{spendable:.0f}\n"
            f"  (Balance Rs.{balance:.0f}, Rs.{wl_allocated:.0f} in wishlist goals)\n"
            f"  Shortfall:        Rs.{amount - spendable:.0f}\n\n"
        )
        if months_needed > 0:
            response += f"At your savings rate, you could afford it in ~{months_needed:.1f} months."
        else:
            response += "Start saving regularly to reach this goal."
        return response

    if remaining_budget is not None and amount > remaining_budget:
        return (
            f"⚠️ Exceeds remaining budget.\n\n"
            f"  Item price:       Rs.{amount:.0f}\n"
            f"  Budget remaining: Rs.{remaining_budget:.0f}\n\n"
            f"Consider waiting till next month when budget resets."
        )

    if amount > balance * 0.4:
        return (
            f"💡 Large purchase — think it through.\n\n"
            f"  Item price: Rs.{amount:.0f}\n"
            f"  Balance:    Rs.{balance:.0f}\n"
            f"  That's {(amount/balance*100):.0f}% of your balance.\n\n"
            f"Keep enough for emergencies (3-6 months expenses)."
        )

    return (
        f"✅ You can afford this!\n\n"
        f"  Item price:         Rs.{amount:.0f}\n"
        f"  Spendable balance:  Rs.{spendable:.0f}\n"
        f"  After purchase:     Rs.{spendable - amount:.0f}\n"
        f"  Month spent:        Rs.{month_spent:.0f}\n\n"
        f"Keep some emergency savings aside."
    )


def handle_time_based_query(text, uid, cur):
    summary = handle_get_total_expense(text, uid, cur)
    details = handle_show_expenses(text, uid, cur)
    if "No transactions" in details:
        return summary
    return f"{summary}\n\n{details}"


def handle_edit_expense(text, uid, cur, conn):
    tl = text.lower()
    if "delete" in tl or "remove" in tl:
        cat = extract_category(text)
        if cat and cat.lower() in tl:
            cur.execute("""
                SELECT id, amount, type, category FROM expenses
                WHERE user_id=%s AND LOWER(category)=LOWER(%s) AND status='confirmed'
                ORDER BY date DESC, time DESC LIMIT 1
            """, (uid, cat))
        else:
            cur.execute("""
                SELECT id, amount, type, category FROM expenses
                WHERE user_id=%s AND status='confirmed'
                ORDER BY date DESC, time DESC LIMIT 1
            """, (uid,))
        res = cur.fetchone()
        if not res:
            return "No matching expense found to delete."
        if isinstance(res, dict):
            exp_id, amount, t_type, real_cat = res['id'], float(res['amount']), res['type'], res['category']
        else:
            exp_id, amount, t_type, real_cat = res[0], float(res[1]), res[2], res[3]
        cur.execute("DELETE FROM expenses WHERE id=%s", (exp_id,))
        adj = amount if t_type == "expense" else -amount
        cur.execute("UPDATE users SET balance = balance + %s WHERE id=%s", (adj, uid))
        conn.commit()
        return f"✅ Deleted: {real_cat} expense of Rs.{amount:.2f}."
    elif "edit" in tl or "update" in tl:
        amount = extract_amount(text)
        cat = extract_category(text)
        if not amount:
            return "Specify the new amount.\nExample: 'Edit the food expense to 300'"
        if cat and cat.lower() in tl:
            cur.execute("""
                SELECT id, amount, type, category FROM expenses
                WHERE user_id=%s AND LOWER(category)=LOWER(%s) AND status='confirmed'
                ORDER BY date DESC, time DESC LIMIT 1
            """, (uid, cat))
        else:
            cur.execute("""
                SELECT id, amount, type, category FROM expenses
                WHERE user_id=%s AND status='confirmed'
                ORDER BY date DESC, time DESC LIMIT 1
            """, (uid,))
        res = cur.fetchone()
        if not res:
            return "No matching expense found to edit."
        if isinstance(res, dict):
            exp_id, old_amt, t_type, real_cat = res['id'], float(res['amount']), res['type'], res['category']
        else:
            exp_id, old_amt, t_type, real_cat = res[0], float(res[1]), res[2], res[3]
        undo = old_amt if t_type == "expense" else -old_amt
        cur.execute("UPDATE users SET balance = balance + %s WHERE id=%s", (undo, uid))
        apply = -amount if t_type == "expense" else amount
        cur.execute("UPDATE users SET balance = balance + %s WHERE id=%s", (apply, uid))
        cur.execute("UPDATE expenses SET amount=%s WHERE id=%s", (amount, exp_id))
        conn.commit()
        return f"✅ Updated {real_cat}: Rs.{old_amt:.2f} -> Rs.{amount:.2f}."
    return "Say 'delete last expense' or 'edit food expense to 300'."


@app.route('/ai/chat', methods=['POST'])
def ai_chat():
    data = request.json or {}
    uid = data.get('user_id') or (
        logged_in_user["id"]
        if 'logged_in_user' in globals() and logged_in_user
        else None
    )
    message = (data.get("message") or "").strip()

    if uid is None:
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    if not message:
        return jsonify({"success": False, "message": "Message is required"}), 400

    print(f"[FinBot] uid={uid} | {message}")

    ctx = _ctx(uid)
    intent = classify_intent(message, ctx)
    cur = get_cursor()
    response_text = ""

    try:
        cur.execute("SELECT balance, username FROM users WHERE id=%s", (uid,))
        user_row = cur.fetchone()
        if not user_row:
            return jsonify({"success": False, "message": "User not found"}), 404

        balance = float(user_row[0])
        username = user_row[1]

        if intent == "GREETING":
            response_text = handle_greeting(username, balance, uid, cur)

        elif intent == "ADD_EXPENSE":
            response_text, ok = handle_add_expense(message, uid, cur, mysql_conn)
            if ok:
                cat = extract_category(message) or "Other"
                _set_ctx(uid, "ADD_EXPENSE", {"category": cat})

        elif intent == "GET_TOTAL_EXPENSE":
            response_text = handle_get_total_expense(message, uid, cur)
            _set_ctx(uid, "GET_TOTAL_EXPENSE")

        elif intent == "TIME_BASED_QUERY":
            response_text = handle_time_based_query(message, uid, cur)
            _set_ctx(uid, "TIME_BASED_QUERY")

        elif intent == "CATEGORY_EXPENSE":
            response_text = handle_category_expense(message, uid, cur)
            _set_ctx(uid, "CATEGORY_EXPENSE", {"category": extract_category(message)})

        elif intent == "CHECK_BUDGET":
            response_text = handle_check_budget(uid, cur)
            _set_ctx(uid, "CHECK_BUDGET")

        elif intent == "SET_BUDGET":
            response_text = handle_set_budget(message, uid, cur, mysql_conn)
            _set_ctx(uid, "SET_BUDGET")

        elif intent == "SHOW_EXPENSES":
            response_text = handle_show_expenses(message, uid, cur)
            _set_ctx(uid, "SHOW_EXPENSES")

        elif intent == "SPENDING_ANALYSIS":
            response_text = handle_spending_analysis(uid, cur)
            _set_ctx(uid, "SPENDING_ANALYSIS")

        elif intent == "SAVINGS_INFO":
            response_text = handle_savings_info(uid, cur)
            _set_ctx(uid, "SAVINGS_INFO")

        elif intent == "SAVINGS_GOAL":
            response_text = handle_savings_goal(message, uid, cur)
            _set_ctx(uid, "SAVINGS_GOAL")

        elif intent == "COMPARE_EXPENSES":
            response_text = handle_compare(uid, cur)
            _set_ctx(uid, "COMPARE_EXPENSES")

        elif intent == "EDIT_EXPENSE":
            response_text = handle_edit_expense(message, uid, cur, mysql_conn)

        elif intent == "WISHLIST_STATUS":
            response_text = handle_wishlist_status(uid, cur)
            _set_ctx(uid, "WISHLIST_STATUS")

        elif intent == "WISHLIST_TIMELINE":
            response_text = handle_wishlist_timeline(message, uid, cur)
            _set_ctx(uid, "WISHLIST_TIMELINE")

        elif intent == "WISHLIST_ITEM_PROGRESS":
            response_text = handle_wishlist_item_progress(message, uid, cur)
            _set_ctx(uid, "WISHLIST_ITEM_PROGRESS")

        elif intent == "FINANCIAL_ADVICE":
            response_text = handle_financial_advice(uid, cur)
            _set_ctx(uid, "FINANCIAL_ADVICE")

        elif intent == "PURCHASE_ADVICE":
            response_text = handle_purchase_advice(message, uid, cur)

        elif intent == "FOLLOW_UP_QUERY":
            last_intent = ctx.get("last_intent", "")
            last_data = ctx.get("last_data", {})
            if "another" in message or (
                    "add" in message and any(c in message for c in CATEGORY_MAP)):
                cat_str = last_data.get("category", "") if isinstance(last_data, dict) else ""
                response_text, ok = handle_add_expense(
                    message + " " + cat_str, uid, cur, mysql_conn)
            elif "left now" in message or "budget" in message:
                response_text = handle_check_budget(uid, cur)
            elif "only show" in message or any(c in message for c in CATEGORY_MAP):
                response_text = handle_category_expense(message, uid, cur)
            elif last_intent in ("CATEGORY_EXPENSE", "SPENDING_ANALYSIS"):
                response_text = handle_category_expense(message, uid, cur)
            else:
                response_text = handle_time_based_query(message, uid, cur)

        else:
            response_text = (
                f"Hey {username}, I didn't quite get that.\n\n"
                "Here's what I can help with:\n\n"
                "  'I spent 200 on food'\n"
                "  'How much did I spend today?'\n"
                "  'How much this month?'\n"
                "  'Show category wise spending'\n"
                "  'Show my transport expenses'\n"
                "  'Set my budget to 10000'\n"
                "  'Am I over budget?'\n"
                "  'How can I save 80000 this month?'\n"
                "  'How much did I save this month?'\n"
                "  'Compare this month and last month'\n"
                "  'Show my wishlist progress'\n"
                "  'How much have I saved for iPhone?'\n"
                "  'How much more do I need for laptop?'\n"
                "  'When can I afford my iPhone?'\n"
                "  'Can I afford a phone for 15000?'\n"
                "  'Give me tips to save more'"
            )

    except Exception as e:
        print(f"[FinBot ERROR] intent={intent}  err={e}")
        import traceback; traceback.print_exc()
        response_text = "Sorry, something went wrong. Please try again."

    finally:
        cur.close()

    return jsonify({"success": True, "response": response_text, "intent": intent})


# ---------------- RUN SERVER ----------------
if __name__ == '__main__':
    print("Starting Flask server...")
    app.run(host="0.0.0.0", port=5000, debug=True)
