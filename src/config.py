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
    ITEM_TYPE_REPLACEMENTS = CONFIGS_FOLDER / "item_types.xlsx"
    ERROR_SOLVER_PATH = CONFIGS_FOLDER / "solution_of_errors.xlsx"