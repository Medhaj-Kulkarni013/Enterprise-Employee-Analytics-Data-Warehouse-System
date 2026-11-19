-- =====================================================================
-- 05_rbac_dcl_roles.sql | Database-Level RBAC using MySQL 8.0+ DCL
-- Implements Principle of Least Privilege across stg, oltp, and dw schemas.
-- Note: MySQL 8.0+ updates grant tables automatically on GRANT; FLUSH PRIVILEGES
-- is unnecessary (and restricted on managed cloud hosts like Aiven).
-- =====================================================================

-- 1. Create the 3 non-redundant database roles
CREATE ROLE IF NOT EXISTS 'role_data_architect', 'role_hr_operations', 'role_executive';

-- 2. Data Architect: Full DDL/DML/ETL execution across staging, OLTP, and DW
GRANT ALL PRIVILEGES ON stg.*  TO 'role_data_architect';
GRANT ALL PRIVILEGES ON oltp.* TO 'role_data_architect';
GRANT ALL PRIVILEGES ON dw.*   TO 'role_data_architect';

-- 3. HR Operations: OLTP transactional writes + incremental SCD2 sync + DW read
GRANT SELECT, INSERT, UPDATE ON oltp.employee            TO 'role_hr_operations';
GRANT SELECT, INSERT         ON oltp.employee_change_log TO 'role_hr_operations';
GRANT SELECT, INSERT, UPDATE ON oltp.project             TO 'role_hr_operations';
GRANT SELECT, INSERT, UPDATE ON oltp.assignment          TO 'role_hr_operations';
GRANT SELECT, INSERT, UPDATE ON oltp.review              TO 'role_hr_operations';
GRANT SELECT                 ON oltp.department          TO 'role_hr_operations';
GRANT SELECT                 ON oltp.job_role            TO 'role_hr_operations';
GRANT EXECUTE ON PROCEDURE dw.sp_sync_employee_scd2      TO 'role_hr_operations';
GRANT SELECT                 ON dw.*                     TO 'role_hr_operations';

-- 4. Executive: Strictly read-only access to the OLAP Star Schema & Analytics Views
GRANT SELECT ON dw.Dim_Date                TO 'role_executive';
GRANT SELECT ON dw.Dim_Department          TO 'role_executive';
GRANT SELECT ON dw.Dim_Project             TO 'role_executive';
GRANT SELECT ON dw.Dim_Employee            TO 'role_executive';
GRANT SELECT ON dw.Fact_PerformanceReviews TO 'role_executive';
GRANT SELECT ON dw.vw_yoy_performance      TO 'role_executive';
GRANT SELECT ON dw.vw_top_performers_by_dept TO 'role_executive';
GRANT SELECT ON dw.vw_attrition_risk       TO 'role_executive';