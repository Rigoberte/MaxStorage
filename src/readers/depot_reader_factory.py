from src.readers.excel_reader import ExcelReader

class DepotReaderFactory:
    @staticmethod
    def create_depot_reader(depot_name: str) -> ExcelReader:
        if depot_name == 'PERI':
            from src.readers.PERI_excel_reader import PERIExcelReader
            return PERIExcelReader()
        else:
            raise ValueError(f"Unsupported depot name: {depot_name}")