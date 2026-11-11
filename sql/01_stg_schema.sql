CREATE DATABASE stg;
USE stg;

CREATE TABLE IF NOT ExISTS stg.employees_raw(
stg_row_id                BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
employee_id               VARCHAR(20),
  employee_code             VARCHAR(20),
  source_employee_number    VARCHAR(20),
  first_name                VARCHAR(100),
  last_name                 VARCHAR(100),
  email                     VARCHAR(150),
  gender                    VARCHAR(20),
  date_of_birth             VARCHAR(20),
  marital_status            VARCHAR(30),
  education_level           VARCHAR(10),
  education_field           VARCHAR(60),
  distance_from_home_km     VARCHAR(10),
  num_companies_worked      VARCHAR(10),
  prior_experience_years    VARCHAR(10),
  stock_option_level        VARCHAR(10),
  business_travel           VARCHAR(30),
  overtime_flag             VARCHAR(10),
  hire_date                 VARCHAR(20),
  department                VARCHAR(60),
  job_role                  VARCHAR(60),
  job_level                 VARCHAR(10),
  monthly_income            VARCHAR(20),
  manager_id                VARCHAR(20),   -- '' means no manager
  is_active                 VARCHAR(10),
  termination_date          VARCHAR(20),   -- '' means still active
  performance_rating        VARCHAR(10),
  percent_salary_hike       VARCHAR(10),
  training_times_last_year  VARCHAR(10),
  job_satisfaction          VARCHAR(10),
  environment_satisfaction  VARCHAR(10),
  relationship_satisfaction VARCHAR(10),
  work_life_balance         VARCHAR(10),
  job_involvement           VARCHAR(10),
  batch_id                  VARCHAR(40)  NOT NULL DEFAULT 'manual',
  source_file               VARCHAR(100),
  loaded_at                 TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,

  KEY idx_emp_raw_batch (batch_id),
  KEY idx_emp_raw_empid (employee_id)    
);