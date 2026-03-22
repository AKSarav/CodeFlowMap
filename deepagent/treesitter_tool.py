import tree_sitter_python as tspython
import tree_sitter_javascript as tsjavascript
from tree_sitter import Language, Parser
from langchain.tools import BaseTool
from pathlib import Path
from typing import Optional
import json

# ── Language registry ──────────────────────────────────────────
LANGUAGES = {
    ".py":  Language(tspython.language()),
    ".js":  Language(tsjavascript.language()),
    # add .ts, .go, .java etc.
}

def get_general_code_exclusions() -> dict:
    """Return patterns to exclude during repo walk — covers Python and JS/TS projects."""
    return {
        # File extensions (Path.suffix) to skip
        "extensions": {
            ".pyc", ".pyo", ".pyd",                             # Python bytecode
            ".md", ".mdx",                                       # Docs
            ".txt",                                              # Plain text / requirements
            ".log",                                              # Logs
            ".lock",                                             # Lock files
            ".map",                                              # JS source maps
            ".css", ".scss", ".sass", ".less",                   # Styles
            ".html", ".htm",                                     # Templates
            ".json", ".yaml", ".yml", ".toml", ".cfg", ".ini",  # Config / manifests
            ".svg", ".png", ".jpg", ".jpeg", ".gif", ".ico",    # Images
            ".woff", ".woff2", ".ttf", ".eot",                  # Fonts
        },
        # Directory names to skip (matched against any segment of the path)
        "directories": {
            ".git", "__pycache__", "node_modules",
            "venv", ".venv", "env",
            "dist", "build", ".next", "out", ".cache",
            ".pytest_cache", ".mypy_cache", ".ruff_cache",
            "coverage", "htmlcov",
            "migrations",       # Django / Alembic DB migrations
            "static", "assets", # Served static files
        },
        # Exact filenames to skip
        "filenames": {
            "conftest.py", "setup.py", "setup.cfg",
            "pyproject.toml", "package.json", "package-lock.json",
            "yarn.lock", "poetry.lock", "requirements.txt",
            "jest.config.js", "webpack.config.js",
            "vite.config.js", "tsconfig.json",
            ".gitignore", ".dockerignore", "Dockerfile", "Makefile",
        },
        # Skip if the filename contains any of these substrings
        "name_contains": {".test.", ".spec.", ".min."},
        # Skip if the filename starts with any of these prefixes
        "name_prefixes": {"test_", ".env"},
    }

def get_parser(ext: str) -> Optional[Parser]:
    lang = LANGUAGES.get(ext)
    if not lang:
        return None
    p = Parser(lang)
    return p

# ── Core extraction logic ───────────────────────────────────────
def extract_structure(file_path: str) -> dict:
    """Extract functions, classes, imports — NOT raw content."""
    path = Path(file_path)
    parser = get_parser(path.suffix)
    if not parser:
        return {"error": f"Unsupported file type: {path.suffix}"}

    code = path.read_bytes()
    tree = parser.parse(code)
    source = code.decode("utf-8")

    result = {
        "file": str(path),
        "imports": [],
        "classes": [],
        "functions": [],
        "calls": [],      # top-level calls (for flow mapping)
    }

    def node_text(node):
        return source[node.start_byte:node.end_byte]

    def walk(node):
        # Python-specific node types (swap for JS/TS as needed)
        if node.type == "import_statement":
            result["imports"].append(node_text(node).strip())

        elif node.type == "import_from_statement":
            result["imports"].append(node_text(node).strip())

        elif node.type == "class_definition":
            name_node = node.child_by_field_name("name")
            result["classes"].append({
                "name": node_text(name_node),
                "line": node.start_point[0] + 1,
                "methods": [
                    node_text(c.child_by_field_name("name"))
                    for c in node.children
                    if c.type == "function_definition"
                ]
            })

        elif node.type == "function_definition":
            name_node = node.child_by_field_name("name")
            params_node = node.child_by_field_name("parameters")
            result["functions"].append({
                "name": node_text(name_node),
                "line": node.start_point[0] + 1,
                "params": node_text(params_node),
            })

        elif node.type == "call":
            func_node = node.child_by_field_name("function")
            if func_node:
                result["calls"].append({
                    "callee": node_text(func_node),
                    "line": node.start_point[0] + 1,
                })

        for child in node.children:
            walk(child)

    walk(tree.root_node)
    return result


def list_repo_files(repo_path: str, extensions=(".py", ".js")) -> list[str]:
    exc = get_general_code_exclusions()
    excl_dirs      = exc["directories"]
    excl_exts      = exc["extensions"]
    excl_names     = exc["filenames"]
    excl_contains  = exc["name_contains"]
    excl_prefixes  = exc["name_prefixes"]

    def is_excluded(p: Path) -> bool:
        if any(part in excl_dirs for part in p.parts):
            return True
        if p.suffix in excl_exts:
            return True
        if p.name in excl_names:
            return True
        if any(p.name.startswith(pfx) for pfx in excl_prefixes):
            return True
        if any(sub in p.name for sub in excl_contains):
            return True
        return False

    return [
        str(p) for p in Path(repo_path).rglob("*")
        if p.suffix in extensions and not is_excluded(p)
    ]


# ── LangChain Tools ─────────────────────────────────────────────
class CodeStructureTool(BaseTool):
    name: str = "code_structure"
    description: str = (
        "Extract functions, classes, imports, and calls from a single source file. "
        "Input: absolute or relative file path. "
        "Returns structured JSON — do NOT use this to read raw file content."
    )

    def _run(self, file_path: str) -> str:
        result = extract_structure(file_path.strip())
        return json.dumps(result, indent=2)


class RepoIndexTool(BaseTool):
    name: str = "repo_index"
    description: str = (
        "List all source files in a repository. "
        "Input: path to repo root. "
        "Returns file paths grouped by directory — use this first to understand repo layout."
    )

    def _run(self, repo_path: str) -> str:
        files = list_repo_files(repo_path.strip())
        # Group by directory for readability
        grouped: dict[str, list] = {}
        for f in files:
            folder = str(Path(f).parent)
            grouped.setdefault(folder, []).append(Path(f).name)
        return json.dumps(grouped, indent=2)


class SymbolSearchTool(BaseTool):
    name: str = "symbol_search"
    description: str = (
        "Search for a function or class name across the entire repo. "
        "Input: JSON with keys 'repo_path' and 'symbol'. "
        "Returns all files and line numbers where the symbol is defined or called."
    )

    def _run(self, input_str: str) -> str:
        data = json.loads(input_str)
        symbol = data["symbol"]
        repo_path = data["repo_path"]

        hits = []
        for file in list_repo_files(repo_path):
            structure = extract_structure(file)
            for fn in structure.get("functions", []):
                if symbol in fn["name"]:
                    hits.append({"file": file, "type": "definition", "line": fn["line"]})
            for call in structure.get("calls", []):
                if symbol in call["callee"]:
                    hits.append({"file": file, "type": "call", "line": call["line"]})

        return json.dumps(hits, indent=2)