# config.py
import boto3
import json
import logging
from botocore.exceptions import ClientError

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_secret():
    """Get database credentials from AWS Secrets Manager"""
    try:
        secrets_client = boto3.client('secretsmanager', region_name='us-west-2')
        secret_value = secrets_client.get_secret_value(SecretId='bus-system-aurora-credentials')
        secret = json.loads(secret_value['SecretString'])
        return secret
    except Exception as e:
        logger.error(f"Error getting database credentials: {e}")
        return None

def get_ssm_parameter(name):
    """Get parameter from AWS Systems Manager Parameter Store"""
    try:
        ssm = boto3.client('ssm', region_name='us-east-1')
        parameter = ssm.get_parameter(Name=name, WithDecryption=True)
        return parameter['Parameter']['Value']
    except Exception as e:
        logger.error(f"Error getting parameter {name}: {e}")
        return None

# Get configuration from AWS
db_creds = get_secret()
db_host = get_ssm_parameter('/bus-system/aurora/host')
db_name = get_ssm_parameter('/bus-system/aurora/dbname')

if db_creds and db_host and db_name:
    DB_CONFIG = {
        'user': db_creds['username'],
        'password': db_creds['password'],
        'host': db_host,
        'port': 3306,
        'database': db_name,
        'pool_size': 5
    }
else:
    # Fallback configuration
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

# System defaults
REGION_NAME = 'Rabat'
COUNTRY_CODE = 'MA'