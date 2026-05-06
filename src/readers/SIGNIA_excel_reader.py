import pandas as pd
from pathlib import Path
from src.readers.excel_reader import ExcelReader
from src.config import Config

class SIGNIAExcelReader(ExcelReader):
    def __init__(self):
        self.lot_status_replacements = {
            "BAJAS": "Expired",
            "CUARENTENA": "Quarantine",
            "DEVOLUCIONES": "Expired",
            "DISPONIBLE": "Approved",
            "VENCIMIENTO CERCANO": "Approved"
        }
        
        try:
            self.item_type_replacements = pd.read_excel(Config.ITEM_TYPE_REPLACEMENTS, sheet_name="SIGNIA").set_index("ITEM DESCRIPTION")["ITEM_TYPE"].to_dict()
        except Exception as e:
            print(f"Error loading item type replacements file: {e}")
            self.item_type_replacements = {}

        self.type_replacements = {
            "Medication": "Drug",
            "Ancillaries": "Non-Drug",
            "CREDOs": "Non-Drug",
            "TT4": "Non-Drug",
            "Label": "Label"
        }

        self.temperature_replacements = {
            "DE 15°C A 25°C": "Ambient",
            "REFRIGERADO (DE 2°C A 8°C)": "Refrigerated"
        }

        try:
            self.protocols_renaming = pd.read_excel(Config.PROTOCOLS_RENAMING, sheet_name="SIGNIA").set_index("Depot")["FisherBook"].to_dict()
        except Exception as e:
            print(f"Error loading protocols renaming file: {e}")
            self.protocols_renaming = {}

    def _get_storage_type(self, is_a_return: bool) -> str:
        """Determina el tipo de posición basado si es una devolución o no."""
        if is_a_return:
            return "Pallet"
        
        return "Bin"

    def _potential_description(self, general_type: str, temperature: str, is_a_return: bool) -> str:
        """Genera la descripción del servicio basado en el tipo, temperatura y si es una devolución."""
        if is_a_return:
            return "Storage of Returns"
        
        if general_type == "Non-Drug":
            return f"Non-Drug Storage {temperature}"
        
        elif general_type == "Label":
            return f"Storage of Labels {temperature}"
        
        elif general_type == "Drug":
            return f"Storage {temperature}"
        
        else:
            return "Unknown Service"
        
    def _service_description(self, lot_status: str, item_type:str, temperature: str, is_a_return: bool) -> str:
        """Genera la descripción del servicio basado en el tipo, temperatura y si es una devolución."""
        if is_a_return:
            return f"Returned {item_type}"
        
        return f"{temperature} {lot_status} {item_type}"

    def read_excel(self, file_path: Path) -> pd.DataFrame:
        try:
            df: pd.DataFrame = pd.read_excel(file_path)

            # Renombrar protocolos según el archivo de renaming
            df['PROTOCOLO'] = df['PROTOCOLO'].replace(self.protocols_renaming)
            
            # Asegurar que SALDO_TOTAL es numérico
            df['SALDO_TOTAL'] = pd.to_numeric(df['SALDO_TOTAL'], errors='coerce').fillna(0).astype('int64')
            
            df['ITEM_TYPE'] = df['DESCRPCION_PRODUCTO'].map(self.item_type_replacements).fillna('')
            df['ERROR'] = df[df['ITEM_TYPE'] == '']['DESCRPCION_PRODUCTO'].apply(lambda x: f"Item type '{x}' not found in replacements")

            rename_map = {
                "PROTOCOLO": "PROTOCOL",
                "DES_ALMACEN": "LOT_STATUS",
                "UBICACION": "POSITION",
                "TEMPERATURA" : "TEMPERATURE",
                'SALDO_TOTAL': 'AMOUNT_OF_KITS',
                'ITEM_TYPE' : 'ITEM_TYPE'
            }
            
            # Agrupar por columnas y sumar SALDO_TOTAL
            df = df.groupby(list(rename_map.keys()), as_index=False, dropna=False).agg(
                {
                    'SALDO_TOTAL': 'sum',
                    'ERROR': lambda x: '; '.join(x.dropna().unique()) if x.notna().any() else ''
                }
            )
            
            df.rename(columns=rename_map, inplace=True)
            
            df['TEMPERATURE'] = df['TEMPERATURE'].replace(self.temperature_replacements)
            
            df = df[df['PROTOCOL'].notna()]
            
            df['IS_A_RETURN'] = df['LOT_STATUS'] == "DEVOLUCIONES"
            df['STORAGE_TYPE'] = df.apply(
                lambda row: self._get_storage_type(row['IS_A_RETURN']), 
                axis=1
            )
            
            columns_to_keep = ["PROTOCOL", "ITEM_TYPE", "LOT_STATUS", "TEMPERATURE", "STORAGE_TYPE", "POSITION", "AMOUNT_OF_KITS", "IS_A_RETURN", "ERROR"]
            
            df = df[columns_to_keep].copy()
            
            df['LOT_STATUS'] = df['LOT_STATUS'].replace(self.lot_status_replacements)
            df['GENERAL_TYPE'] = df['ITEM_TYPE'].replace(self.type_replacements)
            df['AMOUNT_OF_KITS'] = pd.to_numeric(df['AMOUNT_OF_KITS'], errors='coerce').fillna(0).astype('int64')

            df['POTENTIAL_SERVICE'] = df.apply(
                lambda row: self._potential_description(row.get('GENERAL_TYPE', ''), row.get('TEMPERATURE', ''), row.get('IS_A_RETURN', False)),
                axis=1
            )

            df['DESCRIPTION'] = df.apply(
                lambda row: self._service_description(row.get('LOT_STATUS', ''), row.get('ITEM_TYPE', ''), row.get('TEMPERATURE', ''), row.get('IS_A_RETURN', False)),
                axis=1
            )
            
            return df
            
        except Exception as e:
            print(f"An error occurred while reading the Excel file: {e}")
            return pd.DataFrame()