from dataclasses import dataclass
import pandas as pd
import os

from src.config import Config
from src.readers.excel_reader import ExcelReader
from src.readers.exchanges_rate_excel_reader import ExchangesRateExcelReader
from src.readers.depot_reader_factory import DepotReaderFactory
from src.readers.service_configuration_excel_reader import ServiceConfigurationExcelReader
from src.core.price_calculator import PriceCalculator
from src.core.max_calculator import MaxCalculator

# Mapeo de depósito a país
DEPOT_COUNTRY_MAP: dict[str, str] = {
    "PERI": "Chile",
    "SIGNIA": "Peru"
}

# Configuración de patrones de archivo por país
FILE_PATTERNS: dict[str, tuple[str, str]] = {
    "Chile": ("StockThermoFisher_ST_", ".xls"),
    "Peru": ("Saldos_Al_", ".xlsx")
}

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
        self._price_calculator: PriceCalculator | None = None
        self._max_calculator: MaxCalculator | None = None
        self._depot_reader: ExcelReader | None = None
        self._country_name: str = ""
        self._depot_name: str = ""
    
    def _initialize_calculators(self) -> None:
        exchanges = self._exchange_reader.read_excel(Config.EXCHANGE_RATE_PATH)
        self._service_config_reader = ServiceConfigurationExcelReader(exchanges)
        
        services = self._service_config_reader.read_excel(Config.SERVICE_CONFIG_PATH)
        services = services[services['Country'] == self._country_name] # Filtrar por país
        self._price_calculator = PriceCalculator(services, self._depot_name)
    
    def process_depot_reports(self) -> tuple[dict[str, pd.DataFrame], list[str], list[str]]:
        """
        Procesa todos los reportes de depósito.
        
        Returns:
            Tupla con:
                - Diccionario de {nombre_archivo: billing_report_df}
                - Lista de archivos procesados
                - Lista de archivos saltados
        """
        self._initialize_calculators()
        
        billing_reports: dict[str, pd.DataFrame] = {}
        processed_files: list[str] = []
        skipped_files: list[str] = []
        
        # Eliminar archivos existentes en processed_reports
        for existing_file in Config.PROCESSED_REPORTS_FOLDER.glob("output_*.xlsx"):
            try:
                existing_file.unlink()
            except Exception as e:
                print(f"Error deleting existing file {existing_file}: {e}")
        
        files = os.listdir(Config.DEPOT_REPORTS_FOLDER)
        
        for file in files:
            pattern = FILE_PATTERNS.get(self._country_name)
            if pattern is None:
                raise ValueError(f"No file pattern configured for country: {self._country_name}")
            
            starts, ends = pattern
            if not (file.startswith(starts) and file.endswith(ends)):
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
        self._depot_name = depot_name
        self._country_name = DEPOT_COUNTRY_MAP.get(depot_name, "")
        if not self._country_name:
            raise ValueError(f"Unknown depot: {depot_name}. Valid depots: {list(DEPOT_COUNTRY_MAP.keys())}")
        
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
    
    def save_results(self, result: ProcessingResult, depot_name: str) -> None:
        """
        Guarda los resultados en archivos Excel.
        
        Args:
            result: Resultado del procesamiento
        """
        Config.PROCESSED_REPORTS_FOLDER.mkdir(parents=True, exist_ok=True)

        # Guardar reportes de facturación
        for file_name, billing_report in result.billing_reports.items():
            output_path = Config.PROCESSED_REPORTS_FOLDER / f"output_{depot_name}_{file_name}.xlsx"
            try:
                billing_report.to_excel(output_path, index=False)
            except Exception as e:
                print(f"Error saving file {output_path}: {e}")
        
        # Guardar protocolos con errores
        if not result.error_protocols.empty:
            error_path = Config.DATA_FOLDER / f"protocols_with_errors_{depot_name}.xlsx"
            if error_path.exists():
                try:
                    error_path.unlink()
                except Exception as e:
                    print(f"Error deleting existing error file {error_path}: {e}")
            
            item_type_errors = result.error_protocols[result.error_protocols['ERROR'].str.contains("Item type")]['ERROR']
            
            if not item_type_errors.empty:
                # Extraer todos los item types de cada línea (puede haber más de uno por línea)
                item_type_errors = item_type_errors.str.findall(r"Item type '([^']+)' not found").explode().dropna().unique()

            # Guardar los protocolos en hoja "Errors" y los item types con error en hoja "Item Type Errors"
            try:
                with pd.ExcelWriter(error_path) as writer:
                    result.error_protocols.to_excel(writer, sheet_name="Errors", index=False)
                    
                    if len(item_type_errors) > 0:
                        pd.DataFrame({"ITEM_TYPE_ERRORS": item_type_errors}).to_excel(writer, sheet_name="Item Type Errors", index=False)
            except Exception as e:
                print(f"Error saving error protocols file {error_path}: {e}")
        
        # Guardar valores máximos
        max_path = Config.DATA_FOLDER / f"max_values_{depot_name}.xlsx"
        if max_path.exists():
            max_path.unlink()
        try:
            result.max_values.to_excel(max_path, index=False)
        except Exception as e:
            print(f"Error saving max values file {max_path}: {e}")
