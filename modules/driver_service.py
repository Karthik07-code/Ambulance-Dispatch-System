"""
Driver Service Module
=====================
Encapsulates Driver Panel logic:
- Fetching active assignments assigned specifically to the authenticated driver
- Handling dispatch lifecycle states: Accepted -> En Route -> Arrived -> Patient Picked Up -> Completed
- Receiving real-time Driver GPS updates from watchPosition() and storing them
- Nearby hospitals search (Google Places API / Predefined Emergency Centers)
- Generating Google Maps turn-by-turn navigation URLs
"""

import os
import math
from typing import Dict, Any, List, Optional, Tuple
import requests
from database import get_db_connection


# Predefined Emergency Hospital Centers in Coimbatore
DEMO_HOSPITALS = [
    {
        "name": "PSG Hospitals",
        "address": "Avinashi Road, Peelamedu, Coimbatore",
        "latitude": 11.0255,
        "longitude": 77.0118,
        "phone": "+91 422 257 0170",
        "trauma_center": True
    },
    {
        "name": "Kovai Medical Center & Hospital (KMCH)",
        "address": "99, Avinashi Rd, Peelamedu, Civil Aerodrome Post, Coimbatore",
        "latitude": 11.0504,
        "longitude": 77.0543,
        "phone": "+91 422 432 3800",
        "trauma_center": True
    },
    {
        "name": "Coimbatore Medical College Hospital (CMCH)",
        "address": "Trichy Rd, Gopalapuram, Coimbatore",
        "latitude": 10.9984,
        "longitude": 76.9692,
        "phone": "+91 422 230 1393",
        "trauma_center": True
    },
    {
        "name": "Ganga Hospital (Orthopaedic & Trauma)",
        "address": "313, Mettupalayam Rd, Saibaba Colony, Coimbatore",
        "latitude": 11.0289,
        "longitude": 76.9452,
        "phone": "+91 422 248 5000",
        "trauma_center": True
    },
    {
        "name": "Sri Ramakrishna Hospital",
        "address": "395, Sarojini Naidu Rd, Sidhapudur, Coimbatore",
        "latitude": 11.0261,
        "longitude": 76.9806,
        "phone": "+91 422 450 0000",
        "trauma_center": True
    },
    {
        "name": "GKNM Hospital (G. Kuppuswamy Naidu Memorial)",
        "address": "P.N. Palayam, Coimbatore",
        "latitude": 11.0121,
        "longitude": 76.9818,
        "phone": "+91 422 224 5000",
        "trauma_center": False
    }
]


def get_driver_profile(account_id: int) -> Optional[Dict[str, Any]]:
    """Fetch driver record and linked ambulance details for an authenticated account."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT d.driver_id, d.account_id, d.full_name, d.phone, d.ambulance_id, d.availability_status,
               a.ambulance_number, a.current_location, a.status AS ambulance_status,
               a.latitude AS ambulance_lat, a.longitude AS ambulance_lng
        FROM drivers d
        LEFT JOIN ambulances a ON d.ambulance_id = a.ambulance_id
        WHERE d.account_id = ?;
    """, (account_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_active_dispatch_for_driver(driver_id: int) -> Optional[Dict[str, Any]]:
    """
    Fetch the currently active dispatch assigned to this driver.
    Restricts sensitive patient contact info strictly to the assigned driver.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            d.dispatch_id, d.request_id, d.ambulance_id, d.driver_id,
            d.distance_km, d.route, d.assigned_time, d.dispatch_status,
            d.destination_hospital, d.hospital_lat, d.hospital_lng,
            e.patient_name, e.contact_phone, e.pickup_address, e.emergency_location,
            e.latitude AS pickup_lat, e.longitude AS pickup_lng,
            e.severity, e.emergency_note, e.booking_reference, e.tracking_token,
            a.ambulance_number
        FROM dispatch_history d
        JOIN emergency_requests e ON d.request_id = e.request_id
        JOIN ambulances a ON d.ambulance_id = a.ambulance_id
        WHERE (d.driver_id = ? OR a.driver_id = ?)
          AND d.dispatch_status IN ('Assigned', 'Accepted', 'En Route', 'Arrived', 'Picked Up')
        ORDER BY d.dispatch_id DESC
        LIMIT 1;
    """, (driver_id, driver_id))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    data = dict(row)
    # Generate Google Maps external navigation URL
    p_lat = data.get("pickup_lat")
    p_lng = data.get("pickup_lng")
    if p_lat and p_lng:
        data["google_maps_nav_url"] = f"https://www.google.com/maps/dir/?api=1&destination={p_lat},{p_lng}&travelmode=driving"
    else:
        data["google_maps_nav_url"] = f"https://www.google.com/maps/dir/?api=1&destination={data['emergency_location']}+Coimbatore&travelmode=driving"

    return data


def update_dispatch_status_by_driver(
    driver_id: int,
    dispatch_id: int,
    new_status: str,
    hospital_name: Optional[str] = None
) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    State machine for dispatch transitions handled by the driver:
    'Accepted' -> 'En Route' -> 'Arrived' -> 'Patient Picked Up' -> 'Completed'
    """
    valid_transitions = ("Accepted", "En Route", "Arrived", "Patient Picked Up", "Completed")
    if new_status not in valid_transitions:
        return False, f"Invalid trip status '{new_status}'.", None

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT d.dispatch_id, d.request_id, d.ambulance_id, d.dispatch_status,
                   e.tracking_token, e.emergency_location, a.ambulance_number
            FROM dispatch_history d
            JOIN emergency_requests e ON d.request_id = e.request_id
            JOIN ambulances a ON d.ambulance_id = a.ambulance_id
            WHERE d.dispatch_id = ? AND (d.driver_id = ? OR a.driver_id = ?);
        """, (dispatch_id, driver_id, driver_id))
        dispatch_rec = cursor.fetchone()

        if not dispatch_rec:
            return False, "Dispatch not found or unauthorized.", None

        req_id = dispatch_rec["request_id"]
        amb_id = dispatch_rec["ambulance_id"]
        tracking_token = dispatch_rec["tracking_token"]

        # Update dispatch status
        cursor.execute("""
            UPDATE dispatch_history
            SET dispatch_status = ?
            WHERE dispatch_id = ?;
        """, (new_status, dispatch_id))

        # Update emergency request tracking status
        substatus_text = f"Ambulance {new_status}"
        cursor.execute("""
            UPDATE emergency_requests
            SET tracking_substatus = ?
            WHERE request_id = ?;
        """, (substatus_text, req_id))

        # If driver selected hospital
        if hospital_name and new_status in ("Patient Picked Up", "En Route"):
            cursor.execute("""
                UPDATE dispatch_history
                SET destination_hospital = ?
                WHERE dispatch_id = ?;
            """, (hospital_name, dispatch_id))

        # When trip is completed: release driver and ambulance
        if new_status == "Completed":
            cursor.execute("UPDATE emergency_requests SET request_status = 'Completed' WHERE request_id = ?;", (req_id,))
            cursor.execute("UPDATE ambulances SET status = 'Available', current_location = ? WHERE ambulance_id = ?;", 
                           (dispatch_rec["emergency_location"], amb_id))
            cursor.execute("UPDATE drivers SET availability_status = 'Available' WHERE driver_id = ?;", (driver_id,))

        conn.commit()

        updated_data = {
            "dispatch_id": dispatch_id,
            "request_id": req_id,
            "new_status": new_status,
            "tracking_token": tracking_token,
            "ambulance_number": dispatch_rec["ambulance_number"]
        }
        return True, f"Trip status successfully updated to '{new_status}'.", updated_data

    except Exception as e:
        conn.rollback()
        return False, f"Database error: {str(e)}", None
    finally:
        conn.close()


def update_driver_gps_telemetry(
    driver_id: int,
    latitude: float,
    longitude: float,
    heading: Optional[float] = None,
    accuracy_m: Optional[float] = None
) -> Tuple[bool, str, Optional[str]]:
    """
    Updates driver live GPS position and the linked ambulance coordinates.
    Returns (success, message, tracking_token_to_broadcast).
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Upsert driver location
        cursor.execute("""
            INSERT INTO driver_locations (driver_id, latitude, longitude, heading, accuracy_m, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(driver_id) DO UPDATE SET
                latitude = excluded.latitude,
                longitude = excluded.longitude,
                heading = excluded.heading,
                accuracy_m = excluded.accuracy_m,
                updated_at = CURRENT_TIMESTAMP;
        """, (driver_id, latitude, longitude, heading, accuracy_m))

        # Update linked ambulance coordinates
        cursor.execute("""
            UPDATE ambulances
            SET latitude = ?, longitude = ?
            WHERE driver_id = ?;
        """, (latitude, longitude, driver_id))

        # Check if driver has active dispatch to retrieve tracking token
        cursor.execute("""
            SELECT e.tracking_token
            FROM dispatch_history d
            JOIN emergency_requests e ON d.request_id = e.request_id
            JOIN ambulances a ON d.ambulance_id = a.ambulance_id
            WHERE (d.driver_id = ? OR a.driver_id = ?)
              AND d.dispatch_status IN ('Assigned', 'Accepted', 'En Route', 'Arrived', 'Picked Up')
            LIMIT 1;
        """, (driver_id, driver_id))
        row = cursor.fetchone()
        tracking_token = row["tracking_token"] if row else None

        conn.commit()
        return True, "Location updated.", tracking_token

    except Exception as e:
        conn.rollback()
        return False, f"Database error: {str(e)}", None
    finally:
        conn.close()


def get_nearby_hospitals(user_lat: float, user_lng: float) -> List[Dict[str, Any]]:
    """
    Returns nearby emergency hospitals sorted by approximate road distance from current coordinates.
    Supports Google Places API (New) if API key configured, otherwise demo Coimbatore centers.
    """
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY", "").strip()

    # Optional: If real Google Places API key provided, attempt live Places search
    if api_key and api_key != "YOUR_KEY_HERE":
        try:
            places_url = "https://places.googleapis.com/v1/places:searchNearby"
            headers = {
                "Content-Type": "application/json",
                "X-Goog-Api-Key": api_key,
                "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.location"
            }
            body = {
                "includedTypes": ["hospital"],
                "maxResultCount": 5,
                "locationRestriction": {
                    "circle": {
                        "center": {"latitude": user_lat, "longitude": user_lng},
                        "radius": 10000.0
                    }
                }
            }
            resp = requests.post(places_url, json=body, headers=headers, timeout=4)
            if resp.status_code == 200:
                p_data = resp.json().get("places", [])
                results = []
                for p in p_data:
                    h_lat = p.get("location", {}).get("latitude")
                    h_lng = p.get("location", {}).get("longitude")
                    dist_km = calculate_haversine(user_lat, user_lng, h_lat, h_lng)
                    results.append({
                        "name": p.get("displayName", {}).get("text", "Hospital"),
                        "address": p.get("formattedAddress", ""),
                        "latitude": h_lat,
                        "longitude": h_lng,
                        "distance_km": round(dist_km, 1),
                        "nav_url": f"https://www.google.com/maps/dir/?api=1&destination={h_lat},{h_lng}&travelmode=driving"
                    })
                if results:
                    return sorted(results, key=lambda x: x["distance_km"])
        except Exception:
            pass

    # Demo Fallback: Calculate straight road distances to Coimbatore hospitals
    results = []
    for h in DEMO_HOSPITALS:
        dist_km = calculate_haversine(user_lat, user_lng, h["latitude"], h["longitude"])
        results.append({
            "name": h["name"],
            "address": h["address"],
            "latitude": h["latitude"],
            "longitude": h["longitude"],
            "phone": h["phone"],
            "trauma_center": h["trauma_center"],
            "distance_km": round(dist_km, 1),
            "nav_url": f"https://www.google.com/maps/dir/?api=1&destination={h['latitude']},{h['longitude']}&travelmode=driving"
        })

    return sorted(results, key=lambda x: x["distance_km"])


def calculate_haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine formula to compute great-circle distance between two GPS points in km."""
    R = 6371.0  # Earth radius in kilometers
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) * math.sin(dlat / 2) +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) * math.sin(dlon / 2))
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

