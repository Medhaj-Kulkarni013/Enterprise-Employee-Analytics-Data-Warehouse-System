"""Manager for employee project assignment CRUD operations."""

import mysql.connector

from core.exceptions import DatabaseError, DuplicateError, NotFoundError, ValidationError
from managers.crud_manager import CrudManager
from models.assignment import Assignment


class AssignmentManager(CrudManager):
    """Handles allocations stored in oltp.assignment."""

    TABLE = "oltp.assignment"

    def create(self, assignment):
        self._validate_entity(assignment)
        data = assignment.to_dict()
        try:
            with self.transaction() as cursor:
                cursor.execute(
                    f"""INSERT INTO {self.TABLE}
                    (employee_id, project_id, role_on_project, allocation_pct,
                     start_date, end_date)
                    VALUES (%s, %s, %s, %s, %s, %s)""",
                    tuple(data[key] for key in (
                        "employee_id", "project_id", "role_on_project",
                        "allocation_pct", "start_date", "end_date"
                    ))
                )
                return cursor.lastrowid
        except mysql.connector.IntegrityError as error:
            if error.errno == 1062:
                raise DuplicateError(
                    "An assignment already exists for this employee, project, and start date.",
                    error,
                ) from error
            raise DatabaseError("Assignment violates a database constraint.", error) from error
        except (ValidationError, DuplicateError, DatabaseError):
            raise
        except Exception as error:
            raise DatabaseError("Unexpected error while creating assignment.", error) from error

    def get_by_id(self, assignment_id):
        self._validate_id(assignment_id)
        connection = cursor = None
        try:
            connection, cursor = self.get_connection()
            cursor.execute(
                f"SELECT * FROM {self.TABLE} WHERE assignment_id=%s",
                (assignment_id,),
            )
            row = cursor.fetchone()
            if row is None:
                raise NotFoundError(f"Assignment with ID {assignment_id} was not found.")
            return Assignment.from_row(row)
        except (ValidationError, NotFoundError, DatabaseError):
            raise
        except mysql.connector.Error as error:
            raise DatabaseError("Failed to retrieve assignment.", error) from error
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()

    def get_all(self, employee_id=None, project_id=None, limit=100, offset=0):
        if not isinstance(limit, int) or limit <= 0:
            raise ValidationError("Limit must be a positive integer.")
        if not isinstance(offset, int) or offset < 0:
            raise ValidationError("Offset cannot be negative.")
        clauses = []
        params = []
        if employee_id is not None:
            self._validate_id(employee_id, "Employee")
            clauses.append("employee_id=%s")
            params.append(employee_id)
        if project_id is not None:
            self._validate_id(project_id, "Project")
            clauses.append("project_id=%s")
            params.append(project_id)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        connection = cursor = None
        try:
            connection, cursor = self.get_connection()
            cursor.execute(
                f"SELECT * FROM {self.TABLE}{where} "
                "ORDER BY assignment_id LIMIT %s OFFSET %s",
                tuple(params) + (limit, offset),
            )
            return [Assignment.from_row(row) for row in cursor.fetchall()]
        except mysql.connector.Error as error:
            raise DatabaseError("Failed to retrieve assignments.", error) from error
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()

    def update(self, assignment_id, assignment):
        self._validate_id(assignment_id)
        self._validate_entity(assignment)
        data = assignment.to_dict()
        try:
            with self.transaction() as cursor:
                cursor.execute(
                    f"SELECT assignment_id FROM {self.TABLE} WHERE assignment_id=%s FOR UPDATE",
                    (assignment_id,),
                )
                if cursor.fetchone() is None:
                    raise NotFoundError(f"Assignment with ID {assignment_id} was not found.")
                cursor.execute(
                    f"""UPDATE {self.TABLE}
                    SET employee_id=%s, project_id=%s, role_on_project=%s,
                        allocation_pct=%s, start_date=%s, end_date=%s
                    WHERE assignment_id=%s""",
                    tuple(data[key] for key in (
                        "employee_id", "project_id", "role_on_project",
                        "allocation_pct", "start_date", "end_date"
                    )) + (assignment_id,),
                )
            return True
        except mysql.connector.IntegrityError as error:
            if error.errno == 1062:
                raise DuplicateError("Duplicate employee project assignment.", error) from error
            raise DatabaseError("Assignment update violates a database constraint.", error) from error
        except (ValidationError, NotFoundError, DuplicateError, DatabaseError):
            raise
        except Exception as error:
            raise DatabaseError("Unexpected error while updating assignment.", error) from error

    def delete(self, assignment_id):
        self._validate_id(assignment_id)
        try:
            with self.transaction() as cursor:
                cursor.execute(
                    f"DELETE FROM {self.TABLE} WHERE assignment_id=%s",
                    (assignment_id,),
                )
                if cursor.rowcount == 0:
                    raise NotFoundError(f"Assignment with ID {assignment_id} was not found.")
            return True
        except (ValidationError, NotFoundError, DatabaseError):
            raise
        except Exception as error:
            raise DatabaseError("Unexpected error while deleting assignment.", error) from error

    @staticmethod
    def _validate_entity(assignment):
        if not isinstance(assignment, Assignment):
            raise ValidationError("Expected an Assignment object.")
        try:
            assignment.validate()
        except ValueError as error:
            raise ValidationError(str(error)) from error

    @staticmethod
    def _validate_id(record_id, label="Assignment"):
        if not isinstance(record_id, int) or isinstance(record_id, bool) or record_id <= 0:
            raise ValidationError(f"{label} ID must be a positive integer.")
