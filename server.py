"""server.py - the CGPA MCP server (Assignment 3, Task 1).

Every function in tools.py is registered as an MCP tool. FastMCP builds each tool's
input schema from the type hints and its description from the docstring, exactly like
@tool did for LangChain - but now ANY MCP client (any language, any framework) can
list and call them.

Run locally:   python server.py          -> http://127.0.0.1:8000/mcp
Test, no LLM:  fastmcp list server.py
               fastmcp call server.py get_credit_hours semesters='[5,6]'

When hosted (Render, Horizon, ...) the platform sets PORT; HOST defaults to 127.0.0.1
locally and should be 0.0.0.0 on a host (render.yaml / Dockerfile set it).
"""

import os

from fastmcp import FastMCP

from tools import (
    calculate_new_cgpa,
    calculate_semester_gpa,
    get_completed_credit_hours,
    get_credit_hours,
    get_horizon_credit_hours,
    get_remaining_credit_hours,
    get_semester_courses,
    marks_to_grade_points,
    required_gpa_for_target,
    save_report,
)

mcp = FastMCP("cgpa")

# turns a plain function into an MCP tool (name = function name, description = docstring)
mcp.tool(marks_to_grade_points)
mcp.tool(calculate_semester_gpa)
mcp.tool(calculate_new_cgpa)
mcp.tool(required_gpa_for_target)
mcp.tool(get_semester_courses)
mcp.tool(get_remaining_credit_hours)
mcp.tool(save_report)
mcp.tool(get_completed_credit_hours)
mcp.tool(get_horizon_credit_hours)
mcp.tool(get_credit_hours)


if __name__ == "__main__":
    mcp.run(
        transport="http",  # streamable HTTP, served at /mcp
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
    )
