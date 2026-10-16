"""Tests for the tool-limited reviewer agent definition (T-0073).

Verifies that the reviewer agent definition restricts tools strictly to Read, Grep,
and Glob, and that any execution call (e.g. Bash, PowerShell) is refused.
"""
from __future__ import annotations

import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[3]
AGENT_FILE = REPO_ROOT / ".claude" / "agents" / "reviewer.md"


def parse_frontmatter(content: str) -> dict:
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    end_idx = -1
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break
    if end_idx == -1:
        return {}
    
    data = {}
    current_key = None
    for line in lines[1:end_idx]:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" in line and not line.startswith(" ") and not line.startswith("\t"):
            key, val = line.split(":", 1)
            current_key = key.strip()
            val = val.strip()
            if val:
                data[current_key] = val
            else:
                data[current_key] = []
        elif stripped.startswith("-") and current_key:
            item = stripped.lstrip("-").strip()
            if isinstance(data.get(current_key), list):
                data[current_key].append(item)
    return data


def evaluate_agent_tool_call(agent_tools: list[str], requested_tool: str) -> tuple[bool, str]:
    """Check if a tool call is permitted by the agent definition."""
    if requested_tool in agent_tools:
        return True, f"Permitted: tool '{requested_tool}' is allowed"
    return False, f"Refused: tool '{requested_tool}' is not in allowed tools ({', '.join(sorted(agent_tools))})"


class ReviewerAgentDefinitionTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(AGENT_FILE.exists(), f"Agent definition missing at {AGENT_FILE}")
        self.content = AGENT_FILE.read_text(encoding="utf-8")
        self.fm = parse_frontmatter(self.content)

    def test_reviewer_agent_declares_exact_read_only_tools(self):
        tools = self.fm.get("tools")
        self.assertIsInstance(tools, list, "Frontmatter must define a tools list")
        self.assertEqual(set(tools), {"Read", "Grep", "Glob"}, "Tools must be strictly Read, Grep, Glob")

    def test_bash_and_powershell_tools_are_absent_from_agent_definition(self):
        tools = set(self.fm.get("tools", []))
        self.assertNotIn("Bash", tools)
        self.assertNotIn("PowerShell", tools)
        self.assertNotIn("Edit", tools)
        self.assertNotIn("Write", tools)

    def test_bash_call_is_refused(self):
        tools = self.fm.get("tools", [])
        allowed, reason = evaluate_agent_tool_call(tools, "Bash")
        self.assertFalse(allowed, "Bash invocation must be refused for reviewer agent")
        self.assertIn("Refused", reason)
        self.assertIn("Bash", reason)

    def test_powershell_call_is_refused(self):
        tools = self.fm.get("tools", [])
        allowed, reason = evaluate_agent_tool_call(tools, "PowerShell")
        self.assertFalse(allowed, "PowerShell invocation must be refused for reviewer agent")
        self.assertIn("Refused", reason)

    def test_read_and_grep_calls_are_permitted(self):
        tools = self.fm.get("tools", [])
        for tool in ["Read", "Grep", "Glob"]:
            allowed, _ = evaluate_agent_tool_call(tools, tool)
            self.assertTrue(allowed, f"{tool} must be permitted for reviewer agent")


if __name__ == "__main__":
    unittest.main()
