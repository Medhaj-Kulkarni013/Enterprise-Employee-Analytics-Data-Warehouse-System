-- =====================================================================
-- 02d_load_oltp_from_stg.sql  (v2: self-healing and re-runnable)
-- stg.employees_raw -> oltp.employee / employee_change_log / review
-- Brief reference: Phase 2, item 2 (move data from staging toward OLTP/OLAP).
-- v2 fixes the "0 employees inserted, then FK error on review" failure:
--   * lookups (department, job_role) are filled FROM STAGING, so names can never mismatch
--   * the batch is auto-detected (the batch with the most rows) unless you set @batch yourself
--   * every insert skips rows that already exist, so re-running never duplicates or fails
-- Empty CSV cells are '' in stg: use CASE WHEN col = '' (NOT CAST(NULLIF(...)), which
-- returns NULL for real dates on MySQL 8.0.46).
-- =====================================================================
SET SQL_SAFE_UPDATES = 0;
SET @batch = (SELECT batch_id FROM stg.employees_raw GROUP BY batch_id ORDER BY COUNT(*) DESC LIMIT 1);
-- SET @batch = 'full_100k';      -- uncomment to force a specific batch

-- 0) PREFLIGHT: look at these 3 result sets before anything is inserted
SELECT @batch AS batch_used, COUNT(*) AS stg_rows FROM stg.employees_raw WHERE batch_id = @batch;
SELECT 'department values in staging' AS what, department AS value, COUNT(*) AS n
  FROM stg.employees_raw WHERE batch_id = @batch GROUP BY department;
SELECT 'job_role values in staging' AS what, job_role AS value, COUNT(*) AS n
  FROM stg.employees_raw WHERE batch_id = @batch GROUP BY job_role;

-- 1) lookups, taken from the staged data (INSERT IGNORE skips ones that already exist)
INSERT IGNORE INTO oltp.department (department_name)
SELECT DISTINCT TRIM(department) FROM stg.employees_raw WHERE batch_id = @batch AND TRIM(department) <> '';
INSERT IGNORE INTO oltp.job_role (job_role_name)
SELECT DISTINCT TRIM(job_role)   FROM stg.employees_raw WHERE batch_id = @batch AND TRIM(job_role) <> '';

-- 2) employee, without managers
INSERT INTO oltp.employee
  (employee_id, employee_code, first_name, last_name, email, gender, date_of_birth, marital_status,
   education_level, education_field, distance_from_home_km, num_companies_worked,
   stock_option_level, prior_experience_years, business_travel, overtime_flag, hire_date,
   department_id, job_role_id, job_level, monthly_income, is_active, termination_date)
SELECT CAST(s.employee_id AS UNSIGNED), s.employee_code, s.first_name, s.last_name, s.email,
       s.gender, CAST(s.date_of_birth AS DATE), s.marital_status, CAST(s.education_level AS UNSIGNED),
       s.education_field, CAST(s.distance_from_home_km AS UNSIGNED),
       CAST(s.num_companies_worked AS UNSIGNED), CAST(s.stock_option_level AS UNSIGNED),
       CAST(s.prior_experience_years AS UNSIGNED), s.business_travel,
       CAST(s.overtime_flag AS UNSIGNED), CAST(s.hire_date AS DATE),
       d.department_id, jr.job_role_id, CAST(s.job_level AS UNSIGNED),
       CAST(s.monthly_income AS DECIMAL(10,2)), CAST(s.is_active AS UNSIGNED),
       CASE WHEN s.termination_date = '' THEN NULL ELSE CAST(s.termination_date AS DATE) END
FROM stg.employees_raw s
JOIN oltp.department d ON d.department_name = TRIM(s.department)
JOIN oltp.job_role  jr ON jr.job_role_name  = TRIM(s.job_role)
WHERE s.batch_id = @batch
  AND NOT EXISTS (SELECT 1 FROM oltp.employee x WHERE x.employee_id = CAST(s.employee_id AS UNSIGNED));

-- 3) managers (second pass; the FK proves every manager exists)
UPDATE oltp.employee e
JOIN stg.employees_raw s ON s.employee_id = e.employee_id AND s.batch_id = @batch
SET e.manager_id = CAST(s.manager_id AS UNSIGNED)
WHERE s.manager_id <> '' AND e.manager_id IS NULL;

-- 4) first change-log row per employee ('Hire'); the history script adds later versions
INSERT INTO oltp.employee_change_log
  (employee_id, effective_date, change_type, department_id, job_role_id, job_level, monthly_income)
SELECT e.employee_id, e.hire_date, 'Hire', e.department_id, e.job_role_id, e.job_level, e.monthly_income
FROM oltp.employee e
WHERE NOT EXISTS (SELECT 1 FROM oltp.employee_change_log l WHERE l.employee_id = e.employee_id);

-- 5) the 2025 snapshot review (dated 2025-12-31, or the termination date if the employee left earlier)
INSERT INTO oltp.review
  (employee_id, reviewer_id, review_date, performance_rating, job_satisfaction,
   environment_satisfaction, relationship_satisfaction, work_life_balance,
   job_involvement, percent_salary_hike, training_times_last_year)
SELECT CAST(s.employee_id AS UNSIGNED),
       CASE WHEN s.manager_id = '' THEN NULL ELSE CAST(s.manager_id AS UNSIGNED) END,
       LEAST(DATE '2025-12-31',
             COALESCE(CASE WHEN s.termination_date = '' THEN NULL ELSE CAST(s.termination_date AS DATE) END,
                      DATE '2025-12-31')),
       CAST(s.performance_rating AS UNSIGNED), CAST(s.job_satisfaction AS UNSIGNED),
       CAST(s.environment_satisfaction AS UNSIGNED), CAST(s.relationship_satisfaction AS UNSIGNED),
       CAST(s.work_life_balance AS UNSIGNED), CAST(s.job_involvement AS UNSIGNED),
       CAST(s.percent_salary_hike AS UNSIGNED), CAST(s.training_times_last_year AS UNSIGNED)
FROM stg.employees_raw s
JOIN oltp.employee e ON e.employee_id = CAST(s.employee_id AS UNSIGNED)      -- only for employees that exist
WHERE s.batch_id = @batch
  AND NOT EXISTS (SELECT 1 FROM oltp.review r WHERE r.employee_id = e.employee_id
                  AND r.review_date = LEAST(DATE '2025-12-31', COALESCE(e.termination_date, DATE '2025-12-31')));

-- 6) VERIFICATION (expected in comments)
SELECT @batch AS batch_used,
       (SELECT COUNT(*) FROM stg.employees_raw WHERE batch_id = @batch) AS stg_rows,        -- 100000
       (SELECT COUNT(*) FROM oltp.employee)            AS oltp_employee,                    -- 100000
       (SELECT COUNT(*) FROM oltp.employee_change_log) AS oltp_change_log,                  -- >= 100000
       (SELECT COUNT(*) FROM oltp.review)              AS oltp_review;                      -- >= 100000

SELECT COUNT(*) AS dangling_managers FROM oltp.employee e                                    -- 0
LEFT JOIN oltp.employee m ON m.employee_id = e.manager_id
WHERE e.manager_id IS NOT NULL AND m.employee_id IS NULL;
SELECT COUNT(*) AS employees_without_manager FROM oltp.employee WHERE manager_id IS NULL;   -- 4778
SELECT COUNT(*) AS reviews_outside_employment FROM oltp.review r                            -- 0
JOIN oltp.employee e ON e.employee_id = r.employee_id
WHERE r.review_date < e.hire_date OR (e.termination_date IS NOT NULL AND r.review_date > e.termination_date);
SELECT COUNT(*) AS self_managers FROM oltp.employee WHERE manager_id = employee_id;         -- 0