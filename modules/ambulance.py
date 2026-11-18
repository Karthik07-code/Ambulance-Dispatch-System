"""
Ambulance Management Module
===========================
Handles CRUD operations and state transitions for ambulances.
"""

from typing import List, Optional, Dict, Any, Tuple
from database import get_db_connection


def get_all_ambulances() -> List[Dict[str, Any]]:
    """Retrieve all ambulance records ordered by ambulance number."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT ambulance_id, ambulance_number, current_location, status
        FROM ambulances
        ORDER BY ambulance_id ASC;
    """)
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def get_ambulance_by_id(ambulance_id: int) -> Optional[Dict[str, Any]]:
    """Retrieve a single ambulance record by its ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT ambulance_id, ambulance_number, current_location, status
        FROM ambulances
        WHERE ambulance_id = ?;
    """, (ambulance_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def add_ambulance(ambulance_number: str, current_location: str, status: str = "Available") -> Tuple[bool, str]:
    """
    Register a new ambulance into the system.
    Returns (success, message).
    """
    ambulance_number = ambulance_number.strip().upper()
    current_location = current_location.strip()

    if not ambulance_number:
        return False, "Ambulance number is required."
    if not current_location:
        return False, "Current location is required."
    if status not in ("Available", "Busy", "Maintenance"):
        return False, f"Invalid status: {status}"

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO ambulances (ambulance_number, current_location, status)
            VALUES (?, ?, ?);
        """, (ambulance_number, current_location, status))
        conn.commit()
        return True, f"Ambulance {ambulance_number} registered successfully."
    except Exception as e:
        conn.rollback()
        if "UNIQUE constraint failed" in str(e):
            return False, f"Ambulance number '{ambulance_number}' already exists."
        return False, f"Database error: {str(e)}"
    finally:
        conn.close()


def update_ambulance(ambulance_id: int, ambulance_number: str, current_location: str, status: str) -> Tuple[bool, str]:
    """
    Update details of an existing ambulance.
    """
    ambulance_number = ambulance_number.strip().upper()
    current_location = current_location.strip()

    if not ambulance_number:
        return False, "Ambulance number is required."
    if not current_location:
        return False, "Current location is required."
    if status not in ("Available", "Busy", "Maintenance"):
        return False, f"Invalid status: {status}"

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE ambulances
            SET ambulance_number = ?, current_location = ?, status = ?
            WHERE ambulance_id = ?;
        """, (ambulance_number, current_location, status, ambulance_id))
        conn.commit()
        return True, f"Ambulance {ambulance_number} updated successfully."
    except Exception as e:
        conn.rollback()
        if "UNIQUE constraint failed" in str(e):
            return False, f"Ambulance number '{ambulance_number}' already exists."
        return False, f"Database error: {str(e)}"
    finally:
        conn.close()


def delete_ambulance(ambulance_id: int) -> Tuple[bool, str]:
    """Delete an ambulance record."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Check if ambulance is currently busy
        cursor.execute("SELECT status, ambulance_number FROM ambulances WHERE ambulance_id = ?;", (ambulance_id,))
        row = cursor.fetchone()
        if not row:
            return False, "Ambulance not found."
        if row["status"] == "Busy":
            return False, f"Cannot delete ambulance {row['ambulance_number']} while it is Busy on a dispatch."

        cursor.execute("DELETE FROM ambulances WHERE ambulance_id = ?;", (ambulance_id,))
        conn.commit()
        return True, f"Ambulance {row['ambulance_number']} deleted successfully."
    except Exception as e:
        conn.rollback()
        return False, f"Database error: {str(e)}"
    finally:
        conn.close()


def get_available_ambulances() -> List[Dict[str, Any]]:
    """Retrieve all currently Available ambulances."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT ambulance_id, ambulance_number, current_location, status
        FROM ambulances
        WHERE status = 'Available'
        ORDER BY ambulance_id ASC;
    """)
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows
