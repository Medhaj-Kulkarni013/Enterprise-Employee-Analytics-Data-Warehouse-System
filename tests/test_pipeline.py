"""Unit tests for ETL Pipeline Template Method, Preprocessor, Synthesizer, and HistoryGenerator."""
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from pipeline.base_step import PipelineStep
from pipeline.history_generator import HistoryGenerator
from pipeline.preprocessor import Preprocessor
from pipeline.synthesizer import Synthesizer


def _make_raw_ibm_df():
    """Create a minimal valid 35-column IBM HR fixture covering required categorical domains."""
    cols = [
        "EmployeeNumber", "Age", "Attrition", "BusinessTravel", "DailyRate", "Department",
        "DistanceFromHome", "Education", "EducationField", "EmployeeCount", "EnvironmentSatisfaction",
        "Gender", "HourlyRate", "JobInvolvement", "JobLevel", "JobRole", "JobSatisfaction",
        "MaritalStatus", "MonthlyIncome", "MonthlyRate", "NumCompaniesWorked", "Over18",
        "OverTime", "PercentSalaryHike", "PerformanceRating", "RelationshipSatisfaction",
        "StandardHours", "StockOptionLevel", "TotalWorkingYears", "TrainingTimesLastYear",
        "WorkLifeBalance", "YearsAtCompany", "YearsInCurrentRole", "YearsSinceLastPromotion",
        "YearsWithCurrManager",
    ]
    rows = [
        (101, 35, "No", "Travel_Rarely", 800, "Research & Development", 5, 3, "Life Sciences",
         1, 3, "Male", 65, 3, 2, "Research Scientist", 4, "Married", 6200, 18000, 1, "Y",
         "No", 12, 3, 3, 80, 1, 10, 2, 3, 6, 4, 4, 3),
        (102, 42, "Yes", "Travel_Frequently", 600, "Sales", 12, 4, "Marketing",
         1, 2, "Female", 72, 2, 3, "Sales Executive", 3, "Single", 9500, 21000, 3, "Y",
         "Yes", 15, 3, 4, 80, 0, 16, 3, 2, 8, 5, 6, 4),
        (103, 50, "No", "Non-Travel", 900, "Human Resources", 3, 4, "Human Resources",
         1, 4, "Male", 85, 4, 5, "Manager", 4, "Divorced", 17500, 24000, 2, "Y",
         "No", 18, 4, 3, 80, 2, 25, 4, 4, 15, 7, 9, 8),
        (104, 38, "No", "Travel_Rarely", 750, "Research & Development", 8, 3, "Medical",
         1, 3, "Female", 70, 3, 5, "Research Director", 4, "Married", 18200, 23000, 1, "Y",
         "No", 14, 3, 4, 80, 1, 14, 3, 3, 10, 5, 7, 6),
        (105, 45, "No", "Travel_Rarely", 700, "Sales", 6, 3, "Technical Degree",
         1, 3, "Male", 68, 3, 5, "Manager", 3, "Married", 16900, 22000, 2, "Y",
         "No", 13, 3, 3, 80, 1, 20, 2, 3, 12, 6, 8, 5),
        (106, 29, "Yes", "Travel_Frequently", 500, "Research & Development", 15, 2, "Other",
         1, 2, "Female", 55, 2, 1, "Laboratory Technician", 2, "Single", 2800, 12000, 1, "Y",
         "Yes", 11, 3, 2, 80, 0, 5, 2, 2, 3, 1, 2, 2),
        (107, 41, "No", "Travel_Rarely", 820, "Research & Development", 4, 4, "Life Sciences",
         1, 4, "Male", 80, 4, 4, "Manufacturing Director", 4, "Married", 14000, 20000, 2, "Y",
         "No", 16, 3, 4, 80, 1, 15, 3, 3, 9, 4, 5, 4),
        (108, 34, "No", "Travel_Rarely", 780, "Research & Development", 7, 3, "Medical",
         1, 3, "Female", 74, 3, 3, "Healthcare Representative", 3, "Married", 8800, 19000, 1, "Y",
         "No", 14, 3, 3, 80, 1, 11, 3, 3, 7, 3, 4, 3),
        (109, 26, "Yes", "Travel_Frequently", 450, "Sales", 18, 2, "Marketing",
         1, 2, "Male", 50, 2, 1, "Sales Representative", 2, "Single", 2400, 11000, 0, "Y",
         "Yes", 11, 3, 2, 80, 0, 3, 2, 2, 2, 0, 1, 1),
        (110, 31, "No", "Non-Travel", 650, "Human Resources", 5, 3, "Human Resources",
         1, 3, "Female", 60, 3, 2, "Human Resources", 3, "Single", 4200, 15000, 1, "Y",
         "No", 12, 3, 3, 80, 1, 6, 3, 3, 4, 2, 2, 2),
    ]
    return pd.DataFrame(rows, columns=cols)


class TestPipeline(unittest.TestCase):
    def test_abstract_pipeline_step_cannot_be_instantiated(self):
        with self.assertRaises(TypeError):
            PipelineStep("AbstractStep")

    def test_end_to_end_preprocess_synthesize_and_history_generation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            raw_csv = tmp / "ibm_raw.csv"
            clean_csv = tmp / "clean.csv"
            synth_csv = tmp / "synth_200.csv"
            sample_csv = tmp / "sample_50.csv"
            hist_csv = tmp / "history.csv"

            _make_raw_ibm_df().to_csv(raw_csv, index=False)

            # 1. Preprocessor
            prep = Preprocessor(input_path=raw_csv, output_path=clean_csv)
            clean_df = prep.run()
            self.assertEqual(len(clean_df), 10)
            self.assertIn("source_employee_number", clean_df.columns)
            self.assertNotIn("EmployeeCount", clean_df.columns)

            # 2. Synthesizer (scaled fixture of 200 rows)
            synth = Synthesizer(
                input_path=clean_csv,
                output_path=synth_csv,
                sample_path=sample_csv,
                n_records=200,
                seed=42,
            )
            synth_df = synth.run()
            self.assertEqual(len(synth_df), 200)
            self.assertEqual(synth_df["employee_id"].nunique(), 200)
            self.assertEqual(synth_df["email"].nunique(), 200)
            # Only JobLevel 5 employees may lack a manager
            no_mgr = synth_df[synth_df["manager_id"].isna()]
            self.assertTrue((no_mgr["job_level"] == 5).all())

            # 3. HistoryGenerator (SCD2 events)
            hist_gen = HistoryGenerator(
                input_path=synth_csv,
                output_path=hist_csv,
                fraction=0.25,
                seed=42,
            )
            hist_df = hist_gen.run()
            self.assertFalse(hist_df.empty)
            self.assertIn("Hire", set(hist_df["change_type"]))
            self.assertFalse(hist_df.duplicated(["employee_id", "effective_date"]).any())


if __name__ == "__main__":
    unittest.main()