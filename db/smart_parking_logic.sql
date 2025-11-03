-- --- COMPREHENSIVE CLEANUP (V4) ---
-- This block will DROP all procedures, functions, and triggers
-- to replace them with the new, simpler logic.

DROP PROCEDURE IF EXISTS sp_BookReservation;
DROP PROCEDURE IF EXISTS sp_UserCheckIn;
DROP PROCEDURE IF EXISTS sp_UserCheckOut;
DROP PROCEDURE IF EXISTS sp_ReleaseReservation; -- Dropping in case it exists
DROP PROCEDURE IF EXISTS sp_AddUser;
DROP PROCEDURE IF EXISTS sp_CancelReservation;
DROP PROCEDURE IF EXISTS sp_DeactivateUser;
DROP PROCEDURE IF EXISTS sp_GetUserDetails;
DROP PROCEDURE IF EXISTS sp_MakePayment;
DROP PROCEDURE IF EXISTS sp_ReleaseParking;
DROP PROCEDURE IF EXISTS sp_ReserveParking;
DROP PROCEDURE IF EXISTS sp_UpdateUserDetail;

DROP FUNCTION IF EXISTS fn_CalculateFee;
DROP FUNCTION IF EXISTS fn_CheckAvailability;
DROP FUNCTION IF EXISTS fn_CalculateParkingFee;
DROP FUNCTION IF EXISTS fn_GetSpaceAvailability;
DROP FUNCTION IF EXISTS CheckSpaceAvailability;
DROP FUNCTION IF EXISTS CalculateParkingFee;
DROP FUNCTION IF EXISTS fn_CalculateParkingF;
DROP FUNCTION IF EXISTS fn_GetSpaceAvailabi;

DROP TRIGGER IF EXISTS trg_AfterUpdateOccupancyLog;
DROP TRIGGER IF EXISTS trg_AfterLogExit;
DROP TRIGGER IF EXISTS trg_BeforeUserDeactivate;
DROP TRIGGER IF EXISTS trg_BeforeReservationInsert;
DROP TRIGGER IF EXISTS trg_AfterInsertReservation;
DROP TRIGGER IF EXISTS trg_AfterUpdateReservation;
DROP TRIGGER IF EXISTS trg_BeforeInsertReservation;
DROP TRIGGER IF EXISTS trg_AfterReservationBooked;
DROP TRIGGER IF EXISTS trg_AfterReservationFinished;
DROP TRIGGER IF EXISTS trg_AfterReservationComplete;
-- --- END CLEANUP ---

DROP PROCEDURE IF EXISTS sp_ReleaseReservation;


-- -----------------------------------------------------
-- Function fn_CalculateFee
-- (Used to calculate final bill at release)
-- -----------------------------------------------------
DELIMITER $$
CREATE FUNCTION `fn_CalculateFee`(
    p_start_time DATETIME,
    p_end_time DATETIME
) RETURNS decimal(10,2)
    DETERMINISTIC
BEGIN
    DECLARE v_hours DECIMAL(10,2);
    DECLARE v_fee DECIMAL(10,2);
    -- Calculate duration in hours
    SET v_hours = TIMESTAMPDIFF(MINUTE, p_start_time, p_end_time) / 60.0;
    -- Simple fee: $20 per hour
    SET v_fee = v_hours * 20.00;
    -- Minimum fee of $10
    IF v_fee < 10.00 THEN
        SET v_fee = 10.00;
    END IF;
    RETURN v_fee;
END$$
DELIMITER ;

-- -----------------------------------------------------
-- Function fn_CheckAvailability
-- (Used to check for reservation conflicts)
-- -----------------------------------------------------
DELIMITER $$
CREATE FUNCTION `fn_CheckAvailability`(
    p_space_id VARCHAR(10),
    p_start_time DATETIME,
    p_end_time DATETIME
) RETURNS tinyint(1)
    DETERMINISTIC
BEGIN
    DECLARE v_count INT;
    -- Check for any overlapping reservations for the same space
    SELECT COUNT(*) INTO v_count
    FROM RESERVATION
    WHERE SPACE_ID = p_space_id
    AND (
        (p_start_time < END_TIME) AND (p_end_time > START_TIME)
    )
    AND STATUS = 'Booked';
    
    IF v_count > 0 THEN
        RETURN 0; -- Not available
    ELSE
        RETURN 1; -- Available
    END IF;
END$$
DELIMITER ;

-- -----------------------------------------------------
-- Procedure sp_BookReservation (NEW LOGIC)
-- (Creates reservation, sets space to Occupied)
-- -----------------------------------------------------
DELIMITER $$
CREATE PROCEDURE `sp_BookReservation`(
    IN p_user_id VARCHAR(10),
    IN p_space_id VARCHAR(10),
    IN p_start_time DATETIME,
    IN p_end_time DATETIME
)
BEGIN
    DECLARE v_res_id VARCHAR(10);
    DECLARE v_is_available INT;
    DECLARE v_max_res_num INT;

    -- Check availability
    SET v_is_available = fn_CheckAvailability(p_space_id, p_start_time, p_end_time);

    IF v_is_available = 0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Error: Space is not available for the selected time.';
    ELSE
        -- 1. Generate new, robust Reservation ID
        SELECT IFNULL(MAX(CAST(SUBSTRING(RES_ID, 2) AS UNSIGNED)), 0) INTO v_max_res_num FROM RESERVATION;
        SET v_res_id = CONCAT('R', LPAD(v_max_res_num + 1, 3, '0'));

        -- 2. Insert into RESERVATION
        -- (trg_BeforeReservationInsert will check user status)
        INSERT INTO RESERVATION (RES_ID, USER_ID, SPACE_ID, START_TIME, END_TIME, STATUS)
        VALUES (v_res_id, p_user_id, p_space_id, p_start_time, p_end_time, 'Booked');
        
        -- 3. Update PARKING_SPACE status
        UPDATE PARKING_SPACE
        SET STATUS = 'Occupied'
        WHERE SPACE_ID = p_space_id;
        
        -- 4. NO PAYMENT INSERTED. Bill is generated at release.
        
        -- 5. Send success message
        SELECT 'Reservation successful! Space is now marked as Occupied.' AS message;

    END IF;
END$$
DELIMITER ;

-- -----------------------------------------------------
-- NEW Procedure sp_ReleaseReservation
-- (Generates bill, completes reservation, frees space)
-- -----------------------------------------------------
-- Re-create the procedure with the new logic
DELIMITER $$
CREATE PROCEDURE `sp_ReleaseReservation`(
    IN p_res_id VARCHAR(10)
)
BEGIN
    -- Declare all necessary variables
    DECLARE v_space_id VARCHAR(10);
    DECLARE v_user_id VARCHAR(10); -- Added this to fetch the USER_ID
    DECLARE v_start_time DATETIME;
    DECLARE v_end_time DATETIME;
    DECLARE v_current_status ENUM('Booked', 'Completed', 'Cancelled');
    DECLARE v_pay_id VARCHAR(10);
    DECLARE v_amount DECIMAL(10,2);
    DECLARE v_max_pay_num INT;
    DECLARE v_log_id VARCHAR(10); -- Added for the log
    DECLARE v_max_log_num INT; -- Added for the log

    -- Find the reservation to release
    -- *** MODIFIED to fetch USER_ID ***
    SELECT USER_ID, SPACE_ID, START_TIME, END_TIME, STATUS
    INTO v_user_id, v_space_id, v_start_time, v_end_time, v_current_status
    FROM RESERVATION
    WHERE RES_ID = p_res_id;
    
    IF v_space_id IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Error: Reservation ID not found.';
    ELSEIF v_current_status != 'Booked' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Error: This reservation is already completed or cancelled.';
    ELSE
        -- 1. Calculate the fee
        SET v_amount = fn_CalculateFee(v_start_time, v_end_time);
        
        -- 2. Generate new Payment ID
        SELECT IFNULL(MAX(CAST(SUBSTRING(PAYMENT_ID, 4) AS UNSIGNED)), 0) INTO v_max_pay_num FROM PAYMENT;
        SET v_pay_id = CONCAT('PAY', LPAD(v_max_pay_num + 1, 3, '0'));
        
        -- 3. Create PAYMENT entry
        INSERT INTO PAYMENT (PAYMENT_ID, RES_ID, AMOUNT, TIME_STAMP, PAYMENT_STATUS)
        VALUES (v_pay_id, p_res_id, v_amount, NOW(), 'Pending');
    
        -- 4. Update the RESERVATION status
        UPDATE RESERVATION
        SET STATUS = 'Completed'
        WHERE RES_ID = p_res_id;
        
        -- 5. Update the PARKING_SPACE status
        UPDATE PARKING_SPACE
        SET STATUS = 'Available'
        WHERE SPACE_ID = v_space_id;
        
        -- --- *** NEW LOGIC START *** ---
        -- 6. Generate new Log ID
        SELECT IFNULL(MAX(CAST(SUBSTRING(LOG_ID, 2) AS UNSIGNED)), 0) INTO v_max_log_num FROM OCCUPANCY_LOG;
        SET v_log_id = CONCAT('L', LPAD(v_max_log_num + 1, 3, '0'));
        
        -- 7. Create OCCUPANCY_LOG entry
        -- We use the reservation's start/end time as the log's entry/exit time
        INSERT INTO OCCUPANCY_LOG (LOG_ID, USER_ID, SPACE_ID, ENTRY_TIME, EXIT_TIME)
        VALUES (v_log_id, v_user_id, v_space_id, v_start_time, v_end_time);
        -- --- *** NEW LOGIC END *** ---
        
        -- 8. Send success message
        SELECT 'Reservation released. Bill and Occupancy Log created.' AS message, v_pay_id AS new_payment_id;
    END IF;
END$$
DELIMITER ;

-- -----------------------------------------------------
-- TRIGGER 1: trg_BeforeUserDeactivate (Kept)
-- Enforces: "user cant deactivate account if they have pending bills"
-- -----------------------------------------------------
DELIMITER $$
CREATE TRIGGER `trg_BeforeUserDeactivate`
BEFORE UPDATE ON `USERS`
FOR EACH ROW
BEGIN
    DECLARE v_pending_payments INT;
    IF NEW.STATUS = 'Inactive' AND OLD.STATUS = 'Active' THEN
        SELECT COUNT(*) INTO v_pending_payments
        FROM PAYMENT p
        JOIN RESERVATION r ON p.RES_ID = r.RES_ID
        WHERE r.USER_ID = OLD.USER_ID AND p.PAYMENT_STATUS = 'Pending';
        
        IF v_pending_payments > 0 THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Error: User has pending payments. Cannot deactivate account.';
        END IF;
    END IF;
END$$
DELIMITER ;

-- -----------------------------------------------------
-- TRIGGER 2: trg_BeforeReservationInsert (Kept)
-- Enforces: "deactivated users cant make a reservation"
-- -----------------------------------------------------
DELIMITER $$
CREATE TRIGGER `trg_BeforeReservationInsert`
BEFORE INSERT ON `RESERVATION`
FOR EACH ROW
BEGIN
    DECLARE v_user_status ENUM('Active', 'Inactive');
    SELECT STATUS INTO v_user_status FROM USERS WHERE USER_ID = NEW.USER_ID;
    
    IF v_user_status = 'Inactive' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Error: Deactivated users cannot make new reservations.';
    END IF;
END$$
DELIMITER ;