from fastapi import APIRouter
import boto3
import re
import logging
from botocore.exceptions import ClientError

router = APIRouter(prefix="/chat", tags=["suggestions"])

def parse_questions_from_xml(xml_text: str) -> list:
    """Parse questions from XML format"""
    try:
        # Find questions within XML tags
        pattern = r'<question\s+id="(\d+)">(.*?)</question>'
        matches = re.findall(pattern, xml_text, re.DOTALL | re.IGNORECASE)
        
        questions = []
        for match in matches:
            question_id, text = match
            # Clean up text (remove extra whitespace)
            clean_text = re.sub(r'\s+', ' ', text.strip())
            questions.append({
                "id": question_id,
                "text": clean_text
            })
        
        return questions[:2]  # Limit to 2 questions
    except Exception as e:
        logging.error(f"Error parsing XML questions: {e}")
        return []

async def generate_questions_with_llm(available_tools: list, conversation_history: str = "") -> list:
    """Generate questions using Amazon Nova Pro model"""
    try:
        bedrock_client = boto3.client('bedrock-runtime')
        model_id = "us.amazon.nova-pro-v1:0"
        
        # Create tool list for context
        tool_names = [tool for tool in available_tools if tool]
        tools_context = ", ".join(tool_names) if tool_names else "general financial tools"
        
        system_prompts = [{
            "text": "You are a helpful assistant that generates concise, actionable question suggestions. Generate exactly 2 questions that use one or multiple available tools. Each question should be 1 sentence and directly relate to using the tools. If no tools are available, generate simple general questions. Return in XML format only."
        }]
        
        context_text = f"Available tools: {tools_context}"
        if conversation_history:
            context_text += f"\n\nRecent conversation context:\n{conversation_history}"
        
        message = {
            "role": "user", 
            "content": [{
                "text": f"{context_text}\n\nBased on the available tools and conversation context, generate exactly 2 concise questions (1 sentence each) that would be helpful follow-up questions. Format as: <question id=\"1\">question text</question><question id=\"2\">question text</question>"
            }]
        }
        
        response = bedrock_client.converse(
            modelId=model_id,
            messages=[message],
            system=system_prompts,
            inferenceConfig={"temperature": 0.3}
        )
        
        # Extract response text
        response_text = response['output']['message']['content'][0]['text']
        
        # Parse XML and extract questions
        questions = parse_questions_from_xml(response_text)
        
        if questions:
            return questions
        else:
            raise Exception("No valid questions parsed from LLM response")
            
    except ClientError as e:
        logging.error(f"AWS Bedrock error: {e}")
        return []
    except Exception as e:
        logging.error(f"Error calling Nova Pro model: {e}")
        return []

@router.post("/suggestions")
async def generate_suggestions(request: dict):
    """Generate dynamic suggested questions using Amazon Nova Pro"""
    try:
        available_tools = request.get("available_tools", [])
        conversation_history = request.get("conversation_history", "")
        
        # Try to generate questions with LLM first
        questions = await generate_questions_with_llm(available_tools, conversation_history)
        
        # If LLM fails, use rule-based fallback
        if not questions:
            questions = []
            if "get_portfolio_overview" in available_tools:
                questions.append({"id": "1", "text": "What's my portfolio performance?"})
            else:
                questions.append({"id": "1", "text": "What can you help with?"})
            
            if "get_account_details" in available_tools:
                questions.append({"id": "2", "text": "Show account details"})
            else:
                questions.append({"id": "2", "text": "Give financial insights"})
        
        return {"questions": questions}
        
    except Exception as e:
        logging.error(f"Error in generate_suggestions: {e}")
        # Final fallback questions
        return {
            "questions": [
                {"id": "1", "text": "What's my financial health?"},
                {"id": "2", "text": "Show portfolio overview"}
            ]
        }