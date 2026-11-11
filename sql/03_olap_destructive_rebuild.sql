-- =====================================================================
-- DESTRUCTIVE REBUILD: drops and recreates dw. Does NOT drop oltp or stg.
-- Back up dw first. MySQL 8.0.16+. Run only when a full warehouse rebuild is intended.
--
-- What it does, in order (brief references in brackets):
--   1. drops and recreates schema dw with the star schema           [Phase 1 item 3, Phase 2 item 1]
--   2. creates the 9 ETL stored procedures (CTEs, window funcs)   [Phase 2 item 2]
--   3. runs the full ETL (OLTP -> OLAP) and validates it          [Phase 2 item 2]
--   4. creates the analytics views the Streamlit pages read       [Phase 4 item 2]
--   5. runs the SCD2 self-test (one grid, PASS/FAIL)              [SCD Type 2, Phase 4 item 1]
--   6. runs the final acceptance check (one grid, PASS/FAIL)
-- Last two result grids: first the SCD2 self-test (T0..T12 + OVERALL), then the acceptance check.
-- Requires: MySQL 8.0.16+, oltp already loaded (employee, employee_change_log, review, department, job_role).
-- =====================================================================
ROLLBACK;
DROP SCHEMA IF EXISTS dw;
CREATE SCHEMA IF NOT EXISTS dw DEFAULT CHARACTER SET utf8mb4;

-- ---------------------------------------------------------------------
-- 1. STAR SCHEMA
-- ---------------------------------------------------------------------
-- =====================================================================
-- 04_olap.sql  |  OLAP data warehouse: Star Schema (schema `dw`)
-- Brief reference: Phase 1, item 3 ("Design a Star Schema containing":
--   Fact table  Fact_PerformanceReviews (tracking scores, ratings)
--   Dimensions  Dim_Employee, Dim_Project, Dim_Date, Dim_Department
--   "Implement Surrogate Keys for all Dimension tables"
--   "Design Dim_Employee to support SCD Type 2 (start_date, end_date, is_current)")
--   + Phase 2, item 1 (execute the DDL in MySQL).
-- Our design choices (not named in the brief): row_hash + version_no columns on
--   Dim_Employee (change detection / ordering), an 'Unknown' row (key -1) in
--   Dim_Project, attrition_flag on Dim_Employee (needed for the attrition dashboard).
-- Safe to re-run (IF NOT EXISTS). Requires MySQL 8.0.16+.
-- =====================================================================
CREATE SCHEMA IF NOT EXISTS dw DEFAULT CHARACTER SET utf8mb4;

-- ---------------------------------------------------------------------
-- Dim_Date  (surrogate key date_key; full_date is the business key)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dw.Dim_Date (
  date_key       INT          NOT NULL AUTO_INCREMENT,
  full_date      DATE         NOT NULL,
  day_of_month   TINYINT      NOT NULL,
  day_name       VARCHAR(10)  NOT NULL,
  week_of_year   TINYINT      NOT NULL,
  month_number   TINYINT      NOT NULL,
  month_name     VARCHAR(10)  NOT NULL,
  quarter_number TINYINT      NOT NULL,
  year_number    SMALLINT     NOT NULL,
  is_weekend     TINYINT(1)   NOT NULL,
  PRIMARY KEY (date_key),
  UNIQUE KEY uq_dim_date_full (full_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------------
-- Dim_Department  (surrogate key department_key; department_id = business key)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dw.Dim_Department (
  department_key   INT         NOT NULL AUTO_INCREMENT,
  department_id    INT         NOT NULL,
  department_name  VARCHAR(50) NOT NULL,
  PRIMARY KEY (department_key),
  UNIQUE KEY uq_dim_department_bk (department_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------------
-- Dim_Project  (surrogate key project_key; project_id = business key)
-- Row -1 = 'Unknown': reviews that are not tied to a project.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dw.Dim_Project (
  project_key   INT          NOT NULL AUTO_INCREMENT,
  project_id    INT          NOT NULL,
  project_code  VARCHAR(10)  NOT NULL,
  project_name  VARCHAR(100) NOT NULL,
  project_status        VARCHAR(20)  NOT NULL,
  start_date    DATE         NULL,
  end_date      DATE         NULL,
  PRIMARY KEY (project_key),
  UNIQUE KEY uq_dim_project_bk (project_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT IGNORE INTO dw.Dim_Project (project_key, project_id, project_code, project_name, project_status)
VALUES (-1, 0, 'N/A', 'Unknown / not project-related', 'Unknown');

-- ---------------------------------------------------------------------
-- Dim_Employee  -- SCD TYPE 2
-- One employee has ONE ROW PER VERSION. employee_key (surrogate) is unique per
-- version; employee_id (business key) repeats. Tracked attributes: department,
-- job role, job level, monthly income. Current row: is_current = 1,
-- end_date = '9999-12-31'. attrition_flag/termination_date are kept identical
-- on all versions of an employee (updated in place, SCD Type 1 behaviour).
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dw.Dim_Employee (
  employee_key     INT          NOT NULL AUTO_INCREMENT,
  employee_id      INT          NOT NULL,
  employee_code    VARCHAR(10)  NOT NULL,
  first_name       VARCHAR(40)  NOT NULL,
  last_name        VARCHAR(40)  NOT NULL,
  email            VARCHAR(60)  NOT NULL,
  gender           VARCHAR(10)  NOT NULL,
  date_of_birth    DATE         NOT NULL,
  education_level  TINYINT      NOT NULL,
  education_field  VARCHAR(30)  NOT NULL,
  business_travel  VARCHAR(20)  NOT NULL,
  overtime_flag    TINYINT(1)   NOT NULL,
  hire_date        DATE         NOT NULL,
  -- tracked by SCD2 -------------------------------------------------
  department_id    INT          NOT NULL,
  department_name  VARCHAR(50)  NOT NULL,
  job_role_name    VARCHAR(50)  NOT NULL,
  job_level        TINYINT      NOT NULL,
  monthly_income   DECIMAL(10,2) NOT NULL,
  -- attrition (same on every version of the employee) ---------------
  attrition_flag   TINYINT(1)   NOT NULL DEFAULT 0,
  termination_date DATE         NULL,
  -- SCD2 housekeeping (brief: start_date, end_date, is_current) -------
  start_date       DATE         NOT NULL,
  end_date         DATE         NOT NULL DEFAULT '9999-12-31',
  is_current       TINYINT(1)   NOT NULL DEFAULT 1,
  version_no       INT          NOT NULL DEFAULT 1,
  row_hash         CHAR(32)     NOT NULL,
  PRIMARY KEY (employee_key),
  UNIQUE KEY uq_dim_employee_version (employee_id, start_date),
  KEY idx_dim_employee_lookup (employee_id, start_date, end_date),
  KEY idx_dim_employee_current (is_current, department_id),
  CONSTRAINT chk_dim_emp_dates CHECK (end_date >= start_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------------
-- Fact_PerformanceReviews   grain: one row per performance review
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dw.Fact_PerformanceReviews (
  fact_id                    BIGINT   NOT NULL AUTO_INCREMENT,
  employee_key               INT      NOT NULL,    -- the employee VERSION valid on the review date
  department_key             INT      NOT NULL,
  project_key                INT      NOT NULL DEFAULT -1,
  review_date_key            INT      NOT NULL,
  review_id                  BIGINT   NOT NULL,    -- degenerate dimension: traces back to oltp.review
  performance_rating         TINYINT  NOT NULL,
  job_satisfaction           TINYINT  NOT NULL,
  environment_satisfaction   TINYINT  NOT NULL,
  relationship_satisfaction  TINYINT  NOT NULL,
  work_life_balance          TINYINT  NOT NULL,
  job_involvement            TINYINT  NOT NULL,
  percent_salary_hike        TINYINT  NOT NULL,
  training_times_last_year   TINYINT  NOT NULL,
  monthly_income_at_review   DECIMAL(10,2) NOT NULL,
  PRIMARY KEY (fact_id),
  UNIQUE KEY uq_fact_review (review_id),
  KEY idx_fact_employee (employee_key),
  KEY idx_fact_department (department_key),
  KEY idx_fact_project (project_key),
  KEY idx_fact_date (review_date_key),
  CONSTRAINT fk_fact_employee   FOREIGN KEY (employee_key)    REFERENCES dw.Dim_Employee (employee_key),
  CONSTRAINT fk_fact_department FOREIGN KEY (department_key)  REFERENCES dw.Dim_Department (department_key),
  CONSTRAINT fk_fact_project    FOREIGN KEY (project_key)     REFERENCES dw.Dim_Project (project_key),
  CONSTRAINT fk_fact_date       FOREIGN KEY (review_date_key) REFERENCES dw.Dim_Date (date_key),
  CONSTRAINT chk_fact_rating    CHECK (performance_rating BETWEEN 1 AND 4)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------------
-- 2. STORED PROCEDURES
-- ---------------------------------------------------------------------
-- =====================================================================
-- 06_etl_procedures.sql  |  Stored procedures for the ETL (MySQL 8.0.16+)
-- Brief reference: Phase 2, item 2 ("ETL Pipelines (SQL & Python)"):
--   * "Write Stored Procedures to move data from the OLTP tables to the OLAP Data Warehouse."
--   * "Use CTEs and Window Functions ... to clean, rank, and transform the synthesized dataset
--      before loading it into your Dimension and Fact tables."
--   * "Ensure your ETL logic correctly handles the SCD Type 2 inserts/updates when employee
--      attributes change."   (+ Phase 4, item 1: a department change in the UI triggers SCD2)
-- Our design choices (not named in the brief): dw.etl_run_log + sp_etl_log (audit/error trail),
--   sp_run_full_etl (one call that runs everything and validates), sp_load_oltp_from_staging
--   (puts the cleaning CTE/window function in front of OLTP).
-- RUN THIS FILE IN WORKBENCH OR THE mysql CLIENT (it uses DELIMITER $$).
-- Re-runnable: procedures are dropped and recreated.
-- =====================================================================
CREATE TABLE IF NOT EXISTS dw.etl_run_log (
  log_id        BIGINT       NOT NULL AUTO_INCREMENT,
  run_id        VARCHAR(40)  NOT NULL,
  step_name     VARCHAR(60)  NOT NULL,
  log_status        VARCHAR(10)  NOT NULL,
  rows_affected BIGINT       NULL,
  message       VARCHAR(500) NULL,
  logged_at     TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (log_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

DROP PROCEDURE IF EXISTS dw.sp_etl_log;
DROP PROCEDURE IF EXISTS dw.sp_load_oltp_from_staging;
DROP PROCEDURE IF EXISTS dw.sp_load_dim_date;
DROP PROCEDURE IF EXISTS dw.sp_load_dim_department;
DROP PROCEDURE IF EXISTS dw.sp_load_dim_project;
DROP PROCEDURE IF EXISTS dw.sp_load_dim_employee_scd2;
DROP PROCEDURE IF EXISTS dw.sp_load_fact_performance_reviews;
DROP PROCEDURE IF EXISTS dw.sp_scd2_update_employee;
DROP PROCEDURE IF EXISTS dw.sp_run_full_etl;

DELIMITER $$

-- ---------------------------------------------------------------------
-- helper: one audit row per step
-- ---------------------------------------------------------------------
CREATE PROCEDURE dw.sp_etl_log(IN p_step VARCHAR(60), IN p_status VARCHAR(10),
                               IN p_rows BIGINT, IN p_msg VARCHAR(500))
BEGIN
  INSERT INTO dw.etl_run_log (run_id, step_name, log_status, rows_affected, message)
  VALUES (COALESCE(@etl_run_id, 'manual'), p_step, p_status, p_rows, p_msg);
END$$

-- ---------------------------------------------------------------------
-- staging -> OLTP, with the CLEANING step:
--   a CTE ranks duplicate staged rows with ROW_NUMBER() and keeps the newest one per employee;
--   rows whose employee_id is not numeric are rejected; text is trimmed; '' becomes NULL.
-- ---------------------------------------------------------------------
CREATE PROCEDURE dw.sp_load_oltp_from_staging(IN p_batch VARCHAR(40))
BEGIN
  DECLARE v_staged BIGINT DEFAULT 0;
  DECLARE v_dups BIGINT DEFAULT 0;
  DECLARE v_bad BIGINT DEFAULT 0;
  DECLARE v_emp BIGINT DEFAULT 0;
  DECLARE v_msg VARCHAR(400);

  SELECT COUNT(*) INTO v_staged FROM stg.employees_raw WHERE batch_id = p_batch;
  IF v_staged = 0 THEN
    SET v_msg = CONCAT('No staged rows for batch ', COALESCE(p_batch, 'NULL'));
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_msg;
  END IF;

  SELECT COUNT(*) INTO v_bad FROM stg.employees_raw
   WHERE batch_id = p_batch AND employee_id NOT REGEXP '^[0-9]+$';
  SELECT COUNT(*) - COUNT(DISTINCT employee_id) INTO v_dups FROM stg.employees_raw
   WHERE batch_id = p_batch AND employee_id REGEXP '^[0-9]+$';

  -- lookups come from the staged data itself (names can never mismatch)
  INSERT IGNORE INTO oltp.department (department_name)
    SELECT DISTINCT TRIM(department) FROM stg.employees_raw WHERE batch_id = p_batch AND TRIM(department) <> '';
  INSERT IGNORE INTO oltp.job_role (job_role_name)
    SELECT DISTINCT TRIM(job_role) FROM stg.employees_raw WHERE batch_id = p_batch AND TRIM(job_role) <> '';

  INSERT INTO oltp.employee
    (employee_id, employee_code, first_name, last_name, email, gender, date_of_birth, marital_status,
     education_level, education_field, distance_from_home_km, num_companies_worked, stock_option_level,
     prior_experience_years, business_travel, overtime_flag, hire_date, department_id, job_role_id,
     job_level, monthly_income, is_active, termination_date)
  WITH cleaned AS (
    SELECT s.*, ROW_NUMBER() OVER (PARTITION BY s.employee_id ORDER BY s.loaded_at DESC, s.stg_row_id DESC) AS rn
    FROM stg.employees_raw s
    WHERE s.batch_id = p_batch AND s.employee_id REGEXP '^[0-9]+$'
  )
  SELECT CAST(c.employee_id AS UNSIGNED), TRIM(c.employee_code), TRIM(c.first_name), TRIM(c.last_name),
         TRIM(c.email), TRIM(c.gender), CAST(c.date_of_birth AS DATE), TRIM(c.marital_status),
         CAST(c.education_level AS UNSIGNED), TRIM(c.education_field), CAST(c.distance_from_home_km AS UNSIGNED),
         CAST(c.num_companies_worked AS UNSIGNED), CAST(c.stock_option_level AS UNSIGNED),
         CAST(c.prior_experience_years AS UNSIGNED), TRIM(c.business_travel), CAST(c.overtime_flag AS UNSIGNED),
         CAST(c.hire_date AS DATE), d.department_id, jr.job_role_id, CAST(c.job_level AS UNSIGNED),
         CAST(c.monthly_income AS DECIMAL(10,2)), CAST(c.is_active AS UNSIGNED),
         CASE WHEN c.termination_date = '' THEN NULL ELSE CAST(c.termination_date AS DATE) END
  FROM cleaned c
  JOIN oltp.department d ON d.department_name = TRIM(c.department)
  JOIN oltp.job_role  jr ON jr.job_role_name  = TRIM(c.job_role)
  WHERE c.rn = 1
    AND NOT EXISTS (SELECT 1 FROM oltp.employee x WHERE x.employee_id = CAST(c.employee_id AS UNSIGNED));
  SET v_emp = ROW_COUNT();

  UPDATE oltp.employee e
  JOIN stg.employees_raw s ON s.employee_id = e.employee_id AND s.batch_id = p_batch
  SET e.manager_id = CAST(s.manager_id AS UNSIGNED)
  WHERE s.manager_id <> '' AND e.manager_id IS NULL;

  INSERT INTO oltp.employee_change_log
    (employee_id, effective_date, change_type, department_id, job_role_id, job_level, monthly_income)
  SELECT e.employee_id, e.hire_date, 'Hire', e.department_id, e.job_role_id, e.job_level, e.monthly_income
  FROM oltp.employee e
  WHERE NOT EXISTS (SELECT 1 FROM oltp.employee_change_log l WHERE l.employee_id = e.employee_id);

  INSERT INTO oltp.review
    (employee_id, reviewer_id, review_date, performance_rating, job_satisfaction, environment_satisfaction,
     relationship_satisfaction, work_life_balance, job_involvement, percent_salary_hike, training_times_last_year)
  WITH cleaned AS (
    SELECT s.*, ROW_NUMBER() OVER (PARTITION BY s.employee_id ORDER BY s.loaded_at DESC, s.stg_row_id DESC) AS rn
    FROM stg.employees_raw s
    WHERE s.batch_id = p_batch AND s.employee_id REGEXP '^[0-9]+$'
  )
  SELECT e.employee_id,
         CASE WHEN c.manager_id = '' THEN NULL ELSE CAST(c.manager_id AS UNSIGNED) END,
         LEAST(DATE '2025-12-31', COALESCE(e.termination_date, DATE '2025-12-31')),
         CAST(c.performance_rating AS UNSIGNED), CAST(c.job_satisfaction AS UNSIGNED),
         CAST(c.environment_satisfaction AS UNSIGNED), CAST(c.relationship_satisfaction AS UNSIGNED),
         CAST(c.work_life_balance AS UNSIGNED), CAST(c.job_involvement AS UNSIGNED),
         CAST(c.percent_salary_hike AS UNSIGNED), CAST(c.training_times_last_year AS UNSIGNED)
  FROM cleaned c
  JOIN oltp.employee e ON e.employee_id = CAST(c.employee_id AS UNSIGNED)
  WHERE c.rn = 1
    AND NOT EXISTS (SELECT 1 FROM oltp.review r WHERE r.employee_id = e.employee_id
                    AND r.review_date = LEAST(DATE '2025-12-31', COALESCE(e.termination_date, DATE '2025-12-31')));

  CALL dw.sp_etl_log('sp_load_oltp_from_staging', 'OK', v_emp,
       CONCAT('batch=', p_batch, ' staged=', v_staged, ' duplicates_dropped=', v_dups, ' rejected_non_numeric_id=', v_bad));
END$$

-- ---------------------------------------------------------------------
-- Dim_Date: every day in the range (RECURSIVE CTE); only missing days are inserted
-- ---------------------------------------------------------------------
CREATE PROCEDURE dw.sp_load_dim_date(IN p_start DATE, IN p_end DATE)
BEGIN
  DECLARE v_rows BIGINT DEFAULT 0;
  SET SESSION cte_max_recursion_depth = 100000;
  INSERT INTO dw.Dim_Date (full_date, day_of_month, day_name, week_of_year, month_number,
                           month_name, quarter_number, year_number, is_weekend)
  WITH RECURSIVE days AS (
    SELECT p_start AS d
    UNION ALL
    SELECT d + INTERVAL 1 DAY FROM days WHERE d < p_end
  )
  SELECT d, DAY(d), DAYNAME(d), WEEK(d, 3), MONTH(d), MONTHNAME(d), QUARTER(d), YEAR(d), DAYOFWEEK(d) IN (1, 7)
  FROM days
  WHERE NOT EXISTS (SELECT 1 FROM dw.Dim_Date x WHERE x.full_date = days.d);
  SET v_rows = ROW_COUNT();
  CALL dw.sp_etl_log('sp_load_dim_date', 'OK', v_rows, NULL);
END$$

-- ---------------------------------------------------------------------
-- Dim_Department / Dim_Project: surrogate keys, SCD Type 1 (overwrite changes, add new rows)
-- ---------------------------------------------------------------------
CREATE PROCEDURE dw.sp_load_dim_department()
BEGIN
  DECLARE v_new BIGINT DEFAULT 0;
  DECLARE v_upd BIGINT DEFAULT 0;
  UPDATE dw.Dim_Department dd JOIN oltp.department d ON d.department_id = dd.department_id
  SET dd.department_name = d.department_name
  WHERE dd.department_name <> d.department_name;
  SET v_upd = ROW_COUNT();
  INSERT INTO dw.Dim_Department (department_id, department_name)
  SELECT d.department_id, d.department_name FROM oltp.department d
  WHERE NOT EXISTS (SELECT 1 FROM dw.Dim_Department x WHERE x.department_id = d.department_id);
  SET v_new = ROW_COUNT();
  CALL dw.sp_etl_log('sp_load_dim_department', 'OK', v_new + v_upd, CONCAT('inserted=', v_new, ' updated=', v_upd));
END$$

CREATE PROCEDURE dw.sp_load_dim_project()
BEGIN
  DECLARE v_new BIGINT DEFAULT 0;
  DECLARE v_upd BIGINT DEFAULT 0;
  UPDATE dw.Dim_Project dp JOIN oltp.project p ON p.project_id = dp.project_id
  SET dp.project_code = p.project_code, dp.project_name = p.project_name, dp.project_status = p.project_status,
      dp.start_date = p.start_date, dp.end_date = p.end_date
  WHERE NOT (dp.project_code <=> p.project_code AND dp.project_name <=> p.project_name AND dp.project_status <=> p.project_status
             AND dp.start_date <=> p.start_date AND dp.end_date <=> p.end_date);
  SET v_upd = ROW_COUNT();
  INSERT INTO dw.Dim_Project (project_id, project_code, project_name, project_status, start_date, end_date)
  SELECT p.project_id, p.project_code, p.project_name, p.project_status, p.start_date, p.end_date FROM oltp.project p
  WHERE NOT EXISTS (SELECT 1 FROM dw.Dim_Project x WHERE x.project_id = p.project_id);
  SET v_new = ROW_COUNT();
  CALL dw.sp_etl_log('sp_load_dim_project', 'OK', v_new + v_upd, CONCAT('inserted=', v_new, ' updated=', v_upd));
END$$

-- ---------------------------------------------------------------------
-- Dim_Employee, SCD TYPE 2 (batch load, covers the first load AND later changes)
-- ROW_NUMBER() numbers the versions of every employee in the change log and LEAD() gives the
-- next version's start date, so the CTE already holds the CORRECT final state of every version:
--   end_date = next start - 1 day, is_current = no next version.
-- Step 1 inserts versions the dimension does not have yet; step 2 closes superseded versions;
-- step 3 refreshes the non-tracked (Type 1) attributes. Safe to re-run: a second run changes nothing.
-- ---------------------------------------------------------------------
CREATE PROCEDURE dw.sp_load_dim_employee_scd2()
BEGIN
  DECLARE v_new BIGINT DEFAULT 0;
  DECLARE v_closed BIGINT DEFAULT 0;
  DECLARE v_t1 BIGINT DEFAULT 0;

  -- 1) insert new versions
  INSERT INTO dw.Dim_Employee
    (employee_id, employee_code, first_name, last_name, email, gender, date_of_birth, education_level,
     education_field, business_travel, overtime_flag, hire_date, department_id, department_name,
     job_role_name, job_level, monthly_income, attrition_flag, termination_date,
     start_date, end_date, is_current, version_no, row_hash)
  WITH versions AS (
    SELECT l.employee_id, l.effective_date, l.department_id, l.job_role_id, l.job_level, l.monthly_income,
           ROW_NUMBER() OVER w AS version_no,
           LEAD(l.effective_date) OVER w AS next_start
    FROM oltp.employee_change_log l
    WINDOW w AS (PARTITION BY l.employee_id ORDER BY l.effective_date)
  )
  SELECT e.employee_id, e.employee_code, e.first_name, e.last_name, e.email, e.gender, e.date_of_birth,
         e.education_level, e.education_field, e.business_travel, e.overtime_flag, e.hire_date,
         v.department_id, d.department_name, jr.job_role_name, v.job_level, v.monthly_income,
         1 - e.is_active, e.termination_date, v.effective_date,
         COALESCE(DATE_SUB(v.next_start, INTERVAL 1 DAY), DATE '9999-12-31'),
         v.next_start IS NULL, v.version_no,
         MD5(CONCAT_WS('|', v.department_id, v.job_role_id, v.job_level, v.monthly_income))
  FROM versions v
  JOIN oltp.employee   e  ON e.employee_id   = v.employee_id
  JOIN oltp.department d  ON d.department_id = v.department_id
  JOIN oltp.job_role   jr ON jr.job_role_id  = v.job_role_id
  WHERE NOT EXISTS (SELECT 1 FROM dw.Dim_Employee x
                    WHERE x.employee_id = v.employee_id AND x.start_date = v.effective_date);
  SET v_new = ROW_COUNT();

  -- 2) close superseded versions / fix is_current and version_no
  WITH versions AS (
    SELECT l.employee_id, l.effective_date,
           ROW_NUMBER() OVER w AS version_no,
           LEAD(l.effective_date) OVER w AS next_start
    FROM oltp.employee_change_log l
    WINDOW w AS (PARTITION BY l.employee_id ORDER BY l.effective_date)
  )
  UPDATE dw.Dim_Employee d
  JOIN versions v ON v.employee_id = d.employee_id AND v.effective_date = d.start_date
  SET d.end_date   = COALESCE(DATE_SUB(v.next_start, INTERVAL 1 DAY), DATE '9999-12-31'),
      d.is_current = (v.next_start IS NULL),
      d.version_no = v.version_no
  WHERE d.end_date   <> COALESCE(DATE_SUB(v.next_start, INTERVAL 1 DAY), DATE '9999-12-31')
     OR d.is_current <> (v.next_start IS NULL)
     OR d.version_no <> v.version_no;
  SET v_closed = ROW_COUNT();

  -- 3) Type 1 attributes (identical on every version of an employee)
  UPDATE dw.Dim_Employee d
  JOIN oltp.employee e ON e.employee_id = d.employee_id
  SET d.email = e.email, d.overtime_flag = e.overtime_flag, d.business_travel = e.business_travel,
      d.attrition_flag = 1 - e.is_active, d.termination_date = e.termination_date
  WHERE NOT (d.email <=> e.email AND d.overtime_flag <=> e.overtime_flag AND d.business_travel <=> e.business_travel
             AND d.attrition_flag <=> (1 - e.is_active) AND d.termination_date <=> e.termination_date);
  SET v_t1 = ROW_COUNT();

  CALL dw.sp_etl_log('sp_load_dim_employee_scd2', 'OK', v_new + v_closed,
       CONCAT('versions_inserted=', v_new, ' versions_closed_or_fixed=', v_closed, ' type1_rows_updated=', v_t1));
END$$

-- ---------------------------------------------------------------------
-- Fact_PerformanceReviews: each review is tied to the employee VERSION valid on the review date.
-- ROW_NUMBER() ranks the matching versions (newest start first) so exactly one is used.
-- Existing review facts are refreshed from OLTP; missing review facts are inserted.
-- ---------------------------------------------------------------------
CREATE PROCEDURE dw.sp_load_fact_performance_reviews()
BEGIN
  DECLARE v_rows BIGINT DEFAULT 0;
  -- Refresh existing review facts so corrections in OLTP are propagated on reruns.
  UPDATE dw.Fact_PerformanceReviews f
  JOIN oltp.review r ON r.review_id = f.review_id
  JOIN dw.Dim_Employee de ON de.employee_id = r.employee_id
                       AND r.review_date BETWEEN de.start_date AND de.end_date
  JOIN dw.Dim_Department dd ON dd.department_id = de.department_id
  JOIN dw.Dim_Date dt ON dt.full_date = r.review_date
  LEFT JOIN dw.Dim_Project dp ON dp.project_id = r.project_id
  SET f.employee_key = de.employee_key,
      f.department_key = dd.department_key,
      f.project_key = COALESCE(dp.project_key, -1),
      f.review_date_key = dt.date_key,
      f.performance_rating = r.performance_rating,
      f.job_satisfaction = r.job_satisfaction,
      f.environment_satisfaction = r.environment_satisfaction,
      f.relationship_satisfaction = r.relationship_satisfaction,
      f.work_life_balance = r.work_life_balance,
      f.job_involvement = r.job_involvement,
      f.percent_salary_hike = r.percent_salary_hike,
      f.training_times_last_year = r.training_times_last_year,
      f.monthly_income_at_review = de.monthly_income;

  INSERT INTO dw.Fact_PerformanceReviews
    (employee_key, department_key, project_key, review_date_key, review_id, performance_rating,
     job_satisfaction, environment_satisfaction, relationship_satisfaction, work_life_balance,
     job_involvement, percent_salary_hike, training_times_last_year, monthly_income_at_review)
  WITH matched AS (
    SELECT r.review_id, r.review_date, r.project_id, r.performance_rating, r.job_satisfaction,
           r.environment_satisfaction, r.relationship_satisfaction, r.work_life_balance, r.job_involvement,
           r.percent_salary_hike, r.training_times_last_year,
           de.employee_key, de.department_id, de.monthly_income,
           ROW_NUMBER() OVER (PARTITION BY r.review_id ORDER BY de.start_date DESC) AS rn
    FROM oltp.review r
    JOIN dw.Dim_Employee de ON de.employee_id = r.employee_id
                           AND r.review_date BETWEEN de.start_date AND de.end_date
    WHERE NOT EXISTS (SELECT 1 FROM dw.Fact_PerformanceReviews f WHERE f.review_id = r.review_id)
  )
  SELECT m.employee_key, dd.department_key, COALESCE(dp.project_key, -1), dt.date_key, m.review_id,
         m.performance_rating, m.job_satisfaction, m.environment_satisfaction, m.relationship_satisfaction,
         m.work_life_balance, m.job_involvement, m.percent_salary_hike, m.training_times_last_year, m.monthly_income
  FROM matched m
  JOIN dw.Dim_Department dd ON dd.department_id = m.department_id
  JOIN dw.Dim_Date       dt ON dt.full_date = m.review_date
  LEFT JOIN dw.Dim_Project dp ON dp.project_id = m.project_id
  WHERE m.rn = 1;
  SET v_rows = ROW_COUNT();
  CALL dw.sp_etl_log('sp_load_fact_performance_reviews', 'OK', v_rows, NULL);
END$$

-- ---------------------------------------------------------------------
-- SCD2 for ONE employee, called from the application (Phase 4, item 1):
--   the app (EmployeeManager.change_department) runs ONE transaction that
--     1) UPDATE oltp.employee   2) INSERT oltp.employee_change_log   3) CALL this procedure
--   This procedure compares the employee's current OLTP state with the current Dim_Employee row.
--   If a tracked attribute (department, job role, level, income) differs it
--     (a) CLOSES the current version (end_date = effective date - 1 day, is_current = 0) and
--     (b) INSERTS a new current version (start_date = effective date, version_no + 1).
--   It does not start or commit a transaction itself: the caller owns it, so a failure rolls back all three steps.
-- ---------------------------------------------------------------------
CREATE PROCEDURE dw.sp_scd2_update_employee(IN p_employee_id INT UNSIGNED, IN p_effective_date DATE)
BEGIN
  DECLARE v_key INT;
  DECLARE v_start DATE;
  DECLARE v_old_hash CHAR(32);
  DECLARE v_new_hash CHAR(32);
  DECLARE v_msg VARCHAR(300);

  SELECT employee_key, start_date, row_hash INTO v_key, v_start, v_old_hash
  FROM dw.Dim_Employee WHERE employee_id = p_employee_id AND is_current = 1 LIMIT 1;
  IF v_key IS NULL THEN
    SET v_msg = CONCAT('Employee ', p_employee_id, ' has no current row in Dim_Employee (run sp_load_dim_employee_scd2 first)');
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_msg;
  END IF;

  SELECT MD5(CONCAT_WS('|', department_id, job_role_id, job_level, monthly_income)) INTO v_new_hash
  FROM oltp.employee WHERE employee_id = p_employee_id;
  IF v_new_hash IS NULL THEN
    SET v_msg = CONCAT('Employee ', p_employee_id, ' does not exist in oltp.employee');
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_msg;
  END IF;

  -- NULL-safe comparison: a missing/NULL stored hash counts as 'changed' (never a silent skip)
  IF NOT (v_new_hash <=> v_old_hash) THEN
    IF p_effective_date <= v_start THEN
      SET v_msg = CONCAT('Effective date ', p_effective_date, ' must be after the current version start ', v_start);
      SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_msg;
    END IF;

    -- (a) close the current version
    UPDATE dw.Dim_Employee
    SET end_date = DATE_SUB(p_effective_date, INTERVAL 1 DAY), is_current = 0
    WHERE employee_key = v_key;

    -- (b) insert the new current version
    INSERT INTO dw.Dim_Employee
      (employee_id, employee_code, first_name, last_name, email, gender, date_of_birth, education_level,
       education_field, business_travel, overtime_flag, hire_date, department_id, department_name,
       job_role_name, job_level, monthly_income, attrition_flag, termination_date,
       start_date, end_date, is_current, version_no, row_hash)
    SELECT e.employee_id, e.employee_code, e.first_name, e.last_name, e.email, e.gender, e.date_of_birth,
           e.education_level, e.education_field, e.business_travel, e.overtime_flag, e.hire_date,
           e.department_id, d.department_name, jr.job_role_name, e.job_level, e.monthly_income,
           1 - e.is_active, e.termination_date, p_effective_date, DATE '9999-12-31', 1,
           (SELECT MAX(x.version_no) FROM dw.Dim_Employee x WHERE x.employee_id = e.employee_id) + 1,
           v_new_hash
    FROM oltp.employee e
    JOIN oltp.department d  ON d.department_id = e.department_id
    JOIN oltp.job_role   jr ON jr.job_role_id  = e.job_role_id
    WHERE e.employee_id = p_employee_id;

    CALL dw.sp_etl_log('sp_scd2_update_employee', 'OK', 2, CONCAT('employee ', p_employee_id, ' new version from ', p_effective_date));
  END IF;
END$$

-- ---------------------------------------------------------------------
-- master: OLTP -> OLAP in the right order, inside ONE transaction, then validate.
-- Any error (or a failed validation) rolls everything back and is written to dw.etl_run_log.
-- ---------------------------------------------------------------------
CREATE PROCEDURE dw.sp_run_full_etl()
BEGIN
  DECLARE v_bad_current BIGINT DEFAULT 0;
  DECLARE v_gaps BIGINT DEFAULT 0;
  DECLARE v_missing BIGINT DEFAULT 0;
  DECLARE v_msg VARCHAR(400);
  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    GET DIAGNOSTICS CONDITION 1 v_msg = MESSAGE_TEXT;
    ROLLBACK;
    CALL dw.sp_etl_log('sp_run_full_etl', 'ERROR', 0, LEFT(v_msg, 500));
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_msg;
  END;

  SET @etl_run_id = UUID();
  START TRANSACTION;
  CALL dw.sp_load_dim_date(DATE '1980-01-01', DATE '2030-12-31');
  CALL dw.sp_load_dim_department();
  CALL dw.sp_load_dim_project();
  CALL dw.sp_load_dim_employee_scd2();
  CALL dw.sp_load_fact_performance_reviews();

  -- validation: exactly one current version per employee, no gaps/overlaps, every review in the fact
  SELECT COUNT(*) INTO v_bad_current FROM (
    SELECT employee_id FROM dw.Dim_Employee GROUP BY employee_id HAVING SUM(is_current) <> 1) x;
  SELECT COUNT(*) INTO v_gaps FROM (
    SELECT end_date, LEAD(start_date) OVER (PARTITION BY employee_id ORDER BY start_date) AS next_start
    FROM dw.Dim_Employee) y
  WHERE next_start IS NOT NULL AND next_start <> DATE_ADD(end_date, INTERVAL 1 DAY);
  SELECT COUNT(*) INTO v_missing FROM oltp.review r
  LEFT JOIN dw.Fact_PerformanceReviews f ON f.review_id = r.review_id WHERE f.fact_id IS NULL;

  IF v_bad_current > 0 OR v_gaps > 0 OR v_missing > 0 THEN
    SET v_msg = CONCAT('Validation failed: employees_without_one_current_row=', v_bad_current,
                       ' version_gaps=', v_gaps, ' reviews_missing_from_fact=', v_missing);
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_msg;
  END IF;

  CALL dw.sp_etl_log('sp_run_full_etl', 'OK', 0, 'all steps and validations passed');
  COMMIT;
END$$

DELIMITER ;

-- ---------------------------------------------------------------------
-- 3. FULL ETL: OLTP -> OLAP (one transaction; validates itself; any error rolls back and is logged)
-- ---------------------------------------------------------------------
CALL dw.sp_run_full_etl();

-- OPTIONAL (not run): let MySQL refresh the warehouse every night so OLTP changes always reach OLAP.
-- Needs the event scheduler:  SET GLOBAL event_scheduler = ON;   (it resets on server restart unless set in my.ini)
-- CREATE EVENT IF NOT EXISTS dw.ev_nightly_etl ON SCHEDULE EVERY 1 DAY STARTS (CURRENT_DATE + INTERVAL 1 DAY + INTERVAL 2 HOUR)
--   DO CALL dw.sp_run_full_etl();

-- ---------------------------------------------------------------------
-- 4. ANALYTICS VIEWS
-- ---------------------------------------------------------------------
-- =====================================================================
-- 12_analytics_views.sql  |  Views the Streamlit dashboards read (they query ONLY the star schema)
-- Brief reference: Phase 4, item 2 ("Connect Streamlit directly to your Data Warehouse (Star Schema)";
--   charts for: year-over-year performance trends; top-performing employees by department using
--   SQL Window Functions like DENSE_RANK(); employee attrition risk OR project bottleneck analysis).
-- Our design choices (not named in the brief): the composite performance_score used for ranking,
--   and the High/Medium/Low attrition bands. The project-bottleneck view is not included: the brief says
--   "attrition risk OR project bottleneck", and there are no project assignments yet.
-- Safe to re-run (CREATE OR REPLACE).
-- =====================================================================

-- 1) YEAR-OVER-YEAR performance trend per department (LAG gives the previous year)
CREATE OR REPLACE VIEW dw.vw_yoy_performance AS
SELECT year_number, department_name, avg_rating, avg_salary_hike, reviews,
       LAG(avg_rating) OVER (PARTITION BY department_name ORDER BY year_number) AS prev_year_avg_rating,
       ROUND(avg_rating - LAG(avg_rating) OVER (PARTITION BY department_name ORDER BY year_number), 3) AS yoy_change
FROM (
  SELECT dt.year_number, dd.department_name,
         ROUND(AVG(f.performance_rating), 3) AS avg_rating,
         ROUND(AVG(f.percent_salary_hike), 2) AS avg_salary_hike,
         COUNT(*) AS reviews
  FROM dw.Fact_PerformanceReviews f
  JOIN dw.Dim_Date       dt ON dt.date_key       = f.review_date_key
  JOIN dw.Dim_Department dd ON dd.department_key = f.department_key
  GROUP BY dt.year_number, dd.department_name
) y;

-- 2) TOP PERFORMERS per department and year, ranked with DENSE_RANK()
--    performance_score = rating*10 + salary hike % *0.5 + sum of the five 1-4 satisfaction scores
CREATE OR REPLACE VIEW dw.vw_top_performers_by_dept AS
SELECT year_number, department_name, employee_id, employee_code, full_name, job_role_name, job_level,
       performance_rating, percent_salary_hike, performance_score,
       DENSE_RANK() OVER (PARTITION BY year_number, department_name ORDER BY performance_score DESC) AS rank_in_dept
FROM (
  SELECT dt.year_number, dd.department_name, de.employee_id, de.employee_code,
         CONCAT(de.first_name, ' ', de.last_name) AS full_name, de.job_role_name, de.job_level,
         f.performance_rating, f.percent_salary_hike,
         f.performance_rating * 10 + f.percent_salary_hike * 0.5
           + f.job_satisfaction + f.environment_satisfaction + f.relationship_satisfaction
           + f.work_life_balance + f.job_involvement AS performance_score
  FROM dw.Fact_PerformanceReviews f
  JOIN dw.Dim_Employee   de ON de.employee_key   = f.employee_key
  JOIN dw.Dim_Department dd ON dd.department_key = f.department_key
  JOIN dw.Dim_Date       dt ON dt.date_key       = f.review_date_key
) s;

-- 3) ATTRITION RISK: attrition rate per group of current employees, with a risk band and a rank
CREATE OR REPLACE VIEW dw.vw_attrition_risk AS
SELECT department_name, job_level, overtime, business_travel, headcount, leavers,
       ROUND(100 * leavers / headcount, 1) AS attrition_rate_pct,
       CASE WHEN leavers / headcount >= 0.25 THEN 'High'
            WHEN leavers / headcount >= 0.15 THEN 'Medium' ELSE 'Low' END AS risk_band,
       DENSE_RANK() OVER (ORDER BY leavers / headcount DESC) AS risk_rank
FROM (
  SELECT de.department_name, de.job_level,
         IF(de.overtime_flag = 1, 'Overtime', 'No overtime') AS overtime, de.business_travel,
         COUNT(*) AS headcount, SUM(de.attrition_flag) AS leavers
  FROM dw.Dim_Employee de
  WHERE de.is_current = 1
  GROUP BY de.department_name, de.job_level, de.overtime_flag, de.business_travel
) g
WHERE headcount >= 30;       -- ignore tiny groups

-- ---------------------------------------------------------------------
-- 5. SCD2 SELF-TEST
-- ---------------------------------------------------------------------
-- =====================================================================
-- 09_scd2_selftest.sql  |  ONE call that tests the whole SCD Type 2 solution and shows PASS/FAIL rows
-- Brief reference: Phase 1 item 3 (Dim_Employee SCD2), Phase 2 item 2 (ETL handles SCD2 inserts/updates),
--                  Phase 4 item 1 (a department change triggers an SCD2 update in the warehouse).
-- HOW TO USE:  run this whole file ONCE (Workbench or the mysql client: it uses DELIMITER).
--              It creates dw.sp_scd2_selftest and calls it. The result is ONE grid. Everything it
--              changes is rolled back. Nothing needs to be run by hand afterwards.
-- NOTE: the test starts its own transaction, so do not run it while you have an uncommitted
--       transaction of your own open (the ROLLBACK below clears any leftover one).
-- =====================================================================
ROLLBACK;
DROP PROCEDURE IF EXISTS dw.sp_scd2_selftest;

DELIMITER $$
CREATE PROCEDURE dw.sp_scd2_selftest()
main: BEGIN
  DECLARE v_err VARCHAR(400) DEFAULT NULL;
  DECLARE v_emp1 BIGINT; DECLARE v_emp2 BIGINT;
  DECLARE v_dept1 BIGINT; DECLARE v_new1 BIGINT; DECLARE v_dept2 BIGINT; DECLARE v_new2 BIGINT;
  DECLARE v_before1 BIGINT; DECLARE v_before2 BIGINT; DECLARE v_cnt BIGINT;
  DECLARE v_dim0 BIGINT; DECLARE v_log0 BIGINT; DECLARE v_fails BIGINT;
  DECLARE v_eff DATE DEFAULT '2030-01-01';          -- later than every real version start
  DECLARE CONTINUE HANDLER FOR SQLEXCEPTION GET DIAGNOSTICS CONDITION 1 v_err = MESSAGE_TEXT;

  DROP TEMPORARY TABLE IF EXISTS selftest_results;
  CREATE TEMPORARY TABLE selftest_results (          -- MEMORY engine: survives the ROLLBACK below
    id INT AUTO_INCREMENT PRIMARY KEY, test_name VARCHAR(150), result VARCHAR(6), detail VARCHAR(300)
  ) ENGINE = MEMORY;

  SELECT COUNT(*) INTO v_dim0 FROM dw.Dim_Employee;
  SELECT COUNT(*) INTO v_log0 FROM oltp.employee_change_log;

  INSERT INTO selftest_results (test_name, result, detail)
  SELECT 'T0  sp_scd2_update_employee is the current version', IF(COUNT(*) = 1, 'PASS', 'FAIL'),
         IF(COUNT(*) = 1, 'up to date', 'OLD COPY: re-run the NEW 06_etl_procedures.sql, then run this file again')
  FROM information_schema.routines
  WHERE routine_schema = 'dw' AND routine_name = 'sp_scd2_update_employee' AND ROUTINE_DEFINITION LIKE '%<=> v_old_hash%';

  -- two employees that still have exactly ONE version
  SELECT employee_id INTO v_emp1 FROM dw.Dim_Employee GROUP BY employee_id HAVING COUNT(*) = 1 ORDER BY employee_id LIMIT 1;
  SELECT employee_id INTO v_emp2 FROM dw.Dim_Employee GROUP BY employee_id HAVING COUNT(*) = 1 AND employee_id > v_emp1 ORDER BY employee_id LIMIT 1;
  IF v_emp1 IS NULL OR v_emp2 IS NULL THEN
    INSERT INTO selftest_results (test_name, result, detail)
    VALUES ('SETUP  two single-version employees found', 'FAIL', 'Dim_Employee is empty or every employee already has history: load the dimension first');
    SELECT * FROM selftest_results ORDER BY id;
    LEAVE main;
  END IF;

  START TRANSACTION;

  -- ============ PART A: the path the Streamlit button uses (incremental) ============
  SELECT department_id INTO v_dept1 FROM oltp.employee WHERE employee_id = v_emp1;
  SELECT MIN(department_id) INTO v_new1 FROM oltp.department WHERE department_id <> v_dept1;
  SELECT COUNT(*) INTO v_before1 FROM dw.Dim_Employee WHERE employee_id = v_emp1;
  UPDATE oltp.employee SET department_id = v_new1 WHERE employee_id = v_emp1;
  INSERT INTO oltp.employee_change_log (employee_id, effective_date, change_type, department_id, job_role_id, job_level, monthly_income)
    SELECT employee_id, v_eff, 'Transfer', department_id, job_role_id, job_level, monthly_income FROM oltp.employee WHERE employee_id = v_emp1;
  SET v_err = NULL;
  CALL dw.sp_scd2_update_employee(v_emp1, v_eff);

  INSERT INTO selftest_results (test_name, result, detail)
  SELECT 'T1  a department change adds exactly one new version',
         IF(v_err IS NULL AND (SELECT COUNT(*) FROM dw.Dim_Employee WHERE employee_id = v_emp1) = v_before1 + 1, 'PASS', 'FAIL'),
         COALESCE(v_err, CONCAT('employee ', v_emp1, ' moved to department ', v_new1));
  INSERT INTO selftest_results (test_name, result, detail)
  SELECT 'T2  old version is closed the day before the effective date and is no longer current',
         IF(EXISTS (SELECT 1 FROM dw.Dim_Employee WHERE employee_id = v_emp1 AND version_no = v_before1
                    AND end_date = DATE_SUB(v_eff, INTERVAL 1 DAY) AND is_current = 0), 'PASS', 'FAIL'), 'end_date = effective date - 1 day, is_current = 0';
  INSERT INTO selftest_results (test_name, result, detail)
  SELECT 'T3  new version is current: starts on the effective date, ends 9999-12-31, new department',
         IF(EXISTS (SELECT 1 FROM dw.Dim_Employee WHERE employee_id = v_emp1 AND version_no = v_before1 + 1
                    AND start_date = v_eff AND end_date = DATE '9999-12-31' AND is_current = 1 AND department_id = v_new1), 'PASS', 'FAIL'), 'version_no + 1, is_current = 1';
  INSERT INTO selftest_results (test_name, result, detail)
  SELECT 'T4  the employee has exactly one current row',
         IF((SELECT SUM(is_current) FROM dw.Dim_Employee WHERE employee_id = v_emp1) = 1, 'PASS', 'FAIL'), '';

  SET v_err = NULL;  SELECT COUNT(*) INTO v_cnt FROM dw.Dim_Employee WHERE employee_id = v_emp1;
  CALL dw.sp_scd2_update_employee(v_emp1, v_eff);                         -- same change again
  INSERT INTO selftest_results (test_name, result, detail)
  SELECT 'T5  repeating the same change does nothing (no duplicate version)',
         IF(v_err IS NULL AND (SELECT COUNT(*) FROM dw.Dim_Employee WHERE employee_id = v_emp1) = v_cnt, 'PASS', 'FAIL'), COALESCE(v_err, 'no change, no error');

  SET v_err = NULL;
  CALL dw.sp_scd2_update_employee(999999999, v_eff);
  INSERT INTO selftest_results (test_name, result, detail)
  SELECT 'T6  an unknown employee is rejected with an error', IF(v_err LIKE '%no current row%', 'PASS', 'FAIL'), COALESCE(v_err, 'NO ERROR WAS RAISED');

  UPDATE oltp.employee SET monthly_income = monthly_income + 500 WHERE employee_id = v_emp1;
  SET v_err = NULL;
  CALL dw.sp_scd2_update_employee(v_emp1, DATE '2029-01-01');             -- before the current version started
  INSERT INTO selftest_results (test_name, result, detail)
  SELECT 'T7  an effective date before the current version start is rejected',
         IF(v_err LIKE '%must be after the current version start%', 'PASS', 'FAIL'), COALESCE(v_err, 'NO ERROR WAS RAISED');

  -- ============ PART B: the batch path (change recorded only in OLTP, then the ETL runs) ============
  SELECT department_id INTO v_dept2 FROM oltp.employee WHERE employee_id = v_emp2;
  SELECT MIN(department_id) INTO v_new2 FROM oltp.department WHERE department_id <> v_dept2;
  SELECT COUNT(*) INTO v_before2 FROM dw.Dim_Employee WHERE employee_id = v_emp2;
  UPDATE oltp.employee SET department_id = v_new2 WHERE employee_id = v_emp2;
  INSERT INTO oltp.employee_change_log (employee_id, effective_date, change_type, department_id, job_role_id, job_level, monthly_income)
    SELECT employee_id, v_eff, 'Transfer', department_id, job_role_id, job_level, monthly_income FROM oltp.employee WHERE employee_id = v_emp2;
  SET v_err = NULL;
  CALL dw.sp_load_dim_employee_scd2();
  INSERT INTO selftest_results (test_name, result, detail)
  SELECT 'T8  the batch ETL creates the new version and closes the old one correctly',
         IF(v_err IS NULL
            AND (SELECT COUNT(*) FROM dw.Dim_Employee WHERE employee_id = v_emp2) = v_before2 + 1
            AND EXISTS (SELECT 1 FROM dw.Dim_Employee WHERE employee_id = v_emp2 AND version_no = v_before2
                        AND end_date = DATE_SUB(v_eff, INTERVAL 1 DAY) AND is_current = 0)
            AND EXISTS (SELECT 1 FROM dw.Dim_Employee WHERE employee_id = v_emp2 AND version_no = v_before2 + 1
                        AND start_date = v_eff AND end_date = DATE '9999-12-31' AND is_current = 1), 'PASS', 'FAIL'),
         COALESCE(v_err, CONCAT('employee ', v_emp2, ' versions: ', v_before2, ' -> ', v_before2 + 1));
  SET v_err = NULL;
  CALL dw.sp_load_dim_employee_scd2();                                     -- run the ETL again
  CALL dw.sp_scd2_update_employee(v_emp2, v_eff);                          -- and the incremental call for the same change
  INSERT INTO selftest_results (test_name, result, detail)
  SELECT 'T9  batch + incremental paths agree: running both again creates no duplicate version',
         IF(v_err IS NULL AND (SELECT COUNT(*) FROM dw.Dim_Employee WHERE employee_id = v_emp2) = v_before2 + 1, 'PASS', 'FAIL'), COALESCE(v_err, 'still one new version');

  -- ============ PART C: rules that must hold for the WHOLE dimension ============
  SELECT COUNT(*) INTO v_cnt FROM (SELECT employee_id FROM dw.Dim_Employee GROUP BY employee_id HAVING SUM(is_current) <> 1) x;
  INSERT INTO selftest_results (test_name, result, detail)
  VALUES ('T10 every employee has exactly one current version', IF(v_cnt = 0, 'PASS', 'FAIL'), CONCAT('violations: ', v_cnt));
  SELECT COUNT(*) INTO v_cnt FROM (
    SELECT end_date, LEAD(start_date) OVER (PARTITION BY employee_id ORDER BY start_date) AS nxt FROM dw.Dim_Employee) y
  WHERE nxt IS NOT NULL AND nxt <> DATE_ADD(end_date, INTERVAL 1 DAY);
  INSERT INTO selftest_results (test_name, result, detail)
  VALUES ('T11 versions have no gaps or overlaps', IF(v_cnt = 0, 'PASS', 'FAIL'), CONCAT('violations: ', v_cnt));

  ROLLBACK;                                                                -- undo everything the test did

  SELECT department_id INTO v_cnt FROM oltp.employee WHERE employee_id = v_emp1;
  INSERT INTO selftest_results (test_name, result, detail)
  SELECT 'T12 nothing was left behind (dimension, change log and OLTP are back to the original)',
         IF((SELECT COUNT(*) FROM dw.Dim_Employee) = v_dim0
            AND (SELECT COUNT(*) FROM oltp.employee_change_log) = v_log0
            AND v_cnt = v_dept1
            AND (SELECT department_id FROM oltp.employee WHERE employee_id = v_emp2) = v_dept2, 'PASS', 'FAIL'),
         CONCAT('dimension rows ', v_dim0, ', change-log rows ', v_log0);

  SELECT COUNT(*) INTO v_fails FROM selftest_results WHERE result = 'FAIL';
  INSERT INTO selftest_results (test_name, result, detail)
  VALUES ('OVERALL', IF(v_fails = 0, 'PASS', 'FAIL'), CONCAT(v_fails, ' test(s) failed'));

  SELECT id, test_name, result, detail FROM selftest_results ORDER BY id;
END$$
DELIMITER ;

CALL dw.sp_scd2_selftest();

-- ---------------------------------------------------------------------
-- 6. FINAL ACCEPTANCE
-- ---------------------------------------------------------------------
-- =====================================================================
-- 10_final_acceptance.sql  |  Final acceptance check for OLTP + OLAP + SCD2 (read-only, nothing is changed)
-- Run the whole file once. First row = OVERALL verdict. Every check says PASS or FAIL;
-- INFO rows are not errors: they show what data is still missing for the brief.
-- Brief references are in the section names.
-- =====================================================================
WITH checks AS (
  -- ---------------- STRUCTURE (Phase 1 items 1-3, Phase 2 item 1) ----------------
  SELECT 10 AS n, 'STRUCTURE' AS section, 'schemas stg, oltp and dw exist' AS check_name,
         IF((SELECT COUNT(*) FROM information_schema.schemata WHERE schema_name IN ('stg','oltp','dw')) = 3,'PASS','FAIL') AS result,
         '3 expected' AS actual
  UNION ALL SELECT 11, 'STRUCTURE', 'OLTP has the brief''s entities: department, employee, project, review, assignment',
         IF((SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='oltp' AND LOWER(table_name) IN ('department','employee','project','review','assignment')) = 5,'PASS','FAIL'), '5 expected'
  UNION ALL SELECT 12, 'STRUCTURE', 'OLTP design-choice tables exist: job_role, employee_change_log',
         IF((SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='oltp' AND LOWER(table_name) IN ('job_role','employee_change_log')) = 2,'PASS','FAIL'), '2 expected'
  UNION ALL SELECT 13, 'STRUCTURE', 'star schema: Fact_PerformanceReviews + Dim_Employee, Dim_Project, Dim_Date, Dim_Department',
         IF((SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='dw' AND LOWER(table_name) IN ('fact_performancereviews','dim_employee','dim_project','dim_date','dim_department')) = 5,'PASS','FAIL'), '5 expected'
  UNION ALL SELECT 14, 'STRUCTURE', 'every dimension has an auto-increment surrogate primary key',
         IF((SELECT COUNT(*) FROM information_schema.columns WHERE table_schema='dw' AND LOWER(table_name) LIKE 'dim\\_%' AND column_key='PRI' AND extra LIKE '%auto_increment%') = 4,'PASS','FAIL'), '4 expected'
  UNION ALL SELECT 15, 'STRUCTURE', 'OLTP foreign keys defined (at least 10)',
         IF((SELECT COUNT(*) FROM information_schema.referential_constraints WHERE constraint_schema='oltp') >= 10,'PASS','FAIL'),
         CONCAT((SELECT COUNT(*) FROM information_schema.referential_constraints WHERE constraint_schema='oltp'), ' found')
  UNION ALL SELECT 16, 'STRUCTURE', 'fact table has its 4 dimension foreign keys',
         IF((SELECT COUNT(*) FROM information_schema.referential_constraints WHERE constraint_schema='dw' AND LOWER(table_name)='fact_performancereviews') = 4,'PASS','FAIL'), '4 expected'
  UNION ALL SELECT 17, 'STRUCTURE', 'CHECK constraints exist (enforced from MySQL 8.0.16)',
         IF((SELECT COUNT(*) FROM information_schema.table_constraints WHERE constraint_schema IN ('oltp','dw') AND constraint_type='CHECK') > 0,'PASS','FAIL'),
         CONCAT((SELECT COUNT(*) FROM information_schema.table_constraints WHERE constraint_schema IN ('oltp','dw') AND constraint_type='CHECK'), ' checks, MySQL ', VERSION())
  UNION ALL SELECT 18, 'STRUCTURE', 'the 7 ETL stored procedures exist (Phase 2 item 2)',
         IF((SELECT COUNT(*) FROM information_schema.routines WHERE routine_schema='dw' AND routine_type='PROCEDURE' AND routine_name IN
             ('sp_load_dim_date','sp_load_dim_department','sp_load_dim_project','sp_load_dim_employee_scd2','sp_load_fact_performance_reviews','sp_scd2_update_employee','sp_run_full_etl')) = 7,'PASS','FAIL'), '7 expected'

  -- ---------------- OLTP DATA ----------------
  UNION ALL SELECT 20, 'OLTP DATA', 'employees in oltp = distinct employee ids in the largest staged batch',
         IF((SELECT COUNT(*) FROM oltp.employee) =
            (SELECT COUNT(DISTINCT employee_id) FROM stg.employees_raw WHERE batch_id = (SELECT batch_id FROM stg.employees_raw GROUP BY batch_id ORDER BY COUNT(*) DESC LIMIT 1) AND employee_id REGEXP '^[0-9]+$'),'PASS','FAIL'),
         CONCAT((SELECT COUNT(*) FROM oltp.employee), ' employees')
  UNION ALL SELECT 21, 'OLTP DATA', 'no manager_id points to a non-existent employee',
         IF((SELECT COUNT(*) FROM oltp.employee e LEFT JOIN oltp.employee m ON m.employee_id=e.manager_id WHERE e.manager_id IS NOT NULL AND m.employee_id IS NULL)=0,'PASS','FAIL'), '0 expected'
  UNION ALL SELECT 22, 'OLTP DATA', 'nobody is their own manager',
         IF((SELECT COUNT(*) FROM oltp.employee WHERE manager_id = employee_id)=0,'PASS','FAIL'), '0 expected'
  UNION ALL SELECT 23, 'OLTP DATA', 'every review falls inside the employee''s employment period',
         IF((SELECT COUNT(*) FROM oltp.review r JOIN oltp.employee e ON e.employee_id=r.employee_id
             WHERE r.review_date < e.hire_date OR (e.termination_date IS NOT NULL AND r.review_date > e.termination_date))=0,'PASS','FAIL'), '0 expected'
  UNION ALL SELECT 24, 'OLTP DATA', 'every employee''s first change-log row is a Hire on the hire date',
         IF((SELECT COUNT(*) FROM oltp.employee e JOIN oltp.employee_change_log l ON l.employee_id=e.employee_id
             AND l.effective_date=(SELECT MIN(x.effective_date) FROM oltp.employee_change_log x WHERE x.employee_id=e.employee_id)
             WHERE l.change_type<>'Hire' OR l.effective_date<>e.hire_date)=0,'PASS','FAIL'), '0 expected'
  UNION ALL SELECT 25, 'OLTP DATA', 'the newest change-log version equals the employee row (department, role, level, income)',
         IF((SELECT COUNT(*) FROM oltp.employee e JOIN oltp.employee_change_log l ON l.employee_id=e.employee_id
             AND l.effective_date=(SELECT MAX(x.effective_date) FROM oltp.employee_change_log x WHERE x.employee_id=e.employee_id)
             WHERE l.department_id<>e.department_id OR l.job_role_id<>e.job_role_id OR l.job_level<>e.job_level OR l.monthly_income<>e.monthly_income)=0,'PASS','FAIL'), '0 expected'

  -- ---------------- OLAP DATA ----------------
  UNION ALL SELECT 30, 'OLAP DATA', 'Dim_Date has one row per day with no holes',
         IF((SELECT COUNT(*) FROM dw.Dim_Date) = (SELECT DATEDIFF(MAX(full_date), MIN(full_date)) + 1 FROM dw.Dim_Date),'PASS','FAIL'),
         (SELECT CONCAT(COUNT(*), ' days, ', MIN(full_date), ' to ', MAX(full_date)) FROM dw.Dim_Date)
  UNION ALL SELECT 31, 'OLAP DATA', 'Dim_Department rows = oltp.department rows',
         IF((SELECT COUNT(*) FROM dw.Dim_Department)=(SELECT COUNT(*) FROM oltp.department),'PASS','FAIL'), CONCAT((SELECT COUNT(*) FROM dw.Dim_Department),' rows')
  UNION ALL SELECT 32, 'OLAP DATA', 'Dim_Project has the Unknown row (key -1) plus one row per oltp project',
         IF((SELECT COUNT(*) FROM dw.Dim_Project WHERE project_key=-1)=1 AND (SELECT COUNT(*) FROM dw.Dim_Project)=(SELECT COUNT(*) FROM oltp.project)+1,'PASS','FAIL'),
         CONCAT((SELECT COUNT(*) FROM dw.Dim_Project),' rows')
  UNION ALL SELECT 33, 'OLAP DATA', 'Dim_Employee rows = oltp change-log rows (one dimension row per version)',
         IF((SELECT COUNT(*) FROM dw.Dim_Employee)=(SELECT COUNT(*) FROM oltp.employee_change_log),'PASS','FAIL'),
         CONCAT((SELECT COUNT(*) FROM dw.Dim_Employee),' vs ',(SELECT COUNT(*) FROM oltp.employee_change_log))
  UNION ALL SELECT 34, 'OLAP DATA', 'Fact_PerformanceReviews rows = oltp.review rows',
         IF((SELECT COUNT(*) FROM dw.Fact_PerformanceReviews)=(SELECT COUNT(*) FROM oltp.review),'PASS','FAIL'),
         CONCAT((SELECT COUNT(*) FROM dw.Fact_PerformanceReviews),' vs ',(SELECT COUNT(*) FROM oltp.review))
  UNION ALL SELECT 35, 'OLAP DATA', 'fact measures reconcile with oltp (sum of ratings, hikes and satisfaction scores)',
         IF((SELECT SUM(performance_rating)+SUM(percent_salary_hike)+SUM(job_satisfaction) FROM dw.Fact_PerformanceReviews)
            =(SELECT SUM(performance_rating)+SUM(percent_salary_hike)+SUM(job_satisfaction) FROM oltp.review),'PASS','FAIL'), 'totals must be identical'
  UNION ALL SELECT 36, 'OLAP DATA', 'fact review counts per year match oltp',
         IF((SELECT COUNT(*) FROM (SELECT YEAR(review_date) y, COUNT(*) c FROM oltp.review GROUP BY 1) a
             LEFT JOIN (SELECT dt.year_number y, COUNT(*) c FROM dw.Fact_PerformanceReviews f JOIN dw.Dim_Date dt ON dt.date_key=f.review_date_key GROUP BY 1) b ON b.y=a.y
             WHERE b.c IS NULL OR b.c<>a.c)=0,'PASS','FAIL'), '0 differing years expected'

  -- ---------------- SCD TYPE 2 (Phase 1 item 3, Phase 2 item 2) ----------------
  UNION ALL SELECT 40, 'SCD2', 'Dim_Employee unique keys are only PRIMARY and (employee_id, start_date)',
         IF((SELECT COUNT(*) FROM (SELECT index_name FROM information_schema.statistics WHERE table_schema='dw' AND LOWER(table_name)='dim_employee' AND non_unique=0
              AND index_name NOT IN ('PRIMARY','uq_dim_employee_version')) z)=0
            AND (SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema='dw' AND LOWER(table_name)='dim_employee' AND index_name='uq_dim_employee_version')=2,'PASS','FAIL'), 'a unique key on employee_id alone would block SCD2'
  UNION ALL SELECT 41, 'SCD2', 'every employee has exactly one current version (is_current = 1)',
         IF((SELECT COUNT(*) FROM (SELECT employee_id FROM dw.Dim_Employee GROUP BY employee_id HAVING SUM(is_current)<>1) z)=0,'PASS','FAIL'), '0 violations expected'
  UNION ALL SELECT 42, 'SCD2', 'versions have no gaps or overlaps (next start = previous end + 1 day)',
         IF((SELECT COUNT(*) FROM (SELECT end_date, LEAD(start_date) OVER (PARTITION BY employee_id ORDER BY start_date) nxt FROM dw.Dim_Employee) z
             WHERE nxt IS NOT NULL AND nxt<>DATE_ADD(end_date, INTERVAL 1 DAY))=0,'PASS','FAIL'), '0 violations expected'
  UNION ALL SELECT 43, 'SCD2', 'current rows end on 9999-12-31, closed rows do not',
         IF((SELECT COUNT(*) FROM dw.Dim_Employee WHERE (is_current=1 AND end_date<>DATE '9999-12-31') OR (is_current=0 AND end_date=DATE '9999-12-31') OR end_date<start_date)=0,'PASS','FAIL'), '0 violations expected'
  UNION ALL SELECT 44, 'SCD2', 'version_no runs 1..n for every employee',
         IF((SELECT COUNT(*) FROM (SELECT employee_id FROM dw.Dim_Employee GROUP BY employee_id HAVING MAX(version_no)<>COUNT(*) OR MIN(version_no)<>1) z)=0,'PASS','FAIL'), '0 violations expected'
  UNION ALL SELECT 45, 'SCD2', 'each fact row points at the employee version valid on its review date',
         IF((SELECT COUNT(*) FROM dw.Fact_PerformanceReviews f JOIN dw.Dim_Employee de ON de.employee_key=f.employee_key JOIN dw.Dim_Date dt ON dt.date_key=f.review_date_key
             WHERE dt.full_date NOT BETWEEN de.start_date AND de.end_date)=0,'PASS','FAIL'), '0 violations expected'

  -- ---------------- INFORMATION (not errors) ----------------
  UNION ALL SELECT 90, 'INFO', 'employees that already have more than one version (engineered history)',
         'INFO', CONCAT((SELECT COUNT(*) FROM (SELECT employee_id FROM dw.Dim_Employee GROUP BY employee_id HAVING COUNT(*)>1) z),
                        ' employees. 0 = SCD2 logic works but the synthesizer has not produced history yet')
  UNION ALL SELECT 91, 'INFO', 'reviews per year 2021-2025 (the year-over-year dashboard needs reviews in several recent years)',
         'INFO', COALESCE((SELECT GROUP_CONCAT(CONCAT(y, ': ', c) ORDER BY y SEPARATOR ',  ') FROM
                           (SELECT dt.year_number y, COUNT(*) c FROM dw.Fact_PerformanceReviews f JOIN dw.Dim_Date dt ON dt.date_key=f.review_date_key
                            WHERE dt.year_number BETWEEN 2021 AND 2025 GROUP BY dt.year_number) q), 'none')
  UNION ALL SELECT 92, 'INFO', 'projects and assignments in oltp (forms and bottleneck analysis need them)',
         'INFO', CONCAT((SELECT COUNT(*) FROM oltp.project), ' projects, ', (SELECT COUNT(*) FROM oltp.assignment), ' assignments')
  UNION ALL SELECT 93, 'INFO', 'latest full ETL run in dw.etl_run_log',
         'INFO', COALESCE((SELECT CONCAT(log_status, ': ', COALESCE(message,''), ' at ', logged_at) FROM dw.etl_run_log WHERE step_name='sp_run_full_etl' ORDER BY log_id DESC LIMIT 1), 'never run through sp_run_full_etl')
)
SELECT 0 AS n, 'ALL' AS section, 'OVERALL VERDICT' AS check_name,
       IF(SUM(result='FAIL')=0,'PASS','FAIL') AS result,
       CONCAT(SUM(result='PASS'),' passed, ',SUM(result='FAIL'),' failed') AS actual
FROM checks
UNION ALL
SELECT n, section, check_name, result, actual FROM checks
ORDER BY n;

-- Compatibility entry points retained for the existing Streamlit/OOP managers.
DROP PROCEDURE IF EXISTS dw.sp_load_warehouse;
DROP PROCEDURE IF EXISTS dw.sp_top_performers;
DELIMITER $$
CREATE PROCEDURE dw.sp_load_warehouse()
BEGIN
  CALL dw.sp_run_full_etl();
END$$

CREATE PROCEDURE dw.sp_top_performers(IN p_department_id INT)
BEGIN
  SELECT year_number, department_name, employee_id, employee_code, full_name,
         job_role_name, job_level, performance_rating, percent_salary_hike,
         performance_score, rank_in_dept
  FROM dw.vw_top_performers_by_dept
  WHERE p_department_id IS NULL OR department_name = (
      SELECT department_name FROM dw.Dim_Department WHERE department_id = p_department_id
  )
  ORDER BY year_number DESC, department_name, rank_in_dept, employee_id;
END$$
DELIMITER ;
