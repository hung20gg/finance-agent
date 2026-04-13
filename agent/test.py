import asyncio
import json
from fastmcp import Client
import fastmcp
from agent.llm import get_llm_wrapper
from typing import List, Dict, Union, Any

host = "http://localhost"
port = 9004
# HTTP server
url = f"{host}:{port}/sse"
print(f"Connecting to MCP server at {url}...")
client = Client(url)


llm = get_llm_wrapper("groq:openai/gpt-oss-120b")

def fastmcp_to_gemini_tools(tools) -> list:
    gemini_tools = []
    
    for tool in tools:
        tool = tool.model_dump()
        gemini_tool = {
            "name": tool.get("name"),
            "description": tool.get("description"),
            "parameters": tool.get("inputSchema", {}),
        }
        gemini_tools.append(gemini_tool)
    return gemini_tools

def fastmcp_to_openai_tools(tools) -> list:
    openai_tools = []
    
    for tool in tools:
        tool = tool.model_dump()
        openai_tool = {
            "type": "function",
            "function": {
                "name": tool.get("name"),
                "description": tool.get("description"),
                "parameters": tool.get("inputSchema", {}),
            }
        }
        openai_tools.append(openai_tool)
    return openai_tools

async def main():
    async with client:
        # Basic server interaction
        await client.ping()

        print("Available tools:")
        tools = await client.list_tools()
        print(json.dumps(fastmcp_to_gemini_tools(tools), indent=2, ensure_ascii=False))
        

        # Execute operations
        
        result = await client.call_tool("fuzzy_search_financial_metrics", {"query": "revenue", "field": "category_code"})
        print("Tool call result:")
        print(result.content[0].text)
        
        # messages = [
        #     {
        #         "role": "user",
        #         "content": "Tin tức từ VIC từ 1/1/2024 đến 1/6/2024"
        #     }
        # ]

        # # for msg in llm.stream_tool_calling(messages, tools=openai_tools):
        # #     print('[STREAM]', msg, end='', flush=True)
        

        # tool_responses = llm.tool_calling(messages, tools=openai_tools)
        
        # messages.append({
        #     "role": "assistant",
        #     "tool_calls": tool_responses['tool_calls'],
        #     "content": tool_responses['content']
        # })
        
        # print(tool_responses)
        # for tool_response in tool_responses['tool_calls']:
        #     print(tool_response)
        #     tool_id = tool_response.get("id")
        #     function = tool_response.get("function")
        #     function_name = function.get("name")
        #     arguments = json.loads(function.get("arguments"))            
        #     tool_result = await client.call_tool(function_name, arguments)
            
        #     messages.append({
        #         "role": "tool",
        #         "tool_call_id": tool_id,
        #         "content": json.dumps(tool_result.content[0].text)
        #     })
            
        # response = llm(messages)
        
        # print("Final LLM response:")
        # print(response)
            
        
        # print(tool_responses)
asyncio.run(main())