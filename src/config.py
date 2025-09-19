# config.py
import os
import boto3
from botocore.exceptions import ClientError
import json

# Set up logging
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# African Regional Hubs for DynamoDB Global Tables
AFRICAN_HUBS = {
    'af-south-1': ['ZA', 'NA', 'BW', 'ZW', 'MZ', 'SZ', 'LS', 'MW'],
    'eu-west-1': ['NG', 'GH', 'CI', 'SN', 'ML', 'GN', 'BF', 'NE'],
    'me-south-1': ['EG', 'LY', 'TN', 'DZ', 'MA', 'SD', 'ER', 'DJ'],
    'eu-central-1': ['CM', 'GA', 'CG', 'CD', 'CF', 'GQ', 'AO', 'ZM']
}

# Current deployment configuration
COUNTRY_CODE = os.getenv('COUNTRY_CODE', 'NG').upper()
CURRENT_REGION = next((region for region, countries in AFRICAN_HUBS.items() 
                      if COUNTRY_CODE in countries), 'af-south-1')

# DynamoDB Configuration - Global Table with On-Demand Pricing
DYNAMODB_CONFIG = {
    'table_name': 'africa_bus_tracker_global',
    'region': CURRENT_REGION,
    'billing_mode': 'PAY_PER_REQUEST',
    'ttl_attribute': 'expiry_time',
    'batch_size': 25  # Optimal for Raspberry Pi
}

# Aurora Serverless Configuration (Reference data only)
DB_CONFIG = {
    'user': os.getenv('DB_USER', 'bus_user'),
    'password': os.getenv('DB_PASSWORD', 'secure_password_123'),
    'host': os.getenv('DB_HOST', 'bus-system-aurora.cluster-cjaoaywuce0y.us-east-1.rds.amazonaws.com'),
    'port': int(os.getenv('DB_PORT', 3306)),
    'database': os.getenv('DB_NAME', 'BusSystem'),
    'connect_timeout': 15,  # Reduced timeout for RPi
    'read_timeout': 30
}

# System defaults
REGION_NAME = os.getenv('REGION_NAME', 'WestAfrica')

# Audio configuration
AUDIO_CONFIG = {
    'rate': 140,
    'volume': 1.0,
    'language': os.getenv('AUDIO_LANGUAGE', 'en'),
    'repeat_count': 3,
    'repeat_delay': 10
}

# Raspberry Pi specific settings
PI_CONFIG = {
    'max_offline_storage': 1000,
    'health_check_interval': 300,  # 5 minutes
    'low_memory_threshold': 85,    # %
    'high_temp_threshold': 70,     # °C
    'sync_interval': 30,           # Seconds between DynamoDB syncs
    'batch_size': 25               # Records per batch
}

# AWS Services Configuration
AWS_CONFIG = {
    'max_retries': 3,
    'timeout': 15,
    'dynamo_db_region': CURRENT_REGION,
    'aurora_region': 'us-east-1'  # Cheapest region for Aurora
}
