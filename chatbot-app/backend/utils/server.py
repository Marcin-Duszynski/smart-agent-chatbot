import socket
import os

def find_available_port(start_port: int = 8000, max_attempts: int = 10) -> int:
    """Find an available port starting from start_port"""
    for port in range(start_port, start_port + max_attempts):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('localhost', port))
                return port
        except OSError:
            continue
    
    raise RuntimeError(f"Could not find an available port in range {start_port}-{start_port + max_attempts - 1}")

def kill_process_on_port(port: int, force: bool = True):
    """Kill any process running on the specified port using Python's psutil library"""
    # Validate port number to prevent issues
    if not isinstance(port, int) or port < 1 or port > 65535:
        raise ValueError(f"Invalid port number: {port}")

    import time

    try:
        import psutil

        killed = False
        # Find processes using the port
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                # Get connections directly from process
                connections = proc.connections()
                if connections:
                    for conn in connections:
                        if hasattr(conn, 'laddr') and conn.laddr and conn.laddr.port == port:
                            print(f"Killing process {proc.info['pid']} ({proc.info['name']}) on port {port}")
                            if force:
                                # Force kill immediately for faster port release
                                proc.kill()
                            else:
                                proc.terminate()
                                # Wait for graceful shutdown
                                try:
                                    proc.wait(timeout=3)
                                except psutil.TimeoutExpired:
                                    proc.kill()  # Force kill if needed
                            killed = True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, AttributeError):
                continue

        # If we killed any process, wait for OS to release the port
        if killed:
            time.sleep(1)

    except ImportError:
        print(f"psutil not available - cannot automatically kill processes on port {port}")
        print("Please manually kill any processes using the port and try again")
    except Exception as e:
        print(f"Error killing process on port {port}: {e}")

def start_server_with_port_management(app_module: str, preferred_port: int = None):
    """Start server with automatic port management - always tries to use preferred port"""
    import uvicorn
    import time
    from config import Config

    # Use Config.PORT if no preferred_port is provided
    if preferred_port is None:
        preferred_port = Config.PORT

    print("Starting Strands Agent Chatbot Server with FastAPI + SSE...")
    print("Make sure you have AWS credentials configured for Bedrock access")

    # Try to acquire the preferred port with multiple retries
    max_retries = 3
    for attempt in range(max_retries):
        try:
            # Kill any process on the preferred port
            kill_process_on_port(preferred_port, force=True)

            # Try to bind to the preferred port
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(('localhost', preferred_port))
                # Port is available
                break
        except OSError as e:
            if attempt < max_retries - 1:
                print(f"Port {preferred_port} still busy (attempt {attempt + 1}/{max_retries}), retrying in 2 seconds...")
                time.sleep(2)
            else:
                # Final attempt failed, try fallback range
                print(f"Port {preferred_port} unavailable after {max_retries} attempts")
                try:
                    port = find_available_port(8001, 20)
                    print(f"Using alternative port {port}")
                    print(f"API Documentation: http://{Config.HOST}:{port}/docs")
                    print(f"SSE Streaming endpoint: POST /chat/stream")
                    print(f"Health check: GET /health")
                    uvicorn.run(app_module, host=Config.HOST, port=port, reload=Config.RELOAD)
                    return
                except Exception as fallback_error:
                    print(f"Could not start server on any port: {fallback_error}")
                    print("Please manually kill any processes using ports 8000-8020 and try again")
                    raise

    # Successfully acquired the preferred port
    print(f"Server starting on http://{Config.HOST}:{preferred_port}")
    print(f"API Documentation: http://{Config.HOST}:{preferred_port}/docs")
    print(f"SSE Streaming endpoint: POST /chat/stream")
    print(f"Health check: GET /health")

    try:
        uvicorn.run(app_module, host=Config.HOST, port=preferred_port, reload=Config.RELOAD)
    except Exception as e:
        print(f"Failed to start server on port {preferred_port}: {e}")
        raise
