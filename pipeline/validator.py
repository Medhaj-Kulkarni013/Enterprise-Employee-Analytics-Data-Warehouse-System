
from pathlib import Path
import pandas as pd

from pipeline.base_step import PipelineStep


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_DATE = pd.Timestamp("2025-12-31")

OUTPUT_COLUMNS = [
    "employee_id", "employee_code", "source_employee_number",
    "first_name", "last_name", "email", "gender", "date_of_birth",
    "marital_status", "education_level", "education_field",
    "distance_from_home_km", "num_companies_worked",
    "prior_experience_years", "stock_option_level", "business_travel",
    "overtime_flag", "hire_date", "department", "job_role", "job_level",
    "monthly_income", "manager_id", "is_active", "termination_date",
    "performance_rating", "percent_salary_hike",
    "training_times_last_year", "job_satisfaction",
    "environment_satisfaction", "relationship_satisfaction",
    "work_life_balance", "job_involvement"
]


class DataValidator(PipelineStep):
    def __init__(
        self,
        raw_path=PROJECT_ROOT / "data/raw/ibm_hr_dataset.csv",
        clean_path=PROJECT_ROOT / "data/processed/employees_clean_base.csv",
        synthetic_path=PROJECT_ROOT / "data/synthetic/employees_100k.csv",
        report_path=PROJECT_ROOT / "reports/validation_report.txt",
        expected_records=100_000,
    ):
        super().__init__("Data Validation")

        self.raw_path = Path(raw_path)
        self.clean_path = Path(clean_path)
        self.synthetic_path = Path(synthetic_path)
        self.report_path = Path(report_path)
        self.expected_records = expected_records

        self.results = []
        self.raw_data = None
        self.clean_data = None
        self.synthetic_data = None

    def validate_input(self):
        paths = [
            self.raw_path,
            self.clean_path,
            self.synthetic_path,
        ]

        for path in paths:
            if not path.exists():
                raise FileNotFoundError(f"Required input file not found: {path}")

    def _add_check(self, name, passed, details):
        self.results.append({
            "name": name,
            "passed": bool(passed),
            "details": str(details),
        })

    def _check_structure(self):
        df = self.synthetic_data

        self._add_check(
            "Synthetic row count",
            len(df) == self.expected_records,
            f"Expected {self.expected_records:,}; found {len(df):,}",
        )

        self._add_check(
            "Synthetic column count",
            len(df.columns) == len(OUTPUT_COLUMNS),
            f"Expected {len(OUTPUT_COLUMNS)}; found {len(df.columns)}",
        )

        self._add_check(
            "Exact column names and order",
            list(df.columns) == OUTPUT_COLUMNS,
            "Output columns match the required 33-column schema."
            if list(df.columns) == OUTPUT_COLUMNS
            else "Output columns do not match the required schema/order.",
        )

    def _check_uniqueness(self):
        df = self.synthetic_data

        for column in ["employee_id", "employee_code", "email"]:
            if column not in df.columns:
                self._add_check(
                    f"Unique {column}",
                    False,
                    f"Column {column} is missing.",
                )
                continue

            duplicate_count = int(df[column].duplicated().sum())

            self._add_check(
                f"Unique {column}",
                duplicate_count == 0 and df[column].notna().all(),
                f"Duplicate values: {duplicate_count}; "
                f"null values: {int(df[column].isna().sum())}",
            )

        if "employee_id" in df.columns:
            ids = pd.to_numeric(df["employee_id"], errors="coerce")
            expected_ids = set(range(1, self.expected_records + 1))
            actual_ids = set(ids.dropna().astype(int))

            self._add_check(
                "Employee ID sequence",
                actual_ids == expected_ids and ids.notna().all(),
                "Employee IDs must cover the sequence "
                f"1 to {self.expected_records:,}.",
            )

    def _check_nulls(self):
        df = self.synthetic_data
        allowed_null_columns = {"manager_id", "termination_date"}

        unexpected_nulls = {
            column: int(count)
            for column, count in df.isna().sum().items()
            if count > 0 and column not in allowed_null_columns
        }

        self._add_check(
            "Unexpected null values",
            len(unexpected_nulls) == 0,
            unexpected_nulls if unexpected_nulls else "No unexpected nulls.",
        )

    def _check_dates(self):
        df = self.synthetic_data

        dob = pd.to_datetime(df["date_of_birth"], errors="coerce")
        hire = pd.to_datetime(df["hire_date"], errors="coerce")
        termination = pd.to_datetime(
            df["termination_date"], errors="coerce"
        )

        valid_dob = dob.notna() & (dob <= SNAPSHOT_DATE)
        self._add_check(
            "Valid date of birth",
            valid_dob.all(),
            f"Invalid or missing DOB values: {int((~valid_dob).sum())}",
        )

        valid_hire = hire.notna() & (hire <= SNAPSHOT_DATE)
        self._add_check(
            "Valid hire dates",
            valid_hire.all(),
            f"Invalid, missing, or future hire dates: "
            f"{int((~valid_hire).sum())}",
        )

        adult_at_hire = (
            dob.notna()
            & hire.notna()
            & (hire >= dob + pd.DateOffset(years=18))
        )

        self._add_check(
            "Employee was at least 18 at hire",
            adult_at_hire.all(),
            f"Employees failing age-at-hire check: "
            f"{int((~adult_at_hire).sum())}",
        )

        active = df["is_active"].eq(1)
        attrited = df["is_active"].eq(0)

        active_without_termination = active & termination.isna()
        attrited_with_termination = attrited & termination.notna()

        self._add_check(
            "Active employees have no termination date",
            active_without_termination.sum() == active.sum(),
            f"Active employees: {int(active.sum())}; "
            f"active employees with termination dates: "
            f"{int((active & termination.notna()).sum())}",
        )

        self._add_check(
            "Attrited employees have termination dates",
            attrited_with_termination.sum() == attrited.sum(),
            f"Attrited employees: {int(attrited.sum())}; "
            f"attrited employees missing termination dates: "
            f"{int((attrited & termination.isna()).sum())}",
        )

        termination_after_hire = (
            termination.isna()
            | (hire.notna() & (termination > hire))
        )

        self._add_check(
            "Termination date is after hire date",
            termination_after_hire.all(),
            f"Invalid termination dates: "
            f"{int((~termination_after_hire).sum())}",
        )

        termination_before_snapshot = (
            termination.isna() | (termination <= SNAPSHOT_DATE)
        )

        self._add_check(
            "Termination date is on or before snapshot",
            termination_before_snapshot.all(),
            f"Termination dates after snapshot: "
            f"{int((~termination_before_snapshot).sum())}",
        )

        valid_status = df["is_active"].isin([0, 1])

        self._add_check(
            "Valid employment status values",
            valid_status.all(),
            f"Invalid status values: "
            f"{int((~valid_status).sum())}",
        )

    def _check_experience(self):
        df = self.synthetic_data

        experience = pd.to_numeric(
            df["prior_experience_years"], errors="coerce"
        )

        valid_experience = experience.notna() & (experience >= 0)

        self._add_check(
            "Non-negative prior experience",
            valid_experience.all(),
            f"Invalid prior experience values: "
            f"{int((~valid_experience).sum())}",
        )

    def _check_salary_bands(self):
        clean = self.clean_data
        synthetic = self.synthetic_data

        source = clean.copy()
        source["JobLevel"] = pd.to_numeric(
            source["JobLevel"], errors="coerce"
        )
        source["MonthlyIncome"] = pd.to_numeric(
            source["MonthlyIncome"], errors="coerce"
        )

        salary_bands = source.groupby("JobLevel")[
            "MonthlyIncome"
        ].agg(["min", "max"])

        job_level = pd.to_numeric(
            synthetic["job_level"], errors="coerce"
        )
        income = pd.to_numeric(
            synthetic["monthly_income"], errors="coerce"
        )

        failures = []

        for level in sorted(salary_bands.index.dropna()):
            lower = salary_bands.loc[level, "min"]
            upper = salary_bands.loc[level, "max"]

            mask = job_level == level
            invalid = mask & (
                income.isna() | (income < lower) | (income > upper)
            )

            if invalid.any():
                failures.append(
                    f"JobLevel {int(level)}: {int(invalid.sum())} "
                    f"records outside [{lower}, {upper}]"
                )

        self._add_check(
            "Monthly income within source JobLevel bands",
            len(failures) == 0,
            "; ".join(failures) if failures
            else "All salaries fall within their source JobLevel bands.",
        )

    def _check_managers(self):
        df = self.synthetic_data

        employee_ids = pd.to_numeric(
            df["employee_id"], errors="coerce"
        )
        manager_ids = pd.to_numeric(
            df["manager_id"], errors="coerce"
        )
        job_levels = pd.to_numeric(
            df["job_level"], errors="coerce"
        )

        departments = df["department"]

        employee_lookup = pd.DataFrame({
            "employee_id": employee_ids,
            "job_level": job_levels,
            "department": departments,
        }).dropna(subset=["employee_id"])

        employee_lookup["employee_id"] = (
            employee_lookup["employee_id"].astype(int)
        )

        lookup = employee_lookup.set_index("employee_id")

        manager_present = manager_ids.notna()
        manager_exists = manager_ids.isin(lookup.index)

        existing_manager_rows = manager_present & manager_exists

        manager_levels = manager_ids.map(lookup["job_level"])
        manager_departments = manager_ids.map(lookup["department"])

        higher_level = (
            ~manager_present
            | (manager_levels > job_levels)
        )

        same_department = (
            ~manager_present
            | (manager_departments == departments)
        )

        level_five_without_manager = (
            (job_levels != 5) | manager_ids.isna()
        )

        no_manager_only_level_five = (
            manager_ids.notna() | (job_levels == 5)
        )

        self._add_check(
            "All manager references exist",
            (~manager_present | manager_exists).all(),
            f"Employees with missing manager references: "
            f"{int((manager_present & ~manager_exists).sum())}",
        )

        self._add_check(
            "Managers have a higher JobLevel",
            higher_level.all(),
            f"Invalid manager hierarchy records: "
            f"{int((~higher_level).sum())}",
        )

        self._add_check(
            "Managers belong to the same department",
            same_department.all(),
            f"Cross-department manager assignments: "
            f"{int((~same_department).sum())}",
        )

        self._add_check(
            "JobLevel 5 employees have no manager",
            level_five_without_manager.all(),
            f"JobLevel 5 employees with a manager: "
            f"{int(((job_levels == 5) & manager_ids.notna()).sum())}",
        )

        self._add_check(
            "Only JobLevel 5 employees have no manager",
            no_manager_only_level_five.all(),
            f"Employees below JobLevel 5 without a manager: "
            f"{int((manager_ids.isna() & (job_levels != 5)).sum())}",
        )

        self._add_check(
            "Manager-less employee count",
            int(manager_ids.isna().sum()) == 4778,
            f"Expected 4,778; found {int(manager_ids.isna().sum()):,}",
        )

    def _check_distributions(self):
        raw = self.raw_data
        synthetic = self.synthetic_data

        # Department distribution comparison
        source_department = raw["Department"].value_counts(normalize=True)
        synthetic_department = synthetic[
            "department"
        ].value_counts(normalize=True)

        departments = sorted(
            set(source_department.index) |
            set(synthetic_department.index)
        )

        department_differences = {}

        for department in departments:
            source_pct = source_department.get(department, 0) * 100
            synthetic_pct = synthetic_department.get(department, 0) * 100

            department_differences[department] = {
                "source_pct": round(source_pct, 2),
                "synthetic_pct": round(synthetic_pct, 2),
                "difference_pp": round(
                    abs(source_pct - synthetic_pct), 2
                ),
            }

        max_department_difference = max(
            (
                value["difference_pp"]
                for value in department_differences.values()
            ),
            default=0,
        )

        self._add_check(
            "Department distribution",
            max_department_difference <= 1.0,
            f"Maximum difference: {max_department_difference:.2f} "
            f"percentage points. Details: {department_differences}",
        )

        # Attrition distribution comparison
        source_attrition = (
            raw["Attrition"].astype(str).str.strip().str.lower()
            == "yes"
        ).mean() * 100

        synthetic_attrition = (
            synthetic["is_active"].eq(0).mean() * 100
        )

        attrition_difference = abs(
            source_attrition - synthetic_attrition
        )

        self._add_check(
            "Attrition distribution",
            attrition_difference <= 1.0,
            f"Source attrition: {source_attrition:.2f}%; "
            f"synthetic attrition: {synthetic_attrition:.2f}%; "
            f"difference: {attrition_difference:.2f} percentage points.",
        )

    def execute(self):
        self.raw_data = pd.read_csv(self.raw_path)
        self.clean_data = pd.read_csv(self.clean_path)
        self.synthetic_data = pd.read_csv(self.synthetic_path)

        self.results = []

        self._check_structure()
        self._check_uniqueness()
        self._check_nulls()
        self._check_dates()
        self._check_experience()
        self._check_salary_bands()
        self._check_managers()
        self._check_distributions()

        passed_count = sum(result["passed"] for result in self.results)
        failed_count = len(self.results) - passed_count
        overall_status = "PASS" if failed_count == 0 else "FAIL"

        lines = [
            "EMPLOYEE ANALYTICS - DATA VALIDATION REPORT",
            "=" * 60,
            f"Snapshot date: {SNAPSHOT_DATE.date()}",
            f"Expected synthetic records: {self.expected_records:,}",
            f"Actual synthetic records: {len(self.synthetic_data):,}",
            f"Actual synthetic columns: {len(self.synthetic_data.columns)}",
            "",
            "VALIDATION RESULTS",
            "-" * 60,
        ]

        for index, result in enumerate(self.results, start=1):
            status = "PASS" if result["passed"] else "FAIL"
            lines.append(f"{index:02d}. [{status}] {result['name']}")
            lines.append(f"    {result['details']}")

        lines.extend([
            "",
            "SUMMARY",
            "-" * 60,
            f"Total checks: {len(self.results)}",
            f"Passed: {passed_count}",
            f"Failed: {failed_count}",
            f"Overall status: {overall_status}",
            "",
        ])

        report = "\n".join(lines)

        self.report_path.parent.mkdir(parents=True, exist_ok=True)
        self.report_path.write_text(report, encoding="utf-8")

        print(report)
        print(f"\nValidation report saved to: {self.report_path}")

        return report

    def validate_output(self, result):
        failed_checks = [
            check
            for check in self.results
            if not check["passed"]
        ]

        if failed_checks:
            failure_summary = "\n".join(
                f"- {check['name']}: {check['details']}"
                for check in failed_checks
            )

            raise ValueError(
                f"Data validation failed with "
                f"{len(failed_checks)} failed check(s).\n"
                f"See report: {self.report_path}\n"
                f"{failure_summary}"
            )


if __name__ == "__main__":
    validator = DataValidator()
    validator.run()
