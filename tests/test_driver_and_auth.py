"""
Automated Tests for Staff Authentication & Driver Panel Workflow.
Verifies login, role guards, dispatch state machine, GPS telemetry, and hospital search.
"""

import unittest
import os
import json

import database
test_db_path = os.path.join(os.path.dirname(__file__), "driver_auth_test.db")

from app import app
from database import init_db
from modules import auth, driver_service, ambulance, emergency, dispatch


class TestDriverAndAuth(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False

    def setUp(self):
        database.DB_PATH = test_db_path
        if os.path.exists(test_db_path):
            os.remove(test_db_path)
        init_db(seed=True)
        self.client = app.test_client()

    def tearDown(self):
        if os.path.exists(test_db_path):
            os.remove(test_db_path)

    def test_authentication_login_and_logout(self):
        # 1. Successful Admin Login
        resp = self.client.post("/login", data={
            "username": "admin",
            "password": "admin123"
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Emergency Dispatch Dashboard", resp.data)

        # 2. Logout
        logout_resp = self.client.get("/logout", follow_redirects=True)
        self.assertEqual(logout_resp.status_code, 200)
        self.assertIn(b"Sign In", logout_resp.data)

        # 3. Invalid credentials
        bad_resp = self.client.post("/login", data={
            "username": "admin",
            "password": "wrongpassword"
        }, follow_redirects=True)
        self.assertEqual(bad_resp.status_code, 200)
        self.assertIn(b"Invalid username or password", bad_resp.data)

    def test_driver_role_guard(self):
        # Unauthenticated access to /driver redirects to /login
        r1 = self.client.get("/driver")
        self.assertEqual(r1.status_code, 302)
        self.assertIn("/login", r1.location)

        # Authenticate as driver1
        self.client.post("/login", data={
            "username": "driver1",
            "password": "driver123"
        }, follow_redirects=True)

        # Now access /driver
        r2 = self.client.get("/driver")
        self.assertEqual(r2.status_code, 200)
        self.assertIn(b"Ravi Chandran", r2.data)
        self.assertIn(b"AMB-101", r2.data)

    def test_driver_dispatch_lifecycle_progression(self):
        # 1. Login as driver1 (linked to AMB-101)
        self.client.post("/login", data={
            "username": "driver1",
            "password": "driver123"
        })

        # 2. Trigger auto dispatch so driver1 has an active assignment
        dispatch_result = dispatch.dispatch_next_emergency()
        self.assertTrue(dispatch_result["success"])
        dispatch_id = dispatch_result["dispatch_id"]

        # Link driver1 to this dispatch record directly
        conn = database.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE dispatch_history SET driver_id = 1 WHERE dispatch_id = ?;", (dispatch_id,))
        conn.commit()
        conn.close()

        # 3. Driver accepts dispatch
        s1 = self.client.post(f"/driver/status/{dispatch_id}", data={"status": "Accepted"}, follow_redirects=True)
        self.assertEqual(s1.status_code, 200)

        # 4. Driver marks En Route
        s2 = self.client.post(f"/driver/status/{dispatch_id}", data={"status": "En Route"}, follow_redirects=True)
        self.assertEqual(s2.status_code, 200)

        # 5. Driver marks Arrived
        s3 = self.client.post(f"/driver/status/{dispatch_id}", data={"status": "Arrived"}, follow_redirects=True)
        self.assertEqual(s3.status_code, 200)

        # 6. Driver selects hospital and marks Patient Picked Up
        s4 = self.client.post(f"/driver/status/{dispatch_id}", data={
            "status": "Patient Picked Up",
            "hospital_name": "PSG Hospitals"
        }, follow_redirects=True)
        self.assertEqual(s4.status_code, 200)

        # 7. Driver marks Completed
        s5 = self.client.post(f"/driver/status/{dispatch_id}", data={"status": "Completed"}, follow_redirects=True)
        self.assertEqual(s5.status_code, 200)

        # Verify ambulance is now released and back to Available
        amb = ambulance.get_ambulance_by_id(dispatch_result["ambulance"]["ambulance_id"])
        self.assertEqual(amb["status"], "Available")

    def test_driver_gps_telemetry_endpoint(self):
        # Login as driver1
        self.client.post("/login", data={
            "username": "driver1",
            "password": "driver123"
        })

        # Send live GPS coordinates
        loc_resp = self.client.post("/api/driver/location", json={
            "latitude": 11.0185,
            "longitude": 76.9572,
            "heading": 45.0,
            "accuracy": 5.0
        })
        self.assertEqual(loc_resp.status_code, 200)
        data = json.loads(loc_resp.data)
        self.assertTrue(data["success"])

    def test_nearby_hospitals_api(self):
        hosp_resp = self.client.get("/api/driver/hospitals?lat=11.0168&lng=76.9558")
        self.assertEqual(hosp_resp.status_code, 200)
        data = json.loads(hosp_resp.data)
        self.assertTrue(data["success"])
        self.assertTrue(len(data["hospitals"]) >= 4)
        # Should be sorted by distance
        dists = [h["distance_km"] for h in data["hospitals"]]
        self.assertEqual(dists, sorted(dists))


if __name__ == "__main__":
    unittest.main()

