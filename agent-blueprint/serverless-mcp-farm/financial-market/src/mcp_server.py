#!/usr/bin/env python3
"""
Financial Market MCP Server for Lambda deployment using awslabs-mcp-lambda-handler
Provides comprehensive financial market data, analysis, and news tools.
"""

import logging
import os
import sys
import asyncio
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from awslabs.mcp_lambda_handler import MCPLambdaHandler
from pydantic import Field
from loguru import logger

# Logging configuration
logging.basicConfig(level=logging.INFO)
logger_std = logging.getLogger(__name__)

# Set up loguru logging
logger.remove()
logger.add(sys.stderr, level=os.getenv('FASTMCP_LOG_LEVEL', 'WARNING'))

# Create MCP Lambda handler
mcp = MCPLambdaHandler(name="financial-market", version="1.0.0")

class APIError(Exception):
    pass

# Helper functions for formatting output
def format_number(num):
    """Format a number with commas and 2 decimal places"""
    if num is None:
        return 'N/A'
    try:
        return f"{num:,.2f}"
    except (ValueError, TypeError):
        return 'N/A'

def format_percent(num):
    """Format a number as a percentage with 2 decimal places"""
    if num is None:
        return 'N/A'
    try:
        return f"{num*100:.2f}%"
    except (ValueError, TypeError):
        return 'N/A'

def format_stock_quote(quote):
    """Format stock quote data for display"""
    result = f"""
Symbol: {quote['symbol']}
Name: {quote['shortName'] or 'N/A'}
Price: ${format_number(quote['regularMarketPrice'])}
Change: ${format_number(quote['regularMarketChange'])} ({format_percent(quote['regularMarketChangePercent'] if quote['regularMarketChangePercent'] is not None else None)})
Previous Close: ${format_number(quote['regularMarketPreviousClose'])}
Open: ${format_number(quote['regularMarketOpen'])}
Day Range: ${format_number(quote['regularMarketDayLow'])} - ${format_number(quote['regularMarketDayHigh'])}
52 Week Range: ${format_number(quote['fiftyTwoWeekLow'])} - ${format_number(quote['fiftyTwoWeekHigh'])}
Volume: {format_number(quote['regularMarketVolume'])}
Avg. Volume: {format_number(quote['averageDailyVolume3Month'])}
Market Cap: ${format_number(quote['marketCap'])}
P/E Ratio: {format_number(quote['trailingPE'])}
EPS: ${format_number(quote['epsTrailingTwelveMonths'])}
Dividend Yield: {format_percent(quote['dividendYield'])}
""".strip()
    
    return result

def format_market_data(indices):
    """Format market indices data for display"""
    result_parts = []
    
    for index in indices:
        change_percent = format_percent(index['regularMarketChangePercent'] if index['regularMarketChangePercent'] is not None else None)
        
        index_data = f"""
{index['shortName'] or index['symbol']}
Price: {format_number(index['regularMarketPrice'])}
Change: {format_number(index['regularMarketChange'])} ({change_percent})
Previous Close: {format_number(index['regularMarketPreviousClose'])}
Day Range: {format_number(index['regularMarketDayLow'])} - {format_number(index['regularMarketDayHigh'])}
""".strip()
        
        result_parts.append(index_data)
    
    return '\n\n'.join(result_parts)

def parse_news_item(item):
    """Parse news item from yfinance"""
    try:
        content = item.get('content', item)
        
        provider_name = "Unknown"
        if 'provider' in content and isinstance(content['provider'], dict):
            provider_name = content['provider'].get('displayName', provider_name)
        
        pub_date = datetime.now().isoformat()
        if 'pubDate' in content:
            pub_date = content['pubDate']
        elif 'providerPublishTime' in content and content['providerPublishTime']:
            pub_date = datetime.fromtimestamp(content['providerPublishTime']).isoformat()
        
        link = ""
        if 'clickThroughUrl' in content and isinstance(content['clickThroughUrl'], dict):
            link = content['clickThroughUrl'].get('url', "")
        elif 'link' in content:
            link = content['link']
        elif 'url' in content:
            link = content['url']
        
        summary = ""
        for field in ['summary', 'description', 'shortDescription', 'longDescription', 'snippetText']:
            if field in content and content[field]:
                summary = content[field]
                break
        
        return {
            "title": content.get("title", "No title available"),
            "publisher": provider_name,
            "link": link,
            "published_date": pub_date,
            "summary": summary
        }
    except Exception as e:
        logger.error(f"Error parsing news item: {str(e)}")
        return None

# Format complex JSON data into readable text
def format_analysis_results(data, indent=0):
    if data is None:
        return "N/A"
    
    if isinstance(data, dict):
        result = ""
        for key, value in data.items():
            formatted_key = key.replace('_', ' ').title()
            
            if isinstance(value, dict) or isinstance(value, list):
                result += f"{' ' * indent}{formatted_key}:\n{format_analysis_results(value, indent + 2)}\n"
            else:
                if isinstance(value, float):
                    if abs(value) < 0.01:  
                        formatted_value = f"{value:.2e}"
                    else:
                        formatted_value = f"{value:.2f}"
                    
                    if "percent" in key.lower() or "growth" in key.lower() or "margin" in key.lower():
                        formatted_value += "%"
                elif isinstance(value, int) and value > 1000:
                    formatted_value = f"{value:,}"  
                else:
                    formatted_value = str(value)
                
                result += f"{' ' * indent}{formatted_key}: {formatted_value}\n"
        return result
    
    elif isinstance(data, list):
        result = ""
        for i, item in enumerate(data):
            result += f"{' ' * indent}{i+1}. {format_analysis_results(item, indent + 2)}\n"
        return result
    
    else:
        return str(data)

# Helper functions for analysis interpretation
def interpret_rsi(rsi: float) -> str:
    if rsi >= 70: return "Overbought"
    elif rsi <= 30: return "Oversold"
    else: return "Neutral"

def interpret_macd(macd: float, signal: float) -> str:
    if macd > signal: return "Bullish"
    elif macd < signal: return "Bearish"
    else: return "Neutral"

def interpret_ma_trend(ma_distances: dict) -> str:
    if ma_distances["from_200sma"] > 0 and ma_distances["from_50sma"] > 0: return "Uptrend"
    elif ma_distances["from_200sma"] < 0 and ma_distances["from_50sma"] < 0: return "Downtrend"
    else: return "Mixed"

def interpret_relative_strength(stock_change: float, sp500_change: float) -> str:
    if stock_change > sp500_change: return "Outperforming market"
    elif stock_change < sp500_change: return "Underperforming market"
    else: return "Market performer"

async def fetch_fundamental_analysis(equity):
    try:
        ticker = yf.Ticker(equity)
        info = ticker.info
        if not info:
            raise ValueError(f"No fundamental data available for {equity}")
        
        return {
            "company_info": {
                "longName": info.get("longName"),
                "shortName": info.get("shortName"),
                "industry": info.get("industry"),
                "sector": info.get("sector"),
                "country": info.get("country"),
                "website": info.get("website"),
                "fullTimeEmployees": info.get("fullTimeEmployees"),
                "longBusinessSummary": info.get("longBusinessSummary")
            },
            "valuation_metrics": {
                "trailingPE": info.get("trailingPE"),
                "forwardPE": info.get("forwardPE"),
                "priceToBook": info.get("priceToBook"),
                "priceToSalesTrailing12Months": info.get("priceToSalesTrailing12Months"),
                "enterpriseValue": info.get("enterpriseValue"),
                "enterpriseToEbitda": info.get("enterpriseToEbitda"),
                "enterpriseToRevenue": info.get("enterpriseToRevenue"),
                "bookValue": info.get("bookValue")
            },
            "earnings_and_revenue": {
                "totalRevenue": info.get("totalRevenue"),
                "revenueGrowth": info.get("revenueGrowth"),
                "revenuePerShare": info.get("revenuePerShare"),
                "ebitda": info.get("ebitda"),
                "ebitdaMargins": info.get("ebitdaMargins"),
                "netIncomeToCommon": info.get("netIncomeToCommon"),
                "earningsGrowth": info.get("earningsGrowth"),
                "earningsQuarterlyGrowth": info.get("earningsQuarterlyGrowth"),
                "forwardEps": info.get("forwardEps"),
                "trailingEps": info.get("trailingEps")
            },
            "margins_and_returns": {
                "profitMargins": info.get("profitMargins"),
                "operatingMargins": info.get("operatingMargins"),
                "grossMargins": info.get("grossMargins"),
                "returnOnEquity": info.get("returnOnEquity"),
                "returnOnAssets": info.get("returnOnAssets")
            },
            "dividends": {
                "dividendYield": info.get("dividendYield"),
                "dividendRate": info.get("dividendRate"),
                "payoutRatio": info.get("payoutRatio"),
                "fiveYearAvgDividendYield": info.get("fiveYearAvgDividendYield")
            },
            "balance_sheet": {
                "totalCash": info.get("totalCash"),
                "totalDebt": info.get("totalDebt"),
                "debtToEquity": info.get("debtToEquity"),
                "currentRatio": info.get("currentRatio"),
                "quickRatio": info.get("quickRatio")
            },
            "ownership": {
                "heldPercentInstitutions": info.get("heldPercentInstitutions"),
                "heldPercentInsiders": info.get("heldPercentInsiders"),
                "floatShares": info.get("floatShares"),
                "sharesOutstanding": info.get("sharesOutstanding"),
                "shortRatio": info.get("shortRatio")
            },
            "analyst_opinions": {
                "recommendationKey": info.get("recommendationKey"),
                "numberOfAnalystOpinions": info.get("numberOfAnalystOpinions"),
                "targetMeanPrice": info.get("targetMeanPrice"),
                "targetHighPrice": info.get("targetHighPrice"),
                "targetLowPrice": info.get("targetLowPrice")
            },
            "risk_metrics": {
                "beta": info.get("beta"),
                "52WeekChange": info.get("52WeekChange"),
                "SandP52WeekChange": info.get("SandP52WeekChange")
            }
        }
    except Exception as e:
        logger.error(f"Error in fundamental analysis for {equity}: {str(e)}")
        raise APIError(f"Fundamental analysis failed: {str(e)}")

async def fetch_technical_analysis(equity):
    try:
        ticker = yf.Ticker(equity)
        hist = ticker.history(period="1y")
        if hist.empty:
            raise ValueError(f"No historical data available for {equity}")

        current_price = hist["Close"].iloc[-1]
        avg_volume = hist["Volume"].mean()

        sma_20 = hist["Close"].rolling(window=20).mean().iloc[-1]
        sma_50 = hist["Close"].rolling(window=50).mean().iloc[-1]
        sma_200 = hist["Close"].rolling(window=200).mean().iloc[-1]

        delta = hist["Close"].diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.rolling(window=14).mean()
        avg_loss = loss.rolling(window=14).mean()
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs)).iloc[-1]

        high_low = hist["High"] - hist["Low"]
        high_close = (hist["High"] - hist["Close"].shift()).abs()
        low_close = (hist["Low"] - hist["Close"].shift()).abs()
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        atr = true_range.rolling(window=14).mean().iloc[-1]

        ema12 = hist["Close"].ewm(span=12, adjust=False).mean()
        ema26 = hist["Close"].ewm(span=26, adjust=False).mean()
        macd = ema12 - ema26
        signal_line = macd.ewm(span=9, adjust=False).mean()
        macd_histogram = macd - signal_line

        price_changes = {
            "1d": hist["Close"].pct_change(periods=1).iloc[-1] * 100,
            "5d": hist["Close"].pct_change(periods=5).iloc[-1] * 100,
            "20d": hist["Close"].pct_change(periods=20).iloc[-1] * 100
        }

        ma_distances = {
            "from_20sma": ((current_price / sma_20) - 1) * 100,
            "from_50sma": ((current_price / sma_50) - 1) * 100,
            "from_200sma": ((current_price / sma_200) - 1) * 100
        }

        return {
            "price": current_price,
            "avg_volume": avg_volume,
            "moving_averages": {
                "sma_20": sma_20,
                "sma_50": sma_50,
                "sma_200": sma_200
            },
            "indicators": {
                "rsi": rsi,
                "atr": atr,
                "atr_percent": (atr / current_price) * 100,
                "macd": macd.iloc[-1],
                "macd_signal": signal_line.iloc[-1],
                "macd_histogram": macd_histogram.iloc[-1]
            },
            "trend_analysis": price_changes,
            "ma_distances": ma_distances
        }
    except Exception as e:
        logger.error(f"Error in technical analysis for {equity}: {str(e)}")
        raise APIError(f"Technical analysis failed: {str(e)}")

async def fetch_comprehensive_analysis(equity):
    try:
        fundamental_data = await fetch_fundamental_analysis(equity)
        technical_data = await fetch_technical_analysis(equity)
        
        current_price = technical_data["price"]
        target_price = fundamental_data["analyst_opinions"]["targetMeanPrice"]
        
        upside_potential = ((target_price / current_price) - 1) * 100 if target_price else None
        
        return {
            "core_valuation": {
                "current_price": current_price,
                "pe_ratio": {
                    "trailing": fundamental_data["valuation_metrics"]["trailingPE"],
                    "forward": fundamental_data["valuation_metrics"]["forwardPE"],
                    "industry_comparison": "Requires industry average PE data"
                },
                "price_to_book": fundamental_data["valuation_metrics"]["priceToBook"],
                "enterprise_to_ebitda": fundamental_data["valuation_metrics"]["enterpriseToEbitda"]
            },
            "growth_metrics": {
                "revenue_growth": fundamental_data["earnings_and_revenue"]["revenueGrowth"],
                "earnings_growth": fundamental_data["earnings_and_revenue"]["earningsGrowth"],
                "profit_margin": fundamental_data["margins_and_returns"]["profitMargins"],
                "return_on_equity": fundamental_data["margins_and_returns"]["returnOnEquity"]
            },
            "financial_health": {
                "debt_to_equity": fundamental_data["balance_sheet"]["debtToEquity"],
                "current_ratio": fundamental_data["balance_sheet"]["currentRatio"],
                "quick_ratio": fundamental_data["balance_sheet"]["quickRatio"],
                "beta": fundamental_data["risk_metrics"]["beta"]
            },
            "market_sentiment": {
                "analyst_recommendation": fundamental_data["analyst_opinions"]["recommendationKey"],
                "target_price": {
                    "mean": target_price,
                    "current": current_price,
                    "upside_potential": upside_potential
                },
                "institutional_holdings": fundamental_data["ownership"]["heldPercentInstitutions"],
                "insider_holdings": fundamental_data["ownership"]["heldPercentInsiders"]
            },
            "technical_signals": {
                "rsi": {
                    "value": technical_data["indicators"]["rsi"],
                    "signal": interpret_rsi(technical_data["indicators"]["rsi"])
                },
                "macd": {
                    "value": technical_data["indicators"]["macd"],
                    "signal": technical_data["indicators"]["macd_signal"],
                    "histogram": technical_data["indicators"]["macd_histogram"],
                    "trend": interpret_macd(
                        technical_data["indicators"]["macd"],
                        technical_data["indicators"]["macd_signal"]
                    )
                },
                "moving_averages": {
                    "sma_50": technical_data["moving_averages"]["sma_50"],
                    "sma_200": technical_data["moving_averages"]["sma_200"],
                    "price_vs_sma200": technical_data["ma_distances"]["from_200sma"],
                    "trend": interpret_ma_trend(technical_data["ma_distances"])
                }
            },
            "momentum": {
                "short_term": technical_data["trend_analysis"]["20d"],
                "year_to_date": fundamental_data["risk_metrics"]["52WeekChange"],
                "relative_strength": {
                    "vs_sp500": fundamental_data["risk_metrics"]["SandP52WeekChange"],
                    "interpretation": interpret_relative_strength(
                        fundamental_data["risk_metrics"]["52WeekChange"],
                        fundamental_data["risk_metrics"]["SandP52WeekChange"]
                    )
                }
            }
        }
    except Exception as e:
        logger.error(f"Error in comprehensive analysis for {equity}: {str(e)}")
        raise APIError(f"Comprehensive analysis failed: {str(e)}")

async def fetch_fundamental_by_groups(equity, groups):
    try:
        full_data = await fetch_fundamental_analysis(equity)
        result = {}
        for group in groups:
            if group in full_data:
                result[group] = full_data[group]
        return result
    except Exception as e:
        logger.error(f"Error in fundamental groups analysis for {equity}: {str(e)}")
        raise APIError(f"Fundamental groups analysis failed: {str(e)}")

# MCP tool definitions
@mcp.tool()
def stock_quote(symbol: str = Field(description="Stock ticker symbol (e.g., AAPL, MSFT, TSLA)")) -> str:
    """
    Get current stock quote information.
    Returns detailed information about a stock including current price,
    day range, 52-week range, market cap, volume, P/E ratio, etc.
    """
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        
        if not info:
            return f"No data found for symbol: {symbol}"
            
        quote_data = {
            "symbol": symbol,
            "shortName": info.get("shortName") or info.get("longName") or symbol,
            "regularMarketPrice": info.get("regularMarketPrice"),
            "regularMarketChange": info.get("regularMarketChange"),
            "regularMarketChangePercent": info.get("regularMarketChangePercent"),
            "regularMarketPreviousClose": info.get("regularMarketPreviousClose"),
            "regularMarketOpen": info.get("regularMarketOpen"),
            "regularMarketDayLow": info.get("regularMarketDayLow"),
            "regularMarketDayHigh": info.get("regularMarketDayHigh"),
            "fiftyTwoWeekLow": info.get("fiftyTwoWeekLow"),
            "fiftyTwoWeekHigh": info.get("fiftyTwoWeekHigh"),
            "regularMarketVolume": info.get("regularMarketVolume"),
            "averageDailyVolume3Month": info.get("averageDailyVolume3Month"),
            "marketCap": info.get("marketCap"),
            "trailingPE": info.get("trailingPE"),
            "epsTrailingTwelveMonths": info.get("epsTrailingTwelveMonths"),
            "dividendYield": info.get("dividendYield")
        }
        
        return format_stock_quote(quote_data)
    except Exception as e:
        logger.error(f"Error in stock_quote: {str(e)}")
        return f"Error retrieving stock quote: {str(e)}"

@mcp.tool()
def stock_history(
    symbol: str = Field(description="Stock ticker symbol (e.g., AAPL, MSFT, TSLA)"),
    period: str = Field(default="1mo", description="Time period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)"),
    interval: str = Field(default="1d", description="Data interval (1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo)")
) -> str:
    """
    Get historical stock data.
    Returns price and volume data for a specified time period.
    Useful for charting, trend analysis, and evaluating stock performance over time.
    """
    try:
        valid_periods = ['1d', '5d', '1mo', '3mo', '6mo', '1y', '2y', '5y', '10y', 'ytd', 'max']
        valid_intervals = ['1m', '2m', '5m', '15m', '30m', '60m', '90m', '1h', '1d', '5d', '1wk', '1mo', '3mo']
        
        if period not in valid_periods:
            raise ValueError(f"Invalid period: {period}. Valid periods are: {', '.join(valid_periods)}")
        
        if interval not in valid_intervals:
            raise ValueError(f"Invalid interval: {interval}. Valid intervals are: {', '.join(valid_intervals)}")
        
        ticker = yf.Ticker(symbol)
        history = ticker.history(period=period, interval=interval)
        
        if history.empty:
            return f"No historical data found for symbol: {symbol}"
        
        result = f"Historical data for {symbol} ({period}, {interval} intervals)\n"
        result += f"Currency: {ticker.info.get('currency', 'USD')}\n\n"
        
        result += "Date       | Open     | High     | Low      | Close    | Volume\n"
        result += "-----------|----------|----------|----------|----------|-----------\n"
        
        max_points = 10
        step = max(1, len(history) // max_points)
        
        for i in range(0, len(history), step):
            date = history.index[i].strftime('%Y-%m-%d')
            
            open_price = history['Open'].iloc[i] if 'Open' in history.columns else None
            high = history['High'].iloc[i] if 'High' in history.columns else None
            low = history['Low'].iloc[i] if 'Low' in history.columns else None
            close = history['Close'].iloc[i] if 'Close' in history.columns else None
            volume = history['Volume'].iloc[i] if 'Volume' in history.columns else None
            
            open_str = f"${open_price:.2f}" if open_price is not None else 'N/A'
            high_str = f"${high:.2f}" if high is not None else 'N/A'
            low_str = f"${low:.2f}" if low is not None else 'N/A'
            close_str = f"${close:.2f}" if close is not None else 'N/A'
            volume_str = f"{volume:,}" if volume is not None else 'N/A'
            
            result += f"{date.ljust(11)} | {open_str.ljust(8)} | {high_str.ljust(8)} | {low_str.ljust(8)} | {close_str.ljust(8)} | {volume_str}\n"
        
        if not history.empty and 'Close' in history.columns:
            first_close = history['Close'].iloc[0]
            last_close = history['Close'].iloc[-1]
            
            change = last_close - first_close
            percent_change = (change / first_close) * 100 if first_close else 0
            
            result += f"\nPrice Change: ${change:.2f} ({percent_change:.2f}%)"
        
        return result
    except Exception as e:
        logger.error(f"Error in stock_history: {str(e)}")
        return f"Error retrieving stock history: {str(e)}"

@mcp.tool()
def market_data(indices: List[str] = Field(default=None, description="List of index symbols (e.g., ^GSPC for S&P 500, ^DJI for Dow Jones)")) -> str:
    """
    Get current market data.
    Returns information about major market indices (like S&P 500, NASDAQ, Dow Jones).
    Use this for broad market overview and current market sentiment.
    """
    try:
        if indices is None:
            indices = ["^GSPC", "^DJI", "^IXIC"]  # Default indices: S&P 500, Dow Jones, NASDAQ
        
        index_results = []
        
        for index_symbol in indices:
            try:
                ticker = yf.Ticker(index_symbol)
                info = ticker.info
                
                if info:
                    index_results.append({
                        "symbol": index_symbol,
                        "shortName": info.get('shortName') or info.get('longName') or index_symbol,
                        "regularMarketPrice": info.get('regularMarketPrice'),
                        "regularMarketChange": info.get('regularMarketChange'),
                        "regularMarketChangePercent": info.get('regularMarketChangePercent'),
                        "regularMarketPreviousClose": info.get('regularMarketPreviousClose'),
                        "regularMarketDayHigh": info.get('regularMarketDayHigh'),
                        "regularMarketDayLow": info.get('regularMarketDayLow')
                    })
            except Exception as error:
                logger.error(f"Failed to fetch data for index: {index_symbol}. Error: {str(error)}")
        
        if index_results:
            return format_market_data(index_results)
        
        return "Unable to retrieve market data. Data may be temporarily unavailable."
    except Exception as e:
        return f"Error retrieving market data: {str(e)}"

@mcp.tool()
def financial_news(
    symbol: str = Field(description="Stock ticker symbol (e.g., AAPL, MSFT, TSLA)"),
    count: int = Field(default=5, description="Number of news articles to return (1-20)")
) -> str:
    """Get the latest financial news for a specific stock ticker symbol."""
    try:
        if not symbol or len(symbol.strip()) == 0:
            return "Please provide a valid stock ticker symbol."
        
        symbol = symbol.strip().upper()
        count = min(max(count, 1), 20)
        
        logger.info(f"Getting latest news for ticker: {symbol}, count: {count}")
        
        ticker = yf.Ticker(symbol)
        news_data = ticker.news
        
        if not news_data:
            logger.info(f"No news found for ticker {symbol}")
            return f"No recent news found for {symbol}."

        logger.info(f"Found {len(news_data)} news articles for {symbol}")
            
        formatted_news = []
        news_count = min(count, len(news_data))
        
        for item in news_data[:news_count]: 
            parsed_item = parse_news_item(item)
            if parsed_item:
                formatted_news.append(parsed_item)
        
        if not formatted_news:
            return f"No news articles could be processed for {symbol}."
            
        result = f"Latest news for {symbol} ({len(formatted_news)} articles):\n\n"
        for i, item in enumerate(formatted_news, 1):
            result += f"{i}. {item['title']}\n"
            result += f"   Publisher: {item['publisher']}\n"
            result += f"   Date: {item['published_date']}\n"
            if item['summary']:
                result += f"   Summary: {item['summary']}\n"
            if item['link']:
                result += f"   Link: {item['link']}\n"
            result += "\n"
                
        return result
            
    except Exception as e:
        logger.error(f"Error in financial_news: {str(e)}")
        return f"Error retrieving financial news: {str(e)}"

@mcp.tool()
def fundamental_data_by_category(
    equity: str = Field(description="Stock ticker symbol (e.g., AAPL, MSFT, TSLA)"),
    categories: str = Field(description="Comma-separated categories: company_info, valuation_metrics, earnings_and_revenue, margins_and_returns, dividends, balance_sheet, ownership, analyst_opinions, risk_metrics")
) -> str:
    """
    Get specific categories of fundamental data for a company.
    Available categories: company_info, valuation_metrics, earnings_and_revenue,
    margins_and_returns, dividends, balance_sheet, ownership, analyst_opinions, risk_metrics
    """
    try:
        category_list = []
        if categories.startswith('[') and categories.endswith(']'):
            import json
            try:
                category_list = json.loads(categories)
            except json.JSONDecodeError:
                category_list = [cat.strip() for cat in categories.strip('[]').split(',')] 
        else:
            category_list = [cat.strip() for cat in categories.split(',')]
            
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            data = loop.run_until_complete(fetch_fundamental_by_groups(equity, category_list))
            return format_analysis_results(data)
        finally:
            loop.close()
    except Exception as e:
        return f"Error retrieving fundamental data: {str(e)}"

@mcp.tool()
def comprehensive_analysis(equity: str = Field(description="Stock ticker symbol (e.g., AAPL, MSFT, TSLA)")) -> str:
    """
    Get complete investment analysis combining both fundamental and technical factors.
    Provides a holistic view of a stock with interpreted signals, valuation assessment,
    growth metrics, financial health indicators, and momentum analysis with clear buy/sell signals.
    """
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            data = loop.run_until_complete(fetch_comprehensive_analysis(equity))
            return format_analysis_results(data)
        finally:
            loop.close()
    except Exception as e:
        return f"Error retrieving comprehensive analysis: {str(e)}"