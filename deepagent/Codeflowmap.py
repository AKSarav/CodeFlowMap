#!/usr/bin/env python3
"""
CodeFlowMap — Deep Agent CLI for Codebase Architecture Diagrams

Analyzes any codebase and generates C4-level Mermaid diagrams using a Deep Agent
powered by LangGraph. The agent autonomously plans, scans, analyzes, and generates
diagrams with built-in self-correction and context management.

Tree-sitter is the primary structural parser. The LLM (via LangChain's init_chat_model)
handles architecture analysis, class enrichment, flow tracing, and diagram generation.

Analysis Protocol:
  Step 1 — Discover entry points & runtime context (tree-sitter + BFS)
  Step 2 — Map modules, layers, external systems (LLM reasoning)
  Step 3 — Trace class/interface structures (tree-sitter AST + LLM enrichment)
  Step 4 — Trace data & control flow (LLM reasoning)
  → Generate Component Diagram (C4 Level 3)
  → Generate Class Diagram (C4 Level 4)

Supports: Python, TypeScript, JavaScript, Java, Go, C#, Ruby, Rust
LLM Providers: Any provider supported by LangChain (OpenAI, Anthropic, Google, Ollama, Azure, etc.)

Usage:
    python codeflowmap.py --repo /path/to/repo
    python codeflowmap.py --repo /path/to/repo --output ./diagrams --verbose
    python codeflowmap.py --repo /path/to/repo --module src/auth-service
    python codeflowmap.py --repo /path/to/repo --model anthropic:claude-sonnet-4-6
"""

import argparse
import ast
import json
import os
import sys
import re
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from langchain.agents.middleware.todo import write_todos
from treesitter_tool import CodeStructureTool, RepoIndexTool, SymbolSearchTool, get_general_code_exclusions
from langgraph.checkpoint.memory import MemorySaver

# ── tree-sitter (required for structural parsing) ───────────────────────────
from tree_sitter import Language, Parser, Node

import treesitter_tool  # type: ignore

# Language grammars — each is optional; install what you need.
# Missing grammars fall back to regex-based extraction.
_tspython = _tstypescript = _tsjavascript = _tsjava = None
_tsgo = _tscsharp = _tsruby = _tsrust = None

try:
    import tree_sitter_python as _tspython            # type: ignore
except ImportError:
    pass
try:
    import tree_sitter_typescript as _tstypescript     # type: ignore
except ImportError:
    pass
try:
    import tree_sitter_javascript as _tsjavascript     # type: ignore
except ImportError:
    pass
try:
    import tree_sitter_java as _tsjava                 # type: ignore
except ImportError:
    pass
try:
    import tree_sitter_go as _tsgo                     # type: ignore
except ImportError:
    pass
try:
    import tree_sitter_c_sharp as _tscsharp            # type: ignore
except ImportError:
    pass
try:
    import tree_sitter_ruby as _tsruby                 # type: ignore
except ImportError:
    pass
try:
    import tree_sitter_rust as _tsrust                 # type: ignore
except ImportError:
    pass

from dotenv import load_dotenv

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger("codeflowmap")

# Optional rich console for pretty printing
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn
    # Force UTF-8 encoding on the Rich console so unicode symbols render
    # correctly on Windows terminals that default to cp1252.
    import io as _io
    _safe_stdout = _io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True
    ) if hasattr(sys.stdout, "buffer") else sys.stdout
    console = Console(file=_safe_stdout, highlight=False)
except ImportError:
    console = None
    Progress = None

# ============================================================================
# 1. IMPORTS & ENV LOADING
# ============================================================================

load_dotenv()

# ============================================================================
# 2. CLI ARGUMENT PARSER
# ============================================================================

def parse_arguments() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="CodeFlowMap: Analyze a codebase and generate C4-level Mermaid diagrams.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python codeflowmap.py --repo /path/to/repo
  python codeflowmap.py --repo /path/to/repo --output ./diagrams --verbose
  python codeflowmap.py --repo /path/to/repo --module src/payments
        """
    )
    parser.add_argument("--repo", required=True,
                        help="Absolute or relative path to the repository root")
    parser.add_argument("--output", default="./codeflowmap_output",
                        help="Directory to write diagram files (default: ./codeflowmap_output)")
    parser.add_argument("--module", default=None,
                        help="Scope analysis to a subfolder (relative to repo root)")
    parser.add_argument("--model", default=None,
                        help="LiteLLM model identifier (e.g. gpt-4o, anthropic/claude-sonnet-4-20250514, "
                             "gemini/gemini-2.0-flash, ollama/llama3). Overrides CODEFLOWMAP_MODEL env var.")
    parser.add_argument("--context", default=None,
                        help="Free-text background about this codebase passed to every LLM prompt "
                             '(e.g. "Multi-tenant SaaS, payments via Stripe, Postgres + Redis")')
    parser.add_argument("--include-tests", action="store_true", dest="include_tests",
                        help="Include test/spec files in analysis (useful for test framework repos)")
    parser.add_argument("--verbose", action="store_true",
                        help="Print reasoning steps to terminal")
    parser.add_argument("--format", choices=["mmd", "md"], default="md",
                        help="Output format: mmd (Mermaid) or md (Markdown, default)")
    return parser.parse_args()

# ============================================================================
# 8. CORE SCAN FUNCTION
# ============================================================================


def _strip_mermaid_fences(text: str) -> str:
    """
    Robustly strip a single outermost ```mermaid / ``` fence from LLM output.
    Preserves all internal content (including any %% comments or nested backtick examples).
    """
    text = text.strip()
    # Remove leading fence
    text = re.sub(r'^```(?:mermaid|flowchart|graph|classDiagram|sequence)?[ \t]*\n?', '', text)
    # Remove trailing fence (only if it's the last line)
    text = re.sub(r'\n?```[ \t]*$', '', text)
    return text.strip()


def _validate_mermaid(diagram: str, kind: str) -> tuple:
    """
    Comprehensive Mermaid syntax validation.
    Returns (is_valid: bool, issues: list[str]).

    Checks performed:
      - Correct first keyword for diagram type
      - No leftover markdown fences inside the diagram
      - Balanced braces (class bodies)
      - subgraph / end count matches (flowchart)
      - Node IDs do not contain spaces
      - Edge syntax is well-formed (no bare arrows without target)
      - classDiagram: class blocks are properly closed
      - classDiagram: no 'graph' / 'flowchart' keyword leaked in
      - flowchart: no 'classDiagram' keyword leaked in
      - No obvious truncation (diagram ends mid-statement)
      - No raw Python/JS code accidentally included
    """
    issues = []
    if not diagram or not diagram.strip():
        return False, ["Empty diagram"]

    stripped = diagram.strip()
    lines = stripped.splitlines()
    first = lines[0].strip() if lines else ""

    # ── 1. Correct opening keyword ──────────────────────────────────────────
    if kind == "component":
        if not re.match(r'^flowchart\s+[A-Z]{2}', first) and not re.match(r'^graph\s+[A-Z]{2}', first):
            issues.append(f"Must start with 'flowchart TD' (or LR/RL/BT), got: {first!r}")
    elif kind == "class":
        if not first.startswith("classDiagram"):
            issues.append(f"Must start with 'classDiagram', got: {first!r}")
        # Catch leaked flowchart keyword
        if re.search(r'^\s*(flowchart|graph)\s', stripped, re.MULTILINE):
            issues.append("classDiagram contains leaked 'flowchart'/'graph' keyword")

    # ── 2. No leftover markdown fences ──────────────────────────────────────
    if re.search(r'^```', stripped, re.MULTILINE):
        issues.append("Diagram contains leftover markdown fences (```)")

    # ── 3. Balanced braces ──────────────────────────────────────────────────
    opens = stripped.count("{")
    closes = stripped.count("}")
    if abs(opens - closes) > 2:
        issues.append(f"Unbalanced braces: {opens} open, {closes} close")

    # ── 4. subgraph / end balance ────────────────────────────────────────────
    sg_count = len(re.findall(r'^\s*subgraph\b', stripped, re.MULTILINE))
    end_count = len(re.findall(r'^\s*end\s*$', stripped, re.MULTILINE))
    if sg_count != end_count:
        issues.append(f"subgraph/end mismatch: {sg_count} subgraphs, {end_count} 'end' tokens")

    # ── 5. Node IDs must not contain spaces (flowchart) ─────────────────────
    # Only flag actual node declaration lines, not subgraph/classDef/end/comment lines.
    if kind == "component":
        for _line in lines:
            _ls = _line.strip()
            if re.match(r'^(subgraph\b|classDef\b|%%|end\s*$)', _ls):
                continue
            # Real node definition: identifier with a space before [ ( {
            _bad = re.match(r'^([A-Za-z]\w* +[A-Za-z]\w*)\s*[\[({]', _ls)
            if _bad:
                issues.append(f"Node ID contains space: {_bad.group(1)!r}")
                break  # report once

    # ── 6. Edge syntax: arrow must have a target ────────────────────────────
    dangling = re.findall(r'-->\s*$', stripped, re.MULTILINE)
    if dangling:
        issues.append(f"{len(dangling)} edge(s) with no target node (dangling arrows)")

    # ── 7. classDiagram: class blocks must be closed ────────────────────────
    if kind == "class":
        class_opens = len(re.findall(r'^\s*class\s+\w+\s*\{', stripped, re.MULTILINE))
        if class_opens > 0 and opens < class_opens:
            issues.append(f"{class_opens} class blocks opened but fewer closing braces found")

    # ── 7a. classDiagram: annotation must be INSIDE body, not inline ──────
    if kind == "class":
        inline_annot = re.findall(
            r'^\s*class\s+\w+\s+<<[^>]+>>\s*\{',
            stripped, re.MULTILINE,
        )
        if inline_annot:
            issues.append(
                f"{len(inline_annot)} class(es) have <<annotation>> inline with "
                f"the class declaration. Move annotation INSIDE the body. "
                f"Wrong: `class Foo <<Service>> {{` → "
                f"Correct: `class Foo {{\\n    <<Service>>`"
            )

    # ── 7b. classDiagram: no raw generic angle brackets <T> ──────────────
    if kind == "class":
        raw_generics = re.findall(
            r'[:\s]\w+<\w+>',
            stripped,
        )
        if raw_generics:
            examples = ", ".join(raw_generics[:3])
            issues.append(
                f"Found raw angle-bracket generics ({examples}). "
                f"Mermaid does not support <T> syntax in classDiagram. "
                f"Use ~T~ instead: e.g. List~string~, Observable~any~, EventEmitter~void~"
            )

    # ── 7c. classDiagram: no pipe | in types (union syntax) ──────────────
    if kind == "class":
        pipes_in_types = re.findall(
            r'^\s*[+\-#]\w+.*\|',
            stripped, re.MULTILINE,
        )
        if pipes_in_types:
            issues.append(
                f"{len(pipes_in_types)} field/method line(s) contain '|' (pipe). "
                f"Mermaid classDiagram does not support union types. "
                f"Replace 'Type | null' with 'Type_or_null' or just 'Type'."
            )

    # ── 7d. classDiagram: no array brackets [] in types ──────────────────
    if kind == "class":
        array_brackets = re.findall(
            r'^\s*[+\-#~].*\w+\[\]',
            stripped, re.MULTILINE,
        )
        if array_brackets:
            issues.append(
                f"{len(array_brackets)} field/method line(s) contain '[]' (array brackets). "
                f"Mermaid classDiagram does not support []. "
                f"Use ~Array~ instead: e.g. `items: Item~Array~`."
            )

    # ── 8. Truncation check ──────────────────────────────────────────────────
    last_line = lines[-1].strip() if lines else ""
    # Diagram ends mid-arrow or mid-word → likely truncated
    if re.search(r'(-->|==>|-\.-|\|\s*)$', last_line):
        issues.append("Diagram appears truncated (last line ends with an incomplete arrow)")

    # ── 9. Leaked code artefacts ────────────────────────────────────────────
    if re.search(r'\bdef\s+\w+\s*\(|\bfunction\s+\w+\s*\(|\bimport\s+\w', stripped):
        issues.append("Diagram contains leaked source code (def/function/import keywords)")

    # ── 10. Relationship arrows must have both sides ────────────────────────
    if kind == "class":
        bad_rel = re.findall(r'^\s*(<\|--|<\|\.\.|\*--|o--|-->|\.\.>)\s*$', stripped, re.MULTILINE)
        if bad_rel:
            issues.append(f"{len(bad_rel)} relationship line(s) missing one side")

    return len(issues) == 0, issues


# ============================================================================
# 9. DEEP AGENT TOOLS
# ============================================================================

def scan_repository(repo_path: str) -> str:
    """Validate and return the repository path for the agent to analyze.

    This is a lightweight validation tool that checks if the provided directory
    exists and is accessible. The agent will handle all analysis and scanning logic.

    Args:
        repo_path: Absolute or relative path to the repository directory.

    Returns:
        JSON with validation status, resolved path, and directory info.
    """
    resolved_path = Path(repo_path).resolve()
    
    if not resolved_path.exists():
        return json.dumps({
            "valid": False,
            "error": f"Directory does not exist: {repo_path}",
            "attempted_path": str(resolved_path),
        })
    
    if not resolved_path.is_dir():
        return json.dumps({
            "valid": False,
            "error": f"Path is not a directory: {repo_path}",
            "attempted_path": str(resolved_path),
        })
    
    # Quick check: count files to ensure it's accessible
    try:
        file_count = len(list(resolved_path.rglob("*")))
    except PermissionError:
        return json.dumps({
            "valid": False,
            "error": f"Permission denied accessing directory: {resolved_path}",
            "attempted_path": str(resolved_path),
        })
    
    return json.dumps({
        "valid": True,
        "repository_path": str(resolved_path),
        "file_count": file_count,
        "accessible": True,
    })


def _auto_repair_class_diagram(diagram: str) -> str:
    """Best-effort auto-repair for common classDiagram Mermaid syntax errors."""
    lines = diagram.splitlines()
    repaired: list[str] = []

    for line in lines:
        stripped = line.strip()

        # Fix 1: Move inline <<Annotation>> into the class body.
        # `class Foo <<Service>> {` → `class Foo {` + `    <<Service>>`
        m = re.match(r'^(\s*)class\s+(\w+)\s+(<<[^>]+>>)\s*\{', line)
        if m:
            indent, cls_name, annotation = m.group(1), m.group(2), m.group(3)
            repaired.append(f"{indent}class {cls_name} {{")
            repaired.append(f"{indent}    {annotation}")
            continue

        # Fix 2: Replace angle-bracket generics <T> with ~T~
        if re.search(r'<\w+>', stripped) and not stripped.startswith("%%"):
            line = re.sub(r'<(\w+(?:,\s*\w+)*)>', r'~\1~', line)

        # Fix 3: Replace union pipe `Type | null` with `TypeOrNull`
        line = re.sub(r'(\w+)\s*\|\s*null', r'\1OrNull', line)
        line = re.sub(r'(\w+)\s*\|\s*(\w+)', r'\1Or\2', line)

        # Fix 4: Replace array brackets `Type[]` with `Type~Array~`
        line = re.sub(r'(\w+)\[\]', r'\1~Array~', line)

        repaired.append(line)

    return "\n".join(repaired)


def validate_mermaid_diagram(diagram: str, kind: str) -> str:
    """Validate a Mermaid diagram for syntax correctness and attempt auto-repair.

    Call this after generating each diagram to check for errors before including
    it in the final output.

    Args:
        diagram: The Mermaid diagram code (without markdown fences).
        kind: Either "component" for flowchart diagrams or "class" for classDiagram.

    Returns:
        JSON with is_valid (bool), issues (list), and repaired_diagram (str or null).
        If repaired_diagram is non-null, it contains the auto-fixed version — validate it
        again to confirm all issues are resolved.  If is_valid is false and no auto-repair
        was possible, fix the listed issues manually and validate again.
    """
    cleaned = _strip_mermaid_fences(diagram)
    is_valid, issues = _validate_mermaid(cleaned, kind)

    repaired = None
    if not is_valid and kind == "class":
        repaired = _auto_repair_class_diagram(cleaned)
        re_valid, re_issues = _validate_mermaid(repaired, kind)
        if re_valid:
            return json.dumps({
                "is_valid": False,
                "issues": issues,
                "auto_repaired": True,
                "repaired_diagram": repaired,
                "repair_note": "Auto-repair fixed all issues. Use the repaired_diagram.",
            })
        else:
            return json.dumps({
                "is_valid": False,
                "issues": issues,
                "auto_repaired": False,
                "repaired_diagram": repaired,
                "remaining_issues_after_repair": re_issues,
                "repair_note": "Auto-repair fixed some issues but not all. Review remaining_issues.",
            })

    return json.dumps({"is_valid": is_valid, "issues": issues})


# ============================================================================
# 10. SYSTEM PROMPT — 4-Step CodeFlowMap Analysis Protocol
# ============================================================================


CODEFLOWMAP_SYSTEM_PROMPT = """
You are **CodeFlowMap** — a Senior Staff Engineer specializing in software architecture documentation. Your role is to deeply analyze a codebase and produce precise, comprehensive **Mermaid diagrams** modeled after the **C4 architecture model** at two levels:

1. **Component Level** (C4 Level 3 — Component Diagram)
2. **Class Level** (C4 Level 4 — Code/Class Diagram)

Think like an engineer **onboarding a new team member**: the diagrams should make the architecture immediately comprehensible.

---

## CRITICAL RULES

- **Never fabricate** classes, methods, or relationships not present in the actual code.
- Always **resolve import paths to actual modules** — do not guess.
- If files are auto-generated (migrations, lock files, compiled output), **skip them**.
- Prefer **clarity over completeness** — omit trivial utility classes unless architecturally significant.
- If a module is a thin pass-through with no logic, it may be omitted from the class diagram but should still appear in the component diagram if it handles routing or orchestration.
- After calling `scan_repository`, proceed DIRECTLY to analysis and diagram generation — do not re-scan.

---

## TOOL USAGE — MANDATORY

You have four specialised tools. **Follow this hierarchy strictly — violating it wastes tokens and degrades output quality.**

| Tool | When to use |
|------|-------------|
| `scan_repository` | First call only — validates repo path and returns file count. |
| `repo_index` | Second call — returns every `.py` / `.js` file grouped by directory. Use this to understand repo layout and decide which files to inspect. |
| `code_structure` | **Primary analysis tool.** Call it on every source file you need to understand. Returns imports, classes, methods, calls — no raw source. |
| `symbol_search` | When you need to know where a class or function is defined or called across the whole repo. |

### NEVER use `read_file` on source code files
`read_file` returns raw file content. On source files this is pure token waste — you get hundreds of lines of implementation noise when `code_structure` gives you the exact structural facts you need (imports, class names, method signatures, call graph) in a compact JSON.

**`read_file` is only acceptable for these non-code files:**
- `package.json`, `pyproject.toml`, `requirements.txt`, `setup.cfg` — to identify dependencies and framework versions
- `tsconfig.json`, `.eslintrc.*`, `vite.config.*`, `webpack.config.*` — to understand build/compile config
- `docker-compose.yml`, `Dockerfile` — to identify runtime environment and external services
- `README.md` — only if no other signals exist for the entry point or tech stack

**For every `.py` and `.js` file: always call `code_structure`, never `read_file`.**

### Efficient analysis pattern
```
scan_repository()                      → confirms repo is accessible
repo_index(repo_path)                  → full file map grouped by directory
code_structure(file) × N               → structural facts for each relevant file
symbol_search(repo, symbol) × M        → cross-file usage for key classes/functions
```

---

## ANALYSIS PROTOCOL

These are the steps you need to follow to analyze the codebase and generate the diagrams

### Step 1 — Scan the Repository
Call `scan_repository`. Then call `repo_index` to get the full file layout. From the directory groupings, identify which directories contain entry points, business logic, data access, and infrastructure.

### Step 2 — Discover Entry Points & Runtime Context
From the `repo_index` output, identify:
- All entry points: `main()` functions, CLI entrypoints, server bootstrap files, route handlers, exported public APIs, index files.
- Runtime context: web server, CLI tool, library, monorepo, microservice, SPA, desktop app, etc.
- Primary language(s), framework(s), and build tools in use.

### Step 3 — Map Modules & Boundaries
Call `code_structure` on the entry-point files identified in Step 2, then work outward through their imports. Use `repo_index` groupings to identify layer boundaries without reading every file. Identify:
1. Logical **modules**, **layers**, and **packages** (controllers, services, repositories, domain, infrastructure, utils, config, adapters).
2. **Module ownership**: which modules own which data models and responsibilities.
3. **External dependencies**: databases, third-party APIs, message queues, caches, auth providers — be specific with technology names (e.g., "PostgreSQL via Prisma ORM", not just "database").
4. **Cross-cutting concerns**: logging, auth, error handling, middleware, telemetry, i18n.
5. Find logical boundaries between modules and layers.

### Step 4 — Trace Class & Interface Structures
For each architecturally significant file, call `code_structure` to get its classes, methods, and imports. Use `symbol_search` to find where base classes or interfaces are implemented across the repo. Enumerate:
- **Classes**, **interfaces**, **abstract classes**, **enums**, and **type aliases**.
- **Inheritance** (`extends`), **implementation** (`implements`), **composition** (has-a), and **dependency injection** (depends-on) relationships.
- Method signatures for key public-facing or architecturally significant methods — avoid clutter from trivial getters/setters.
- **Design patterns** in use: Repository, Factory, Singleton, Observer, Strategy, Decorator, Adapter, etc.

### Step 5 — Trace Data & Control Flow
Use the `calls` list from `code_structure` results to follow the call graph without reading raw source. Use `symbol_search` to locate service/repository definitions when the call target isn't in a file you've already inspected. Follow the call graph from entry points through layers:
1. What triggers the flow (HTTP request, CLI command, event, cron)?
2. Which entry point catches it?
3. What middleware/interceptors run?
4. Which service/handler processes it?
5. What data stores / external APIs are hit?
6. How does the response flow back?
- Identify synchronous vs asynchronous flows (callbacks, Promises, async/await, event emitters, queues).
- Flag circular dependencies or architectural anti-patterns.
- Identify the external systems and their purpose.
- includes a Staff Engineer-level observations section after every diagram generation

---

## DIAGRAM GENERATION

### General Rules
- Use only valid **Mermaid syntax** that renders correctly.
- Use meaningful, readable node IDs (not random hashes).
- Labels must reflect **actual** class names, component names, and relationships from the code.
- Group related elements using `subgraph` blocks to reflect module/layer boundaries.
- Prioritize **breadth over depth** at the component level and **depth over breadth** at the class level (focus class detail on the core domain).

### Component Diagram (C4 Level 3)

**Goal**: Show the major runtime components, their responsibilities, and how they communicate.

**Format**: `flowchart TD` (or `LR` for wide architectures)

**Must Include**:
- All significant **components** (services, controllers, gateways, adapters, handlers, workers)
- **External systems** (databases, third-party APIs, queues, caches, file systems)
- Directional **relationships** with labeled edges describing interaction: `"HTTP REST"`, `"SQL query"`, `"publishes event"`, `"reads from"`, `"authenticates via"`
- **Subgraphs** grouping by layer: `API Layer`, `Business Logic`, `Data Layer`, `Infrastructure`, `External Systems`
- Entry point components clearly positioned at the top
- **classDef** blocks with distinct fill colors per layer
- Assign EVERY node a `:::className`
- No orphan nodes

**Full Example**:
```
flowchart TD
  classDef api fill:#fef3c7,stroke:#92400e,stroke-width:1px,color:#1f2937;
  classDef biz fill:#dbeafe,stroke:#1d4ed8,stroke-width:1px,color:#111827;
  classDef data fill:#d1fae5,stroke:#065f46,stroke-width:1px,color:#111827;
  classDef infra fill:#e0e7ff,stroke:#312e81,stroke-width:1px,color:#111827;
  classDef ext fill:#ffe4e6,stroke:#be123c,stroke-width:1px,color:#111827;

  subgraph APILayer["API Layer"]
    Controller["HTTP Controller"]:::api
    AuthMW["Auth Middleware"]:::api
  end
  subgraph BizLayer["Business Logic"]
    OrderSvc["OrderService"]:::biz
    PaymentSvc["PaymentService"]:::biz
  end
  subgraph DataLayer["Data Layer"]
    OrderRepo["OrderRepository"]:::data
    UserRepo["UserRepository"]:::data
  end
  subgraph External["External Systems"]
    DB[("PostgreSQL")]:::ext
    Stripe["Stripe API"]:::ext
  end

  Controller -->|"validates token"| AuthMW
  AuthMW -->|"delegates request"| OrderSvc
  OrderSvc -->|"processes payment"| PaymentSvc
  OrderSvc -->|"persists order"| OrderRepo
  PaymentSvc -->|"charges card via HTTPS"| Stripe
  OrderRepo -->|"SQL queries"| DB
  UserRepo -->|"SQL queries"| DB
```

### Class Diagram (C4 Level 4)

**Goal**: Show the internal code structure — classes, interfaces, fields, key methods, and relationships.

**Format**: `classDiagram` with `direction TB`

**Must Include**:
- All architecturally significant **classes** and **interfaces**
- **Fields** with visibility and types for important domain properties
- **Key methods** with parameter types and return types
- Relationship types:
  - `<|--` Inheritance (extends)
  - `<|..` Realization (implements)
  - `*--` Composition (owns lifecycle)
  - `o--` Aggregation (references)
  - `-->` Dependency (uses, calls)
- **Multiplicity** where meaningful: `"1"`, `"0..*"`, `"1..*"`
- **Design patterns** annotated: `<<Repository>>`, `<<Service>>`, `<<Factory>>`, `<<Singleton>>`, `<<Interface>>`, `<<Abstract>>`, `<<Entity>>`, `<<ValueObject>>`, `<<Adapter>>`
- Group with `%%` section comments: `%% Domain Entities`, `%% Services`, etc.
- Max 35 classes. Each class MUST show at least 2 fields or methods.

**CRITICAL SYNTAX RULES (violating these will fail validation)**:
- Annotations like `<<Service>>` MUST go INSIDE the class body on their OWN LINE, NEVER inline:
  WRONG:   `class Foo <<Service>> {`
  CORRECT: `class Foo {` then `<<Service>>` on the next line inside the body.
- NO angle-bracket generics `<T>`. Use Mermaid tilde syntax: `List~string~`, `Observable~any~`, `EventEmitter~void~`, `Map~string,int~`.
- NO union types with `|`. Replace `Type | null` with just `Type` or `TypeOrNull`.
- NO `[]` in types. Replace `Item[]` with `Item~Array~` or just `Items`.
- Method return types go AFTER the closing paren with NO colon: `+getName() string` not `+getName(): string`.

**Full Example**:
```
classDiagram
  direction TB
  %% Services
  class OrderService {
    <<Service>>
    -orderRepo: OrderRepository
    -paymentService: PaymentService
    +createOrder(userId: string, items: Items) Order
    +cancelOrder(orderId: string) void
  }

  class OrderRepository {
    <<Repository>>
    -db: DatabaseConnection
    +findById(id: string) Order
    +save(order: Order) Order
    +delete(id: string) void
  }

  %% Interfaces
  class IPaymentService {
    <<Interface>>
    +charge(amount: number, token: string) PaymentResult
    +refund(transactionId: string) void
  }

  class StripePaymentService {
    <<Adapter>>
    -stripeClient: StripeClient
    +charge(amount: number, token: string) PaymentResult
    +refund(transactionId: string) void
  }

  %% Domain
  class Order {
    <<Entity>>
    +id: string
    +userId: string
    +items: Items
    +status: OrderStatus
    +totalAmount: number
    +createdAt: Date
  }

  OrderService --> OrderRepository : uses
  OrderService --> IPaymentService : depends on
  IPaymentService <|.. StripePaymentService : implements
  OrderService "1" *-- "0..*" Order : creates
  OrderRepository --> Order : persists
```

---

## VALIDATE & WRITE OUTPUT

1. Call `validate_mermaid_diagram` for BOTH diagrams (kind="component" and kind="class").
   - If the tool returns `auto_repaired: true`, USE the `repaired_diagram` it provides.
   - If `auto_repaired: false` with `remaining_issues_after_repair`, fix those manually and re-validate.
   - NEVER skip validation. NEVER include a diagram that has not passed validation.
   - Keep re-validating until `is_valid: true` for BOTH diagrams.
2. Use `write_file` to save the final `codeflowmap.md` with this EXACT structure:

# CodeFlowMap — {repo_name}

## Codebase Summary

{2-4 sentence summary of what the system does, its architecture style (MVC, hexagonal, layered, etc.), and the primary technology stack. Bold all proper nouns and technology names.}

---

## Component Diagram (C4 Level 3)

```mermaid
{validated component diagram}
```

---

## Class Diagram (C4 Level 4)

```mermaid
{validated class diagram}
```

---

## Architectural Notes

{5-10 observations a Senior Staff Engineer would flag:
- Key design decisions observed in the codebase
- Identified design patterns (Repository, Factory, Observer, etc.)
- Any coupling concerns or architectural risks
- External dependency surface area
- Suggestions for diagram readers on what to focus on

Each note must reference actual class/file/function names from the codebase.}

### Data / Control Flow
{numbered end-to-end flow description tracing a request from entry point to response}

### Module Map
| Module | Layer | Responsibility | Key Files |
|--------|-------|----------------|-----------|
{table rows}

### External Systems
| System | Technology | Purpose | Accessed By |
|--------|-----------|---------|-------------|
{table rows}
"""


# ============================================================================
# 11. AGENT CREATION
# ============================================================================

def create_codeflowmap_agent(
    model: str = None,
    repo_path: str = "",
    output_dir: str = "./codeflowmap_output",
):
    """Create a CodeFlowMap Deep Agent."""
    from deepagents import create_deep_agent
    from deepagents.backends import FilesystemBackend

    model = model or os.getenv("CODEFLOWMAP_MODEL", "openai:gpt-4o")

    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # Root the backend at the repo so ls/read_file/glob/grep operate on the
    # actual codebase. virtual_mode=False means relative paths resolve under
    # root_dir but absolute paths (used for the output file) are honoured as-is,
    # so the agent can still write codeflowmap.md to the absolute output_dir.
    fs_root = repo_path if repo_path else output_dir

    checkpointer = MemorySaver()

    agent = create_deep_agent(
        model=model,
        tools=[scan_repository, CodeStructureTool(), RepoIndexTool(), SymbolSearchTool(), validate_mermaid_diagram],
        system_prompt=CODEFLOWMAP_SYSTEM_PROMPT,
        memory=["memory/CODEFLOWMAP.md"],
        backend=FilesystemBackend(root_dir=fs_root, virtual_mode=False),
        checkpointer=checkpointer,
        interrupt_on={"write_todos": True}
    )

    agent.get_graph().draw_mermaid_png(output_file_path="codeflowmap.png")
    return agent


def _extract_text(content) -> str:
    """Safely extract text from message content (may be str, list of blocks, or None)."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "".join(parts)
    return str(content)


def _stream_agent(agent, message: str, verbose: bool = False, thread_id: str = "default"):
    """Run agent with streaming, showing tool calls, results, and subagent progress.

    Uses stream_mode=["updates","messages"] + subgraphs=True + version="v2" so that:
    - "updates" events surface subagent lifecycle (pending → running → complete)
    - "messages" events stream tokens, tool_call_chunks (with args), and tool results
    - subgraphs=True makes events from nested subagent graphs flow through
    - version="v2" gives a clean {type, ns, data} dict per chunk (no tuple unpacking)
    """
    for noisy in ("httpx", "httpcore", "openai", "anthropic", "litellm"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    from rich.text import Text
    from rich.syntax import Syntax

    _ICONS = {
        "scan_repository": "🔍", "validate_mermaid_diagram": "🧪",
        "write_todos": "📋", "write_file": "📝", "read_file": "📖",
        "edit_file": "✏️ ", "ls": "📂", "glob": "🔎", "grep": "🔎",
        "task": "🤖",
    }

    def _source_label(ns) -> str:
        """'main' or the innermost tools:xxx segment from the namespace."""
        for seg in reversed(ns or ()):
            if seg.startswith("tools:"):
                return seg
        return "main"

    def _print_tool_call_panel(name: str, args_str: str, call_id: str = "", source: str = "main"):
        icon = _ICONS.get(name, "⚙️")
        label = f"[subagent] " if source != "main" else ""
        try:
            display = json.dumps(json.loads(args_str), indent=2, ensure_ascii=False) if args_str else "{}"
        except (json.JSONDecodeError, ValueError):
            display = args_str or "{}"
        if call_id:
            display += f"\n  # call_id: {call_id}"
        if console:
            console.print(Panel(
                Syntax(display, "json", word_wrap=True, background_color="default")
                if display.lstrip().startswith("{") else Text(display),
                title=f"{icon} {label}Tool Call: [bold]{name}[/bold]",
                title_align="left",
                border_style="cyan" if source != "main" else "bright_cyan",
                padding=(0, 1),
            ))
        else:
            print(f"\n── {label}Tool Call: {name} ──\n{display}")

    def _print_tool_result_panel(name: str, content: str, source: str = "main"):
        label = "[subagent] " if source != "main" else ""
        display = content
        try:
            display = json.dumps(json.loads(content), indent=2, ensure_ascii=False)
        except (json.JSONDecodeError, TypeError):
            pass
        if len(display) > 3000:
            display = display[:3000] + f"\n... ({len(content)} chars total)"
        if console:
            console.print(Panel(
                Syntax(display, "json", word_wrap=True, background_color="default")
                if display.lstrip().startswith(("{", "[")) else Text(display),
                title=f"✅ {label}Tool Output: [bold]{name}[/bold]",
                title_align="left",
                border_style="green",
                padding=(0, 1),
            ))
        else:
            print(f"\n── {label}Tool Output: {name} ──\n{display}")

    def _print_thinking_panel(text: str, source: str = "main"):
        label = "[subagent] " if source != "main" else ""
        if console:
            console.print(Panel(
                Text(text.strip()),
                title=f"💭 {label}AI Reasoning",
                title_align="left",
                border_style="yellow" if source != "main" else "bright_yellow",
                padding=(0, 1),
            ))
        else:
            print(f"\n── {label}AI Reasoning ──\n{text}")

    def _print_subagent_panel(status: str, description: str):
        icons = {"pending": "⏳", "running": "⚙️ ", "complete": "✅", "error": "❌"}
        borders = {"pending": "dim", "running": "magenta", "complete": "green", "error": "red"}
        if console:
            console.print(Panel(
                Text(description[:300] if description else "(no description)"),
                title=f"{icons.get(status, '🤖')} Subagent [{status.upper()}]",
                title_align="left",
                border_style=borders.get(status, "magenta"),
                padding=(0, 1),
            ))
        else:
            print(f"\n── Subagent [{status.upper()}] ── {description[:100]}")

    if console:
        console.print("\n[bold cyan]● Deep Agent starting analysis...[/bold cyan]\n")
    else:
        print("\n● Deep Agent starting analysis...\n")

    # Per-source state
    thinking_bufs: Dict[str, List[str]] = {}       # source → accumulated text chunks
    pending_calls: Dict[str, Dict] = {}             # call_id → {name, args_str, source}
    active_subagents: Dict[str, Dict] = {}          # tool_call_id → {description, status}

    from langgraph.types import Command

    config = {"configurable": {"thread_id": thread_id}}
    # resume_cmd is None on first call; set to Command(resume=...) after an interrupt
    resume_cmd: dict | None = None

    while True:
        stream_input = resume_cmd if resume_cmd is not None else {"messages": [{"role": "user", "content": message}]}
        interrupted = False
        interrupt_value = None

        for chunk in agent.stream(
            stream_input,
            config=config,
            stream_mode=["updates", "messages"],
            subgraphs=True,
            version="v2",
        ):
            chunk_type = chunk.get("type")
            ns = chunk.get("ns", ())
            data = chunk.get("data")
            source = _source_label(ns)
            is_subagent = source != "main"

            # ── INTERRUPT: HITL pause waiting for human decision ──────────
            if chunk_type == "updates":
                for node_name, node_data in (data or {}).items():
                    if node_name == "__interrupt__":
                        interrupted = True
                        interrupt_value = node_data
                        break

            if interrupted:
                break

            # ── UPDATES: subagent lifecycle ───────────────────────────────
            if chunk_type == "updates":
                for node_name, node_data in (data or {}).items():
                    # Main agent model_request spawned a task tool call → subagent pending
                    if not is_subagent and node_name == "model_request":
                        for msg in node_data.get("messages", []):
                            for tc in getattr(msg, "tool_calls", []):
                                if tc.get("name") == "task":
                                    cid = tc["id"]
                                    desc = tc.get("args", {}).get("description", "")
                                    active_subagents[cid] = {"description": desc, "status": "pending"}
                                    _print_subagent_panel("pending", desc)

                    # First update from inside a subagent namespace → mark running
                    if is_subagent:
                        for cid, sub in active_subagents.items():
                            if sub["status"] == "pending":
                                sub["status"] = "running"
                                _print_subagent_panel("running", sub["description"])
                                break

                    # Main agent tools node returned a tool message → subagent complete
                    if not is_subagent and node_name == "tools":
                        for msg in node_data.get("messages", []):
                            if getattr(msg, "type", None) == "tool":
                                cid = getattr(msg, "tool_call_id", None)
                                if cid and cid in active_subagents:
                                    active_subagents[cid]["status"] = "complete"
                                    _print_subagent_panel("complete", active_subagents[cid]["description"])

            # ── MESSAGES: tokens, tool call chunks, tool results ──────────
            elif chunk_type == "messages":
                token, _metadata = data

                # Args arrive as streaming string fragments in tool_call_chunks —
                # accumulate by call_id; never print until fully assembled.
                if getattr(token, "tool_call_chunks", None):
                    for tc in token.tool_call_chunks:
                        cid = tc.get("id") or ""
                        name = tc.get("name") or ""
                        frag = tc.get("args") or ""
                        if cid not in pending_calls:
                            pending_calls[cid] = {"name": "", "args_str": "", "source": source}
                        if name:
                            pending_calls[cid]["name"] = name
                        pending_calls[cid]["args_str"] += frag

                # Complete tool_calls message: flush thinking + print with full assembled args
                elif getattr(token, "tool_calls", None):
                    src = thinking_bufs.pop(source, None)
                    if src:
                        _print_thinking_panel("".join(src), source)
                    for tc in token.tool_calls:
                        name = tc.get("name", "")
                        cid = tc.get("id", "")
                        if name:
                            # Prefer the accumulated string (has full args); fall back to dict
                            args_str = pending_calls.get(cid, {}).get("args_str") or \
                                       json.dumps(tc.get("args", {}), ensure_ascii=False)
                            _print_tool_call_panel(name, args_str, cid, source)
                    pending_calls.clear()

                # Tool result: flush any pending calls first (some providers skip the
                # tool_calls message and jump straight to the result)
                elif getattr(token, "type", None) == "tool":
                    if pending_calls:
                        src = thinking_bufs.pop(source, None)
                        if src:
                            _print_thinking_panel("".join(src), source)
                        for cid, p in pending_calls.items():
                            if p["name"]:
                                _print_tool_call_panel(p["name"], p["args_str"], cid, p["source"])
                        pending_calls.clear()
                    content = _extract_text(getattr(token, "content", ""))
                    _print_tool_result_panel(getattr(token, "name", "tool"), content, source)

                # Plain AI text: accumulate into per-source thinking buffer
                elif getattr(token, "type", None) in ("ai", "AIMessageChunk"):
                    content = _extract_text(getattr(token, "content", ""))
                    if content:
                        thinking_bufs.setdefault(source, []).append(content)

        if interrupted:
            # Gather all HITLRequest action_requests from the interrupt value.
            iv = interrupt_value if isinstance(interrupt_value, (list, tuple)) else [interrupt_value]
            decisions: list[dict] = []

            for intr in iv:
                hitl = getattr(intr, "value", intr) if not isinstance(intr, dict) else intr
                action_requests = (hitl or {}).get("action_requests", [])

                for action_req in action_requests:
                    tool_name = action_req.get("name", "") if isinstance(action_req, dict) \
                                else getattr(action_req, "name", "")
                    tool_args = action_req.get("args", {}) if isinstance(action_req, dict) \
                                else getattr(action_req, "args", {})

                    if tool_name == "write_todos":
                        # Show the planned todos and ask the user to approve or reject.
                        todos = tool_args.get("todos", tool_args)
                        todos_display = json.dumps(todos, indent=2, ensure_ascii=False) \
                                        if not isinstance(todos, str) else todos
                        if console:
                            from rich.prompt import Confirm
                            console.print(Panel(
                                Syntax(todos_display, "json", word_wrap=True, background_color="default"),
                                title="📋 Agent Todo Plan — Review Required",
                                title_align="left",
                                border_style="yellow",
                                padding=(0, 1),
                            ))
                            approved = Confirm.ask("\n[bold yellow]Approve this plan and continue?[/bold yellow]",
                                                   default=True)
                        else:
                            print(f"\n── 📋 Agent Todo Plan ──\n{todos_display}")
                            raw = input("\nApprove this plan and continue? [Y/n]: ").strip().lower()
                            approved = raw in ("", "y", "yes")

                        decisions.append({"type": "approve"} if approved
                                         else {"type": "reject", "message": "User rejected the plan."})
                    else:
                        # Auto-approve any other interrupted tool (defensive — shouldn't happen
                        # given interrupt_on only lists write_todos).
                        decisions.append({"type": "approve"})

                # If action_requests was empty, still need one approve to unblock
                if not action_requests:
                    decisions.append({"type": "approve"})

            resume_cmd = Command(resume={"decisions": decisions})
            continue

        # Stream ended normally — done
        break

    # Flush any remaining thinking from all sources
    for src, buf in thinking_bufs.items():
        if buf:
            _print_thinking_panel("".join(buf), src)

    if console:
        console.print("\n[bold green]● Analysis complete.[/bold green]\n")
    else:
        print("\n● Analysis complete.\n")


# ============================================================================
# 12. MAIN FUNCTION
# ============================================================================

def main():
    """Main entry point."""
    if sys.platform == "win32":
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

    args = parse_arguments()

    # Apply --model CLI override
    if args.model:
        os.environ["CODEFLOWMAP_MODEL"] = args.model

    repo_path = Path(args.repo).resolve()
    if not repo_path.exists():
        print(f"Error: Repository path does not exist: {repo_path}", file=sys.stderr)
        sys.exit(1)

    output_dir = args.output
    output_md = Path(output_dir) / "codeflowmap.md"

    # Print header
    if console:
        console.print(Panel(
            "[bold cyan]CodeFlowMap[/bold cyan] — Deep Agent Architecture Analyzer\n\n"
            f"Repository: {repo_path}\n"
            f"Output:     {output_md}\n"
            f"Model:      {os.getenv('CODEFLOWMAP_MODEL', 'openai:gpt-4o')}"
            + (f"\nContext:    [italic]{args.context}[/italic]" if args.context else ""),
            title="[bold]>> Starting Analysis[/bold]"
        ))
    else:
        print("=" * 60)
        print("CodeFlowMap — Deep Agent Architecture Analyzer")
        print("=" * 60)
        print(f"Repository: {repo_path}")
        print(f"Output: {output_md}\n")

    # Build user message
    message = f"Analyze the codebase at `{repo_path}`"
    if args.module:
        message += f", scoped to the `{args.module}` module"
    if args.context:
        message += f".\n\nAdditional context from the developer: {args.context}"
    if args.include_tests:
        message += "\n\nInclude test/spec files in the analysis."
    message += f"\n\nSave the final output to the absolute path `{Path(output_dir).resolve() / 'codeflowmap.md'}`."

    # Create and run agent with streaming
    try:
        agent = create_codeflowmap_agent(repo_path=str(repo_path), output_dir=output_dir)

        _stream_agent(agent, message, verbose=args.verbose, thread_id=str(repo_path))

        # Print completion
        if console:
            console.print(Panel(
                f"[green]Analysis complete![/green]\n\n"
                f"[bold]Output:[/bold] {output_md}",
                title="[green bold]SUCCESS[/green bold]",
            ))
        else:
            print("\n" + "=" * 60)
            print("Analysis Complete")
            print("=" * 60)
            print(f"Output: {output_md}")

    except KeyboardInterrupt:
        print("\nAborted by user.", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"Error during analysis: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)

# ============================================================================
# 13. ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    main()

