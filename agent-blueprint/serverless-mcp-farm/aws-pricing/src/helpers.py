"""
Helper utilities for AWS Pricing MCP Server
"""

from typing import Any, Dict, List


class CostAnalysisHelper:
    """Helper class for cost analysis operations."""
    
    @staticmethod
    def parse_pricing_data(
        pricing_data: Dict[str, Any], 
        service_name: str, 
        related_services: List[str] = None
    ) -> Dict[str, Any]:
        """Parse pricing data into a structured format for cost analysis.
        
        Args:
            pricing_data: Raw pricing data from AWS API
            service_name: Primary service name
            related_services: List of related services
            
        Returns:
            Structured pricing data for analysis
        """
        return {
            'service_name': service_name,
            'service_description': f'Cost analysis for {service_name}',
            'assumptions': [
                'Standard ON DEMAND pricing unless otherwise specified',
                'No caching or optimization techniques applied',
                'Default service configurations'
            ],
            'free_tier': 'Check AWS Free Tier documentation for current offers',
            'key_cost_factors': [
                'Request volume and frequency',
                'Data storage requirements',
                'Compute resources utilized'
            ],
            'recommendations': {
                'immediate': [
                    'Monitor usage patterns',
                    'Set up cost alerts',
                    'Review resource utilization'
                ],
                'best_practices': [
                    'Implement cost allocation tags',
                    'Use AWS Cost Explorer for analysis',
                    'Consider reserved capacity for predictable workloads'
                ]
            }
        }
    
    @staticmethod
    def generate_cost_table(pricing_structure: Dict[str, Any]) -> Dict[str, str]:
        """Generate cost tables from pricing structure.
        
        Args:
            pricing_structure: Structured pricing data
            
        Returns:
            Dictionary containing formatted cost tables
        """
        return {
            'unit_pricing_details_table': 'No detailed unit pricing information available.',
            'cost_calculation_table': 'No cost calculation details available.',
            'usage_cost_table': 'Cost scaling information not available.',
            'projected_costs_table': 'Insufficient data to generate cost projections.'
        }
    
    @staticmethod
    def generate_well_architected_recommendations(service_names: List[str]) -> Dict[str, List[str]]:
        """Generate AWS Well-Architected Framework cost optimization recommendations.
        
        Args:
            service_names: List of service names
            
        Returns:
            Dictionary with immediate actions and best practices
        """
        return {
            'immediate': [
                'Optimize resource usage based on actual requirements',
                'Implement cost allocation tags for better tracking',
                'Set up AWS Budgets alerts for cost monitoring'
            ],
            'best_practices': [
                'Regularly review costs with AWS Cost Explorer',
                'Consider reserved capacity for predictable workloads',
                'Implement automated scaling based on demand'
            ]
        }
