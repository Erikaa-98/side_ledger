from database import get_connection
from datetime import datetime, timedelta
from app import send_reminder_email

def main():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id, email FROM users")
    users = c.fetchall()
    today = datetime.now().date()
    reminder_days = today + timedelta(days=7)

    for user_id, email in users:
        c.execute("SELECT name, follow_up_date FROM institutions WHERE follow_up_date BETWEEN ? AND ? AND user_id=? ORDER BY follow_up_date ASC",
                  (today.strftime("%Y-%m-%d"), reminder_days.strftime("%Y-%m-%d"), user_id))
        reminders = c.fetchall()
        if reminders:
            send_reminder_email(email, reminders)

    conn.close()

if __name__ == "__main__":
    main()