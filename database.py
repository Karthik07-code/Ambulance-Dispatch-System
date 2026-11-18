"""
Database Layer for Emergency Ambulance Dispatch System
======================================================
Manages SQLite database initialization, table creation, seed data,
and database connections with foreign key enforcement.
"""

import os
import sqlite3
from typing import Generator

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ambulance.db")


def get_db_connection() -> sqlite3.Connection:
    """
    Establish and return a connection to the SQLite database.
    Enforces foreign keys and returns dictionary-like rows.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(seed: bool = True) -> None:
    """
    Create necessary database tables if they do not exist and seed initial demo data.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Ambulances table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ambulances (
            ambulance_id INTEGER PRIMARY KEY AUTOINCREMENT,
            ambulance_number TEXT UNIQUE NOT NULL,
            current_location TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('Available', 'Busy', 'Maintenance')) DEFAULT 'Available'
        );
    """)

    # 2. Emergency requests table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS emergency_requests (
            request_id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_name TEXT NOT NULL,
            emergency_location TEXT NOT NULL,
            severity TEXT NOT NULL CHECK(severity IN ('Critical', 'High', 'Medium', 'Low')),
            request_status TEXT NOT NULL CHECK(request_status IN ('Pending', 'Assigned', 'Completed', 'Cancelled')) DEFAULT 'Pending',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # 3. Dispatch history table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dispatch_history (
            dispatch_id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER NOT NULL,
            ambulance_id INTEGER NOT NULL,
            distance_km REAL NOT NULL,
            route TEXT,
            assigned_time DATETIME DEFAULT CURRENT_TIMESTAMP,
            dispatch_status TEXT NOT NULL CHECK(dispatch_status IN ('Assigned', 'Accepted', 'En Route', 'Arrived', 'Picked Up', 'Completed', 'Cancelled')) DEFAULT 'Assigned',
            FOREIGN KEY (request_id) REFERENCES emergency_requests (request_id) ON DELETE CASCADE,
            FOREIGN KEY (ambulance_id) REFERENCES ambulances (ambulance_id) ON DELETE CASCADE
        );
    """)

    # 4. Accounts table for Role-Based Authentication (Admin & Driver)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            account_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('Admin', 'Driver')),
            is_active INTEGER DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # 5. Drivers profile table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS drivers (
            driver_id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER UNIQUE NOT NULL,
            full_name TEXT NOT NULL,
            phone TEXT NOT NULL,
            ambulance_id INTEGER,
            availability_status TEXT NOT NULL CHECK(availability_status IN ('Available', 'On Duty', 'Busy', 'Off Duty')) DEFAULT 'Available',
            FOREIGN KEY (account_id) REFERENCES accounts (account_id) ON DELETE CASCADE,
            FOREIGN KEY (ambulance_id) REFERENCES ambulances (ambulance_id) ON DELETE SET NULL
        );
    """)

    # 6. Driver real-time locations telemetry table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS driver_locations (
            driver_id INTEGER PRIMARY KEY,
            dispatch_id INTEGER,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            heading REAL,
            accuracy_m REAL,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (driver_id) REFERENCES drivers (driver_id) ON DELETE CASCADE,
            FOREIGN KEY (dispatch_id) REFERENCES dispatch_history (dispatch_id) ON DELETE SET NULL
        );
    """)

    conn.commit()

    # 7. Non-destructive migrations for User & Driver Panel extensions
    run_migrations(conn)

    if seed:
        seed_initial_data(conn)

    conn.close()


def run_migrations(conn: sqlite3.Connection) -> None:
    """
    Non-destructive schema migrations. Safely adds columns required by the User Panel
    without dropping or altering existing tables or records.
    """
    cursor = conn.cursor()

    # 1. Inspect emergency_requests columns
    cursor.execute("PRAGMA table_info(emergency_requests);")
    existing_er_cols = {row["name"] for row in cursor.fetchall()}

    er_columns_to_add = [
        ("contact_phone", "TEXT"),
        ("emergency_note", "TEXT"),
        ("pickup_address", "TEXT"),
        ("latitude", "REAL"),
        ("longitude", "REAL"),
        ("tracking_token_hash", "TEXT"),
        ("tracking_token", "TEXT"),
        ("booking_reference", "TEXT"),
        ("user_live_lat", "REAL"),
        ("user_live_lng", "REAL"),
        ("user_live_updated_at", "DATETIME"),
        ("cancellation_reason", "TEXT"),
        ("tracking_substatus", "TEXT DEFAULT 'Waiting for Assignment'")
    ]

    for col_name, col_type in er_columns_to_add:
        if col_name not in existing_er_cols:
            cursor.execute(f"ALTER TABLE emergency_requests ADD COLUMN {col_name} {col_type};")

    # 2. Inspect ambulances columns
    cursor.execute("PRAGMA table_info(ambulances);")
    existing_amb_cols = {row["name"] for row in cursor.fetchall()}

    amb_columns_to_add = [
        ("latitude", "REAL"),
        ("longitude", "REAL"),
        ("driver_id", "INTEGER")
    ]

    for col_name, col_type in amb_columns_to_add:
        if col_name not in existing_amb_cols:
            cursor.execute(f"ALTER TABLE ambulances ADD COLUMN {col_name} {col_type};")

    # 3. Inspect dispatch_history columns
    cursor.execute("PRAGMA table_info(dispatch_history);")
    existing_dh_cols = {row["name"] for row in cursor.fetchall()}

    dh_columns_to_add = [
        ("driver_id", "INTEGER"),
        ("destination_hospital", "TEXT"),
        ("hospital_lat", "REAL"),
        ("hospital_lng", "REAL")
    ]

    for col_name, col_type in dh_columns_to_add:
        if col_name not in existing_dh_cols:
            cursor.execute(f"ALTER TABLE dispatch_history ADD COLUMN {col_name} {col_type};")

    # Sync coordinates for existing ambulances based on their current_location
    from dsa.graph import LOCATION_COORDINATES
    for loc, (lat, lng) in LOCATION_COORDINATES.items():
        cursor.execute("""
            UPDATE ambulances 
            SET latitude = ?, longitude = ? 
            WHERE current_location = ? AND (latitude IS NULL OR longitude IS NULL);
        """, (lat, lng, loc))

    conn.commit()



def seed_initial_data(conn: sqlite3.Connection) -> None:
    """
    Populate database with sample ambulances, drivers, accounts, and initial pending requests if empty.
    """
    from werkzeug.security import generate_password_hash
    from dsa.graph import LOCATION_COORDINATES

    cursor = conn.cursor()

    # Seed ambulances if table is empty
    cursor.execute("SELECT COUNT(*) AS count FROM ambulances;")
    if cursor.fetchone()["count"] == 0:
        sample_ambulances = [
            ("AMB-101", "Gandhipuram", "Available", 11.0168, 76.9558),
            ("AMB-102", "Peelamedu", "Available", 11.0267, 77.0123),
            ("AMB-103", "RS Puram", "Available", 11.0089, 76.9463),
            ("AMB-104", "Singanallur", "Available", 10.9972, 77.0253),
            ("AMB-105", "Railway Station", "Available", 10.9996, 76.9634),
        ]
        cursor.executemany(
            "INSERT INTO ambulances (ambulance_number, current_location, status, latitude, longitude) VALUES (?, ?, ?, ?, ?);",
            sample_ambulances
        )
        conn.commit()

    # Seed accounts (Admin and Drivers)
    cursor.execute("SELECT COUNT(*) AS count FROM accounts;")
    if cursor.fetchone()["count"] == 0:
        # Default Admin: admin / admin123
        admin_hash = generate_password_hash("admin123")
        cursor.execute("""
            INSERT INTO accounts (username, password_hash, role, is_active)
            VALUES ('admin', ?, 'Admin', 1);
        """, (admin_hash,))
        
        # Drivers: driver1..driver4 / driver123
        driver_pw_hash = generate_password_hash("driver123")
        driver_data = [
            ("driver1", "Ravi Chandran", "+91 98421 11001", 1),
            ("driver2", "Senthil Kumar", "+91 98421 11002", 2),
            ("driver3", "Murugan P.", "+91 98421 11003", 3),
            ("driver4", "Karthik Selvam", "+91 98421 11004", 4)
        ]

        for username, full_name, phone, amb_id in driver_data:
            cursor.execute("""
                INSERT INTO accounts (username, password_hash, role, is_active)
                VALUES (?, ?, 'Driver', 1);
            """, (username, driver_pw_hash))
            acc_id = cursor.lastrowid

            cursor.execute("""
                INSERT INTO drivers (account_id, full_name, phone, ambulance_id, availability_status)
                VALUES (?, ?, ?, ?, 'Available');
            """, (acc_id, full_name, phone, amb_id))
            drv_id = cursor.lastrowid

            # Link ambulance to driver
            cursor.execute("UPDATE ambulances SET driver_id = ? WHERE ambulance_id = ?;", (drv_id, amb_id))

            # Initial driver location
            amb_coords = [(11.0168, 76.9558), (11.0267, 77.0123), (11.0089, 76.9463), (10.9972, 77.0253)][amb_id - 1]
            cursor.execute("""
                INSERT INTO driver_locations (driver_id, latitude, longitude)
                VALUES (?, ?, ?);
            """, (drv_id, amb_coords[0], amb_coords[1]))

        conn.commit()

    # Seed demo emergency requests if table is empty
    cursor.execute("SELECT COUNT(*) AS count FROM emergency_requests;")
    if cursor.fetchone()["count"] == 0:
        sample_emergencies = [
            ("Ramesh Kumar", "Peelamedu", "Medium", "Pending"),
            ("Kavitha Sundaram", "Singanallur", "Critical", "Pending"),
            ("Anand Verma", "RS Puram", "High", "Pending"),
            ("Priya Natarajan", "Gandhipuram", "Low", "Pending"),
        ]
        cursor.executemany(
            "INSERT INTO emergency_requests (patient_name, emergency_location, severity, request_status) VALUES (?, ?, ?, ?);",
            sample_emergencies
        )
        conn.commit()


if __name__ == "__main__":
    init_db()
    print("Database initialized successfully at:", DB_PATH)

