# CodeFlowMap - DeepAgent based CLI tool

A CLI deep-agent that reads any codebase and produces **C4-level Mermaid architecture diagrams** — automatically. Point it at a repo, approve the plan, and get a component diagram + class diagram written to Markdown.

---

## How it works

CodeFlowMap runs a [deepagents](https://docs.langchain.com/oss/python/deepagents/) agent loop with four specialised tools:

| Tool | What it does |
|------|-------------|
| `scan_repository` | Validates the repo path and counts files |
| `repo_index` | Lists every `.py` / `.js` file grouped by directory |
| `code_structure` | Extracts imports, classes, methods, and calls via **tree-sitter** — no raw source reading |
| `symbol_search` | Finds where a class or function is defined or called across the whole repo |

The agent follows a five-step analysis protocol — entry points → module map → class structures → data/control flow → diagram generation — then validates both diagrams with a Mermaid linter before writing the final Markdown file.

**Token efficiency:** `code_structure` returns compact structural JSON (~10–30 lines per file) instead of raw source code, keeping analysis costs low even on large repos.

---

## Output

A single `codeflowmap.md` file containing:

- **Codebase summary** — architecture style, primary tech stack
- **Component Diagram** (C4 Level 3) — major runtime components, external systems, and labelled communication edges rendered as a `flowchart`
- **Class Diagram** (C4 Level 4) — classes, interfaces, inheritance, composition, and design patterns rendered as a `classDiagram`
- **Architectural notes** — Staff-Engineer-level observations, data/control flow walkthrough, module map table, and external systems table

---

## Supported languages

Python · TypeScript · JavaScript · Java · Go · C# · Ruby · Rust

---

## Quick start

```bash
# 1. Clone and create a virtual environment
git clone <repo-url>
cd CodeFlowMapAgent
python -m venv venv && source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure your LLM provider
cp .env.example .env
# Edit .env and set your API key + model (see Configuration below)

# 4. Run
python Codeflowmap.py --repo /path/to/your/repo
```

The agent will:
1. Scan the repository
2. Write a todo plan and **pause for your approval** before proceeding
3. Analyse the codebase using tree-sitter structural parsing
4. Generate and self-validate both Mermaid diagrams
5. Write `codeflowmap_output/codeflowmap.md`

---

## CLI reference

```
python Codeflowmap.py [OPTIONS]

Required:
  --repo PATH           Absolute or relative path to the repository root

Optional:
  --output DIR          Output directory (default: ./codeflowmap_output)
  --module SUBPATH      Scope analysis to a subfolder (relative to repo root)
  --model MODEL         LLM model identifier — overrides CODEFLOWMAP_MODEL env var
  --context TEXT        Free-text background context passed to every prompt
                        e.g. "Multi-tenant SaaS, payments via Stripe, Postgres + Redis"
  --include-tests       Include test/spec files in analysis
  --verbose             Stream agent reasoning and tool calls to the terminal
  --format {md,mmd}     Output format: md (Markdown, default) or mmd (raw Mermaid)
```

### Examples

```bash
# Basic — analyse a Python repo with default model
python Codeflowmap.py --repo ~/projects/my-api

# Scope to a single microservice
python Codeflowmap.py --repo ~/projects/monorepo --module services/auth

# Use a specific model and add developer context
python Codeflowmap.py \
  --repo ~/projects/my-api \
  --model anthropic:claude-sonnet-4-6 \
  --context "FastAPI service, PostgreSQL via SQLAlchemy, Celery workers" \
  --verbose

# Write diagrams to a custom output directory
python Codeflowmap.py --repo ~/projects/my-api --output ~/docs/architecture
```

---

## Configuration

Copy `.env.example` to `.env` and fill in your values.

### LLM model

```env
CODEFLOWMAP_MODEL=openai:gpt-4o
```

Any provider supported by LangChain's `init_chat_model` works:

| Provider | Example value |
|----------|--------------|
| OpenAI | `openai:gpt-4o` · `openai:gpt-4o-mini` |
| Anthropic | `anthropic:claude-sonnet-4-6` · `anthropic:claude-3-haiku-20240307` |
| Google | `google_genai:gemini-2.5-flash-lite` · `google_genai:gemini-2.0-flash` |
| Ollama (local) | `ollama:llama3` — no API key needed, just run `ollama serve` |
| Azure OpenAI | `azure_openai:gpt-4o` |
| AWS Bedrock | `bedrock_converse:anthropic.claude-3-5-sonnet` |

### API keys

```env
OPENAI_API_KEY=sk-...
# or
ANTHROPIC_API_KEY=sk-ant-...
# or
GOOGLE_API_KEY=...
```

### Tuning (optional)

```env
CODEFLOWMAP_MAX_FILES=200          # max source files to index
CODEFLOWMAP_MAX_FILE_SIZE=80       # max file size in KB
CODEFLOWMAP_MAX_CONTENT_CHARS=6000 # max chars per file fed to the LLM
CODEFLOWMAP_MAX_TRACE_DEPTH=12     # BFS depth for call-graph tracing
CODEFLOWMAP_MAX_REACHABLE=300      # max reachable nodes in the call graph
```

---

## Project structure

```
CodeFlowMapAgent/
├── Codeflowmap.py        # Main CLI — agent setup, streaming loop, system prompt
├── treesitter_tool.py    # LangChain tools wrapping tree-sitter AST parsing
├── requirements.txt
├── .env.example
└── codeflowmap_output/   # Generated diagrams land here
```

---

## Requirements

- Python 3.11+
- An API key for your chosen LLM provider (or a local Ollama instance)
- The target repository accessible on the local filesystem
