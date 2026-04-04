from typing import Any, Dict, List
from llm import LLM

def count_messages_tokens(messages: List[Dict[str, Any]]) -> int:
    try:
        import tiktoken
    except ImportError:
        raise ImportError("tiktoken library is required for token counting. Please install it via 'pip install tiktoken'.")
    
    total_tokens = 0
    enc = tiktoken.get_encoding("o200k_base")
    for message in messages:
        content = message.get("content", "")

        tokens = enc.encode(content)
        total_tokens += len(tokens)        

    return total_tokens


def count_messages_words(messages: List[Dict[str, Any]]) -> int:
    total_words = 0
    for message in messages:
        content = message.get("content", "")
        words = content.split()
        total_words += len(words)
    return total_words


def flatten_messages(messages: List[Dict[str, Any]]) -> str:
    """Flatten messages including tool calls and responses into a readable format."""
    flattened_parts = []
    
    for msg in messages:
        role = msg.get('role', 'unknown').capitalize()
        content = msg.get('content')
        
        # Handle content (can be string, list, or None)
        if content is not None:
            if isinstance(content, str):
                text_content = content
            elif isinstance(content, list):
                # Extract text from content list (handles [{"type": "text", "text": "..."}])
                text_parts = []
                for item in content:
                    if isinstance(item, dict) and item.get('type') == 'text':
                        text_parts.append(item.get('text', ''))
                text_content = '\n'.join(text_parts)
            else:
                text_content = str(content)
            
            flattened_parts.append(f"## {role}:\n\n{text_content}\n")
        
        # Handle tool calls (for assistant messages)
        tool_calls = msg.get('tool_calls', [])
        if tool_calls:
            if not content:  # Only add header if content wasn't already added
                flattened_parts.append(f"## {role}:\n")
            
            flattened_parts.append("### Tool Calls:\n")
            for tool_call in tool_calls:
                tool_id = tool_call.get('id', 'unknown')
                function = tool_call.get('function', {})
                function_name = function.get('name', 'unknown')
                arguments = function.get('arguments', '{}')
                
                flattened_parts.append(f"- **{function_name}** (ID: {tool_id})\n Arguments: {arguments}\n")
            flattened_parts.append("\n")
        
        # Handle tool call ID (for tool response messages)
        if msg.get('tool_call_id'):
            tool_id = msg.get('tool_call_id')
            flattened_parts[-1] = flattened_parts[-1].rstrip() + f" (Response to: {tool_id})\n\n"
    
    return "\n".join(flattened_parts).strip()


def summarize_messages(llm: LLM, messages: List[Dict[str, Any]]) -> str:
    
    prompt = """
    You are an expert summarization AI. 
    
    Given the following conversation messages, provide a concise summary highlighting the key points discussed.
    
    Maintain language and important details while ensuring clarity and brevity.
    
    {messages}

    ## Note:
    - Only return the summary text without any additional commentary.
    """

    flattened = flatten_messages(messages)
    full_prompt = prompt.replace("{messages}", flattened)
    response = llm.chat_completion([{"role": "user", "content": full_prompt}])
    return response.get("content", "").strip()