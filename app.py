import streamlit as st
import pandas as pd
import numpy as np
import time
import os
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import random

from database import ElevatorDatabase
from elevator_model import ElevatorSystem

# Initialize session state variables
if "initialized" not in st.session_state:
    st.session_state.initialized = False
    st.session_state.elevator_system = None
    st.session_state.db = None
    st.session_state.num_floors = 10
    st.session_state.num_elevators = 3
    st.session_state.request_history = []
    st.session_state.show_stats = False

# Ensure these are always defined, even if the session state was restored partially
if "refresh_display" not in st.session_state:
    st.session_state.refresh_display = False
if "last_action" not in st.session_state:
    st.session_state.last_action = ""
if "last_action_type" not in st.session_state:
    st.session_state.last_action_type = "info"


def safe_rerun():
    """Rerun the app in a way compatible with different Streamlit versions."""
    try:
        st.rerun()
    except AttributeError:
        try:
            st.experimental_rerun()
        except AttributeError:
            st.error("Could not rerun the app. Please refresh the page manually.")


def initialize_system(num_floors, num_elevators):
    """Initialize or reinitialize the elevator system."""
    if st.session_state.db:
        st.session_state.db.close()

    # Create a new database connection
    st.session_state.db = ElevatorDatabase()

    # Initialize the elevator system
    st.session_state.elevator_system = ElevatorSystem(
        num_elevators, num_floors, st.session_state.db
    )
    st.session_state.initialized = True

    # Clear request history
    st.session_state.request_history = []


def request_elevator(origin, destination):
    """Request an elevator and update the UI."""
    if not st.session_state.initialized:
        st.error("Please initialize the elevator system first.")
        return

    try:
        # Process the request
        elevator_id, travel_time = st.session_state.elevator_system.request_elevator(
            origin, destination
        )

        # Add to history
        request_time = datetime.now().strftime("%H:%M:%S")
        st.session_state.request_history.append(
            {
                "Time": request_time,
                "Elevator": elevator_id,
                "From": origin,
                "To": destination,
                "Travel Time (s)": round(travel_time, 1),
            }
        )

        # Store the latest action for display
        st.session_state.last_action = f"Elevator {elevator_id} assigned. Travel time: {round(travel_time, 1)} seconds."
        st.session_state.last_action_type = "success"

        # Force UI refresh by setting a flag
        st.session_state.refresh_display = True

        return True
    except Exception as e:
        st.error(f"Error processing request: {str(e)}")
        return False


def simulate_random_requests(num_requests):
    """Simulate multiple random elevator requests."""
    if not st.session_state.initialized:
        st.error("Please initialize the elevator system first.")
        return False

    try:
        request_details = []

        for _ in range(num_requests):
            origin = random.randint(0, st.session_state.num_floors - 1)
            destination = random.randint(0, st.session_state.num_floors - 1)

            # Ensure origin and destination are different
            while destination == origin:
                destination = random.randint(0, st.session_state.num_floors - 1)

            # Process the request
            elevator_id, travel_time = (
                st.session_state.elevator_system.request_elevator(origin, destination)
            )

            # Add to history
            request_time = datetime.now().strftime("%H:%M:%S")
            st.session_state.request_history.append(
                {
                    "Time": request_time,
                    "Elevator": elevator_id,
                    "From": origin,
                    "To": destination,
                    "Travel Time (s)": round(travel_time, 1),
                }
            )

            request_details.append(
                f"#{_ + 1}: Floor {origin} → {destination} (Elevator {elevator_id})"
            )
            time.sleep(0.05)  # Small delay to prevent database contention

        st.session_state.last_action = f"Completed {num_requests} random requests"
        st.session_state.last_action_type = "success"
        st.session_state.refresh_display = True
        return True
    except Exception as e:
        st.error(f"Error simulating requests: {str(e)}")
        return False


def move_to_optimal_resting_floor():
    """Move idle elevators to their predicted optimal resting floors."""
    if not st.session_state.initialized:
        st.error("Please initialize the elevator system first.")
        return False

    try:
        # In a real system, this would use ML predictions
        # For demo, we'll just move idle elevators to random floors
        statuses = st.session_state.elevator_system.get_elevators_status()
        moved_elevators = []

        for status in statuses:
            if status["status"] == "idle":
                optimal_floor = random.randint(0, st.session_state.num_floors - 1)

                # Only move if it's not already at that floor
                if optimal_floor != status["floor"]:
                    result = (
                        st.session_state.elevator_system.move_elevator_to_resting_floor(
                            status["id"], optimal_floor
                        )
                    )
                    if result:
                        moved_elevators.append((status["id"], optimal_floor))

        if moved_elevators:
            elevator_texts = [
                f"Elevator {id} to floor {floor}" for id, floor in moved_elevators
            ]
            movement_text = ", ".join(elevator_texts)
            st.session_state.last_action = f"Moved: {movement_text}"
            st.session_state.last_action_type = "info"
        else:
            st.session_state.last_action = "No idle elevators to move."
            st.session_state.last_action_type = "warning"

        # Force UI refresh
        st.session_state.refresh_display = True
        return True
    except Exception as e:
        st.error(f"Error moving elevators: {str(e)}")
        return False


def display_statistics():
    """Display elevator usage statistics."""
    if not st.session_state.db:
        st.error("No data available. Please initialize the system first.")
        return

    try:
        # Get demand data
        conn = st.session_state.db.conn
        df_demands = pd.read_sql(
            "SELECT origin_floor, COUNT(*) as count FROM demands GROUP BY origin_floor",
            conn,
        )

        if not df_demands.empty:
            st.subheader("Demand by Floor")
            fig, ax = plt.subplots(figsize=(10, 6))

            # Filter floors to current range
            df_demands = df_demands[
                df_demands["origin_floor"] < st.session_state.num_floors
            ]

            # Prepare visualization data
            all_floors = np.arange(st.session_state.num_floors)
            counts = np.zeros(st.session_state.num_floors)

            # Fill with actual data
            for _, row in df_demands.iterrows():
                floor = int(row["origin_floor"])
                if 0 <= floor < st.session_state.num_floors:
                    counts[floor] = int(row["count"])

            ax.bar(all_floors, counts)
            ax.set_xlabel("Floor")
            ax.set_ylabel("Number of Requests")
            ax.set_xticks(range(st.session_state.num_floors))
            ax.set_xlim(-0.5, st.session_state.num_floors - 0.5)
            st.pyplot(fig)

            # Resting floor stats
            df_resting = pd.read_sql(
                """
                SELECT floor, SUM(duration_seconds) as total_time
                FROM resting_periods
                WHERE end_time IS NOT NULL
                GROUP BY floor
                ORDER BY floor
                """,
                conn,
            )

            if not df_resting.empty:
                st.subheader("Time Spent Resting by Floor")
                fig, ax = plt.subplots(figsize=(10, 6))

                # Filter to current floors
                df_resting = df_resting[
                    df_resting["floor"] < st.session_state.num_floors
                ]

                # Prepare data
                all_floors = np.arange(st.session_state.num_floors)
                times = np.zeros(st.session_state.num_floors)

                # Fill with actual data
                for _, row in df_resting.iterrows():
                    floor = int(row["floor"])
                    if 0 <= floor < st.session_state.num_floors:
                        times[floor] = float(row["total_time"])

                ax.bar(all_floors, times)
                ax.set_xlabel("Floor")
                ax.set_ylabel("Total Resting Time (seconds)")
                ax.set_xticks(range(st.session_state.num_floors))
                ax.set_xlim(-0.5, st.session_state.num_floors - 0.5)
                st.pyplot(fig)

            # Most common journeys
            df_journeys = pd.read_sql(
                f"""
                SELECT start_floor, end_floor, COUNT(*) as count
                FROM journeys
                WHERE start_floor < {st.session_state.num_floors}
                AND end_floor < {st.session_state.num_floors}
                GROUP BY start_floor, end_floor
                ORDER BY count DESC
                LIMIT 10
                """,
                conn,
            )

            if not df_journeys.empty:
                st.subheader("Top Journey Patterns")
                st.dataframe(df_journeys)

            # Elevator usage
            df_elevator = pd.read_sql(
                f"""
                SELECT elevator_id, COUNT(*) as journey_count, 
                       AVG(julianday(end_time) - julianday(start_time)) * 86400 as avg_journey_time
                FROM journeys
                WHERE elevator_id <= {st.session_state.num_elevators}
                GROUP BY elevator_id
                ORDER BY elevator_id
                """,
                conn,
            )

            if not df_elevator.empty:
                st.subheader("Elevator Utilization")
                fig, ax = plt.subplots(figsize=(10, 6))

                elevator_ids = np.arange(1, st.session_state.num_elevators + 1)
                journey_counts = np.zeros(st.session_state.num_elevators)

                for _, row in df_elevator.iterrows():
                    elevator_id = int(row["elevator_id"])
                    if 1 <= elevator_id <= st.session_state.num_elevators:
                        journey_counts[elevator_id - 1] = int(row["journey_count"])

                ax.bar(elevator_ids, journey_counts)
                ax.set_xlabel("Elevator ID")
                ax.set_ylabel("Number of Journeys")
                ax.set_xticks(elevator_ids)
                st.pyplot(fig)

                st.dataframe(df_elevator)
        else:
            st.info(
                "No demand data recorded yet. Generate some elevator activity first."
            )

    except Exception as e:
        st.error(f"Error generating statistics: {str(e)}")
        st.exception(e)


def display_elevator_status():
    """
    Display current elevator positions and status.

    This function creates a visual representation of elevator positions on different floors,
    color-coding them based on their status (idle, moving up, moving down).
    It also displays a tabular view of elevator details for better accessibility.
    """
    if not st.session_state.initialized:
        return

    statuses = st.session_state.elevator_system.get_elevators_status()

    # Visualization of elevator positions
    fig, ax = plt.subplots(figsize=(10, 6))

    # Floor lines
    for floor in range(st.session_state.num_floors):
        ax.axhline(y=floor, color="gray", linestyle="-", alpha=0.3)

    # Position elevators on the chart
    elevator_x = np.linspace(0.2, 0.8, len(statuses))
    elevator_colors = {"idle": "green", "moving_up": "blue", "moving_down": "red"}

    for i, status in enumerate(statuses):
        color = elevator_colors.get(status["status"], "black")
        ax.scatter(
            elevator_x[i],
            status["floor"],
            color=color,
            s=100,
            label=f"Elevator {status['id']}" if i == 0 else "",
        )
        ax.text(
            elevator_x[i],
            status["floor"],
            f"{status['id']}",
            ha="center",
            va="center",
            color="white",
            fontweight="bold",
        )

    # Chart formatting
    ax.set_xlim(0, 1)
    ax.set_ylim(-0.5, st.session_state.num_floors - 0.5)
    ax.set_yticks(range(st.session_state.num_floors))
    ax.set_yticklabels(range(st.session_state.num_floors))
    ax.set_ylabel("Floor")
    ax.set_title("Elevator Positions")
    ax.set_xticks([])  # Hide x-axis

    # Legend
    for status, color in elevator_colors.items():
        ax.scatter([], [], color=color, s=100, label=status.replace("_", " ").title())

    ax.legend(loc="upper right")

    st.pyplot(fig)

    # Table view for accessibility
    st.subheader("Elevator Status Details")
    status_data = []
    for status in statuses:
        status_data.append(
            {
                "Elevator ID": status["id"],
                "Current Floor": status["floor"],
                "Status": status["status"].replace("_", " ").title(),
            }
        )
    status_df = pd.DataFrame(status_data)
    st.dataframe(status_df)


# Main Streamlit app
def main():
    st.title("Elevator Simulation System")
    st.write(
        "This system simulates elevator operations and collects data for ML-based prediction of optimal resting floors."
    )

    # Configuration section
    with st.sidebar:
        st.header("Configuration")
        num_floors = st.slider("Number of Floors", 2, 20, 10)
        num_elevators = st.slider("Number of Elevators", 1, 5, 3)

        if st.button("Initialize System"):
            st.session_state.num_floors = num_floors
            st.session_state.num_elevators = num_elevators
            initialize_system(num_floors, num_elevators)
            st.session_state.last_action = "Elevator system initialized!"
            st.session_state.last_action_type = "success"
            st.session_state.refresh_display = True
            safe_rerun()

        st.session_state.show_stats = st.checkbox("Show Statistics")

    # Only show the rest if the system is initialized
    if st.session_state.initialized:
        # Display current elevator status
        st.header("Current Elevator Status")
        display_elevator_status()

        # Request form
        st.header("Request an Elevator")
        col1, col2 = st.columns(2)
        with col1:
            origin_floor = st.selectbox(
                "From Floor:", range(st.session_state.num_floors)
            )
        with col2:
            # Set a default destination floor that's different from origin
            default_destination = (origin_floor + 1) % st.session_state.num_floors
            destination_floor = st.selectbox(
                "To Floor:",
                range(st.session_state.num_floors),
                index=default_destination,
            )

        # Disable the button if origin and destination are the same
        button_disabled = origin_floor == destination_floor
        if button_disabled:
            st.error("Origin and destination floors must be different.")

        request_clicked = st.button("Request Elevator", disabled=button_disabled)

        if request_clicked:
            success = request_elevator(origin_floor, destination_floor)
            if success:
                st.rerun()

        # Display the last action message at the top level
        if hasattr(st.session_state, "last_action") and st.session_state.last_action:
            action_type = getattr(st.session_state, "last_action_type", "info")
            if action_type == "success":
                st.success(st.session_state.last_action)
            elif action_type == "info":
                st.info(st.session_state.last_action)
            elif action_type == "warning":
                st.warning(st.session_state.last_action)
            else:
                st.error(st.session_state.last_action)

        # Simulation section
        st.header("Simulation Tools")
        col1, col2 = st.columns(2)
        with col1:
            num_requests = st.slider("Number of Random Requests", 1, 50, 10)
            if st.button("Simulate Random Requests"):
                with st.spinner(f"Simulating {num_requests} random requests..."):
                    simulate_random_requests(num_requests)
                st.rerun()

        with col2:
            optimal_clicked = st.button("Move to Optimal Resting Floors")
            if optimal_clicked:
                success = move_to_optimal_resting_floor()
                if success:
                    st.rerun()

        # Request history
        if st.session_state.request_history:
            st.header("Request History")
            history_df = pd.DataFrame(st.session_state.request_history)
            st.dataframe(history_df)

        # Statistics
        if st.session_state.show_stats:
            st.header("System Statistics")
            display_statistics()
    else:
        st.info("Please initialize the elevator system using the sidebar controls.")


if __name__ == "__main__":
    main()
