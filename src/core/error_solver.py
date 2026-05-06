from src.config import Config
import pandas as pd

class ErrorSolver:
    def __init__(self, depot_name: str) -> None:
        try:
            df = pd.read_excel(Config.ERROR_SOLVER_PATH, sheet_name=depot_name)
            self.df = df
        except Exception as e:
            print(f"Error reading Excel file: {e}")
            self.df = pd.DataFrame(
                columns=["PROTOCOL", "PROTOCOL_ID", "DESCRIPTION", "SERVICE_ID"]
            )

    def solve_protocol_error(self, protocol_name: str) -> str:
        """Resuelve un error de protocolo dado su nombre."""
        if not protocol_name:
            return ""
        
        match = self.df[self.df["PROTOCOL"] == protocol_name]
        if not match.empty:
            return match.iloc[0]["PROTOCOL_ID"]
        else:
            return ""
        
    def solve_service_id_error(self, protocol_id: str, description: str) -> str | None:
        """Resuelve un error de protocolo dado su ID."""
        match = self.df[(self.df["PROTOCOL_ID"] == protocol_id) & (self.df["DESCRIPTION"] == description)]
        if not match.empty:
            return match.iloc[0]["SERVICE_ID"]
        else:
            return None