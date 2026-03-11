import mysql.connector
import os
from dotenv import load_dotenv

load_dotenv()

def add_column():
    try:
        connection = mysql.connector.connect(
            host=os.getenv("DB_HOST", "localhost"),
            user=os.getenv("DB_USER", "root"),
            password=os.getenv("DB_PASSWORD", ""),
            database=os.getenv("DB_NAME", "expense_tracker"),
            port=int(os.getenv("DB_PORT", 3306))
        )
        cursor = connection.cursor()
        
        # Check if column exists
        cursor.execute("""
            SELECT count(*)
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'budgets' AND COLUMN_NAME = 'last_alert_sent'
        """, (os.getenv("DB_NAME", "expense_tracker"),))
        
        if cursor.fetchone()[0] == 0:
            print("Adding last_alert_sent column...")
            cursor.execute("ALTER TABLE budgets ADD COLUMN last_alert_sent INT DEFAULT 0;")
            connection.commit()
            print("Column added successfully!")
        else:
            print("Column already exists.")
            
        cursor.close()
        connection.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    add_column()
