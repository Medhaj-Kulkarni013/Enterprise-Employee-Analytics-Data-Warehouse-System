
import json
import logging
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_DATE = pd.Timestamp("2025-12-31")


class DocumentationGenerator:
    """
    Generate documentation artifacts for the employee
    preprocessing and synthesis pipeline.

    Outputs:
        docs/mappings.json
        docs/data_profile.md
    """

    def __init__(
        self,
        raw_path=None,
        synthetic_path=None,
        mappings_path=None,
        profile_path=None,
    ):
        self.raw_path = Path(
            raw_path or PROJECT_ROOT / "data/raw/ibm_hr_dataset.csv"
        )

        self.synthetic_path = Path(
            synthetic_path
            or PROJECT_ROOT / "data/synthetic/employees_100k.csv"
        )

        self.mappings_path = Path(
            mappings_path or PROJECT_ROOT / "docs/mappings.json"
        )

        self.profile_path = Path(
            profile_path or PROJECT_ROOT / "docs/data_profile.md"
        )

        self.logger = logging.getLogger(self.__class__.__name__)

        self.mappings = self._get_mappings()

    @staticmethod
    def _get_mappings():
        """
        Return code-to-label mappings for ordinal attributes.
        """

        return {
            "education_level": {
                "1": "Below College",
                "2": "College",
                "3": "Bachelor",
                "4": "Master",
                "5": "Doctor",
            },
            "performance_rating": {
                "1": "Low",
                "2": "Good",
                "3": "Excellent",
                "4": "Outstanding",
            },
            "job_satisfaction": {
                "1": "Low",
                "2": "Medium",
                "3": "High",
                "4": "Very High",
            },
            "environment_satisfaction": {
                "1": "Low",
                "2": "Medium",
                "3": "High",
                "4": "Very High",
            },
            "relationship_satisfaction": {
                "1": "Low",
                "2": "Medium",
                "3": "High",
                "4": "Very High",
            },
            "job_involvement": {
                "1": "Low",
                "2": "Medium",
                "3": "High",
                "4": "Very High",
            },
            "work_life_balance": {
                "1": "Bad",
                "2": "Good",
                "3": "Better",
                "4": "Best",
            },
            "job_level": {
                "1": "Level 1",
                "2": "Level 2",
                "3": "Level 3",
                "4": "Level 4",
                "5": "Level 5",
            },
            "stock_option_level": {
                "0": "No Stock Options",
                "1": "Level 1",
                "2": "Level 2",
                "3": "Level 3",
            },
        }

    def generate_mappings(self):
        """
        Generate the ordinal code-to-label JSON file.
        """

        self.mappings_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with open(
            self.mappings_path,
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                self.mappings,
                file,
                indent=4,
                ensure_ascii=False,
            )

        self.logger.info(
            "Mappings generated: %s",
            self.mappings_path,
        )

    @staticmethod
    def _calculate_age(date_of_birth):
        """
        Calculate completed age as of the snapshot date.
        """

        dates = pd.to_datetime(date_of_birth)

        age = (
            SNAPSHOT_DATE.year - dates.dt.year
            - (
                (SNAPSHOT_DATE.month < dates.dt.month)
                | (
                    (SNAPSHOT_DATE.month == dates.dt.month)
                    & (SNAPSHOT_DATE.day < dates.dt.day)
                )
            ).astype(int)
        )

        return age

    @staticmethod
    def _calculate_tenure(hire_date):
        """
        Calculate completed years of company tenure
        as of the snapshot date.
        """

        dates = pd.to_datetime(hire_date)

        tenure = (
            SNAPSHOT_DATE.year - dates.dt.year
            - (
                (SNAPSHOT_DATE.month < dates.dt.month)
                | (
                    (SNAPSHOT_DATE.month == dates.dt.month)
                    & (SNAPSHOT_DATE.day < dates.dt.day)
                )
            ).astype(int)
        )

        return tenure

    @staticmethod
    def _numeric_summary(series):
        """
        Calculate descriptive statistics for a numeric series.
        """

        series = pd.to_numeric(series, errors="coerce").dropna()

        return {
            "count": len(series),
            "mean": series.mean(),
            "median": series.median(),
            "std": series.std(),
            "min": series.min(),
            "max": series.max(),
        }

    @staticmethod
    def _format_summary(summary):
        """
        Format descriptive statistics as Markdown rows.
        """

        return [
            f"| Count | {summary['count']:,} |",
            f"| Mean | {summary['mean']:.2f} |",
            f"| Median | {summary['median']:.2f} |",
            f"| Standard deviation | {summary['std']:.2f} |",
            f"| Minimum | {summary['min']:.2f} |",
            f"| Maximum | {summary['max']:.2f} |",
        ]

    def _build_profile(self, raw, synthetic):
        """
        Build the complete before-and-after data profile.
        """

        raw_age = raw["Age"]
        synthetic_age = self._calculate_age(
            synthetic["date_of_birth"]
        )

        raw_income = raw["MonthlyIncome"]
        synthetic_income = synthetic["monthly_income"]

        raw_tenure = raw["YearsAtCompany"]
        synthetic_tenure = self._calculate_tenure(
            synthetic["hire_date"]
        )

        sections = []

        sections.append("# Employee Analytics - Data Profile\n")

        sections.append("## 1. Overview\n")
        sections.append(
            f"- **Original IBM HR dataset:** "
            f"{len(raw):,} rows × {len(raw.columns)} columns"
        )
        sections.append(
            f"- **Synthetic employee dataset:** "
            f"{len(synthetic):,} rows × {len(synthetic.columns)} columns"
        )
        sections.append(
            f"- **Snapshot date:** {SNAPSHOT_DATE.date()}"
        )
        sections.append(
            "- **Synthesis random seed:** 42\n"
        )

        numeric_metrics = [
            (
                "Age",
                raw_age,
                synthetic_age,
            ),
            (
                "Monthly Income",
                raw_income,
                synthetic_income,
            ),
            (
                "Years at Company (Tenure)",
                raw_tenure,
                synthetic_tenure,
            ),
        ]

        for title, original, generated in numeric_metrics:
            original_summary = self._numeric_summary(original)
            generated_summary = self._numeric_summary(generated)

            sections.append(f"## {title}\n")

            sections.append(
                "| Statistic | Original | Synthetic |"
            )
            sections.append(
                "|---|---:|---:|"
            )

            statistics = [
                ("Count", "count"),
                ("Mean", "mean"),
                ("Median", "median"),
                ("Standard deviation", "std"),
                ("Minimum", "min"),
                ("Maximum", "max"),
            ]

            for label, key in statistics:
                if key == "count":
                    original_value = f"{original_summary[key]:,}"
                    generated_value = f"{generated_summary[key]:,}"
                else:
                    original_value = f"{original_summary[key]:.2f}"
                    generated_value = f"{generated_summary[key]:.2f}"

                sections.append(
                    f"| {label} | {original_value} | "
                    f"{generated_value} |"
                )

            sections.append("")

        # Department distribution
        sections.append("## Department Distribution\n")
        sections.append(
            "| Department | Original Count | Original % | "
            "Synthetic Count | Synthetic % |"
        )
        sections.append(
            "|---|---:|---:|---:|---:|"
        )

        raw_department = raw["Department"].value_counts()
        synthetic_department = synthetic["department"].value_counts()

        departments = sorted(
            set(raw_department.index)
            | set(synthetic_department.index)
        )

        for department in departments:
            raw_count = int(raw_department.get(department, 0))
            synthetic_count = int(
                synthetic_department.get(department, 0)
            )

            raw_pct = raw_count / len(raw) * 100
            synthetic_pct = (
                synthetic_count / len(synthetic) * 100
            )

            sections.append(
                f"| {department} | {raw_count:,} | "
                f"{raw_pct:.2f}% | {synthetic_count:,} | "
                f"{synthetic_pct:.2f}% |"
            )

        sections.append("")

        # Attrition distribution
        sections.append("## Attrition Distribution\n")
        sections.append(
            "| Employment Status | Original Count | Original % | "
            "Synthetic Count | Synthetic % |"
        )
        sections.append(
            "|---|---:|---:|---:|---:|"
        )

        raw_active = (raw["Attrition"] == "No").sum()
        raw_attrited = (raw["Attrition"] == "Yes").sum()

        synthetic_active = (
            synthetic["is_active"] == 1
        ).sum()

        synthetic_attrited = (
            synthetic["is_active"] == 0
        ).sum()

        status_rows = [
            (
                "Active",
                raw_active,
                synthetic_active,
            ),
            (
                "Attrited",
                raw_attrited,
                synthetic_attrited,
            ),
        ]

        for status, raw_count, synthetic_count in status_rows:
            raw_pct = raw_count / len(raw) * 100
            synthetic_pct = (
                synthetic_count / len(synthetic) * 100
            )

            sections.append(
                f"| {status} | {raw_count:,} | "
                f"{raw_pct:.2f}% | {synthetic_count:,} | "
                f"{synthetic_pct:.2f}% |"
            )

        sections.append("")

        # Structural characteristics
        sections.append("## Structural Characteristics\n")
        sections.append(
            f"- Total synthetic employees: "
            f"{len(synthetic):,}"
        )
        sections.append(
            f"- Unique employee IDs: "
            f"{synthetic['employee_id'].nunique():,}"
        )
        sections.append(
            f"- Unique employee codes: "
            f"{synthetic['employee_code'].nunique():,}"
        )
        sections.append(
            f"- Unique email addresses: "
            f"{synthetic['email'].nunique():,}"
        )
        sections.append(
            f"- Employees without managers: "
            f"{synthetic['manager_id'].isna().sum():,}"
        )
        sections.append(
            f"- Active employees: {synthetic_active:,}"
        )
        sections.append(
            f"- Attrited employees: {synthetic_attrited:,}\n"
        )

        # Methodology
        sections.append("## Synthesis Methodology\n")
        sections.append(
            "The synthetic dataset was generated using "
            "the following approach:\n"
        )
        sections.append(
            "1. Cleaned the original IBM HR dataset."
        )
        sections.append(
            "2. Applied whole-row resampling with replacement."
        )
        sections.append(
            "3. Applied controlled noise to selected numeric "
            "attributes, including age, tenure and income."
        )
        sections.append(
            "4. Redrew 10% of selected satisfaction, involvement "
            "and training records from their original empirical "
            "distributions."
        )
        sections.append(
            "5. Generated employee identities and deterministic "
            "email addresses using the Faker `en_IN` locale."
        )
        sections.append(
            "6. Derived dates using the fixed snapshot date."
        )
        sections.append(
            "7. Assigned managers within the same department "
            "with a strictly higher job level."
        )
        sections.append(
            "8. Used random seed 42 for reproducibility.\n"
        )

        # Interpretation
        sections.append("## Interpretation and Limitations\n")
        sections.append(
            "The synthetic dataset preserves the broad statistical "
            "and structural characteristics of the original IBM HR "
            "dataset while expanding it to 100,000 records.\n"
        )
        sections.append(
            "The generated records are synthetic employees and must "
            "not be interpreted as actual additional IBM employees "
            "or historical employment events. The dataset is intended "
            "for data engineering, database design and analytics "
            "demonstrations.\n"
        )

        return "\n".join(sections)

    def generate_data_profile(self):
        """
        Generate the before-and-after Markdown data profile.
        """

        self.logger.info("Loading datasets for data profiling.")

        raw = pd.read_csv(self.raw_path)
        synthetic = pd.read_csv(self.synthetic_path)

        profile = self._build_profile(raw, synthetic)

        self.profile_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.profile_path.write_text(
            profile,
            encoding="utf-8",
        )

        self.logger.info(
            "Data profile generated: %s",
            self.profile_path,
        )

    def generate_all(self):
        """
        Generate all documentation artifacts.
        """

        self.logger.info(
            "Starting documentation generation."
        )

        self.generate_mappings()
        self.generate_data_profile()

        self.logger.info(
            "Documentation generation completed successfully."
        )
