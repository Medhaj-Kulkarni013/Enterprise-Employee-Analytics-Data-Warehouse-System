
from pathlib import Path
import logging

import pandas as pd

from pipeline.base_step import PipelineStep


class Preprocessor(PipelineStep):
    """
    Cleans and transforms the original IBM HR Employee Attrition dataset.

    Responsibilities:
    - Load the original dataset.
    - Handle missing values and duplicate rows.
    - Drop unnecessary columns.
    - Convert binary attributes into integer flags.
    - Preserve source employee numbers for lineage.
    - Validate data consistency.
    - Export the cleaned base dataset.
    """

    DROP_COLUMNS = [
        "EmployeeCount",
        "Over18",
        "StandardHours",
        "DailyRate",
        "HourlyRate",
        "MonthlyRate",
    ]

    REQUIRED_COLUMNS = {
        "EmployeeNumber",
        "Age",
        "Attrition",
        "OverTime",
        "YearsAtCompany",
        "TotalWorkingYears",
        "YearsInCurrentRole",
        "YearsSinceLastPromotion",
        "YearsWithCurrManager",
        "JobLevel",
        "MonthlyIncome",
        "Department",
        "JobRole",
        "EducationField",
    }

    CATEGORY_DOMAINS = {
        "Gender": {"Male", "Female"},
        "Attrition": {"Yes", "No"},
        "OverTime": {"Yes", "No"},
        "MaritalStatus": {"Single", "Married", "Divorced"},
        "BusinessTravel": {
            "Non-Travel",
            "Travel_Rarely",
            "Travel_Frequently",
        },
        "Department": {
            "Human Resources",
            "Research & Development",
            "Sales",
        },
        "EducationField": {
            "Life Sciences",
            "Medical",
            "Marketing",
            "Technical Degree",
            "Other",
            "Human Resources",
        },
        "JobRole": {
            "Sales Executive",
            "Research Scientist",
            "Laboratory Technician",
            "Manufacturing Director",
            "Healthcare Representative",
            "Manager",
            "Sales Representative",
            "Research Director",
            "Human Resources",
        },
    }

    def __init__(
        self,
        input_path="data/raw/ibm_hr_dataset.csv",
        output_path="data/processed/employees_clean_base.csv",
    ):
        super().__init__("IBM HR Data Preprocessing")

        self.input_path = Path(input_path)
        self.output_path = Path(output_path)

        self.original_shape = None
        self.rows_removed_for_missing_data = 0
        self.duplicates_removed = 0
        self.numeric_values_imputed = 0
        self.categorical_values_imputed = 0

    def validate_input(self):
        """Check that the input file exists and has the required schema."""

        if not self.input_path.exists():
            raise FileNotFoundError(
                f"Input dataset not found: {self.input_path}"
            )

        columns = pd.read_csv(self.input_path, nrows=0).columns.tolist()

        missing_columns = self.REQUIRED_COLUMNS - set(columns)

        if missing_columns:
            raise ValueError(
                f"Input dataset is missing required columns: "
                f"{sorted(missing_columns)}"
            )

        if len(columns) != 35:
            raise ValueError(
                f"Expected 35 source columns, found {len(columns)}."
            )

    def execute(self):
        """Clean, transform and save the IBM HR dataset."""

        self.logger.info("Loading source dataset: %s", self.input_path)

        df = pd.read_csv(self.input_path)

        self.original_shape = df.shape

        self.logger.info(
            "Original dataset shape: %s rows x %s columns",
            df.shape[0],
            df.shape[1],
        )

        # 1. Remove rows with more than 30% missing values.
        missing_ratio = df.isnull().mean(axis=1)

        rows_to_drop = missing_ratio > 0.30

        self.rows_removed_for_missing_data = int(rows_to_drop.sum())

        df = df.loc[~rows_to_drop].copy()

        # 2. Remove duplicate rows.
        duplicate_mask = df.duplicated()

        self.duplicates_removed = int(duplicate_mask.sum())

        df = df.drop_duplicates().copy()

        # 3. Impute remaining missing values.
        for column in df.columns:

            missing_count = int(df[column].isnull().sum())

            if missing_count == 0:
                continue

            if pd.api.types.is_numeric_dtype(df[column]):
                median_value = df[column].median()

                if pd.isna(median_value):
                    raise ValueError(
                        f"Cannot impute numeric column '{column}': "
                        "it contains no valid values."
                    )

                df[column] = df[column].fillna(median_value)

                self.numeric_values_imputed += missing_count

            else:
                mode_values = df[column].mode(dropna=True)

                if mode_values.empty:
                    raise ValueError(
                        f"Cannot impute categorical column '{column}': "
                        "it contains no valid values."
                    )

                df[column] = df[column].fillna(mode_values.iloc[0])

                self.categorical_values_imputed += missing_count

        # 4. Strip whitespace from text columns.
        text_columns = df.select_dtypes(
            include=["object", "string"]
        ).columns

        for column in text_columns:
            df[column] = df[column].astype("string").str.strip()

        # 5. Validate known categorical domains.
        self._validate_category_domains(df)

        # 6. Drop the six unnecessary columns.
        df = df.drop(columns=self.DROP_COLUMNS)

        # 7. Convert Yes/No attributes into binary flags.
        df["Attrition"] = df["Attrition"].map({
            "Yes": 1,
            "No": 0,
        }).astype("int8")

        df["OverTime"] = df["OverTime"].map({
            "Yes": 1,
            "No": 0,
        }).astype("int8")

        # 8. Preserve EmployeeNumber only as source lineage.
        df = df.rename(
            columns={
                "EmployeeNumber": "source_employee_number"
            }
        )

        # 9. Validate data consistency.
        self._validate_consistency(df)

        # 10. Export cleaned base dataset.
        self.output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        df.to_csv(self.output_path, index=False)

        self.logger.info(
            "Cleaned base dataset saved to: %s",
            self.output_path,
        )

        return df

    def validate_output(self, result):
        """Validate the cleaned DataFrame produced by execute()."""

        if not isinstance(result, pd.DataFrame):
            raise TypeError("Preprocessor output must be a DataFrame.")

        if result.empty:
            raise ValueError("Cleaned dataset is empty.")

        if result.isnull().sum().sum() != 0:
            raise ValueError(
                "Missing values remain after preprocessing."
            )

        if result.duplicated().any():
            raise ValueError(
                "Duplicate rows remain after preprocessing."
            )

        if "EmployeeNumber" in result.columns:
            raise ValueError(
                "EmployeeNumber should have been renamed."
            )

        if not self.output_path.exists():
            raise FileNotFoundError(
                "Cleaned dataset was not exported successfully."
            )

    def _validate_category_domains(self, df):
        """
        Ensure categorical values match the IBM dataset's
        expected domains.
        """

        for column, expected_values in self.CATEGORY_DOMAINS.items():

            actual_values = set(df[column].dropna().unique())

            if actual_values != expected_values:
                raise ValueError(
                    f"Unexpected values in '{column}'. "
                    f"Expected: {sorted(expected_values)}; "
                    f"Found: {sorted(actual_values)}"
                )

    def _validate_consistency(self, df):
        """Check the original employee data's business rules."""

        # YearsAtCompany cannot exceed TotalWorkingYears.
        if (
            df["YearsAtCompany"] > df["TotalWorkingYears"]
        ).any():
            raise ValueError(
                "YearsAtCompany exceeds TotalWorkingYears."
            )

        # YearsInCurrentRole cannot exceed YearsAtCompany.
        if (
            df["YearsInCurrentRole"] > df["YearsAtCompany"]
        ).any():
            raise ValueError(
                "YearsInCurrentRole exceeds YearsAtCompany."
            )

        # Age must be at least 18 + TotalWorkingYears.
        if (
            df["Age"] < 18 + df["TotalWorkingYears"]
        ).any():
            raise ValueError(
                "Age and TotalWorkingYears are inconsistent."
            )

        # Monthly income must be positive.
        if (df["MonthlyIncome"] <= 0).any():
            raise ValueError(
                "MonthlyIncome must be greater than zero."
            )

        # Every job level must have a valid income range.
        income_bands = df.groupby("JobLevel")["MonthlyIncome"].agg(
            ["min", "max"]
        )

        if income_bands.isnull().any().any():
            raise ValueError(
                "Unable to calculate income bands by JobLevel."
            )

        self.logger.info(
            "Income bands by JobLevel:\n%s",
            income_bands.to_string(),
        )

        self.logger.info("Base data consistency checks passed.")

    def get_cleaning_summary(self):
        """Return counts of rows and values affected by cleaning."""

        return {
            "original_shape": self.original_shape,
            "rows_removed_for_missing_data":
                self.rows_removed_for_missing_data,
            "duplicates_removed": self.duplicates_removed,
            "numeric_values_imputed": self.numeric_values_imputed,
            "categorical_values_imputed":
                self.categorical_values_imputed,
        }