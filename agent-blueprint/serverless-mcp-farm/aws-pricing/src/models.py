"""
Data models for AWS Pricing MCP Server
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Any, Dict, List, Optional, Union


class PricingFilter(BaseModel):
    """Model for pricing filter parameters."""
    
    model_config = ConfigDict(populate_by_name=True)
    
    field: str = Field(..., description="The field to filter on", alias="Field")
    type: str = Field(default="TERM_MATCH", description="The filter type", alias="Type")
    value: Union[str, List[str]] = Field(..., description="The value(s) to filter by", alias="Value")


class OutputOptions(BaseModel):
    """Model for output filtering options."""
    
    pricing_terms: Optional[List[str]] = Field(
        None, 
        description="Filter by pricing terms (e.g., ['OnDemand', 'Reserved'])"
    )
    product_attributes: Optional[List[str]] = Field(
        None,
        description="Include only specific product attributes"
    )
    exclude_free_products: Optional[bool] = Field(
        False,
        description="Exclude products with $0.00 OnDemand pricing"
    )


class ErrorResponse(BaseModel):
    """Model for error responses."""
    
    model_config = ConfigDict(extra="allow")
    
    error_type: str = Field(..., description="Type of error")
    message: str = Field(..., description="Error message")


# Field definitions for tool parameters
SERVICE_CODE_FIELD = Field(..., description="AWS service code (e.g., 'AmazonEC2', 'AmazonS3')")

REGION_FIELD = Field(
    ..., 
    description="AWS region string (e.g., 'us-east-1') or list for multi-region comparison"
)

FILTERS_FIELD = Field(
    None,
    description="Optional list of filter dictionaries"
)

GET_PRICING_MAX_ALLOWED_CHARACTERS_FIELD = Field(
    100000,
    description="Response size limit in characters (default: 100,000, use -1 for unlimited)"
)

OUTPUT_OPTIONS_FIELD = Field(
    None,
    description="Optional output filtering options to reduce response size"
)

MAX_RESULTS_FIELD = Field(
    100,
    description="Maximum number of results to return per page (default: 100, max: 100)"
)

NEXT_TOKEN_FIELD = Field(
    None,
    description="Pagination token from previous response to get next page of results"
)

ATTRIBUTE_NAMES_FIELD = Field(
    ...,
    description="List of attribute names to get values for"
)

EFFECTIVE_DATE_FIELD = Field(
    None,
    description="Effective date in 'YYYY-MM-DD HH:MM' format (default: current timestamp)"
)
