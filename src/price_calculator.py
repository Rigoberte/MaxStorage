import pandas as pd
import math
from difflib import SequenceMatcher

class PriceCalculator:
    def __init__(self, services_df: pd.DataFrame):
        self.services_df = services_df
        self.transformation_matrix = pd.DataFrame(
            {
                "Pallet" : {"Pallet": 1.0, "Shelf": 2.0, "Bin": 8.0},
                "Shelf" : {"Pallet": 0.5, "Shelf": 1.0, "Bin": 4.0},
                "Bin" : {"Pallet": 0.125, "Shelf": 0.250, "Bin": 1.0}
            }
        )
        self.protocol_memo = {}
        self.service_memo = {}

        self.protocols_with_errors = pd.DataFrame(columns=['PROTOCOL', 'MATCHED_PROTOCOL', 'PROTOCOL_ID', 'POTENTIAL_SERVICE', 'SERVICE_ID', 'DESCRIPTION', 'STORAGE_TYPE', 'AMOUNT_OF_KITS', 'DISTINCT_POSITIONS', 'ERROR', 'FILE_NAME'])

    def _add_protocol_with_error(self, 
            inventory_protocol: str, matched_protocol: str, 
            protocol_id: str, potential_service: str, 
            service_id: str, description: str, 
            storage_type: str, amount_of_kits: int, distinct_positions: int,
            error_message: str, file_name: str):
        
        if not (
            (self.protocols_with_errors['PROTOCOL'] == inventory_protocol) & 
            (self.protocols_with_errors['POTENTIAL_SERVICE'] == potential_service) & 
            (self.protocols_with_errors['DESCRIPTION'] == description) &
            (self.protocols_with_errors['STORAGE_TYPE'] == storage_type) &
            (self.protocols_with_errors['ERROR'] == error_message)
            ).any():

            self.protocols_with_errors = pd.concat([
                self.protocols_with_errors,
                pd.DataFrame([{
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
                }])
            ], ignore_index=True)


    def _convertFromTo(self, amount_of_positions: int, from_type: str, to_type: str) -> int:
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
        
        self.protocol_memo[inventory_protocol] = (protocol_name, protocol_id)
        return (protocol_name, protocol_id)

    def _find_matching_service(self, protocol: str, potential_service: str) -> pd.Series | None:
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
        
        self.service_memo[cache_key] = best_match
        return best_match
    
    def get_error_protocols(self) -> pd.DataFrame:
        """
        Retorna una copia del DataFrame con los protocolos que tuvieron errores.
        
        Returns:
            DataFrame con los protocolos con errores
        """
        return self.protocols_with_errors.copy()

    def calculate_storage_billing(self, inventory_report_df: pd.DataFrame, file_name: str) -> pd.DataFrame:
        """
        Procesa el reporte de depósito para calcular la facturación de almacenamiento.
        
        1. Agrupa los registros por PROTOCOL, POTENTIAL_SERVICE, STORAGE_TYPE, DESCRIPTION
            sumando AMOUNT_OF_KITS y contando posiciones distintas (POSITION).
        2. Busca el protocolo más parecido en la configuración de servicios.
        3. Identifica el servicio exacto y recupera el Protocol ID.
        4. Aplica la matriz de conversión para transformar el tipo de storage.
        5. Calcula el precio multiplicando las posiciones convertidas por Price_USD.
        
        Returns:
            DataFrame con el detalle de facturación.
        """
        if inventory_report_df.empty:
            return pd.DataFrame()
        
        # Paso 1: Agrupar por PROTOCOL, POTENTIAL_SERVICE, STORAGE_TYPE, DESCRIPTION
        grouped = inventory_report_df.groupby(
            ['PROTOCOL', 'POTENTIAL_SERVICE', 'STORAGE_TYPE'], #, 'DESCRIPTION'],
            as_index=False,
            dropna=False
        ).agg({
            'AMOUNT_OF_KITS': 'sum',
            'POSITION': 'nunique',  # Count distinct positions
            'DESCRIPTION': lambda x: '; '.join(x.dropna().unique())  # Keep descriptions as a list
        }).rename(columns={'POSITION': 'DISTINCT_POSITIONS'})
        
        # Preparar columnas de resultado
        result_rows = []
        
        for _, row in grouped.iterrows():
            inventory_protocol = row['PROTOCOL']
            potential_service = row['POTENTIAL_SERVICE']
            storage_type = row['STORAGE_TYPE']
            description = row['DESCRIPTION']
            amount_of_kits = row['AMOUNT_OF_KITS']
            distinct_positions = row['DISTINCT_POSITIONS']
            
            # Paso 2: Buscar el protocolo más parecido
            matched_protocol, protocol_id = self._find_best_protocol_match(inventory_protocol)

            if matched_protocol == "":
                new_row = {
                    'PROTOCOL': inventory_protocol,
                    'MATCHED_PROTOCOL': None,
                    'PROTOCOL_ID': None,
                    'POTENTIAL_SERVICE': potential_service,
                    'SERVICE_ID': None,
                    'DESCRIPTION': description,
                    'STORAGE_TYPE': storage_type,
                    'SERVICE_POSITION_TYPE': None,
                    'AMOUNT_OF_KITS': amount_of_kits,
                    'DISTINCT_POSITIONS': distinct_positions,
                    'CONVERTED_POSITIONS': None,
                    'PRICE_USD': None,
                    'TOTAL_PRICE': None,
                    'ERROR': 'No matching protocol found'
                }
                
                result_rows.append(new_row)
                self._add_protocol_with_error(
                    inventory_protocol=inventory_protocol,
                    matched_protocol=None,
                    protocol_id=None,
                    potential_service=potential_service,
                    service_id=None,
                    description=description,
                    storage_type=storage_type,
                    amount_of_kits=amount_of_kits,
                    distinct_positions=distinct_positions,
                    error_message='No matching protocol found',
                    file_name=file_name
                )
                continue
            
            # Paso 3: Identificar el servicio exacto
            matching_service = self._find_matching_service(matched_protocol, potential_service)
            
            if matching_service is None:
                result_rows.append({
                    'PROTOCOL': inventory_protocol,
                    'MATCHED_PROTOCOL': matched_protocol,
                    'PROTOCOL_ID': protocol_id,
                    'POTENTIAL_SERVICE': potential_service,
                    'SERVICE_ID': None,
                    'DESCRIPTION': description,
                    'STORAGE_TYPE': storage_type,
                    'SERVICE_POSITION_TYPE': None,
                    'AMOUNT_OF_KITS': amount_of_kits,
                    'DISTINCT_POSITIONS': distinct_positions,
                    'CONVERTED_POSITIONS': None,
                    'PRICE_USD': None,
                    'TOTAL_PRICE': None,
                    'ERROR': 'No matching service found'
                })
                self._add_protocol_with_error(
                    inventory_protocol=inventory_protocol,
                    matched_protocol=matched_protocol,
                    protocol_id=protocol_id,
                    potential_service=potential_service,
                    service_id=None,
                    description=description,
                    storage_type=storage_type,
                    amount_of_kits=amount_of_kits,
                    distinct_positions=distinct_positions,
                    error_message='No matching service found',
                    file_name=file_name
                )
                continue
            
            # Paso 4: Aplicar matriz de conversión
            service_position_type = matching_service['Position Type']
            
            try:
                converted_positions = self._convertFromTo(
                    distinct_positions, 
                    storage_type, 
                    service_position_type
                )
            except ValueError as e:
                result_rows.append({
                    'PROTOCOL': inventory_protocol,
                    'MATCHED_PROTOCOL': matched_protocol,
                    'PROTOCOL_ID': protocol_id,
                    'POTENTIAL_SERVICE': potential_service,
                    'SERVICE_ID': matching_service['Service ID'],
                    'DESCRIPTION': description,
                    'STORAGE_TYPE': storage_type,
                    'SERVICE_POSITION_TYPE': service_position_type,
                    'AMOUNT_OF_KITS': amount_of_kits,
                    'DISTINCT_POSITIONS': distinct_positions,
                    'CONVERTED_POSITIONS': None,
                    'PRICE_USD': matching_service['Price_USD'],
                    'TOTAL_PRICE': None,
                    'ERROR': str(e)
                })
                self._add_protocol_with_error(
                    inventory_protocol=inventory_protocol,
                    matched_protocol=matched_protocol,
                    protocol_id=protocol_id,
                    potential_service=potential_service,
                    service_id=matching_service['Service ID'],
                    description=description,
                    storage_type=storage_type,
                    amount_of_kits=amount_of_kits,
                    distinct_positions=distinct_positions,
                    error_message=str(e),
                    file_name=file_name
                )
                continue
            
            # Paso 5: Calcular el precio
            price_usd = matching_service['Price_USD']
            total_price = converted_positions * price_usd if pd.notna(price_usd) else None
            
            result_rows.append({
                'PROTOCOL': inventory_protocol,
                'MATCHED_PROTOCOL': matched_protocol,
                'PROTOCOL_ID': protocol_id,
                'POTENTIAL_SERVICE': potential_service,
                'SERVICE_ID': matching_service['Service ID'],
                'DESCRIPTION': description,
                'STORAGE_TYPE': storage_type,
                'SERVICE_POSITION_TYPE': service_position_type,
                'AMOUNT_OF_KITS': amount_of_kits,
                'DISTINCT_POSITIONS': distinct_positions,
                'CONVERTED_POSITIONS': converted_positions,
                'PRICE_USD': price_usd,
                'TOTAL_PRICE': total_price,
                'ERROR': None
            })
        
        return pd.DataFrame(result_rows)