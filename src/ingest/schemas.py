
from pydantic import BaseModel
class Event(BaseModel):
    ts: str
    user_id: int
    trip_id: str
    vehicle_id: str
    speed: float
    accel: float
    brake: float
    lat: float
    lon: float
    geohash: str
