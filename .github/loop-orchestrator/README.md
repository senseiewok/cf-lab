# AI Loop Orchestrator

> **Status: not functional.** `loop.py` exits immediately with `not implemented`, and the "AI council review" and consensus voting described below are a design sketch, not behaviour. `AGENTS.md` governs: deterministic checks decide when work is done, and a finding is never decided by majority vote.

A Python-based autonomous development loop orchestrator for the Sensei Ewok Research Lab.

## Overview

This system implements an autonomous AI loop with:
- **Auto-trigger detection**: File changes, scheduled intervals, and keyword prompts
- **Multi-stage execution**: Task analysis → Plan generation → Execution → Verification → Learning
- **AI council review**: Independent review with consensus voting for high-impact changes

## Requirements

- Python 3.10+
- Python packages: `watchdog`, `asyncio`

## Configuration

### triggers.json

Configure when the loop should trigger:

```json
{
  "triggers": {
    "file_change": {
      "enabled": true,
      "paths": ["src/**/*.css", "src/**/*.js", "**/*.md"],
      "debounce": 5000
    },
    "schedule": {
      "enabled": true,
      "interval_hours": 6
    },
    "prompt": {
      "enabled": true,
      "keywords": ["review", "council", "loop", "auto"]
    }
  }
}
```

### loop-config.json

Configure execution settings:

```json
{
  "models": {
    "primary": "qwen3.8:27b",
    "challenger": "qwen3.8:27b",
    "council": ["qwen3.8:27b"]
  },
  "execution": {
    "auto_verify": true,
    "auto_commit": false,
    "max_retries": 3
  }
}
```

## Usage

### Start the loop

```bash
python loop.py
```

### Trigger manually

```bash
python loop.py --trigger prompt --keywords "review, council"
```

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Loop Orchestrator                    │
└─────────────────────────────────────────────────────────┘
                            │
    ┌───────────────────────┼───────────────────────┐
    ▼                       ▼                       ▼
┌───────────────┐   ┌─────────────────┐   ┌─────────────────┐
│  Trigger      │   │  Task Analysis  │   │  AI Council     │
│  Detection    │   │  & Plan         │   │  Review         │
│  - File       │   │  - Problem      │   │  - Deliberation   │
│  - Schedule   │   │  - Solution     │   │  - Voting       │
│  - Prompt     │   │  - Approach     │   │  - Consensus      │
└───────────────┘   └─────────────────┘   └─────────────────┘
                            │                       │
                            ▼                       ▼
                    ┌─────────────────┐   ┌─────────────────┐
                    │  Execution      │   │  Verification   │
                    │  - Code gen     │   │  - Test         │
                    │  - File writes  │   │  - Validation   │
                    └─────────────────┘   └─────────────────┘
                            │
                            ▼
                    ┌─────────────────┐
                    │  Learning Store │
                    │  - Successes    │
                    │  - Failures     │
                    │  - Patterns     │
                    └─────────────────┘
```

## Best Practices

1. **Use local models only**: All AI work uses `qwen3.8:27b` in fast mode (thinking off) - no online API models
2. **Review before deploy**: High-impact changes go to council review
3. **Auto-verify**: Test changes automatically before committing
4. **Store learnings**: Record what worked and what failed for future improvement

## See Also

- [AI Loop Council Skill](../../.claude/skills/ai-loop-council/SKILL.md) - Council architecture details
- [Copilot Instructions](../copilot-instructions.md) - Model routing and configuration