# logic.py
import json
import os
import pytz
from datetime import datetime, date
from typing import Dict
from database import DatabaseConnectionPool, DatabaseOperations
from data_models import Bus, BusRoute
from audio_system import AudioSystem
from config import COUNTRY_CODE, REGION_NAME
import mariadb
from threading import Event, Thread, Lock
import queue
import logging

# Set up logging
logger = logging.getLogger(__name__)

class StopTracker:
    _announcement_templates = {
        'es': "Ruta {route_id}, con dirección {direction}, Estación {stop_name}",
        'en': "Route {route_id}, direction {direction}, Stop {stop_name}",
        'fr': "Route {route_id}, direction {direction}, Station {stop_name}",
        'pt': "Percurso {route_id}, direção {direction}, Estação {stop_name}"
    }
    
    # A queue to store logs when the database is offline
    _offline_log_queue = queue.Queue()
    _sync_thread = None
    _is_syncing = False
    _sync_lock = Lock()

    def __init__(self, bus: Bus, route: BusRoute):
        self.bus = bus
        self.client = route.client
        self.last_update_time = datetime.now(pytz.timezone(route.timezone))
        self.table_name = f"stop_logs_{self.bus.id.replace(' ', '_')}"
        if not StopTracker._sync_thread or not StopTracker._sync_thread.is_alive():
            StopTracker._sync_thread = Thread(target=self._sync_offline_logs, daemon=True)
            StopTracker._sync_thread.start()
    
    def record_stop(self):
        """Record current stop, update last stop, and handle offline queuing."""
        now = datetime.now(pytz.timezone(self.bus.route.timezone))
        new_record = {
            'BUSS_ID': self.bus.system_id,
            'ID': self.bus.id,
            'Direccion': self.bus.final_destination,
            'Current_Stop': self.bus.current_stop,
            'Time': now,
            'Ruta': ','.join(self.bus.route.stops),
            'Cliente': self.client,
            'Country': self.bus.route.country,
            'Region': self.bus.route.region,
            'Language': self.bus.route.language,
            'Timezone': self.bus.route.timezone
        }
        self.last_update_time = now
        
        try:
            self._insert_log_record(new_record)
            self._update_last_stop(new_record)
            
            # If we were previously offline, try to sync now
            if StopTracker._offline_log_queue.qsize() > 0:
                logger.info("Connection restored. Attempting to sync offline logs...")
                self._sync_offline_logs()
        except mariadb.Error as e:
            logger.error(f"Database connection lost: {e}. Switching to offline mode.")
            logger.info("Stop log queued locally.")
            StopTracker._offline_log_queue.put(new_record)

    def _insert_log_record(self, record: Dict):
        """Inserts a single log record into the daily log table."""
        db_pool = DatabaseConnectionPool()
        conn = db_pool.get_connection()
        cur = conn.cursor()
        
        table_name_daily = f"stop_logs_{record['ID'].replace(' ', '_')}_{date.today().isoformat().replace('-', '_')}"

        try:
            create_query = f"""
            CREATE TABLE IF NOT EXISTS {table_name_daily} (
                ID INT AUTO_INCREMENT PRIMARY KEY, BUSS_ID TEXT, Bus_Number TEXT, Direccion TEXT,
                Current_Stop TEXT, Time DATETIME, Ruta TEXT, Cliente TEXT, Country TEXT,
                Region TEXT, Language TEXT, Timezone TEXT, INDEX idx_buss_time (BUSS_ID(100), Time)
            )
            """
            cur.execute(create_query)
            
            insert_query = f"""
            INSERT INTO {table_name_daily} 
            (BUSS_ID, Bus_Number, Direccion, Current_Stop, Time, Ruta, Cliente, Country, Region, Language, Timezone)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            cur.execute(insert_query, (
                record['BUSS_ID'], record['ID'], record['Direccion'], record['Current_Stop'],
                record['Time'], record['Ruta'], record['Cliente'],
                record['Country'], record['Region'], record['Language'], record['Timezone']
            ))
            conn.commit()
            logger.info(f"Logged stop to {table_name_daily}")
        finally:
            db_pool.release_connection(conn)

    def _update_last_stop(self, record: Dict):
        """Update the last stop record in the country-specific ULTIMAS_PARADAS table."""
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
                record['BUSS_ID'], record['ID'], record['Direccion'], record['Current_Stop'],
                mysql_time, record['Ruta'], record['Cliente'], COUNTRY_CODE,
                REGION_NAME, record['Language'], record['Timezone']
            ))
            conn.commit()
            logger.info(f"Updated record in {table_name}")
            
        except mariadb.Error as e:
            conn.rollback()
            raise  # Re-raise the exception after logging
        finally:
            db_pool.release_connection(conn)

    def announce_stop(self, audio_system: AudioSystem, exit_event: Event):
        """Announce current stop information based on the route's language setting."""
        lang = self.bus.route.language or 'es'

        template = self._announcement_templates.get(lang, self._announcement_templates['es'])

        announcement = template.format(
            route_id=self.bus.id,
            direction=self.bus.final_destination,
            stop_name=self.bus.current_stop
        )

        logger.info(announcement)
        audio_system.play_audio(announcement, lang, exit_event, repetitions=3)
    
    @staticmethod
    def _sync_offline_logs():
        """Attempts to sync queued logs with the database."""
        with StopTracker._sync_lock:
            if StopTracker._is_syncing:
                return
            StopTracker._is_syncing = True
        
        logger.info("Starting offline log sync...")
        temp_queue = queue.Queue()
        while not StopTracker._offline_log_queue.empty():
            temp_queue.put(StopTracker._offline_log_queue.get())

        while not temp_queue.empty():
            record = temp_queue.get()
            try:
                # Create a minimal route object for the tracker
                route_data = {
                    'id': record['ID'],
                    'stops': record['Ruta'].split(','),
                    'route_type': 1,
                    'client': record['Cliente'],
                    'country': record['Country'],
                    'region': record.get('Region', ''),
                    'language': record['Language'],
                    'timezone': record['Timezone']
                }
                route = BusRoute(**route_data)
                bus = Bus(record['ID'], route)
                tracker = StopTracker(bus, route)
                tracker._insert_log_record(record)
                tracker._update_last_stop(record)
            except mariadb.Error as e:
                logger.error(f"Sync failed. Re-queuing logs. Error: {e}")
                StopTracker._offline_log_queue.put(record)
                while not temp_queue.empty():
                    StopTracker._offline_log_queue.put(temp_queue.get())
                break
        
        with StopTracker._sync_lock:
            StopTracker._is_syncing = False
        logger.info("Offline log sync complete.")

class RouteCache:
    _instance = None
    _routes = None
    _last_update = None
    _cache_file = 'routes_cache.json'
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def get_routes(self, force_refresh=False) -> Dict[str, BusRoute]:
        if self._routes is None or force_refresh or (
            self._last_update and (datetime.now() - self._last_update).total_seconds() > 3600
        ):
            self._load_routes()
        return self._routes
    
    def _load_routes(self):
        try:
            db_pool = DatabaseConnectionPool()
            conn = db_pool.get_connection()
            cur = conn.cursor()
            
            if not COUNTRY_CODE or not REGION_NAME:
                raise ValueError("COUNTRY_CODE and REGION_NAME must be set in config.py.")

            query = "SELECT ID, PARADAS, TIPO, CLIENTE, LANGUAGE, TIMEZONE FROM RUTAS WHERE COUNTRY = ? AND REGION = ?"
            cur.execute(query, (COUNTRY_CODE, REGION_NAME))
            rows = cur.fetchall()
            
            self._routes = {}
            for row in rows:
                route_id, stops, route_type, client, language, timezone = row
                self._routes[route_id] = BusRoute(
                    id=route_id,
                    stops=stops.split(','),
                    route_type=route_type,
                    client=client,
                    country=COUNTRY_CODE,
                    region=REGION_NAME,
                    language=language,
                    timezone=timezone
                )
            
            self._save_routes_to_cache()
            self._last_update = datetime.now()
            logger.info(f"Loaded {len(self._routes)} routes from database for {REGION_NAME}, {COUNTRY_CODE}.")
        except (mariadb.Error, ValueError) as e:
            logger.error(f"Error loading routes from database: {e}. Attempting to load from cache.")
            self._load_routes_from_cache()
        finally:
            if 'conn' in locals() and conn:
                db_pool.release_connection(conn)

    def _save_routes_to_cache(self):
        """Saves the current routes to a local JSON file."""
        try:
            with open(self._cache_file, 'w') as f:
                serializable_routes = {
                    route_id: {
                        'id': route.id,
                        'stops': route.stops,
                        'route_type': route.route_type,
                        'client': route.client,
                        'country': route.country,
                        'region': route.region,
                        'language': route.language,
                        'timezone': route.timezone
                    } for route_id, route in self._routes.items()
                }
                json.dump(serializable_routes, f, indent=4)
            logger.info(f"Routes saved to local cache: {self._cache_file}")
        except Exception as e:
            logger.error(f"Error saving routes to cache: {e}")

    def _load_routes_from_cache(self):
        """Loads routes from the local JSON file."""
        if os.path.exists(self._cache_file):
            try:
                with open(self._cache_file, 'r') as f:
                    cached_data = json.load(f)
                    self._routes = {
                        route_id: BusRoute(
                            id=data['id'],
                            stops=data['stops'],
                            route_type=data['route_type'],
                            client=data['client'],
                            country=data['country'],
                            region=data['region'],
                            language=data['language'],
                            timezone=data['timezone']
                        ) for route_id, data in cached_data.items()
                    }
                logger.info(f"Loaded {len(self._routes)} routes from local cache.")
                self._last_update = datetime.now()
            except Exception as e:
                logger.error(f"Error loading routes from cache: {e}. No routes available.")
                self._routes = {}
        else:
            logger.info("Local cache file not found. No routes available.")
            self._routes = {}