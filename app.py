import streamlit as st
import mysql.connector
import pandas as pd
from datetime import datetime, date, time

# -----------------------------------------------------------------
# DATABASE HELPER FUNCTIONS
# -----------------------------------------------------------------

# Function to get a database connection
def get_db_connection():
    """Establishes a connection to the MySQL database using secrets."""
    try:
        conn = mysql.connector.connect(
            host=st.secrets["mysql"]["host"],
            user=st.secrets["mysql"]["user"],
            password=st.secrets["mysql"]["password"],
            database=st.secrets["mysql"]["database"],
            autocommit=True  # Ensure data is committed after each operation
        )
        return conn
    except mysql.connector.Error as err:
        st.error(f"Error connecting to database: {err}")
        return None

# Function to run a query and fetch all results (for SELECT)
def fetch_query(query, params=None):
    """Runs a SELECT query and returns a DataFrame."""
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute(query, params)
                results = cursor.fetchall()
                return pd.DataFrame(results) if results else pd.DataFrame()
        except mysql.connector.Error as err:
            st.error(f"Database Query Error: {err.msg}")
        finally:
            if conn.is_connected():
                conn.close()
    return pd.DataFrame()

# Function to execute a command (for INSERT, UPDATE, DELETE)
def execute_command(query, params=None):
    """Runs an INSERT, UPDATE, or DELETE command."""
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor() as cursor:
                cursor.execute(query, params)
                conn.commit()
            return True
        except mysql.connector.Error as err:
            st.error(f"Database Command Error: {err.msg}")
        finally:
            if conn.is_connected():
                conn.close()
    return False

# Function to call a stored procedure
def call_procedure(proc_name, args=()):
    """Calls a stored procedure and returns any results."""
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor(dictionary=True) as cursor:
                cursor.callproc(proc_name, args)
                # Handle results from procedures
                results = []
                for result in cursor.stored_results():
                    results.extend(result.fetchall())
                
                conn.commit() # Commit any changes made by the procedure
                
                if results:
                    return pd.DataFrame(results)
                return True # Success
        except mysql.connector.Error as err:
            st.error(f"Procedure Error ({proc_name}): {err.msg}")
        finally:
            if conn.is_connected():
                conn.close()
    return False

# -----------------------------------------------------------------
# FEATURE: DASHBOARD
# -----------------------------------------------------------------
def show_dashboard():
    st.header("Parking Lot Status")
    st.write("Live view of all parking spaces.")
    
    spaces_df = fetch_query("SELECT SPACE_ID, LOCATION, STATUS, PRIORITY FROM PARKING_SPACE ORDER BY SPACE_ID")
    
    if spaces_df.empty:
        st.warning("No parking spaces found in the database.")
        return

    cols = st.columns(4)
    for index, row in spaces_df.iterrows():
        col = cols[index % 4]
        with col.container(border=True):
            if row['STATUS'] == 'Available':
                st.success(f"**{row['SPACE_ID']}**")
            else:
                st.error(f"**{row['SPACE_ID']}**")
            st.write(f"_{row['LOCATION']}_")
            st.caption(f"Priority: {row['PRIORITY']}")

# -----------------------------------------------------------------
# FEATURE: USER MANAGEMENT
# -----------------------------------------------------------------
def show_user_management():
    st.header("User Management")
    
    tabs = st.tabs(["Find User", "Add User", "Update User", "Delete User"])

    # --- Find User Tab ---
    with tabs[0]:
        st.subheader("Find User Details")
        user_id_find = st.text_input("Enter User ID to Find", key="find_user_id").upper().strip()
        if st.button("Find User", key="find_user_btn"):
            if user_id_find:
                user_df = fetch_query("SELECT * FROM USERS WHERE USER_ID = %s", (user_id_find,))
                if not user_df.empty:
                    st.dataframe(user_df)
                else:
                    st.warning("User not found.")
            else:
                st.info("Please enter a User ID.")

    # --- Add User Tab ---
    with tabs[1]:
        st.subheader("Add a New User")
        with st.form("add_user_form", clear_on_submit=True):
            user_id = st.text_input("User ID (e.g., CS003)").upper().strip()
            col1, col2 = st.columns(2)
            first_name = col1.text_input("First Name")
            last_name = col2.text_input("Last Name")
            email = st.text_input("Email").strip()
            phone_num = st.text_input("Phone Number").strip()
            vehicle_no = st.text_input("Vehicle Number").upper().strip()
            user_type = st.selectbox("User Type", ['Student', 'Faculty', 'Staff'])
            
            submitted = st.form_submit_button("Add User")
            if submitted:
                if all([user_id, first_name, last_name, email, phone_num, vehicle_no, user_type]):
                    query = """
                        INSERT INTO USERS (USER_ID, FIRST_NAME, LAST_NAME, EMAIL, PHONE_NUM, VEHICLE_NO, USER_TYPE, STATUS)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, 'Active')
                    """
                    params = (user_id, first_name, last_name, email, phone_num, vehicle_no, user_type)
                    if execute_command(query, params):
                        st.success(f"User '{first_name} {last_name}' ({user_id}) added successfully!")
                    # Error is handled by execute_command
                else:
                    st.error("Please fill out all fields.")

    # --- Update User Tab ---
    with tabs[2]:
        st.subheader("Update User Details")
        user_id_update = st.text_input("Enter User ID to Update", key="update_user_id").upper().strip()
        
        if user_id_update:
            user_data_df = fetch_query("SELECT * FROM USERS WHERE USER_ID = %s", (user_id_update,))
            if not user_data_df.empty:
                user_data = user_data_df.iloc[0]
                
                with st.form("update_user_form"):
                    st.write(f"Updating details for: **{user_data['FIRST_NAME']} {user_data['LAST_NAME']}**")
                    
                    email = st.text_input("Email", value=user_data['EMAIL']).strip()
                    phone_num = st.text_input("Phone Number", value=user_data['PHONE_NUM']).strip()
                    vehicle_no = st.text_input("Vehicle Number", value=user_data['VEHICLE_NO']).upper().strip()
                    
                    user_type_options = ['Student', 'Faculty', 'Staff']
                    user_type_index = user_type_options.index(user_data['USER_TYPE'])
                    user_type = st.selectbox("User Type", user_type_options, index=user_type_index)
                    
                    status_options = ['Active', 'Inactive']
                    status_index = status_options.index(user_data['STATUS'])
                    status = st.selectbox("Account Status", status_options, index=status_index)
                    
                    update_submitted = st.form_submit_button("Update User")
                    if update_submitted:
                        # Client-side check (also enforced by trigger trg_BeforeUserDeactivate)
                        if status == 'Inactive' and user_data['STATUS'] == 'Active':
                            pending_df = fetch_query("""
                                SELECT COUNT(*) as pending_count 
                                FROM PAYMENT p
                                JOIN RESERVATION r ON p.RES_ID = r.RES_ID
                                WHERE r.USER_ID = %s AND p.PAYMENT_STATUS = 'Pending'
                            """, (user_id_update,))
                            
                            pending_count = 0
                            if not pending_df.empty:
                                pending_count = pending_df.iloc[0]['pending_count']

                            if pending_count > 0:
                                st.error("Cannot deactivate user. User has pending payments.")
                            else:
                                # Proceed with update
                                query = """
                                    UPDATE USERS SET EMAIL = %s, PHONE_NUM = %s, VEHICLE_NO = %s, USER_TYPE = %s, STATUS = %s
                                    WHERE USER_ID = %s
                                """
                                params = (email, phone_num, vehicle_no, user_type, status, user_id_update)
                                if execute_command(query, params):
                                    st.success(f"User {user_id_update} updated successfully!")
                                    st.rerun()
                        else:
                            # Proceed with normal update
                            query = """
                                UPDATE USERS SET EMAIL = %s, PHONE_NUM = %s, VEHICLE_NO = %s, USER_TYPE = %s, STATUS = %s
                                WHERE USER_ID = %s
                            """
                            params = (email, phone_num, vehicle_no, user_type, status, user_id_update)
                            if execute_command(query, params):
                                st.success(f"User {user_id_update} updated successfully!")
                                st.rerun()
            else:
                st.warning("User not found. Please enter a valid User ID.")

    # --- Delete User Tab ---
    with tabs[3]:
        st.subheader("Delete User Account")
        st.warning("This action is permanent and cannot be undone.")
        user_id_del = st.text_input("Enter User ID to Delete", key="delete_user_id").upper().strip()
        
        if st.button("Delete User", key="delete_user_btn", type="primary"):
            if user_id_del:
                # Client-side check (also enforced by trigger)
                pending_df = fetch_query("""
                    SELECT COUNT(*) as pending_count 
                    FROM PAYMENT p
                    JOIN RESERVATION r ON p.RES_ID = r.RES_ID
                    WHERE r.USER_ID = %s AND p.PAYMENT_STATUS = 'Pending'
                """, (user_id_del,))
                
                pending_count = 0
                if not pending_df.empty:
                    pending_count = pending_df.iloc[0]['pending_count']
                
                if pending_count > 0:
                    st.error("Cannot delete user. User has pending payments.")
                else:
                    if execute_command("DELETE FROM USERS WHERE USER_ID = %s", (user_id_del,)):
                        st.success(f"User {user_id_del} deleted successfully.")
            else:
                st.info("Please enter a User ID.")

# -----------------------------------------------------------------
# FEATURE: PARKING & RESERVATIONS (*** MODIFIED ***)
# -----------------------------------------------------------------
def show_parking_reservations():
    st.header("Parking & Reservations")
    
    # --- MODIFIED TABS ---
    tabs = st.tabs(["Make Reservation", "Release Reservation", "View All Reservations"])

    # --- Make Reservation Tab ---
    with tabs[0]:
        st.subheader("Book a Parking Space")
        
        # Load *only* available spaces for the selectbox
        spaces_df = fetch_query("SELECT SPACE_ID, LOCATION FROM PARKING_SPACE WHERE STATUS = 'Available' ORDER BY SPACE_ID")
        if spaces_df.empty:
            st.error("No available parking spaces found.")
            return

        spaces_list = [f"{row['SPACE_ID']} - {row['LOCATION']}" for _, row in spaces_df.iterrows()]
        
        with st.form("book_reservation_form", clear_on_submit=True):
            user_id = st.text_input("User ID").upper().strip()
            selected_space = st.selectbox("Select Parking Space", spaces_list)
            
            if not selected_space:
                 st.error("No available spaces to select.")
                 st.form_submit_button("Book Reservation", disabled=True)
                 return

            space_id = selected_space.split(' - ')[0]
            
            st.write("Select Start Time & Date")
            col1, col2 = st.columns(2)
            start_date = col1.date_input("Start Date", min_value=date.today())
            start_time = col2.time_input("Start Time", value=time(9, 0)) # Default to 9:00 AM
            
            st.write("Select End Time & Date")
            col3, col4 = st.columns(2)
            end_date = col3.date_input("End Date", min_value=start_date)
            end_time = col4.time_input("End Time", value=time(17, 0)) # Default to 5:00 PM
            
            book_submitted = st.form_submit_button("Book Reservation")
            
            if book_submitted:
                if not user_id:
                    st.error("Please enter a User ID.")
                    return

                # Combine date and time
                start_datetime = datetime.combine(start_date, start_time)
                end_datetime = datetime.combine(end_date, end_time)

                if end_datetime <= start_datetime:
                    st.error("End time must be after start time.")
                    return
                
                # Check for deactivated user (also enforced by trigger)
                user_status_df = fetch_query("SELECT STATUS FROM USERS WHERE USER_ID = %s", (user_id,))
                if user_status_df.empty:
                    st.error("User ID not found.")
                    return
                
                if user_status_df.iloc[0]['STATUS'] == 'Inactive':
                    st.error("This user is deactivated and cannot make reservations.")
                    return
                
                # Call the stored procedure
                st.info("Attempting to book...")
                args = (user_id, space_id, start_datetime, end_datetime)
                result_df = call_procedure("sp_BookReservation", args)
                
                if isinstance(result_df, pd.DataFrame) and 'message' in result_df.columns:
                    st.success(result_df.iloc[0]['message'])
                    st.balloons()
                    st.rerun() # Rerun to update dashboard and available spaces
                # Error handling is done by call_procedure

    # --- NEW "Release Reservation" Tab ---
    with tabs[1]:
        st.subheader("Release a Reservation")
        st.write("This will complete the reservation, generate the bill, and free the parking space.")

        # Fetch active reservations to make selection easier
        active_reservations_df = fetch_query("""
            SELECT RES_ID, USER_ID, SPACE_ID, START_TIME, END_TIME 
            FROM RESERVATION 
            WHERE STATUS = 'Booked'
            ORDER BY START_TIME ASC
        """)
        
        if active_reservations_df.empty:
            st.info("No active reservations to release.")
            return

        st.dataframe(active_reservations_df)
        
        # Create a list of active reservation IDs for the selectbox
        active_res_ids = active_reservations_df['RES_ID'].tolist()
        
        with st.form("release_reservation_form"):
            selected_res_id = st.selectbox("Select Reservation ID to Release", active_res_ids)
            
            release_submitted = st.form_submit_button("Release Reservation & Generate Bill")
            
            if release_submitted:
                if not selected_res_id:
                    st.error("Please select a reservation to release.")
                else:
                    st.info(f"Attempting to release {selected_res_id}...")
                    args = (selected_res_id,)
                    result_df = call_procedure("sp_ReleaseReservation", args)
                    
                    if isinstance(result_df, pd.DataFrame) and 'message' in result_df.columns:
                        st.success(result_df.iloc[0]['message'])
                        st.balloons()
                        st.rerun() # Rerun to update lists and dashboard
                    # Error handling is done by call_procedure

    # --- View All Reservations Tab ---
    with tabs[2]:
        st.subheader("All Reservations")
        reservations_df = fetch_query("SELECT * FROM RESERVATION ORDER BY START_TIME DESC")
        if not reservations_df.empty:
            st.dataframe(reservations_df)
        else:
            st.info("No reservations found.")


# -----------------------------------------------------------------
# FEATURE: BILLING & PAYMENTS
# -----------------------------------------------------------------
def show_billing():
    st.header("Billing & Payments")
    st.write("View payment status and generated bills.")
    
    user_id = st.text_input("Enter User ID to View Payments").upper().strip()
    
    if user_id:
        # Fetch user details
        user_df = fetch_query("SELECT FIRST_NAME, LAST_NAME FROM USERS WHERE USER_ID = %s", (user_id,))
        if user_df.empty:
            st.error("User not found.")
            return
            
        st.subheader(f"Payments for {user_df.iloc[0]['FIRST_NAME']} {user_df.iloc[0]['LAST_NAME']}")
        
        # Query to get all payments for the user
        payments_query = """
            SELECT 
                p.PAYMENT_ID, 
                p.RES_ID, 
                r.SPACE_ID, 
                r.START_TIME, 
                r.END_TIME, 
                p.AMOUNT, 
                p.PAYMENT_STATUS, 
                p.TIME_STAMP
            FROM PAYMENT p
            JOIN RESERVATION r ON p.RES_ID = r.RES_ID
            WHERE r.USER_ID = %s
            ORDER BY p.TIME_STAMP DESC
        """
        payments_df = fetch_query(payments_query, (user_id,))
        
        if payments_df.empty:
            st.info("No payment records found for this user.")
            return

        # Display Pending Payments
        st.write("---")
        st.subheader("Pending Payments")
        pending_df = payments_df[payments_df['PAYMENT_STATUS'] == 'Pending']
        if not pending_df.empty:
            st.dataframe(pending_df)
            total_due = pending_df['AMOUNT'].sum()
            st.warning(f"**Total Amount Due: ₹{total_due:,.2f}**")

            # --- PAYMENT SECTION ---
            st.write("---")
            st.subheader("Pay a Bill")
            
            # Create a list of pending payment IDs for the selectbox
            pending_payment_ids = pending_df['PAYMENT_ID'].tolist()
            
            # Use a form for the payment action
            with st.form("pay_bill_form"):
                selected_payment_id = st.selectbox("Select Bill to Pay", pending_payment_ids)
                pay_button_submitted = st.form_submit_button("Mark as Paid")
                
                if pay_button_submitted:
                    # Create and execute the update query
                    payment_query = """
                        UPDATE PAYMENT 
                        SET PAYMENT_STATUS = 'Completed', TIME_STAMP = %s
                        WHERE PAYMENT_ID = %s
                    """
                    # Use current time for the timestamp
                    current_time = datetime.now()
                    params = (current_time, selected_payment_id)
                    
                    if execute_command(payment_query, params):
                        st.success(f"Payment {selected_payment_id} marked as completed!")
                        st.balloons()
                        st.rerun() # Rerun to refresh the data
                    else:
                        st.error("Failed to process payment.")
            # --- END PAYMENT SECTION ---

        else:
            st.success("No pending payments.")

        # Display Completed/Failed Payments (Bill History)
        st.write("---")
        st.subheader("Payment History (Bills)")
        history_df = payments_df[payments_df['PAYMENT_STATUS'] != 'Pending']
        if not history_df.empty:
            st.dataframe(history_df)
        else:
            st.info("No payment history found.")


# -----------------------------------------------------------------
# MAIN APP
# -----------------------------------------------------------------
def main():
    st.set_page_config(page_title="Smart Parking", layout="wide")
    st.title("Smart Parking Management System")

    # --- Sidebar Navigation ---
    st.sidebar.title("Navigation")
    
    # Initialize session state to keep track of the current page
    if 'page' not in st.session_state:
        st.session_state.page = "Dashboard"

    # Define a function to update the page in session state
    def set_page(page_name):
        st.session_state.page = page_name

    # Create buttons for navigation
    # Use 'type' to highlight the active page
    st.sidebar.button(
        "Dashboard",
        on_click=set_page,
        args=("Dashboard",),
        use_container_width=True,
        type="primary" if st.session_state.page == "Dashboard" else "secondary"
    )
    st.sidebar.button(
        "User Management",
        on_click=set_page,
        args=("User Management",),
        use_container_width=True,
        type="primary" if st.session_state.page == "User Management" else "secondary"
    )
    st.sidebar.button(
        "Parking & Reservations",
        on_click=set_page,
        args=("Parking & Reservations",),
        use_container_width=True,
        type="primary" if st.session_state.page == "Parking & Reservations" else "secondary"
    )
    st.sidebar.button(
        "Billing & Payments",
        on_click=set_page,
        args=("Billing & Payments",),
        use_container_width=True,
        type="primary" if st.session_state.page == "Billing & Payments" else "secondary"
    )

    # Get the current page from session state
    choice = st.session_state.page

    # --- Page Routing ---
    if choice == "Dashboard":
        show_dashboard()
    elif choice == "User Management":
        show_user_management()
    elif choice == "Parking & Reservations":
        show_parking_reservations()
    elif choice == "Billing & Payments":
        show_billing()

if __name__ == "__main__":
    main()