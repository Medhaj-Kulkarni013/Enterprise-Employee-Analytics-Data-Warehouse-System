"""Generate employee history events for SCD Type 2 loading."""

from pathlib import Path

import pandas as pd

from pipeline.base_step import PipelineStep


class HistoryGenerator(PipelineStep):
    """Create initial and change events from the synthetic employee snapshot."""

    REQUIRED_COLUMNS = {
        "employee_id", "hire_date", "department", "job_role",
        "job_level", "monthly_income",
    }

    def __init__(
        self,
        input_path="data/synthetic/employees_100k.csv",
        output_path="data/synthetic/employee_history.csv",
        fraction=0.10,
        seed=42,
    ):
        super().__init__("Employee SCD Type 2 History Generation")
        self.input_path = Path(input_path)
        self.output_path = Path(output_path)
        self.fraction = fraction
        self.seed = seed

    def validate_input(self):
        if not self.input_path.is_file():
            raise FileNotFoundError(f"Synthetic dataset not found: {self.input_path}")
        if not 0 < self.fraction <= 1:
            raise ValueError("History fraction must be between 0 and 1.")
        columns = pd.read_csv(self.input_path, nrows=0).columns
        missing = self.REQUIRED_COLUMNS - set(columns)
        if missing:
            raise ValueError(f"Synthetic dataset is missing columns: {sorted(missing)}")

    def execute(self):
        employees = pd.read_csv(self.input_path)
        selected = employees.sample(frac=self.fraction, random_state=self.seed).copy()
        selected["hire_date"] = pd.to_datetime(selected["hire_date"])
        selected["effective_date"] = selected["hire_date"] + pd.DateOffset(years=2)
        selected = selected[selected["effective_date"] <= pd.Timestamp("2025-12-31")]
        selected["old_job_level"] = (selected["job_level"] - 1).clip(lower=1)
        selected["old_monthly_income"] = (
            selected["monthly_income"] * 0.90
        ).round(2)
        selected["change_type"] = selected.apply(
            lambda row: "Promotion" if row["job_level"] > 1 else "SalaryHike",
            axis=1,
        )

        initial = selected.assign(
            effective_date=selected["hire_date"],
            change_type="Hire",
            job_level=selected["old_job_level"],
            monthly_income=selected["old_monthly_income"],
        )
        changes = selected[
            ["employee_id", "effective_date", "change_type", "department",
             "job_role", "job_level", "monthly_income"]
        ]
        initial = initial[
            ["employee_id", "effective_date", "change_type", "department",
             "job_role", "job_level", "monthly_income"]
        ]
        history = pd.concat([initial, changes], ignore_index=True)
        history["effective_date"] = pd.to_datetime(
            history["effective_date"]
        ).dt.strftime("%Y-%m-%d")
        history = history.sort_values(["employee_id", "effective_date"])
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        history.to_csv(self.output_path, index=False)
        return history

    def validate_output(self, result):
        if not isinstance(result, pd.DataFrame):
            raise TypeError("History output must be a DataFrame.")
        if result.empty:
            raise ValueError("No valid historical events were generated.")
        if result.duplicated(["employee_id", "effective_date"]).any():
            raise ValueError("History contains duplicate employee effective dates.")
