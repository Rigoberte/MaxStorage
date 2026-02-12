from src.excel_reader import ExcelReader
from pathlib import Path
import pandas as pd

class ServiceConfigurationExcelReader(ExcelReader):
    def __init__(self, exchanges_df: pd.DataFrame):
        self.renames = {
            "Sponsor\nID": "Sponsor ID",
            "Sponsor\nStatus" : "Sponsor Status",
            "Protocol\nID": "Protocol ID",
            "Study\nStatus": "Study Status",
            "Service\nID": "Service ID",
            "Service\nStatus": "Service Status",
            "Have \nPrice / Contract" : "Price",
            "Discount\n(inherited\n or custom)": "Discount"
        }

        self.exchanges_df = exchanges_df

    def read_excel(self, file_path: Path) -> pd.DataFrame:
        try:
            df = pd.read_excel(file_path, header=1)
            df.rename(columns=self.renames, inplace=True)

            df = df[["Sponsor", "Protocol", "Protocol ID", "Study Status", "Service", "Service ID", "Service Status", "Price", "Currency", "Discount", "Country"]]
            df = df[(df['Country'] == 'Chile') & (df['Service Status'] == 'Active') & (df['Currency'] != '')]

            #Obtener valor entre " (per" y ")" para crear la columna "Position Type"
            df["Position Type"] = df["Service"].apply(lambda x: str.strip(x.split(" (per")[1].split(")")[0]) if isinstance(x, str) and " (per" in x else "Unknown")

            # Limpiar la columna Service para eliminar cualquier texto después de " (per"
            df["Service"] = df["Service"].apply(lambda x: x.split(" (per")[0] if isinstance(x, str) else x)

            # Agregar columna Exchange Rate basada en la columna Currency
            df = df.merge(self.exchanges_df, on='Currency', how='left')

            df['Price_USD'] = df['Price'] * df['Exchange Rate']

            return df
        except Exception as e:
            print(f"Error reading Excel file: {e}")
            return pd.DataFrame()  # Retornar un DataFrame vacío en caso de error