import pandas as pd
from typing import Set


class MaxCalculator:
    """
    Calculador de valores máximos por protocolo.
    
    Recibe reportes de facturación y mantiene el registro con el mayor
    TOTAL_PRICE por protocolo.
    """
    
    def __init__(self, protocols_with_errors: Set[str] | None = None):
        self._max_values = pd.DataFrame()
        self._protocols_with_errors = protocols_with_errors or set()
        self._best_protocol_totals: dict[str, float] = {}

    def get_max_values(self) -> pd.DataFrame:
        return self._max_values.copy()
    
    def optimize_daily_report(self, daily_report: pd.DataFrame, file_name: str) -> None:
        if daily_report.empty:
            return
        
        valid_protocols = daily_report[
            ~daily_report['PROTOCOL'].isin(self._protocols_with_errors)
        ]
        
        if valid_protocols.empty:
            return
        
        unique_protocols = valid_protocols['PROTOCOL'].unique()
        
        for protocol in unique_protocols:
            protocol_rows = valid_protocols[valid_protocols['PROTOCOL'] == protocol]
            protocol_total = protocol_rows['TOTAL_PRICE'].sum()
            
            if protocol not in self._best_protocol_totals or protocol_total > self._best_protocol_totals[protocol]:
                self._best_protocol_totals[protocol] = protocol_total
                
                if not self._max_values.empty:
                    self._max_values = self._max_values[self._max_values['PROTOCOL'] != protocol]

                clean_file_name = file_name.replace("output_", "").replace(".xlsx", "")
                
                self._max_values = pd.concat(
                    [self._max_values, protocol_rows.assign(FILE_NAME=clean_file_name)], 
                    ignore_index=True
                )