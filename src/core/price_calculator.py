import pandas as pd
import math
from difflib import SequenceMatcher
from src.core.error_solver import ErrorSolver

class PriceCalculator:
    def __init__(self, services_df: pd.DataFrame, depot_name: str):
        self.services_df = services_df
        self.depot_name = depot_name
        
        self.transformation_matrix = pd.DataFrame(
            {
                "Pallet" : {"Pallet": 1.0, "Shelf": 2.0, "Bin": 8.0},
                "Shelf" : {"Pallet": 0.5, "Shelf": 1.0, "Bin": 4.0},
                "Bin" : {"Pallet": 0.125, "Shelf": 0.250, "Bin": 1.0}
            }
        )
        self.protocol_memo = {}
        self.service_memo = {}

        # Lista para acumular errores (más eficiente que concat en loop)
        self._error_rows: list[dict] = []

        self.error_solver = ErrorSolver(depot_name)

    def _add_protocol_with_error(self, 
            inventory_protocol: str, matched_protocol: str | None, 
            protocol_id: str | None, potential_service: str, 
            service_id: str | None, description: str, 
            storage_type: str, amount_of_kits: int, distinct_positions: int,
            error_message: str, file_name: str) -> None:
        """Agrega un registro de error a la lista de protocolos con errores."""
        # Verificar si ya existe este error (evitar duplicados)
        error_key = (inventory_protocol, potential_service, description, storage_type, error_message)
        if any(
            (r['PROTOCOL'], r['POTENTIAL_SERVICE'], r['DESCRIPTION'], r['STORAGE_TYPE'], r['ERROR']) == error_key
            for r in self._error_rows
        ):
            return
        
        self._error_rows.append({
            'PROTOCOL': inventory_protocol,
            'MATCHED_PROTOCOL': matched_protocol,
            'PROTOCOL_ID': protocol_id,
            'POTENTIAL_SERVICE': potential_service,
            'SERVICE_ID': service_id,
            'DESCRIPTION': description,
            'STORAGE_TYPE': storage_type,
            'AMOUNT_OF_KITS': amount_of_kits,
            'DISTINCT_POSITIONS': distinct_positions,
            'ERROR': error_message,
            'FILE_NAME': file_name
        })


    def _convert_from_to(self, amount_of_positions: int, from_type: str, to_type: str) -> int:
        """Convierte la cantidad de posiciones de un tipo a otro usando la matriz de transformación."""
        if from_type not in self.transformation_matrix.columns or to_type not in self.transformation_matrix.columns:
            raise ValueError(f"Invalid from_type '{from_type}' or to_type '{to_type}'. Valid types are: {self.transformation_matrix.columns.tolist()}")
        converted = amount_of_positions * self.transformation_matrix[from_type][to_type]
        return math.ceil(converted)  # Redondear hacia arriba

    def _find_best_protocol_match(self, inventory_protocol: str) -> tuple[str, str]:
        """
        Busca el protocolo más parecido en la configuración de servicios.
        Retorna (Protocol, Protocol ID).
        """
        if pd.isna(inventory_protocol) or inventory_protocol == "":
            return ("", "")
        
        if inventory_protocol in self.protocol_memo:
            return self.protocol_memo[inventory_protocol]

        protocol_name = ""
        protocol_id = ""
        max_similarity = 0.85
        
        inventory_protocol = str(inventory_protocol).strip().upper()
        
        for _, row in self.services_df[['Protocol', 'Protocol ID']].drop_duplicates().iterrows():
            service_protocol = str(row['Protocol']).strip().upper()
            similarity = SequenceMatcher(None, inventory_protocol, service_protocol).ratio()
            if similarity > max_similarity:
                protocol_name = row['Protocol']
                protocol_id = row['Protocol ID']
                max_similarity = similarity

        if protocol_id == "":
            protocol_id = self.error_solver.solve_protocol_error(inventory_protocol)
            matched_row = self.services_df[self.services_df['Protocol ID'] == protocol_id]
            if not matched_row.empty:
                protocol_name = matched_row.iloc[0]['Protocol']

        if protocol_id == "":
            return ("", "")
        
        self.protocol_memo[inventory_protocol] = (protocol_name, protocol_id)
        return (protocol_name, protocol_id)

    def _find_matching_service(self, protocol: str, potential_service: str, description: str) -> pd.Series | None:
        """
        Busca el servicio que coincida con el protocolo y el servicio potencial.
        Retorna la fila del servicio encontrado o None.
        """
        if protocol == "" or potential_service == "":
            return None
        
        cache_key = (protocol, potential_service)
        if cache_key in self.service_memo:
            return self.service_memo[cache_key]
        
        # Filtrar por protocolo
        protocol_services = self.services_df[self.services_df['Protocol'] == protocol]
        
        if protocol_services.empty:
            return None
        
        # Buscar el servicio más parecido al POTENTIAL_SERVICE
        potential_service_upper = str(potential_service).strip().upper()
        best_match = None
        best_score = 0.85
        
        for _, row in protocol_services.iterrows():
            service_name = str(row['Service']).strip().upper()
            similarity = SequenceMatcher(None, potential_service_upper, service_name).ratio()
            if similarity > best_score:
                best_score = similarity
                best_match = row

        if best_match is None:
            resolved_service_id = self.error_solver.solve_service_id_error(protocol, description)
            if resolved_service_id is not None:
                best_row = protocol_services[protocol_services['Service ID'] == resolved_service_id]
                if not best_row.empty:
                    best_match = best_row.iloc[0]

        if best_match is None:
            return None

        self.service_memo[cache_key] = best_match
        return best_match
    
    def get_error_protocols(self) -> pd.DataFrame:
        """
        Retorna un DataFrame con los protocolos que tuvieron errores.
        
        Returns:
            DataFrame con los protocolos con errores
        """
        if not self._error_rows:
            return pd.DataFrame(columns=[
                'PROTOCOL', 'MATCHED_PROTOCOL', 'PROTOCOL_ID', 'POTENTIAL_SERVICE',
                'SERVICE_ID', 'DESCRIPTION', 'STORAGE_TYPE', 'AMOUNT_OF_KITS',
                'DISTINCT_POSITIONS', 'ERROR', 'FILE_NAME'
            ])
        return pd.DataFrame(self._error_rows)

    def _build_billing_row(
        self,
        inventory_protocol: str,
        potential_service: str,
        description: str,
        storage_type: str,
        amount_of_kits: int,
        distinct_positions: int,
        matched_protocol: str | None = None,
        protocol_id: str | None = None,
        service_id: str | None = None,
        service_position_type: str | None = None,
        converted_positions: int | None = None,
        price_usd: float | None = None,
        total_price: float | None = None,
        error: str | None = None
    ) -> dict:
        """Construye un diccionario con los datos de una fila de facturación."""
        return {
            'PROTOCOL': inventory_protocol,
            'MATCHED_PROTOCOL': matched_protocol,
            'PROTOCOL_ID': protocol_id,
            'POTENTIAL_SERVICE': potential_service,
            'SERVICE_ID': service_id,
            'DESCRIPTION': description,
            'STORAGE_TYPE': storage_type,
            'SERVICE_POSITION_TYPE': service_position_type,
            'AMOUNT_OF_KITS': amount_of_kits,
            'DISTINCT_POSITIONS': distinct_positions,
            'CONVERTED_POSITIONS': converted_positions,
            'PRICE_USD': price_usd,
            'TOTAL_PRICE': total_price,
            'ERROR': error
        }

    def _group_inventory_report(self, inventory_report_df: pd.DataFrame) -> pd.DataFrame:
        """Agrupa el reporte de inventario por protocolo, servicio y tipo de storage."""
        return inventory_report_df.groupby(
            ['PROTOCOL', 'POTENTIAL_SERVICE', 'STORAGE_TYPE'],
            as_index=False,
            dropna=False
        ).agg({
            'AMOUNT_OF_KITS': 'sum',
            'POSITION': 'nunique',
            'DESCRIPTION': lambda x: '; '.join(x.dropna().unique()),
            'ERROR': lambda x: '; '.join(x.dropna().unique()) if x.notna().any() else ''
        }).rename(columns={'POSITION': 'DISTINCT_POSITIONS'})

    def _process_row_with_previous_error(
        self, row: pd.Series, file_name: str
    ) -> dict | None:
        """Procesa una fila que ya tiene un error previo. Retorna el resultado o None si no hay error."""
        previous_error = row['ERROR']
        if not (pd.notna(previous_error) and previous_error != ""):
            return None
        
        billing_row = self._build_billing_row(
            inventory_protocol=row['PROTOCOL'],
            potential_service=row['POTENTIAL_SERVICE'],
            description=row['DESCRIPTION'],
            storage_type=row['STORAGE_TYPE'],
            amount_of_kits=row['AMOUNT_OF_KITS'],
            distinct_positions=row['DISTINCT_POSITIONS'],
            error=previous_error
        )
        self._add_protocol_with_error(
            inventory_protocol=row['PROTOCOL'],
            matched_protocol=None,
            protocol_id=None,
            potential_service=row['POTENTIAL_SERVICE'],
            service_id=None,
            description=row['DESCRIPTION'],
            storage_type=row['STORAGE_TYPE'],
            amount_of_kits=row['AMOUNT_OF_KITS'],
            distinct_positions=row['DISTINCT_POSITIONS'],
            error_message=previous_error,
            file_name=file_name
        )
        return billing_row

    def _process_unmatched_protocol(
        self, row: pd.Series, file_name: str
    ) -> dict:
        """Procesa una fila cuando no se encuentra protocolo coincidente."""
        billing_row = self._build_billing_row(
            inventory_protocol=row['PROTOCOL'],
            potential_service=row['POTENTIAL_SERVICE'],
            description=row['DESCRIPTION'],
            storage_type=row['STORAGE_TYPE'],
            amount_of_kits=row['AMOUNT_OF_KITS'],
            distinct_positions=row['DISTINCT_POSITIONS'],
            error='No matching protocol found'
        )
        self._add_protocol_with_error(
            inventory_protocol=row['PROTOCOL'],
            matched_protocol=None,
            protocol_id=None,
            potential_service=row['POTENTIAL_SERVICE'],
            service_id=None,
            description=row['DESCRIPTION'],
            storage_type=row['STORAGE_TYPE'],
            amount_of_kits=row['AMOUNT_OF_KITS'],
            distinct_positions=row['DISTINCT_POSITIONS'],
            error_message='No matching protocol found',
            file_name=file_name
        )
        return billing_row

    def _process_unmatched_service(
        self,
        row: pd.Series,
        matched_protocol: str,
        protocol_id: str,
        file_name: str
    ) -> dict:
        """Procesa una fila cuando no se encuentra servicio coincidente."""
        billing_row = self._build_billing_row(
            inventory_protocol=row['PROTOCOL'],
            potential_service=row['POTENTIAL_SERVICE'],
            description=row['DESCRIPTION'],
            storage_type=row['STORAGE_TYPE'],
            amount_of_kits=row['AMOUNT_OF_KITS'],
            distinct_positions=row['DISTINCT_POSITIONS'],
            matched_protocol=matched_protocol,
            protocol_id=protocol_id,
            error='No matching service found'
        )
        self._add_protocol_with_error(
            inventory_protocol=row['PROTOCOL'],
            matched_protocol=matched_protocol,
            protocol_id=protocol_id,
            potential_service=row['POTENTIAL_SERVICE'],
            service_id=None,
            description=row['DESCRIPTION'],
            storage_type=row['STORAGE_TYPE'],
            amount_of_kits=row['AMOUNT_OF_KITS'],
            distinct_positions=row['DISTINCT_POSITIONS'],
            error_message='No matching service found',
            file_name=file_name
        )
        return billing_row

    def _process_conversion_error(
        self,
        row: pd.Series,
        matched_protocol: str,
        protocol_id: str,
        matching_service: pd.Series,
        service_position_type: str,
        error: ValueError,
        file_name: str
    ) -> dict:
        """Procesa una fila cuando hay error en la conversión de posiciones."""
        billing_row = self._build_billing_row(
            inventory_protocol=row['PROTOCOL'],
            potential_service=row['POTENTIAL_SERVICE'],
            description=row['DESCRIPTION'],
            storage_type=row['STORAGE_TYPE'],
            amount_of_kits=row['AMOUNT_OF_KITS'],
            distinct_positions=row['DISTINCT_POSITIONS'],
            matched_protocol=matched_protocol,
            protocol_id=protocol_id,
            service_id=matching_service['Service ID'],
            service_position_type=service_position_type,
            price_usd=matching_service['Price_USD'],
            error=str(error)
        )
        self._add_protocol_with_error(
            inventory_protocol=row['PROTOCOL'],
            matched_protocol=matched_protocol,
            protocol_id=protocol_id,
            potential_service=row['POTENTIAL_SERVICE'],
            service_id=matching_service['Service ID'],
            description=row['DESCRIPTION'],
            storage_type=row['STORAGE_TYPE'],
            amount_of_kits=row['AMOUNT_OF_KITS'],
            distinct_positions=row['DISTINCT_POSITIONS'],
            error_message=str(error),
            file_name=file_name
        )
        return billing_row

    def _process_successful_row(
        self,
        row: pd.Series,
        matched_protocol: str,
        protocol_id: str,
        matching_service: pd.Series,
        service_position_type: str,
        converted_positions: int
    ) -> dict:
        """Procesa una fila exitosa con todos los cálculos completados."""
        price_usd = matching_service['Price_USD']
        total_price = converted_positions * price_usd if pd.notna(price_usd) else None
        
        return self._build_billing_row(
            inventory_protocol=row['PROTOCOL'],
            potential_service=row['POTENTIAL_SERVICE'],
            description=row['DESCRIPTION'],
            storage_type=row['STORAGE_TYPE'],
            amount_of_kits=row['AMOUNT_OF_KITS'],
            distinct_positions=row['DISTINCT_POSITIONS'],
            matched_protocol=matched_protocol,
            protocol_id=protocol_id,
            service_id=matching_service['Service ID'],
            service_position_type=service_position_type,
            converted_positions=converted_positions,
            price_usd=price_usd,
            total_price=total_price
        )

    def _process_grouped_row(self, row: pd.Series, file_name: str) -> dict:
        """
        Procesa una fila agrupada del reporte de inventario.
        
        Retorna un diccionario con los datos de facturación.
        """
        if row['PROTOCOL'] == "MATERIALES":
            pass
        
        # Verificar si hay error previo
        error_row = self._process_row_with_previous_error(row, file_name)
        if error_row is not None:
            return error_row
        

        # Buscar protocolo coincidente
        matched_protocol, protocol_id = self._find_best_protocol_match(row['PROTOCOL'])
        
        if matched_protocol == "":
            return self._process_unmatched_protocol(row, file_name)
        
        # Buscar servicio coincidente
        matching_service = self._find_matching_service(matched_protocol, row['POTENTIAL_SERVICE'], row['DESCRIPTION'])
        
        if matching_service is None:
            return self._process_unmatched_service(row, matched_protocol, protocol_id, file_name)
        
        # Intentar conversión de posiciones
        service_position_type = matching_service['Position Type']
        try:
            converted_positions = self._convert_from_to(
                row['DISTINCT_POSITIONS'],
                row['STORAGE_TYPE'],
                service_position_type
            )
        except ValueError as e:
            return self._process_conversion_error(
                row, matched_protocol, protocol_id,
                matching_service, service_position_type, e, file_name
            )
        
        # Éxito: calcular precio
        return self._process_successful_row(
            row, matched_protocol, protocol_id,
            matching_service, service_position_type, converted_positions
        )

    def calculate_storage_billing(self, inventory_report_df: pd.DataFrame, file_name: str) -> pd.DataFrame:
        """
        Procesa el reporte de depósito para calcular la facturación de almacenamiento.
        
        Pasos:
        1. Agrupa los registros por PROTOCOL, POTENTIAL_SERVICE, STORAGE_TYPE
        2. Busca el protocolo más parecido en la configuración de servicios
        3. Identifica el servicio exacto y recupera el Protocol ID
        4. Aplica la matriz de conversión para transformar el tipo de storage
        5. Calcula el precio multiplicando las posiciones convertidas por Price_USD
        
        Args:
            inventory_report_df: DataFrame con el reporte de inventario
            file_name: Nombre del archivo para tracking de errores
            
        Returns:
            DataFrame con el detalle de facturación
        """
        if inventory_report_df.empty:
            return pd.DataFrame()
        
        grouped = self._group_inventory_report(inventory_report_df)
        result_rows = [
            self._process_grouped_row(row, file_name)
            for _, row in grouped.iterrows()
        ]
        
        return pd.DataFrame(result_rows)