# data_models.py
from dataclasses import dataclass
from typing import List, Optional
import uuid

@dataclass
class BusRoute:
    id: str
    stops: List[str]
    route_type: int
    client: str
    country: str
    region: Optional[str]
    language: str
    timezone: str

class Bus:
    __slots__ = ['id', 'route', 'current_stop_index', 'direction', 'system_id']
    
    def __init__(self, bus_id: str, route: BusRoute):
        self.id = bus_id
        self.route = route
        self.current_stop_index = 0
        self.direction = 1
        self.system_id = str(uuid.getnode())
    
    def set_direction(self, direction_choice: int):
        if direction_choice == 1 and self.route.route_type == 2:
            self.route.stops.reverse()
            self.direction = -1
        elif direction_choice == 1 and self.route.route_type == 1:
            print("Warning: Unidirectional route selected. Direction will remain forward.")
            self.direction = 1
        else:
            self.direction = 1
    
    def next_stop(self):
        if self.route.route_type == 1:
            self.current_stop_index = (self.current_stop_index + 1) % len(self.route.stops)
        else:
            if self.direction == 1:
                if self.current_stop_index == len(self.route.stops) - 1:
                    self.direction = -1
                    self.current_stop_index -= 1
                else:
                    self.current_stop_index += 1
            else:
                if self.current_stop_index == 0:
                    self.direction = 1
                    self.current_stop_index += 1
                else:
                    self.current_stop_index -= 1
    
    @property
    def current_stop(self) -> str:
        return self.route.stops[self.current_stop_index]
    
    @property
    def final_destination(self) -> str:
        return self.route.stops[-1] if self.direction == 1 else self.route.stops[0]