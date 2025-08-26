"""
Static data for AWS Pricing MCP Server
Contains templates and patterns that were previously stored as files
"""

# Bedrock Architecture Patterns
BEDROCK_PATTERNS = """# Amazon Bedrock Architecture Patterns

This document outlines common architecture patterns for Amazon Bedrock applications, their components, and cost considerations.

## Common Pricing Assumptions and Models

### Pricing Models

- **ON DEMAND**: Pay-as-you-go pricing with no upfront commitment. This is the default pricing model for most Bedrock services and is charged based on actual usage.
- **PROVISIONED THROUGHPUT**: Reserved capacity for consistent workloads, offering cost savings for predictable usage patterns.
- **BATCH**: Lower cost for non-real-time processing, suitable for asynchronous workloads.
- **CACHED**: Reduced costs through reusing previously generated responses or embeddings.

### Common Assumptions

When calculating costs for Bedrock services, the following assumptions are typically made:

1. **Usage Pattern Assumptions**:
   - Standard ON DEMAND pricing unless otherwise specified
   - No caching or optimization techniques applied
   - Average request sizes based on typical workloads
   - No reserved capacity or savings plans

2. **Technical Assumptions**:
   - Token counts based on English language (other languages may have different tokenization rates)
   - Average token counts: 1K tokens ≈ 750 words of English text
   - Standard prompt templates without optimization
   - Default parameter settings (temperature, top-p, etc.)

3. **Infrastructure Assumptions**:
   - Default service configurations
   - No custom scaling policies
   - Standard availability and redundancy settings
   - No special networking or VPC configurations

### Common Exclusions

The following items are typically excluded from Bedrock cost analyses:

1. **Infrastructure Exclusions**:
   - Data transfer costs between regions
   - VPC endpoint costs
   - Custom networking configurations
   - Development and testing environments

2. **Operational Exclusions**:
   - Development and maintenance costs
   - Training costs for custom models
   - Human review and quality assurance
   - Monitoring and observability costs beyond CloudWatch

3. **Business Exclusions**:
   - Implementation and integration costs
   - Staff training and onboarding
   - Business process changes
   - Opportunity costs

### Unit Pricing and Calculation Examples

**Example 1: Foundation Model Inference**
```
Unit Price: $0.0008 per 1K input tokens, $0.0016 per 1K output tokens
Usage: 1,000,000 input tokens, 500,000 output tokens
Calculation: ($0.0008/1K × 1,000K input) + ($0.0016/1K × 500K output) = $0.80 + $0.80 = $1.60
```

**Example 2: Knowledge Base**
```
Unit Price: $0.20 per OCU-hour (OpenSearch Serverless)
Usage: 2 OCUs (minimum) × 24 hours × 30 days = 1,440 OCU-hours
Calculation: $0.20 × 1,440 OCU-hours = $288.00
```

**Example 3: Agent**
```
Pricing: Based on foundation model usage (input/output tokens)
Usage: Agent with 10,000 requests using Claude 3.5 Haiku
Calculation: Foundation model costs based on tokens processed
Additional costs: Lambda invocations for action groups (if used)
Note: Refer to AWS documentation for the most current pricing details
```

## Core Foundation Model Pattern

### Architecture Components

- **Foundation Model**: Claude, Llama, Titan, etc.
- **Orchestration**: Lambda, ECS, or direct API calls
- **Storage**: S3 for prompts/responses (optional)

### Cost Drivers

- Input token volume
- Output token volume
- Request frequency
- Model selection

### Cost Optimization Considerations

- Prompt engineering to reduce token usage
- Response caching for common queries
- Batch processing where applicable
- Model selection based on performance/cost tradeoff

## Knowledge Base Extension

Amazon Bedrock Knowledge Bases is a fully managed Retrieval-Augmented Generation (RAG) workflow that enables customers to create highly accurate, low-latency, secure, and custom generative AI applications by incorporating contextual information from their own data sources. It supports various data sources, including S3, and Confluence, Salesforce, and SharePoint, in preview. It also offers document ingestion for streaming data. Bedrock Knowledge Bases converts unstructured data into embeddings, stores them in vector databases, and enables retrieval from diverse data stores. It also integrates with Kendra for managed retrieval and supports structured data retrieval using natural language to SQL.

- Knowledge Base with vector store
- Knowledge Base with structured data store
- Knowledge Base with Kendra GenAI Index

### Knowledge Base with vector store

- **Vector Store Options**:
  - Amazon OpenSearch Serverless (default/recommended)
  - Amazon Aurora PostgreSQL
  - Neptune Analytics
  - Pinecone
  - Redis Enterprise Cloud
  - MongoDB Atlas
- **Embedding Model**: Titan Embeddings
- **Data Source**:
  - Amazon S3
  - Confluence
  - Microsoft SharePoint
  - Salesforce
  - Web Crawler
  - Custom

#### Cost Drivers for Knowledge Base with vector store

- Vector store costs (varies by provider)
  - For OpenSearch Serverless: OCU allocation (minimum 2 OCUs)
- Document volume and size
- Query frequency and complexity
- Vector storage requirements
- Rerank models:
  - Rerank models are designed to improve the relevance and accuracy of responses in Retrieval Augmented Generation (RAG) applications. They are charged per query.
  - Amazon-rerank-v1.0, Cohere rerank models, ...

#### Cost Drivers for Knowledge Base with structured data store

- Structured Data Retrieval (SQL Generation)
- Database
  - If you are not including Database pricing for this option, clearly indicate that this is NOT included in the pricing and add the explanation in 'Assumptions'

#### Cost Drivers for Knowledge Base with Kendra GenAI Index

- Amazon Kendra pricing

### Cost Optimization Considerations for Knowledge Base

- Optimize document chunking strategy
- Configure OCU capacity based on workload
- Implement efficient vector search patterns
- Consider data lifecycle management for older documents
- Monitor OCU utilization metrics
- Choose appropriate vector store based on your specific needs

## Agent Extension

### Additional Components

- **Agent Service**: Bedrock Agent
- **Action Groups**: Lambda functions
- **API Integration**: API Gateway

### Architecture Relationships

- Agent leverages foundation model for responses
- Foundation model costs are included in agent usage
- Action groups extend agent capabilities
- Knowledge bases can be associated with agents

### Cost Drivers for Agent Extension

- Foundation model token usage
- Action group invocations
- Associated knowledge base queries

### Cost Optimization Considerations for Agent Extension

- Optimize agent prompts to reduce token consumption
- Implement response caching for common queries
- Use knowledge base filtering to reduce the context size
- Design efficient action groups

## Guardrails Extension

- **Guardrails Service**: Bedrock Guardrails
- **Policy Configuration**: Content filters, denied topics, etc.

### Architecture Relationships

- Applied to foundation model inputs/outputs
- Can be integrated with agents and knowledge bases
- Charged based on text units processed

### Cost Drivers for Guardrails Extension

- Text unit volume (1K characters per unit)
- Number of enabled policies
- Request frequency

### Cost Optimization Considerations for Guardrails Extension

- Apply guardrails selectively based on use case
- Monitor guardrail usage and adjust as needed
- Optimize input text to reduce text unit count

## Data Automation Extension

Amazon Bedrock Data Automation transforms unstructured, multimodal content into structured data formats for use cases like intelligent document processing, video analysis, and RAG. Bedrock Data Automation can generate Standard Output content using predefined defaults which are modality specific, like scene-by-scene descriptions of videos, audio transcripts or automated document analysis. Customers can additionally create Custom Outputs by specifying their output requirements in Blueprints based on their own data schema that they can then easily load into an existing database or data warehouse. Through an integration with Knowledge Bases, Bedrock Data Automation can also be used to parse content for RAG applications, improving the accuracy and relevancy of results by including information embedded in both images and text.

- **Bedrock Data Automation inference API**
  - Standard Output
    - Audio
    - Documents
    - Images
    - Video
  - Custom Output (includes Standard Output)
    - Documents
    - Images

### Architecture Relationships

- Feeds processed data into knowledge bases
- Enhances multimodal capabilities
- Charged per page for documents, per minute for video, per image for images

### Cost Drivers

- Modality:
  - Audio
  - Documents
  - Images
  - Video
- Document/image/video volume
- Output types (standard vs. custom)
- Field count for custom outputs

### Cost Optimization Considerations

- Optimize processing settings based on content type
- Balance between standard and custom outputs
- Process only necessary content
- Consider field count in custom output blueprints

## Common Architecture Mistakes

### Double-Counting Foundation Model Costs

- Agent costs already include foundation model usage
- Don't count both separately in cost estimates

### Underestimating Vector Store Costs

- Vector store is typically the largest cost component
- For OpenSearch Serverless: Minimum 2 OCUs required ($345.60/month minimum)
- OCUs needed for both indexing and search
- Each vector store option has its own pricing model

### Ignoring Minimum Resource Requirements

- OpenSearch Serverless requires minimum 2 OCUs
- Foundation models have minimum token charges
- Custom models have minimum provisioned throughput requirements

### Missing Storage Costs

- Both S3 (for documents) and vector store storage costs should be included
- Consider data transfer costs between services
- Account for custom model storage costs
"""

# Cost Report Template
COST_REPORT_TEMPLATE = """# AWS Cost Analysis Report: {service_name}

## Executive Summary

{service_description}

This cost analysis is based on the following pricing model:
- **ON DEMAND** pricing (pay-as-you-go) unless otherwise specified
- Standard service configurations without reserved capacity or savings plans
- No caching or optimization techniques applied

## Assumptions

{assumptions_section}

## Limitations and Exclusions

{limitations_section}

## Unit Pricing Details

{unit_pricing_details_table}

## Cost Calculation

{cost_calculation_table}

## Free Tier Information

{free_tier_info}

## Cost Scaling with Usage

{usage_cost_table}

## Key Cost Factors

The following factors significantly impact your monthly costs:

{key_cost_factors}

## Projected Costs Over Time

{projected_costs}

## AWS Well-Architected Cost Optimization Recommendations

### Immediate Actions

- {recommendation_1}
- {recommendation_2}
- {recommendation_3}

### Best Practices

- {best_practice_1}
- {best_practice_2}
- {best_practice_3}

{custom_analysis_sections}

## Conclusion

{conclusion}

---

*This analysis is based on current AWS pricing as of the report generation date. Prices may vary by region and are subject to change. For the most up-to-date pricing information, please refer to the official AWS Pricing pages.*
"""
