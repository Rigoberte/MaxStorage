import os
from pathlib import Path

from src.PERI_excel_reader import PERIExcelReader
from src.service_configuration_excel_reader import ServiceConfigurationExcelReader
from src.exchanges_rate import ExchangesRateExcelReader
from src.price_calculator import PriceCalculator
from src.max_calculator import MaxCalculator

folder_path = Path(r"C:\Users\inaki.costa\Thermo Fisher Scientific\PPI CTD Latam - General\Digital PPI Solutions\Max Storage Andina")
exchange_rate_path = folder_path / "exchanges_rate.xlsx"
service_configuration_path = folder_path / "Services - Configuration.xlsx"
folder_data = Path(os.getcwd()) / "data"

def main():
    process_depot_reports()
    calculate_max_price_per_protocol()


def process_depot_reports():
    exchanges = ExchangesRateExcelReader().read_excel(exchange_rate_path)

    services = ServiceConfigurationExcelReader(exchanges).read_excel(service_configuration_path)

    depotExcelReader = PERIExcelReader()

    calculator = PriceCalculator(services)

    files = os.listdir(folder_data / "depot_reports")
    for file in files:
        if not (file.startswith("StockThermoFisher_ST_") and file.endswith(".xls")):
            continue
        print (f"Processing file: {file}")
        
        file_path = folder_data / "depot_reports" / file

        inventory_report = depotExcelReader.read_excel(file_path)
        
        billing_report = calculator.calculate_storage_billing(inventory_report)

        file_name = str.replace(os.path.splitext(file)[0], " ", "_")
        output_path = folder_data / "processed_reports" / ("output_" + file_name + ".xlsx")

        if output_path.exists():
            output_path.unlink()
        billing_report.to_excel(output_path, index=False)

    calculator.save_error_protocols(folder_data)
    return

def calculate_max_price_per_protocol():
    print("Calculating max price per protocol...")
    max_calculator = MaxCalculator(folder_data / "processed_reports")
    max_values_df = max_calculator.calculate_max()

    output_path = folder_data / "max_values.xlsx"
    if output_path.exists():
        output_path.unlink()
    max_values_df.to_excel(output_path, index=False)

if __name__ == "__main__":
    main()