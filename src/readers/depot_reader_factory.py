from src.readers.excel_reader import ExcelReader

class DepotReaderFactory:
    @staticmethod
    def create_depot_reader(depot_name: str) -> ExcelReader:
        if depot_name == 'PERI':
            from src.readers.PERI_excel_reader import PERIExcelReader
            return PERIExcelReader()
        elif depot_name == 'SIGNIA':
            from src.readers.SIGNIA_excel_reader import SIGNIAExcelReader
            return SIGNIAExcelReader()
        else:
            raise ValueError(f"Unsupported depot name: {depot_name}")