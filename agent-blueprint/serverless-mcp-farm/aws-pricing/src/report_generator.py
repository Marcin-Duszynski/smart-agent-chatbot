"""
Cost report generator for AWS Pricing MCP Server
"""

from helpers import CostAnalysisHelper
from static_data import COST_REPORT_TEMPLATE
from typing import Any, Dict, List, Optional


def generate_cost_report(
    pricing_data: Dict[str, Any],
    service_name: str,
    related_services: Optional[List[str]] = None,
    pricing_model: str = 'ON DEMAND',
    assumptions: Optional[List[str]] = None,
    exclusions: Optional[List[str]] = None,
    output_file: Optional[str] = None,
    detailed_cost_data: Optional[Dict[str, Any]] = None,
    ctx: Optional[Any] = None,
    format: str = 'markdown'
) -> str:
    """Generate a cost analysis report.
    
    Args:
        pricing_data: Raw pricing data from AWS API
        service_name: Primary service name
        related_services: List of related services
        pricing_model: Pricing model (default: 'ON DEMAND')
        assumptions: List of assumptions
        exclusions: List of exclusions
        output_file: Optional output file path
        detailed_cost_data: Detailed cost information
        ctx: Optional context for logging
        format: Output format ('markdown' or 'csv')
        
    Returns:
        Generated cost report as string
    """
    try:
        # Use detailed cost data if provided, otherwise create basic structure
        if detailed_cost_data and 'services' in detailed_cost_data:
            return _generate_detailed_report(
                detailed_cost_data, service_name, pricing_model, 
                assumptions, exclusions, output_file, ctx, format
            )
        else:
            return _generate_basic_report(
                pricing_data, service_name, related_services, 
                pricing_model, assumptions, exclusions, output_file, ctx, format
            )
            
    except Exception as e:
        error_msg = f"Error generating cost report: {str(e)}"
        if ctx:
            # Assume ctx has an error method for logging
            pass
        return error_msg


def _generate_basic_report(
    pricing_data: Dict[str, Any],
    service_name: str,
    related_services: Optional[List[str]],
    pricing_model: str,
    assumptions: Optional[List[str]],
    exclusions: Optional[List[str]],
    output_file: Optional[str],
    ctx: Optional[Any],
    format: str
) -> str:
    """Generate a basic cost report from pricing data."""
    
    # Parse pricing data
    pricing_structure = CostAnalysisHelper.parse_pricing_data(
        pricing_data, service_name, related_services
    )
    
    # Generate cost tables
    cost_tables = CostAnalysisHelper.generate_cost_table(pricing_structure)
    
    # Start with template
    report = COST_REPORT_TEMPLATE
    
    # Replace placeholders
    report = report.replace('{service_name}', service_name.title())
    report = report.replace('{service_description}', pricing_structure['service_description'])
    
    # Handle assumptions
    if assumptions:
        assumptions_text = '\n'.join([f'- {assumption}' for assumption in assumptions])
    else:
        assumptions_text = '\n'.join([f'- {assumption}' for assumption in pricing_structure['assumptions']])
    report = report.replace('{assumptions_section}', assumptions_text)
    
    # Handle exclusions/limitations
    if exclusions:
        limitations_text = '\n'.join([f'- {exclusion}' for exclusion in exclusions])
    else:
        limitations_text = f'- This analysis only includes confirmed pricing information for {service_name}\n- Providing less information is better than giving incorrect information'
    report = report.replace('{limitations_section}', limitations_text)
    
    # Replace cost tables
    report = report.replace('{unit_pricing_details_table}', cost_tables['unit_pricing_details_table'])
    report = report.replace('{cost_calculation_table}', cost_tables['cost_calculation_table'])
    report = report.replace('{usage_cost_table}', cost_tables['usage_cost_table'])
    report = report.replace('{projected_costs}', cost_tables['projected_costs_table'])
    
    # Replace other sections
    report = report.replace('{free_tier_info}', pricing_structure['free_tier'])
    
    key_factors = '\n'.join([f'- {factor}' for factor in pricing_structure['key_cost_factors']])
    report = report.replace('{key_cost_factors}', key_factors)
    
    # Replace recommendations
    recommendations = pricing_structure['recommendations']
    if len(recommendations['immediate']) >= 3:
        report = report.replace('{recommendation_1}', recommendations['immediate'][0])
        report = report.replace('{recommendation_2}', recommendations['immediate'][1])
        report = report.replace('{recommendation_3}', recommendations['immediate'][2])
    
    if len(recommendations['best_practices']) >= 3:
        report = report.replace('{best_practice_1}', recommendations['best_practices'][0])
        report = report.replace('{best_practice_2}', recommendations['best_practices'][1])
        report = report.replace('{best_practice_3}', recommendations['best_practices'][2])
    
    # Replace remaining placeholders
    report = report.replace('{custom_analysis_sections}', '')
    report = report.replace('{conclusion}', f'This analysis provides a foundation for understanding {service_name} costs. For more detailed analysis, consider using specific pricing filters and usage scenarios.')
    
    # Write to file if requested
    if output_file:
        try:
            with open(output_file, 'w') as f:
                f.write(report)
        except Exception as e:
            if ctx:
                pass  # Log error if context available
    
    return report


def _generate_detailed_report(
    detailed_cost_data: Dict[str, Any],
    service_name: str,
    pricing_model: str,
    assumptions: Optional[List[str]],
    exclusions: Optional[List[str]],
    output_file: Optional[str],
    ctx: Optional[Any],
    format: str
) -> str:
    """Generate a detailed cost report from structured cost data."""
    
    # Start with template
    report = COST_REPORT_TEMPLATE
    
    # Replace basic information
    project_name = detailed_cost_data.get('project_name', service_name)
    report = report.replace('{service_name}', project_name)
    
    description = detailed_cost_data.get('description', f'Cost analysis for {project_name}')
    report = report.replace('{service_description}', description)
    
    # Handle assumptions
    if 'assumptions' in detailed_cost_data:
        if isinstance(detailed_cost_data['assumptions'], list):
            assumptions_text = '\n'.join([f'- {assumption}' for assumption in detailed_cost_data['assumptions']])
        else:
            assumptions_text = detailed_cost_data['assumptions']
    elif assumptions:
        assumptions_text = '\n'.join([f'- {assumption}' for assumption in assumptions])
    else:
        assumptions_text = '- Standard configuration for all services\n- Default usage patterns\n- No reserved instances applied'
    
    report = report.replace('{assumptions_section}', assumptions_text)
    
    # Handle exclusions
    if 'exclusions' in detailed_cost_data:
        if isinstance(detailed_cost_data['exclusions'], list):
            limitations_text = '\n'.join([f'- {exclusion}' for exclusion in detailed_cost_data['exclusions']])
        else:
            limitations_text = detailed_cost_data['exclusions']
    elif exclusions:
        limitations_text = '\n'.join([f'- {exclusion}' for exclusion in exclusions])
    else:
        limitations_text = '- This analysis only includes confirmed compatible services\n- Database costs may not be included if compatibility is uncertain'
    
    report = report.replace('{limitations_section}', limitations_text)
    
    # Generate service-specific tables if services are provided
    if 'services' in detailed_cost_data:
        services = detailed_cost_data['services']
        
        # Create unit pricing table
        unit_pricing_table = _create_unit_pricing_table(services)
        report = report.replace('{unit_pricing_details_table}', unit_pricing_table)
        
        # Create cost calculation table
        cost_calc_table = _create_cost_calculation_table(services)
        report = report.replace('{cost_calculation_table}', cost_calc_table)
        
        # Create usage scaling table
        usage_table = _create_usage_scaling_table(services)
        report = report.replace('{usage_cost_table}', usage_table)
        
    else:
        # Use default tables
        report = report.replace('{unit_pricing_details_table}', 'No detailed unit pricing information available.')
        report = report.replace('{cost_calculation_table}', 'No cost calculation details available.')
        report = report.replace('{usage_cost_table}', 'Cost scaling information not available.')
    
    # Replace other sections with defaults
    report = report.replace('{free_tier_info}', 'Check AWS Free Tier documentation for current offers and limitations.')
    report = report.replace('{key_cost_factors}', '- Request volume and frequency\n- Data storage requirements\n- Compute resources utilized')
    report = report.replace('{projected_costs}', 'Insufficient data to generate cost projections.')
    
    # Handle recommendations
    if 'recommendations' in detailed_cost_data:
        recs = detailed_cost_data['recommendations']
        immediate = recs.get('immediate', [])
        best_practices = recs.get('best_practices', [])
        
        if len(immediate) >= 3:
            report = report.replace('{recommendation_1}', immediate[0])
            report = report.replace('{recommendation_2}', immediate[1])
            report = report.replace('{recommendation_3}', immediate[2])
        
        if len(best_practices) >= 3:
            report = report.replace('{best_practice_1}', best_practices[0])
            report = report.replace('{best_practice_2}', best_practices[1])
            report = report.replace('{best_practice_3}', best_practices[2])
    
    # Replace remaining placeholders
    report = report.replace('{custom_analysis_sections}', '')
    conclusion = detailed_cost_data.get('conclusion', f'This analysis provides cost insights for {project_name}. Regular monitoring and optimization will help maintain cost efficiency.')
    report = report.replace('{conclusion}', conclusion)
    
    # Write to file if requested
    if output_file:
        try:
            with open(output_file, 'w') as f:
                f.write(report)
        except Exception as e:
            if ctx:
                pass  # Log error if context available
    
    return report


def _create_unit_pricing_table(services: Dict[str, Any]) -> str:
    """Create unit pricing table from services data."""
    table = ['| Service | Resource Type | Unit | Price | Free Tier |',
             '|---------|--------------|------|-------|-----------|']
    
    for service_name, service_data in services.items():
        unit_pricing = service_data.get('unit_pricing', {})
        free_tier = service_data.get('free_tier_info', 'None')
        
        if unit_pricing:
            for resource_type, price in unit_pricing.items():
                formatted_type = resource_type.replace('_', ' ').title()
                table.append(f'| {service_name} | {formatted_type} | 1 unit | {price} | {free_tier} |')
        else:
            table.append(f'| {service_name} | N/A | N/A | N/A | {free_tier} |')
    
    return '\n'.join(table)


def _create_cost_calculation_table(services: Dict[str, Any]) -> str:
    """Create cost calculation table from services data."""
    table = ['| Service | Usage | Calculation | Monthly Cost |',
             '|---------|-------|-------------|-------------|']
    
    total_cost = 0.0
    
    for service_name, service_data in services.items():
        usage = service_data.get('usage', 'N/A')
        calculation = service_data.get('calculation_details', 'N/A')
        cost = service_data.get('estimated_cost', 'N/A')
        
        table.append(f'| {service_name} | {usage} | {calculation} | {cost} |')
        
        # Try to extract numeric cost for total
        if isinstance(cost, str) and '$' in cost:
            try:
                import re
                cost_match = re.search(r'\$(\d+(?:\.\d+)?)', cost)
                if cost_match:
                    total_cost += float(cost_match.group(1))
            except:
                pass
    
    if total_cost > 0:
        table.append(f'| **Total** | **All services** | **Sum of calculations** | **${total_cost:.2f}/month** |')
    
    return '\n'.join(table)


def _create_usage_scaling_table(services: Dict[str, Any]) -> str:
    """Create usage scaling table from services data."""
    table = ['| Service | Low Usage | Medium Usage | High Usage |',
             '|---------|-----------|--------------|------------|']
    
    for service_name, service_data in services.items():
        # Simple scaling based on estimated cost
        cost_str = service_data.get('estimated_cost', '$0')
        try:
            import re
            cost_match = re.search(r'\$(\d+(?:\.\d+)?)', cost_str)
            if cost_match:
                base_cost = float(cost_match.group(1))
                low = f'${base_cost * 0.5:.2f}/month'
                medium = f'${base_cost:.2f}/month'
                high = f'${base_cost * 2:.2f}/month'
            else:
                low = medium = high = 'Varies'
        except:
            low = medium = high = 'Varies'
        
        table.append(f'| {service_name} | {low} | {medium} | {high} |')
    
    return '\n'.join(table)
