"""
Dispatch Management & Decision Engine Module
============================================
Orchestrates the dispatch workflow:
1. Prioritises pending emergency calls using the Min-Heap EmergencyPriorityQueue.
2. Evaluates all Available ambulances via Dijkstra's shortest path algorithm.
3. Allocates the nearest reachable ambulance using an atomic database transaction.
4. Maintains audit history and lifecycle state transitions (Assigned -> Completed / Cancelled).
"""

from typing import Dict, Any, List, Optional, Tuple
from database import get_db_connection
from dsa.graph import ROAD_NETWORK
from dsa.priority_queue import EmergencyPriorityQueue
from dsa.dijkstra import dijkstra_shortest_path
from modules.emergency import get_pending_emergencies
from modules.ambulance import get_available_ambulances


def dispatch_next_emergency() -> Dict[str, Any]:
    """
    Automatic Dispatch Engine:
    1. Fetches all Pending emergency requests.
    2. Uses Min-Heap Priority Queue to select the highest-priority request (Critical > High > Med > Low, FIFO ties).
    3. Finds the closest Available ambulance using Dijkstra's algorithm.
    4. Commits atomic assignment to the database.
    """
    pending_list = get_pending_emergencies()
    if not pending_list:
        return {
            "success": False,
            "error_type": "NO_EMERGENCIES",
            "message": "No pending emergency requests to dispatch at this time."
        }

    # Populate Priority Queue
    pq = EmergencyPriorityQueue()
    for req in pending_list:
        pq.push(req)

    # Extract highest priority request
    top_emergency = pq.pop()
    return _execute_dispatch_for_emergency(top_emergency)


def dispatch_specific_emergency(request_id: int) -> Dict[str, Any]:
    """
    Dispatch an administrator-selected emergency request by its ID.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT request_id, patient_name, emergency_location, severity, request_status, created_at
        FROM emergency_requests
        WHERE request_id = ?;
    """, (request_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return {
            "success": False,
            "error_type": "NOT_FOUND",
            "message": f"Emergency request #{request_id} not found."
        }

    emergency = dict(row)
    if emergency["request_status"] != "Pending":
        return {
            "success": False,
            "error_type": "INVALID_STATE",
            "message": f"Emergency request #{request_id} is already '{emergency['request_status']}'."
        }

    return _execute_dispatch_for_emergency(emergency)


def _execute_dispatch_for_emergency(emergency: Dict[str, Any]) -> Dict[str, Any]:
    """
    Internal helper to run Dijkstra and assign an available ambulance to a given emergency.
    """
    available_ambulances = get_available_ambulances()
    if not available_ambulances:
        return {
            "success": False,
            "error_type": "NO_AMBULANCES",
            "message": f"No ambulances are currently Available to attend request #{emergency['request_id']} for {emergency['patient_name']}.",
            "emergency": emergency
        }

    incident_loc = emergency["emergency_location"]

    # Evaluate Dijkstra shortest path from each available ambulance to the incident location
    candidate_evaluations = []
    best_ambulance = None
    min_distance = float('inf')
    best_route: List[str] = []

    for amb in available_ambulances:
        amb_loc = amb["current_location"]
        dist, route = dijkstra_shortest_path(ROAD_NETWORK, amb_loc, incident_loc)

        eval_info = {
            "ambulance_id": amb["ambulance_id"],
            "ambulance_number": amb["ambulance_number"],
            "current_location": amb_loc,
            "distance_km": dist if dist != float('inf') else None,
            "route": route,
            "route_display": " -> ".join(route) if route else "No route found",
            "reachable": dist != float('inf')
        }
        candidate_evaluations.append(eval_info)

        if dist < min_distance:
            min_distance = dist
            best_ambulance = amb
            best_route = route

    # If no route exists to the incident location from any available ambulance
    if best_ambulance is None or min_distance == float('inf'):
        return {
            "success": False,
            "error_type": "NO_ROUTE",
            "message": f"No reachable route found between available ambulances and incident location '{incident_loc}'.",
            "emergency": emergency,
            "candidates_evaluated": candidate_evaluations
        }

    # Perform atomic assignment with database transaction
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Atomic lock check: verify ambulance is still Available and request is still Pending
        cursor.execute("SELECT status FROM ambulances WHERE ambulance_id = ?;", (best_ambulance["ambulance_id"],))
        amb_check = cursor.fetchone()
        cursor.execute("SELECT request_status FROM emergency_requests WHERE request_id = ?;", (emergency["request_id"],))
        req_check = cursor.fetchone()

        if not amb_check or amb_check["status"] != "Available":
            conn.rollback()
            return {
                "success": False,
                "error_type": "CONCURRENT_CONFLICT",
                "message": f"Ambulance {best_ambulance['ambulance_number']} is no longer available. Please retry dispatch."
            }

        if not req_check or req_check["request_status"] != "Pending":
            conn.rollback()
            return {
                "success": False,
                "error_type": "CONCURRENT_CONFLICT",
                "message": f"Emergency request #{emergency['request_id']} has already been assigned or completed."
            }

        route_string = " -> ".join(best_route)

        # 1. Update ambulance to Busy
        cursor.execute("""
            UPDATE ambulances
            SET status = 'Busy'
            WHERE ambulance_id = ?;
        """, (best_ambulance["ambulance_id"],))

        # 2. Update emergency request to Assigned
        cursor.execute("""
            UPDATE emergency_requests
            SET request_status = 'Assigned'
            WHERE request_id = ?;
        """, (emergency["request_id"],))

        # 3. Create dispatch history record
        cursor.execute("""
            INSERT INTO dispatch_history (request_id, ambulance_id, distance_km, route, dispatch_status)
            VALUES (?, ?, ?, ?, 'Assigned');
        """, (emergency["request_id"], best_ambulance["ambulance_id"], min_distance, route_string))

        dispatch_id = cursor.lastrowid
        conn.commit()

        return {
            "success": True,
            "dispatch_id": dispatch_id,
            "emergency": emergency,
            "ambulance": best_ambulance,
            "distance_km": min_distance,
            "route": best_route,
            "route_display": route_string,
            "candidates_evaluated": candidate_evaluations,
            "message": f"Ambulance {best_ambulance['ambulance_number']} assigned to {emergency['patient_name']} ({min_distance} km via {route_string})."
        }

    except Exception as e:
        conn.rollback()
        return {
            "success": False,
            "error_type": "DB_ERROR",
            "message": f"Dispatch transaction failed: {str(e)}"
        }
    finally:
        conn.close()


def complete_dispatch(dispatch_id: int) -> Tuple[bool, str]:
    """
    Mark an active dispatch as Completed.
    - Updates dispatch_status = 'Completed'
    - Updates emergency_requests = 'Completed'
    - Updates ambulance status = 'Available' and moves current_location to the incident location.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT d.dispatch_id, d.request_id, d.ambulance_id, d.dispatch_status,
                   e.emergency_location, a.ambulance_number
            FROM dispatch_history d
            JOIN emergency_requests e ON d.request_id = e.request_id
            JOIN ambulances a ON d.ambulance_id = a.ambulance_id
            WHERE d.dispatch_id = ?;
        """, (dispatch_id,))
        dispatch = cursor.fetchone()

        if not dispatch:
            return False, "Dispatch record not found."
        if dispatch["dispatch_status"] != "Assigned":
            return False, f"Dispatch #{dispatch_id} is already '{dispatch['dispatch_status']}'."

        # Update dispatch record
        cursor.execute("""
            UPDATE dispatch_history
            SET dispatch_status = 'Completed'
            WHERE dispatch_id = ?;
        """, (dispatch_id,))

        # Update emergency request
        cursor.execute("""
            UPDATE emergency_requests
            SET request_status = 'Completed'
            WHERE request_id = ?;
        """, (dispatch["request_id"],))

        # Update ambulance: make available and relocate to incident location
        cursor.execute("""
            UPDATE ambulances
            SET status = 'Available', current_location = ?
            WHERE ambulance_id = ?;
        """, (dispatch["emergency_location"], dispatch["ambulance_id"]))

        conn.commit()
        return True, f"Dispatch #{dispatch_id} marked as Completed. Ambulance {dispatch['ambulance_number']} is now Available at {dispatch['emergency_location']}."

    except Exception as e:
        conn.rollback()
        return False, f"Database error while completing dispatch: {str(e)}"
    finally:
        conn.close()


def cancel_dispatch(dispatch_id: int) -> Tuple[bool, str]:
    """
    Cancel an active dispatch.
    - Updates dispatch_status = 'Cancelled'
    - Returns emergency_requests to 'Pending' so it can be redispatched.
    - Reverts ambulance status = 'Available'.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT d.dispatch_id, d.request_id, d.ambulance_id, d.dispatch_status, a.ambulance_number
            FROM dispatch_history d
            JOIN ambulances a ON d.ambulance_id = a.ambulance_id
            WHERE d.dispatch_id = ?;
        """, (dispatch_id,))
        dispatch = cursor.fetchone()

        if not dispatch:
            return False, "Dispatch record not found."
        if dispatch["dispatch_status"] != "Assigned":
            return False, f"Cannot cancel dispatch in status '{dispatch['dispatch_status']}'."

        cursor.execute("UPDATE dispatch_history SET dispatch_status = 'Cancelled' WHERE dispatch_id = ?;", (dispatch_id,))
        cursor.execute("UPDATE emergency_requests SET request_status = 'Pending' WHERE request_id = ?;", (dispatch["request_id"],))
        cursor.execute("UPDATE ambulances SET status = 'Available' WHERE ambulance_id = ?;", (dispatch["ambulance_id"],))

        conn.commit()
        return True, f"Dispatch #{dispatch_id} cancelled. Request returned to Pending queue and Ambulance {dispatch['ambulance_number']} marked Available."
    except Exception as e:
        conn.rollback()
        return False, f"Database error: {str(e)}"
    finally:
        conn.close()


def get_all_dispatches() -> List[Dict[str, Any]]:
    """Retrieve all dispatch history records ordered by assignment time descending."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT d.dispatch_id, d.request_id, d.ambulance_id, d.distance_km, d.route,
               d.assigned_time, d.dispatch_status,
               e.patient_name, e.emergency_location, e.severity,
               a.ambulance_number
        FROM dispatch_history d
        JOIN emergency_requests e ON d.request_id = e.request_id
        JOIN ambulances a ON d.ambulance_id = a.ambulance_id
        ORDER BY d.dispatch_id DESC;
    """)
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def get_active_dispatches() -> List[Dict[str, Any]]:
    """Retrieve all currently active (Assigned) dispatches."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT d.dispatch_id, d.request_id, d.ambulance_id, d.distance_km, d.route,
               d.assigned_time, d.dispatch_status,
               e.patient_name, e.emergency_location, e.severity,
               a.ambulance_number, a.current_location AS ambulance_origin
        FROM dispatch_history d
        JOIN emergency_requests e ON d.request_id = e.request_id
        JOIN ambulances a ON d.ambulance_id = a.ambulance_id
        WHERE d.dispatch_status = 'Assigned'
        ORDER BY d.dispatch_id DESC;
    """)
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def get_dashboard_stats() -> Dict[str, Any]:
    """Calculate summary metrics for the Admin Dashboard."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Ambulances stats
    cursor.execute("SELECT COUNT(*) AS total FROM ambulances;")
    total_ambulances = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) AS count FROM ambulances WHERE status = 'Available';")
    available_ambulances = cursor.fetchone()["count"]

    cursor.execute("SELECT COUNT(*) AS count FROM ambulances WHERE status = 'Busy';")
    busy_ambulances = cursor.fetchone()["count"]

    cursor.execute("SELECT COUNT(*) AS count FROM ambulances WHERE status = 'Maintenance';")
    maintenance_ambulances = cursor.fetchone()["count"]

    # Emergencies stats
    cursor.execute("SELECT COUNT(*) AS total FROM emergency_requests;")
    total_emergencies = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) AS count FROM emergency_requests WHERE request_status = 'Pending';")
    pending_emergencies = cursor.fetchone()["count"]

    cursor.execute("SELECT COUNT(*) AS count FROM emergency_requests WHERE request_status = 'Assigned';")
    assigned_emergencies = cursor.fetchone()["count"]

    cursor.execute("SELECT COUNT(*) AS count FROM emergency_requests WHERE request_status = 'Completed';")
    completed_emergencies = cursor.fetchone()["count"]

    # Recent dispatches count
    cursor.execute("SELECT COUNT(*) AS total FROM dispatch_history;")
    total_dispatches = cursor.fetchone()["total"]

    conn.close()

    return {
        "total_ambulances": total_ambulances,
        "available_ambulances": available_ambulances,
        "busy_ambulances": busy_ambulances,
        "maintenance_ambulances": maintenance_ambulances,
        "total_emergencies": total_emergencies,
        "pending_emergencies": pending_emergencies,
        "assigned_emergencies": assigned_emergencies,
        "completed_emergencies": completed_emergencies,
        "total_dispatches": total_dispatches
    }

