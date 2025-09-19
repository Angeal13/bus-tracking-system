# database.py
import mariadb
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import json
import os
import logging
import boto3
from botocore.exceptions import ClientError, ConnectionError
from config import DB_CONFIG, COUNTRY_CODE, DYNAMODB_CONFIG, CURRENT_REGION, PI_CONFIG, AWS_CONFIG

logger = logging.getLogger(__name__)

class PiOptimizedDynamoDBManager:
    _instance = None
    _last_sync_time = 0
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        try:
            # Raspberry Pi optimized configuration with reduced timeouts
            session = boto3.Session(
                region_name=DYNAMODB_CONFIG['region'],
                config=boto3.session.Config(
                    connect_timeout=AWS_CONFIG['timeout'],
                    read_timeout=AWS_CONFIG['timeout'],
                    retries={'max_attempts': AWS_CONFIG['max_retries']}
                )
            )
            self.client = session.client('dynamodb')
            self.resource = session.resource('dynamodb')
            self.table = self.resource.Table(DYNAMODB_CONFIG['table_name'])
            logger.info(f"DynamoDB connected from Raspberry Pi in {DYNAMODB_CONFIG['region']}")
        except Exception as e:
            logger.error(f"DynamoDB init failed: {e}")
            self.client = None
            self.table = None
    
    def should_sync(self):
        """Check if it's time to sync based on interval"""
        current_time = time.time()
        return current_time - self._last_sync_time >= PI_CONFIG['sync_interval']
    
    def update_sync_time(self):
        """Update last sync time"""
        self._last_sync_time = time.time()

dynamo_manager = PiOptimizedDynamoDBManager()

class OfflineMode:
    OFFLINE_DATA_DIR = "offline_data"
    _current_size = 0
    
    def __init__(self):
        if not os.path.exists(self.OFFLINE_DATA_DIR):
            os.makedirs(self.OFFLINE_DATA_DIR)
        self._current_size = self._count_offline_files()
    
    def _count_offline_files(self):
        try:
            return len([f for f in os.listdir(self.OFFLINE_DATA_DIR) if f.endswith('.json')])
        except:
            return 0
    
    def save_last_stop(self, record: Dict):
        if self._current_size >= PI_CONFIG['max_offline_storage']:
            self._cleanup_oldest_files()
            
        filename = f"last_stop_{record['BUSS_ID']}.json"
        filepath = os.path.join(self.OFFLINE_DATA_DIR, filename)
        
        try:
            with open(filepath, 'w') as f:
                json.dump(record, f, default=str, separators=(',', ':'))
            self._current_size += 1
        except Exception as e:
            logger.error(f"Failed to save offline data: {e}")
    
    def save_route_data(self, table_name: str, records: List[Dict]):
        if self._current_size >= PI_CONFIG['max_offline_storage']:
            self._cleanup_oldest_files()
            
        filename = f"route_data_{table_name}.json"
        filepath = os.path.join(self.OFFLINE_DATA_DIR, filename)
        
        try:
            with open(filepath, 'w') as f:
                json.dump(records, f, default=str, separators=(',', ':'))
            self._current_size += 1
        except Exception as e:
            logger.error(f"Failed to save offline route data: {e}")
    
    def get_pending_data(self) -> Dict[str, List[Dict]]:
        pending_data = {}
        try:
            for filename in os.listdir(self.OFFLINE_DATA_DIR):
                if filename.startswith("route_data_") and filename.endswith(".json"):
                    filepath = os.path.join(self.OFFLINE_DATA_DIR, filename)
                    with open(filepath, 'r') as f:
                        data = json.load(f)
                        table_name = filename[11:-5]
                        pending_data[table_name] = data
        except Exception as e:
            logger.error(f"Error reading offline data: {e}")
        return pending_data
    
    def clear_synced_data(self, table_name: str):
        filename = f"route_data_{table_name}.json"
        filepath = os.path.join(self.OFFLINE_DATA_DIR, filename)
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
                self._current_size -= 1
            except Exception as e:
                logger.error(f"Error removing synced data: {e}")
    
    def _cleanup_oldest_files(self):
        try:
            files = []
            for filename in os.listdir(self.OFFLINE_DATA_DIR):
                if filename.endswith('.json'):
                    filepath = os.path.join(self.OFFLINE_DATA_DIR, filename)
                    files.append((filepath, os.path.getmtime(filepath)))
            
            files.sort(key=lambda x: x[1])
            
            while self._current_size > PI_CONFIG['max_offline_storage'] * 0.8 and files:
                oldest_file, _ = files.pop(0)
                os.remove(oldest_file)
                self._current_size -= 1
                
        except Exception as e:
            logger.error(f"Error cleaning up offline storage: {e}")

offline_mode = OfflineMode()

class DatabaseConnectionPool:
    _instance = None
    _connections = []
    _max_connections = 2  # Reduced for Raspberry Pi and Aurora Serverless
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize_pool()
        return cls._instance
    
    def _initialize_pool(cls):
        for _ in range(cls._max_connections):
            try:
                conn = mariadb.connect(**DB_CONFIG)
                cls._connections.append(conn)
            except mariadb.Error as e:
                logger.error(f"Error creating Aurora connection: {e}")
    
    def get_connection(self):
        while not self._connections:
            time.sleep(0.1)
        return self._connections.pop()
    
    def release_connection(self, conn):
        self._connections.append(conn)
    
    def close_all(self):
        for conn in self._connections:
            conn.close()
        self._connections = []

class DatabaseOperations:
    @staticmethod
    def is_connection_available():
        return dynamo_manager.client is not None and dynamo_manager.table is not None
    
    @staticmethod
    def _convert_to_dynamo_item(record: Dict) -> Dict:
        time_str = record['Time'].isoformat() if hasattr(record['Time'], 'isoformat') else str(record['Time'])
        expiry_time = int(time.time()) + 2592000  # 30 days TTL
        
        return {
            'PK': {'S': f"BUS#{record['BUSS_ID']}"},
            'SK': {'S': 'CURRENT_STATUS'},
            'GSI1PK': {'S': f"COUNTRY#{record['Country']}"},
            'GSI1SK': {'S': f"TIME#{time_str}"},
            'BUSS_ID': {'S': record['BUSS_ID']},
            'ID': {'S': record['ID']},
            'Direccion': {'S': record['Direccion']},
            'Current_Stop': {'S': record['Current_Stop']},
            'Time': {'S': time_str},
            'Ruta': {'S': record['Ruta']},
            'Cliente': {'S': record['Cliente']},
            'Country': {'S': record['Country']},
            'Region': {'S': record.get('Region', 'Unknown')},
            'Language': {'S': record['Language']},
            'Timezone': {'S': record['Timezone']},
            'expiry_time': {'N': str(expiry_time)}  # TTL for automatic cleanup
        }
    
    @staticmethod
    def update_last_stop(record: Dict):
        """Update last stop with efficient DynamoDB writes"""
        if DatabaseOperations.is_connection_available():
            try:
                item = DatabaseOperations._convert_to_dynamo_item(record)
                dynamo_manager.client.put_item(
                    TableName=DYNAMODB_CONFIG['table_name'],
                    Item=item
                )
                logger.info(f"Updated last stop for bus {record['BUSS_ID']} in DynamoDB")
            except Exception as e:
                logger.error(f"DynamoDB error: {e}")
                offline_mode.save_last_stop(record)
        else:
            logger.warning("DynamoDB connection unavailable, saving to offline storage")
            offline_mode.save_last_stop(record)
    
    @staticmethod
    def save_route_data(table_name: str, records: List[Dict]):
        """Batch save with optimized DynamoDB writes"""
        if DatabaseOperations.is_connection_available() and records:
            try:
                # Batch write in optimized chunks for Raspberry Pi
                batch_size = PI_CONFIG['batch_size']
                for i in range(0, len(records), batch_size):
                    batch = records[i:i + batch_size]
                    
                    with dynamo_manager.table.batch_writer() as writer:
                        for record in batch:
                            item = DatabaseOperations._convert_to_dynamo_item(record)
                            writer.put_item(Item=item)
                    
                    logger.info(f"Saved batch of {len(batch)} records to DynamoDB")
                    time.sleep(0.1)  # Small delay to prevent overwhelming RPi
                
            except Exception as e:
                logger.error(f"DynamoDB batch error: {e}")
                offline_mode.save_route_data(table_name, records)
        else:
            logger.warning("DynamoDB connection unavailable, saving to offline storage")
            offline_mode.save_route_data(table_name, records)
    
    @staticmethod
    def get_routes() -> Dict[str, Dict]:
        """Get routes from Aurora (reference data only)"""
        db_pool = DatabaseConnectionPool()
        conn = db_pool.get_connection()
        cur = conn.cursor()
        
        try:
            cur.execute("""
                SELECT ID, PARADAS, TIPO, CLIENTE, COUNTRY, REGION, LANGUAGE, TIMEZONE 
                FROM RUTAS 
                WHERE COUNTRY = ? AND REGION = ?
            """, (COUNTRY_CODE, REGION_NAME))
            
            rows = cur.fetchall()
            routes = {}
            
            for row in rows:
                route_id, stops, route_type, client, country, region, language, timezone = row
                routes[route_id] = {
                    'stops': stops.split(','),
                    'route_type': route_type,
                    'client': client,
                    'country': country,
                    'region': region,
                    'language': language,
                    'timezone': timezone
                }
            
            return routes
            
        except Exception as e:
            logger.error(f"Error loading routes from Aurora: {e}")
            return {}
        finally:
            db_pool.release_connection(conn)
    
    @staticmethod
    def sync_offline_data():
        """Sync offline data when connection is available"""
        if not DatabaseOperations.is_connection_available():
            return False
        
        pending_data = offline_mode.get_pending_data()
        if not pending_data:
            return True
        
        logger.info(f"Found {len(pending_data)} offline data files to sync")
        
        try:
            for table_name, records in pending_data.items():
                # Convert string times back to datetime objects
                for record in records:
                    if isinstance(record['Time'], str):
                        record['Time'] = datetime.fromisoformat(record['Time'].replace('Z', '+00:00'))
                
                DatabaseOperations.save_route_data(table_name, records)
                offline_mode.clear_synced_data(table_name)
            
            return True
        except Exception as e:
            logger.error(f"Error syncing offline data: {e}")
            return False
    
    @staticmethod
    def get_bus_status(bus_id: str):
        """Get latest bus status from DynamoDB"""
        if not DatabaseOperations.is_connection_available():
            return None
        
        try:
            response = dynamo_manager.client.query(
                TableName=DYNAMODB_CONFIG['table_name'],
                KeyConditionExpression='PK = :pk AND SK = :sk',
                ExpressionAttributeValues={
                    ':pk': {'S': f"BUS#{bus_id}"},
                    ':sk': {'S': 'CURRENT_STATUS'}
                },
                Limit=1,
                ScanIndexForward=False  # Get most recent
            )
            
            if response.get('Items'):
                return response['Items'][0]
            return None
            
        except Exception as e:
            logger.error(f"Bus status query failed: {e}")
            return None
    
    @staticmethod
    def get_country_buses(country_code: str):
        """Get all active buses in a country from DynamoDB"""
        if not DatabaseOperations.is_connection_available():
            return []
        
        try:
            response = dynamo_manager.client.query(
                TableName=DYNAMODB_CONFIG['table_name'],
                IndexName='GSI1',
                KeyConditionExpression='GSI1PK = :country',
                ExpressionAttributeValues={
                    ':country': {'S': f"COUNTRY#{country_code}"}
                },
                Limit=100  # Reasonable limit for dashboard
            )
            return response.get('Items', [])
        except Exception as e:
            logger.error(f"Country query failed: {e}")
            return []
