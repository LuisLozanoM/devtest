import unittest
import os
import sqlite3
from datetime import datetime
import time

from database import ElevatorDatabase
from elevator_model import Elevator, ElevatorSystem


class TestElevatorDatabase(unittest.TestCase):
    """Test cases for the ElevatorDatabase class."""

    def setUp(self):
        """Set up a test database before each test."""
        self.test_db_path = "test_elevator_data.db"
        # Remove test DB if it exists
        if os.path.exists(self.test_db_path):
            os.remove(self.test_db_path)
        self.db = ElevatorDatabase(self.test_db_path)

    def tearDown(self):
        """Clean up after each test."""
        self.db.close()
        if os.path.exists(self.test_db_path):
            os.remove(self.test_db_path)

    def test_initialize_elevators(self):
        """Test that elevators are properly initialized in the database."""
        num_elevators = 3
        num_floors = 10
        self.db.initialize_elevators(num_elevators, num_floors)

        # Verify elevators were created
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM elevators")
        count = cursor.fetchone()[0]
        self.assertEqual(
            count, num_elevators, "Should initialize the correct number of elevators"
        )

        # Verify elevators start at ground floor (0)
        cursor.execute("SELECT current_floor FROM elevators")
        floors = cursor.fetchall()
        for floor in floors:
            self.assertEqual(floor[0], 0, "All elevators should start at floor 0")

    def test_record_demand(self):
        """Test recording elevator demand."""
        # Initialize elevators
        self.db.initialize_elevators(1, 10)

        # Record a demand
        demand_id = self.db.record_demand(3, 7, 1, 5.0)

        # Verify the demand was recorded
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT * FROM demands WHERE id = ?", (demand_id,))
        demand = cursor.fetchone()
        self.assertIsNotNone(demand, "Demand should be recorded in the database")
        self.assertEqual(demand[2], 3, "Origin floor should be 3")
        self.assertEqual(demand[3], 7, "Destination floor should be 7")

    def test_journey_tracking(self):
        """Test tracking a complete elevator journey."""
        # Initialize elevators
        self.db.initialize_elevators(1, 10)

        # Start a journey
        journey_id = self.db.start_journey(1, 0, 2)

        # End the journey
        self.db.end_journey(journey_id, 5)

        # Verify the journey was recorded
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT * FROM journeys WHERE id = ?", (journey_id,))
        journey = cursor.fetchone()
        self.assertIsNotNone(journey, "Journey should be recorded")
        self.assertEqual(journey[1], 1, "Elevator ID should be 1")
        self.assertEqual(journey[4], 0, "Start floor should be 0")
        self.assertEqual(journey[5], 5, "End floor should be 5")
        self.assertEqual(journey[6], 2, "Passenger count should be 2")
        self.assertIsNotNone(journey[2], "Start time should be recorded")
        self.assertIsNotNone(journey[3], "End time should be recorded")

    def test_resting_period(self):
        """Test recording elevator resting periods."""
        # Initialize elevators
        self.db.initialize_elevators(1, 10)

        # Start a resting period
        period_id = self.db.start_resting_period(1, 3)

        # Wait a bit
        time.sleep(0.5)

        # End the resting period
        duration = self.db.end_resting_period(period_id)

        # Verify the duration is reasonable
        self.assertGreater(duration, 0, "Duration should be positive")
        self.assertLess(duration, 1, "Duration should be less than 1 second")

        # Verify the record in the database
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT * FROM resting_periods WHERE id = ?", (period_id,))
        period = cursor.fetchone()
        self.assertIsNotNone(period, "Resting period should be recorded")
        self.assertEqual(period[1], 1, "Elevator ID should be 1")
        self.assertEqual(period[2], 3, "Floor should be 3")
        self.assertIsNotNone(period[3], "Start time should be recorded")
        self.assertIsNotNone(period[4], "End time should be recorded")
        self.assertAlmostEqual(
            period[5],
            duration,
            delta=0.1,
            msg="Duration in DB should match return value",
        )


class TestElevatorSystem(unittest.TestCase):
    """Test cases for the ElevatorSystem and Elevator classes."""

    def setUp(self):
        """Set up test environment."""
        self.test_db_path = "test_elevator_system.db"
        # Remove test DB if it exists
        if os.path.exists(self.test_db_path):
            os.remove(self.test_db_path)
        self.db = ElevatorDatabase(self.test_db_path)
        self.system = ElevatorSystem(3, 10, self.db)

    def tearDown(self):
        """Clean up after each test."""
        self.db.close()
        if os.path.exists(self.test_db_path):
            os.remove(self.test_db_path)

    def test_elevator_movement(self):
        """Test basic elevator movement."""
        # Get first elevator
        elevator = self.system.elevators[0]

        # Initial state
        self.assertEqual(elevator.current_floor, 0, "Elevator should start at floor 0")
        self.assertEqual(elevator.status, "idle", "Elevator should start as idle")

        # Move to floor 5
        travel_time = elevator.move(5)

        # Verify state after move
        self.assertEqual(elevator.current_floor, 5, "Elevator should be at floor 5")
        self.assertEqual(elevator.status, "idle", "Elevator should be idle after move")
        self.assertGreaterEqual(travel_time, 0, "Travel time should be non-negative")

        # Verify database update
        cursor = self.db.conn.cursor()
        cursor.execute(
            "SELECT current_floor FROM elevators WHERE id = ?", (elevator.id,)
        )
        db_floor = cursor.fetchone()[0]
        self.assertEqual(db_floor, 5, "Database should be updated with new floor")

    def test_elevator_request(self):
        """Test the elevator request and assignment process."""
        # Request an elevator from floor 3 to floor 7
        elevator_id, time_taken = self.system.request_elevator(3, 7)

        # Verify an elevator was assigned
        self.assertIsNotNone(elevator_id, "An elevator should be assigned")
        self.assertGreaterEqual(time_taken, 0, "Travel time should be non-negative")

        # Verify the elevator is now at floor 7
        for elevator in self.system.elevators:
            if elevator.id == elevator_id:
                self.assertEqual(
                    elevator.current_floor,
                    7,
                    "Assigned elevator should be at destination floor",
                )
                self.assertEqual(
                    elevator.status, "idle", "Elevator should be idle after journey"
                )

    def test_invalid_request(self):
        """Test handling of invalid elevator requests."""
        # Same origin and destination
        with self.assertRaises(ValueError):
            self.system.request_elevator(3, 3)

        # Out of range floor
        with self.assertRaises(ValueError):
            self.system.request_elevator(3, 20)

    def test_optimal_resting_floor(self):
        """Test moving an elevator to its optimal resting floor."""
        # Request to initialize elevator positions
        self.system.request_elevator(0, 5)

        # Get statuses
        statuses = self.system.get_elevators_status()

        # Find an idle elevator
        idle_elevator = None
        for status in statuses:
            if status["status"] == "idle":
                idle_elevator = status
                break

        if idle_elevator:
            # Try to move to optimal floor
            optimal_floor = (idle_elevator["floor"] + 2) % 10  # Just a different floor
            result = self.system.move_elevator_to_resting_floor(
                idle_elevator["id"], optimal_floor
            )

            # Verify the move was successful
            self.assertTrue(result, "Moving to optimal floor should succeed")

            # Verify the elevator is now at the optimal floor
            updated_statuses = self.system.get_elevators_status()
            for status in updated_statuses:
                if status["id"] == idle_elevator["id"]:
                    self.assertEqual(
                        status["floor"],
                        optimal_floor,
                        "Elevator should be at optimal floor",
                    )

    def test_multiple_requests(self):
        """Test handling multiple elevator requests."""
        # Generate several requests
        requests = [(1, 8), (3, 6), (9, 2), (4, 7), (2, 5)]

        # Process each request
        for origin, destination in requests:
            elevator_id, _ = self.system.request_elevator(origin, destination)
            self.assertIsNotNone(
                elevator_id,
                f"Request from {origin} to {destination} should be assigned",
            )

        # Verify we have the expected number of demands recorded
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM demands")
        count = cursor.fetchone()[0]
        self.assertEqual(
            count, len(requests), f"Should have recorded {len(requests)} demands"
        )

    def test_data_retrieval_for_ml(self):
        """Test retrieving data in a format suitable for ML training."""
        # Generate some test data
        for _ in range(10):
            origin = int(10 * time.time()) % 10  # Pseudo-random floor
            destination = (origin + 5) % 10
            self.system.request_elevator(origin, destination)
            time.sleep(0.1)  # Ensure different timestamps

        # Get data for ML
        ml_data = self.db.get_elevator_data_for_ml(days=1)

        # Verify the format is suitable for ML
        self.assertIsNotNone(ml_data, "Should retrieve data for ML")
        if ml_data:  # If any data is retrieved
            first_row = ml_data[0]
            self.assertEqual(
                len(first_row),
                5,
                "Each row should have 5 features (hour, day, floor, count, avg_wait)",
            )

            # Check columns represent proper features
            hour = int(first_row[0])
            self.assertTrue(0 <= hour < 24, "Hour should be between 0 and 23")

            day = int(first_row[1])
            self.assertTrue(0 <= day <= 6, "Day of week should be between 0 and 6")

            floor = int(first_row[2])
            self.assertTrue(0 <= floor < 10, "Floor should be within building range")

            count = int(first_row[3])
            self.assertGreater(count, 0, "Count should be positive")

            avg_wait = float(first_row[4])
            self.assertGreaterEqual(
                avg_wait, 0, "Average wait time should be non-negative"
            )


if __name__ == "__main__":
    unittest.main()
