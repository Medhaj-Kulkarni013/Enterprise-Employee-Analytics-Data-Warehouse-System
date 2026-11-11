
from pathlib import Path
import logging

import numpy as np
import pandas as pd
from faker import Faker

from pipeline.base_step import PipelineStep


class Synthesizer(PipelineStep):
    """
    Generates 100,000 synthetic employee records from the
    cleaned IBM HR dataset.

    Generation strategy:
    1. Whole-row resampling with replacement.
    2. Controlled noise on selected attributes.
    3. Faker-based employee identity generation.
    4. Date derivation.
    5. Same-department manager assignment.
    6. Validation and CSV export.
    """

    SNAPSHOT_DATE = pd.Timestamp("2025-12-31")

    YEAR_COLUMNS = [
        "TotalWorkingYears",
        "YearsAtCompany",
        "YearsInCurrentRole",
        "YearsSinceLastPromotion",
        "YearsWithCurrManager",
    ]

    NOISE_COLUMNS = [
        "JobSatisfaction",
        "EnvironmentSatisfaction",
        "RelationshipSatisfaction",
        "WorkLifeBalance",
        "JobInvolvement",
        "TrainingTimesLastYear",
    ]

    OUTPUT_COLUMNS = [
        "employee_id",
        "employee_code",
        "source_employee_number",
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
        "prior_experience_years",
        "stock_option_level",
        "business_travel",
        "overtime_flag",
        "hire_date",
        "department",
        "job_role",
        "job_level",
        "monthly_income",
        "manager_id",
        "is_active",
        "termination_date",
        "performance_rating",
        "percent_salary_hike",
        "training_times_last_year",
        "job_satisfaction",
        "environment_satisfaction",
        "relationship_satisfaction",
        "work_life_balance",
        "job_involvement",
    ]

    REQUIRED_COLUMNS = {
        "source_employee_number",
        "Age",
        "Attrition",
        "BusinessTravel",
        "Department",
        "DistanceFromHome",
        "Education",
        "EducationField",
        "EnvironmentSatisfaction",
        "Gender",
        "JobInvolvement",
        "JobLevel",
        "JobRole",
        "JobSatisfaction",
        "MaritalStatus",
        "MonthlyIncome",
        "NumCompaniesWorked",
        "OverTime",
        "PercentSalaryHike",
        "PerformanceRating",
        "RelationshipSatisfaction",
        "StockOptionLevel",
        "TotalWorkingYears",
        "TrainingTimesLastYear",
        "WorkLifeBalance",
        "YearsAtCompany",
        "YearsInCurrentRole",
        "YearsSinceLastPromotion",
        "YearsWithCurrManager",
    }

    def __init__(
        self,
        input_path="data/processed/employees_clean_base.csv",
        output_path="data/synthetic/employees_100k.csv",
        sample_path="data/synthetic/employees_sample_500.csv",
        n_records=100_000,
        seed=42,
    ):
        super().__init__("Employee Data Synthesis")

        self.input_path = Path(input_path)
        self.output_path = Path(output_path)
        self.sample_path = Path(sample_path)

        self.n_records = n_records
        self.seed = seed

        self.rng = np.random.default_rng(seed)

        self.fake = Faker("en_IN")
        self.fake.seed_instance(seed)

        self.base_data = None
        self.income_bands = None

    def validate_input(self):
        """Validate the cleaned base dataset before synthesis."""

        if not self.input_path.exists():
            raise FileNotFoundError(
                f"Cleaned base dataset not found: {self.input_path}"
            )

        if self.n_records <= 0:
            raise ValueError("Number of synthetic records must be positive.")

        df = pd.read_csv(self.input_path)

        missing_columns = self.REQUIRED_COLUMNS - set(df.columns)

        if missing_columns:
            raise ValueError(
                f"Cleaned dataset is missing columns: "
                f"{sorted(missing_columns)}"
            )

        if df.empty:
            raise ValueError("Cleaned base dataset is empty.")

        if df.isnull().sum().sum() > 0:
            raise ValueError(
                "Cleaned base dataset contains missing values."
            )

        if df["source_employee_number"].duplicated().any():
            raise ValueError(
                "Source employee numbers should be unique in the base data."
            )

        self.base_data = df

        self.income_bands = (
            df.groupby("JobLevel")["MonthlyIncome"]
            .agg(["min", "max"])
            .to_dict("index")
        )

        self.logger.info(
            "Loaded %s cleaned employee records.",
            len(df),
        )

    def execute(self):
        """Generate and export the synthetic employee dataset."""

        base = self.base_data

        self.logger.info(
            "Starting synthesis of %s employee records.",
            self.n_records,
        )

        # Step 1: Whole-row resampling with replacement.
        synthetic = base.sample(
            n=self.n_records,
            replace=True,
            random_state=self.seed,
        ).reset_index(drop=True)

        # Step 2: Introduce controlled noise.
        self._apply_year_noise(synthetic)
        self._apply_age_noise(synthetic)
        self._apply_income_noise(synthetic)
        self._apply_satisfaction_noise(synthetic)

        # Step 3: Generate employee identities.
        identities = self._generate_identities()

        synthetic["employee_id"] = identities["employee_id"]
        synthetic["employee_code"] = identities["employee_code"]
        synthetic["first_name"] = identities["first_name"]
        synthetic["last_name"] = identities["last_name"]
        synthetic["email"] = identities["email"]

        # Step 4: Derive employee dates.
        synthetic["date_of_birth"] = self._derive_date_of_birth(
            synthetic["Age"]
        )

        synthetic["hire_date"] = self._derive_hire_date(
            synthetic["YearsAtCompany"],
            synthetic["Attrition"],
            synthetic["date_of_birth"],
        )

        # Step 5: Convert Attrition into active status.
        synthetic["is_active"] = (
            1 - synthetic["Attrition"].astype(int)
        )

        synthetic["termination_date"] = self._derive_termination_date(
            synthetic
        )

        # Step 6: Assign managers.
        synthetic["manager_id"] = self._assign_managers(synthetic)

        # Step 7: Calculate prior work experience.
        synthetic["prior_experience_years"] = (
            synthetic["TotalWorkingYears"]
            - synthetic["YearsAtCompany"]
        )

        # Step 8: Rename source columns to the final schema.
        synthetic = synthetic.rename(
            columns={
                "Gender": "gender",
                "MaritalStatus": "marital_status",
                "Education": "education_level",
                "EducationField": "education_field",
                "DistanceFromHome": "distance_from_home_km",
                "NumCompaniesWorked": "num_companies_worked",
                "StockOptionLevel": "stock_option_level",
                "BusinessTravel": "business_travel",
                "OverTime": "overtime_flag",
                "Department": "department",
                "JobRole": "job_role",
                "JobLevel": "job_level",
                "MonthlyIncome": "monthly_income",
                "PerformanceRating": "performance_rating",
                "PercentSalaryHike": "percent_salary_hike",
                "TrainingTimesLastYear": "training_times_last_year",
                "JobSatisfaction": "job_satisfaction",
                "EnvironmentSatisfaction": "environment_satisfaction",
                "RelationshipSatisfaction": "relationship_satisfaction",
                "WorkLifeBalance": "work_life_balance",
                "JobInvolvement": "job_involvement",
            }
        )

        # Step 9: Keep only the required 33 columns in exact order.
        final_df = synthetic[self.OUTPUT_COLUMNS].copy()

        # Step 10: Format dates as ISO YYYY-MM-DD strings.
        date_columns = [
            "date_of_birth",
            "hire_date",
            "termination_date",
        ]

        for column in date_columns:
            final_df[column] = pd.to_datetime(
                final_df[column]
            ).dt.strftime("%Y-%m-%d")

        # Step 11: Validate the final dataset.
        self._validate_synthetic_data(final_df)

        # Step 12: Export the full dataset.
        self.output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        final_df.to_csv(self.output_path, index=False)

        # Step 13: Export a reproducible 500-row sample.
        self.sample_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        final_df.sample(
            n=min(500, len(final_df)),
            random_state=self.seed,
        ).to_csv(self.sample_path, index=False)

        self.logger.info(
            "Synthetic employee dataset saved: %s",
            self.output_path,
        )

        self.logger.info(
            "Sample dataset saved: %s",
            self.sample_path,
        )

        return final_df

    def validate_output(self, result):
        """Validate the DataFrame returned by execute()."""

        if not isinstance(result, pd.DataFrame):
            raise TypeError("Synthesizer output must be a DataFrame.")

        if len(result) != self.n_records:
            raise ValueError(
                f"Expected {self.n_records} rows, found {len(result)}."
            )

        if result.columns.tolist() != self.OUTPUT_COLUMNS:
            raise ValueError("Final output columns do not match the schema.")

        if result["employee_id"].nunique() != self.n_records:
            raise ValueError("Employee IDs are not unique.")

        if result["employee_code"].nunique() != self.n_records:
            raise ValueError("Employee codes are not unique.")

        if result["email"].nunique() != self.n_records:
            raise ValueError("Employee emails are not unique.")

        if not self.output_path.exists():
            raise FileNotFoundError("Full synthetic CSV was not exported.")

        if not self.sample_path.exists():
            raise FileNotFoundError("500-row sample CSV was not exported.")

    def _apply_year_noise(self, df):
        """Apply integer noise of -1, 0 or +1 to experience columns."""

        for column in self.YEAR_COLUMNS:
            noise = self.rng.integers(
                low=-1,
                high=2,
                size=len(df),
            )

            df[column] = (
                df[column].to_numpy() + noise
            ).clip(min=0)

        # Enforce experience and tenure relationships.
        df["TotalWorkingYears"] = np.maximum(
            df["TotalWorkingYears"],
            df["YearsAtCompany"],
        )

        for column in [
            "YearsInCurrentRole",
            "YearsSinceLastPromotion",
            "YearsWithCurrManager",
        ]:
            df[column] = np.minimum(
                df[column],
                df["YearsAtCompany"],
            )

    def _apply_age_noise(self, df):
        """Apply age noise and enforce the minimum working age."""

        noise = self.rng.integers(
            low=-2,
            high=3,
            size=len(df),
        )

        df["Age"] = (
            df["Age"].to_numpy() + noise
        ).clip(min=18, max=60)

        # An employee must have been at least 18 when
        # their total working experience began.
        minimum_age = 18 + df["TotalWorkingYears"]

        df["Age"] = np.maximum(
            df["Age"],
            minimum_age,
        )

    def _apply_income_noise(self, df):
        """Apply lognormal salary noise and clip to source salary bands."""

        noise = self.rng.lognormal(
            mean=0,
            sigma=0.08,
            size=len(df),
        )

        df["MonthlyIncome"] = (
            df["MonthlyIncome"].to_numpy() * noise
        )

        for job_level, band in self.income_bands.items():

            mask = df["JobLevel"] == job_level

            df.loc[mask, "MonthlyIncome"] = df.loc[
                mask, "MonthlyIncome"
            ].clip(
                lower=band["min"],
                upper=band["max"],
            )

        df["MonthlyIncome"] = df["MonthlyIncome"].round().astype(int)

    def _apply_satisfaction_noise(self, df):
        """Redraw 10% of rows from original empirical distributions."""

        for column in self.NOISE_COLUMNS:

            mask = self.rng.random(len(df)) < 0.10

            original_values = self.base_data[column].to_numpy()

            df.loc[mask, column] = self.rng.choice(
                original_values,
                size=int(mask.sum()),
                replace=True,
            )

    def _generate_identities(self):
        """Generate unique IDs, codes, names and deterministic emails."""

        employee_ids = np.arange(1, self.n_records + 1)

        employee_codes = [
            f"E{employee_id:06d}"
            for employee_id in employee_ids
        ]

        first_names = [
            self.fake.first_name()
            for _ in range(self.n_records)
        ]

        last_names = [
            self.fake.last_name()
            for _ in range(self.n_records)
        ]

        emails = [
            f"{code.lower()}@example.com"
            for code in employee_codes
        ]

        return {
            "employee_id": employee_ids,
            "employee_code": employee_codes,
            "first_name": first_names,
            "last_name": last_names,
            "email": emails,
        }

    def _derive_date_of_birth(self, ages):
        """
        Generate varied dates of birth while preserving the
        employee's exact age as of the snapshot date.

        For employees aged 18, ensure their 18th birthday
        occurs no later than the day before the snapshot date.
        This allows zero-tenure attrited employees to have
        a valid hire date.
        """

        ages = ages.astype(int).to_numpy()

        birth_years = self.SNAPSHOT_DATE.year - ages

        anniversary_dates = pd.to_datetime({
            "year": birth_years,
            "month": np.full(len(ages), self.SNAPSHOT_DATE.month),
            "day": np.full(len(ages), self.SNAPSHOT_DATE.day),
        })

        random_days = self.rng.integers(
            low=0,
            high=365,
            size=len(ages),
        )

        birth_dates = (
            anniversary_dates
            - pd.to_timedelta(random_days, unit="D")
        )

        birth_dates = pd.Series(pd.to_datetime(birth_dates))

        # Ensure employees aged 18 have already turned 18
        # at least one day before the snapshot date.
        age_18_mask = ages == 18

        latest_birth_date = (
            self.SNAPSHOT_DATE
            - pd.DateOffset(years=18)
            - pd.Timedelta(days=1)
        )

        birth_dates.loc[age_18_mask] = (
            birth_dates.loc[age_18_mask]
            .clip(upper=latest_birth_date)
        )

        return pd.to_datetime(birth_dates)

    def _derive_hire_date(
        self,
        years_at_company,
        attrition,
        date_of_birth,
    ):
        """
        Generate varied hire dates while preserving completed
        years of company tenure as of the snapshot date.

        Additional constraints:
        - Hire date cannot be before the employee's 18th birthday.
        - Hire date cannot be after the snapshot date.
        - Attrited employees must have at least one day between
          hire date and the snapshot date.
        """

        tenure = years_at_company.astype(int).to_numpy()

        hire_years = self.SNAPSHOT_DATE.year - tenure

        anniversary_dates = pd.to_datetime({
            "year": hire_years,
            "month": np.full(len(tenure), self.SNAPSHOT_DATE.month),
            "day": np.full(len(tenure), self.SNAPSHOT_DATE.day),
        })

        random_days = self.rng.integers(
            low=0,
            high=365,
            size=len(tenure),
        )

        hire_dates = (
            anniversary_dates
            - pd.to_timedelta(random_days, unit="D")
        )

        birth_dates = pd.to_datetime(date_of_birth)

        eighteenth_birthday = (
            birth_dates + pd.DateOffset(years=18)
        )

        hire_dates = pd.Series(
            pd.to_datetime(hire_dates),
            index=years_at_company.index,
        )

        hire_dates = pd.Series(
            np.maximum(
                hire_dates.to_numpy(),
                eighteenth_birthday.to_numpy(),
            ),
            index=years_at_company.index,
        )

        attrited = attrition.astype(int) == 1

        latest_valid_hire_date = (
            self.SNAPSHOT_DATE - pd.Timedelta(days=1)
        )

        zero_tenure_attrited = (
            attrited & (years_at_company == 0)
        )

        hire_dates.loc[zero_tenure_attrited] = np.minimum(
            hire_dates.loc[zero_tenure_attrited],
            latest_valid_hire_date,
        )

        return pd.to_datetime(hire_dates)

    def _derive_termination_date(self, df):
        """
        Generate termination dates for attrited employees.

        Termination occurs between 20% and 100% of the period
        between the actual hire date and the snapshot date.

        Active employees receive a NULL termination date.
        """

        hire_dates = pd.to_datetime(df["hire_date"])

        duration_days = (
            self.SNAPSHOT_DATE - hire_dates
        ).dt.days.to_numpy()

        if (duration_days < 0).any():
            raise ValueError(
                "Hire date cannot be after the snapshot date."
            )

        attrited = df["Attrition"].astype(int).to_numpy() == 1

        if (duration_days[attrited] < 1).any():
            raise ValueError(
                "Attrited employees must have a valid period "
                "between hire date and snapshot date."
            )

        random_fraction = self.rng.uniform(
            low=0.20,
            high=1.00,
            size=len(df),
        )

        termination_offset = np.ceil(
            duration_days * random_fraction
        ).astype(int)

        termination_dates = (
            hire_dates
            + pd.to_timedelta(termination_offset, unit="D")
        )

        termination_dates = pd.Series(
            termination_dates,
            index=df.index,
        )

        # Active employees must have no termination date.
        termination_dates = termination_dates.where(
            df["Attrition"].astype(int) == 1,
            pd.NaT,
        )

        return termination_dates

    def _assign_managers(self, df):
        """
        Assign managers from the same department with a
        strictly higher JobLevel.

        JobLevel 5 employees do not have managers.
        """

        manager_ids = np.full(
            len(df),
            np.nan,
        )

        employee_ids = np.arange(
            1,
            len(df) + 1,
        )

        for department in df["Department"].unique():

            department_mask = (
                df["Department"].to_numpy() == department
            )

            department_indices = np.flatnonzero(
                department_mask
            )

            department_levels = df.iloc[
                department_indices
            ]["JobLevel"].to_numpy()

            for job_level in np.sort(
                np.unique(department_levels)
            ):

                if job_level == 5:
                    continue

                employee_indices = department_indices[
                    department_levels == job_level
                ]

                candidate_indices = department_indices[
                    department_levels > job_level
                ]

                if len(candidate_indices) == 0:
                    raise ValueError(
                        f"No higher-level manager available in "
                        f"department '{department}' for JobLevel "
                        f"{job_level} employees."
                    )

                selected_managers = self.rng.choice(
                    candidate_indices,
                    size=len(employee_indices),
                    replace=True,
                )

                manager_ids[employee_indices] = (
                    employee_ids[selected_managers]
                )

        return pd.array(
            manager_ids,
            dtype="Int64",
        )

    def _validate_synthetic_data(self, df):
        """Perform business-rule validation before exporting."""

        if len(df) != self.n_records:
            raise ValueError("Incorrect number of synthetic employees.")

        if df.columns.tolist() != self.OUTPUT_COLUMNS:
            raise ValueError("Incorrect output column order.")

        if df.isnull().sum().sum() > 0:
            # manager_id and termination_date are allowed to be null.
            allowed_null_columns = {
                "manager_id",
                "termination_date",
            }

            unexpected_nulls = [
                column
                for column in df.columns
                if column not in allowed_null_columns
                and df[column].isnull().any()
            ]

            if unexpected_nulls:
                raise ValueError(
                    f"Unexpected null values: {unexpected_nulls}"
                )

        # Unique employee identifiers.
        for column in [
            "employee_id",
            "employee_code",
            "email",
        ]:
            if df[column].duplicated().any():
                raise ValueError(
                    f"Duplicate values found in {column}."
                )

        # Parse dates for validation.
        hire_dates = pd.to_datetime(df["hire_date"])
        birth_dates = pd.to_datetime(df["date_of_birth"])

        termination_dates = pd.to_datetime(
            df["termination_date"],
            errors="coerce",
        )

        # No future hire dates.
        if (hire_dates > self.SNAPSHOT_DATE).any():
            raise ValueError("Hire date is after the snapshot date.")

        # No employee hired before age 18.
        if (
            (hire_dates - birth_dates).dt.days < 18 * 365
        ).any():
            raise ValueError("An employee was hired before age 18.")

        # Termination must not occur before hire.
        terminated = termination_dates.notna()

        if (
            termination_dates[terminated]
            < hire_dates[terminated]
        ).any():
            raise ValueError("Termination date occurs before hire date.")

        # Attrition and termination-date relationship.
        active = df["is_active"] == 1

        if termination_dates[active].notna().any():
            raise ValueError(
                "Active employees must have null termination dates."
            )

        if termination_dates[~active].isna().any():
            raise ValueError(
                "Attrited employees must have termination dates."
            )

        # Salary must remain within the original JobLevel bands.
        for job_level, band in self.income_bands.items():

            mask = df["job_level"] == job_level

            if (
                (df.loc[mask, "monthly_income"] < band["min"])
                | (df.loc[mask, "monthly_income"] > band["max"])
            ).any():
                raise ValueError(
                    f"Salary outside income band for JobLevel {job_level}."
                )

        # Manager must exist, belong to the same department,
        # and have a strictly higher job level.
        manager_rows = df[df["manager_id"].notna()].copy()

        manager_lookup = df.set_index("employee_id")

        manager_data = manager_lookup.loc[
            manager_rows["manager_id"].astype(int)
        ]

        if (
            manager_rows["department"].to_numpy()
            != manager_data["department"].to_numpy()
        ).any():
            raise ValueError(
                "A manager belongs to a different department."
            )

        if (
            manager_data["job_level"].to_numpy()
            <= manager_rows["job_level"].to_numpy()
        ).any():
            raise ValueError(
                "A manager does not have a strictly higher job level."
            )

        # Only JobLevel 5 employees may have no manager.
        without_manager = df[df["manager_id"].isna()]

        if not (
            without_manager["job_level"] == 5
        ).all():
            raise ValueError(
                "An employee below JobLevel 5 has no manager."
            )

        self.logger.info("All synthetic data validations passed.")
