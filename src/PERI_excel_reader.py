import pandas as pd
from pathlib import Path
from src.excel_reader import ExcelReader
from src.config import Config

class PERIExcelReader(ExcelReader):
    def __init__(self):
        self.lot_status_replacements = {
            "BLOQUEADO": "Expired",
            "CUARENTENA": "Quarantine",
            "DEVOLUCION": "Expired",
            "LIBERADO": "Approved",
            "RECHAZADO": "Expired",
            "RECHAZADOE": "Expired",
            "VENCIDO": "Expired"
        }
        
        self.item_type_replacements = {
            "material": "CREDOs",
            "materiales": "Ancillaries",
            "medicación": "Medication",
            "monitores": "TT4",
            "retorno": "Medication"
        }

        self.type_replacements = {
            "Medication": "Drug",
            "Ancillaries": "Non-Drug",
            "CREDOs": "Non-Drug",
            "TT4": "Non-Drug",
            "Label": "Label"
        }

        try:
            self.protocols_renaming = pd.read_excel(Config.PROTOCOLS_RENAMING, sheet_name="PERI").set_index("Depot")["FisherBook"].to_dict()
        except Exception as e:
            print(f"Error loading protocols renaming file: {e}")
            self.protocols_renaming = {}

    def _get_temperature_condition(self, ubicacion: str) -> str:
        """Determina la condición de temperatura basada en la ubicación."""
        if pd.isna(ubicacion):
            return ""
        
        ubicacion = str(ubicacion)
        if ubicacion.startswith("EFR"):
            return "Refrigerated"
        elif ubicacion.startswith("EF"):
            return "Ambient"
        elif ubicacion.startswith("L"):
            return "Ambient"
        elif ubicacion.startswith("MG"):
            return "Frozen"
        return ""

    def _get_storage_type(self, ubicacion: str, temperatura: str) -> str:
        """Determina el tipo de posición basado en la ubicación y temperatura."""
        if pd.isna(ubicacion):
            return ""
        
        ubicacion = str(ubicacion)
        if temperatura == "Frozen":
            return "Shelf"
        elif ubicacion.startswith("EF"):
            return "Bin"
        elif ubicacion.startswith("L"):
            return "Pallet"
        return ""

    def _extract_item_type(self, linea: str) -> str:
        """Extrae el texto antes del primer espacio, lo convierte a minúsculas y aplica reemplazos."""
        if pd.isna(linea):
            return ""
        linea = str(linea).strip()
        
        before_delimiter = linea.split(" ")[0] if " " in linea else linea
        item_type = before_delimiter.lower().strip()
        
        return self.item_type_replacements.get(item_type, item_type)
    
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
            
            # Asegurar que SALDO es numérico
            df['SALDO'] = pd.to_numeric(df['SALDO'], errors='coerce').fillna(0).astype('int64')
            
            rename_map = {
                "PROTOCOLO": "PROTOCOL",
                "LINEA": "ITEM_TYPE",
                "ESTADO STOCK": "LOT_STATUS",
                "CLIENTE": "COMPONENT",
                "UBICACIÓN": "POSITION",
                'SALDO': 'AMOUNT_OF_KITS'
            }
            
            # Agrupar por columnas y sumar SALDO
            df = df.groupby(list(rename_map.keys()), as_index=False, dropna=False).agg({'SALDO': 'sum'})
            
            df.rename(columns=rename_map, inplace=True)
            
            df['TEMPERATURE'] = df['POSITION'].apply(self._get_temperature_condition)
            
            df = df[df['PROTOCOL'].notna()]
            
            df['STORAGE_TYPE'] = df.apply(
                lambda row: self._get_storage_type(row['POSITION'], row['TEMPERATURE']), 
                axis=1
            )
            
            columns_to_keep = ["PROTOCOL", "ITEM_TYPE", "LOT_STATUS", "TEMPERATURE", "STORAGE_TYPE", "POSITION", "AMOUNT_OF_KITS"]
            
            df = df[columns_to_keep].copy()
            
            df['IS_A_RETURN'] = df['LOT_STATUS'] == "DEVOLUCION"
            df['LOT_STATUS'] = df['LOT_STATUS'].replace(self.lot_status_replacements)
            df['ITEM_TYPE'] = df['ITEM_TYPE'].apply(self._extract_item_type)
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