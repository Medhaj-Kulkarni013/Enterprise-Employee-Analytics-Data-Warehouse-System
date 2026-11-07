
from abc import ABC, abstractmethod
import logging


class PipelineStep(ABC):
    """
    Abstract base class for all ETL pipeline steps.

    Implements the Template Method design pattern:
    every pipeline step follows the same execution sequence:
    validate input -> execute -> validate output.
    """

    def __init__(self, step_name: str):
        """
        Initialize the pipeline step.

        Args:
            step_name: Name used to identify the pipeline step.
        """
        self.step_name = step_name
        self.logger = logging.getLogger(self.__class__.__name__)

    def run(self):
        """
        Template method that controls the execution of a pipeline step.

        The execution sequence is fixed and shared by all subclasses.
        """
        self.logger.info("Starting pipeline step: %s", self.step_name)

        try:
            self.validate_input()

            result = self.execute()

            self.validate_output(result)

            self.logger.info(
                "Pipeline step completed successfully: %s",
                self.step_name
            )

            return result

        except Exception:
            self.logger.exception(
                "Pipeline step failed: %s",
                self.step_name
            )
            raise

    def validate_input(self):
        """
        Validate the input required by this pipeline step.

        Subclasses can override this method with specific checks.
        """
        pass

    @abstractmethod
    def execute(self):
        """
        Execute the actual processing logic.

        Every concrete pipeline step must implement this method.
        """
        pass

    def validate_output(self, result):
        """
        Validate the output produced by this pipeline step.

        Subclasses can override this method with specific checks.
        """
        pass
