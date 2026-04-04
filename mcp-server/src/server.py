# main.py
import os
import importlib
import argparse
from fastmcp import FastMCP
from client import PostgresClient
from env_config import load_env_config, get_env

# Load environment configuration
load_env_config()

current_dir = os.path.dirname(os.path.abspath(__file__))

# --- 서버 및 클라이언트 초기화 ---
mcp = FastMCP("Tools for Financal Data Analysis")


client = PostgresClient(
    postgres_url=get_env('POSTGRES_URL')
)


script_dir = os.path.dirname(os.path.abspath(__file__))
tools_dir = os.path.join(script_dir, "tools")

# --- 2. 'tools' 디렉토리에서 모든 도구를 자동으로 찾아 등록하는 로직 ---
print("--- 도구 자동 탐색 시작 ---")
print(f"탐색 대상 디렉토리: {tools_dir}")

try:
    for filename in os.listdir(tools_dir):
        # Only target Python files and exclude special files like __init__.py
        if filename.endswith(".py") and not filename.startswith("__"):
            # Module path is based on absolute file system path for more stable loading.
            # Using module loader directly for more robust approach.
            module_name = f"tools.{filename[:-3]}"

            try:
                module = importlib.import_module(module_name)

                if hasattr(module, "register_tool"):
                    register_function = getattr(module, "register_tool")
                    register_function(mcp, client)
                    print(f"✅ Tool '{module_name}' registered successfully.")
                else:
                    print(f"⚠️ Module '{module_name}' has no 'register_tool' function, skipping.")

            except Exception as e:
                print(f"❌ Error registering tool '{module_name}': {e}")

except FileNotFoundError:
    print(f"❌ Fatal error: Directory '{tools_dir}' not found. Please check file structure.")
except Exception as e:
    print(f"❌ Unexpected error while loading tools: {e}")


# --- 서버 실행 ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SQL MCP Server")
    parser.add_argument("--transport", choices=["sse", "http", "stdio"], default="sse")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=9004)
    args = parser.parse_args()

    # FastMCP.run commonly supports 'transport'. Host/port are relevant for SSE but may be optional.
    # To maintain compatibility, we only pass 'transport'. SSE default port is expected to be 9004.
    if args.transport in ["sse", "http"]:
        mcp.run(transport=args.transport, host=args.host, port=args.port)
    else:
        mcp.run(transport="stdio")