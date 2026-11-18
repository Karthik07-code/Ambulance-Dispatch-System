"""
Emergency Request Management Module
====================================
Handles registration, listing, editing, and state lifecycle of emergency calls.
"""

from typing import List, Optional, Dict, Any, Tuple
from database import get_db_connection


VALID_SEVERITIES = ("Critical", "High", "Medium", "Low")
VALID_STATUSES = ("Pending", "Assigned", "Completed", "Cancelled")


def get_all_emergencies(status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Retrieve emergency requests, optionally filtered by status.
    Ordered by created_at DESC (newest first).
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    if status_filter and status_filter in VALID_STATUSES:
        cursor.execute("""
            SELECT request_id, patient_name, emergency_location, severity, request_status, created_at
            FROM emergency_requests
            WHERE request_status = ?
            ORDER BY request_id DESC;
        """, (status_filter,))
    else:
        cursor.execute("""
            SELECT request_id, patient_name, emergency_location, severity, request_status, created_at
            FROM emergency_requests
            ORDER BY request_id DESC;
        """)

    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def get_emergency_by_id(request_id: int) -> Optional[Dict[str, Any]]:
    """Retrieve an emergency request by its ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT request_id, patient_name, emergency_location, severity, request_status, created_at
        FROM emergency_requests
        WHERE request_id = ?;
    """, (request_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def add_emergency(patient_name: str, emergency_location: str, severity: str) -> Tuple[bool, str, Optional[int]]:
    """
    Register a new emergency request into the system.
    Returns (success, message, new_request_id).
    """
    patient_name = patient_name.strip()
    emergency_location = emergency_location.strip()
    severity = severity.capitalize()

    if not patient_name:
        return False, "Patient name / label is required.", None
    if not emergency_location:
        return False, "Emergency location is required.", None
    if severity not in VALID_SEVERITIES:
        return False, f"Invalid severity '{severity}'. Must be one of: {', '.join(VALID_SEVERITIES)}", None

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO emergency_requests (patient_name, emergency_location, severity, request_status)
            VALUES (?, ?, ?, 'Pending');
        """, (patient_name, emergency_location, severity))
        conn.commit()
        req_id = cursor.lastrowid
        return True, f"Emergency request #{req_id} for '{patient_name}' registered successfully.", req_id
    except Exception as e:
        conn.rollback()
        return False, f"Database error: {str(e)}", None
    finally:
        conn.close()


def update_emergency(
    request_id: int,
    patient_name: str,
    emergency_location: str,
    severity: str,
    request_status: str
) -> Tuple[bool, str]:
    """Update an existing emergency request."""
    patient_name = patient_name.strip()
    emergency_location = emergency_location.strip()
    severity = severity.capitalize()

    if not patient_name:
        return False, "Patient name is required."
    if not emergency_location:
        return False, "Emergency location is required."
    if severity not in VALID_SEVERITIES:
        return False, f"Invalid severity: {severity}"
    if request_status not in VALID_STATUSES:
        return False, f"Invalid status: {request_status}"

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE emergency_requests
            SET patient_name = ?, emergency_location = ?, severity = ?, request_status = ?
            WHERE request_id = ?;
        """, (patient_name, emergency_location, severity, request_status, request_id))
        conn.commit()
        return True, f"Emergency request #{request_id} updated successfully."
    except Exception as e:
        conn.rollback()
        return False, f"Database error: {str(e)}"
    finally:
        conn.close()


def delete_emergency(request_id: int) -> Tuple[bool, str]:
    """Delete an emergency request if not actively assigned."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT request_status FROM emergency_requests WHERE request_id = ?;", (request_id,))
        row = cursor.fetchone()
        if not row:
            return False, "Emergency request not found."
        if row["request_status"] == "Assigned":
            return False, "Cannot delete an emergency request that is currently Assigned to an active dispatch."

        cursor.execute("DELETE FROM emergency_requests WHERE request_id = ?;", (request_id,))
        conn.commit()
        return True, f"Emergency request #{request_id} deleted successfully."
    except Exception as e:
        conn.rollback()
        return False, f"Database error: {str(e)}"
    finally:
        conn.close()


def get_pending_emergencies() -> List[Dict[str, Any]]:
    """Retrieve all pending emergency requests sorted by arrival (FIFO order)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT request_id, patient_name, emergency_location, severity, request_status, created_at
        FROM emergency_requests
        WHERE request_status = 'Pending'
        ORDER BY request_id ASC;
    """)
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

