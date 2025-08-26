"""
Constants for AWS Pricing MCP Server
"""

import os

# Logging configuration
LOG_LEVEL = os.getenv('FASTMCP_LOG_LEVEL', 'ERROR')

# AWS Configuration
DEFAULT_AWS_REGION = os.getenv('AWS_REGION', 'us-west-2')
DEFAULT_AWS_PROFILE = os.getenv('AWS_PROFILE', 'default')

# Pricing API Configuration
DEFAULT_MAX_RESULTS = 100
DEFAULT_MAX_ALLOWED_CHARACTERS = 100000

# Currency mapping for regions
REGION_CURRENCY_MAP = {
    'us-east-1': 'USD',
    'us-east-2': 'USD',
    'us-west-1': 'USD',
    'us-west-2': 'USD',
    'ca-central-1': 'USD',
    'eu-west-1': 'USD',
    'eu-west-2': 'USD',
    'eu-west-3': 'USD',
    'eu-central-1': 'USD',
    'eu-north-1': 'USD',
    'ap-northeast-1': 'USD',
    'ap-northeast-2': 'USD',
    'ap-southeast-1': 'USD',
    'ap-southeast-2': 'USD',
    'ap-south-1': 'USD',
    'sa-east-1': 'USD',
    'af-south-1': 'USD',
    'me-south-1': 'USD',
    'ap-east-1': 'USD',
    'eu-south-1': 'USD',
}

# Default currency
DEFAULT_CURRENCY = 'USD'
