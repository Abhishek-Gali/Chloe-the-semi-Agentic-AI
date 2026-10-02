"""
Project Chloe - Autonomous MCP Tool Dispatcher
Validates security policies against operating modes, dispatches actions, and returns structured findings.
"""

import json
import logging
from typing import Dict, Any, Optional
from app.core.modes import OperatingMode, ModePolicy
from app.mcp.system_tools import SystemTools
from app.mcp.cyber_tools import CyberTools
from app.mcp.web_search import WebSearchTool

logger = logging.getLogger(__name__)

class MCPDispatcher:
    def __init__(self):
        self.tool_registry = {
            # System Tools
            "launch_app": lambda p: SystemTools.launch_app(p.get("app_name", "")),
            "open_notepad_with_content": lambda p: SystemTools.open_notepad_with_content(p.get("content", ""), p.get("title", "Chloe_Note")),
            "open_chrome_search": lambda p: SystemTools.open_chrome_search(p.get("query", "")),
            "write_file": lambda p: SystemTools.write_file(p.get("path", ""), p.get("content", "")),
            "create_folder": lambda p: SystemTools.create_folder(p.get("path", "")),
            "explore_directory": lambda p: SystemTools.explore_directory(p.get("path", ".")),
            "run_shell_command": lambda p: SystemTools.run_shell_command(p.get("command", "")),
            "get_system_info": lambda p: SystemTools.get_system_info(),
            "get_tailscale_status": lambda p: SystemTools.get_tailscale_status(),
            
            # Cyber Tools
            "cve_lookup": lambda p: CyberTools.cve_lookup(p.get("cve_id"), p.get("keyword")),
            "threat_check": lambda p: CyberTools.threat_check(p.get("ip"), p.get("domain")),
            "virustotal_check": lambda p: CyberTools.virustotal_check(p.get("resource", "")),
            "run_scanner": lambda p: CyberTools.run_scanner(p.get("target", "127.0.0.1"), p.get("ports")),
            
            # Web Search
            "web_search": lambda p: WebSearchTool.search_and_scrape(p.get("query", ""), int(p.get("max_results", 3))),
        }

    async def execute_tool(self, tool_name: str, params: Dict[str, Any], mode: OperatingMode = OperatingMode.PARTIALLY_ISOLATED) -> Dict[str, Any]:
        """
        Executes a registered tool if authorized under the current mode policy.
        """
        logger.info(f"MCP Dispatcher: Request to execute '{tool_name}' under mode '{mode.value}' with params: {params}")

        # Security policy check
        if not ModePolicy.is_action_allowed(mode, tool_name):
            return {
                "status": "policy_denied",
                "tool": tool_name,
                "message": f"Execution of tool '{tool_name}' is prohibited under '{mode.value}' mode."
            }

        # Lazy check for vault query
        if tool_name == "query_vault":
            try:
                from app.pipeline.rag_ingestion import rag_pipeline
                query = params.get("query", "")
                results = await rag_pipeline.query_documents(query)
                return {"status": "success", "tool": "query_vault", "results": results}
            except Exception as e:
                return {"status": "error", "tool": "query_vault", "message": str(e)}

        handler = self.tool_registry.get(tool_name)
        if not handler:
            return {
                "status": "error",
                "tool": tool_name,
                "message": f"Tool '{tool_name}' not found in registry. Available: {list(self.tool_registry.keys())}"
            }

        try:
            # Check if handler returns coroutine
            import asyncio
            result = handler(params)
            if asyncio.iscoroutine(result):
                result = await result
            return {
                "status": "success",
                "tool": tool_name,
                "result": result
            }
        except Exception as e:
            logger.error(f"Error executing {tool_name}: {e}")
            return {
                "status": "error",
                "tool": tool_name,
                "message": f"Tool execution failed: {str(e)}"
            }

mcp_dispatcher = MCPDispatcher()
