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

def kill_process_on_port(port: int):
    """Kill any process running on the specified port using Python's psutil library"""
    # Validate port number to prevent issues
    if not isinstance(port, int) or port < 1 or port > 65535:
        raise ValueError(f"Invalid port number: {port}")
    
    try:
        import psutil
        
        # Find processes using the port
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                # Get connections directly from process
                connections = proc.connections()
                if connections:
                    for conn in connections:
                        if hasattr(conn, 'laddr') and conn.laddr and conn.laddr.port == port:
                            print(f"Killing process {proc.info['pid']} ({proc.info['name']}) on port {port}")
                            proc.terminate()
                            # Wait for graceful shutdown
                            try:
                                proc.wait(timeout=3)
                            except psutil.TimeoutExpired:
                                proc.kill()  # Force kill if needed
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, AttributeError):
                continue
    except ImportError:
        print(f"psutil not available - cannot automatically kill processes on port {port}")
        print("Please manually kill any processes using the port and try again")
    except Exception as e:
        print(f"Error killing process on port {port}: {e}")

def start_server_with_port_management(app_module: str, preferred_port: int = None):
    """Start server with automatic port management"""
    import uvicorn
    from config import Config
    
    # Use Config.PORT if no preferred_port is provided
    if preferred_port is None:
        preferred_port = Config.PORT
    
    print("Starting Strands Agent Chatbot Server with FastAPI + SSE...")
    print("Make sure you have AWS credentials configured for Bedrock access")
    
    try:
        kill_process_on_port(preferred_port)
        
        port = find_available_port(preferred_port)
        
        if port != preferred_port:
            print(f"Port {preferred_port} was busy, using port {port} instead")
        
        print(f"Server starting on http://{Config.HOST}:{port}")
        print(f"API Documentation: http://{Config.HOST}:{port}/docs")
        print(f"SSE Streaming endpoint: POST /chat/stream")
        print(f"Health check: GET /health")
        
        uvicorn.run(app_module, host=Config.HOST, port=port, reload=Config.RELOAD)
        
    except Exception as e:
        print(f"Failed to start server: {e}")
        print("Trying to find any available port...")
        
        try:
            port = find_available_port(8001, 20)
            print(f"Using alternative port {port}")
            print(f"API Documentation: http://{Config.HOST}:{port}/docs")
            print(f"SSE Streaming endpoint: POST /chat/stream")
            uvicorn.run(app_module, host=Config.HOST, port=port, reload=Config.RELOAD)
        except Exception as fallback_error:
            print(f"Could not start server on any port: {fallback_error}")
            print("Please manually kill any processes using ports 8000-8020 and try again")
