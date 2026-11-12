
"""
Manager responsible for Employee CRUD operations.
"""

import mysql.connector
from datetime import date
from decimal import Decimal

from managers.crud_manager import CrudManager
from models.employee import Employee
from core.exceptions import (
    DatabaseError,
    ValidationError,
    NotFoundError,
    DuplicateError
)


class EmployeeManager(CrudManager):
    """Handles employee-related database operations."""

    TABLE = "oltp.employee"

    # Columns that can be modified through ordinary employee updates.
    # Department, job role, level and salary are excluded because
    # they require historical change tracking.
    UPDATABLE_FIELDS = {
        "first_name",
        "last_name",
        "email"
    }

    REQUIRED_CREATE_FIELDS = {
        "employee_code",
        "first_name",
        "last_name",
        "email",
        "gender",
        "date_of_birth",
        "marital_status",
        "education_level",
        "education_field",
        "distance_from_home_km",
        "num_companies_worked",
        "stock_option_level",
        "prior_experience_years",
        "business_travel",
        "overtime_flag",
        "hire_date",
        "department_id",
        "job_role_id",
        "job_level",
        "monthly_income"
    }

    def __init__(self):
        super().__init__()



    @staticmethod
    def _sync_employee_dimension(cursor, employee_id):
        """Synchronize one employee's SCD2 and Type 1 warehouse rows."""
        cursor.callproc("dw.sp_sync_employee_scd2", (employee_id,))

        for result in cursor.stored_results():
            result.fetchall()

    @staticmethod
    def _raise_database_error(error, context, duplicate_message=None):
        """Preserve the underlying MySQL error when the transaction wraps it."""
        original = getattr(error, "original_error", None)

        if isinstance(original, mysql.connector.IntegrityError):
            if original.errno == 1062 and duplicate_message:
                raise DuplicateError(duplicate_message, original) from error

            detail = (
                f"MySQL error {original.errno} "
                f"(SQLSTATE {original.sqlstate}): {original.msg}"
            )
        else:
            detail = getattr(error, "message", str(error))

        raise DatabaseError(
            f"{context}: {detail}", original or error
        ) from error


    # ---------------------------------------------------------
    # CREATE
    # ---------------------------------------------------------

    def create(self, employee):
        """Insert a new employee and return the generated ID."""

        if not isinstance(employee, Employee):
            raise ValidationError("Expected an Employee object.")

        try:
            employee.validate()
        except ValueError as error:
            raise ValidationError(str(error)) from error

        data = employee.to_dict()

        missing_fields = self.REQUIRED_CREATE_FIELDS - set(data)

        if missing_fields:
            raise ValidationError(
                "Employee model is missing required database fields: "
                + ", ".join(sorted(missing_fields))
                + ". Update the Employee model before creating records."
            )

        columns = list(self.REQUIRED_CREATE_FIELDS)

        query = f"""
            INSERT INTO {self.TABLE}
            ({", ".join(f"`{column}`" for column in columns)})
            VALUES ({", ".join(["%s"] * len(columns))})
        """

        values = tuple(data[column] for column in columns)

        try:
            with self.transaction() as cursor:
                cursor.execute(query, values)
                employee_id = cursor.lastrowid
                cursor.execute(
                    """INSERT INTO oltp.employee_change_log
                    (employee_id, effective_date, change_type, department_id,
                     job_role_id, job_level, monthly_income)
                    VALUES (%s, %s, 'Hire', %s, %s, %s, %s)""",
                    (
                        employee_id,
                        data["hire_date"],
                        data["department_id"],
                        data["job_role_id"],
                        data["job_level"],
                        data["monthly_income"],
                    ),
                )
                self._sync_employee_dimension(cursor, employee_id)
            # with self.transaction() as cursor:
            #     cursor.callproc("dw.sp_run_full_etl")

            #     for result in cursor.stored_results():
            #         result.fetchall()

            return employee_id

        except DatabaseError as error:
            self._raise_database_error(
                error,
                "Employee creation failed",
                "Employee code or email already exists."
            )

        except (ValidationError, DuplicateError):
            raise

        except Exception as error:
            raise DatabaseError(
                "Unexpected error while creating employee.",
                error
            ) from error


    # ---------------------------------------------------------
    # READ
    # ---------------------------------------------------------

    def get_by_id(self, employee_id):
        """Fetch an employee using its primary key."""

        if not isinstance(employee_id, int) or employee_id <= 0:
            raise ValidationError("Employee ID must be a positive integer.")

        connection = None
        cursor = None

        try:
            connection, cursor = self.get_connection()

            query = f"""
                SELECT *
                FROM {self.TABLE}
                WHERE employee_id = %s
            """

            cursor.execute(query, (employee_id,))
            row = cursor.fetchone()

            if row is None:
                raise NotFoundError(
                    f"Employee with ID {employee_id} was not found."
                )

            return Employee.from_row(row)

        except (ValidationError, NotFoundError, DatabaseError):
            raise

        except mysql.connector.Error as error:
            raise DatabaseError(
                "Failed to retrieve employee.",
                error
            ) from error

        finally:
            if cursor:
                cursor.close()

            if connection:
                connection.close()

    def get_all(self, limit=100, offset=0):
        """Fetch employees with pagination."""

        if not isinstance(limit, int) or limit <= 0:
            raise ValidationError("Limit must be a positive integer.")

        if not isinstance(offset, int) or offset < 0:
            raise ValidationError("Offset cannot be negative.")

        connection = None
        cursor = None

        try:
            connection, cursor = self.get_connection()

            query = f"""
                SELECT *
                FROM {self.TABLE}
                ORDER BY employee_id
                LIMIT %s OFFSET %s
            """

            cursor.execute(query, (limit, offset))
            rows = cursor.fetchall()

            return [
                Employee.from_row(row)
                for row in rows
            ]

        except mysql.connector.Error as error:
            raise DatabaseError(
                "Failed to retrieve employees.",
                error
            ) from error

        finally:
            if cursor:
                cursor.close()

            if connection:
                connection.close()

    # ---------------------------------------------------------
    # UPDATE
    # ---------------------------------------------------------

    def update(self, employee_id, employee):
        """Update permitted employee details."""

        if not isinstance(employee_id, int) or employee_id <= 0:
            raise ValidationError("Employee ID must be a positive integer.")

        if not isinstance(employee, Employee):
            raise ValidationError("Expected an Employee object.")

        try:
            employee.validate()
        except ValueError as error:
            raise ValidationError(str(error)) from error

        data = employee.to_dict()

        updates = {
            field: data[field]
            for field in self.UPDATABLE_FIELDS
            if field in data
        }

        if not updates:
            raise ValidationError("No permitted fields provided for update.")

        assignments = ", ".join(
            f"`{column}` = %s"
            for column in updates
        )

        values = tuple(updates.values()) + (employee_id,)

        query = f"""
            UPDATE {self.TABLE}
            SET {assignments}
            WHERE employee_id = %s
        """

        try:
            with self.transaction() as cursor:

                cursor.execute(
                    f"SELECT employee_id FROM {self.TABLE} "
                    "WHERE employee_id = %s FOR UPDATE",
                    (employee_id,)
                )

                if cursor.fetchone() is None:
                    raise NotFoundError(
                        f"Employee with ID {employee_id} was not found."
                    )

                cursor.execute(query, values)

                self._sync_employee_dimension(cursor, employee_id)





            return True

        except DatabaseError as error:
            self._raise_database_error(
                error,
                "Employee update failed",
                "The email address is already assigned to another employee."
            )

        except (ValidationError, NotFoundError, DuplicateError):
            raise

        except Exception as error:
            raise DatabaseError(
                "Unexpected error while updating employee.",
                error
            ) from error



    # ---------------------------------------------------------
    # DELETE
    # ---------------------------------------------------------

    def delete(self, employee_id):
        """Delete an employee using its primary key."""

        if not isinstance(employee_id, int) or employee_id <= 0:
            raise ValidationError("Employee ID must be a positive integer.")

        try:
            with self.transaction() as cursor:

                cursor.execute(
                    f"SELECT employee_id FROM {self.TABLE} "
                    "WHERE employee_id = %s FOR UPDATE",
                    (employee_id,)
                )

                if cursor.fetchone() is None:
                    raise NotFoundError(
                        f"Employee with ID {employee_id} was not found."
                    )

                cursor.execute(
                    f"DELETE FROM {self.TABLE} WHERE employee_id = %s",
                    (employee_id,)
                )

            return True

        except mysql.connector.IntegrityError as error:
            raise DatabaseError(
                "Cannot delete this employee because related records exist. "
                "Consider marking the employee inactive instead.",
                error
            ) from error

        except (ValidationError, NotFoundError, DatabaseError):
            raise

        except Exception as error:
            raise DatabaseError(
                "Unexpected error while deleting employee.",
                error
            ) from error

    def update_employment(
        self,
        employee_id,
        *,
        department_id=None,
        job_role_id=None,
        job_level=None,
        monthly_income=None,
        effective_date=None,
        change_type=None,
    ):
        """Update tracked employment attributes and append an audit event."""
        self._validate_id(employee_id)
        effective_date = effective_date or date.today()
        if isinstance(effective_date, str):
            effective_date = date.fromisoformat(effective_date)
        if not isinstance(effective_date, date):
            raise ValidationError("Effective date must be a valid date.")

        updates = {
            key: value
            for key, value in {
                "department_id": department_id,
                "job_role_id": job_role_id,
                "job_level": job_level,
                "monthly_income": monthly_income,
            }.items()
            if value is not None
        }
        if not updates:
            raise ValidationError("At least one employment field is required.")
        if job_level is not None and (
            not isinstance(job_level, int) or not 1 <= job_level <= 5
        ):
            raise ValidationError("Job level must be between 1 and 5.")
        if monthly_income is not None and monthly_income <= 0:
            raise ValidationError("Monthly income must be greater than zero.")
        if change_type is None:
            changed_fields = set(updates)
            if "department_id" in changed_fields or "job_role_id" in changed_fields:
                change_type = "Transfer"
            elif "job_level" in changed_fields:
                change_type = "Promotion"
            else:
                change_type = "SalaryHike"
        if change_type not in {"Transfer", "Promotion", "SalaryHike"}:
            raise ValidationError("Invalid employment change type.")

        try:
            with self.transaction() as cursor:
                cursor.execute(
                    f"""SELECT department_id, job_role_id, job_level, monthly_income
                    FROM {self.TABLE} WHERE employee_id=%s FOR UPDATE""",
                    (employee_id,),
                )

                current = cursor.fetchone()
                if current is None:
                    raise NotFoundError(f"Employee with ID {employee_id} was not found.")


                cursor.execute(
                    """
                    SELECT MAX(effective_date) AS latest_effective_date
                    FROM oltp.employee_change_log
                    WHERE employee_id = %s
                    """,
                    (employee_id,)
                )

                latest_event = cursor.fetchone()["latest_effective_date"]

                if latest_event is not None and effective_date <= latest_event:
                    raise ValidationError(
                        "Effective date must be later than the employee's latest "
                        f"recorded employment change ({latest_event})."
                    )


                state = {
                    "department_id": current["department_id"],
                    "job_role_id": current["job_role_id"],
                    "job_level": current["job_level"],
                    "monthly_income": current["monthly_income"],
                }
                changed = {}
                for field, value in updates.items():
                    if field == "monthly_income":
                        same = Decimal(str(state[field])).quantize(Decimal("0.01")) == Decimal(str(value)).quantize(Decimal("0.01"))
                    else:
                        same = state[field] == value
                    if not same:
                        changed[field] = value
                if not changed:
                    raise ValidationError("No employment attributes changed; no history event was created.")
                state.update(changed)
                assignments = ", ".join(f"`{field}`=%s" for field in changed)
                cursor.execute(
                    f"UPDATE {self.TABLE} SET {assignments} WHERE employee_id=%s",
                    tuple(changed.values()) + (employee_id,),
                )
                cursor.execute(
                    """INSERT INTO oltp.employee_change_log
                    (employee_id, effective_date, change_type, department_id,
                     job_role_id, job_level, monthly_income)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                    (
                        employee_id,
                        effective_date,
                        change_type,
                        state["department_id"],
                        state["job_role_id"],
                        state["job_level"],
                        state["monthly_income"],
                    ),
                )
                # Keep OLTP update, immutable audit event and SCD2 version change atomic.
                self._sync_employee_dimension(cursor, employee_id)
            return True


        except DatabaseError as error:
            self._raise_database_error(
                error,
                "Employment update failed",
                "An employment change already exists for this employee and date."
            )

        except (ValidationError, NotFoundError, DuplicateError):
            raise

        except Exception as error:
            raise DatabaseError(
                "Unexpected employment update failure.",
                error
            ) from error

    def get_change_history(self, employee_id):
        """Return chronological employment changes for an employee."""
        self._validate_id(employee_id)
        connection = cursor = None
        try:
            connection, cursor = self.get_connection()
            cursor.execute(
                """SELECT * FROM oltp.employee_change_log
                WHERE employee_id=%s ORDER BY effective_date, change_id""",
                (employee_id,),
            )
            return cursor.fetchall()
        except mysql.connector.Error as error:
            raise DatabaseError("Failed to retrieve employee history.", error) from error
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()

    @staticmethod
    def _validate_id(employee_id):
        if not isinstance(employee_id, int) or isinstance(employee_id, bool) or employee_id <= 0:
            raise ValidationError("Employee ID must be a positive integer.")
