from pathlib import Path
import os

class Config:
    DATA_FOLDER =  Path(os.getcwd()) / "data"
    
    # Carpetas de datos
    DEPOT_REPORTS_FOLDER = DATA_FOLDER / "depot_reports"
    PROCESSED_REPORTS_FOLDER = DATA_FOLDER / "processed_reports"
    CONFIGS_FOLDER = DATA_FOLDER / "configs"
    
    # Archivos de configuración
    EXCHANGE_RATE_PATH = CONFIGS_FOLDER / "exchanges_rate.xlsx"
    SERVICE_CONFIG_PATH = CONFIGS_FOLDER / "Services - Configuration.xlsx"
    PROTOCOLS_RENAMING = CONFIGS_FOLDER / "protocols_renaming.xlsx"

    # Archivos de salida
    PROTOCOLS_WITH_ERRORS_PATH = DATA_FOLDER / "protocols_with_errors.xlsx"
    MAX_VALUES_OUTPUT_PATH = DATA_FOLDER / "max_values.xlsx"