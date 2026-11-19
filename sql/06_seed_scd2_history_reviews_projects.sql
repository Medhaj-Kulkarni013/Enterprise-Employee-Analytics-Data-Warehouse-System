-- =====================================================================
-- 10_seed_scd2_history_reviews_projects.sql
-- Synthetic-data enrichment for the OLTP database (run BEFORE the warehouse build).
--
-- Why: the snapshot dataset gives every employee ONE state and ONE review, so
--   * Dim_Employee has no real SCD Type 2 history (no employee has > 1 version),
--   * the year-over-year dashboard has no data (most reviews fall in 2025),
--   * there are no projects / assignments for the "manage assignments" story.
--
-- What it does (all deterministic: no RAND(), results are reproducible):
--   A. SCD2 history     ~18% of employees with enough tenure get ONE change event
--                       (Promotion / SalaryHike / Transfer). The existing 'Hire' row is
--                       rewritten to hold the PREVIOUS state; a new event row holds the
--                       CURRENT state, so the newest change-log row still equals the employee row.
--   B. Projects         4 projects per department (code prefix SEED) and one assignment for ~35%
--                       of active employees.
--   C. Review history   one review per employee for each year 2021-2024 (year-end), when employed.
--                       Ratings drift upward over time so the year-over-year view shows a trend.
--
-- Safe to re-run: every step is guarded (NOT EXISTS / ON DUPLICATE KEY), so a second run adds nothing.
-- It only touches oltp.employee_change_log, oltp.project, oltp.assignment, oltp.review.
-- AFTER running it, rebuild the warehouse by running 09_olap_99_check.sql (it drops and rebuilds dw).
-- Requires MySQL 8.0.16+.
-- =====================================================================
USE oltp;   -- temporary tables below need a default database
SET SQL_SAFE_UPDATES = 0;
SET @snapshot = DATE '2025-12-31';
-- ---------------------------------------------------------------------
-- A. SCD2 history
-- ---------------------------------------------------------------------
DROP TEMPORARY TABLE IF EXISTS tmp_role_top;
CREATE TEMPORARY TABLE tmp_role_top (
  department_id INT NOT NULL PRIMARY KEY,
  job_role_id   INT NOT NULL
);
INSERT INTO tmp_role_top (department_id, job_role_id)
SELECT department_id, job_role_id
FROM (SELECT department_id, job_role_id,
             ROW_NUMBER() OVER (PARTITION BY department_id ORDER BY COUNT(*) DESC, job_role_id) AS rn
      FROM oltp.employee GROUP BY department_id, job_role_id) x
WHERE rn = 1;

DROP TEMPORARY TABLE IF EXISTS tmp_other;
CREATE TEMPORARY TABLE tmp_other (
  dept  INT NOT NULL,
  other INT NOT NULL,
  rn    INT NOT NULL,
  cn    INT NOT NULL,
  PRIMARY KEY (dept, rn)
);
INSERT INTO tmp_other (dept, other, rn, cn)
SELECT a.department_id AS dept, b.department_id AS other,
       ROW_NUMBER() OVER (PARTITION BY a.department_id ORDER BY b.department_id) AS rn,
       COUNT(*)     OVER (PARTITION BY a.department_id)                          AS cn
FROM oltp.department a JOIN oltp.department b ON a.department_id <> b.department_id;

DROP TEMPORARY TABLE IF EXISTS tmp_hist;
CREATE TEMPORARY TABLE tmp_hist (
  employee_id    INT           NOT NULL PRIMARY KEY,
  hire_date      DATE          NOT NULL,
  department_id  INT           NOT NULL,
  job_role_id    INT           NOT NULL,
  job_level      TINYINT       NOT NULL,
  monthly_income DECIMAL(10,2) NOT NULL,
  hf             INT           NOT NULL,
  prev_dept      INT           NULL,
  prev_role      INT           NULL,
  eff_date       DATE          NOT NULL,
  ev             VARCHAR(20)   NOT NULL
);
INSERT INTO tmp_hist (employee_id, hire_date, department_id, job_role_id, job_level, monthly_income,
                      hf, prev_dept, prev_role, eff_date, ev)
SELECT t.employee_id, t.hire_date, t.department_id, t.job_role_id, t.job_level, t.monthly_income,
       t.hf, t.prev_dept, t.prev_role,
       DATE_ADD(t.hire_date, INTERVAL (270 + MOD(t.hv, t.span)) DAY) AS eff_date,
       CASE WHEN t.tu < 40 AND t.job_level >= 2 THEN 'Promotion'
            WHEN t.tu < 75 OR t.prev_dept IS NULL OR t.prev_role IS NULL THEN 'SalaryHike'
            ELSE 'Transfer' END AS ev
FROM (
  SELECT e.employee_id, e.hire_date, e.department_id, e.job_role_id, e.job_level, e.monthly_income,
         DATEDIFF(LEAST(@snapshot, COALESCE(e.termination_date, @snapshot)), e.hire_date) - 360 AS span,
         MOD(e.employee_id * 7919    + 31, 100)    AS tu,
         MOD(e.employee_id * 104729  + 7, 100000)  AS hv,
         MOD(e.employee_id * 1299709 + 3, 100)     AS hf,
         o.other AS prev_dept, rt.job_role_id AS prev_role
  FROM oltp.employee e
  LEFT JOIN tmp_other    o  ON o.dept = e.department_id AND o.rn = 1 + MOD(e.employee_id, o.cn)
  LEFT JOIN tmp_role_top rt ON rt.department_id = o.other
  WHERE NOT EXISTS (SELECT 1 FROM oltp.employee_change_log l
                    WHERE l.employee_id = e.employee_id AND l.change_type <> 'Hire')
    AND MOD(e.employee_id * 2654435761, 100) < 18
) t
WHERE t.span >= 180;



-- 1) rewrite the Hire row to the PREVIOUS state
UPDATE oltp.employee_change_log l
JOIN tmp_hist t ON t.employee_id = l.employee_id AND l.change_type = 'Hire'
SET l.department_id  = CASE WHEN t.ev = 'Transfer'   THEN t.prev_dept ELSE l.department_id END,
    l.job_role_id    = CASE WHEN t.ev = 'Transfer'   THEN t.prev_role ELSE l.job_role_id   END,
    l.job_level      = CASE WHEN t.ev = 'Promotion'  THEN t.job_level - 1 ELSE l.job_level END,
    l.monthly_income = CASE t.ev
                         WHEN 'Promotion'  THEN ROUND(t.monthly_income / (1.12 + t.hf / 1000), 2)
                         WHEN 'SalaryHike' THEN ROUND(t.monthly_income / (1.05 + t.hf / 1500), 2)
                         ELSE l.monthly_income END;

-- 2) add the event row holding the CURRENT state
INSERT INTO oltp.employee_change_log
  (employee_id, effective_date, change_type, department_id, job_role_id, job_level, monthly_income)
SELECT employee_id, eff_date, ev, department_id, job_role_id, job_level, monthly_income
FROM tmp_hist;

-- ---------------------------------------------------------------------
-- B. Projects and assignments
-- ---------------------------------------------------------------------
INSERT INTO oltp.project (project_code, project_name, department_id, start_date, end_date, project_status)
SELECT s.code, s.project_name, s.department_id, s.start_date, s.end_date, s.project_status
FROM (
  SELECT CONCAT('SEED', LPAD(ROW_NUMBER() OVER (ORDER BY d.department_id, n.n), 3, '0')) AS code,
         CONCAT(n.name, ' - ', d.department_name) AS project_name, d.department_id,
         n.start_date, n.end_date, n.status AS project_status
  FROM oltp.department d
  CROSS JOIN (SELECT 1 AS n, 'Platform Modernization' AS name, DATE '2024-01-01' AS start_date, CAST(NULL AS DATE) AS end_date, 'Active' AS status
              UNION ALL SELECT 2, 'Customer Insights',  DATE '2024-06-01', NULL, 'Active'
              UNION ALL SELECT 3, 'Process Automation', DATE '2023-01-01', DATE '2024-09-30', 'Completed'
              UNION ALL SELECT 4, 'Talent Programme',    DATE '2025-03-01', NULL, 'Active') n
) s
ON DUPLICATE KEY UPDATE project_code = project_code;

INSERT INTO oltp.assignment (employee_id, project_id, role_on_project, allocation_pct, start_date, end_date)
SELECT e.employee_id, p.project_id,
       CASE WHEN MOD(e.employee_id * 31, 10) = 0 THEN 'Lead'
            WHEN MOD(e.employee_id * 31, 10) < 6 THEN 'Contributor' ELSE 'Support' END,
       20 + 10 * MOD(e.employee_id * 17, 9),
       GREATEST(e.hire_date, p.start_date), NULL
FROM oltp.employee e
JOIN (SELECT pr.project_id, pr.department_id, pr.start_date,
             ROW_NUMBER() OVER (PARTITION BY pr.department_id ORDER BY pr.project_id) AS prn,
             COUNT(*)     OVER (PARTITION BY pr.department_id)                        AS pc
      FROM oltp.project pr
      WHERE pr.project_code LIKE 'SEED%' AND pr.project_status = 'Active') p
  ON p.department_id = e.department_id AND p.prn = 1 + MOD(e.employee_id, p.pc)
WHERE e.is_active = 1
  AND MOD(e.employee_id * 2654435761, 100) < 35
  AND NOT EXISTS (SELECT 1 FROM oltp.assignment a WHERE a.employee_id = e.employee_id);

-- ---------------------------------------------------------------------
-- C. Review history 2021-2024 (year-end reviews, only while employed)
--    P(rating drops by 1) = (2025 - year) * 9% * department factor (Sales 1.3, HR 0.7, others 1.0)
--    P(rating rises by 1) = 4%      => averages climb towards 2025: a visible year-over-year trend
-- ---------------------------------------------------------------------
INSERT INTO oltp.review
  (employee_id, reviewer_id, project_id, review_date, performance_rating, job_satisfaction,
   environment_satisfaction, relationship_satisfaction, work_life_balance, job_involvement,
   percent_salary_hike, training_times_last_year)
WITH RECURSIVE yrs(yr) AS (SELECT 2021 UNION ALL SELECT yr + 1 FROM yrs WHERE yr < 2024),
base AS (
  SELECT r.*, ROW_NUMBER() OVER (PARTITION BY r.employee_id ORDER BY r.review_date DESC) AS rn
  FROM oltp.review r
),
x AS (
  SELECT b.employee_id, b.reviewer_id, y.yr, DATE(CONCAT(y.yr, '-12-31')) AS rd,
         b.performance_rating AS pr, b.job_satisfaction AS js, b.environment_satisfaction AS es,
         b.relationship_satisfaction AS rs, b.work_life_balance AS wl, b.job_involvement AS ji,
         MOD(b.employee_id * 2654435761 + y.yr * 40503, 1000) AS u,
         CASE d.department_name WHEN 'Sales' THEN 13 WHEN 'Human Resources' THEN 7 ELSE 10 END AS pm
  FROM base b
  JOIN yrs y
  JOIN oltp.employee   e ON e.employee_id   = b.employee_id
  JOIN oltp.department d ON d.department_id = e.department_id
  WHERE b.rn = 1
    AND e.hire_date <= DATE(CONCAT(y.yr, '-06-30'))
    AND (e.termination_date IS NULL OR e.termination_date >= DATE(CONCAT(y.yr, '-12-31')))
)
SELECT x.employee_id, x.reviewer_id,
       (SELECT a.project_id FROM oltp.assignment a
        WHERE a.employee_id = x.employee_id AND a.start_date <= x.rd ORDER BY a.start_date DESC LIMIT 1),
       x.rd,
       CASE WHEN x.u < (2025 - x.yr) * 9 * x.pm THEN GREATEST(1, x.pr - 1)
            WHEN x.u >= 960                     THEN LEAST(4, x.pr + 1)
            ELSE x.pr END,
       GREATEST(1, LEAST(4, x.js + MOD(x.u, 3) - 1)),
       GREATEST(1, LEAST(4, x.es + MOD(FLOOR(x.u / 7), 3) - 1)),
       GREATEST(1, LEAST(4, x.rs + MOD(FLOOR(x.u / 11), 3) - 1)),
       GREATEST(1, LEAST(4, x.wl + MOD(FLOOR(x.u / 13), 3) - 1)),
       GREATEST(1, LEAST(4, x.ji + MOD(FLOOR(x.u / 17), 3) - 1)),
       11 + MOD(FLOOR(x.u / 3) + x.yr, 15),
       MOD(FLOOR(x.u / 5) + x.yr, 7)
FROM x
WHERE NOT EXISTS (SELECT 1 FROM oltp.review r2 WHERE r2.employee_id = x.employee_id AND r2.review_date = x.rd);

-- link the existing latest reviews to the employee's project (so Dim_Project is not all 'Unknown')
UPDATE oltp.review r
JOIN oltp.assignment a ON a.employee_id = r.employee_id AND r.review_date >= a.start_date
SET r.project_id = a.project_id
WHERE r.project_id IS NULL;

-- ---------------------------------------------------------------------
-- Summary (compare with the INFO lines of 09_olap_99_check.sql after the rebuild)
-- ---------------------------------------------------------------------
SELECT 'employees with SCD2 history' AS what, COUNT(*) AS n
FROM (SELECT employee_id FROM oltp.employee_change_log GROUP BY employee_id HAVING COUNT(*) > 1) h
UNION ALL SELECT CONCAT('change events: ', t.change_type), t.n
          FROM (SELECT change_type, COUNT(*) AS n FROM oltp.employee_change_log GROUP BY change_type) t
UNION ALL SELECT CONCAT('reviews in ', t.yr), t.n
          FROM (SELECT YEAR(review_date) AS yr, COUNT(*) AS n FROM oltp.review GROUP BY YEAR(review_date)) t
UNION ALL SELECT 'projects', COUNT(*) FROM oltp.project
UNION ALL SELECT 'assignments', COUNT(*) FROM oltp.assignment;
