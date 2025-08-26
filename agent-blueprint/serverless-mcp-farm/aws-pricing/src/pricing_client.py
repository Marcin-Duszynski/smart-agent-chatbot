"""
AWS Pricing API client for AWS Pricing MCP Server
"""

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from consts import DEFAULT_AWS_REGION, DEFAULT_CURRENCY, REGION_CURRENCY_MAP
from loguru import logger
from typing import Optional


def create_pricing_client():
    """Create and return an AWS Pricing client.
    
    Returns:
        boto3.client: AWS Pricing client
        
    Raises:
        Exception: If client creation fails
    """
    try:
        # Create pricing client - always use us-east-1 for pricing API
        client = boto3.client('pricing', region_name='us-east-1')
        
        # Test the client with a simple call
        client.describe_services(MaxResults=1)
        
        logger.info("Successfully created AWS Pricing client")
        return client
        
    except NoCredentialsError:
        logger.error("AWS credentials not found")
        raise Exception("AWS credentials not found. Please configure AWS credentials.")
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_message = e.response['Error']['Message']
        logger.error(f"AWS client error: {error_code} - {error_message}")
        
        if error_code == 'UnauthorizedOperation':
            raise Exception("Access denied. Please ensure your AWS credentials have pricing:* permissions.")
        else:
            raise Exception(f"AWS API error: {error_code} - {error_message}")
            
    except Exception as e:
        logger.error(f"Failed to create AWS Pricing client: {str(e)}")
        raise Exception(f"Failed to create AWS Pricing client: {str(e)}")


def get_currency_for_region(region: str) -> str:
    """Get the currency code for a given AWS region.
    
    Args:
        region: AWS region code
        
    Returns:
        str: Currency code (e.g., 'USD')
    """
    return REGION_CURRENCY_MAP.get(region, DEFAULT_CURRENCY)
