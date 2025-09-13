# database.py
import mariadb
import time
from datetime import datetime
from typing import Dict, List, Optional
import json
import os
import logging
from config import DB_CONFIG, COUNTRY_CODE

# Set up logging
logger = logging.getLogger(__name__)

class DatabaseConnectionPool:
    _instance = None
    _connections = []
    _max_connections = 5
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize_pool()
        return cls._instance
    
    @classmethod
    def _initialize_pool(cls):
        for _ in range(cls._max_connections):
            try:
                conn = mariadb.connect(
                    user=DB_CONFIG['user'],
                    password=DB_CONFIG['password'],
                    host=DB_CONFIG['host'],
                    port=DB_CONFIG['port'],
                    database=DB_CONFIG['database'],
                    pool_name=f"bus_pool_{len(cls._connections)}",
                    pool_size=1
                )
                cls._connections.append(conn)
            except mariadb.Error as e:
                logger.error(f"Error creating connection: {e}")
    
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

class OfflineMode:
    OFFLINE_DATA_DIR = "offline_data"
    
    def __init__(self):
        if not os.path.exists(self.OFFLINE_DATA_DIR):
            os.makedirs(self.OFFLINE_DATA_DIR)
    
    def save_last_stop(self, record: Dict):
        """Save last stop data to offline storage"""
        filename = f"last_stop_{record['ID']}.json"
        filepath = os.path.join(self.OFFLINE_DATA_DIR, filename)
        
        with open(filepath, 'w') as f:
            json.dump(record, f, default=str)
    
    def save_route_data(self, table_name: str, records: List[Dict]):
        """Save route data to offline storage"""
        filename = f"route_data_{table_name}.json"
        filepath = os.path.join(self.OFFLINE_DATA_DIR, filename)
        
        with open(filepath, 'w') as f:
            json.dump(records, f, default=str)
    
    def get_pending_data(self) -> Dict[str, List[Dict]]:
        """Get all pending data that needs to be synced"""
        pending_data = {}
        
        for filename in os.listdir(self.OFFLINE_DATA_DIR):
            if filename.startswith("route_data_"):
                filepath = os.path.join(self.OFFLINE_DATA_DIR, filename)
                with open(filepath, 'r') as f:
                    data = json.load(f)
                    table_name = filename[11:-5]  # Remove "route_data_" and ".json"
                    pending_data[table_name] = data
        
        return pending_data
    
    def clear_synced_data(self, table_name: str):
        """Remove synced data from offline storage"""
        filename = f"route_data_{table_name}.json"
        filepath = os.path.join(self.OFFLINE_DATA_DIR, filename)
        
        if os.path.exists(filepath):
            os.remove(filepath)

offline_mode = OfflineMode()

class DatabaseOperations:
    @staticmethod
    def is_connection_available():
        """Check if database connection is available"""
        try:
            db_pool = DatabaseConnectionPool()
            conn = db_pool.get_connection()
            db_pool.release_connection(conn)
            return True
        except:
            return False
    
    @staticmethod
    def get_routes() -> Dict[str, Dict]:
        """Get all routes from database"""
        if not DatabaseOperations.is_connection_available():
            logger.warning("Database connection unavailable - cannot load routes")
            return {}
            
        db_pool = DatabaseConnectionPool()
        conn = db_pool.get_connection()
        cur = conn.cursor()
        
        try:
            cur.execute("SELECT ID, PARADAS, TIPO, CLIENTE, COUNTRY, REGION, LANGUAGE, TIMEZONE FROM RUTAS")
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
            logger.error(f"Error loading routes: {e}")
            return {}
        finally:
            db_pool.release_connection(conn)
    
    @staticmethod
    def update_last_stop(record: Dict):
        """Update the last stop record in the country-specific ULTIMAS_PARADAS table with offline fallback"""
        if DatabaseOperations.is_connection_available():
            db_pool = DatabaseConnectionPool()
            conn = db_pool.get_connection()
            cur = conn.cursor()
            
            try:
                mysql_time = record['Time'].strftime('%Y-%m-%d %H:%M:%S')
                table_name = f"ULTIMAS_PARADAS_{COUNTRY_CODE}"
                
                # First check if table exists
                cur.execute(f"SHOW TABLES LIKE '{table_name}'")
                if not cur.fetchone():
                    # Table doesn't exist, create it with proper schema for country sharding
                    create_query = f"""
                    CREATE TABLE {table_name} (
                        BUSS_ID VARCHAR(255) PRIMARY KEY,
                        ID VARCHAR(255),
                        DIRECCION VARCHAR(255),
                        ESTACION VARCHAR(255),
                        TIEMPO DATETIME,
                        PARADAS TEXT,
                        CLIENTE VARCHAR(255),
                        COUNTRY VARCHAR(10),
                        REGION VARCHAR(255),
                        LANGUAGE VARCHAR(10),
                        TIMEZONE VARCHAR(50),
                        INDEX idx_buss_id (BUSS_ID),
                        INDEX idx_time (TIEMPO)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                    """
                    cur.execute(create_query)
                    logger.info(f"Created new table: {table_name}")
                    conn.commit()
                
                # Now insert/update the record
                query = f"""
                INSERT INTO {table_name} 
                (BUSS_ID, ID, DIRECCION, ESTACION, TIEMPO, PARADAS, CLIENTE, COUNTRY, REGION, LANGUAGE, TIMEZONE)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                ID=VALUES(ID), DIRECCION=VALUES(DIRECCION), ESTACION=VALUES(ESTACION), TIEMPO=VALUES(TIEMPO),
                PARADAS=VALUES(PARADAS), CLIENTE=VALUES(CLIENTE), COUNTRY=VALUES(COUNTRY), REGION=VALUES(REGION),
                LANGUAGE=VALUES(LANGUAGE), TIMEZONE=VALUES(TIMEZONE)
                """
                cur.execute(query, (
                    record['BUSS_ID'],
                    record['ID'],
                    record['Direccion'],
                    record['Current_Stop'],
                    mysql_time,
                    record['Ruta'],
                    record['Cliente'],
                    record['Country'],
                    record.get('Region'),
                    record['Language'],
                    record['Timezone']
                ))
                conn.commit()
            except Exception as e:
                logger.error(f"Database error, saving to offline storage: {e}")
                offline_mode.save_last_stop(record)
                conn.rollback()
            finally:
                db_pool.release_connection(conn)
        else:
            logger.warning("Database connection unavailable, saving to offline storage")
            offline_mode.save_last_stop(record)
    
    @staticmethod
    def save_route_data(table_name: str, records: List[Dict]):
        """Batch save all collected data to database with offline fallback"""
        if DatabaseOperations.is_connection_available():
            db_pool = DatabaseConnectionPool()
            conn = db_pool.get_connection()
            cur = conn.cursor()
            
            try:
                create_query = f"""
                CREATE TABLE IF NOT EXISTS `{table_name}` (
                    BUSS_ID VARCHAR(255),
                    ID TEXT,
                    Direccion TEXT,
                    Current_Stop TEXT,
                    Time DATETIME,
                    Ruta TEXT,
                    Cliente TEXT,
                    Country TEXT,
                    Region TEXT,
                    Language TEXT,
                    Timezone TEXT,
                    INDEX idx_buss_time (BUSS_ID, Time)
                )
                """
                cur.execute(create_query)
                
                values = []
                for record in records:
                    values.append((
                        record['BUSS_ID'],
                        record['ID'],
                        record['Direccion'],
                        record['Current_Stop'],
                        record['Time'].strftime('%Y-%m-%d %H:%M:%S'),
                        record['Ruta'],
                        record['Cliente'],
                        record['Country'],
                        record.get('Region'),
                        record['Language'],
                        record['Timezone']
                    ))
                
                if values:
                    insert_query = f"""
                    INSERT INTO `{table_name}` 
                    (BUSS_ID, ID, Direccion, Current_Stop, Time, Ruta, Cliente, Country, Region, Language, Timezone)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """
                    cur.executemany(insert_query, values)
                    conn.commit()
                    logger.info(f"Saved {len(values)} records to {table_name}")
            except Exception as e:
                logger.error(f"Database error, saving to offline storage: {e}")
                offline_mode.save_route_data(table_name, records)
                conn.rollback()
            finally:
                db_pool.release_connection(conn)
        else:
            logger.warning("Database connection unavailable, saving to offline storage")
            offline_mode.save_route_data(table_name, records)
    
    @staticmethod
    def sync_offline_data():
        """Sync all offline data when connection is restored"""
        if not DatabaseOperations.is_connection_available():
            return False
        
        pending_data = offline_mode.get_pending_data()
        if not pending_data:
            return True
        
        logger.info(f"Found {len(pending_data)} offline data files to sync")
        
        try:
            for table_name, records in pending_data.items():
                # Convert string timestamps back to datetime objects
                for record in records:
                    record['Time'] = datetime.strptime(record['Time'], '%Y-%m-%d %H:%M:%S')
                
                # Use the regular save method which will now work
                DatabaseOperations.save_route_data(table_name, records)
                offline_mode.clear_synced_data(table_name)
            
            return True
        except Exception as e:
            logger.error(f"Error syncing offline data: {e}")
            return False