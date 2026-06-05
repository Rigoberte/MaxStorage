from dataclasses import dataclass
import pandas as pd
import os
from pathlib import Path
from datetime import date

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
    selected_report: pd.DataFrame
    import_file: pd.DataFrame
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

    def _build_selected_report(self, max_values: pd.DataFrame) -> pd.DataFrame:
        """Lee los archivos originales de depot_reports sin procesar, por cada FILE_NAME en max_values, una sola vez."""
        if max_values.empty or "FILE_NAME" not in max_values.columns:
            return pd.DataFrame()

        selected_frames: list[pd.DataFrame] = []
        unique_files = max_values["FILE_NAME"].dropna().unique()

        for file_name in unique_files:
            file_path = self._find_depot_report_file(file_name)
            if file_path is None:
                continue

            # Leer directamente con pandas sin aplicar transformaciones del depot_reader
            try:
                source_report = pd.read_excel(file_path)
            except Exception as e:
                print(f"Error reading depot report {file_path}: {e}")
                continue

            if source_report is None or source_report.empty:
                continue

            # Obtener los protocolos para este archivo según max_values
            selected_protocols = set(
                max_values[max_values["FILE_NAME"] == file_name]["PROTOCOL"].dropna().unique()
            )
            if not selected_protocols:
                continue

            # Buscar la columna de protocolo (puede variar según el formato)
            protocol_col = self._find_protocol_column(source_report)
            if protocol_col is None:
                continue

            selected_source = source_report[source_report[protocol_col].isin(selected_protocols)].copy()
            if selected_source.empty:
                continue

            selected_source.insert(0, "FILE_NAME", file_name)
            selected_frames.append(selected_source)

        if not selected_frames:
            return pd.DataFrame()

        return pd.concat(selected_frames, ignore_index=True)

    def _build_import_file(self, max_values: pd.DataFrame) -> pd.DataFrame:
        """Construye la hoja de importación a partir del reporte seleccionado."""
        # Columnas objetivo del archivo de importación
        out_cols = [
            "protocolID",
            "serviceID",
            "eventHistoryApplyDate",
            "eventHistoryDescription",
            "eventHistoryQtyDescription",
            "eventHistoryStorageType",
            "eventHistoryUOM",
        ]

        if max_values.empty:
            return pd.DataFrame(columns=out_cols)

        # Fecha de aplicación: día 15 del mes actual
        apply_date = date.today().replace(day=15)
        apply_date_str = apply_date.strftime("%d-%m-%Y")

        src = max_values

        # Preparar columnas fuente con nombres esperados (si faltan, quedan NaN)
        protocol_id = src.get("PROTOCOL_ID") if "PROTOCOL_ID" in src.columns else pd.Series([pd.NA] * len(src))
        service_id = src.get("SERVICE_ID") if "SERVICE_ID" in src.columns else pd.Series([pd.NA] * len(src))
        description = src.get("DESCRIPTION") if "DESCRIPTION" in src.columns else pd.Series([pd.NA] * len(src))
        amount_of_kits = src.get("AMOUNT_OF_KITS") if "AMOUNT_OF_KITS" in src.columns else pd.Series([pd.NA] * len(src))
        storage_type = src.get("STORAGE_TYPE") if "STORAGE_TYPE" in src.columns else pd.Series([pd.NA] * len(src))
        distinct_positions = src.get("DISTINCT_POSITIONS") if "DISTINCT_POSITIONS" in src.columns else pd.Series([pd.NA] * len(src))

        out = pd.DataFrame({
            "protocolID": protocol_id.values,
            "serviceID": service_id.values,
            "eventHistoryApplyDate": [apply_date_str] * len(src),
            "eventHistoryDescription": description.values,
            "eventHistoryQtyDescription": amount_of_kits.values,
            "eventHistoryStorageType": storage_type.values,
            "eventHistoryUOM": distinct_positions.values,
        })

        return out[out_cols]
    
    def _find_depot_report_file(self, file_name: str) -> Path | None:
        """Encuentra el archivo en depot_reports que corresponde al file_name."""
        if not Config.DEPOT_REPORTS_FOLDER.exists():
            return None

        pattern = FILE_PATTERNS.get(self._country_name)
        if pattern is None:
            return None

        _, file_extension = pattern
        potential_file = Config.DEPOT_REPORTS_FOLDER / f"{file_name}{file_extension}"

        if potential_file.exists():
            return potential_file

        return None

    def _find_protocol_column(self, df: pd.DataFrame) -> str | None:
        """Detecta el nombre de la columna de protocolo en el DataFrame."""
        possible_names = ["PROTOCOLO", "PROTOCOL"]
        for col_name in possible_names:
            if col_name in df.columns:
                return col_name
        return None
    
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
        selected_report = self._build_selected_report(max_values)
        import_file = self._build_import_file(max_values)
        
        return ProcessingResult(
            billing_reports=billing_reports,
            error_protocols=error_protocols,
            max_values=max_values,
            selected_report=selected_report,
            import_file=import_file,
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
        
        # Guardar valores máximos y hojas auxiliares en un único workbook
        max_path = Config.DATA_FOLDER / f"max_values_{depot_name}.xlsx"
        if max_path.exists():
            max_path.unlink()
        try:
            with pd.ExcelWriter(max_path) as writer:
                result.max_values.to_excel(writer, sheet_name="Max Values", index=False)
                result.import_file.to_excel(writer, sheet_name="Import File", index=False)
                result.selected_report.to_excel(writer, sheet_name="Report", index=False)
        except Exception as e:
            print(f"Error saving max values file {max_path}: {e}")
