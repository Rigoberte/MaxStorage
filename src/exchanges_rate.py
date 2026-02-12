from src.excel_reader import ExcelReader
from pathlib import Path
import pandas as pd

class ExchangesRateExcelReader(ExcelReader):
    def read_excel(self, file_path: Path) -> pd.DataFrame:
        try:
            df = pd.read_excel(file_path)
            return df
        except Exception as e:
            print(f"Error reading Excel file: {e}")
            return pd.DataFrame()