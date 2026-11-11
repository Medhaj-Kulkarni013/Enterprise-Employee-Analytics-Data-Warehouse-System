CREATE DATABASE oltp;
USE oltp;

CREATE TABLE IF NOT EXISTS oltp.department(
    department_id INT PRIMARY KEY AUTO_INCREMENT,
    department_name VARCHAR(50) UNIQUE NOT NULL
);

CREATE TABLE job_role(
    job_role_id INT PRIMARY KEY AUTO_INCREMENT,
    job_role_name VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE oltp.employee(
    employee_id INT PRIMARY KEY AUTO_INCREMENT,
    employee_code VARCHAR(10) NOT NULL UNIQUE,
    first_name VARCHAR(40) NOT NULL,
    last_name VARCHAR(40) NOT NULL,
    email VARCHAR(60) NOT NULL UNIQUE,
    gender ENUM('Male', 'Female') NOT NULL,
    date_of_birth DATE NOT NULL,
    marital_status ENUM('Single','Married','Divorced') NOT NULL,
    education_level TINYINT NOT NULL,
    education_field ENUM('Human Resources', 'Life Sciences', 'Marketing', 'Medical', 'Technical Degree', 'Other') NOT NULL,
    distance_from_home_km TINYINT NOT NULL,
    num_companies_worked TINYINT NOT NULL,
    stock_option_level TINYINT NOT NULL,
    prior_experience_years TINYINT NOT NULL,
    business_travel ENUM ('Non-Travel', 'Travel_rarely', 'Travel_frequently') NOT NULL,
    overtime_flag TINYINT(1) NOT NULL,
    hire_date DATE NOT NULL,
    department_id INT NOT NULL,
    job_role_id INT NOT NULL,
    job_level TINYINT NOT NULL,
    monthly_income DECIMAL(10,2) NOT NULL,
    manager_id INT NULL,
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    termination_date DATE NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY idx_employee_dept_active (department_id, is_active),
    CONSTRAINT fk_employee_department FOREIGN KEY (department_id) REFERENCES oltp.department (department_id),
  CONSTRAINT fk_employee_job_role   FOREIGN KEY (job_role_id)   REFERENCES oltp.job_role (job_role_id),
  CONSTRAINT fk_employee_manager    FOREIGN KEY (manager_id)    REFERENCES oltp.employee (employee_id),
  CONSTRAINT chk_emp_education  CHECK (education_level BETWEEN 1 AND 5),
  CONSTRAINT chk_emp_distance   CHECK (distance_from_home_km <= 200),
  CONSTRAINT chk_emp_stock      CHECK (stock_option_level BETWEEN 0 AND 3),
  CONSTRAINT chk_emp_job_level  CHECK (job_level BETWEEN 1 AND 5),
  CONSTRAINT chk_emp_income     CHECK (monthly_income > 0),
  CONSTRAINT chk_emp_hire_age   CHECK (hire_date >= DATE_ADD(date_of_birth, INTERVAL 18 YEAR)),
  CONSTRAINT chk_emp_termination CHECK (
        (is_active = 1 AND termination_date IS NULL)
     OR (is_active = 0 AND termination_date IS NOT NULL AND termination_date >= hire_date))
    
);

CREATE TABLE oltp.project(
    project_id INT PRIMARY KEY AUTO_INCREMENT,
    project_code VARCHAR(10) NOT NULL UNIQUE,
    project_name VARCHAR(100) NOT NULL,
    department_id INT NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NULL,
    project_status ENUM('Planned','Active','Completed','On Hold') NOT NULL,

    CONSTRAINT fk_project_department FOREIGN KEY (department_id) REFERENCES oltp.department (department_id),
  CONSTRAINT chk_project_dates CHECK (end_date IS NULL OR end_date >= start_date)
);

CREATE TABLE IF NOT EXISTS oltp.employee_change_log(
    change_id INT PRIMARY KEY AUTO_INCREMENT,
    employee_id INT NOT NULL,
    effective_date DATE NOT NULL,
    change_type      ENUM('Hire','Transfer','Promotion','SalaryHike') NOT NULL,
    department_id INT NOT NULL,
    job_role_id INT NOT NULL,
    job_level TINYINT NOT NULL,
    monthly_income DECIMAL(10,2) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_change_emp_date (employee_id, effective_date),
    CONSTRAINT fk_change_employee   FOREIGN KEY (employee_id)  REFERENCES oltp.employee (employee_id),
  CONSTRAINT fk_change_department FOREIGN KEY (department_id) REFERENCES oltp.department (department_id),
  CONSTRAINT fk_change_job_role   FOREIGN KEY (job_role_id)   REFERENCES oltp.job_role (job_role_id),
  CONSTRAINT chk_change_level  CHECK (job_level BETWEEN 1 AND 5),
  CONSTRAINT chk_change_income CHECK (monthly_income > 0)
);

CREATE TABLE oltp.assignment(
    assignment_id INT PRIMARY KEY AUTO_INCREMENT,
    employee_id INT NOT NULL,
    project_id INT NOT NULL,
    role_on_project  ENUM('Lead','Contributor','Support') NOT NULL,
    allocation_pct INT NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NULL,
    UNIQUE KEY uq_assignment (employee_id, project_id, start_date),
  KEY idx_assignment_project (project_id),
  CONSTRAINT fk_assignment_employee FOREIGN KEY (employee_id) REFERENCES oltp.employee (employee_id),
  CONSTRAINT fk_assignment_project  FOREIGN KEY (project_id)  REFERENCES oltp.project (project_id),
  CONSTRAINT chk_assignment_alloc CHECK (allocation_pct BETWEEN 1 AND 100),
  CONSTRAINT chk_assignment_dates CHECK (end_date IS NULL OR end_date >= start_date)
);

CREATE TABLE IF NOT EXISTS oltp.review(
    review_id INT PRIMARY KEY AUTO_INCREMENT,
    employee_id INT NOT NULL,
    reviewer_id INT NULL,
    project_id INT NULL,
    review_date DATE NOT NULL,
    performance_rating TINYINT NOT NULL,
    job_satisfaction TINYINT NOT NULL,
    environment_satisfaction TINYINT NOT NULL,
    relationship_satisfaction TINYINT NOT NULL,
    work_life_balance TINYINT NOT NULL,
    job_involvement TINYINT NOT NULL,
    percent_salary_hike TINYINT NOT NULL,
    training_times_last_year TINYINT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_review_emp_date (employee_id, review_date),
  KEY idx_review_date (review_date),
  KEY idx_review_reviewer (reviewer_id),
  KEY idx_review_project (project_id),
  CONSTRAINT fk_review_employee FOREIGN KEY (employee_id) REFERENCES oltp.employee (employee_id),
  CONSTRAINT fk_review_reviewer FOREIGN KEY (reviewer_id) REFERENCES oltp.employee (employee_id),
  CONSTRAINT fk_review_project  FOREIGN KEY (project_id)  REFERENCES oltp.project (project_id),
  CONSTRAINT chk_review_rating  CHECK (performance_rating BETWEEN 1 AND 4),
  CONSTRAINT chk_review_jobsat  CHECK (job_satisfaction BETWEEN 1 AND 4),
  CONSTRAINT chk_review_envsat  CHECK (environment_satisfaction BETWEEN 1 AND 4),
  CONSTRAINT chk_review_relsat  CHECK (relationship_satisfaction BETWEEN 1 AND 4),
  CONSTRAINT chk_review_wlb     CHECK (work_life_balance BETWEEN 1 AND 4),
  CONSTRAINT chk_review_invol   CHECK (job_involvement BETWEEN 1 AND 4),
  CONSTRAINT chk_review_hike    CHECK (percent_salary_hike BETWEEN 0 AND 100),
  CONSTRAINT chk_review_train   CHECK (training_times_last_year BETWEEN 0 AND 20),
  CONSTRAINT chk_review_reviewer CHECK (reviewer_id IS NULL OR reviewer_id <> employee_id)
);

-- drop database oltp;

-- ALTER TABLE oltp.projectoltp
-- RENAME COLUMN status TO project_status;