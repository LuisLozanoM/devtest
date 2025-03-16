import time
from datetime import datetime


class Elevator:
    def __init__(self, id, total_floors, db):
        """Initialize an elevator with its ID and database connection."""
        self.id = id
        self.current_floor = 0
        self.status = "idle"
        self.total_floors = total_floors
        self.db = db
        self.current_resting_id = None
        self.current_journey_id = None

        # Initialize in database
        self.db.update_elevator_status(self.id, self.current_floor, self.status)

        # Start first resting period
        self.start_resting()

    def start_resting(self):
        """Record the start of a resting period."""
        if self.status == "idle" and self.current_resting_id is None:
            self.current_resting_id = self.db.start_resting_period(
                self.id, self.current_floor
            )

    def end_resting(self):
        """End the current resting period if one exists."""
        if self.current_resting_id is not None:
            self.db.end_resting_period(self.current_resting_id)
            self.current_resting_id = None

    def move(self, destination_floor):
        """Move the elevator to the specified floor."""
        # Don't move if already at the destination
        if self.current_floor == destination_floor:
            return 0.0

        # End any current resting period
        if self.status == "idle" and self.current_resting_id:
            self.db.end_resting_period(self.current_resting_id)
            self.current_resting_id = None

        # Set direction
        if destination_floor > self.current_floor:
            self.status = "moving_up"
        else:
            self.status = "moving_down"

        # Update status in database
        self.db.update_elevator_status(self.id, self.current_floor, self.status)

        # Simulate travel time (1 second per floor)
        travel_time = abs(destination_floor - self.current_floor)
        time.sleep(0.2)  # Reduced for demo purposes

        # Update position and status
        self.current_floor = destination_floor
        self.status = "idle"
        self.db.update_elevator_status(self.id, self.current_floor, self.status)

        # Begin a new resting period
        self.current_resting_id = self.db.start_resting_period(
            self.id, self.current_floor
        )

        return travel_time

    def start_journey(self, start_floor, passenger_count=1):
        """Begin recording a journey."""
        self.current_journey_id = self.db.start_journey(
            self.id, start_floor, passenger_count
        )
        return self.current_journey_id

    def end_journey(self, end_floor):
        """End the current journey."""
        if self.current_journey_id:
            self.db.end_journey(self.current_journey_id, end_floor)
            self.current_journey_id = None

    def move_to_optimal_resting_floor(self, optimal_floor):
        """Position the elevator at its predicted optimal resting floor."""
        # Only move if idle
        if self.status != "idle":
            return False

        travel_time = self.move(optimal_floor)
        return travel_time > 0


class ElevatorSystem:
    def __init__(self, num_elevators, num_floors, db):
        """Initialize the elevator system with the given number of elevators."""
        self.num_elevators = num_elevators
        self.num_floors = num_floors
        self.db = db
        self.elevators = []

        # Initialize elevators in the database
        self.db.initialize_elevators(num_elevators, num_floors)

        # Create elevator objects
        for i in range(1, num_elevators + 1):
            self.elevators.append(Elevator(i, num_floors, db))

    def request_elevator(self, origin_floor, destination_floor):
        """Process a request for an elevator."""
        if origin_floor == destination_floor:
            raise ValueError("Origin and destination floors cannot be the same")

        if not (
            0 <= origin_floor < self.num_floors
            and 0 <= destination_floor < self.num_floors
        ):
            raise ValueError(f"Floors must be between 0 and {self.num_floors-1}")

        # Find the closest available elevator
        assigned_elevator = None
        min_distance = float("inf")

        for elevator in self.elevators:
            # Calculate distance
            distance = abs(elevator.current_floor - origin_floor)

            # Prefer idle elevators, but allow busy ones if needed
            if distance < min_distance:
                min_distance = distance
                assigned_elevator = elevator

        # Record the demand
        wait_time = min_distance  # Simplified wait time calculation
        self.db.record_demand(
            origin_floor, destination_floor, assigned_elevator.id, wait_time
        )

        # Start journey and move to pick up
        assigned_elevator.start_journey(assigned_elevator.current_floor)
        pickup_time = assigned_elevator.move(origin_floor)

        # Travel to destination
        travel_time = assigned_elevator.move(destination_floor)

        # End the journey
        assigned_elevator.end_journey(destination_floor)

        # Total journey time
        total_time = pickup_time + travel_time

        return assigned_elevator.id, total_time

    def get_elevators_status(self):
        """Get the current status of all elevators in the system."""
        statuses = []
        for elevator in self.elevators:
            statuses.append(
                {
                    "id": elevator.id,
                    "floor": elevator.current_floor,
                    "status": elevator.status,
                }
            )
        return statuses

    def move_elevator_to_resting_floor(self, elevator_id, optimal_floor):
        """Move an elevator to what is predicted to be its optimal resting floor."""
        if not (0 <= optimal_floor < self.num_floors):
            raise ValueError(f"Floor must be between 0 and {self.num_floors-1}")

        for elevator in self.elevators:
            if elevator.id == elevator_id and elevator.status == "idle":
                elevator.move_to_optimal_resting_floor(optimal_floor)
                return True

        return False  # Elevator not found or not idle
