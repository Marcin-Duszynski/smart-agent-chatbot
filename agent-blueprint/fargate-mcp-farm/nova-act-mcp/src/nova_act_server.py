import os
import sys
import asyncio
import logging
import traceback
import json
import signal
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
from datetime import datetime, timedelta
from fastmcp import FastMCP

# Import these with try/except to handle different FastMCP versions
try:
    from fastmcp.utilities.types import Image
except ImportError:
    try:
        from fastmcp.types import Image
    except ImportError:
        # Fallback to basic type
        Image = bytes

try:
    from fastmcp.server.dependencies import get_http_headers
except ImportError:
    # Fallback function
    def get_http_headers():
        return {}
from browser_controller import BrowserController
from nova_act_config import DEFAULT_BROWSER_SETTINGS

# Tool modules are organized below in sections:
# 1. Nova Act Native Tools (High-level natural language)
# 2. Playwright/JavaScript Tools (Low-level direct control)

_session_thread_pools = {}  # Dict[session_id, ThreadPoolExecutor]

def create_fastmcp_response(status: str, message: str, screenshot_data: Dict[str, Any], additional_data: Dict[str, Any] = None) -> Union[List[Any], str]:
    """Create FastMCP response - return list with text and Image object"""
    import base64
    
    # Build response items
    response_items = []
    
    # Add text message
    response_items.append(message)
    
    # Add additional data as JSON if provided
    if additional_data:
        import json
        response_items.append(json.dumps(additional_data, indent=2))
    
    # Add image if screenshot is available
    if screenshot_data and screenshot_data.get("data"):
        try:
            image_bytes = base64.b64decode(screenshot_data["data"])
            
            # Create FastMCP Image object
            screenshot_image = Image(
                data=image_bytes,
                format=screenshot_data.get("format", "jpeg")
            )
            response_items.append(screenshot_image)
            
            print(f"📷 Created FastMCP response with Image object ({len(image_bytes)} bytes)")
            
        except Exception as e:
            print(f"❌ Failed to process screenshot: {e}")
    
    # Return list of items for FastMCP to process
    return response_items

try:
    from dotenv import load_dotenv
    # Find .env file in py-backend directory
    env_path = Path(__file__).parent.parent.parent.parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        logging.info(f"Loaded .env from: {env_path}")
    else:
        logging.debug(f".env file not found at: {env_path} (this is normal in containerized environments)")
except ImportError:
    logging.warning("python-dotenv not available, skipping .env file loading")

logging.basicConfig(
    level=logging.DEBUG,
    format='[MCP] %(levelname)s - %(name)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger("browser_mcp")
logger.setLevel(logging.DEBUG)

mcp = FastMCP("browser-automation")

# Multiple browser controllers for different sessions (HTTP mode)
_browser_controllers = {}  # Dict[session_id, BrowserController]
_session_metadata = {}     # Dict[session_id, dict] - TTL and activity tracking
_shutdown_event = None
_is_shutting_down = False

# Session management settings - hardcoded defaults
SESSION_TTL_SECONDS = 600  # 10 minutes
SESSION_CLEANUP_INTERVAL = 60  # 1 minute  
DEFAULT_HEADLESS_MODE = True  # Default headless setting

# Screenshot streaming management - removed (not needed for basic MCP operation)

def _nova_thread_initializer():
    """Initialize Nova Act thread with isolated asyncio context"""
    import asyncio
    try:
        # Remove any existing event loop
        asyncio.set_event_loop(None)
    except:
        pass
    
    try:
        # Create a fresh event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        logger.debug("Nova Act thread initialized with fresh event loop")
    except Exception as e:
        logger.warning(f"Failed to initialize Nova Act thread: {e}")

def get_session_thread_pool(session_id: str) -> ThreadPoolExecutor:
    """Get or create a dedicated ThreadPoolExecutor for a specific session"""
    global _session_thread_pools
    
    if session_id not in _session_thread_pools:
        _session_thread_pools[session_id] = ThreadPoolExecutor(
            max_workers=1,  # Nova Act recommends single thread per session
            thread_name_prefix=f"nova-session-{session_id}-",
            initializer=_nova_thread_initializer
        )
        logger.info(f"Created dedicated ThreadPool for session {session_id}")
    
    return _session_thread_pools[session_id]

def shutdown_session_thread_pool(session_id: str):
    """Shutdown ThreadPoolExecutor for a specific session"""
    global _session_thread_pools
    
    if session_id in _session_thread_pools:
        executor = _session_thread_pools[session_id]
        executor.shutdown(wait=True)
        del _session_thread_pools[session_id]
        logger.info(f"Shut down ThreadPool for session {session_id}")

def shutdown_all_session_thread_pools():
    """Shutdown all session ThreadPoolExecutors"""
    global _session_thread_pools
    
    for session_id in list(_session_thread_pools.keys()):
        shutdown_session_thread_pool(session_id)

def update_session_activity(session_id: str, headless: bool = None):
    """Update the last activity timestamp for a session"""
    global _session_metadata
    
    now = datetime.now()
    if session_id not in _session_metadata:
        # Use hardcoded default headless setting if not specified
        _session_metadata[session_id] = {
            'created_at': now,
            'last_activity': now,
            'request_count': 0,
            'ttl_seconds': SESSION_TTL_SECONDS,
            'headless': headless if headless is not None else DEFAULT_HEADLESS_MODE
        }
    else:
        # Update headless setting if provided
        if headless is not None:
            _session_metadata[session_id]['headless'] = headless
    
    _session_metadata[session_id]['last_activity'] = now
    _session_metadata[session_id]['request_count'] += 1
    logger.debug(f"Updated activity for session {session_id}, headless: {_session_metadata[session_id]['headless']}")

def get_or_create_browser(session_id: str, headless: bool = None) -> BrowserController:
    """Get existing browser controller or create new one for session"""
    global _browser_controllers
    
    # Try to get headless setting from headers if not explicitly provided
    if headless is None:
        headless = get_headless_from_headers()
    
    # Update session activity and headless setting
    update_session_activity(session_id, headless)
    
    # Check if browser exists and is initialized
    if session_id in _browser_controllers:
        browser = _browser_controllers[session_id]
        if browser and browser.is_initialized():
            logger.debug(f"Using existing browser for session {session_id}")
            return browser
        else:
            logger.info(f"Browser for session {session_id} not initialized, creating new one")
    
    # Create new browser controller
    browser = BrowserController(session_id=session_id)
    _browser_controllers[session_id] = browser
    logger.info(f"Created new browser controller for session {session_id}")
    
    return browser

def get_session_headless_setting(session_id: str) -> bool:
    """Get headless setting for a specific session"""
    global _session_metadata
    if session_id in _session_metadata:
        return _session_metadata[session_id].get('headless', DEFAULT_HEADLESS_MODE)
    return DEFAULT_HEADLESS_MODE

def _calculate_element_relevance_score(element: Dict[str, Any], keywords: List[str]) -> int:
    """Calculate relevance score for an element based on keywords"""
    score = 0
    
    # Extract searchable text from element
    searchable_texts = []
    
    # Text content
    text_content = element.get('text', {})
    if text_content.get('content'):
        searchable_texts.append(text_content['content'].lower())
    if text_content.get('label'):
        searchable_texts.append(text_content['label'].lower())
    if text_content.get('placeholder'):
        searchable_texts.append(text_content['placeholder'].lower())
    
    # Attributes
    attributes = element.get('attributes', {})
    for attr_key, attr_value in attributes.items():
        if attr_value and isinstance(attr_value, str):
            searchable_texts.append(attr_value.lower())
    
    # Selectors (class names, IDs)
    selectors = element.get('selectors', {})
    for selector_type, selector_value in selectors.items():
        if selector_value and isinstance(selector_value, str):
            searchable_texts.append(selector_value.lower())
    
    # Score calculation
    for keyword in keywords:
        keyword_lower = keyword.lower()
        
        for text in searchable_texts:
            if keyword_lower in text:
                # Exact match gets higher score
                if keyword_lower == text.strip():
                    score += 10
                # Partial match in ID or class gets high score
                elif any(keyword_lower in attr.lower() for attr in [
                    attributes.get('id', ''), 
                    attributes.get('class', ''),
                    attributes.get('name', '')
                ] if attr):
                    score += 8
                # Partial match in text content
                elif keyword_lower in text_content.get('content', '').lower():
                    score += 6
                # Partial match in other text
                else:
                    score += 3
    
    # Element type bonuses
    tag = element.get('tag', '').lower()
    if tag in ['button', 'input', 'select', 'a']:
        score += 2  # Interactive elements get slight bonus
    
    # Visibility bonus
    state = element.get('state', {})
    if state.get('visible', False):
        score += 1
    
    return score

def cleanup_expired_sessions():
    """Clean up expired sessions based on TTL"""
    global _browser_controllers, _session_metadata
    
    if _is_shutting_down:
        return
    
    now = datetime.now()
    expired_sessions = []
    
    for session_id, metadata in _session_metadata.items():
        last_activity = metadata['last_activity']
        ttl_seconds = metadata['ttl_seconds']
        
        if now - last_activity > timedelta(seconds=ttl_seconds):
            expired_sessions.append(session_id)
    
    for session_id in expired_sessions:
        logger.info(f"Session {session_id} expired, cleaning up")
        
        
        # Close browser if exists
        if session_id in _browser_controllers:
            try:
                browser = _browser_controllers[session_id]
                if browser:
                    browser.close()
                del _browser_controllers[session_id]
                logger.info(f"Closed expired browser for session {session_id}")
            except Exception as e:
                logger.error(f"Error closing expired browser for session {session_id}: {e}")
        
        # Shutdown thread pool
        try:
            shutdown_session_thread_pool(session_id)
        except Exception as e:
            logger.error(f"Error shutting down thread pool for session {session_id}: {e}")
        
        # Remove metadata
        if session_id in _session_metadata:
            del _session_metadata[session_id]
    
    if expired_sessions:
        logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")

async def session_cleanup_task():
    """Background task to clean up expired sessions"""
    while not _is_shutting_down:
        try:
            cleanup_expired_sessions()
            await asyncio.sleep(SESSION_CLEANUP_INTERVAL)
        except Exception as e:
            logger.error(f"Error in session cleanup task: {e}")
            await asyncio.sleep(SESSION_CLEANUP_INTERVAL)

# Screenshot streaming functionality removed - not needed for basic MCP operation

async def run_in_session_thread(session_id: str, func, *args, **kwargs):
    """Execute function in dedicated session thread (Nova Act SDK recommended approach)"""
    executor = get_session_thread_pool(session_id)
    loop = asyncio.get_event_loop()
    
    def wrapper():
        return func(*args, **kwargs)
    
    logger.debug(f"Executing {func.__name__} in session {session_id} thread")
    return await loop.run_in_executor(executor, wrapper)

def format_log_response(response_data):
    if isinstance(response_data, dict):
        simplified = {
            "status": response_data.get("status", "unknown"),
            "message": response_data.get("message", "")
        }
        if "current_url" in response_data:
            simplified["current_url"] = response_data["current_url"]
        if "page_title" in response_data:
            simplified["page_title"] = response_data["page_title"]
        return json.dumps(simplified)
    return str(response_data)

def get_session_id_from_context() -> str:
    """Extract session ID from current context"""
    try:
        headers = get_http_headers()
        session_id = headers.get("x-session-id") or headers.get("X-Session-ID")
        if session_id:
            logger.debug(f"Got session ID from HTTP header: {session_id}")
            return session_id
        else:
            logger.warning(f"No session ID in headers. Available headers: {list(headers.keys())}")
    except Exception as e:
        logger.warning(f"Failed to get HTTP headers: {e}")
        # Not in HTTP context, try environment variable
        session_id = os.environ.get("BROWSER_SESSION_ID")
        if session_id:
            return session_id
    
    logger.warning("No session ID provided - using default session")
    return "default"

def get_headless_from_headers() -> bool:
    """Extract headless setting from HTTP headers"""
    try:
        headers = get_http_headers()
        headless_header = headers.get("x-browser-headless") or headers.get("X-Browser-Headless")
        if headless_header:
            headless_value = headless_header.lower() in ("true", "1", "yes")
            logger.debug(f"Got headless setting from HTTP header: {headless_value}")
            return headless_value
    except Exception as e:
        logger.debug(f"No headless header found or error reading headers: {e}")
    
    return None  # No header provided

def get_browser_controller(session_id: str = None) -> BrowserController:
    global _browser_controllers
    
    if _is_shutting_down:
        return None
    
    # Get session_id from context if not provided
    if not session_id:
        session_id = get_session_id_from_context()
    
    # Create or get controller for this session
    if session_id not in _browser_controllers:
        logger.info(f"Creating new browser controller for session: {session_id}")
        _browser_controllers[session_id] = BrowserController(session_id=session_id)
    else:
        logger.debug(f"Reusing existing browser controller for session: {session_id}")
    
    return _browser_controllers[session_id]

def create_error_response(e: Exception, context: str) -> Dict[str, Any]:
    logger.error(f"Error in {context}: {str(e)}")
    return {
        "status": "error",
        "message": f"Failed to {context}: {str(e)}"
    }

# ============================================================================
# NOVA ACT NATIVE TOOLS - High-level natural language browser automation
# ============================================================================

@mcp.tool()
async def navigate(url: str) -> Union[Dict[str, Any], Image]:
    """
    Navigate browser to a specified URL. Browser will be automatically initialized if needed.
    
    Args:
        url: Complete URL to navigate to (e.g., 'https://www.amazon.com' or 'https://www.google.com/search?q=shoes')
              URLs without protocol will automatically have 'https://' added
    """
    try:
        session_id = get_session_id_from_context()
        browser = get_or_create_browser(session_id)
        
        # Auto-initialize browser if not already initialized
        if not await run_in_session_thread(session_id, browser.is_initialized):
            session_headless = get_session_headless_setting(session_id)
            logger.info(f"Auto-initializing browser for session {session_id} (headless: {session_headless})")
            init_result = await run_in_session_thread(
                session_id, 
                browser.initialize_browser, 
                headless=session_headless,
                starting_url=url
            )
            if not init_result[0]:  # initialization failed
                return {"status": "error", "message": f"Failed to initialize browser: {init_result[2]}"}
        
        result = await run_in_session_thread(session_id, browser.go_to_url, url)
        
        # Create lightweight response without full base64 screenshot data
        screenshot_data = result.get("screenshot", {})
        page_title = await run_in_session_thread(session_id, browser.get_page_title)
        message = f"Navigated to {url}"
        
        additional_data = {
            "current_url": result["current_url"],
            "page_title": page_title
        }
        
        # Create response with text and separate image
        logger.info(f"Navigation completed to {url}")
        return create_fastmcp_response("success", message, screenshot_data, additional_data)
    except Exception as e:
        return create_error_response(e, "navigate to URL")

@mcp.tool()
async def act(instruction: str) -> Union[Dict[str, Any], Image]:
    """
    Execute browser actions using natural language instructions focused on visible elements.
    OPTIMAL: Complete focused tasks using CURRENTLY VISIBLE elements within 2 steps.
    
    Args:
        instruction: Natural language description of what to do with CURRENTLY VISIBLE elements.
                   Be specific about visual characteristics like color, text, position, and size.
                   Focus on completing a focused task that can be done with visible elements in 1-2 steps.
                   
                   PREFERRED - Focused tasks (max 2 steps):
                   - "Click the blue 'Sign Up' button in the top right corner"
                   - "Type 'hiking boots' into the search box and press Enter"
                   - "Click the 'State' dropdown menu and select 'California'"
                   - "Fill out the visible login form with username field"
                   - "Click 'Add to Cart' button"
                   
                   GOOD - Multi-step but logical:
                   - "Open the user menu, then click 'Profile Settings'"
                   - "Click 'Filter' dropdown, select 'Price: Low to High', then click Apply"
                   
                   AVOID - Workflows requiring scrolling or navigation to new pages:
                   - "Fill out entire registration form across multiple screens"
                   - "Navigate through multiple pages to complete checkout"
                   
                   Break complex workflows into logical chunks per screen/view.
    """
    try:
        session_id = get_session_id_from_context()
        browser = get_or_create_browser(session_id)
        
        # Auto-initialize browser if not already initialized
        if not await run_in_session_thread(session_id, browser.is_initialized):
            session_headless = get_session_headless_setting(session_id)
            logger.info(f"Auto-initializing browser for session {session_id} (headless: {session_headless})")
            init_result = await run_in_session_thread(
                session_id, 
                browser.initialize_browser, 
                headless=session_headless
            )
            if not init_result[0]:  # initialization failed
                return {"status": "error", "message": f"Failed to initialize browser: {init_result[2]}"}
        
        # Always use 3 steps for focused tasks
        max_steps = 3
        timeout = DEFAULT_BROWSER_SETTINGS.get("timeout", 300)
        
        result = await run_in_session_thread(
            session_id,
            browser.execute_action, 
            instruction,
            max_steps=max_steps, 
            timeout=timeout
        )
        
        screenshot_data = await run_in_session_thread(session_id, browser.take_screenshot)
        current_url = await run_in_session_thread(session_id, browser.get_current_url)
        page_title = await run_in_session_thread(session_id, browser.get_page_title)
        
        # Add URL to screenshot data for reference
        if screenshot_data:
            screenshot_data["url"] = current_url
        
        additional_data = {
            "instruction": instruction,
            "current_url": current_url,
            "page_title": page_title
        }
        
        if hasattr(result, 'parsed_response') and result.parsed_response:
            status = "success" if result.parsed_response.get("success", False) else "error"
            message = result.parsed_response.get("details", "No details provided")
            return create_fastmcp_response(status, message, screenshot_data, additional_data)
        else:
            return create_fastmcp_response("completed", "Action completed", screenshot_data, additional_data)
    except Exception as e:
        error_str = str(e)
        screenshot_data = {}
        current_url = ""
        page_title = ""
        
        try:
            session_id = get_session_id_from_context()
            browser = get_browser_controller(session_id)
            if await run_in_session_thread(session_id, browser.is_initialized):
                screenshot_data = await run_in_session_thread(session_id, browser.take_screenshot)
                current_url = await run_in_session_thread(session_id, browser.get_current_url)
                page_title = await run_in_session_thread(session_id, browser.get_page_title)
        except:
            pass
            
        if "ActExceededMaxStepsError" in error_str:
            if screenshot_data:
                screenshot_data["url"] = current_url
            additional_data = {
                "technical_details": error_str,
                "instruction": instruction,
                "current_url": current_url,
                "page_title": page_title
            }
            return create_fastmcp_response(
                "in_progress", 
                "I'm still analyzing the page to find what you're looking for. Here's what I see so far.",
                screenshot_data,
                additional_data
            )
        
        return create_error_response(e, f"perform action: {instruction}")

@mcp.tool()
async def extract(
    description: str,
    schema_type: str = "bool",
    custom_schema: Optional[str] = None
) -> Union[Dict[str, Any], Image]:
    """
    Extract data from the current page based on the provided description and schema.
    
    Args:
        description: Detailed description of the data to extract
        schema_type: Type of schema to use. Options:
                    - 'bool': Simple yes/no or true/false result (default)
                    - 'product': Product information (name, price, description, availability)
                    - 'search_result': Search results list (title, url, description)
                    - 'form': Form fields information (name, type, value, required)
                    - 'navigation': Navigation links (text, url, current_page)
                    - 'custom': Use custom JSON schema (requires custom_schema parameter)
        custom_schema: JSON schema as string when schema_type is 'custom'.
                      Example: '{"type": "object", "properties": {"title": {"type": "string"}, "url": {"type": "string"}}}'
    """
    try:
        session_id = get_session_id_from_context()
        browser = get_browser_controller(session_id)
        
        if not await run_in_session_thread(session_id, browser.is_initialized):
            return {"status": "error", "message": "Browser not initialized"}
        
        schema = None
        if schema_type == "custom":
            if not custom_schema:
                return {
                    "status": "error",
                    "message": "custom_schema parameter is required when schema_type is 'custom'"
                }
            try:
                schema = json.loads(custom_schema)
            except json.JSONDecodeError as e:
                return {
                    "status": "error",
                    "message": f"Invalid JSON in custom_schema: {str(e)}"
                }
        elif schema_type == "product":
            # Basic product schema
            schema = {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "price": {"type": "string"},
                    "description": {"type": "string"},
                    "availability": {"type": "string"}
                }
            }
        elif schema_type == "search_result":
            # Basic search result schema
            schema = {
                "type": "object",
                "properties": {
                    "results": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string"},
                                "url": {"type": "string"},
                                "description": {"type": "string"}
                            }
                        }
                    }
                }
            }
        elif schema_type == "form":
            # Basic form fields schema
            schema = {
                "type": "object",
                "properties": {
                    "fields": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "type": {"type": "string"},
                                "value": {"type": "string"},
                                "required": {"type": "boolean"}
                            }
                        }
                    }
                }
            }
        elif schema_type == "navigation":
            # Basic navigation schema
            schema = {
                "type": "object",
                "properties": {
                    "links": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "text": {"type": "string"},
                                "url": {"type": "string"}
                            }
                        }
                    },
                    "current_page": {"type": "string"}
                }
            }
        elif schema_type == "bool":
            # Basic boolean schema
            schema = {
                "type": "object",
                "properties": {
                    "result": {"type": "boolean"},
                    "details": {"type": "string"}
                }
            }
        elif schema_type not in ["bool", "product", "search_result", "form", "navigation", "custom"]:
            return {
                "status": "error",
                "message": f"Invalid schema_type: {schema_type}. Valid options: bool, product, search_result, form, navigation, custom"
            }
        
        prompt = f"{description} from the current webpage"
        
        max_steps = DEFAULT_BROWSER_SETTINGS.get("max_steps", 30)
        timeout = DEFAULT_BROWSER_SETTINGS.get("timeout", 300)
        
        result = await run_in_session_thread(
            session_id,
            browser.execute_action, 
            prompt, 
            schema=schema,
            max_steps=max_steps, 
            timeout=timeout
        )
        
        screenshot_data = await run_in_session_thread(session_id, browser.take_screenshot)
        current_url = await run_in_session_thread(session_id, browser.get_current_url)
        page_title = await run_in_session_thread(session_id, browser.get_page_title)
        
        # Add URL to screenshot data for reference
        if screenshot_data:
            screenshot_data["url"] = current_url
        
        additional_data = {
            "schema_type": schema_type,
            "current_url": current_url,
            "page_title": page_title
        }
        
        if hasattr(result, 'parsed_response') and result.parsed_response:
            additional_data["data"] = result.parsed_response
            return create_fastmcp_response("success", "Data extracted successfully", screenshot_data, additional_data)
        else:
            additional_data["data"] = getattr(result, "response", {})
            return create_fastmcp_response("partial_success", "Data extraction completed but structured response not available", screenshot_data, additional_data)
    except Exception as e:
        return create_error_response(e, "extract data")

# ============================================================================
# PLAYWRIGHT/JAVASCRIPT TOOLS - Low-level direct browser control
# ============================================================================

@mcp.tool()
async def get_page_structure(focus_keywords: Optional[str] = None) -> Union[Dict[str, Any], Image]:
    """
    Get detailed structure of the current page including all interactive elements with their properties.
    This provides comprehensive information needed for precise browser automation.
    
    Args:
        focus_keywords: Optional comma-separated keywords (max 10) to focus on when page structure is too large.
                       Examples: "search,filter,sort" or "checkout,cart,payment" or "login,signup,account"
                       The filtered elements will retain all necessary information for JavaScript execution and quick_action.
    
    Returns detailed page structure with elements, selectors, states, and bounding boxes.
    When structure is too large, prioritizes elements matching focus_keywords.
    """
    try:
        session_id = get_session_id_from_context()
        browser = get_or_create_browser(session_id)
        
        # Ensure browser is initialized
        if not await run_in_session_thread(session_id, browser.is_initialized):
            initialize_result = await run_in_session_thread(
                session_id, browser.initialize_browser, True, None
            )
            if not initialize_result[0]:
                return {
                    "status": "error",
                    "message": "Failed to initialize browser"
                }
        
        # Get page structure using JavaScript evaluation
        structure_script = """
        () => {
            const elements = [];
            const forms = [];
            
            // Helper function to generate unique ref
            function generateRef(element, index) {
                return `ref-${element.tagName.toLowerCase()}-${index}`;
            }
            
            // Helper function to get element selectors
            function getSelectors(element) {
                const selectors = {};
                
                // CSS selector
                if (element.id) {
                    selectors.css = `#${element.id}`;
                } else if (element.className) {
                    selectors.css = `.${element.className.split(' ')[0]}`;
                } else {
                    selectors.css = element.tagName.toLowerCase();
                }
                
                // XPath
                selectors.xpath = getElementXPath(element);
                
                // ARIA
                const role = element.getAttribute('role') || element.tagName.toLowerCase();
                const name = element.getAttribute('aria-label') || element.getAttribute('name') || element.textContent.trim().substring(0, 50);
                if (name) {
                    selectors.aria = `${role}[name='${name}']`;
                }
                
                return selectors;
            }
            
            // Helper function to get XPath
            function getElementXPath(element) {
                if (element.id !== '') {
                    return `//*[@id="${element.id}"]`;
                }
                if (element === document.body) {
                    return '//body';
                }
                
                let ix = 0;
                const siblings = element.parentNode.childNodes;
                for (let i = 0; i < siblings.length; i++) {
                    const sibling = siblings[i];
                    if (sibling === element) {
                        return getElementXPath(element.parentNode) + '/' + element.tagName.toLowerCase() + '[' + (ix + 1) + ']';
                    }
                    if (sibling.nodeType === 1 && sibling.tagName === element.tagName) {
                        ix++;
                    }
                }
            }
            
            // Helper function to get bounding box
            function getBoundingBox(element) {
                const rect = element.getBoundingClientRect();
                return {
                    x: Math.round(rect.x),
                    y: Math.round(rect.y),
                    width: Math.round(rect.width),
                    height: Math.round(rect.height)
                };
            }
            
            // Helper function to get element state
            function getElementState(element) {
                const computedStyle = window.getComputedStyle(element);
                return {
                    visible: computedStyle.display !== 'none' && computedStyle.visibility !== 'hidden' && element.offsetParent !== null,
                    enabled: !element.disabled,
                    focused: document.activeElement === element,
                    checked: element.checked || false,
                    selected: element.selected || false,
                    value: element.value || '',
                    clickable: element.tagName.toLowerCase() === 'button' || 
                              element.tagName.toLowerCase() === 'a' ||
                              element.onclick !== null ||
                              element.getAttribute('onclick') !== null ||
                              computedStyle.cursor === 'pointer'
                };
            }
            
            // Get interactive elements
            const interactive_selectors = [
                'input', 'button', 'select', 'textarea', 'a[href]', 
                '[onclick]', '[role="button"]', '[tabindex]',
                'form', 'label', '[contenteditable="true"]'
            ];
            
            let elementIndex = 0;
            interactive_selectors.forEach(selector => {
                document.querySelectorAll(selector).forEach(element => {
                    const ref = generateRef(element, elementIndex++);
                    element.setAttribute('data-ref', ref);
                    
                    const elementInfo = {
                        ref: ref,
                        tag: element.tagName.toLowerCase(),
                        type: element.type || null,
                        selectors: getSelectors(element),
                        attributes: {
                            id: element.id || null,
                            name: element.name || null,
                            class: element.className || null,
                            placeholder: element.placeholder || null,
                            required: element.required || false,
                            disabled: element.disabled || false
                        },
                        state: getElementState(element),
                        boundingBox: getBoundingBox(element),
                        text: {
                            content: element.textContent ? element.textContent.trim().substring(0, 100) : '',
                            label: element.getAttribute('aria-label') || 
                                   (element.labels && element.labels[0] ? element.labels[0].textContent.trim() : ''),
                            placeholder: element.placeholder || ''
                        }
                    };
                    
                    elements.push(elementInfo);
                });
            });
            
            // Get forms
            document.querySelectorAll('form').forEach((form, index) => {
                const formRef = `ref-form-${index}`;
                const fieldRefs = [];
                
                form.querySelectorAll('input, select, textarea, button').forEach(field => {
                    const fieldRef = field.getAttribute('data-ref');
                    if (fieldRef) {
                        fieldRefs.push(fieldRef);
                    }
                });
                
                forms.push({
                    ref: formRef,
                    selector: form.id ? `#${form.id}` : `form:nth-of-type(${index + 1})`,
                    fields: fieldRefs,
                    action: form.action || '',
                    method: form.method || 'get'
                });
            });
            
            // Summary counts
            const summary = {
                buttons: document.querySelectorAll('button, input[type="button"], input[type="submit"]').length,
                inputs: document.querySelectorAll('input').length,
                links: document.querySelectorAll('a[href]').length,
                dropdowns: document.querySelectorAll('select').length,
                forms: document.querySelectorAll('form').length
            };
            
            return {
                url: window.location.href,
                title: document.title,
                viewport: {
                    width: window.innerWidth,
                    height: window.innerHeight
                },
                elements: elements,
                forms: forms,
                interactable_summary: summary
            };
        }
        """
        
        # Execute the structure analysis script
        structure_data = await run_in_session_thread(
            session_id,
            lambda: browser.nova.page.evaluate(structure_script)
        )
        
        # Get current screenshot for reference
        screenshot_data = await run_in_session_thread(session_id, browser.take_screenshot)
        
        # Add URL to screenshot data for reference
        if screenshot_data:
            screenshot_data["url"] = structure_data.get('url', '')
        
        additional_data = {
            "structure": structure_data
        }
        
        # Log structure data size and details
        import json
        original_elements_count = len(structure_data.get('elements', []))
        forms_count = len(structure_data.get('forms', []))
        
        # Check if structure is too large and apply keyword-based filtering if needed
        structure_json = json.dumps(structure_data)
        MAX_SIZE = 300000  # 300KB threshold
        
        if len(structure_json) > MAX_SIZE and focus_keywords:
            print(f"⚠️  PAGE STRUCTURE: Too large ({len(structure_json)} chars), applying keyword filtering")
            keywords = [kw.strip().lower() for kw in focus_keywords.split(',')][:10]  # Limit to max 10 keywords
            print(f"🔍 Filtering by keywords: {keywords}")
            
            # Score and filter elements based on keyword relevance
            scored_elements = []
            essential_elements = []  # Always include these for completeness
            
            for element in structure_data.get('elements', []):
                # Always include essential interactive elements regardless of keywords
                tag = element.get('tag', '').lower()
                element_type = element.get('type', '').lower()
                if tag == 'form' or element_type in ['submit', 'button'] or tag == 'button':
                    essential_elements.append((999, element))  # High priority score
                
                score = _calculate_element_relevance_score(element, keywords)
                if score > 0:  # Only include elements with some relevance
                    scored_elements.append((score, element))
            
            # Combine essential and scored elements, remove duplicates
            all_scored = essential_elements + scored_elements
            seen_refs = set()
            unique_elements = []
            for score, element in all_scored:
                ref = element.get('ref', '')
                if ref not in seen_refs:
                    seen_refs.add(ref)
                    unique_elements.append((score, element))
            
            scored_elements = unique_elements
            
            # Sort by score (highest first) and take top elements that fit within size limit
            scored_elements.sort(key=lambda x: x[0], reverse=True)
            
            # Incrementally add elements until we reach a reasonable size
            filtered_elements = []
            temp_structure = structure_data.copy()
            
            for score, element in scored_elements:
                temp_structure['elements'] = filtered_elements + [element]
                temp_json = json.dumps(temp_structure)
                if len(temp_json) > MAX_SIZE and len(filtered_elements) > 20:  # Keep at least 20 elements
                    break
                filtered_elements.append(element)
            
            structure_data['elements'] = filtered_elements
            structure_json = json.dumps(structure_data)
            
            print(f"🎯 Filtered to {len(filtered_elements)} most relevant elements")
            print(f"📊 Top scored elements:")
            for i, (score, element) in enumerate(scored_elements[:5]):
                element_desc = f"{element.get('tag', 'unknown')}#{element.get('attributes', {}).get('id', '')} - {element.get('text', {}).get('content', '')[:30]}"
                print(f"  {i+1}. Score {score}: {element_desc}")
            
            # Add filtering info to the response
            structure_data['filtering_info'] = {
                'applied': True,
                'keywords': keywords,
                'original_elements': original_elements_count,
                'filtered_elements': len(filtered_elements),
                'essential_elements_included': len([e for s, e in essential_elements]),
                'note': 'Filtered elements retain full selector, state, and bounding box information for JavaScript execution and quick_action'
            }
        
        elif len(structure_json) > MAX_SIZE:
            print(f"⚠️  PAGE STRUCTURE: Too large ({len(structure_json)} chars) but no keywords provided")
            print(f"💡 Consider using focus_keywords parameter like: 'search,filter,sort' or 'checkout,cart,payment'")
            # Fallback to simple truncation
            structure_data['elements'] = structure_data['elements'][:100]
            structure_json = json.dumps(structure_data)
        
        final_elements_count = len(structure_data.get('elements', []))
        
        print(f"🔍 PAGE STRUCTURE DEBUG:")
        print(f"  Elements found: {final_elements_count} (from original {original_elements_count})")
        print(f"  Forms found: {forms_count}")
        print(f"  JSON size: {len(structure_json)} characters")
        print(f"  Structure keys: {list(structure_data.keys())}")
        if final_elements_count > 0:
            print(f"  First element: {structure_data['elements'][0].get('tag', 'unknown')} - {structure_data['elements'][0].get('ref', 'no-ref')}")
        
        message = f"Page structure extracted: {len(structure_data.get('elements', []))} interactive elements found"
        return create_fastmcp_response("success", message, screenshot_data, additional_data)
        
    except Exception as e:
        return create_error_response(e, "get page structure")

@mcp.tool()
async def wait_for_condition(
    condition_type: str,
    text: Optional[str] = None,
    target: Optional[str] = None
) -> Dict[str, Any]:
    """
    Wait for a specific condition to be met on the page.
    
    Args:
        condition_type: Type of condition to wait for. Options:
                       - 'text_appears': Wait for text to appear on page
                       - 'text_disappears': Wait for text to disappear from page
                       - 'element_visible': Wait for element to become visible
                       - 'element_hidden': Wait for element to become hidden
                       - 'page_load': Wait for page to finish loading
                       - 'url_change': Wait for URL to change
        text: Text content to wait for (required for text-based conditions)
        target: CSS selector for element (required for element-based conditions)
    """
    try:
        session_id = get_session_id_from_context()
        browser = get_or_create_browser(session_id)
        
        # Ensure browser is initialized
        if not await run_in_session_thread(session_id, browser.is_initialized):
            return {
                "status": "error",
                "message": "Browser not initialized"
            }
        
        timeout = 5  # Fixed 5 second timeout
        start_time = datetime.now()
        
        def wait_condition():
            page = browser.nova.page
                
            if condition_type == 'text_appears':
                if not text:
                    raise ValueError("text is required for text_appears condition")
                page.wait_for_function(
                    f"() => document.body.textContent.includes('{text}')",
                    timeout=timeout * 1000
                )
                
            elif condition_type == 'text_disappears':
                if not text:
                    raise ValueError("text is required for text_disappears condition")
                page.wait_for_function(
                    f"() => !document.body.textContent.includes('{text}')",
                    timeout=timeout * 1000
                )
                
            elif condition_type == 'element_visible':
                if not target:
                    raise ValueError("target is required for element_visible condition")
                page.wait_for_selector(target, state='visible', timeout=timeout * 1000)
                
            elif condition_type == 'element_hidden':
                if not target:
                    raise ValueError("target is required for element_hidden condition")
                page.wait_for_selector(target, state='hidden', timeout=timeout * 1000)
                
            elif condition_type == 'page_load':
                page.wait_for_load_state('load', timeout=timeout * 1000)
                
            elif condition_type == 'url_change':
                current_url = page.url
                page.wait_for_function(
                    f"() => window.location.href !== '{current_url}'",
                    timeout=timeout * 1000
                )
                
            else:
                raise ValueError(f"Unknown condition type: {condition_type}")
        
        # Execute wait condition
        await run_in_session_thread(session_id, wait_condition)
        
        end_time = datetime.now()
        waited_time = (end_time - start_time).total_seconds()
        
        # Get current state for verification
        current_url = await run_in_session_thread(session_id, browser.get_current_url)
        
        return {
            "status": "success",
            "condition_met": True,
            "waited_time": round(waited_time, 2),
            "timeout": timeout,
            "condition": condition_type,
            "text": text,
            "target": target,
            "current_url": current_url,
            "message": f"Condition '{condition_type}' met after {waited_time:.2f} seconds"
        }
        
    except Exception as e:
        end_time = datetime.now()
        waited_time = (end_time - start_time if 'start_time' in locals() else datetime.now()).total_seconds()
        
        if "TimeoutError" in str(e) or "timeout" in str(e).lower():
            return {
                "status": "timeout",
                "condition_met": False,
                "waited_time": round(waited_time, 2),
                "timeout": timeout,
                "condition": condition_type,
                "text": text,
                "target": target,
                "message": f"Condition '{condition_type}' not met within {timeout} seconds"
            }
        else:
            return create_error_response(e, f"wait for condition '{condition_type}'")

@mcp.tool()
async def execute_js(script: str) -> Dict[str, Any]:
    """
    Execute JavaScript code in the browser context and return the result.
    
    Args:
        script: JavaScript code to execute. Should be a function expression like:
               "() => { return document.title; }" or
               "() => { document.querySelector('#btn').click(); return 'clicked'; }" or
               "document.title" (simple expressions will be auto-wrapped)
    """
    try:
        session_id = get_session_id_from_context()
        browser = get_or_create_browser(session_id)
        
        # Ensure browser is initialized
        if not await run_in_session_thread(session_id, browser.is_initialized):
            return {
                "status": "error",
                "message": "Browser not initialized"
            }
        
        start_time = datetime.now()
        
        def execute_script():
            page = browser.nova.page
            
            # Validate script format
            if not script.strip().startswith('()') and not script.strip().startswith('('):
                # Auto-wrap simple expressions
                wrapped_script = f"() => {{ return {script}; }}"
            else:
                wrapped_script = script
            
            try:
                # Execute the script
                result = page.evaluate(wrapped_script)
                
                # Get console messages during execution
                console_messages = []
                
                return {
                    "result": result,
                    "console_messages": console_messages,
                    "error": None
                }
            except Exception as e:
                return {
                    "result": None,
                    "console_messages": [],
                    "error": str(e)
                }
        
        # Execute the JavaScript
        execution_result = await run_in_session_thread(session_id, execute_script)
        
        end_time = datetime.now()
        execution_time = (end_time - start_time).total_seconds()
        
        current_url = await run_in_session_thread(session_id, browser.get_current_url)
        
        if execution_result["error"]:
            return {
                "status": "error",
                "result": None,
                "execution_time": round(execution_time, 3),
                "console_output": execution_result["console_messages"],
                "error": execution_result["error"],
                "current_url": current_url,
                "message": f"JavaScript execution failed: {execution_result['error']}"
            }
        else:
            result_data = execution_result["result"]
            result_type = type(result_data).__name__
            
            return {
                "status": "success",
                "result": {
                    "data": result_data,
                    "type": result_type
                },
                "execution_time": round(execution_time, 3),
                "console_output": execution_result["console_messages"],
                "errors": [],
                "current_url": current_url,
                "message": f"JavaScript executed successfully in {execution_time:.3f}s"
            }
        
    except Exception as e:
        return create_error_response(e, "execute JavaScript")

@mcp.tool()
async def quick_action(
    action: str,
    target_ref: Optional[str] = None,
    target_selector: Optional[str] = None,
    value: Optional[str] = None,
    options: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Perform quick browser actions on specific elements using references or selectors.
    
    Args:
        action: Action to perform. Options:
               - 'click': Click on element
               - 'type': Type text into element
               - 'clear': Clear element content
               - 'select': Select option from dropdown
               - 'check': Check checkbox/radio
               - 'uncheck': Uncheck checkbox/radio
               - 'hover': Hover over element
               - 'focus': Focus on element
               - 'scroll_to': Scroll element into view
        target_ref: Element reference from get_page_structure (e.g., 'ref-button-0')
        target_selector: CSS selector if ref is not available
        value: Value for actions that require input (type, select)
        options: Additional options for specific actions (e.g., {'button': 'right'} for right-click)
    """
    try:
        session_id = get_session_id_from_context()
        browser = get_or_create_browser(session_id)
        
        # Ensure browser is initialized
        if not await run_in_session_thread(session_id, browser.is_initialized):
            return {
                "status": "error",
                "message": "Browser not initialized"
            }
        
        # Determine target selector
        if target_ref:
            if target_ref.startswith('ref-'):
                selector = f'[data-ref="{target_ref}"]'
                target_description = f"element with ref {target_ref}"
            else:
                selector = target_ref
                target_description = f"element {target_ref}"
        elif target_selector:
            selector = target_selector
            target_description = f"element {target_selector}"
        else:
            return {
                "status": "error",
                "message": "Either target_ref or target_selector must be provided"
            }
        
        options = options or {}
        start_time = datetime.now()
        
        def perform_action():
            page = browser.nova.page
            
            try:
                # Get the element
                element = page.locator(selector)
                
                # Check if element exists and is visible
                if not element.count():
                    raise ValueError(f"Element not found: {selector}")
                
                # Perform the action
                if action == 'click':
                    button = options.get('button', 'left')
                    if options.get('double', False):
                        element.dblclick(button=button)
                    else:
                        element.click(button=button)
                    
                elif action == 'type':
                    if not value:
                        raise ValueError("value is required for type action")
                    if options.get('clear_first', True):
                        element.clear()
                    element.fill(value)
                    
                elif action == 'clear':
                    element.clear()
                    
                elif action == 'select':
                    if not value:
                        raise ValueError("value is required for select action")
                    element.select_option(value)
                    
                elif action == 'check':
                    element.check()
                    
                elif action == 'uncheck':
                    element.uncheck()
                    
                elif action == 'hover':
                    element.hover()
                    
                elif action == 'focus':
                    element.focus()
                    
                elif action == 'scroll_to':
                    element.scroll_into_view_if_needed()
                    
                else:
                    raise ValueError(f"Unknown action: {action}")
                
                # Check if page changed (URL or content)
                new_url = page.url
                
                return {
                    "success": True,
                    "new_url": new_url,
                    "error": None
                }
                
            except Exception as e:
                return {
                    "success": False,
                    "new_url": page.url if 'page' in locals() else None,
                    "error": str(e)
                }
        
        # Execute the action
        action_result = await run_in_session_thread(session_id, perform_action)
        
        end_time = datetime.now()
        execution_time = (end_time - start_time).total_seconds()
        
        if action_result["success"]:
            # Get current page state
            current_url = await run_in_session_thread(session_id, browser.get_current_url)
            page_changed = action_result["new_url"] != current_url if current_url else False
            
            return {
                "status": "success",
                "action": action,
                "target": {
                    "ref": target_ref,
                    "selector": selector,
                    "element": target_description
                },
                "value": value,
                "result": f"Action '{action}' performed successfully",
                "page_changed": page_changed,
                "new_url": action_result["new_url"],
                "execution_time": round(execution_time, 3),
                "message": f"Quick action '{action}' completed on {target_description}"
            }
        else:
            return {
                "status": "error",
                "action": action,
                "target": {
                    "ref": target_ref,
                    "selector": selector,
                    "element": target_description
                },
                "value": value,
                "error": action_result["error"],
                "execution_time": round(execution_time, 3),
                "message": f"Quick action '{action}' failed: {action_result['error']}"
            }
        
    except Exception as e:
        return create_error_response(e, f"perform quick action '{action}'")



def cleanup_resources_sync():
    """
    Comprehensive shutdown process - prevent resource leaks through reference cleanup
    """
    global _browser_controllers, _is_shutting_down
    _is_shutting_down = True
    
    if _browser_controllers:
        try:
            logger.info("Closing all browser resources...")
            
            # Close all session browser controllers
            for session_id, controller in list(_browser_controllers.items()):
                try:
                    if controller:
                        logger.info(f"Closing browser for session {session_id}")
                        controller.close()
                except Exception as e:
                    logger.error(f"Error closing browser for session {session_id}: {e}")
            
            # Clear all references
            _browser_controllers.clear()
            
            # Force terminate any remaining Chrome processes
            try:
                import psutil
                import os
                
                current_pid = os.getpid()
                parent_process = psutil.Process(current_pid)
                
                # Find all Chrome/Chromium child processes
                chrome_processes = []
                for child in parent_process.children(recursive=True):
                    try:
                        if child.name().lower() in ['chrome', 'chromium', 'google chrome']:
                            chrome_processes.append(child)
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
                
                if chrome_processes:
                    logger.info(f"Force terminating {len(chrome_processes)} remaining Chrome processes")
                    
                    # Terminate all Chrome processes
                    for proc in chrome_processes:
                        try:
                            logger.info(f"Terminating Chrome process {proc.pid}")
                            proc.terminate()
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            continue
                    
                    # Wait and kill if still running
                    import time
                    time.sleep(1.0)
                    
                    for proc in chrome_processes:
                        try:
                            if proc.is_running():
                                logger.warning(f"Force killing Chrome process {proc.pid}")
                                proc.kill()
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            continue
                            
            except ImportError:
                logger.warning("psutil not available for process cleanup")
            except Exception as e:
                logger.error(f"Error in process cleanup: {e}")
            
            # Shutdown all session ThreadPools
            shutdown_all_session_thread_pools()
            
            # Force garbage collection
            import gc
            gc.collect()
            
            logger.info("Resource cleanup completed")
        except Exception as e:
            # Log errors but continue shutdown process
            logger.error(f"Error during cleanup: {str(e)}")
    
    # Continue shutdown process

# Use ThreadPoolExecutor for timeout-safe shutdown
async def shutdown_server(timeout=5.0):
    """
    Gracefully shutdown the server and clean up resources with timeout
    """
    global _browser_controllers, _is_shutting_down, _shutdown_event
    import threading
    logger.info(f"Shutdown starting in thread ID: {threading.get_ident()}")

    if _is_shutting_down:
        logger.info("Shutdown already in progress, skipping")
        return
        
    logger.info(f"Starting graceful shutdown with {timeout}s timeout...")
    _is_shutting_down = True
    
    # First try to cancel all running tasks
    cancelled_tasks = 0
    try:
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        logger.info(f"Cancelling {len(tasks)} running tasks")
        
        for task in tasks:
            task.cancel()
            cancelled_tasks += 1
        
        # Give tasks some time to cancel
        if tasks:
            try:
                await asyncio.wait(tasks, timeout=min(2.0, timeout/2))
            except (asyncio.CancelledError, Exception):
                pass
    except Exception as e:
        logger.error(f"Error cancelling tasks: {str(e)}")
    
    logger.info(f"Cancelled {cancelled_tasks} tasks")
    
    # Now close all browsers
    if _browser_controllers:
        try:
            logger.info("Closing all browsers...")
            try:
                # First try to close all controllers directly
                for session_id, controller in list(_browser_controllers.items()):
                    try:
                        if controller and hasattr(controller, 'close'):
                            result = controller.close()
                            logger.info(f"Direct browser close result for {session_id}: {result}")
                    except Exception as direct_error:
                        logger.error(f"Direct browser close failed for {session_id}: {direct_error}")
                
                # Then try with executor as backup
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(cleanup_resources_sync)
                    try:
                        await asyncio.wait_for(
                            asyncio.wrap_future(future),
                            timeout=min(3.0, timeout * 0.6)  # Use shorter timeout for browser close
                        )
                    except (asyncio.TimeoutError, Exception) as e:
                        logger.warning(f"Browser close through executor had issues: {str(e)}")
            except Exception as close_error:
                logger.error(f"Error in browser close routine: {close_error}")
        finally:
            # Always clear all controller references
            _browser_controllers.clear()
    
    # Shutdown all session ThreadPools
    shutdown_all_session_thread_pools()
    
    # Set shutdown event
    if _shutdown_event:
        try:
            _shutdown_event.set()
        except Exception as e:
            logger.error(f"Error setting shutdown event: {e}")
    
    # Force garbage collection
    try:
        import gc
        gc.collect()
    except:
        pass
    
    logger.info("Shutdown completed")

def register_exit_handlers():
    def sync_signal_handler(signum, _):
        global _is_shutting_down
        if _is_shutting_down:
            logger.info("Already shutting down, ignoring signal")
            return
            
        logger.info(f"Received signal {signum}, cleaning up synchronously")
        _is_shutting_down = True
        
        cleanup_resources_sync()
        
        if signum == signal.SIGINT:
            logger.info("Exit due to SIGINT")
            sys.exit(130)  # 128 + 2 (SIGINT)
        elif signum == signal.SIGTERM:
            logger.info("Exit due to SIGTERM")
            sys.exit(143)  # 128 + 15 (SIGTERM)
    
    signal.signal(signal.SIGINT, sync_signal_handler)
    signal.signal(signal.SIGTERM, sync_signal_handler)

async def async_main(args):
    # Create shutdown event
    global _shutdown_event
    _shutdown_event = asyncio.Event()
    
    # Register synchronous cleanup handlers
    register_exit_handlers()
    
    # Set up asyncio signal handlers for graceful shutdown
    try:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(
                sig,
                lambda _=sig: asyncio.create_task(
                    shutdown_server(timeout=1.0)
                )
            )
    except NotImplementedError:
        # Signal handlers not available on this platform (e.g., Windows)
        logger.warning("Asyncio signal handlers not available on this platform")
    except Exception as e:
        logger.error(f"Error setting up signal handlers: {str(e)}")
    
    # Start background session cleanup task
    cleanup_task = asyncio.create_task(session_cleanup_task())
    logger.info(f"Started session cleanup task (TTL: {SESSION_TTL_SECONDS}s, interval: {SESSION_CLEANUP_INTERVAL}s)")
    
    try:
        logger.info("Starting MCP server...")
        if args.transport == "stdio":
            # Run in stdio mode with short timeout
            await asyncio.wait_for(
                mcp.run_async(transport="stdio"),
                timeout=None  # No timeout for the main task
            )
        else:
            # Run in HTTP mode with short timeout
            await asyncio.wait_for(
                mcp.run_async(transport="http", host=args.host, port=args.port),
                timeout=None  # No timeout for the main task
            )
    except asyncio.CancelledError:
        logger.info("MCP server operation cancelled")
    except asyncio.TimeoutError:
        logger.warning("MCP server startup timed out")
    except Exception as e:
        logger.error(f"Error running MCP server: {str(e)}")
        return 1
    finally:
        # Cancel cleanup task
        if 'cleanup_task' in locals():
            cleanup_task.cancel()
            try:
                await cleanup_task
            except asyncio.CancelledError:
                logger.info("Session cleanup task cancelled")
        
        # Quick shutdown with very short timeout
        try:
            await asyncio.wait_for(shutdown_server(timeout=0.5), timeout=0.8)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            logger.info("Shutdown procedure timed out or was cancelled")
            cleanup_resources_sync()  # Fall back to sync cleanup
        except Exception as e:
            logger.error(f"Error during shutdown: {str(e)}")
            cleanup_resources_sync()  # Fall back to sync cleanup
    
    return 0

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Browser Automation MCP Server")
    parser.add_argument("--transport", type=str, default="streamable-http", choices=["stdio", "http", "streamable-http"],
                        help="Transport protocol (stdio, http, or streamable-http)")
    parser.add_argument("--host", type=str, default="localhost",
                        help="Host to bind to (for HTTP transport)")
    parser.add_argument("--port", type=int, default=8000,
                        help="Port to bind to (for HTTP transport)")
    parser.add_argument("--verbose", action="store_true",
                        help="Enable verbose logging")
    
    args = parser.parse_args()
    
    if args.verbose:
        logger.setLevel(logging.INFO)
    
    # Use asyncio.run with very short timeout for the entire operation
    try:
        if args.transport == "streamable-http":
            # Use streamable HTTP transport with /nova-act/mcp path
            logger.info("Starting MCP server with Streamable HTTP transport on /nova-act/mcp...")
            
            # Use asyncio.run to properly handle the async method
            asyncio.run(
                mcp.run_http_async(
                    transport="streamable-http", 
                    host=args.host, 
                    port=args.port,
                    path="/nova-act/mcp"
                )
            )
        else:
            # Handle KeyboardInterrupt before it reaches asyncio.run()
            exit_code = asyncio.run(async_main(args))
            sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt detected")
        cleanup_resources_sync()
        sys.exit(0)
    except Exception as e:
        logger.error(f"Unhandled exception: {str(e)}")
        traceback.print_exc()
        cleanup_resources_sync()
        sys.exit(1)

if __name__ == "__main__":
    main()