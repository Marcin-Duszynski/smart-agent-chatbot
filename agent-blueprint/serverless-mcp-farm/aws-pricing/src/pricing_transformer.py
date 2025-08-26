"""
Pricing data transformation utilities for AWS Pricing MCP Server
"""

import json
from loguru import logger
from models import OutputOptions
from typing import Any, Dict, List, Optional


def transform_pricing_data(
    price_list: List[str], 
    output_options: Optional[OutputOptions] = None
) -> List[Dict[str, Any]]:
    """Transform raw pricing data based on output options.
    
    Args:
        price_list: List of pricing data strings from AWS API
        output_options: Optional filtering options
        
    Returns:
        List of transformed pricing dictionaries
        
    Raises:
        ValueError: If data processing fails
    """
    try:
        transformed_data = []
        
        for price_item in price_list:
            try:
                # Parse JSON string
                price_data = json.loads(price_item)
                
                # Apply output options filtering if provided
                if output_options:
                    price_data = _apply_output_filters(price_data, output_options)
                
                # Skip if filtered out completely
                if price_data:
                    transformed_data.append(price_data)
                    
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse pricing data item: {e}")
                continue
                
        logger.info(f"Transformed {len(transformed_data)} pricing items")
        return transformed_data
        
    except Exception as e:
        logger.error(f"Failed to transform pricing data: {e}")
        raise ValueError(f"Failed to transform pricing data: {str(e)}")


def _apply_output_filters(
    price_data: Dict[str, Any], 
    output_options: OutputOptions
) -> Optional[Dict[str, Any]]:
    """Apply output filtering options to a single pricing item.
    
    Args:
        price_data: Single pricing data dictionary
        output_options: Filtering options
        
    Returns:
        Filtered pricing data or None if filtered out
    """
    try:
        # Create a copy to avoid modifying original
        filtered_data = price_data.copy()
        
        # Filter by pricing terms
        if output_options.pricing_terms:
            terms = filtered_data.get('terms', {})
            filtered_terms = {}
            
            for term_type in output_options.pricing_terms:
                if term_type in terms:
                    filtered_terms[term_type] = terms[term_type]
            
            if not filtered_terms:
                return None  # No matching terms found
                
            filtered_data['terms'] = filtered_terms
        
        # Filter product attributes
        if output_options.product_attributes:
            product = filtered_data.get('product', {})
            attributes = product.get('attributes', {})
            
            filtered_attributes = {}
            for attr in output_options.product_attributes:
                if attr in attributes:
                    filtered_attributes[attr] = attributes[attr]
            
            if product:
                product['attributes'] = filtered_attributes
                filtered_data['product'] = product
        
        # Exclude free products if requested
        if output_options.exclude_free_products:
            if _is_free_product(filtered_data):
                return None
        
        return filtered_data
        
    except Exception as e:
        logger.warning(f"Failed to apply output filters: {e}")
        return price_data  # Return original data if filtering fails


def _is_free_product(price_data: Dict[str, Any]) -> bool:
    """Check if a product has $0.00 OnDemand pricing.
    
    Args:
        price_data: Pricing data dictionary
        
    Returns:
        True if product is free (has $0.00 OnDemand pricing)
    """
    try:
        terms = price_data.get('terms', {})
        on_demand = terms.get('OnDemand', {})
        
        for term_key, term_data in on_demand.items():
            price_dimensions = term_data.get('priceDimensions', {})
            
            for dimension_key, dimension_data in price_dimensions.items():
                price_per_unit = dimension_data.get('pricePerUnit', {})
                
                # Check if any currency has a non-zero price
                for currency, price in price_per_unit.items():
                    try:
                        if float(price) > 0:
                            return False
                    except (ValueError, TypeError):
                        continue
        
        return True  # All prices are $0.00 or no pricing found
        
    except Exception:
        return False  # If we can't determine, assume it's not free
