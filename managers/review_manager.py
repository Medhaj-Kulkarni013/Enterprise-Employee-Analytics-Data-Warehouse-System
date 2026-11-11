"""Manager responsible for employee review CRUD operations."""

import mysql.connector

from core.exceptions import DatabaseError, DuplicateError, NotFoundError, ValidationError
from managers.crud_manager import CrudManager
from models.review import Review


class ReviewManager(CrudManager):
    """Handles employee performance review database operations."""

    TABLE = "oltp.review"

    def create(self, review):
        if not isinstance(review, Review):
            raise ValidationError("Expected a Review object.")
        try:
            review.validate()
        except ValueError as error:
            raise ValidationError(str(error)) from error
        data = review.to_dict()
        query = f"""
            INSERT INTO {self.TABLE}
            (employee_id, reviewer_id, project_id, review_date, performance_rating,
             job_satisfaction, environment_satisfaction, relationship_satisfaction,
             work_life_balance, job_involvement, percent_salary_hike,
             training_times_last_year)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        values = tuple(data[key] for key in (
            "employee_id", "reviewer_id", "project_id", "review_date",
            "performance_rating", "job_satisfaction", "environment_satisfaction",
            "relationship_satisfaction", "work_life_balance", "job_involvement",
            "percent_salary_hike", "training_times_last_year"
        ))
        try:
            with self.transaction() as cursor:
                cursor.execute(query, values)
                return cursor.lastrowid
        except mysql.connector.IntegrityError as error:
            if error.errno == 1062:
                raise DuplicateError("A review already exists for this employee and date.", error) from error
            raise DatabaseError("Review creation violated a database constraint.", error) from error
        except (ValidationError, DuplicateError, DatabaseError):
            raise
        except Exception as error:
            raise DatabaseError("Unexpected error while creating review.", error) from error

    def get_by_id(self, review_id):
        self._validate_id(review_id)
        connection = cursor = None
        try:
            connection, cursor = self.get_connection()
            cursor.execute(f"SELECT * FROM {self.TABLE} WHERE review_id=%s", (review_id,))
            row = cursor.fetchone()
            if row is None:
                raise NotFoundError(f"Review with ID {review_id} was not found.")
            return Review.from_row(row)
        except (ValidationError, NotFoundError, DatabaseError):
            raise
        except mysql.connector.Error as error:
            raise DatabaseError("Failed to retrieve review.", error) from error
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
                f"SELECT * FROM {self.TABLE} ORDER BY review_id LIMIT %s OFFSET %s",
                (limit, offset)
            )
            return [Review.from_row(row) for row in cursor.fetchall()]
        except mysql.connector.Error as error:
            raise DatabaseError("Failed to retrieve reviews.", error) from error
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()

    def update(self, review_id, review):
        self._validate_id(review_id)
        if not isinstance(review, Review):
            raise ValidationError("Expected a Review object.")
        try:
            review.validate()
        except ValueError as error:
            raise ValidationError(str(error)) from error
        data = review.to_dict()
        columns = (
            "employee_id", "reviewer_id", "project_id", "review_date",
            "performance_rating", "job_satisfaction", "environment_satisfaction",
            "relationship_satisfaction", "work_life_balance", "job_involvement",
            "percent_salary_hike", "training_times_last_year"
        )
        try:
            with self.transaction() as cursor:
                cursor.execute(
                    f"SELECT review_id FROM {self.TABLE} WHERE review_id=%s FOR UPDATE",
                    (review_id,)
                )
                if cursor.fetchone() is None:
                    raise NotFoundError(f"Review with ID {review_id} was not found.")
                cursor.execute(
                    f"""UPDATE {self.TABLE}
                    SET {", ".join(f"{column}=%s" for column in columns)}
                    WHERE review_id=%s""",
                    tuple(data[column] for column in columns) + (review_id,)
                )
            return True
        except mysql.connector.IntegrityError as error:
            if error.errno == 1062:
                raise DuplicateError("A review already exists for this employee and date.", error) from error
            raise DatabaseError("Review update violated a database constraint.", error) from error
        except (ValidationError, NotFoundError, DuplicateError, DatabaseError):
            raise
        except Exception as error:
            raise DatabaseError("Unexpected error while updating review.", error) from error

    def delete(self, review_id):
        self._validate_id(review_id)
        try:
            with self.transaction() as cursor:
                cursor.execute(f"DELETE FROM {self.TABLE} WHERE review_id=%s", (review_id,))
                if cursor.rowcount == 0:
                    raise NotFoundError(f"Review with ID {review_id} was not found.")
            return True
        except (ValidationError, NotFoundError, DatabaseError):
            raise
        except Exception as error:
            raise DatabaseError("Unexpected error while deleting review.", error) from error

    @staticmethod
    def _validate_id(record_id):
        if not isinstance(record_id, int) or isinstance(record_id, bool) or record_id <= 0:
            raise ValidationError("Review ID must be a positive integer.")
