"""Entry point: ``python -m mcp_server`` speaks MCP over stdio."""
from utils import app_mode

app_mode.headless = True  # before any import that may start Qt work: no window, no event loop

from mcp_server.server import mcp  # noqa: E402

if __name__ == "__main__":
    mcp.run("stdio")
