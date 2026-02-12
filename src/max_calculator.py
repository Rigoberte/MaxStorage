from src.PERI_excel_reader import PERIExcelReader
import pandas as pd
from pathlib import Path
import os

class MaxCalculator:
    def __init__(self, folder_path: Path):
        self.folder_path = Path(folder_path)
        self.excel_reader = PERIExcelReader()
        self.temp_max = pd.DataFrame()
        self.protocols_with_errors = self._load_protocols_with_errors()
        
        # Diccionario para guardar el mejor TOTAL_PRICE por protocolo
        self.best_protocol_totals = {}

    def _load_protocols_with_errors(self) -> set:
        """Carga los protocolos con errores desde el archivo txt."""
        file_path = Path(os.getcwd()) / "data" / "protocols_with_errors.txt"
        try:
            with open(file_path, 'r') as f:
                return set(line.strip() for line in f if line.strip())
        except FileNotFoundError:
            return set()

    def calculate_max(self) -> pd.DataFrame:
        for file in self.folder_path.glob('*.xlsx'):
            if not file.name.startswith("output_"):
                continue

            file_name = file.name
            report = pd.read_excel(file)
            
            self.optimize_daily_report(report, file_name)
        
        return self.temp_max
    
    def optimize_daily_report(self, daily_report: pd.DataFrame, file_name: str) -> None:
        """
        Optimiza el reporte diario comparando protocolos por TOTAL_PRICE.
        
        Para cada protocolo en el reporte diario:
        - Si está en protocols_with_errors, se salta
        - Suma TOTAL_PRICE por protocolo
        - Si es mayor que el guardado previamente, reemplaza todas las líneas del protocolo
        
        Args:
            daily_report: DataFrame con los datos de un día específico
            file_name: Nombre del archivo del reporte diario
        """
        if daily_report.empty:
            return
        
        valid_protocols = daily_report[
            ~daily_report['PROTOCOL'].isin(self.protocols_with_errors)
        ]
        
        if valid_protocols.empty:
            return
        
        # Obtener protocolos únicos del reporte
        unique_protocols = valid_protocols['PROTOCOL'].unique()
        
        for protocol in unique_protocols:
            protocol_rows = valid_protocols[valid_protocols['PROTOCOL'] == protocol]
            protocol_total = protocol_rows['TOTAL_PRICE'].sum()
            
            if protocol not in self.best_protocol_totals or protocol_total > self.best_protocol_totals[protocol]:
                self.best_protocol_totals[protocol] = protocol_total
                
                if not self.temp_max.empty:
                    self.temp_max = self.temp_max[self.temp_max['PROTOCOL'] != protocol]
                
                self.temp_max = pd.concat([self.temp_max, protocol_rows.assign(FILE_NAME=file_name)], ignore_index=True)