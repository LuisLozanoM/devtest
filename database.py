import sqlite3
import os
from datetime import datetime


class ElevatorDatabase:
    def __init__(self, db_path="elevator_data.db"):
        """Initialize the database connection and create tables if they don't exist."""
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.create_tables()

    def create_tables(self):
        """Create the necessary tables for the elevator system."""
        cursor = self.conn.cursor()

        # Elevator information
        cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS elevators (
            id INTEGER PRIMARY KEY,
            current_floor INTEGER,
            status TEXT CHECK(status IN ('idle', 'moving_up', 'moving_down')),
            last_updated TIMESTAMP
        )
        """
        )

        # Request records
        cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS demands (
            id INTEGER PRIMARY KEY,
            timestamp TIMESTAMP,
            origin_floor INTEGER,
            destination_floor INTEGER,
            elevator_id INTEGER,
            wait_time_seconds REAL,
            FOREIGN KEY (elevator_id) REFERENCES elevators(id)
        )
        """
        )

        # Trip records
        cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS journeys (
            id INTEGER PRIMARY KEY,
            elevator_id INTEGER,
            start_time TIMESTAMP,
            end_time TIMESTAMP,
            start_floor INTEGER,
            end_floor INTEGER,
            passenger_count INTEGER,
            FOREIGN KEY (elevator_id) REFERENCES elevators(id)
        )
        """
        )

        # Idle period records
        cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS resting_periods (
            id INTEGER PRIMARY KEY,
            elevator_id INTEGER,
            floor INTEGER,
            start_time TIMESTAMP,
            end_time TIMESTAMP,
            duration_seconds REAL,
            FOREIGN KEY (elevator_id) REFERENCES elevators(id)
        )
        """
        )

        # Future ML feature: time-based aggregation
        # Note: This table is defined for future ML aggregation functionality
        # but is not currently being populated by the application
        cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS hourly_stats (
            id INTEGER PRIMARY KEY,
            hour INTEGER CHECK(hour >= 0 AND hour < 24),
            day_of_week INTEGER CHECK(day_of_week >= 0 AND day_of_week <= 6),
            floor INTEGER,
            demand_count INTEGER,
            avg_wait_time REAL
        )
        """
        )

        self.conn.commit()

    def initialize_elevators(self, num_elevators, num_floors):
        """Reset and initialize elevators in the database."""
        cursor = self.conn.cursor()

        # Clear existing data
        tables = [
            "elevators",
            "demands",
            "journeys",
            "resting_periods",
            "hourly_stats",
        ]
        for table in tables:
            cursor.execute(f"DELETE FROM {table}")

        # Create new elevators
        for i in range(1, num_elevators + 1):
            cursor.execute(
                "INSERT INTO elevators (id, current_floor, status, last_updated) VALUES (?, ?, ?, ?)",
                (i, 0, "idle", datetime.now()),
            )

        self.conn.commit()

    def update_elevator_status(self, elevator_id, floor, status):
        """Update an elevator's current floor and status."""
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE elevators SET current_floor = ?, status = ?, last_updated = ? WHERE id = ?",
            (floor, status, datetime.now(), elevator_id),
        )
        self.conn.commit()

    def record_demand(self, origin_floor, destination_floor, elevator_id, wait_time):
        """Record a request for an elevator."""
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO demands (timestamp, origin_floor, destination_floor, elevator_id, wait_time_seconds) VALUES (?, ?, ?, ?, ?)",
            (datetime.now(), origin_floor, destination_floor, elevator_id, wait_time),
        )
        demand_id = cursor.lastrowid
        self.conn.commit()
        return demand_id

    def start_journey(self, elevator_id, start_floor, passenger_count=1):
        """Record the start of an elevator journey."""
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO journeys (elevator_id, start_time, start_floor, passenger_count) VALUES (?, ?, ?, ?)",
            (elevator_id, datetime.now(), start_floor, passenger_count),
        )
        journey_id = cursor.lastrowid
        self.conn.commit()
        return journey_id

    def end_journey(self, journey_id, end_floor):
        """Record the end of an elevator journey."""
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE journeys SET end_time = ?, end_floor = ? WHERE id = ?",
            (datetime.now(), end_floor, journey_id),
        )
        self.conn.commit()

    def start_resting_period(self, elevator_id, floor):
        """Record when an elevator becomes idle at a floor."""
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO resting_periods (elevator_id, floor, start_time) VALUES (?, ?, ?)",
            (elevator_id, floor, datetime.now()),
        )
        resting_id = cursor.lastrowid
        self.conn.commit()
        return resting_id

    def end_resting_period(self, resting_id):
        """Record when an elevator stops being idle."""
        cursor = self.conn.cursor()
        now = datetime.now()

        # Get the start time
        cursor.execute(
            "SELECT start_time FROM resting_periods WHERE id = ?", (resting_id,)
        )
        result = cursor.fetchone()

        if result:
            start_time_str = result[0]
            if isinstance(start_time_str, str):
                # Convert string to datetime if needed
                start_time = datetime.strptime(start_time_str, "%Y-%m-%d %H:%M:%S.%f")
            else:
                start_time = start_time_str

            # Calculate duration
            duration = (now - start_time).total_seconds()

            # Update record
            cursor.execute(
                "UPDATE resting_periods SET end_time = ?, duration_seconds = ? WHERE id = ?",
                (now, duration, resting_id),
            )
            self.conn.commit()
            return duration

        return 0

    def get_elevator_status(self, elevator_id=None):
        """Get status of a specific elevator or all elevators."""
        cursor = self.conn.cursor()
        if elevator_id:
            cursor.execute(
                "SELECT id, current_floor, status FROM elevators WHERE id = ?",
                (elevator_id,),
            )
            return cursor.fetchone()

        cursor.execute("SELECT id, current_floor, status FROM elevators")
        return cursor.fetchall()

    def get_elevator_data_for_ml(self, days=30):
        """Retrieve data formatted for ML training."""
        cursor = self.conn.cursor()

        # Query to get demand patterns by hour, floor, and day of week
        query = """
        SELECT 
            strftime('%H', timestamp) as hour,
            strftime('%w', timestamp) as day_of_week,
            origin_floor,
            COUNT(*) as demand_count,
            AVG(wait_time_seconds) as avg_wait_time
        FROM demands
        WHERE timestamp > datetime('now', '-' || ? || ' days')
        GROUP BY hour, day_of_week, origin_floor
        ORDER BY hour, day_of_week, origin_floor
        """

        cursor.execute(query, (days,))
        return cursor.fetchall()

    def close(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()
