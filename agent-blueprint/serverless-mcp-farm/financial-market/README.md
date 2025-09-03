# Financial Market MCP Server

A comprehensive financial market data and analysis MCP server that provides real-time stock quotes, historical data, market indices, financial news, fundamental analysis, and comprehensive investment analysis.

## Features

### 6 Available Tools:

1. **stock_quote** - Get current stock quote information with detailed metrics
2. **historical_data** - Get historical stock data for charting and trend analysis  
3. **market_indices** - Get major market index data (S&P 500, NASDAQ, Dow Jones)
4. **financial_news** - Get the latest financial news for specific stocks
5. **fundamental_analysis** - Get company fundamental analysis
6. **market_data** - Get comprehensive market overview

## Dependencies

- `yfinance>=0.2.58` - Yahoo Finance data
- `pandas>=2.0.0` - Data analysis
- `curl_cffi==0.12.0` - HTTP client for financial data
- `awslabs-mcp-lambda-handler` - MCP Lambda integration
- `loguru>=0.7.0` - Advanced logging
- `pydantic` - Data validation

## Deployment

### Prerequisites
- AWS CLI configured
- Appropriate AWS permissions for Lambda, API Gateway, CloudFormation, IAM

### Deploy
```bash
cd infrastructure
./deploy.sh
```

The deployment will:
1. Build Lambda deployment package
2. Deploy CloudFormation stack
3. Update Lambda function code
4. Return API Gateway endpoint URL

### Usage Example
Once deployed, the MCP server will be available at:
```
https://your-api-id.execute-api.us-west-2.amazonaws.com/prod/mcp
```

## Tool Examples

### Get Stock Quote
```json
{
  "method": "stock_quote",
  "arguments": {
    "symbol": "AAPL"
  }
}
```

### Get Market Data
```json
{
  "method": "market_data",
  "arguments": {}
}
```

### Get Financial News
```json
{
  "method": "financial_news", 
  "arguments": {
    "symbol": "TSLA",
    "count": 5
  }
}
```

### Get Fundamental Analysis
```json
{
  "method": "fundamental_analysis",
  "arguments": {
    "symbol": "MSFT"
  }
}
```

## Architecture

- **Runtime**: Python 3.13
- **Memory**: 512MB
- **Timeout**: 60 seconds
- **Platform**: AWS Lambda + API Gateway
- **Protocol**: HTTP/HTTPS with CORS support