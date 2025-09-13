# Copy this file to config_local.py and update values for each Raspberry Pi

# Database configuration (override for each Pi if needed)
DB_CONFIG = {
    'user': "DevOps",
    'password': "DevTeam00",
    'host': "aurora-bus-system.cluster-cjaoaywuce0y.us-west-2.rds.amazonaws.com",
    'port': 3306,
    'database': "BusSystem",
}

# Audio configuration
AUDIO_CONFIG = {
    'rate': 140,
    'volume': 1.0,
    'language': 'es',
    'repeat_count': 3,
    'repeat_delay': 10
}

# System defaults - UPDATE THESE FOR EACH RASPBERRY PI
REGION_NAME = 'Rabat'  # Change based on deployment location
COUNTRY_CODE = 'MA'    # Change based on deployment country

# Device-specific settings
DEVICE_ID = "bus_001"  # Change to unique ID for each Raspberry Pi
