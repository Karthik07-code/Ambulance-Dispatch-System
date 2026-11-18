"""
Integration tests for the complete Dispatch Workflow and Business Logic.
"""

import unittest
import os
import sqlite3

# Point database to an in-memory or temporary test database for clean testing
import database
test_db_path = os.path.join(os.path.dirname(__file__), "test_ambulance.db")
database.DB_PATH = test_db_path

from database import init_db, get_db_connection
from modules import ambulance, emergency, dispatch


class TestDispatchWorkflow(unittest.TestCase):

    def setUp(self):
        database.DB_PATH = test_db_path
        if os.path.exists(test_db_path):
            os.remove(test_db_path)
        init_db(seed=True)

    def tearDown(self):
        if os.path.exists(test_db_path):
            os.remove(test_db_path)

    def test_auto_dispatch_prioritizes_critical(self):
        # In seeded data, Kavitha Sundaram is Critical (Singanallur),
        # while Ramesh Kumar is Medium (Peelamedu).
        # Auto dispatch MUST dispatch Kavitha Sundaram first!
        result = dispatch.dispatch_next_emergency()
        self.assertTrue(result["success"])
        self.assertEqual(result["emergency"]["patient_name"], "Kavitha Sundaram")
        self.assertEqual(result["emergency"]["severity"], "Critical")
        self.assertEqual(result["emergency"]["emergency_location"], "Singanallur")

        # In seeded ambulances:
        # AMB-104 is at Singanallur (distance = 0.0 km)
        # AMB-102 is at Peelamedu (distance = 4.0 km)
        # AMB-104 should be selected!
        self.assertEqual(result["ambulance"]["ambulance_number"], "AMB-104")
        self.assertEqual(result["distance_km"], 0.0)

        # Check DB states
        amb = ambulance.get_ambulance_by_id(result["ambulance"]["ambulance_id"])
        self.assertEqual(amb["status"], "Busy")

        req = emergency.get_emergency_by_id(result["emergency"]["request_id"])
        self.assertEqual(req["request_status"], "Assigned")

    def test_complete_dispatch(self):
        # Run dispatch first
        result = dispatch.dispatch_next_emergency()
        dispatch_id = result["dispatch_id"]
        amb_id = result["ambulance"]["ambulance_id"]
        req_id = result["emergency"]["request_id"]

        # Mark dispatch completed
        success, msg = dispatch.complete_dispatch(dispatch_id)
        self.assertTrue(success)

        # Verify states
        amb = ambulance.get_ambulance_by_id(amb_id)
        self.assertEqual(amb["status"], "Available")

        req = emergency.get_emergency_by_id(req_id)
        self.assertEqual(req["request_status"], "Completed")


if __name__ == "__main__":
    unittest.main()

