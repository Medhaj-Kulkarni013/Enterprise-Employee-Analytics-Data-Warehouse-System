-- =====================================================================
-- Targeted employee synchronization: OLTP -> dw.Dim_Employee + existing facts
--
-- Requirements:
--   * MySQL 8.0.16 or newer (same baseline as the project's OLAP install).
--   * Existing oltp.employee, oltp.employee_change_log, oltp.department,
--     oltp.job_role, dw.Dim_Employee, dw.Dim_Department and
--     dw.Fact_PerformanceReviews tables.
--   * A Hire event on hire_date for the employee, followed by zero or more
--     dated employment-change events.
--
-- Deployment:
--   Run this file once in the target database after the OLAP schema exists.
--   It replaces ONLY dw.sp_sync_employee_scd2. It does not drop/recreate
--   schemas or tables, delete/truncate rows, or invoke the full ETL.
--
-- Runtime:
--   The procedure does not START, COMMIT or ROLLBACK a transaction.
--   Call it inside the same transaction as the corresponding OLTP update and
--   employee_change_log insert. A SIGNAL error must cause the caller to roll
--   back that transaction.
-- =====================================================================

DROP PROCEDURE IF EXISTS dw.sp_sync_employee_scd2;

DELIMITER $$

CREATE PROCEDURE dw.sp_sync_employee_scd2(
    IN p_employee_id INT UNSIGNED
)
BEGIN
    DECLARE v_employee_count INT DEFAULT 0;
    DECLARE v_event_count INT DEFAULT 0;
    DECLARE v_hire_event_count INT DEFAULT 0;
    DECLARE v_valid_hire_event_count INT DEFAULT 0;
    DECLARE v_missing_department_count INT DEFAULT 0;
    DECLARE v_latest_mismatch_count INT DEFAULT 0;
    DECLARE v_dimension_count INT DEFAULT 0;
    DECLARE v_current_count INT DEFAULT 0;
    DECLARE v_unmatched_fact_count INT DEFAULT 0;
    DECLARE v_fact_mismatch_count INT DEFAULT 0;
    DECLARE v_hire_date DATE;
    DECLARE v_first_event_date DATE;
    DECLARE v_message VARCHAR(300);

    -- 0) Validate the source employee and its complete employment history.
    SELECT COUNT(*)
      INTO v_employee_count
      FROM oltp.employee
     WHERE employee_id = p_employee_id;

    IF v_employee_count <> 1 THEN
        SET v_message = CONCAT(
            'Employee ', p_employee_id,
            ' does not exist exactly once in oltp.employee'
        );
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_message;
    END IF;

    SELECT hire_date
      INTO v_hire_date
      FROM oltp.employee
     WHERE employee_id = p_employee_id;

    SELECT COUNT(*),
       MIN(effective_date),
       COALESCE(SUM(change_type = 'Hire'), 0),
       COALESCE(
           SUM(change_type = 'Hire' AND effective_date = v_hire_date),
           0
       )
    INTO v_event_count,
        v_first_event_date,
        v_hire_event_count,
        v_valid_hire_event_count
    FROM oltp.employee_change_log
    WHERE employee_id = p_employee_id;


    IF v_event_count = 0 THEN
        SET v_message = CONCAT(
            'Employee ', p_employee_id,
            ' has no rows in oltp.employee_change_log'
        );
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_message;
    END IF;

    IF v_hire_event_count <> 1
    OR v_valid_hire_event_count <> 1
    OR v_first_event_date <> v_hire_date THEN
    SET v_message = CONCAT(
            'Employee ', p_employee_id,
            ' must have exactly one Hire event on hire_date'
        );
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_message;
    END IF;

    -- Every historical department must already exist in the warehouse
    -- department dimension because review facts reference its surrogate key.
    SELECT COUNT(*)
      INTO v_missing_department_count
      FROM oltp.employee_change_log l
      LEFT JOIN dw.Dim_Department dd
        ON dd.department_id = l.department_id
     WHERE l.employee_id = p_employee_id
       AND dd.department_key IS NULL;

    IF v_missing_department_count <> 0 THEN
        SET v_message = CONCAT(
            'Employee ', p_employee_id,
            ' has employment history referencing a department missing from dw.Dim_Department'
        );
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_message;
    END IF;

    -- The latest immutable history event must agree with the current OLTP
    -- tracked attributes. Do not silently build a warehouse from conflicting
    -- source records.
    SELECT COUNT(*)
      INTO v_latest_mismatch_count
      FROM oltp.employee e
      JOIN oltp.employee_change_log l
        ON l.employee_id = e.employee_id
       AND l.effective_date = (
            SELECT MAX(l2.effective_date)
              FROM oltp.employee_change_log l2
             WHERE l2.employee_id = e.employee_id
       )
     WHERE e.employee_id = p_employee_id
       AND (
            NOT (l.department_id <=> e.department_id)
         OR NOT (l.job_role_id <=> e.job_role_id)
         OR NOT (l.job_level <=> e.job_level)
         OR NOT (l.monthly_income <=> e.monthly_income)
       );

    IF v_latest_mismatch_count <> 0 THEN
        SET v_message = CONCAT(
            'Employee ', p_employee_id,
            ' latest change-log values do not match oltp.employee'
        );
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_message;
    END IF;

    -- 1) Insert any missing SCD2 versions from the authoritative event log.
    --    The unique (employee_id, start_date) key makes this safe to rerun.
    INSERT INTO dw.Dim_Employee
        (
            employee_id,
            employee_code,
            first_name,
            last_name,
            email,
            gender,
            date_of_birth,
            education_level,
            education_field,
            business_travel,
            overtime_flag,
            hire_date,
            department_id,
            department_name,
            job_role_name,
            job_level,
            monthly_income,
            attrition_flag,
            termination_date,
            start_date,
            end_date,
            is_current,
            version_no,
            row_hash
        )
    WITH employee_versions AS (
        SELECT
            l.employee_id,
            l.effective_date,
            l.department_id,
            l.job_role_id,
            l.job_level,
            l.monthly_income,
            ROW_NUMBER() OVER (
                PARTITION BY l.employee_id
                ORDER BY l.effective_date, l.change_id
            ) AS version_no,
            LEAD(l.effective_date) OVER (
                PARTITION BY l.employee_id
                ORDER BY l.effective_date, l.change_id
            ) AS next_start_date
        FROM oltp.employee_change_log l
        WHERE l.employee_id = p_employee_id
    )
    SELECT
        e.employee_id,
        e.employee_code,
        e.first_name,
        e.last_name,
        e.email,
        e.gender,
        e.date_of_birth,
        e.education_level,
        e.education_field,
        e.business_travel,
        e.overtime_flag,
        e.hire_date,
        v.department_id,
        dep.department_name,
        jr.job_role_name,
        v.job_level,
        v.monthly_income,
        1 - e.is_active,
        e.termination_date,
        v.effective_date,
        COALESCE(
            DATE_SUB(v.next_start_date, INTERVAL 1 DAY),
            DATE '9999-12-31'
        ),
        (v.next_start_date IS NULL),
        v.version_no,
        MD5(CONCAT_WS(
            '|',
            v.department_id,
            v.job_role_id,
            v.job_level,
            v.monthly_income
        ))
    FROM employee_versions v
    JOIN oltp.employee e
      ON e.employee_id = v.employee_id
    JOIN oltp.department dep
      ON dep.department_id = v.department_id
    JOIN oltp.job_role jr
      ON jr.job_role_id = v.job_role_id
    WHERE NOT EXISTS (
        SELECT 1
          FROM dw.Dim_Employee existing_version
         WHERE existing_version.employee_id = v.employee_id
           AND existing_version.start_date = v.effective_date
    );

    -- 2) Reconcile all SCD2-tracked values and version boundaries from the
    --    complete source history. This also repairs stale values on existing
    --    rows without deleting historical dimension records.
    WITH employee_versions AS (
        SELECT
            l.employee_id,
            l.effective_date,
            l.department_id,
            l.job_role_id,
            l.job_level,
            l.monthly_income,
            ROW_NUMBER() OVER (
                PARTITION BY l.employee_id
                ORDER BY l.effective_date, l.change_id
            ) AS version_no,
            LEAD(l.effective_date) OVER (
                PARTITION BY l.employee_id
                ORDER BY l.effective_date, l.change_id
            ) AS next_start_date
        FROM oltp.employee_change_log l
        WHERE l.employee_id = p_employee_id
    )
    UPDATE dw.Dim_Employee d
    JOIN employee_versions v
      ON v.employee_id = d.employee_id
     AND v.effective_date = d.start_date
    JOIN oltp.department dep
      ON dep.department_id = v.department_id
    JOIN oltp.job_role jr
      ON jr.job_role_id = v.job_role_id
    SET d.department_id = v.department_id,
        d.department_name = dep.department_name,
        d.job_role_name = jr.job_role_name,
        d.job_level = v.job_level,
        d.monthly_income = v.monthly_income,
        d.end_date = COALESCE(
            DATE_SUB(v.next_start_date, INTERVAL 1 DAY),
            DATE '9999-12-31'
        ),
        d.is_current = (v.next_start_date IS NULL),
        d.version_no = v.version_no,
        d.row_hash = MD5(CONCAT_WS(
            '|',
            v.department_id,
            v.job_role_id,
            v.job_level,
            v.monthly_income
        ))
    WHERE d.employee_id = p_employee_id;

    -- 3) Refresh Type 1 employee attributes on every historical version.
    UPDATE dw.Dim_Employee d
    JOIN oltp.employee e
      ON e.employee_id = d.employee_id
    SET d.employee_code = e.employee_code,
        d.first_name = e.first_name,
        d.last_name = e.last_name,
        d.email = e.email,
        d.gender = e.gender,
        d.date_of_birth = e.date_of_birth,
        d.education_level = e.education_level,
        d.education_field = e.education_field,
        d.business_travel = e.business_travel,
        d.overtime_flag = e.overtime_flag,
        d.hire_date = e.hire_date,
        d.attrition_flag = 1 - e.is_active,
        d.termination_date = e.termination_date
    WHERE d.employee_id = p_employee_id;

    -- 4) Repoint existing review facts to the employee version valid on the
    --    review date, and refresh the corresponding department and income.
    UPDATE dw.Fact_PerformanceReviews f
    JOIN oltp.review r
      ON r.review_id = f.review_id
    JOIN dw.Dim_Employee de
      ON de.employee_id = r.employee_id
     AND r.review_date BETWEEN de.start_date AND de.end_date
    JOIN dw.Dim_Department dd
      ON dd.department_id = de.department_id
    SET f.employee_key = de.employee_key,
        f.department_key = dd.department_key,
        f.monthly_income_at_review = de.monthly_income
    WHERE r.employee_id = p_employee_id;

    -- 5) Validate that the dimension now contains exactly one row per source
    --    history event, and exactly one current version for this employee.
    SELECT COUNT(*)
      INTO v_dimension_count
      FROM dw.Dim_Employee
     WHERE employee_id = p_employee_id;

    IF v_dimension_count <> v_event_count THEN
        SET v_message = CONCAT(
            'Employee ', p_employee_id,
            ' has ', v_dimension_count,
            ' dimension rows but ', v_event_count,
            ' change-log events; refusing to leave inconsistent history'
        );
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_message;
    END IF;

    SELECT COUNT(*)
      INTO v_current_count
      FROM dw.Dim_Employee
     WHERE employee_id = p_employee_id
       AND is_current = 1;

    IF v_current_count <> 1 THEN
        SET v_message = CONCAT(
            'Employee ', p_employee_id,
            ' has ', v_current_count,
            ' current dimension rows; expected exactly one'
        );
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_message;
    END IF;

    -- 6) Every existing fact for this employee must have a matching version
    --    for its review date; otherwise the fact update above could not map it.
    SELECT COUNT(*)
      INTO v_unmatched_fact_count
      FROM dw.Fact_PerformanceReviews f
      JOIN oltp.review r
        ON r.review_id = f.review_id
      LEFT JOIN dw.Dim_Employee de
        ON de.employee_id = r.employee_id
       AND r.review_date BETWEEN de.start_date AND de.end_date
     WHERE r.employee_id = p_employee_id
       AND de.employee_key IS NULL;

    IF v_unmatched_fact_count <> 0 THEN
        SET v_message = CONCAT(
            'Employee ', p_employee_id,
            ' has review facts without a matching employee dimension version'
        );
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_message;
    END IF;

    SELECT COUNT(*)
      INTO v_fact_mismatch_count
      FROM dw.Fact_PerformanceReviews f
      JOIN oltp.review r
        ON r.review_id = f.review_id
      JOIN dw.Dim_Employee de
        ON de.employee_id = r.employee_id
       AND r.review_date BETWEEN de.start_date AND de.end_date
      JOIN dw.Dim_Department dd
        ON dd.department_id = de.department_id
     WHERE r.employee_id = p_employee_id
       AND (
            f.employee_key <> de.employee_key
         OR f.department_key <> dd.department_key
         OR f.monthly_income_at_review <> de.monthly_income
       );

    IF v_fact_mismatch_count <> 0 THEN
        SET v_message = CONCAT(
            'Employee ', p_employee_id,
            ' has ', v_fact_mismatch_count,
            ' review facts that did not synchronize correctly'
        );
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_message;
    END IF;
END$$

DELIMITER ;
