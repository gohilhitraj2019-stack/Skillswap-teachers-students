import sqlite3
import os
import sys

def migrate_database(db_path='instance/skillswap.db'):
    if not os.path.exists(db_path):
        print(f"Database {db_path} does not exist. Skipping.")
        return

    print(f"Starting migration on {db_path}...")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # 1. Inspect and alter teacher_profiles
    cur.execute("PRAGMA table_info(teacher_profiles);")
    tp_cols = [r[1] for r in cur.fetchall()]
    if 'free_sessions_offered' not in tp_cols:
        print("Adding free_sessions_offered to teacher_profiles...")
        cur.execute("ALTER TABLE teacher_profiles ADD COLUMN free_sessions_offered INTEGER DEFAULT 3;")
    if 'free_sessions_completed' not in tp_cols:
        print("Adding free_sessions_completed to teacher_profiles...")
        cur.execute("ALTER TABLE teacher_profiles ADD COLUMN free_sessions_completed INTEGER DEFAULT 0;")

    # Convert teacher hourly_rate if in credits (e.g. <= 100)
    cur.execute("UPDATE teacher_profiles SET hourly_rate = hourly_rate * 10 WHERE hourly_rate > 0 AND hourly_rate <= 100;")
    cur.execute("UPDATE teacher_profiles SET free_sessions_offered = 3 WHERE free_sessions_offered IS NULL;")
    cur.execute("UPDATE teacher_profiles SET free_sessions_completed = 0 WHERE free_sessions_completed IS NULL;")

    # 2. Inspect and alter bookings
    cur.execute("PRAGMA table_info(bookings);")
    b_cols = [r[1] for r in cur.fetchall()]
    if 'amount_inr' not in b_cols:
        print("Adding amount_inr to bookings...")
        cur.execute("ALTER TABLE bookings ADD COLUMN amount_inr NUMERIC(12, 2) DEFAULT 0.0;")
    if 'is_free_session' not in b_cols:
        print("Adding is_free_session to bookings...")
        cur.execute("ALTER TABLE bookings ADD COLUMN is_free_session BOOLEAN DEFAULT 0;")
    if 'free_session_deducted' not in b_cols:
        print("Adding free_session_deducted to bookings...")
        cur.execute("ALTER TABLE bookings ADD COLUMN free_session_deducted BOOLEAN DEFAULT 0;")

    # Migrate booking financial amounts (multiply old credit amounts by 10 to get INR)
    cur.execute("""
        UPDATE bookings 
        SET amount_inr = credits_amount * 10.0,
            platform_commission_amount = platform_commission_amount * 10.0,
            teacher_earnings_amount = teacher_earnings_amount * 10.0,
            is_free_session = 0,
            free_session_deducted = 0
        WHERE amount_inr IS NULL OR amount_inr = 0.0;
    """)

    # 3. Check if wallets already converted (using a flag or examining balances)
    # Check platform_settings credit_to_inr_rate: if it's 10.0, it hasn't been migrated yet!
    cur.execute("SELECT credit_to_inr_rate FROM platform_settings LIMIT 1;")
    row = cur.fetchone()
    already_migrated = False
    if row and float(row[0]) == 1.0:
        already_migrated = True

    if not already_migrated:
        print("Migrating wallet balances with 10.0 credit-to-INR ratio...")
        cur.execute("""
            UPDATE wallets 
            SET available_balance = available_balance * 10,
                held_balance = held_balance * 10,
                earned_balance = earned_balance * 10,
                withdrawn_balance = withdrawn_balance * 10,
                total_purchased = total_purchased * 10;
        """)

        print("Migrating credit_transactions...")
        cur.execute("""
            UPDATE credit_transactions
            SET amount = amount * 10,
                balance_after = balance_after * 10;
        """)

        print("Migrating credit_packages...")
        cur.execute("""
            UPDATE credit_packages
            SET credits = credits * 10;
        """)

        print("Updating platform_settings...")
        cur.execute("""
            UPDATE platform_settings
            SET free_trial_credits = 500,
                credit_to_inr_rate = 1.0;
        """)
    else:
        print("Platform settings indicate database already migrated to INR.")

    conn.commit()
    conn.close()
    print("Migration finished successfully.")

if __name__ == '__main__':
    migrate_database()
