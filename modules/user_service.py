"""
User Panel Service Module
=========================
Encapsulates all public booking, secure token management, live tracking data,
and ETA calculation logic.
Keeps user-facing service code organized separately from Admin code.
"""

import hashlib
import os
import re
import secrets
from datetime import datetime
from typing import Any, Dict, Optional, Tuple
import requests

from database import get_db_connection
from dsa.graph import ROAD_NETWORK, LOCATION_COORDINATES, get_nearest_location
from dsa.dijkstra import dijkstra_shortest_path
from modules import dispatch as dispatch_mod


def hash_token(token: str) -> str:
    """Computes SHA-256 hash of a tracking token for secure database storage and lookup."""
    return hashlib.sha256(token.strip().encode('utf-8')).hexdigest()


def generate_booking_reference() -> str:
    """Generates a human-friendly booking reference code, e.g. BK-2026-7842."""
    random_digits = secrets.randbelow(9000) + 1000
    year = datetime.now().year
    return f"BK-{year}-{random_digits}"


def validate_phone_number(phone: str) -> bool:
    """Validates phone number format (7 to 15 digits, optional + prefix)."""
    cleaned = re.sub(r"[\s\-\(\)]", "", phone)
    return bool(re.match(r"^\+?[0-9]{7,15}$", cleaned))


def create_user_booking(
    patient_name: str,
    contact_phone: str,
    severity: str,
    pickup_address: str,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    emergency_note: Optional[str] = None
) -> Tuple[bool, str, Optional[str], Optional[str], Optional[int]]:
    """
    Validates and registers an emergency ambulance request from the public User Panel.
    Returns: (success, message, raw_tracking_token, booking_reference, request_id)
    """
    patient_name = patient_name.strip()
    contact_phone = contact_phone.strip()
    severity = severity.capitalize()
    pickup_address = pickup_address.strip()
    emergency_note = (emergency_note or "").strip()[:500]

    # Server-side validation
    if not patient_name or len(patient_name) < 2:
        return False, "Please provide a valid patient name or caller label.", None, None, None
    if not contact_phone or not validate_phone_number(contact_phone):
        return False, "Please provide a valid contact phone number.", None, None, None
    if severity not in ("Critical", "High", "Medium", "Low"):
        return False, "Please select a valid emergency severity level.", None, None, None
    if not pickup_address:
        return False, "Please provide or select a pickup location.", None, None, None

    # Determine or approximate nearest predefined road network node
    # If valid lat/lng are provided, find closest predefined road hub
    if latitude is not None and longitude is not None:
        try:
            latitude = float(latitude)
            longitude = float(longitude)
            if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
                return False, "Invalid GPS coordinates.", None, None, None
            nearest_hub = get_nearest_location(latitude, longitude)
        except ValueError:
            return False, "Coordinates must be valid numbers.", None, None, None
    else:
        # Fallback: check if pickup_address matches or contains any known node
        nearest_hub = "Gandhipuram"
        for loc in LOCATION_COORDINATES:
            if loc.lower() in pickup_address.lower():
                nearest_hub = loc
                break
        latitude, longitude = LOCATION_COORDINATES.get(nearest_hub, (11.0168, 76.9558))

    # Generate unguessable, cryptographically random tracking token & hash
    raw_token = secrets.token_urlsafe(32)
    token_hash = hash_token(raw_token)
    booking_ref = generate_booking_reference()

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO emergency_requests (
                patient_name, contact_phone, emergency_location, pickup_address,
                latitude, longitude, severity, emergency_note,
                request_status, tracking_token_hash, tracking_token,
                booking_reference, tracking_substatus, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Pending', ?, ?, ?, 'Waiting for Assignment', CURRENT_TIMESTAMP);
        """, (
            patient_name, contact_phone, nearest_hub, pickup_address,
            latitude, longitude, severity, emergency_note,
            token_hash, raw_token, booking_ref
        ))
        conn.commit()
        request_id = cursor.lastrowid

        # Invoke existing dispatch workflow in the background/attempt immediate assignment
        # If an ambulance is available, it will be assigned right away
        dispatch_result = dispatch_mod.dispatch_specific_emergency(request_id)
        if dispatch_result.get("success"):
            cursor.execute("""
                UPDATE emergency_requests 
                SET tracking_substatus = 'Ambulance Assigned & En Route'
                WHERE request_id = ?;
            """, (request_id,))
            conn.commit()

        return True, "Emergency request registered successfully.", raw_token, booking_ref, request_id

    except Exception as e:
        conn.rollback()
        return False, f"Database error creating booking: {str(e)}", None, None, None
    finally:
        conn.close()


def get_booking_by_token(raw_token: str) -> Optional[Dict[str, Any]]:
    """
    Retrieves public tracking details for a booking using its unguessable token.
    Ensures that ONLY safe, non-sensitive public tracking data is returned.
    """
    if not raw_token or len(raw_token) < 16:
        return None

    token_hash = hash_token(raw_token)

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            e.request_id, e.patient_name, e.emergency_location, e.pickup_address,
            e.latitude, e.longitude, e.severity, e.request_status,
            e.booking_reference, e.emergency_note, e.tracking_substatus,
            e.user_live_lat, e.user_live_lng, e.user_live_updated_at,
            e.created_at, e.cancellation_reason,
            d.dispatch_id, d.ambulance_id, d.distance_km, d.route, d.assigned_time, d.dispatch_status,
            a.ambulance_number, a.current_location AS ambulance_location,
            a.latitude AS ambulance_lat, a.longitude AS ambulance_lng
        FROM emergency_requests e
        LEFT JOIN dispatch_history d ON e.request_id = d.request_id AND d.dispatch_status != 'Cancelled'
        LEFT JOIN ambulances a ON d.ambulance_id = a.ambulance_id
        WHERE e.tracking_token_hash = ?;
    """, (token_hash,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    data = dict(row)

    # If ambulance coordinates are not explicitly set, fetch from predefined coordinates
    if data.get("ambulance_location") and (data.get("ambulance_lat") is None or data.get("ambulance_lng") is None):
        coords = LOCATION_COORDINATES.get(data["ambulance_location"])
        if coords:
            data["ambulance_lat"] = coords[0]
            data["ambulance_lng"] = coords[1]

    # Calculate ETA and route details if ambulance is assigned
    eta_info = calculate_eta(data)
    data["eta_text"] = eta_info["eta_text"]
    data["eta_minutes"] = eta_info["eta_minutes"]
    data["eta_source"] = eta_info["eta_source"]
    data["route_points"] = eta_info["route_points"]

    return data


def calculate_eta(booking_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculates road-based ETA and route coordinates.
    Uses Google Maps Routes API if GOOGLE_MAPS_API_KEY is configured.
    Otherwise falls back to Dijkstra road graph calculation with clear labeling.
    """
    # If not assigned, no ETA
    if booking_data.get("request_status") != "Assigned" or not booking_data.get("ambulance_number"):
        return {
            "eta_text": "Waiting for assignment",
            "eta_minutes": None,
            "eta_source": "none",
            "route_points": []
        }

    amb_lat = booking_data.get("ambulance_lat")
    amb_lng = booking_data.get("ambulance_lng")
    pickup_lat = booking_data.get("latitude")
    pickup_lng = booking_data.get("longitude")
    distance_km = booking_data.get("distance_km") or 0.0

    api_key = os.environ.get("GOOGLE_MAPS_API_KEY", "").strip()

    # If Google Maps API key is available, attempt real Routes API request
    if api_key and api_key != "YOUR_KEY_HERE" and amb_lat and amb_lng and pickup_lat and pickup_lng:
        try:
            routes_url = "https://routes.googleapis.com/directions/v2:computeRoutes"
            headers = {
                "Content-Type": "application/json",
                "X-Goog-Api-Key": api_key,
                "X-Goog-FieldMask": "routes.duration,routes.distanceMeters,routes.polyline.encodedPolyline"
            }
            payload = {
                "origin": {"location": {"latLng": {"latitude": amb_lat, "longitude": amb_lng}}},
                "destination": {"location": {"latLng": {"latitude": pickup_lat, "longitude": pickup_lng}}},
                "travelMode": "DRIVE",
                "routingPreference": "TRAFFIC_AWARE"
            }
            resp = requests.post(routes_url, json=payload, headers=headers, timeout=5)
            if resp.status_code == 200:
                resp_data = resp.json()
                if "routes" in resp_data and len(resp_data["routes"]) > 0:
                    route_item = resp_data["routes"][0]
                    duration_str = route_item.get("duration", "0s")
                    seconds = int(duration_str.rstrip("s")) if duration_str.endswith("s") else 0
                    mins = max(1, round(seconds / 60))
                    return {
                        "eta_text": f"About {mins} mins",
                        "eta_minutes": mins,
                        "eta_source": "google_routes_traffic",
                        "polyline": route_item.get("polyline", {}).get("encodedPolyline"),
                        "route_points": []
                    }
        except Exception:
            # Silently fall back to Dijkstra demo routing
            pass

    # Algorithmic Demo Fallback: Based on Dijkstra shortest road distance
    # Assume emergency vehicle average city speed of ~35 km/h + 2 min dispatch reaction time
    route_names = []
    if booking_data.get("route"):
        route_names = [part.strip() for part in booking_data["route"].split("->")]

    route_points = []
    for loc_name in route_names:
        if loc_name in LOCATION_COORDINATES:
            lat, lng = LOCATION_COORDINATES[loc_name]
            route_points.append({"lat": lat, "lng": lng, "name": loc_name})

    # Add exact pickup coordinate at the end if different from last hub
    if pickup_lat and pickup_lng:
        route_points.append({"lat": pickup_lat, "lng": pickup_lng, "name": "Pickup Point"})

    speed_kmh = 35.0
    travel_mins = (distance_km / speed_kmh) * 60.0
    total_mins = max(2, round(travel_mins + 2))

    return {
        "eta_text": f"About {total_mins} mins (Demo Calculation)",
        "eta_minutes": total_mins,
        "eta_source": "dsa_dijkstra_simulation",
        "route_points": route_points
    }


def cancel_user_booking(raw_token: str, reason: str = "") -> Tuple[bool, str]:
    """
    Handles cancellation requested by the user from the tracking page.
    Follows state transition rules:
    - Pending: Cancelled immediately.
    - Assigned: Handled gracefully and releases the ambulance or creates a cancellation request.
    - Completed / Cancelled: Rejects invalid transitions.
    """
    token_hash = hash_token(raw_token)
    reason = (reason or "Requested by user via tracking portal").strip()[:300]

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT request_id, request_status, patient_name 
            FROM emergency_requests 
            WHERE tracking_token_hash = ?;
        """, (token_hash,))
        booking = cursor.fetchone()

        if not booking:
            return False, "Booking not found or invalid token."

        req_id = booking["request_id"]
        status = booking["request_status"]

        if status == "Cancelled":
            return False, "This booking has already been cancelled."
        if status == "Completed":
            return False, "Cannot cancel a booking that has already been completed."

        if status == "Pending":
            cursor.execute("""
                UPDATE emergency_requests
                SET request_status = 'Cancelled', cancellation_reason = ?, tracking_substatus = 'Cancelled by Requester'
                WHERE request_id = ?;
            """, (reason, req_id))
            conn.commit()
            return True, "Your emergency request has been successfully cancelled."

        if status == "Assigned":
            # Find associated active dispatch and ambulance
            cursor.execute("""
                SELECT d.dispatch_id, d.ambulance_id, a.ambulance_number
                FROM dispatch_history d
                JOIN ambulances a ON d.ambulance_id = a.ambulance_id
                WHERE d.request_id = ? AND d.dispatch_status = 'Assigned';
            """, (req_id,))
            dispatch_rec = cursor.fetchone()

            if dispatch_rec:
                # Cancel dispatch and release ambulance safely
                cursor.execute("""
                    UPDATE dispatch_history
                    SET dispatch_status = 'Cancelled'
                    WHERE dispatch_id = ?;
                """, (dispatch_rec["dispatch_id"],))

                cursor.execute("""
                    UPDATE ambulances
                    SET status = 'Available'
                    WHERE ambulance_id = ?;
                """, (dispatch_rec["ambulance_id"],))

            cursor.execute("""
                UPDATE emergency_requests
                SET request_status = 'Cancelled', cancellation_reason = ?, tracking_substatus = 'Cancelled by Requester'
                WHERE request_id = ?;
            """, (reason, req_id))

            conn.commit()
            return True, "Booking cancelled successfully. The assigned ambulance has been released."

        return False, f"Cannot cancel booking in '{status}' status."

    except Exception as e:
        conn.rollback()
        return False, f"Database error during cancellation: {str(e)}"
    finally:
        conn.close()


def update_user_live_location(raw_token: str, lat: float, lng: float) -> Tuple[bool, str]:
    """
    Updates the requester's live moving location when user enables 'Share my live location'.
    """
    token_hash = hash_token(raw_token)
    try:
        lat = float(lat)
        lng = float(lng)
        if not (-90 <= lat <= 90 and -180 <= lng <= 180):
            return False, "Invalid coordinate range."
    except ValueError:
        return False, "Coordinates must be numbers."

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE emergency_requests
            SET user_live_lat = ?, user_live_lng = ?, user_live_updated_at = CURRENT_TIMESTAMP
            WHERE tracking_token_hash = ?;
        """, (lat, lng, token_hash))
        conn.commit()
        if cursor.rowcount > 0:
            return True, "Live location updated."
        return False, "Booking not found."
    except Exception as e:
        conn.rollback()
        return False, f"Database error: {str(e)}"
    finally:
        conn.close()

