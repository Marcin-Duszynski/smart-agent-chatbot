#!/usr/bin/env python3
"""
AWS Pricing MCP Server for Lambda deployment using awslabs-mcp-lambda-handler
"""

import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from awslabs.mcp_lambda_handler import MCPLambdaHandler
from loguru import logger
from pydantic import Field

from consts import LOG_LEVEL
from models import (
    ATTRIBUTE_NAMES_FIELD,
    EFFECTIVE_DATE_FIELD,
    FILTERS_FIELD,
    GET_PRICING_MAX_ALLOWED_CHARACTERS_FIELD,
    MAX_RESULTS_FIELD,
    NEXT_TOKEN_FIELD,
    OUTPUT_OPTIONS_FIELD,
    REGION_FIELD,
    SERVICE_CODE_FIELD,
    ErrorResponse,
    OutputOptions,
    PricingFilter,
)
from pricing_client import create_pricing_client, get_currency_for_region
from pricing_transformer import transform_pricing_data
from report_generator import generate_cost_report
from static_data import BEDROCK_PATTERNS

# Logging configuration
logging.basicConfig(level=logging.INFO)
logger_std = logging.getLogger(__name__)

# Set up loguru logging
logger.remove()
logger.add(sys.stderr, level=LOG_LEVEL)

# Create MCP Lambda handler
mcp = MCPLambdaHandler(name="aws-pricing", version="1.0.0")


def create_error_response(
    error_type: str,
    message: str,
    **kwargs,  # Accept any additional fields dynamically
) -> Dict[str, Any]:
    """Create a standardized error response and log it."""
    logger.error(message)
    
    # Create error response dictionary directly
    error_response = {
        'error_type': error_type,
        'message': message,
        **kwargs,
    }
    
    return error_response


@mcp.tool()
def get_pricing_service_codes() -> Union[List[str], Dict[str, Any]]:
    """Get AWS service codes available in the Price List API.

    **PURPOSE:** Discover which AWS services have pricing information available in the AWS Price List API.

    **WORKFLOW:** This is the starting point for any pricing query. Use this first to find the correct service code.

    **RETURNS:** List of service codes (e.g., 'AmazonEC2', 'AmazonS3', 'AWSLambda') that can be used with other pricing tools.

    **NEXT STEPS:**
    - Use get_pricing_service_attributes() to see what filters are available for a service
    - Use get_pricing() to get actual pricing data for a service

    **NOTE:** Service codes may differ from AWS console names (e.g., 'AmazonES' for OpenSearch, 'AWSLambda' for Lambda).
    """
    logger.info('Retrieving AWS service codes from Price List API')

    # Create pricing client with error handling
    try:
        pricing_client = create_pricing_client()
    except Exception as e:
        return create_error_response(
            error_type='client_creation_failed',
            message=f'Failed to create AWS Pricing client: {str(e)}',
        )

    # Retrieve service codes with error handling
    try:
        service_codes = []
        next_token = None

        # Retrieve all service codes with pagination handling
        while True:
            if next_token:
                response = pricing_client.describe_services(NextToken=next_token)
            else:
                response = pricing_client.describe_services()

            for service in response['Services']:
                service_codes.append(service['ServiceCode'])

            if 'NextToken' in response:
                next_token = response['NextToken']
            else:
                break

    except Exception as e:
        return create_error_response(
            error_type='api_error',
            message=f'Failed to retrieve service codes from AWS API: {str(e)}',
            suggestion='Verify AWS credentials and permissions for pricing:DescribeServices action.',
        )

    # Check for empty results
    if not service_codes:
        return create_error_response(
            error_type='empty_results',
            message='No service codes returned from AWS Price List API',
        )

    sorted_codes = sorted(service_codes)

    logger.info(f'Successfully retrieved {len(sorted_codes)} service codes')

    return sorted_codes


@mcp.tool()
def get_pricing_service_attributes(
    service_code: str = SERVICE_CODE_FIELD
) -> Union[List[str], Dict[str, Any]]:
    """Get filterable attributes available for an AWS service in the Pricing API.

    **PURPOSE:** Discover what pricing dimensions (filters) are available for a specific AWS service.

    **WORKFLOW:** Use this after get_pricing_service_codes() to see what filters you can apply to narrow down pricing queries.

    **REQUIRES:** Service code from get_pricing_service_codes() (e.g., 'AmazonEC2', 'AmazonRDS').

    **RETURNS:** List of attribute names (e.g., 'instanceType', 'location', 'storageClass') that can be used as filters.

    **NEXT STEPS:**
    - Use get_pricing_attribute_values() to see valid values for each attribute
    - Use these attributes in get_pricing() filters to get specific pricing data

    **EXAMPLE:** For 'AmazonRDS' you might get ['engineCode', 'instanceType', 'deploymentOption', 'location'].
    """
    logger.info(f'Retrieving attributes for AWS service: {service_code}')

    # Create pricing client with error handling
    try:
        pricing_client = create_pricing_client()
    except Exception as e:
        return create_error_response(
            error_type='client_creation_failed',
            message=f'Failed to create AWS Pricing client: {str(e)}',
            service_code=service_code,
        )

    # Get service attributes with error handling
    try:
        response = pricing_client.describe_services(ServiceCode=service_code)
    except Exception as e:
        return create_error_response(
            error_type='api_error',
            message=f'Failed to retrieve attributes for service "{service_code}": {str(e)}',
            service_code=service_code,
            suggestion='Verify that the service code is valid and AWS credentials have the required pricing:DescribeServices permissions. Use get_pricing_service_codes() to get valid service codes.',
        )

    # Check if service was found
    if not response.get('Services'):
        return create_error_response(
            error_type='service_not_found',
            message=f'Service "{service_code}" was not found. Please verify the service code is correct.',
            service_code=service_code,
            suggestion='Use get_pricing_service_codes() to retrieve a list of all available AWS service codes.',
            examples={
                'OpenSearch': 'AmazonES',
                'Lambda': 'AWSLambda',
                'DynamoDB': 'AmazonDynamoDB',
                'EC2': 'AmazonEC2',
                'S3': 'AmazonS3',
            },
        )

    # Extract attribute names
    attributes = []
    for attr in response['Services'][0].get('AttributeNames', []):
        attributes.append(attr)

    # Check for empty results
    if not attributes:
        return create_error_response(
            error_type='empty_results',
            message=f'Service "{service_code}" exists but has no filterable attributes available.',
            service_code=service_code,
            suggestion='This service may not support attribute-based filtering, or there may be a temporary issue. Try using get_pricing() without filters.',
        )

    sorted_attributes = sorted(attributes)

    logger.info(f'Successfully retrieved {len(sorted_attributes)} attributes for {service_code}')

    return sorted_attributes


@mcp.tool()
def get_pricing_attribute_values(
    service_code: str = SERVICE_CODE_FIELD,
    attribute_names: List[str] = ATTRIBUTE_NAMES_FIELD,
) -> Union[Dict[str, List[str]], Dict[str, Any]]:
    """Get valid values for pricing filter attributes.

    **PURPOSE:** Discover what values are available for specific pricing filter attributes of an AWS service.

    **WORKFLOW:** Use this after get_pricing_service_attributes() to see valid values for each filter attribute.

    **REQUIRES:**
    - Service code from get_pricing_service_codes() (e.g., 'AmazonEC2', 'AmazonRDS')
    - List of attribute names from get_pricing_service_attributes() (e.g., ['instanceType', 'location'])

    **RETURNS:** Dictionary mapping attribute names to their valid values.

    **EXAMPLE RETURN:**
    ```
    {
        'instanceType': ['t2.micro', 't3.medium', 'm5.large', ...],
        'location': ['US East (N. Virginia)', 'EU (London)', ...]
    }
    ```

    **NEXT STEPS:** Use these values in get_pricing() filters to get specific pricing data.

    **ERROR HANDLING:** Uses "all-or-nothing" approach - if any attribute fails, the entire operation fails.

    **EXAMPLES:**
    - Single attribute: ['instanceType'] returns {'instanceType': ['t2.micro', 't3.medium', ...]}
    - Multiple attributes: ['instanceType', 'location'] returns both mappings
    """
    if not attribute_names:
        return create_error_response(
            error_type='empty_attribute_list',
            message='No attribute names provided. Please provide at least one attribute name.',
            service_code=service_code,
            attribute_names=attribute_names,
            suggestion='Use get_pricing_service_attributes() to get valid attribute names for this service.',
        )

    logger.info(
        f'Retrieving values for {len(attribute_names)} attributes of service: {service_code}'
    )

    # Create pricing client with error handling
    try:
        pricing_client = create_pricing_client()
    except Exception as e:
        return create_error_response(
            error_type='client_creation_failed',
            message=f'Failed to create AWS Pricing client: {str(e)}',
            service_code=service_code,
            attribute_names=attribute_names,
        )

    # Process each attribute - all-or-nothing approach
    result = {}
    for attribute_name in attribute_names:
        logger.debug(f'Processing attribute: {attribute_name}')

        try:
            # Get attribute values with pagination handling
            values = []
            next_token = None

            while True:
                if next_token:
                    response = pricing_client.get_attribute_values(
                        ServiceCode=service_code, AttributeName=attribute_name, NextToken=next_token
                    )
                else:
                    response = pricing_client.get_attribute_values(
                        ServiceCode=service_code, AttributeName=attribute_name
                    )

                for attr_value in response.get('AttributeValues', []):
                    if 'Value' in attr_value:
                        values.append(attr_value['Value'])

                if 'NextToken' in response:
                    next_token = response['NextToken']
                else:
                    break

            # Check if no values were found
            if not values:
                return create_error_response(
                    error_type='no_attribute_values_found',
                    message=f'No values found for attribute "{attribute_name}" of service "{service_code}". This could be due to an invalid service code or an invalid attribute name for this service.',
                    service_code=service_code,
                    attribute_name=attribute_name,
                    failed_attribute=attribute_name,
                    requested_attributes=attribute_names,
                    suggestion='Use get_pricing_service_codes() to verify the service code and get_pricing_service_attributes() to verify the attribute name for this service.',
                    examples={
                        'Common service codes': ['AmazonEC2', 'AmazonS3', 'AmazonES', 'AWSLambda'],
                        'Common attributes': [
                            'instanceType',
                            'location',
                            'storageClass',
                            'engineCode',
                        ],
                    },
                )

            # Success - add to result
            result[attribute_name] = sorted(values)

        except Exception as e:
            # If any attribute fails, return error for entire operation
            return create_error_response(
                error_type='api_error',
                message=f'Failed to retrieve values for attribute "{attribute_name}": {str(e)}',
                service_code=service_code,
                attribute_name=attribute_name,
                failed_attribute=attribute_name,
                requested_attributes=attribute_names,
                suggestion='Verify that both the service code and attribute name are valid. Use get_pricing_service_codes() to get valid service codes and get_pricing_service_attributes() to get valid attributes for a service.',
            )

    total_values = sum(len(values) for values in result.values())
    logger.info(
        f'Successfully retrieved {total_values} total values for {len(attribute_names)} attributes of service {service_code}'
    )

    return result


@mcp.tool()
def get_pricing(
    service_code: str = SERVICE_CODE_FIELD,
    region: Union[str, List[str]] = REGION_FIELD,
    filters: Optional[List[PricingFilter]] = FILTERS_FIELD,
    max_allowed_characters: int = GET_PRICING_MAX_ALLOWED_CHARACTERS_FIELD,
    output_options: Optional[OutputOptions] = OUTPUT_OPTIONS_FIELD,
    max_results: int = MAX_RESULTS_FIELD,
    next_token: Optional[str] = NEXT_TOKEN_FIELD,
) -> Dict[str, Any]:
    """Get detailed pricing information from AWS Price List API with optional filters.

    This tool provides comprehensive access to AWS pricing data with advanced filtering capabilities.
    Always follow the discovery workflow: get_pricing_service_codes() → get_pricing_service_attributes() → 
    get_pricing_attribute_values() → get_pricing().

    Args:
        service_code: AWS service code (e.g., 'AmazonEC2', 'AmazonS3')
        region: AWS region string or list for multi-region comparison
        filters: Optional list of filter dictionaries
        max_allowed_characters: Response size limit (default: 100,000, -1 for unlimited)
        output_options: Optional filtering options to reduce response size
        max_results: Maximum results per page (default: 100, max: 100)
        next_token: Pagination token for next page

    Returns:
        Dictionary containing pricing information from AWS Pricing API
    """
    logger.info(f'Getting pricing for {service_code} in {region}')

    # Create pricing client with error handling
    try:
        pricing_client = create_pricing_client()
    except Exception as e:
        return create_error_response(
            error_type='client_creation_failed',
            message=f'Failed to create AWS Pricing client: {str(e)}',
            service_code=service_code,
            region=region,
        )

    # Build filters
    try:
        # Build region filter based on parameter type
        api_filters = [
            {
                'Field': 'regionCode',
                'Type': 'ANY_OF' if isinstance(region, list) else 'TERM_MATCH',
                'Value': ','.join(region) if isinstance(region, list) else region,
            }
        ]

        # Add any additional filters if provided
        if filters:
            # Handle both PricingFilter objects and dictionaries
            for f in filters:
                if isinstance(f, PricingFilter):
                    api_filters.append(f.model_dump(by_alias=True))
                elif isinstance(f, dict):
                    api_filters.append(f)
                else:
                    # Skip invalid filter types
                    logger.warning(f"Skipping invalid filter type: {type(f)}")

        # Make the API request
        api_params = {
            'ServiceCode': service_code,
            'Filters': api_filters,
            'MaxResults': max_results,
        }

        # Only include NextToken if it's provided
        if next_token:
            api_params['NextToken'] = next_token

        response = pricing_client.get_products(**api_params)
    except Exception as e:
        return create_error_response(
            error_type='api_error',
            message=f'Failed to retrieve pricing data for service "{service_code}" in region "{region}": {str(e)}',
            service_code=service_code,
            region=region,
            suggestion='Verify that the service code and region combination is valid. Use get_pricing_service_codes() to get valid service codes.',
        )

    # Check if results are empty
    if not response.get('PriceList'):
        return create_error_response(
            error_type='empty_results',
            message=f'The service "{service_code}" did not return any pricing data. AWS service codes typically follow patterns like "AmazonS3", "AmazonEC2", "AmazonES", etc. Please check the exact service code and try again.',
            service_code=service_code,
            region=region,
            examples={
                'OpenSearch': 'AmazonES',
                'Lambda': 'AWSLambda',
                'DynamoDB': 'AmazonDynamoDB',
                'Bedrock': 'AmazonBedrock',
            },
        )

    # Apply filtering with error handling
    try:
        price_list = transform_pricing_data(response['PriceList'], output_options)
        total_count = len(price_list)
    except ValueError as e:
        return create_error_response(
            error_type='data_processing_error',
            message=f'Failed to process pricing data: {str(e)}',
            service_code=service_code,
            region=region,
        )

    # Check if results exceed the character threshold (unless max_characters is -1 for unlimited)
    if max_allowed_characters != -1:
        # Calculate total character count of the FILTERED response data
        total_characters = sum(len(str(item)) for item in price_list)

        if total_characters > max_allowed_characters:
            return create_error_response(
                error_type='result_too_large',
                message=f'Query returned {total_characters:,} characters, exceeding the limit of {max_allowed_characters:,}. Use more specific filters or try output_options={{"pricing_terms": ["OnDemand"]}} to reduce response size.',
                service_code=service_code,
                region=region,
                total_count=total_count,
                total_characters=total_characters,
                max_allowed_characters=max_allowed_characters,
                sample_records=price_list[:3],
                suggestion='Add more specific filters like instanceType, storageClass, deploymentOption, or engineCode to reduce the number of results. For large services like EC2, consider using output_options={"pricing_terms": ["OnDemand"]} to significantly reduce response size by excluding Reserved Instance pricing.',
            )

    # Success response
    logger.info(f'Successfully retrieved {total_count} pricing items for {service_code}')

    result = {
        'status': 'success',
        'service_name': service_code,
        'data': price_list,
        'message': f'Retrieved pricing for {service_code} in {region} from AWS Pricing API',
    }

    # Include next_token if present for pagination
    if 'NextToken' in response:
        result['next_token'] = response['NextToken']

    return result


@mcp.tool()
def get_price_list_urls(
    service_code: str = SERVICE_CODE_FIELD,
    region: str = REGION_FIELD,
    effective_date: Optional[str] = EFFECTIVE_DATE_FIELD,
) -> Dict[str, Any]:
    """Get download URLs for bulk pricing data files.

    **PURPOSE:** Access complete AWS pricing datasets as downloadable files for historical analysis and bulk processing.

    **WORKFLOW:** Use this for historical pricing analysis or bulk data processing when current pricing from get_pricing() isn't sufficient.

    **REQUIRES:**
    - Service code from get_pricing_service_codes() (e.g., 'AmazonEC2', 'AmazonS3')
    - AWS region (e.g., 'us-east-1', 'eu-west-1')
    - Optional: effective_date for historical pricing (default: current date)

    **RETURNS:** Dictionary with download URLs for different formats:
    - 'csv': Direct download URL for CSV format
    - 'json': Direct download URL for JSON format

    **USE CASES:**
    - Historical pricing analysis (get_pricing() only provides current pricing)
    - Bulk data processing without repeated API calls
    - Offline analysis of complete pricing datasets
    - Savings Plans analysis across services

    **FILE PROCESSING:**
    - CSV files: Lines 1-5 are metadata, Line 6 contains headers, Line 7+ contains pricing data
    - Use `tail -n +7 pricing.csv | grep "t3.medium"` to filter data
    """
    logger.info(f'Getting price list file URLs for {service_code} in {region}')

    # Set effective date to current timestamp if not provided
    if not effective_date:
        effective_date = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')
        logger.debug(f'Using current timestamp for effective_date: {effective_date}')

    # Determine currency based on region
    currency = get_currency_for_region(region)
    logger.debug(f'Using currency {currency} for region {region}')

    try:
        # Create pricing client
        pricing_client = create_pricing_client()
    except Exception as e:
        return create_error_response(
            error_type='client_creation_failed',
            message=f'Failed to create AWS Pricing client: {str(e)}',
            service_code=service_code,
            region=region,
        )

    # Step 1: List price lists to find the appropriate ARN
    logger.info(
        f'Searching for price list: service={service_code}, region={region}, date={effective_date}, currency={currency}'
    )

    try:
        list_response = pricing_client.list_price_lists(
            ServiceCode=service_code,
            EffectiveDate=effective_date,
            RegionCode=region,
            CurrencyCode=currency,
        )
    except Exception as e:
        return create_error_response(
            error_type='list_price_lists_failed',
            message=f'Failed to list price lists for service "{service_code}" in region "{region}": {str(e)}',
            service_code=service_code,
            region=region,
            effective_date=effective_date,
            currency=currency,
            suggestion='Verify that the service code and region combination is valid. Use get_pricing_service_codes() to get valid service codes.',
        )

    # Check if any price lists were found
    price_lists = list_response.get('PriceLists', [])
    if not price_lists:
        return create_error_response(
            error_type='no_price_list_found',
            message=f'No price lists found for service "{service_code}" in region "{region}" for date "{effective_date}" with currency "{currency}"',
            service_code=service_code,
            region=region,
            effective_date=effective_date,
            currency=currency,
            suggestion='Try using a different effective date or verify the service code and region combination using get_pricing_service_codes() and get_pricing_attribute_values().',
        )

    # Get the first (most recent) price list
    price_list = price_lists[0]
    price_list_arn = price_list['PriceListArn']
    supported_formats = price_list.get('FileFormats', [])
    logger.info(f'Found price list ARN: {price_list_arn} with formats: {supported_formats}')

    if not supported_formats:
        return create_error_response(
            error_type='no_formats_available',
            message=f'Price list found but no file formats are available for service "{service_code}"',
            service_code=service_code,
            region=region,
            price_list_arn=price_list_arn,
        )

    # Step 2: Get URLs for all available formats
    result = {}

    for file_format in supported_formats:
        format_key = file_format.lower()
        logger.info(f'Getting file URL for format: {file_format}')

        try:
            url_response = pricing_client.get_price_list_file_url(
                PriceListArn=price_list_arn, FileFormat=file_format.upper()
            )

            download_url = url_response.get('Url')
            if not download_url:
                return create_error_response(
                    error_type='empty_url_response',
                    message=f'AWS API returned empty URL for format "{file_format}"',
                    service_code=service_code,
                    region=region,
                    price_list_arn=price_list_arn,
                    file_format=format_key,
                    suggestion='This may be a temporary AWS service issue. Try again in a few minutes.',
                )

            result[format_key] = download_url
            logger.debug(f'Successfully got URL for format {file_format}')

        except Exception as e:
            return create_error_response(
                error_type='format_url_failed',
                message=f'Failed to get download URL for format "{file_format}": {str(e)}',
                service_code=service_code,
                region=region,
                price_list_arn=price_list_arn,
                file_format=format_key,
                suggestion='This format may not be available for this service. Check supported_formats in the price list response.',
            )

    logger.info(
        f'Successfully retrieved {len(result)} price list file URLs for {service_code}'
    )

    return result


@mcp.tool()
def generate_cost_report_wrapper(
    pricing_data: Dict[str, Any] = Field(
        ..., description='Raw pricing data from AWS pricing tools'
    ),
    service_name: str = Field(..., description='Name of the AWS service'),
    # Core parameters (simple, commonly used)
    related_services: Optional[List[str]] = Field(
        None, description='List of related AWS services'
    ),
    pricing_model: str = Field(
        'ON DEMAND', description='Pricing model (e.g., "ON DEMAND", "Reserved")'
    ),
    assumptions: Optional[List[str]] = Field(
        None, description='List of assumptions for cost analysis'
    ),
    exclusions: Optional[List[str]] = Field(
        None, description='List of items excluded from cost analysis'
    ),
    output_file: Optional[str] = Field(None, description='Path to save the report file'),
    format: str = Field('markdown', description='Output format ("markdown" or "csv")'),
    # Advanced parameters (grouped in a dictionary for complex use cases)
    detailed_cost_data: Optional[Dict[str, Any]] = Field(
        None, description='Detailed cost information for complex scenarios'
    ),
) -> str:
    """Generate a comprehensive cost analysis report for AWS services.

    This tool creates detailed cost analysis reports based on AWS pricing data,
    with optional detailed cost information for more complex scenarios.

    **IMPORTANT REQUIREMENTS:**
    - ALWAYS include detailed unit pricing information (e.g., "$0.0008 per 1K input tokens")
    - ALWAYS show calculation breakdowns (unit price × usage = total cost)
    - ALWAYS specify the pricing model (e.g., "ON DEMAND")
    - ALWAYS list all assumptions and exclusions explicitly

    Args:
        pricing_data: Raw pricing data from AWS pricing tools (required)
        service_name: Name of the primary service (required)
        related_services: List of related services to include in the analysis
        pricing_model: The pricing model used (default: "ON DEMAND")
        assumptions: List of assumptions made for the cost analysis
        exclusions: List of items excluded from the cost analysis
        output_file: Path to save the report to a file
        format: Output format ("markdown" or "csv")
        detailed_cost_data: Dictionary containing detailed cost information for complex scenarios

    Returns:
        The generated cost analysis report as a string
    """
    try:
        return generate_cost_report(
            pricing_data=pricing_data,
            service_name=service_name,
            related_services=related_services,
            pricing_model=pricing_model,
            assumptions=assumptions,
            exclusions=exclusions,
            output_file=output_file,
            detailed_cost_data=detailed_cost_data,
            ctx=None,  # No context available in Lambda
            format=format,
        )
    except Exception as e:
        error_msg = f'Error generating cost report: {str(e)}'
        logger.error(error_msg)
        return error_msg


@mcp.tool()
def get_bedrock_patterns() -> str:
    """Get architecture patterns for Amazon Bedrock applications.

    This tool provides architecture patterns, component relationships, and cost considerations
    for Amazon Bedrock applications. It does not include specific pricing information, which
    should be obtained using get_pricing.

    Returns:
        String containing the architecture patterns in markdown format
    """
    return BEDROCK_PATTERNS


def lambda_handler(event, context):
    """AWS Lambda handler function."""
    logger_std.info("Processing Lambda request for AWS Pricing MCP Server")
    
    # Handle GET requests for health check
    if event.get('httpMethod') == 'GET':
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': '{"status": "healthy", "service": "AWS Pricing MCP Server"}'
        }
    
    return mcp.handle_request(event, context)
