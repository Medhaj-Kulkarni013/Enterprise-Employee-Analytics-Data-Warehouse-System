from pathlib import Path
import logging

from pipeline.preprocessor import Preprocessor
from pipeline.synthesizer import Synthesizer
from pipeline.validator import DataValidator
from pipeline.documentation import DocumentationGenerator


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def configure_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main():
    configure_logging()
    logger = logging.getLogger("EmployeeAnalyticsPipeline")

    logger.info("=" * 60)
    logger.info("EMPLOYEE ANALYTICS - DATA SYNTHESIS PIPELINE")
    logger.info("=" * 60)

    # STEP 1: Data preprocessing
    logger.info("STEP 1: Starting data preprocessing...")

    preprocessor = Preprocessor(
        input_path=PROJECT_ROOT / "data/raw/ibm_hr_dataset.csv",
        output_path=PROJECT_ROOT / "data/processed/employees_clean_base.csv",
    )

    clean_data = preprocessor.run()
    cleaning_summary = preprocessor.get_cleaning_summary()

    logger.info("Preprocessing completed successfully.")
    logger.info("Cleaned dataset shape: %s", clean_data.shape)
    logger.info("Cleaning summary: %s", cleaning_summary)

    # STEP 2: Synthetic data generation
    logger.info("STEP 2: Starting synthetic data generation...")

    synthesizer = Synthesizer(
        input_path=PROJECT_ROOT / "data/processed/employees_clean_base.csv",
        output_path=PROJECT_ROOT / "data/synthetic/employees_100k.csv",
        sample_path=PROJECT_ROOT / "data/synthetic/employees_sample_500.csv",
        n_records=100_000,
        seed=42,
    )

    synthetic_data = synthesizer.run()

    logger.info("Synthetic data generation completed successfully.")
    logger.info("Final dataset shape: %s", synthetic_data.shape)

    # STEP 3: Data validation
    logger.info("STEP 3: Starting data validation...")

    validator = DataValidator(
        raw_path=PROJECT_ROOT / "data/raw/ibm_hr_dataset.csv",
        clean_path=PROJECT_ROOT / "data/processed/employees_clean_base.csv",
        synthetic_path=PROJECT_ROOT / "data/synthetic/employees_100k.csv",
        report_path=PROJECT_ROOT / "reports/validation_report.txt",
        expected_records=100_000,
    )

    validation_report = validator.run()

    logger.info("Data validation completed.")
    logger.info(
        "Validation report generated at: %s",
        PROJECT_ROOT / "reports/validation_report.txt",
    )

    # STEP 4: Documentation generation
    logger.info("STEP 4: Starting documentation generation...")

    documentation_generator = DocumentationGenerator(
        raw_path=PROJECT_ROOT / "data/raw/ibm_hr_dataset.csv",
        synthetic_path=PROJECT_ROOT / "data/synthetic/employees_100k.csv",
        mappings_path=PROJECT_ROOT / "docs/mappings.json",
        profile_path=PROJECT_ROOT / "docs/data_profile.md",
    )

    documentation_generator.generate_all()

    logger.info("Documentation generated successfully.")
    logger.info(
        "Mappings: %s",
        PROJECT_ROOT / "docs/mappings.json",
    )
    logger.info(
        "Data profile: %s",
        PROJECT_ROOT / "docs/data_profile.md",
    )

    # Final pipeline summary
    logger.info("=" * 60)
    logger.info("PIPELINE EXECUTION COMPLETED")
    logger.info("=" * 60)

    logger.info("Original records: %s", len(clean_data))
    logger.info("Synthetic records: %s", len(synthetic_data))
    logger.info("Final columns: %s", len(synthetic_data.columns))

    logger.info(
        "Employees without managers: %s",
        synthetic_data["manager_id"].isna().sum(),
    )

    logger.info(
        "Active employees: %s",
        (synthetic_data["is_active"] == 1).sum(),
    )

    logger.info(
        "Attrited employees: %s",
        (synthetic_data["is_active"] == 0).sum(),
    )

    logger.info(
        "Full dataset: %s",
        PROJECT_ROOT / "data/synthetic/employees_100k.csv",
    )

    logger.info(
        "Sample dataset: %s",
        PROJECT_ROOT / "data/synthetic/employees_sample_500.csv",
    )

    logger.info(
        "Validation report: %s",
        PROJECT_ROOT / "reports/validation_report.txt",
    )

    logger.info(
        "Data profile: %s",
        PROJECT_ROOT / "docs/data_profile.md",
    )

    logger.info(
        "Mappings: %s",
        PROJECT_ROOT / "docs/mappings.json",
    )


if __name__ == "__main__":
    main()