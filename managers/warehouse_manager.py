"""Staging and OLAP warehouse data access."""

import csv
from pathlib import Path

import mysql.connector

from core.exceptions import DatabaseError, ValidationError
from managers.base_manager import BaseManager


class WarehouseManager(BaseManager):
    """Loads staging data and runs the warehouse ETL procedure."""

    STAGING_COLUMNS = (
        "employee_id", "employee_code", "source_employee_number", "first_name",
        "last_name", "email", "gender", "date_of_birth", "marital_status",
        "education_level", "education_field", "distance_from_home_km",
        "num_companies_worked", "prior_experience_years", "stock_option_level",
        "business_travel", "overtime_flag", "hire_date", "department",
        "job_role", "job_level", "monthly_income", "manager_id", "is_active",
        "termination_date", "performance_rating", "percent_salary_hike",
        "training_times_last_year", "job_satisfaction",
        "environment_satisfaction", "relationship_satisfaction",
        "work_life_balance", "job_involvement",
    )

    def load_staging_csv(self, csv_path, batch_id="manual", source_file=None, batch_size=1000):
        """Load a synthesized CSV into stg.employees_raw."""
        path = Path(csv_path)
        if not path.is_file():
            raise ValidationError(f"Staging CSV not found: {path}")
        source_file = source_file or path.name
        placeholders = ", ".join(["%s"] * len(self.STAGING_COLUMNS))
        query = f"""INSERT INTO stg.employees_raw
            ({", ".join(self.STAGING_COLUMNS)}, batch_id, source_file)
            VALUES ({placeholders}, %s, %s)"""
        connection = cursor = None
        count = 0
        try:
            connection, cursor = self.get_connection()
            with path.open(newline="", encoding="utf-8") as handle:
                reader = csv.DictReader(handle)
                missing = set(self.STAGING_COLUMNS) - set(reader.fieldnames or ())
                if missing:
                    raise ValidationError(f"CSV is missing staging columns: {sorted(missing)}")
                batch = []
                for row in reader:
                    batch.append(tuple(row[column] or None for column in self.STAGING_COLUMNS)
                                 + (batch_id, source_file))
                    if len(batch) >= batch_size:
                        cursor.executemany(query, batch)
                        count += len(batch)
                        batch.clear()
                if batch:
                    cursor.executemany(query, batch)
                    count += len(batch)
            connection.commit()
            return count
        except (ValidationError, DatabaseError):
            if connection:
                connection.rollback()
            raise
        except mysql.connector.Error as error:
            if connection:
                connection.rollback()
            raise DatabaseError("Failed to load staging CSV.", error) from error
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()

    def load_history_csv(self, csv_path, batch_size=1000):
        """Load generated history events into oltp.employee_change_log."""
        path = Path(csv_path)
        if not path.is_file():
            raise ValidationError(f"History CSV not found: {path}")
        required = {
            "employee_id", "effective_date", "change_type", "department",
            "job_role", "job_level", "monthly_income",
        }
        connection = cursor = None
        try:
            connection, cursor = self.get_connection()
            cursor.execute("SELECT department_id, department_name FROM oltp.department")
            departments = {row["department_name"]: row["department_id"] for row in cursor.fetchall()}
            cursor.execute("SELECT job_role_id, job_role_name FROM oltp.job_role")
            roles = {row["job_role_name"]: row["job_role_id"] for row in cursor.fetchall()}
            with path.open(newline="", encoding="utf-8") as handle:
                reader = csv.DictReader(handle)
                missing = required - set(reader.fieldnames or ())
                if missing:
                    raise ValidationError(f"History CSV is missing columns: {sorted(missing)}")
                query = """INSERT INTO oltp.employee_change_log
                    (employee_id, effective_date, change_type, department_id,
                     job_role_id, job_level, monthly_income)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)"""
                batch = []
                count = 0
                for row in reader:
                    if row["department"] not in departments or row["job_role"] not in roles:
                        raise ValidationError(
                            f"Unknown department or job role for employee {row['employee_id']}."
                        )
                    batch.append((
                        int(row["employee_id"]), row["effective_date"], row["change_type"],
                        departments[row["department"]], roles[row["job_role"]],
                        int(row["job_level"]), float(row["monthly_income"]),
                    ))
                    if len(batch) >= batch_size:
                        cursor.executemany(query, batch)
                        count += len(batch)
                        batch.clear()
                if batch:
                    cursor.executemany(query, batch)
                    count += len(batch)
            connection.commit()
            return count
        except (ValidationError, DatabaseError):
            if connection:
                connection.rollback()
            raise
        except mysql.connector.Error as error:
            if connection:
                connection.rollback()
            raise DatabaseError("Failed to load employee history.", error) from error
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()

    def run_warehouse_etl(self):
        """Execute the idempotent OLTP-to-OLAP stored procedure."""
        connection = cursor = None
        try:
            connection, cursor = self.get_connection()
            cursor.callproc("dw.sp_run_full_etl")
            connection.commit()
            return True
        except mysql.connector.Error as error:
            if connection:
                connection.rollback()
            raise DatabaseError("Warehouse ETL failed.", error) from error
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()

    def promote_staging_batch(self, batch_id):
        """Promote one staging batch into normalized OLTP dimensions."""
        if not isinstance(batch_id, str) or not batch_id.strip():
            raise ValidationError("Batch ID must be a non-empty string.")
        connection = cursor = None
        try:
            connection, cursor = self.get_connection()
            cursor.callproc("dw.sp_load_oltp_from_staging", (batch_id,))
            connection.commit()
            return True
        except mysql.connector.Error as error:
            if connection:
                connection.rollback()
            raise DatabaseError("Staging-to-OLTP promotion failed.", error) from error
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()
