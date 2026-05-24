"""
AST-aware code chunker using tree-sitter.

Strategy:
  - Parse the file with a language-specific tree-sitter grammar
  - Walk the AST to extract functions, classes, and methods as individual chunks
  - Preserve decorators, docstrings, and comments adjacent to each node
  - Fall back to RecursiveCharacterTextSplitter for unsupported languages or parse errors

Compatible with tree-sitter 0.21 through 0.25+ (uses tree-walk, not query.matches/captures
which was removed in 0.23+).

Each chunk carries rich metadata so the contextual enricher and vector DB can
use it without re-parsing.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import List, Optional

from app.services.observability import log_chunking, log_error, Timer

# ── Chunk dataclass ───────────────────────────────────────────────────────────

@dataclass
class CodeChunk:
    """A single semantically meaningful unit of code."""
    raw_content: str          # The original source text for this chunk
    filename: str
    language: str
    chunk_type: str           # "function" | "class" | "method" | "module"
    chunk_index: int
    start_line: int
    end_line: int
    function_name: Optional[str] = None
    class_name: Optional[str] = None
    imports: List[str] = field(default_factory=list)
    decorators: List[str] = field(default_factory=list)
    docstring: Optional[str] = None
    project_id: str = ""

    def to_metadata(self) -> dict:
        """Flat dict suitable for ChromaDB / MongoDB metadata fields."""
        return {
            "filename": self.filename,
            "language": self.language,
            "chunk_type": self.chunk_type,
            "chunk_index": self.chunk_index,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "function_name": self.function_name or "",
            "class_name": self.class_name or "",
            "imports": ", ".join(self.imports),
            "decorators": ", ".join(self.decorators),
            "docstring": (self.docstring or "")[:300],  # cap length
            "project_id": self.project_id,
        }


# ── Language → extension map ──────────────────────────────────────────────────

EXT_TO_LANG = {
    ".py":   "python",
    ".js":   "javascript",
    ".jsx":  "javascript",
    ".ts":   "typescript",
    ".tsx":  "typescript",
    ".java": "java",
    ".go":   "go",
    ".rs":   "rust",
}

# ── tree-sitter grammar loader ────────────────────────────────────────────────

def _load_ts_parsers() -> dict:
    """
    Attempt to load tree-sitter Language objects for each supported language.
    Returns a dict {lang_name: Language}.  Missing languages are silently omitted
    so a missing grammar never crashes the whole application.
    """
    parsers = {}
    try:
        from tree_sitter import Language

        loaders = {
            "python":     ("tree_sitter_python",     "language"),
            "javascript": ("tree_sitter_javascript",  "language"),
            "typescript": ("tree_sitter_typescript",  "language_typescript"),
            "java":       ("tree_sitter_java",        "language"),
            "go":         ("tree_sitter_go",          "language"),
            "rust":       ("tree_sitter_rust",        "language"),
        }

        for lang, (module_name, fn_name) in loaders.items():
            try:
                import importlib
                mod = importlib.import_module(module_name)
                lang_fn = getattr(mod, fn_name)
                parsers[lang] = Language(lang_fn())
            except Exception as e:
                log_error("ast_chunker.grammar_load", error=str(e), language=lang)

    except ImportError:
        log_error("ast_chunker.tree_sitter_import", error="tree-sitter not installed")

    return parsers


_TS_LANGUAGES: dict = {}  # populated lazily on first use


def _get_ts_languages() -> dict:
    global _TS_LANGUAGES
    if not _TS_LANGUAGES:
        _TS_LANGUAGES = _load_ts_parsers()
    return _TS_LANGUAGES


# ── Target node types per language ────────────────────────────────────────────
# We walk the tree and collect nodes whose .type is in this set.
# This avoids the tree-sitter query API which changed in v0.23+
# (query.matches / query.captures removed; now only Node.matches exists in newer
#  bindings but isn't available either in the 0.25.x pip package).

_TARGET_TYPES: dict = {
    "python":     {"function_definition", "class_definition"},
    "javascript": {"function_declaration", "class_declaration", "method_definition",
                   "arrow_function", "function_expression"},
    "typescript": {"function_declaration", "class_declaration", "method_definition",
                   "arrow_function", "function_signature"},
    "java":       {"method_declaration", "class_declaration", "interface_declaration"},
    "go":         {"function_declaration", "method_declaration", "type_declaration"},
    "rust":       {"function_item", "impl_item", "struct_item", "enum_item"},
}

# Node types that are "class-like" (we recurse into them to find methods)
_CLASS_TYPES: set = {
    "class_definition", "class_declaration", "interface_declaration",
    "impl_item", "struct_item", "enum_item", "type_declaration",
}


def _walk_nodes(node, target_types: set, seen_ranges: set, results: list):
    """
    Recursively walk the tree, collecting nodes whose type is in target_types.
    Deduplicates by (start_byte, end_byte).
    Recurses into class-like nodes to pick up methods, but stops at function
    boundaries to avoid nested function explosion.
    """
    if node.type in target_types:
        key = (node.start_byte, node.end_byte)
        if key not in seen_ranges:
            seen_ranges.add(key)
            results.append(node)
        # Recurse into class bodies to capture methods
        if node.type in _CLASS_TYPES:
            for child in node.children:
                _walk_nodes(child, target_types, seen_ranges, results)
        return  # don't recurse deeper into function bodies

    for child in node.children:
        _walk_nodes(child, target_types, seen_ranges, results)


# ── Import extraction helpers ─────────────────────────────────────────────────

def _extract_imports_python(source: str) -> List[str]:
    """Extract import lines from Python source using regex (fast, no AST needed)."""
    pattern = r"^(?:import|from)\s+\S.*"
    return re.findall(pattern, source, re.MULTILINE)[:10]  # cap at 10


def _extract_imports_js(source: str) -> List[str]:
    pattern = r"^(?:import|require)\s+.*"
    return re.findall(pattern, source, re.MULTILINE)[:10]


def _extract_imports_java(source: str) -> List[str]:
    pattern = r"^import\s+\S+;"
    return re.findall(pattern, source, re.MULTILINE)[:10]


def _extract_imports_go(source: str) -> List[str]:
    pattern = r'"[^"]+/[^"]+"'
    return re.findall(pattern, source)[:10]


def _extract_imports_rust(source: str) -> List[str]:
    pattern = r"^use\s+\S+;"
    return re.findall(pattern, source, re.MULTILINE)[:10]


_IMPORT_EXTRACTORS = {
    "python":     _extract_imports_python,
    "javascript": _extract_imports_js,
    "typescript": _extract_imports_js,
    "java":       _extract_imports_java,
    "go":         _extract_imports_go,
    "rust":       _extract_imports_rust,
}


# ── Docstring extraction ──────────────────────────────────────────────────────

def _extract_docstring_python(node_text: str) -> Optional[str]:
    """Return the first triple-quoted string in a Python function/class body."""
    match = re.search(r'"""(.*?)"""', node_text, re.DOTALL)
    if not match:
        match = re.search(r"'''(.*?)'''", node_text, re.DOTALL)
    return match.group(1).strip()[:300] if match else None


def _extract_docstring_js(node_text: str) -> Optional[str]:
    """Return JSDoc comment before a function."""
    match = re.search(r"/\*\*(.*?)\*/", node_text, re.DOTALL)
    return match.group(1).strip()[:300] if match else None


_DOCSTRING_EXTRACTORS = {
    "python":     _extract_docstring_python,
    "javascript": _extract_docstring_js,
    "typescript": _extract_docstring_js,
}


# ── Decorator extraction ──────────────────────────────────────────────────────

def _extract_decorators_python(node_text: str) -> List[str]:
    return re.findall(r"@\w+(?:\(.*?\))?", node_text.split("def ")[0].split("class ")[0])


# ── Core AST parser (tree-walk, version-agnostic) ─────────────────────────────

def _parse_with_treesitter(
    source: str,
    lang: str,
    filename: str,
    project_id: str,
) -> List[CodeChunk]:
    """
    Use tree-sitter to extract function/class/method chunks by walking the AST.

    This approach is compatible with tree-sitter 0.21 through 0.25+ because it
    uses only stable Node attributes (node.type, node.children,
    node.child_by_field_name, node.start_point, node.end_point,
    node.start_byte, node.end_byte, node.text) rather than the query API
    which changed in 0.23+ (query.matches/captures were removed).

    Returns an empty list if parsing fails (caller falls back to text splitter).
    """
    ts_langs = _get_ts_languages()
    if lang not in ts_langs:
        return []

    target_types = _TARGET_TYPES.get(lang)
    if not target_types:
        return []

    try:
        from tree_sitter import Parser as TSParser

        language = ts_langs[lang]
        parser = TSParser(language)
        tree = parser.parse(bytes(source, "utf8"))

        all_imports = _IMPORT_EXTRACTORS.get(lang, lambda _: [])(source)
        docstring_fn = _DOCSTRING_EXTRACTORS.get(lang)

        # Walk the AST and collect target nodes
        collected: List = []
        seen_ranges: set = set()
        _walk_nodes(tree.root_node, target_types, seen_ranges, collected)

        chunks: List[CodeChunk] = []
        for node in collected:
            node_text = source[node.start_byte: node.end_byte]
            if len(node_text.strip()) < 10:
                continue

            start = node.start_point[0]   # 0-indexed line
            end   = node.end_point[0]

            # Extract name via stable child_by_field_name (all versions)
            name_node = node.child_by_field_name("name")
            fn_name: Optional[str] = None
            if name_node is not None:
                try:
                    fn_name = name_node.text.decode("utf8")
                except Exception:
                    fn_name = source[name_node.start_byte: name_node.end_byte]

            # Determine chunk type
            ntype = node.type
            if ntype in _CLASS_TYPES:
                chunk_type = "class"
            elif "function" in ntype or "method" in ntype or "arrow" in ntype:
                chunk_type = "function"
            else:
                chunk_type = "module"

            decorators: List[str] = []
            if lang == "python":
                decorators = _extract_decorators_python(node_text)

            docstring: Optional[str] = None
            if docstring_fn:
                docstring = docstring_fn(node_text)

            chunk = CodeChunk(
                raw_content=node_text,
                filename=filename,
                language=lang,
                chunk_type=chunk_type,
                chunk_index=len(chunks),
                start_line=start + 1,   # convert to 1-indexed
                end_line=end + 1,
                function_name=fn_name if chunk_type == "function" else None,
                class_name=fn_name if chunk_type == "class" else None,
                imports=all_imports,
                decorators=decorators,
                docstring=docstring,
                project_id=project_id,
            )
            chunks.append(chunk)

        return chunks

    except Exception as e:
        log_error("ast_chunker.parse", error=str(e), filename=filename, language=lang)
        return []


# ── Fallback: RecursiveCharacterTextSplitter ─────────────────────────────────

def _parse_with_fallback(
    source: str,
    lang: str,
    filename: str,
    project_id: str,
) -> List[CodeChunk]:
    """
    Fallback to LangChain's language-aware text splitter when tree-sitter
    is unavailable or fails.  Produces simple index-based chunks without
    rich metadata.
    """
    from langchain_text_splitters import Language as LCLang, RecursiveCharacterTextSplitter

    _LC_LANG_MAP = {
        "python":     LCLang.PYTHON,
        "javascript": LCLang.JS,
        "typescript": LCLang.TS,
        "java":       LCLang.JAVA,
        "go":         LCLang.GO,
        "rust":       LCLang.RUST,
    }

    lc_lang = _LC_LANG_MAP.get(lang)
    if lc_lang:
        splitter = RecursiveCharacterTextSplitter.from_language(
            language=lc_lang, chunk_size=1000, chunk_overlap=200
        )
    else:
        splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)

    texts = splitter.split_text(source)
    all_imports = _IMPORT_EXTRACTORS.get(lang, lambda _: [])(source)

    chunks = []
    for i, text in enumerate(texts):
        chunks.append(CodeChunk(
            raw_content=text,
            filename=filename,
            language=lang,
            chunk_type="module",
            chunk_index=i,
            start_line=0,
            end_line=0,
            imports=all_imports,
            project_id=project_id,
        ))
    return chunks


# ── Public API ────────────────────────────────────────────────────────────────

class ASTChunkerService:
    """
    Main entry point for chunking a source file.

    Usage:
        chunker = ASTChunkerService()
        chunks = chunker.chunk(source_code, "auth/jwt.py", "project_id_123")
    """

    def chunk(
        self,
        source: str,
        filename: str,
        project_id: str,
    ) -> List[CodeChunk]:
        """
        Parse `source` and return a list of CodeChunk objects.
        Tries AST parsing first; falls back to text splitting on failure.
        """
        ext = os.path.splitext(filename)[1].lower()
        lang = EXT_TO_LANG.get(ext, "")

        with Timer() as t:
            # Attempt AST parse
            strategy = "ast"
            chunks = _parse_with_treesitter(source, lang, filename, project_id)

            # If AST produced nothing, fall back
            if not chunks:
                strategy = "fallback"
                chunks = _parse_with_fallback(source, lang, filename, project_id)

        log_chunking(
            filename=filename,
            strategy=strategy,
            chunk_count=len(chunks),
            elapsed_ms=t.elapsed_ms,
        )
        return chunks


# Singleton
ast_chunker = ASTChunkerService()
