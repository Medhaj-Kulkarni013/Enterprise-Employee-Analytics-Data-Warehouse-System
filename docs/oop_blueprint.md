# OOP Blueprint – Enterprise Employee Analytics & Data Warehouse System

**Project:** Enterprise Employee Analytics & Data Warehouse System  
**Module Owner:** Member B – OOP Architecture, Streamlit & Deployment  
**Status:** Initial Draft – Subject to Team Review  
**Snapshot Date:** 2025-12-31

---

## 1. Introduction

This document defines the Object-Oriented Programming (OOP) architecture for the Enterprise Employee Analytics & Data Warehouse System.

The application uses Python OOP principles to organize database connectivity, employee-related entities, database operations, ETL processing and analytics.

The architecture is divided into four main layers:

1. Core Layer
2. Entity Layer
3. Manager Layer
4. Pipeline Layer

The objective is to maintain modularity, reusability, maintainability and separation of responsibilities.

## 2. Architecture Overview

### Four-layer architecture

| Layer | Responsibility |
|---|---|
| Core | Database connectivity, Singleton connection management and custom exceptions |
| Entity | Represents Employee, Project and Review objects |
| Manager | Handles CRUD operations and analytical queries |
| Pipeline | Handles preprocessing, synthesis, history generation, staging and ETL execution |

### Application flow

```text
             Streamlit Application
                      |
                      v
                Manager Layer
                      |
                      v
                 Entity Layer
                      |
                      v
                  Core Layer
                      |
                      v
                  MySQL DB

             ETL Pipeline Layer
                      |
                      v
          Preprocessing and Synthesis
                      |
                      v
              History Generation
                      |
                      v
                Staging Loader
                      |
                      v
              ETL Runner / MySQL
```

The exact database and pipeline integration details will be finalized after team discussion.

## 3. Class Inventory

The architecture contains 17 main classes and five custom exception classes.

### 3.1 Core Layer

| Class | Type | Responsibility |
|---|---|---|
| DatabaseConnection | Singleton | Manages shared MySQL connection pool and database access |

**Custom exceptions:**

- `AppError` – Base application exception.
- `DatabaseError` – Database-related errors.
- `ValidationError` – Invalid input or entity data.
- `NotFoundError` – Requested record does not exist.
- `DuplicateError` – Duplicate record encountered.

### 3.2 Entity Layer

| Class | Type | Responsibility |
|---|---|---|
| BaseEntity | Abstract | Defines common entity methods |
| Employee | Concrete | Represents employee information |
| Project | Concrete | Represents project information |
| Review | Concrete | Represents employee performance reviews |

**BaseEntity methods:**
- `validate()`
- `to_dict()`

**Employee methods:**
- `validate()`
- `to_dict()`
- `from_row()`
- `promote()`
- `transfer()`
- `tenure_years()`

**Project methods:**
- `validate()`
- `to_dict()`
- `is_active()`
- `duration_days()`

**Review methods:**
- `validate()`
- `to_dict()`
- `overall_satisfaction()`
- `is_high_performer()`

### 3.3 Manager Layer

| Class | Inherits From | Responsibility |
|---|---|---|
| BaseManager | DatabaseConnection | Provides database access |
| CrudManager | BaseManager | Defines common CRUD operations |
| EmployeeManager | CrudManager | Employee database operations |
| ProjectManager | CrudManager | Project database operations |
| ReviewManager | CrudManager | Review database operations |
| AnalyticsManager | BaseManager | Analytical queries and reports |

**CrudManager abstract methods:**

- `create(entity)`
- `get_by_id(record_id)`
- `update(record_id, entity)`
- `delete(record_id)`

**AnalyticsManager methods:**

- `get_employee_summary()`
- `get_department_analytics()`
- `get_attrition_analysis()`
- `get_performance_analysis()`

### 3.4 Pipeline Layer

| Class | Type | Responsibility |
|---|---|---|
| PipelineStep | Abstract | Defines the common ETL execution structure |
| Preprocessor | Concrete | Cleans and transforms source data |
| Synthesizer | Concrete | Generates synthetic employee records |
| HistoryGenerator | Concrete | Generates historical employee records for SCD Type 2 |
| StagingLoader | Concrete | Loads prepared data into staging tables |
| EtlRunner | Concrete | Coordinates the ETL execution process |

**PipelineStep template method:**

`run()` follows this execution sequence:

1. Validate input.
2. Execute the processing step.
3. Validate output.
4. Return the result.

The `execute()` method is abstract and must be implemented by concrete pipeline classes.

## 4. Inheritance Structure

The proposed inheritance relationships are:

```text
DatabaseConnection
       |
       v
   BaseManager
       |
       v
   CrudManager (Abstract)
       |
       +------------------+
       |          |       |
       v          v       v
 EmployeeManager  ProjectManager  ReviewManager

BaseManager
    |
    +--------------------+
    |                    |
    v                    v
AnalyticsManager    Other Manager Classes


BaseEntity (Abstract)
       |
       +------------------+
       |          |       |
       v          v       v
   Employee   Project   Review


PipelineStep (Abstract)
       |
       +-------------------------------+
       |          |          |          |
       v          v          v          v
 Preprocessor Synthesizer HistoryGenerator StagingLoader
                                     
PipelineStep
       |
       v
    EtlRunner
```

Note: The exact inheritance and composition relationships of `EtlRunner` and the pipeline components will be confirmed during implementation. The diagram represents the proposed architecture.

## 5. Four Pillars of OOP

### 5.1 Encapsulation

Encapsulation means keeping data and its operations together while controlling direct access to internal attributes.

**Implementation:**
- Employee uses private attributes such as `_email` and `_monthly_income`.
- Properties control access to sensitive attributes.
- Validation is performed through setters and entity methods.

**Example:** Monthly income cannot be set to a negative value.

### 5.2 Abstraction

Abstraction means exposing essential functionality while hiding implementation details.

**Implementation:**
- `BaseEntity` defines abstract entity methods.
- `CrudManager` defines common CRUD operations.
- `PipelineStep` defines the ETL execution structure.

### 5.3 Inheritance

Inheritance allows a class to reuse the functionality of another class.

**Implementation:**
- Employee, Project and Review inherit from BaseEntity.
- EmployeeManager, ProjectManager and ReviewManager inherit from CrudManager.
- CrudManager inherits from BaseManager.
- Concrete pipeline classes inherit from PipelineStep.

### 5.4 Polymorphism

Polymorphism allows different classes to implement the same method in their own way.

**Implementation:**
- Each entity implements `validate()` and `to_dict()`.
- Each manager implements CRUD operations for its respective entity.
- Each pipeline step implements its own `execute()` method.

## 6. Design Patterns

### 6.1 Singleton Pattern

**Class:** DatabaseConnection

Purpose:
- Maintain a controlled database connection manager instance.
- Avoid repeatedly creating connection pools.
- Provide shared database connectivity.

The design uses one instance per manager class while sharing the same underlying connection pool.

### 6.2 Repository / Data Access Layer Pattern

**Classes:** EmployeeManager, ProjectManager, ReviewManager and AnalyticsManager.

Purpose:
- Separate database operations from application logic.
- Keep SQL queries inside manager classes.
- Make database operations reusable and easier to maintain.

### 6.3 Factory Method Pattern

**Class:** Employee

Method: `from_row()`

Purpose:
- Create an Employee object from a database result row.
- Convert database records into Python objects.

### 6.4 Template Method Pattern

**Class:** PipelineStep

Method: `run()`

Purpose:
- Define a fixed execution sequence for all pipeline steps.
- Allow subclasses to provide their own processing implementation through `execute()`.

## 7. Database Connectivity

The application uses MySQL as its database.

The `DatabaseConnection` class manages the shared connection pool.

Database configuration should be loaded through environment variables rather than hardcoded credentials.

Example environment variables:

```env
DB_HOST=
DB_PORT=
DB_USER=
DB_PASSWORD=
DB_NAME=
```

Database operations should follow these practices:

- Use parameterized SQL queries with `%s` placeholders.
- Avoid constructing SQL queries using f-strings.
- Handle database errors using custom exceptions.
- Use transactions for operations requiring atomicity.
- Close cursors and return connections to the pool after use.

## 8. Exception Handling

All application-specific exceptions inherit from `AppError`.

```text
Exception
    |
    v
  AppError
    |
    +------------------+
    |        |         |
    v        v         v
DatabaseError
ValidationError
NotFoundError
DuplicateError
```

The custom exception hierarchy provides consistent error handling throughout the application.

## 9. Coding Standards

The following standards should be followed:

1. Use Python naming conventions.
2. Use PascalCase for class names.
3. Use snake_case for methods and variables.
4. Add docstrings to classes and methods.
5. Use type hints where appropriate.
6. Keep database logic inside manager classes.
7. Keep entity validation inside entity classes.
8. Use environment variables for credentials.
9. Use parameterized SQL queries.
10. Avoid unnecessary duplication of code.

## 10. Testing Strategy

The initial OOP blueprint tests should verify:

| Test | Expected Result |
|---|---|
| Instantiate BaseEntity | TypeError |
| Instantiate CrudManager | TypeError |
| Instantiate PipelineStep | TypeError |
| Instantiate EmployeeManager | Successful |
| Instantiate ProjectManager | Successful |
| Instantiate ReviewManager | Successful |
| Instantiate AnalyticsManager | Successful |
| Create DatabaseConnection twice | Same instance |
| Access pool through different manager classes | Same shared pool |

Additional tests will cover entity validation, manager operations, pipeline execution and database integration.

## 11. Pending Team Decisions

The following items require confirmation before the architecture is finalized:

- Final OLTP and OLAP database schemas.
- Employee, Project and Review foreign-key relationships.
- Exact attributes and method signatures required by each manager.
- History generation and SCD Type 2 implementation details.
- Staging table structure and loading strategy.
- Final ETL execution sequence.
- Streamlit page responsibilities and integration.

## 12. Conclusion

This OOP architecture provides a modular foundation for the Enterprise Employee Analytics & Data Warehouse System.

By separating database connectivity, entities, managers and pipeline processing, the system becomes easier to develop, test, maintain and extend.

This document serves as the initial technical reference for the development team. It will be updated as the database schema and implementation details are finalized.