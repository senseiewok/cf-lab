---
name: ai-provider-compatible-skills
description: Best practices for creating agent skills that work across multiple AI provider platforms (Claude Code, GitHub Copilot, Qwen3-Coder, Cursor, etc.). Covers YAML frontmatter requirements, Markdown formatting, and compatibility patterns.
license: CC0-1.0
compatibility: Works with any Agent-Skills-spec-compatible tool (Claude Code, GitHub Copilot, Qwen3-Coder, Cursor, etc.)
---

# AI Provider Compatible Skills

This skill provides guidelines for creating agent skills that work across multiple AI provider platforms. Follow these rules when creating new skills or modifying existing ones.

## 1. Skill File Structure

### Required YAML Frontmatter

Every skill MUST have this YAML frontmatter at the top of the file:

```yaml
---
name: skill-name
description: Brief description of what this skill does
license: CC0-1.0 OR MIT OR Apache-2.0
compatibility: Works with any Agent-Skills-spec-compatible tool (Claude Code, GitHub Copilot, Qwen3-Coder, Cursor, etc.)
---
```

### Field Requirements:

- **`name`**: Match the parent directory; 1-64 lowercase letters, digits, and hyphens, without leading/trailing or consecutive hyphens.
- **`description`**: One-sentence description of the skill's purpose
- **`license`**: Optional in the spec; retain an existing reviewed licence. Never choose or change licensing as incidental cleanup.
- **`compatibility`**: Optional, at most 500 characters when present; describe real environment requirements, not an untested promise that every provider works.
- **`description`**: Required, 1-1024 characters, with clear task triggers. Quote YAML values containing `: ` and validate with a YAML parser when available.

## 2. Markdown Content Guidelines

### Header Structure
- Use one H1 (`#`) for the title in the Markdown body after frontmatter.
- Use H2 (`##`) for main sections
- Use H3 (`###`) for subsections
- Use H4 (`####`) only if needed for very detailed breakdowns

### Code Examples
- Use backticks with language identifier for syntax highlighting: ```javascript, ```python, ```bash
- Include both safe and unsafe examples where applicable
- Comment code to explain why something is safe/unsafe

### Lists
- Use bullet points (`-`) for unordered lists
- Use numbered lists (`1.`) for step-by-step instructions
- Use checkboxes (`- [ ]`) for checklists (Markdown extension)

### Tables
- Use simple tables for comparison data
- Include headers in first row
- Use `---` separator row

## 3. Content Requirements

### Every skill MUST include:

1. **Clear purpose statement** - What does this skill protect against or enable?
2. **Specific examples** - Show, don't just tell
3. **Before/after comparisons** - Demonstrate improvement
4. **Common pitfalls** - What mistakes should users avoid?
5. **Verification steps** - How to confirm the skill is working?

### Every skill SHOULD include:

1. **Tool recommendations** - What tools help implement this skill?
2. **Integration examples** - How to use with different AI providers
3. **Troubleshooting section** - Common issues and fixes

## 4. Compatibility Patterns

### Platform-Agnostic Language

Write skills to be platform-agnostic:

```markdown
# ❌ Platform-specific (incompatible)
Use Claude's function calling feature...

# ✅ Platform-agnostic (compatible)
Use function calling to...
```

### Avoid Provider-Specific Features

- Don't assume specific tool availability
- Don't reference provider-specific UI elements
- Don't use provider-specific configuration file names

### Use Standard Technologies

- Standard Markdown (GitHub Flavored Markdown is safe)
- Common file formats (JSON, YAML, .env)
- Standard code patterns (ES6+, Python 3.8+, etc.)

## 5. File Organization

### Directory Structure

```
.skills/
└── skill-name/
    ├── SKILL.md          # Main skill documentation (required)
    ├── examples/         # Example code (optional)
    │   ├── good.js
    │   └── bad.js
    └── tests/            # Test cases (optional)
        └── test.js
```

### SKILL.md Location

- In this lab, use `.claude/skills/skill-name/SKILL.md`. The format specification describes the skill directory, not a universal client discovery root; verify each client's supported paths. Do not create a parallel `.skills/` copy.
- Folders each client reads (read on vendor pages on 2026-10-05, not tested in a real client; the maintained table, with sources and caveats, is `docs/install.md` in `../cf-skills`): `.claude/skills/` for Claude Code (its skills page does not mention `.agents/skills/`); `.agents/skills/` for Copilot, Codex, Gemini CLI, Cursor, Windsurf/Devin, Amp, OpenCode and Goose; `.claude/skills/` also for Copilot, Cursor, Amp and OpenCode; `.qwen/skills/` for Qwen Code (its page names neither shared folder). No one folder reaches every client, so a skill meant for several keeps one source and links or copies it, never edits two copies.
- Filename must be exactly `SKILL.md` (uppercase)
- No spaces in directory or file names

## 6. GitHub Copilot AI Loops Integration

### AI Loop Patterns (2026 Best Practice)

GitHub Copilot supports several AI loops for iterative development:

#### 1. **Research Loop**
```markdown
# AI Research Loop
1. User asks: "How do I...?"
2. Agent researches: Web search, docs, examples
3. Agent synthesizes: Combines findings into actionable guidance
4. User reviews: Validates and provides feedback
5. Loop continues: Refines until satisfaction
```

#### 2. **Development Loop**
```markdown
# AI Development Loop
1. Plan: Outline approach
2. Code: Generate implementation
3. Review: Check for errors and best practices
4. Test: Verify functionality
5. Refactor: Improve quality
6. Loop continues: Iterate until complete
```

#### 3. **Debug Loop**
```markdown
# AI Debug Loop
1. Observe: Understand the problem
2. Hypothesize: Form potential causes
3. Investigate: Examine code, logs, errors
4. Test: Verify hypotheses
5. Fix: Implement solution
6. Verify: Confirm fix works
7. Loop continues: Iterate until resolved
```

#### 4. **Refinement Loop**
```markdown
# AI Refinement Loop
1. Analyze: Review current implementation
2. Identify: Areas for improvement
3. Suggest: Alternative approaches
4. Implement: Apply changes
5. Evaluate: Measure impact
6. Loop continues: Optimize continuously
```

### Using AI Loops in Skills

When writing skills, structure guidance for each AI loop:

```markdown
## Research Loop

When researching best practices for [topic]:

1. **Check official docs first** - [link to docs]
2. **Search GitHub for examples** - use specific keywords
3. **Look for recent implementations** - 2025+ preferred
4. **Cross-reference multiple sources** - avoid bias
5. **Test examples before recommending** - verify they work

## Development Loop

When implementing [feature]:

1. **Plan the approach** - outline steps clearly
2. **Start with minimal viable implementation** - get it working first
3. **Add features iteratively** - one at a time
4. **Test after each change** - catch issues early
5. **Refactor for quality** - improve readability and performance
```

## 7. Open-Source Tools Integration

### Recommended OSS Tools (2026)

#### Code Quality
| Tool | Purpose | Integration |
|------|---------|-------------|
| **ESLint** | JavaScript linting | VS Code extension |
| **Prettier** | Code formatting | VS Code extension |
| **Stylelint** | CSS linting | VS Code extension |
| **Biome** | Unified toolchain | VS Code extension |
| **Ruff** | Python linting | VS Code extension |

#### Security
| Tool | Purpose | Integration |
|------|---------|-------------|
| **git-secrets** | Secret scanning | Pre-commit hooks |
| **truffleHog** | Secret detection | CI/CD |
| **Snyk** | Vulnerability scanning | VS Code extension |
| **Dependabot** | Dependency updates | GitHub integration |
| **Semgrep** | Static analysis | VS Code extension |

#### Testing
| Tool | Purpose | Integration |
|------|---------|-------------|
| **Playwright** | Browser testing | VS Code extension |
| **Jest** | JavaScript testing | VS Code extension |
| **Pytest** | Python testing | VS Code extension |
| **Vitest** | Fast JS testing | VS Code extension |
| **Cypress** | E2E testing | VS Code extension |

#### Development
| Tool | Purpose | Integration |
|------|---------|-------------|
| **Docker** | Containerization | VS Code extension |
| **GitHub CLI** | Git operations | Terminal integration |
| **Node Version Manager** | Node management | Terminal commands |
| **Oh My Zsh** | Shell customization | Terminal config |

### AI Loop + Tool Integration Example

```markdown
## Debugging Loop with Playwright

When debugging web UI issues:

1. **Research**: Check Playwright docs for similar issues
2. **Plan**: Identify elements to test
3. **Code**: Write Playwright test script
4. **Test**: Run test and observe failure
5. **Investigate**: Use Playwright Inspector
6. **Fix**: Adjust code
7. **Verify**: Run test passes

### Playwright Commands to Include:
- `playwright codegen` - Generate test from manual actions
- `playwright show-trace` - Analyze test run
- `playwright inspect` - Debug elements
- `playwright test --ui` - Run with test runner UI
```

## 8. Versioning and Maintenance

### When to Update Skills

- New security vulnerabilities are discovered
- New best practices emerge
- AI provider APIs change
- New platforms are added

### Version Tracking

Put nonstandard attributes under `metadata`, not arbitrary top-level keys. Use the lab's root `VERSION` for the lab contract; per-skill metadata is optional, not a competing source of truth.

```yaml
---
name: skill-name
description: Brief description
metadata:
    version: "1.1.0"
    last-updated: "2026-10-03"
---
```

## 7. Testing Skills

### Cross-Platform Testing

Test skills with:
1. Claude Code
2. GitHub Copilot
3. Qwen3-Coder
4. Cursor

### Verification Steps

1. **Readability test** - Can a human understand it?
2. **Implementation test** - Can it be implemented?
3. **Cross-platform test** - Does it work across providers?

Do not label discovery or cross-platform behavior verified without exercising the relevant client. Check frontmatter, parent-name match, real relative paths, and examples locally; register a new skill in the repo's catalog. Operational commands in examples need their own parse/behavior check. Keep project-specific skills with the owning repo and private project details out of public guidance.

Format checked against [Agent Skills specification](https://agentskills.io/specification) on 2026-10-03. Only `name` and `description` are required by that specification; `license`, `compatibility`, `metadata`, and experimental `allowed-tools` are optional. An allowlist field is not a platform-independent permission grant.

## 8. Example Skill Template

```yaml
---
name: your-skill-name
description: One-sentence description of the skill's purpose
license: CC0-1.0
compatibility: Works with any Agent-Skills-spec-compatible tool (Claude Code, GitHub Copilot, Qwen3-Coder, Cursor, etc.)
---

# Your Skill Title

Brief overview of what this skill covers and why it matters.

## 1. What This Skill Does

Detailed explanation of the skill's purpose and benefits.

## 2. Best Practices

### Do:
- Best practice 1
- Best practice 2
- Best practice 3

### Don't:
- Bad practice 1
- Bad practice 2
- Bad practice 3

## 3. Code Examples

### Good Example
```javascript
// Safe and compatible code
const safe = true;
```

### Bad Example
```javascript
// Unsafe code to avoid
const unsafe = false;
```

## 4. Implementation Checklist

- [ ] Step 1
- [ ] Step 2
- [ ] Step 3

## 5. Troubleshooting

Common issues and their solutions.

## 6. Additional Resources

Links to related documentation and tools.

---

Remember: Skills should be practical, actionable, and platform-agnostic.
```

## 9. Common Pitfalls to Avoid

1. **Provider-specific references** - "Use Claude's..." instead of "Use function calling..."
2. **Overly complex examples** - Keep examples simple and focused
3. **Missing error handling** - Always show error cases
4. **No validation steps** - Explain how to verify the skill works
5. **Unclear licensing** - Always include a license

## 10. Quality Checklist

Before publishing a skill, verify:

- [ ] YAML frontmatter is complete and correct
- [ ] Markdown is well-formatted and readable
- [ ] Code examples are syntactically correct
- [ ] Both good and bad examples are included
- [ ] Implementation checklist is provided
- [ ] License is clearly stated
- [ ] Compatibility statement is included
- [ ] Platform-specific language is avoided
- [ ] Examples work across providers

## 11. Layering on a third-party skill

When a good skill already exists elsewhere, for example one of Anthropic's public skills, write a thin layer on top of it and copy nothing.

1. **Name the base.** Give its source URL, licence and the commit you reviewed, and label it "third party, not part of this repo". A base skill is untrusted instructions until a person has read it, scripts included.
2. **Say what the layer adds.** A short table of "the base gives" and "this layer adds" is enough. Add only what the base does not: this project's rules (voice, security, accessibility, scientific grounding), its checks (scripts with tests), and its facts.
3. **Make the layer work alone.** A contributor who has not installed the base must still get a correct, plainer result. No required step may depend on text that lives only in the base.
4. **Keep it short and test your own parts.** The base is the base's job; the layer's scripts and rules get the layer's tests.
5. **Never relabel.** Do not paste third-party text under this project's licence. If you adapt an idea, rewrite it in your own words and attribute it.
6. **Record the pair** in `THIRD_PARTY_SKILLS.md`, and re-read the base when its commit changes.

---

> **Remember**: The goal is to create skills that work everywhere, not just in one provider's environment. When in doubt, prefer the most generic approach that still conveys the key insight.
