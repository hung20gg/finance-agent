from agent.strategy import get_agent_state, get_agent_config, get_agent
import json
from dataclasses import asdict

import asyncio
current_time = "2025-12-31"

async def test_react():
    agent_config = {
        "agent_type": "react",
        "streaming": True,
        "model_name": "openrouter:qwen/qwen3.5-122b-a10b",
        "urls" : ["http://localhost:9004/sse"],
        
    }

    agent_state_config = {
        "agent_type": "react",
        "current_time": current_time
    }

    state = get_agent_state(**agent_state_config)
    # state.user_request = "Mức độ tăng trưởng cổ phiếu VIC trong quý 1 2025"
    state.user_request = "Top 5 công ty bất động sản có lợi nhuận cao nhất trong quý 1 2025"
    agent_config = get_agent_config(**agent_config)

    agent = get_agent( config=agent_config)
    await agent.initialize()

    # result = await agent.invoke(state)
    # print(json.dumps(result, ensure_ascii=False, indent=2))
    async for chunk in agent.astream(state, stream_mode="custom"):
        if chunk.get('type') == 'content':
            print(chunk.get('content'), end='', flush=True)


async def test_text2sql():
    text2sql_agent_config = {
        "agent_type": "text2sql",
        "streaming": False,
        "model_name": "openrouter:qwen/qwen3.5-122b-a10b",
        # "model_name": "openrouter:openai/gpt-oss-120b",
        "urls" : ["http://localhost:9004/sse"]
        
    }

    text2sql_state_config = {
        "agent_type": "text2sql",
        "current_time": current_time
    }

    state = get_agent_state(**text2sql_state_config)
    state.user_request = "Retrieve quarterly revenue data for VIC (Vingroup) company for the year 2025. [tuple]"
    agent_config = get_agent_config(**text2sql_agent_config)

    text2sql_agent = get_agent( config=agent_config)
    await text2sql_agent.initialize()

    # async for chunk in text2sql_agent.astream(state, stream_mode="custom"):
    #     if chunk.get('type') == 'content':
    #         print(chunk.get('content'), end='', flush=True)
    result = await text2sql_agent.ainvoke(state)
    print(result)
    # print(json.dumps(result, ensure_ascii=False, indent=2))


async def test_text2chart():
    text2chart_agent_config = {
        "agent_type": "text2chart",
        "streaming": True,
        "model_name": "openrouter:qwen/qwen3.5-122b-a10b",
        "self_evaluation": True,
        # "model_name": "openrouter:openai/gpt-oss-120b",
        "urls" : []
        
    }

    text2chart_state_config = {
        "agent_type": "text2chart",
        "current_time": current_time,
        "data": {
            "period": [1, 2, 3, 4], 
            "revenue": [84057.6, 46435.5, 39143, 163173]
        }
    }

    state = get_agent_state(**text2chart_state_config)
    state.user_request = "Retrieve quarterly revenue data for VIC (Vingroup) company for the year 2025. [tuple]"
    agent_config = get_agent_config(**text2chart_agent_config)

    text2chart_agent = get_agent( config=agent_config)
    await text2chart_agent.initialize()

    async for chunk in text2chart_agent.astream(state, stream_mode="custom"):
        if chunk.get('type') == 'content':
            print(chunk.get('content'), end='', flush=True)
    
    # result = await text2chart_agent.ainvoke(state)
    # print(result)
    # print(json.dumps(result, ensure_ascii=False, indent=2))


async def test_bi_agent():
    text2sql_agent_config = {
        "agent_type": "text2sql",
        "streaming": True,
        "model_name": "openrouter:qwen/qwen3.5-122b-a10b",
        # "model_name": "openrouter:openai/gpt-oss-120b",
        "urls" : ["http://localhost:9004/sse"]
        
    }

    text2chart_agent_config = {
        "agent_type": "text2chart",
        "streaming": False,
        "model_name": "openrouter:qwen/qwen3.5-122b-a10b",
        # "model_name": "openrouter:openai/gpt-oss-120b",
        "urls" : []
        
    }

    bi_agent_config = {
        "agent_type": "bi_agent",
        "streaming": True,
        "model_name": "openrouter:qwen/qwen3.5-122b-a10b",
        # "model_name": "openrouter:openai/gpt-oss-120b",
        "text2sql_agent_config": text2sql_agent_config,
        "text2chart_agent_config": text2chart_agent_config,
        
    }

    text2sql_state_config = {
        "agent_type": "text2sql",
        "current_time": current_time
    }

    text2chart_state_config = {
        "agent_type": "text2chart",
        "current_time": current_time
    }

    bi_agent_state_config = {
        "agent_type": "bi_agent",
        "current_time": current_time,
        "text2sql_state_config": text2sql_state_config,
        "text2chart_state_config": text2chart_state_config
    }


    state = get_agent_state(**bi_agent_state_config)
    state.user_request = "Vẽ biểu đồ biến động doanh thu của VIC trong năm 2025"
    agent_config = get_agent_config(**bi_agent_config)

    bi_agent = get_agent( config=agent_config)
    await bi_agent.initialize()

    async for chunk in bi_agent.astream(state, stream_mode="custom"):
        if chunk.get('type') == 'content':
            print(chunk.get('content'), end='', flush=True)




if __name__ == "__main__":

    asyncio.run(test_bi_agent())
