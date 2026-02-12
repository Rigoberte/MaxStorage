from abc import ABC, abstractmethod
import pandas as pd
from pathlib import Path

class ExcelReader(ABC):
    @abstractmethod
    def read_excel(self, file_path: Path) -> pd.DataFrame:
        """
        Reads an Excel file and returns its contents as a pandas DataFrame.
        
        :param file_path: The path to the Excel file to be read.
        :return: A pandas DataFrame representing the rows in the Excel file.
        """
        pass