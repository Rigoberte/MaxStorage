from dataclasses import dataclass
import pandas as pd
import os

from src.config import Config
from src.readers.exchanges_rate_excel_reader import ExchangesRateExcelReader
from src.readers.depot_reader_factory import DepotReaderFactory
from src.readers.service_configuration_excel_reader import ServiceConfigurationExcelReader
from src.core.price_calculator import PriceCalculator
from src.core.max_calculator import MaxCalculator

@dataclass
class ProcessingResult:
    """Resultado del procesamiento de reportes."""
    billing_reports: dict[str, pd.DataFrame]
    error_protocols: pd.DataFrame
    max_values: pd.DataFrame
    processed_files: list[str]
    skipped_files: list[str]


class StorageService:
    def __init__(self):
        self._exchange_reader = ExchangesRateExcelReader()
        self._service_config_reader: ServiceConfigurationExcelReader | None = None
        self._depot_factory = DepotReaderFactory()
        self._depot_reader = self._depot_factory.create_depot_reader("PERI")
        self._price_calculator: PriceCalculator | None = None
        self._max_calculator: MaxCalculator | None = None
    
    def _initialize_calculators(self) -> None:
        exchanges = self._exchange_reader.read_excel(Config.EXCHANGE_RATE_PATH)
        self._service_config_reader = ServiceConfigurationExcelReader(exchanges)
        services = self._service_config_reader.read_excel(Config.SERVICE_CONFIG_PATH)
        self._price_calculator = PriceCalculator(services)
    
    def process_depot_reports(self) -> tuple[dict[str, pd.DataFrame], list[str], list[str]]:
        """
        Procesa todos los reportes de depósito.
        
        Returns:
            Tupla con:
                - Diccionario de {nombre_archivo: billing_report_df}
                - Lista de archivos procesados
                - Lista de archivos saltados
        """
        if self._price_calculator is None:
            self._initialize_calculators()
        
        billing_reports: dict[str, pd.DataFrame] = {}
        processed_files: list[str] = []
        skipped_files: list[str] = []
        
        files = os.listdir(Config.DEPOT_REPORTS_FOLDER)
        
        for file in files:
            if not (file.startswith("StockThermoFisher_ST_") and file.endswith(".xls")):
                skipped_files.append(file)
                continue
            
            print(f"Processing file: {file}")
            
            file_path = Config.DEPOT_REPORTS_FOLDER / file
            inventory_report = self._depot_reader.read_excel(file_path)
            
            file_name = os.path.splitext(file)[0]
            billing_report = self._price_calculator.calculate_storage_billing(
                inventory_report, file_name
            )
            
            billing_reports[file_name] = billing_report
            processed_files.append(file)
        
        return billing_reports, processed_files, skipped_files
    
    def calculate_max_values(
        self, 
        billing_reports: dict[str, pd.DataFrame],
        protocols_with_errors: pd.DataFrame | None = None
    ) -> pd.DataFrame:
        """
        Calcula los valores máximos por protocolo.
        
        Args:
            billing_reports: Diccionario con reportes de facturación
            protocols_with_errors: DataFrame con protocolos que tienen errores
            
        Returns:
            DataFrame con los valores máximos por protocolo
        """
        error_protocols_set = set()
        if protocols_with_errors is not None and not protocols_with_errors.empty:
            error_protocols_set = set(
                protocols_with_errors['PROTOCOL'].dropna().unique()
            )
        
        self._max_calculator = MaxCalculator(protocols_with_errors=error_protocols_set)
        
        for file_name, report in billing_reports.items():
            self._max_calculator.optimize_daily_report(
                report, 
                f"output_{file_name}.xlsx"
            )
        
        return self._max_calculator.get_max_values()
    
    def get_error_protocols(self) -> pd.DataFrame:
        """Retorna los protocolos con errores."""
        if self._price_calculator is None:
            return pd.DataFrame()
        return self._price_calculator.get_error_protocols()
    
    def process_all(self, depot_name: str) -> ProcessingResult:
        """
        Ejecuta el flujo completo de procesamiento.
        
        Returns:
            ProcessingResult con todos los resultados
        """
        self._depot_reader = self._depot_factory.create_depot_reader(depot_name)

        # Procesar reportes
        billing_reports, processed_files, skipped_files = self.process_depot_reports()
        
        # Obtener errores
        error_protocols = self.get_error_protocols()
        
        # Calcular máximos
        max_values = self.calculate_max_values(billing_reports, error_protocols)
        
        return ProcessingResult(
            billing_reports=billing_reports,
            error_protocols=error_protocols,
            max_values=max_values,
            processed_files=processed_files,
            skipped_files=skipped_files
        )
    
    def save_results(self, result: ProcessingResult) -> None:
        """
        Guarda los resultados en archivos Excel.
        
        Args:
            result: Resultado del procesamiento
        """
        Config.PROCESSED_REPORTS_FOLDER.mkdir(parents=True, exist_ok=True)

        # Eliminar archivos existentes en processed_reports
        for existing_file in Config.PROCESSED_REPORTS_FOLDER.glob("output_*.xlsx"):
            try:
                existing_file.unlink()
            except Exception as e:
                print(f"Error deleting existing file {existing_file}: {e}")

        # Guardar reportes de facturación
        for file_name, billing_report in result.billing_reports.items():
            output_path = Config.PROCESSED_REPORTS_FOLDER / f"output_{file_name}.xlsx"
            try:
                billing_report.to_excel(output_path, index=False)
            except Exception as e:
                print(f"Error saving file {output_path}: {e}")
        
        # Guardar protocolos con errores
        if not result.error_protocols.empty:
            error_path = Config.PROTOCOLS_WITH_ERRORS_PATH
            if error_path.exists():
                try:
                    error_path.unlink()
                except Exception as e:
                    print(f"Error deleting existing error file {error_path}: {e}")
            try:
                result.error_protocols.to_excel(error_path, index=False)
            except Exception as e:
                print(f"Error saving error protocols file {error_path}: {e}")
        
        # Guardar valores máximos
        max_path = Config.MAX_VALUES_OUTPUT_PATH
        if max_path.exists():
            max_path.unlink()
        try:
            result.max_values.to_excel(max_path, index=False)
        except Exception as e:
            print(f"Error saving max values file {max_path}: {e}")
