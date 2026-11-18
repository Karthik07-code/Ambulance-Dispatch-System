"""
Comprehensive Functional & Web Route Tests for Flask Application.
"""

import unittest
import os
import database

# Use dedicated test database
test_db_path = os.path.join(os.path.dirname(__file__), "app_test.db")
database.DB_PATH = test_db_path

from app import app
from database import init_db


class TestAppRoutes(unittest.TestCase):

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

    def test_dashboard_route(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Emergency Dispatch Dashboard", response.data)
        self.assertIn(b"TOTAL FLEET", response.data)

    def test_ambulances_page_and_crud(self):
        # 1. List
        resp = self.client.get("/ambulances")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"AMB-101", resp.data)

        # 2. Add New
        post_resp = self.client.post("/ambulances/new", data={
            "ambulance_number": "AMB-999",
            "current_location": "Gandhipuram",
            "status": "Available"
        }, follow_redirects=True)
        self.assertEqual(post_resp.status_code, 200)
        self.assertIn(b"AMB-999", post_resp.data)

        # 3. Edit
        edit_resp = self.client.post("/ambulances/edit/1", data={
            "ambulance_number": "AMB-101-UPDATED",
            "current_location": "RS Puram",
            "status": "Maintenance"
        }, follow_redirects=True)
        self.assertEqual(edit_resp.status_code, 200)
        self.assertIn(b"AMB-101-UPDATED", edit_resp.data)

    def test_emergencies_page_and_crud(self):
        # 1. List
        resp = self.client.get("/emergencies")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Kavitha Sundaram", resp.data)

        # 2. Add New
        post_resp = self.client.post("/emergencies/new", data={
            "patient_name": "Test Patient Z",
            "emergency_location": "Peelamedu",
            "severity": "Critical"
        }, follow_redirects=True)
        self.assertEqual(post_resp.status_code, 200)
        self.assertIn(b"Test Patient Z", post_resp.data)

    def test_auto_dispatch_and_history(self):
        # Trigger auto dispatch
        dispatch_resp = self.client.post("/dispatch/auto", follow_redirects=True)
        self.assertEqual(dispatch_resp.status_code, 200)
        self.assertIn(b"Dispatch Successful", dispatch_resp.data)

        # Check history page
        hist_resp = self.client.get("/dispatch/history")
        self.assertEqual(hist_resp.status_code, 200)
        self.assertIn(b"Assignment Logs", hist_resp.data)

        # Mark completed
        comp_resp = self.client.post("/dispatch/complete/1", follow_redirects=True)
        self.assertEqual(comp_resp.status_code, 200)
        self.assertIn(b"marked as Completed", comp_resp.data)

    def test_dsa_simulator_page(self):
        resp = self.client.get("/dsa")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Live Dijkstra Path Simulator", resp.data)

        # Post query for Dijkstra: Gandhipuram to Singanallur
        calc_resp = self.client.post("/dsa", data={
            "start_node": "Gandhipuram",
            "target_node": "Singanallur"
        })
        self.assertEqual(calc_resp.status_code, 200)
        self.assertIn(b"Total Distance:", calc_resp.data)


if __name__ == "__main__":
    unittest.main()

