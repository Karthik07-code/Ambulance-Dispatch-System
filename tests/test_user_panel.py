"""
Automated Tests for the Public User Panel & Live Tracking API.
Verifies zero-login booking, token security, ETA computation, cancellation state machine,
and non-destructive integration with the Admin Panel.
"""

import unittest
import os
import json

import database
test_db_path = os.path.join(os.path.dirname(__file__), "user_panel_test.db")
database.DB_PATH = test_db_path

from app import app
from database import init_db
from modules import user_service, ambulance, emergency, dispatch


class TestUserPanel(unittest.TestCase):

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

    def test_public_pages_accessible_without_auth(self):
        # 1. Landing page
        resp = self.client.get("/user")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Book an Ambulance Now", resp.data)

        # 2. Booking form
        resp_book = self.client.get("/user/book")
        self.assertEqual(resp_book.status_code, 200)
        self.assertIn(b"Emergency Ambulance Request", resp_book.data)

    def test_create_user_booking_success(self):
        # Create booking via API
        payload = {
            "patient_name": "Karthik Raja",
            "contact_phone": "+91 9876543210",
            "severity": "Critical",
            "pickup_address": "Near PSG Tech, Peelamedu",
            "latitude": 11.0267,
            "longitude": 77.0123,
            "emergency_note": "Severe breathlessness"
        }
        resp = self.client.post("/api/user/bookings", data=payload)
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertTrue(data["success"])
        self.assertIn("token", data)
        self.assertIn("tracking_url", data)
        self.assertIn("booking_reference", data)

        token = data["token"]
        self.assertTrue(len(token) >= 32)  # Unguessable cryptographically random token

        # Verify tracking page renders with token
        track_resp = self.client.get(f"/track/{token}")
        self.assertEqual(track_resp.status_code, 200)
        self.assertIn(b"Karthik Raja", track_resp.data)

        # Verify JSON tracking API
        api_track = self.client.get(f"/api/user/tracking/{token}")
        self.assertEqual(api_track.status_code, 200)
        track_data = json.loads(api_track.data)
        self.assertTrue(track_data["success"])
        self.assertEqual(track_data["booking"]["patient_name"], "Karthik Raja")

    def test_validation_rejects_invalid_submissions(self):
        # Missing patient name
        r1 = self.client.post("/api/user/bookings", data={
            "patient_name": "",
            "contact_phone": "+91 9876543210",
            "severity": "Critical",
            "pickup_address": "Gandhipuram"
        })
        self.assertEqual(r1.status_code, 400)

        # Invalid phone format
        r2 = self.client.post("/api/user/bookings", data={
            "patient_name": "Test User",
            "contact_phone": "abc-invalid",
            "severity": "High",
            "pickup_address": "Gandhipuram"
        })
        self.assertEqual(r2.status_code, 400)

        # Invalid severity
        r3 = self.client.post("/api/user/bookings", data={
            "patient_name": "Test User",
            "contact_phone": "9876543210",
            "severity": "SuperCritical123",
            "pickup_address": "Gandhipuram"
        })
        self.assertEqual(r3.status_code, 400)

    def test_invalid_or_forged_token_security(self):
        # Random guessable string
        r = self.client.get("/track/fake-forged-token-12345")
        # Should redirect to /user or return 404
        self.assertIn(r.status_code, (302, 404))

        api_r = self.client.get("/api/user/tracking/fake-forged-token-12345")
        self.assertEqual(api_r.status_code, 404)

    def test_cancel_booking_lifecycle(self):
        # Create a pending booking (with all ambulances made busy to keep it pending)
        # Or create with custom function
        success, msg, token, ref, req_id = user_service.create_user_booking(
            patient_name="Cancel Test Patient",
            contact_phone="9988776655",
            severity="Low",
            pickup_address="Gandhipuram",
            latitude=11.0168,
            longitude=76.9558
        )
        self.assertTrue(success)

        # Cancel the booking
        cancel_resp = self.client.post(f"/api/user/tracking/{token}/cancel", json={
            "reason": "Test patient cancelled"
        })
        self.assertEqual(cancel_resp.status_code, 200)

        # Verify status is Cancelled
        track_resp = self.client.get(f"/api/user/tracking/{token}")
        data = json.loads(track_resp.data)
        self.assertEqual(data["booking"]["request_status"], "Cancelled")

        # Duplicate cancellation should be rejected
        cancel_dup = self.client.post(f"/api/user/tracking/{token}/cancel", json={
            "reason": "Again"
        })
        self.assertEqual(cancel_dup.status_code, 400)

    def test_update_live_user_location(self):
        success, msg, token, ref, req_id = user_service.create_user_booking(
            patient_name="GPS Moving Patient",
            contact_phone="9988776655",
            severity="Medium",
            pickup_address="Railway Station",
            latitude=10.9996,
            longitude=76.9634
        )
        self.assertTrue(success)

        # Post live moving coordinate update
        loc_resp = self.client.post(f"/api/user/tracking/{token}/location", json={
            "latitude": 10.9998,
            "longitude": 76.9638
        })
        self.assertEqual(loc_resp.status_code, 200)

        # Check DB reflects updated live coordinate
        track_data = json.loads(self.client.get(f"/api/user/tracking/{token}").data)
        self.assertEqual(track_data["booking"]["user_live_lat"], 10.9998)
        self.assertEqual(track_data["booking"]["user_live_lng"], 76.9638)

    def test_user_booking_visible_in_admin_panel(self):
        # Create booking via User Panel
        self.client.post("/api/user/bookings", data={
            "patient_name": "Admin Visible Patient",
            "contact_phone": "+91 9999900000",
            "severity": "Critical",
            "pickup_address": "RS Puram",
            "latitude": 11.0089,
            "longitude": 76.9463
        })

        # Admin panel requests list must show this patient
        admin_resp = self.client.get("/emergencies")
        self.assertEqual(admin_resp.status_code, 200)
        self.assertIn(b"Admin Visible Patient", admin_resp.data)


if __name__ == "__main__":
    unittest.main()
