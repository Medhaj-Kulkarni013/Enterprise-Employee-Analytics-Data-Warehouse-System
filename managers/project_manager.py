"""Manager responsible for project CRUD operations."""

import mysql.connector

from core.exceptions import DatabaseError, DuplicateError, NotFoundError, ValidationError
from managers.crud_manager import CrudManager
from models.project import Project


class ProjectManager(CrudManager):
    """Handles project-related database operations."""

    TABLE = "oltp.project"

    def create(self, project):
        if not isinstance(project, Project):
            raise ValidationError("Expected a Project object.")
        try:
            project.validate()
        except ValueError as error:
            raise ValidationError(str(error)) from error
        data = project.to_dict()
        query = f"""
            INSERT INTO {self.TABLE}
            (project_code, project_name, department_id, start_date, end_date, project_status)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        try:
            with self.transaction() as cursor:
                cursor.execute(query, (
                    data["project_code"], data["project_name"], data["department_id"],
                    data["start_date"], data["end_date"], data["status"]
                ))
                return cursor.lastrowid
        except mysql.connector.IntegrityError as error:
            if error.errno == 1062:
                raise DuplicateError("Project code already exists.", error) from error
            raise DatabaseError("Project creation violated a database constraint.", error) from error
        except (ValidationError, DuplicateError, DatabaseError):
            raise
        except Exception as error:
            raise DatabaseError("Unexpected error while creating project.", error) from error

    def get_by_id(self, project_id):
        self._validate_id(project_id)
        connection = cursor = None
        try:
            connection, cursor = self.get_connection()
            cursor.execute(f"SELECT * FROM {self.TABLE} WHERE project_id = %s", (project_id,))
            row = cursor.fetchone()
            if row is None:
                raise NotFoundError(f"Project with ID {project_id} was not found.")
            return Project.from_row(row)
        except (ValidationError, NotFoundError, DatabaseError):
            raise
        except mysql.connector.Error as error:
            raise DatabaseError("Failed to retrieve project.", error) from error
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()

    def get_all(self, limit=100, offset=0):
        if not isinstance(limit, int) or limit <= 0:
            raise ValidationError("Limit must be a positive integer.")
        if not isinstance(offset, int) or offset < 0:
            raise ValidationError("Offset cannot be negative.")
        connection = cursor = None
        try:
            connection, cursor = self.get_connection()
            cursor.execute(
                f"SELECT * FROM {self.TABLE} ORDER BY project_id LIMIT %s OFFSET %s",
                (limit, offset)
            )
            return [Project.from_row(row) for row in cursor.fetchall()]
        except mysql.connector.Error as error:
            raise DatabaseError("Failed to retrieve projects.", error) from error
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()

    def update(self, project_id, project):
        self._validate_id(project_id)
        if not isinstance(project, Project):
            raise ValidationError("Expected a Project object.")
        try:
            project.validate()
        except ValueError as error:
            raise ValidationError(str(error)) from error
        data = project.to_dict()
        try:
            with self.transaction() as cursor:
                cursor.execute(
                    f"SELECT project_id FROM {self.TABLE} WHERE project_id=%s FOR UPDATE",
                    (project_id,)
                )
                if cursor.fetchone() is None:
                    raise NotFoundError(f"Project with ID {project_id} was not found.")
                cursor.execute(
                    f"""UPDATE {self.TABLE}
                    SET project_code=%s, project_name=%s, department_id=%s,
                        start_date=%s, end_date=%s, project_status=%s
                    WHERE project_id=%s""",
                    (data["project_code"], data["project_name"], data["department_id"],
                     data["start_date"], data["end_date"], data["status"], project_id)
                )
            return True
        except mysql.connector.IntegrityError as error:
            if error.errno == 1062:
                raise DuplicateError("Project code already exists.", error) from error
            raise DatabaseError("Project update violated a database constraint.", error) from error
        except (ValidationError, NotFoundError, DuplicateError, DatabaseError):
            raise
        except Exception as error:
            raise DatabaseError("Unexpected error while updating project.", error) from error

    def delete(self, project_id):
        self._validate_id(project_id)
        try:
            with self.transaction() as cursor:
                cursor.execute(f"DELETE FROM {self.TABLE} WHERE project_id=%s", (project_id,))
                if cursor.rowcount == 0:
                    raise NotFoundError(f"Project with ID {project_id} was not found.")
            return True
        except mysql.connector.IntegrityError as error:
            raise DatabaseError("Cannot delete a project with related records.", error) from error
        except (ValidationError, NotFoundError, DatabaseError):
            raise
        except Exception as error:
            raise DatabaseError("Unexpected error while deleting project.", error) from error

    @staticmethod
    def _validate_id(record_id):
        if not isinstance(record_id, int) or isinstance(record_id, bool) or record_id <= 0:
            raise ValidationError("Project ID must be a positive integer.")
