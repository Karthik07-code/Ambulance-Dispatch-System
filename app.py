"""
Emergency Ambulance Dispatch System
====================================
Flask Web Application Entrypoint with Real-Time User Panel Tracking
A practical demonstration of Data Structures & Algorithms (DSA):
- Priority Queue (Binary Min-Heap) for emergency triage
- Adjacency List Graph for road network representation
- Dijkstra's Algorithm for shortest path ambulance routing
- User Panel for instant public bookings with live tracking
"""

import os
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room

load_dotenv()

from database import init_db, get_db_connection
from dsa.graph import ROAD_NETWORK, PREDEFINED_LOCATIONS, LOCATION_COORDINATES
from dsa.priority_queue import EmergencyPriorityQueue
from dsa.dijkstra import dijkstra_shortest_path
from modules import ambulance as ambulance_mod
from modules import emergency as emergency_mod
from modules import dispatch as dispatch_mod
from modules import user_service
from modules import auth as auth_mod
from modules import driver_service

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "eads-secret-key-2026-dsa-demo")

# Real-time WebSocket server
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# Automatically initialize database with demo seeds and non-destructive migrations
init_db(seed=True)


def notify_tracking_update(request_id: int) -> None:
    """Broadcasts status update to the tracking room associated with this request."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT tracking_token FROM emergency_requests WHERE request_id = ?;", (request_id,))
    row = cursor.fetchone()
    conn.close()
    if row and row["tracking_token"]:
        token = row["tracking_token"]
        booking_data = user_service.get_booking_by_token(token)
        if booking_data:
            token_hash = user_service.hash_token(token)
            socketio.emit("booking_status_update", booking_data, room=f"tracking_{token_hash}")


@app.context_processor
def inject_user():
    """Make current_user available across all templates."""
    return dict(current_user=auth_mod.get_current_user())


# ==========================================
# 0. Authentication Routes (Admin & Driver)
# ==========================================
@app.route("/login", methods=["GET", "POST"])
def login():
    """Sign-in route for Admin and Driver staff."""
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        next_url = request.form.get("next") or request.args.get("next")

        success, account, msg = auth_mod.authenticate(username, password)
        if success:
            auth_mod.login_user(account)
            flash(f"Welcome back, {account.get('full_name') or account['username']}!", "success")
            if next_url:
                return redirect(next_url)
            if account["role"] == "Driver":
                return redirect(url_for("driver_dashboard"))
            return redirect(url_for("dashboard"))
        else:
            flash(msg, "danger")

    return render_template("auth/login.html")


@app.route("/logout")
def logout():
    """Sign-out route."""
    auth_mod.logout_user()
    flash("You have been signed out.", "info")
    return redirect(url_for("login"))


# ==========================================
# 1. Admin Dashboard Route
# ==========================================
@app.route("/")
@app.route("/dashboard")
def dashboard():
    stats = dispatch_mod.get_dashboard_stats()
    ambulances = ambulance_mod.get_all_ambulances()
    recent_emergencies = emergency_mod.get_all_emergencies()[:6]
    active_dispatches = dispatch_mod.get_active_dispatches()

    # Peek top request in the Priority Queue to display on the dashboard
    pending_list = emergency_mod.get_pending_emergencies()
    next_request = None
    if pending_list:
        pq = EmergencyPriorityQueue()
        for r in pending_list:
            pq.push(r)
        next_request = pq.peek()

    return render_template(
        "dashboard.html",
        stats=stats,
        ambulances=ambulances,
        recent_emergencies=recent_emergencies,
        active_dispatches=active_dispatches,
        next_request=next_request,
        predefined_locations=PREDEFINED_LOCATIONS
    )


# ==========================================
# 2. Ambulance Management Routes (Admin)
# ==========================================
@app.route("/ambulances")
def list_ambulances():
    ambulances = ambulance_mod.get_all_ambulances()
    return render_template(
        "ambulances.html",
        ambulances=ambulances,
        predefined_locations=PREDEFINED_LOCATIONS
    )


@app.route("/ambulances/new", methods=["GET", "POST"])
def new_ambulance():
    if request.method == "POST":
        amb_number = request.form.get("ambulance_number", "")
        location = request.form.get("current_location", "")
        status = request.form.get("status", "Available")

        success, msg = ambulance_mod.add_ambulance(amb_number, location, status)
        if success:
            flash(msg, "success")
            return redirect(url_for("list_ambulances"))
        else:
            flash(msg, "danger")

    return render_template(
        "ambulance_form.html",
        ambulance=None,
        predefined_locations=PREDEFINED_LOCATIONS
    )


@app.route("/ambulances/edit/<int:ambulance_id>", methods=["GET", "POST"])
def edit_ambulance(ambulance_id: int):
    ambulance = ambulance_mod.get_ambulance_by_id(ambulance_id)
    if not ambulance:
        flash("Ambulance not found.", "danger")
        return redirect(url_for("list_ambulances"))

    if request.method == "POST":
        amb_number = request.form.get("ambulance_number", "")
        location = request.form.get("current_location", "")
        status = request.form.get("status", "Available")

        success, msg = ambulance_mod.update_ambulance(ambulance_id, amb_number, location, status)
        if success:
            flash(msg, "success")
            return redirect(url_for("list_ambulances"))
        else:
            flash(msg, "danger")

    return render_template(
        "ambulance_form.html",
        ambulance=ambulance,
        predefined_locations=PREDEFINED_LOCATIONS
    )


@app.route("/ambulances/delete/<int:ambulance_id>", methods=["POST"])
def delete_ambulance_route(ambulance_id: int):
    success, msg = ambulance_mod.delete_ambulance(ambulance_id)
    flash(msg, "success" if success else "danger")
    return redirect(url_for("list_ambulances"))


# ==========================================
# 3. Emergency Request Management Routes (Admin)
# ==========================================
@app.route("/emergencies")
def list_emergencies():
    status_filter = request.args.get("status")
    emergencies = emergency_mod.get_all_emergencies(status_filter)

    # Compute status counts for filter badges
    all_emergencies = emergency_mod.get_all_emergencies()
    all_count = len(all_emergencies)
    pending_count = sum(1 for e in all_emergencies if e["request_status"] == "Pending")
    assigned_count = sum(1 for e in all_emergencies if e["request_status"] == "Assigned")
    completed_count = sum(1 for e in all_emergencies if e["request_status"] == "Completed")

    return render_template(
        "emergencies.html",
        emergencies=emergencies,
        current_filter=status_filter,
        all_count=all_count,
        pending_count=pending_count,
        assigned_count=assigned_count,
        completed_count=completed_count,
        predefined_locations=PREDEFINED_LOCATIONS
    )


@app.route("/emergencies/new", methods=["GET", "POST"])
def new_emergency():
    if request.method == "POST":
        patient_name = request.form.get("patient_name", "")
        location = request.form.get("emergency_location", "")
        severity = request.form.get("severity", "Medium")

        success, msg, _ = emergency_mod.add_emergency(patient_name, location, severity)
        if success:
            flash(msg, "success")
            return redirect(url_for("list_emergencies"))
        else:
            flash(msg, "danger")

    return render_template(
        "emergency_form.html",
        emergency=None,
        predefined_locations=PREDEFINED_LOCATIONS
    )


@app.route("/emergencies/edit/<int:request_id>", methods=["GET", "POST"])
def edit_emergency(request_id: int):
    emergency = emergency_mod.get_emergency_by_id(request_id)
    if not emergency:
        flash("Emergency request not found.", "danger")
        return redirect(url_for("list_emergencies"))

    if request.method == "POST":
        patient_name = request.form.get("patient_name", "")
        location = request.form.get("emergency_location", "")
        severity = request.form.get("severity", "Medium")
        status = request.form.get("request_status", emergency["request_status"])

        success, msg = emergency_mod.update_emergency(request_id, patient_name, location, severity, status)
        if success:
            flash(msg, "success")
            notify_tracking_update(request_id)
            return redirect(url_for("list_emergencies"))
        else:
            flash(msg, "danger")

    return render_template(
        "emergency_form.html",
        emergency=emergency,
        predefined_locations=PREDEFINED_LOCATIONS
    )


@app.route("/emergencies/delete/<int:request_id>", methods=["POST"])
def delete_emergency_route(request_id: int):
    success, msg = emergency_mod.delete_emergency(request_id)
    flash(msg, "success" if success else "danger")
    return redirect(url_for("list_emergencies"))


# ==========================================
# 4. Dispatch Workflow Routes
# ==========================================
@app.route("/dispatch/auto", methods=["POST"])
def auto_dispatch():
    result = dispatch_mod.dispatch_next_emergency()
    if result["success"]:
        flash(
            f"Dispatch Successful! Assigned {result['ambulance']['ambulance_number']} to {result['emergency']['patient_name']} "
            f"({result['distance_km']} km via {result['route_display']}).",
            "success"
        )
        notify_tracking_update(result["emergency"]["request_id"])
    else:
        flash(result["message"], "warning" if result.get("error_type") in ("NO_EMERGENCIES", "NO_AMBULANCES") else "danger")

    return redirect(request.referrer or url_for("dashboard"))


@app.route("/dispatch/single/<int:request_id>", methods=["POST"])
def dispatch_single(request_id: int):
    result = dispatch_mod.dispatch_specific_emergency(request_id)
    if result["success"]:
        flash(
            f"Assigned {result['ambulance']['ambulance_number']} to {result['emergency']['patient_name']} "
            f"({result['distance_km']} km via {result['route_display']}).",
            "success"
        )
        notify_tracking_update(request_id)
    else:
        flash(result["message"], "danger")

    return redirect(request.referrer or url_for("list_emergencies"))


@app.route("/dispatch/complete/<int:dispatch_id>", methods=["POST"])
def mark_completed(dispatch_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT request_id FROM dispatch_history WHERE dispatch_id = ?;", (dispatch_id,))
    row = cursor.fetchone()
    req_id = row["request_id"] if row else None
    conn.close()

    success, msg = dispatch_mod.complete_dispatch(dispatch_id)
    flash(msg, "success" if success else "danger")
    if success and req_id:
        notify_tracking_update(req_id)
    return redirect(request.referrer or url_for("dispatch_history"))


@app.route("/dispatch/cancel/<int:dispatch_id>", methods=["POST"])
def mark_cancelled(dispatch_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT request_id FROM dispatch_history WHERE dispatch_id = ?;", (dispatch_id,))
    row = cursor.fetchone()
    req_id = row["request_id"] if row else None
    conn.close()

    success, msg = dispatch_mod.cancel_dispatch(dispatch_id)
    flash(msg, "info" if success else "danger")
    if success and req_id:
        notify_tracking_update(req_id)
    return redirect(request.referrer or url_for("dispatch_history"))


@app.route("/dispatch/history")
def dispatch_history():
    dispatches = dispatch_mod.get_all_dispatches()
    return render_template("dispatch_history.html", dispatches=dispatches)


# ==========================================
# 5. DSA Architecture & Live Route Simulator
# ==========================================
@app.route("/dsa", methods=["GET", "POST"])
def dsa_architecture():
    selected_start = "Gandhipuram"
    selected_target = "Singanallur"
    computed_dist = None
    computed_path = None

    if request.method == "POST":
        selected_start = request.form.get("start_node", "Gandhipuram")
        selected_target = request.form.get("target_node", "Singanallur")
        computed_dist, computed_path = dijkstra_shortest_path(ROAD_NETWORK, selected_start, selected_target)
    else:
        computed_dist, computed_path = dijkstra_shortest_path(ROAD_NETWORK, selected_start, selected_target)

    network_edges = ROAD_NETWORK.get_all_edges()

    return render_template(
        "dsa_architecture.html",
        predefined_locations=PREDEFINED_LOCATIONS,
        network_edges=network_edges,
        selected_start=selected_start,
        selected_target=selected_target,
        computed_dist=computed_dist,
        computed_path=computed_path
    )


# ==========================================
# 6. Public User Panel Routes (Zero Login)
# ==========================================
@app.route("/user")
def user_home():
    """Public landing page for rapid ambulance requests."""
    return render_template("user/landing.html")


@app.route("/user/book")
def user_book():
    """Public emergency booking form with interactive map."""
    google_maps_api_key = os.environ.get("GOOGLE_MAPS_API_KEY", "")
    return render_template(
        "user/book.html",
        predefined_locations=PREDEFINED_LOCATIONS,
        location_coordinates=LOCATION_COORDINATES,
        google_maps_api_key=google_maps_api_key
    )


@app.route("/user/lookup")
def lookup_tracking():
    """Lookup existing booking by tracking token, full URL, or booking reference."""
    token_input = request.args.get("token", "").strip()
    if not token_input:
        flash("Please enter a tracking token or reference.", "warning")
        return redirect(url_for("user_home"))

    if "/track/" in token_input:
        token_input = token_input.split("/track/")[-1].strip("/")

    # Check if raw token matches
    booking = user_service.get_booking_by_token(token_input)
    if booking:
        return redirect(url_for("track_booking", token=token_input))

    # Check by booking reference
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT tracking_token FROM emergency_requests WHERE booking_reference = ?;", (token_input,))
    row = cursor.fetchone()
    conn.close()
    if row and row["tracking_token"]:
        return redirect(url_for("track_booking", token=row["tracking_token"]))

    flash("No active emergency booking found matching that token or reference.", "danger")
    return redirect(url_for("user_home"))


@app.route("/track/<token>")
def track_booking(token: str):
    """Secure private live tracking view accessed via unguessable token."""
    booking = user_service.get_booking_by_token(token)
    if not booking:
        flash("Invalid tracking link or booking not found.", "danger")
        return redirect(url_for("user_home"))

    google_maps_api_key = os.environ.get("GOOGLE_MAPS_API_KEY", "")
    return render_template(
        "user/track.html",
        booking=booking,
        raw_token=token,
        google_maps_api_key=google_maps_api_key
    )


# ==========================================
# 7. User Panel REST APIs
# ==========================================
@app.route("/api/user/bookings", methods=["POST"])
def api_create_booking():
    """Create emergency booking from public portal."""
    data = request.get_json(silent=True) or request.form
    patient_name = data.get("patient_name", "")
    contact_phone = data.get("contact_phone", "")
    severity = data.get("severity", "Critical")
    pickup_address = data.get("pickup_address", "")
    latitude = data.get("latitude")
    longitude = data.get("longitude")
    emergency_note = data.get("emergency_note", "")

    success, message, token, booking_ref, req_id = user_service.create_user_booking(
        patient_name=patient_name,
        contact_phone=contact_phone,
        severity=severity,
        pickup_address=pickup_address,
        latitude=latitude,
        longitude=longitude,
        emergency_note=emergency_note
    )

    if not success:
        return jsonify({"success": False, "message": message}), 400

    tracking_url = url_for("track_booking", token=token)
    return jsonify({
        "success": True,
        "message": message,
        "token": token,
        "booking_reference": booking_ref,
        "tracking_url": tracking_url,
        "request_id": req_id
    })


@app.route("/api/user/tracking/<token>", methods=["GET"])
def api_get_tracking(token: str):
    """Fetch live tracking status and telemetry for a validated booking."""
    booking = user_service.get_booking_by_token(token)
    if not booking:
        return jsonify({"success": False, "message": "Booking not found or invalid token."}), 404
    return jsonify({"success": True, "booking": booking})


@app.route("/api/user/tracking/<token>/cancel", methods=["POST"])
def api_cancel_booking(token: str):
    """Cancel booking requested by the user."""
    payload = request.get_json(silent=True) or request.form
    reason = payload.get("reason", "Cancelled by user via tracking portal")
    success, message = user_service.cancel_user_booking(token, reason)

    if success:
        token_hash = user_service.hash_token(token)
        socketio.emit("booking_status_update", {"request_status": "Cancelled"}, room=f"tracking_{token_hash}")
        return jsonify({"success": True, "message": message})
    return jsonify({"success": False, "message": message}), 400


@app.route("/api/user/tracking/<token>/location", methods=["POST"])
def api_update_user_location(token: str):
    """Receive live user GPS coordinates while en route/moving."""
    payload = request.get_json(silent=True) or request.form
    lat = payload.get("latitude")
    lng = payload.get("longitude")
    if lat is None or lng is None:
        return jsonify({"success": False, "message": "Missing coordinates."}), 400

    success, msg = user_service.update_user_live_location(token, lat, lng)
    return jsonify({"success": success, "message": msg}), (200 if success else 400)


# ==========================================
# 8. Driver Panel Routes (Authenticated)
# ==========================================
@app.route("/driver")
@app.route("/driver/dashboard")
@auth_mod.login_required
@auth_mod.role_required("Driver", "Admin")
def driver_dashboard():
    """Driver Cockpit: view active mission, patient contact, nearby hospitals, and GPS sync."""
    user = auth_mod.get_current_user()
    driver = driver_service.get_driver_profile(user["account_id"])
    if not driver:
        # If Admin is previewing driver view, provide fallback driver
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM drivers LIMIT 1;")
        row = cursor.fetchone()
        conn.close()
        driver = dict(row) if row else {"driver_id": 1, "full_name": "Demo Driver", "ambulance_number": "AMB-101"}

    driver_id = driver["driver_id"]
    active_dispatch = driver_service.get_active_dispatch_for_driver(driver_id)

    # Nearby hospitals based on patient or vehicle location
    ref_lat = (active_dispatch.get("pickup_lat") if active_dispatch else None) or driver.get("ambulance_lat") or 11.0168
    ref_lng = (active_dispatch.get("pickup_lng") if active_dispatch else None) or driver.get("ambulance_lng") or 76.9558
    hospitals = driver_service.get_nearby_hospitals(ref_lat, ref_lng)

    return render_template(
        "driver/dashboard.html",
        driver=driver,
        active_dispatch=active_dispatch,
        hospitals=hospitals
    )


@app.route("/driver/status/<int:dispatch_id>", methods=["POST"])
@auth_mod.login_required
@auth_mod.role_required("Driver", "Admin")
def driver_update_status(dispatch_id: int):
    """Update dispatch state: Accepted -> En Route -> Arrived -> Patient Picked Up -> Completed."""
    user = auth_mod.get_current_user()
    driver = driver_service.get_driver_profile(user["account_id"])
    driver_id = driver["driver_id"] if driver else 1

    new_status = request.form.get("status", "")
    hospital_name = request.form.get("hospital_name")

    success, msg, update_data = driver_service.update_dispatch_status_by_driver(
        driver_id=driver_id,
        dispatch_id=dispatch_id,
        new_status=new_status,
        hospital_name=hospital_name
    )

    if success:
        flash(msg, "success")
        if update_data and update_data.get("tracking_token"):
            token_hash = user_service.hash_token(update_data["tracking_token"])
            socketio.emit("booking_status_update", {
                "request_status": "Assigned" if new_status != "Completed" else "Completed",
                "tracking_substatus": f"Ambulance {new_status}",
                "ambulance_number": update_data.get("ambulance_number")
            }, room=f"tracking_{token_hash}")
    else:
        flash(msg, "danger")

    return redirect(url_for("driver_dashboard"))


@app.route("/api/driver/location", methods=["POST"])
def api_driver_location():
    """Receives continuous GPS coordinates from driver's device via watchPosition()."""
    user = auth_mod.get_current_user()
    if not user or user["role"] not in ("Driver", "Admin"):
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    driver = driver_service.get_driver_profile(user["account_id"])
    driver_id = driver["driver_id"] if driver else 1

    data = request.get_json(silent=True) or request.form
    lat = data.get("latitude")
    lng = data.get("longitude")
    heading = data.get("heading")
    accuracy = data.get("accuracy")

    if lat is None or lng is None:
        return jsonify({"success": False, "message": "Coordinates required"}), 400

    success, msg, tracking_token = driver_service.update_driver_gps_telemetry(
        driver_id=driver_id,
        latitude=float(lat),
        longitude=float(lng),
        heading=float(heading) if heading is not None else None,
        accuracy_m=float(accuracy) if accuracy is not None else None
    )

    # Real-time WebSocket emission to User live tracking page
    if success and tracking_token:
        token_hash = user_service.hash_token(tracking_token)
        socketio.emit("ambulance_location_update", {
            "latitude": float(lat),
            "longitude": float(lng),
            "heading": heading
        }, room=f"tracking_{token_hash}")

    return jsonify({"success": success, "message": msg})


@app.route("/api/driver/hospitals", methods=["GET"])
def api_nearby_hospitals():
    """Endpoint returning nearby hospitals based on query lat/lng."""
    lat = float(request.args.get("lat", 11.0168))
    lng = float(request.args.get("lng", 76.9558))
    hospitals = driver_service.get_nearby_hospitals(lat, lng)
    return jsonify({"success": True, "hospitals": hospitals})


# ==========================================
# 9. Real-time Socket.IO Handlers
# ==========================================
@socketio.on("join_booking_tracking")
def handle_join_tracking(data):
    """Authorizes and joins connection to a booking-specific tracking room."""
    token = (data or {}).get("token", "").strip()
    if not token:
        return
    booking = user_service.get_booking_by_token(token)
    if booking:
        token_hash = user_service.hash_token(token)
        room_name = f"tracking_{token_hash}"
        join_room(room_name)
        emit("booking_status_update", booking)


# ==========================================
# Error Handlers
# ==========================================
@app.errorhandler(404)
def not_found_error(error):
    if request.path.startswith("/api/"):
        return jsonify({"error": "Resource not found"}), 404
    return render_template("base.html"), 404


@app.errorhandler(500)
def internal_error(error):
    if request.path.startswith("/api/"):
        return jsonify({"error": "Internal server error"}), 500
    return render_template("base.html"), 500


if __name__ == "__main__":
    # Run with Socket.IO support on 127.0.0.1:5000
    socketio.run(app, host="127.0.0.1", port=5000, debug=True)
