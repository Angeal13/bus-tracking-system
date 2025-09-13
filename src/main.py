# main.py
import sys
import keyboard
import time
import mariadb
from threading import Event
from datetime import datetime, date
import pytz
import uuid
import logging
import os

# Import other components
from config import COUNTRY_CODE, REGION_NAME, DB_CONFIG
from database import DatabaseConnectionPool, DatabaseOperations
from data_models import BusRoute, Bus
from audio_system import AudioSystem
from logic import StopTracker, RouteCache
from controller import StationController

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BusTrackingSystem:
    def __init__(self):
        self.controller = StationController()
        self.audio_system = AudioSystem()
        self.route_cache = RouteCache()
        self.active_bus = None
        self.bus_id = self._get_bus_id()

    def _get_bus_id(self):
        """Get a unique identifier for this bus/Raspberry Pi"""
        try:
            # Try to get the MAC address as a unique identifier
            mac = ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff) 
                           for elements in range(0, 8*6, 8)][::-1])
            return f"bus_{mac}"
        except:
            # Fallback to a random UUID if MAC address can't be retrieved
            return f"bus_{str(uuid.uuid4())[:8]}"

    def initialize_system(self):
        """System setup without user input"""
        logger.info(f"{'='*30} Bus Tracking System (Bus ID: {self.bus_id}) {'='*30}")
        
        # Register this bus with the system
        self._register_bus()
        
        # Load routes from database or cache
        routes = self.route_cache.get_routes()
        if not routes:
            raise RuntimeError(f"No routes found for {REGION_NAME}, {COUNTRY_CODE}. Check database connection and cache file.")
        
        logger.info("\nAvailable Routes:")
        for route_id, route in routes.items():
            logger.info(f"{route_id}: {route.stops[0]} → {route.stops[-1]} ({route.client})")
        
        return routes

    def _register_bus(self):
        """Register this bus with the central system"""
        try:
            db_pool = DatabaseConnectionPool()
            conn = db_pool.get_connection()
            cur = conn.cursor()
            
            # Create buses table if it doesn't exist
            create_table_query = """
            CREATE TABLE IF NOT EXISTS registered_buses (
                bus_id VARCHAR(255) PRIMARY KEY,
                ip_address VARCHAR(45),
                last_seen DATETIME,
                status VARCHAR(20) DEFAULT 'active',
                region VARCHAR(100),
                country VARCHAR(10)
            )
            """
            cur.execute(create_table_query)
            
            # Get current IP address
            try:
                import requests
                ip_address = requests.get('https://api.ipify.org').text
            except:
                ip_address = "unknown"
            
            # Insert or update bus registration
            upsert_query = """
            INSERT INTO registered_buses (bus_id, ip_address, last_seen, region, country)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE 
            ip_address = VALUES(ip_address), 
            last_seen = VALUES(last_seen),
            status = 'active'
            """
            
            cur.execute(upsert_query, (
                self.bus_id, 
                ip_address, 
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                REGION_NAME,
                COUNTRY_CODE
            ))
            
            conn.commit()
            logger.info(f"Bus registered successfully with ID: {self.bus_id}")
            
        except Exception as e:
            logger.error(f"Warning: Could not register bus with central system: {e}")
        finally:
            if 'conn' in locals():
                db_pool.release_connection(conn)

    def run_interactive_loop(self, routes):
        """Handles all user interactions"""
        while True:
            try:
                bus_route_id = self.safe_input("\nEnter Route ID (or 'q' to quit): ").strip()
                if bus_route_id.lower() == 'q':
                    break
                
                if bus_route_id not in routes:
                    print("Invalid Route ID! Try again.")
                    continue
                
                route = routes[bus_route_id]
                bus = Bus(bus_route_id, route)
                self.active_bus = bus
                
                print(f"\nSelect starting point for route {bus_route_id}:")
                print(f"0 - {bus.route.stops[0]} (forward direction)")
                if bus.route.route_type == 2:
                    print(f"1 - {bus.route.stops[-1]} (reverse direction)")
                
                direction_choice = int(self.safe_input("Choice (0/1): "))
                bus.set_direction(direction_choice)
                
                tracker = StopTracker(bus, route)
                tracker.record_stop()
                tracker.announce_stop(self.audio_system, self.controller.exit_event)
                
                self.operation_loop(tracker)
                
            except Exception as e:
                logger.error(f"Error in interactive loop: {e}")
                self.audio_system.play_audio(f"System error: {str(e)}", 'en', Event())
                time.sleep(5)

    def operation_loop(self, tracker):
        """Handles the core bus operation logic"""
        print("\nControls:")
        print("Press '0' - Advance to next stop")
        print("Press '-' - Emergency stop")
        
        while not self.controller.exit_event.is_set():
            self.controller.advance_event.clear()
            
            while not self.controller.advance_event.is_set() and not self.controller.exit_event.is_set():
                time.sleep(0.1)
            
            if self.controller.exit_event.is_set():
                break
                
            self.active_bus.next_stop()
            tracker.record_stop()
            tracker.announce_stop(self.audio_system, self.controller.exit_event)

    def safe_input(self, prompt):
        """Protected input handling with recovery"""
        try:
            return input(prompt)
        except (EOFError, KeyboardInterrupt):
            print("\nInput interrupted - please try again")
            time.sleep(1)
            return self.safe_input(prompt)

    def cleanup(self):
        """System shutdown procedure"""
        keyboard.unhook_all()
        DatabaseConnectionPool().close_all()
        self.audio_system.cleanup()
        
        # Mark bus as offline
        self._mark_bus_offline()
        
        logger.info("\nSystem shutdown complete")

    def _mark_bus_offline(self):
        """Mark this bus as offline in the database"""
        try:
            db_pool = DatabaseConnectionPool()
            conn = db_pool.get_connection()
            cur = conn.cursor()
            
            update_query = "UPDATE registered_buses SET status = 'offline' WHERE bus_id = %s"
            cur.execute(update_query, (self.bus_id,))
            
            conn.commit()
            logger.info(f"Bus marked as offline: {self.bus_id}")
            
        except Exception as e:
            logger.error(f"Warning: Could not mark bus as offline: {e}")
        finally:
            if 'conn' in locals():
                db_pool.release_connection(conn)

# Main Execution
def main():
    system = BusTrackingSystem()
    
    try:
        routes = system.initialize_system()
        system.run_interactive_loop(routes)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        system.audio_system.play_audio(f"Fatal system error: {str(e)}", 'en', Event())
    finally:
        system.cleanup()

if __name__ == "__main__":
    main()
