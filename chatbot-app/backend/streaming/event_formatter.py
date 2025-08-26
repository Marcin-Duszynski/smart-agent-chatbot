import json
import base64
import os
from typing import Dict, Any, List, Tuple

class StreamEventFormatter:
    """Handles formatting of streaming events for SSE"""
    
    @staticmethod
    def format_sse_event(event_data: dict) -> str:
        """Format event data as Server-Sent Event with proper JSON serialization"""
        try:
            return f"data: {json.dumps(event_data)}\n\n"
        except (TypeError, ValueError) as e:
            # Fallback for non-serializable objects
            return f"data: {json.dumps({'type': 'error', 'message': f'Serialization error: {str(e)}'})}\n\n"
    
    @staticmethod
    def extract_final_result_data(final_result) -> Tuple[List[Dict[str, str]], str]:
        """Extract images and text from final result with simplified logic"""
        images = []
        result_text = str(final_result)
        
        try:
            if hasattr(final_result, 'message') and hasattr(final_result.message, 'content'):
                content = final_result.message.content
                text_parts = []
                
                for item in content:
                    if isinstance(item, dict):
                        if "text" in item:
                            text_parts.append(item["text"])
                        elif "image" in item and "source" in item["image"]:
                            # Simple image extraction
                            image_data = item["image"]
                            images.append({
                                "format": image_data.get("format", "png"),
                                "data": image_data["source"].get("data", "")
                            })
                
                if text_parts:
                    result_text = " ".join(text_parts)
        
        except Exception as e:
            pass
        
        return images, result_text
    
    @staticmethod
    def create_init_event() -> str:
        """Create initialization event"""
        return StreamEventFormatter.format_sse_event({
            "type": "init",
            "message": "Initializing..."
        })
    
    @staticmethod
    def create_reasoning_event(reasoning_text: str) -> str:
        """Create reasoning event"""
        return StreamEventFormatter.format_sse_event({
            "type": "reasoning",
            "text": reasoning_text,
            "step": "thinking"
        })
    
    @staticmethod
    def create_response_event(text: str) -> str:
        """Create response event"""
        return StreamEventFormatter.format_sse_event({
            "type": "response",
            "text": text,
            "step": "answering"
        })
    
    @staticmethod
    def create_tool_use_event(tool_use: Dict[str, Any]) -> str:
        """Create tool use event"""
        return StreamEventFormatter.format_sse_event({
            "type": "tool_use",
            "toolUseId": tool_use.get("toolUseId"),
            "name": tool_use.get("name"),
            "input": tool_use.get("input", {})
        })
    
    @staticmethod
    def create_tool_result_event(tool_result: Dict[str, Any]) -> str:
        """Create tool result event"""
        # Extract text and images from tool result
        result_text = ""
        result_images = []
        
        if "content" in tool_result:
            for item in tool_result["content"]:
                if isinstance(item, dict):
                    if "text" in item:
                        result_text += item["text"]
                    elif "image" in item and "source" in item["image"]:
                        # Improved image extraction
                        image_source = item["image"]["source"]
                        image_data = ""
                        
                        if "data" in image_source:
                            image_data = image_source["data"]
                        elif "bytes" in image_source:
                            # Handle bytes format
                            if isinstance(image_source["bytes"], bytes):
                                image_data = base64.b64encode(image_source["bytes"]).decode('utf-8')
                            else:
                                image_data = str(image_source["bytes"])
                        
                        if image_data:
                            result_images.append({
                                "format": item["image"].get("format", "png"),
                                "data": image_data
                            })
        
        # Auto-save agent type tool results to markdown files
        # Skip financial_narrative_tool as it handles its own memory storage
        # Handle Python MCP results specially
        tool_use_id = tool_result.get("toolUseId")
        if tool_use_id and result_text:
            # Check if this is financial_narrative_tool or run_python_code
            try:
                from agent import get_global_stream_processor
                processor = get_global_stream_processor()
                if processor and hasattr(processor, 'tool_use_registry'):
                    tool_info = processor.tool_use_registry.get(tool_use_id)
                    tool_name = tool_info.get('tool_name') if tool_info else None
                    
                    print(f"🔍 TOOL RESULT DEBUG: tool_use_id={tool_use_id}, tool_name={tool_name}")
                    print(f"🔍 TOOL INFO: {tool_info}")
                    
                    if tool_name == 'financial_narrative_tool':
                        # Skip auto-save for financial_narrative_tool as it handles its own storage
                        print(f"⏭️ Skipping auto-save for financial_narrative_tool: {tool_use_id}")
                        # Do not call _save_agent_tool_result for financial_narrative_tool
                        pass
                    elif tool_name == 'run_python_code':
                        print(f"🎯 DETECTED PYTHON MCP TOOL: {tool_name}")
                        # Use Base64 interception for file handling
                        processed_text, file_info = StreamEventFormatter._handle_python_mcp_base64(tool_use_id, result_text)
                        
                        if file_info:
                            print(f"📁 Processed and saved {len(file_info)} files for {tool_use_id}")
                            result_text = processed_text
                        StreamEventFormatter._save_agent_tool_result(tool_use_id, result_text)
                    else:
                        print(f"🔍 NON-MCP TOOL: {tool_name} (tool_type: {tool_info.get('tool_type') if tool_info else 'None'})")
                        StreamEventFormatter._save_agent_tool_result(tool_use_id, result_text)
                else:
                    print(f"🔴 No processor or tool_use_registry found for {tool_use_id}")
                    StreamEventFormatter._save_agent_tool_result(tool_use_id, result_text)
            except Exception as e:
                # For financial_narrative_tool, skip even on error to avoid raw data storage
                try:
                    from agent import get_global_stream_processor
                    processor = get_global_stream_processor()
                    if processor and hasattr(processor, 'tool_use_registry'):
                        tool_info = processor.tool_use_registry.get(tool_use_id)
                        tool_name = tool_info.get('tool_name') if tool_info else None
                        if tool_name == 'financial_narrative_tool':
                            print(f"⏭️ Skipping auto-save for financial_narrative_tool even on error: {tool_use_id}")
                            pass
                        elif tool_name == 'run_python_code':
                            print(f"Warning: Error checking tool type, proceeding with Python MCP processing: {e}")
                            StreamEventFormatter._save_agent_tool_result(tool_use_id, result_text)
                        else:
                            print(f"Warning: Error checking tool type, proceeding with auto-save: {e}")
                            StreamEventFormatter._save_agent_tool_result(tool_use_id, result_text)
                    else:
                        print(f"Warning: Error checking tool type, proceeding with auto-save: {e}")
                        StreamEventFormatter._save_agent_tool_result(tool_use_id, result_text)
                except:
                    # Ultimate fallback - proceed with auto-save only if we can't determine tool type
                    print(f"Warning: Error checking tool type, proceeding with auto-save: {e}")
                    StreamEventFormatter._save_agent_tool_result(tool_use_id, result_text)
        
        tool_result_data = {
            "type": "tool_result",
            "toolUseId": tool_result.get("toolUseId"),
            "result": result_text
        }
        if result_images:
            tool_result_data["images"] = result_images
        
        return StreamEventFormatter.format_sse_event(tool_result_data)
    
    @staticmethod
    def create_complete_event(message: str, images: List[Dict[str, str]] = None) -> str:
        """Create completion event"""
        completion_data = {
            "type": "complete",
            "message": message
        }
        if images:
            completion_data["images"] = images
        
        return StreamEventFormatter.format_sse_event(completion_data)
    
    @staticmethod
    def create_error_event(error_message: str) -> str:
        """Create error event"""
        return StreamEventFormatter.format_sse_event({
            "type": "error",
            "message": error_message
        })
    
    @staticmethod
    def create_thinking_event(message: str = "Processing your request...") -> str:
        """Create thinking event"""
        return StreamEventFormatter.format_sse_event({
            "type": "thinking",
            "message": message
        })
    
    @staticmethod
    def create_progress_event(progress_data: Dict[str, Any]) -> str:
        """Create progress event for tool execution"""
        return StreamEventFormatter.format_sse_event({
            "type": "tool_progress",
            "toolId": progress_data.get("toolId"),
            "sessionId": progress_data.get("sessionId"),
            "step": progress_data.get("step"),
            "message": progress_data.get("message"),
            "progress": progress_data.get("progress"),
            "timestamp": progress_data.get("timestamp"),
            "metadata": progress_data.get("metadata", {})
        })
    
    

    @staticmethod
    def _handle_python_mcp_base64(tool_use_id: str, result_text: str) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Intercept Base64 file data from Python MCP results and save to local files
        Returns: (processed_text_without_base64, file_info_list)
        """
        import re
        import base64
        from config import Config
        
        file_info = []
        processed_text = result_text
        
        try:
            # Pattern to match Base64 data URLs: data:application/zip;base64,{base64_data}
            base64_pattern = r'<download[^>]*?>data:([^;]+);base64,([A-Za-z0-9+/=]+)</download>'
            
            print(f"🔍 Base64 interception start for {tool_use_id}")
            print(f"🔍 Result text length: {len(result_text)}")
            print(f"🔍 Looking for pattern: {base64_pattern}")
            print(f"🔍 First 500 chars of result: {result_text[:500]}")
            
            # Check if pattern exists
            import re
            matches = re.findall(base64_pattern, result_text)
            print(f"🔍 Found {len(matches)} Base64 matches")
            
            if matches:
                print(f"🔍 First match MIME type: {matches[0][0]}")
                print(f"🔍 First match Base64 length: {len(matches[0][1])}")
            else:
                print(f"🔍 No matches found - checking for similar patterns...")
                download_patterns = re.findall(r'<download[^>]*?>(.*?)</download>', result_text, re.DOTALL)
                print(f"🔍 Found {len(download_patterns)} download tags")
                for i, pattern in enumerate(download_patterns[:2]):  # Show first 2
                    print(f"🔍 Download {i+1}: {pattern[:100]}...")
                
                # Check for data: patterns
                data_patterns = re.findall(r'data:([^;]+);base64,([A-Za-z0-9+/=]{10,100})', result_text)
                print(f"🔍 Found {len(data_patterns)} data: patterns")
            
            def process_base64_match(match):
                mime_type = match.group(1)
                base64_data = match.group(2)
                
                try:
                    # Decode Base64 data
                    file_data = base64.b64decode(base64_data)
                    
                    # Determine file extension from MIME type
                    extension_map = {
                        'application/zip': '.zip',
                        'text/plain': '.txt',
                        'application/json': '.json',
                        'text/csv': '.csv',
                        'image/png': '.png',
                        'image/jpeg': '.jpg'
                    }
                    extension = extension_map.get(mime_type, '.bin')
                    
                    # Generate filename
                    filename = f"python_output_{len(file_info) + 1}{extension}"
                    
                    # Create output directory
                    from agent import get_global_stream_processor
                    processor = get_global_stream_processor()
                    session_id = None
                    if processor and hasattr(processor, 'tool_use_registry'):
                        tool_info = processor.tool_use_registry.get(tool_use_id)
                        session_id = tool_info.get('session_id') if tool_info else None
                    
                    if session_id:
                        print(f"💾 Attempting to save Base64 file for session {session_id}")
                        try:
                            session_output_dir = Config.get_session_output_dir(session_id)
                            tool_dir = os.path.join(session_output_dir, tool_use_id)
                            print(f"💾 Tool directory: {tool_dir}")
                            print(f"💾 Current working directory: {os.getcwd()}")
                            print(f"💾 Session output dir exists: {os.path.exists(session_output_dir)}")
                            os.makedirs(tool_dir, exist_ok=True)
                            print(f"💾 Tool directory created successfully")
                        except Exception as dir_error:
                            print(f"❌ Error creating directory: {dir_error}")
                            return match.group(0)
                        
                        # Save file
                        try:
                            file_path = os.path.join(tool_dir, filename)
                            print(f"💾 Saving to: {file_path}")
                            with open(file_path, 'wb') as f:
                                f.write(file_data)
                            print(f"💾 File written successfully: {len(file_data)} bytes")
                            
                            # Verify file was saved
                            if os.path.exists(file_path):
                                actual_size = os.path.getsize(file_path)
                                print(f"💾 File verified: {actual_size} bytes on disk")
                            else:
                                print(f"❌ File verification failed: {file_path} does not exist")
                                return match.group(0)
                            
                            # Create download URL (relative to session output)
                            relative_path = os.path.relpath(file_path, Config.get_output_dir())
                            download_url = f"/files/{relative_path}"
                            print(f"💾 Download URL: {download_url}")
                            print(f"💾 File saved successfully: {filename} ({len(file_data)} bytes)")
                            
                            file_info.append({
                                'filename': filename,
                                'mime_type': mime_type,
                                'size': len(file_data),
                                'download_url': download_url,
                                'local_path': file_path
                            })
                            
                            print(f"💾 Saved Base64 file: {filename} ({len(file_data)} bytes) -> {file_path}")
                            
                            # Replace Base64 data with simple message
                            return f"📁 Files have been saved as a ZIP archive."
                        except Exception as save_error:
                            print(f"❌ Error saving file: {save_error}")
                            return match.group(0)
                    else:
                        print(f"⚠️ No session ID found for tool_use_id: {tool_use_id}")
                        return match.group(0)  # Keep original if no session
                        
                except Exception as e:
                    print(f"❌ Error processing Base64 data: {e}")
                    return match.group(0)  # Keep original on error
            
            # Process all Base64 matches
            processed_text = re.sub(base64_pattern, process_base64_match, result_text)
            
            print(f"🔍 Processed Python MCP result: found {len(file_info)} files")
            
        except Exception as e:
            print(f"❌ Error in _handle_python_mcp_base64: {e}")
        
        return processed_text, file_info

    @staticmethod
    def _save_agent_tool_result(tool_use_id: str, result_text: str):
        """Save agent type tool result to memory store with chart replacement - only for actual agent tools"""
        try:
            from agent import get_global_stream_processor
            from config import Config
            from memory_store import get_memory_store
            import re
            
            processor = get_global_stream_processor()
            
            if not processor or not hasattr(processor, 'tool_use_registry'):
                return
                
            tool_info = processor.tool_use_registry.get(tool_use_id)
            if not tool_info:
                return
            
            tool_name = tool_info.get('tool_name')
            session_id = tool_info.get('session_id')
            
            if not tool_name or not session_id:
                return
            
            config_path = os.path.join(os.path.dirname(__file__), '..', 'unified_tools_config.json')
            
            if not os.path.exists(config_path):
                return
            
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            is_agent_tool = False
            for tool in config.get('tools', []):
                if tool.get('id') == tool_name and tool.get('tool_type') == 'agent':
                    is_agent_tool = True
                    break
            
            if is_agent_tool:
                # Get memory store to access chart data
                memory_store = get_memory_store()
                
                # Replace [CHART:chart_name:Title] with ```chart blocks
                def replace_chart_references(text):
                    # Pattern to match [CHART:chart_name:Title]
                    chart_pattern = r'\[CHART:([^:]+):([^\]]+)\]'
                    
                    def chart_replacer(match):
                        chart_name = match.group(1)
                        chart_title = match.group(2)
                        
                        # Get chart data from memory store
                        chart_data = memory_store.get_chart(session_id, chart_name)
                        
                        if chart_data:
                            # Convert chart data to ```chart block
                            chart_json = json.dumps(chart_data, indent=2)
                            return f"```chart\n{chart_json}\n```"
                        else:
                            # If chart not found, keep original reference
                            print(f"Warning: Chart '{chart_name}' not found in memory for session {session_id}")
                            return match.group(0)
                    
                    return re.sub(chart_pattern, chart_replacer, text)
                
                # Replace chart references in the result text
                processed_text = replace_chart_references(result_text)
                
                # Store processed text in memory
                metadata = {
                    'tool_name': tool_name,
                    'tool_type': 'agent'
                }
                memory_store.store_analysis(session_id, tool_use_id, processed_text, {}, metadata)
                
                print(f"Saved agent tool result to memory with chart replacement: session={session_id}, tool_use_id={tool_use_id}")
                
                # Also save to file for backward compatibility (optional)
                try:
                    session_output_dir = Config.get_session_output_dir(session_id)
                    tool_dir = os.path.join(session_output_dir, tool_name, tool_use_id)
                    os.makedirs(tool_dir, exist_ok=True)
                    
                    output_path = os.path.join(tool_dir, 'result.md')
                    with open(output_path, 'w', encoding='utf-8') as f:
                        f.write(processed_text)
                    
                    print(f"Also saved to file for compatibility: {output_path}")
                except Exception as file_error:
                    print(f"Warning: Failed to save file backup: {file_error}")
            
        except Exception as e:
            print(f"Warning: Failed to save agent tool result for {tool_use_id}: {e}")
    
