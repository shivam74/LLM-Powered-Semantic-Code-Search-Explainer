# 🔍 LLM-Powered Semantic Code Search & AI Code Explainer

A **production-grade AI code intelligence platform**. Upload a codebase or import a GitHub repository, then search it using natural language, chat with an AI that understands your code's structure, and get explanations, bug reports, and optimisations — all powered by a contextual retrieval pipeline inspired by Anthropic's 2024 research.

---

## 🌟 Features

- **🔎 Hybrid Semantic Search** — Fuses dense vector search with BM25 keyword retrieval using Reciprocal Rank Fusion (RRF). Finds code by *meaning* and by *exact identifier* simultaneously.
- **📊 Score Transparency** — Every search result surfaces its individual vector score, BM25 score, and fusion score in the UI so you know *why* a chunk was retrieved.
- **🌲 AST-Aware Chunking** — Code is split at function / class / method boundaries using tree-sitter, not arbitrary character counts. Supports Python, JS, TS, Java, Go, and Rust.
- **📖 Contextual Enrichment** — Every chunk is prefixed with its file path, module, function signature, imports, and docstring before embedding, dramatically improving recall.
- **🤖 AI Code Assistant** — Select any snippet and ask the AI to explain, find bugs, or optimise. Context from your entire codebase is automatically retrieved and injected.
- **📁 Project Management** — Isolated projects, each with their own vector index and BM25 corpus. Full CRUD for projects and files.
- **📤 File Upload & GitHub Import** — Upload individual files or import an entire public GitHub repository in one click.
- **🔐 JWT Authentication** — Secure token-based accounts with full project isolation.
- **📡 Retrieval Debug API** — Inspect chunk metadata, individual vector / BM25 / fusion scores, and re-index projects on demand.
- **🔁 Optional Cross-Encoder Reranking** — Toggle `ENABLE_RERANKER=true` to add a `BAAI/bge-reranker-base` reranker pass for even higher precision.

---

## 🏗️ Architecture

### Retrieval Pipeline (v2.0)

```
FILE INDEXING
─────────────────────────────────────────────────────────────────
Source File
  │
  ▼
ASTChunkerService  (tree-sitter, recursive tree-walk)
  • Extracts functions, classes, methods as individual chunks
  • Metadata: filename, language, function_name, class_name,
    start_line, end_line, decorators, docstring, imports
  • Fallback: RecursiveCharacterTextSplitter for unsupported langs
  │
  ▼
ContextualEnricher
  • Builds a structured context header per chunk:
      File: auth/jwt.py | Language: Python | Module: auth
      Type: function | Name: verify_token
      Uses: jwt, fastapi | Description: Validates JWT token
      ---
      <raw code>
  • Optional: Groq LLM generates a 1-sentence summary (ENABLE_LLM_ENRICHMENT)
  │
  ┌────────────────────────────────────────┐
  │                                        │
  ▼                                        ▼
ChromaDB                             MongoDB BM25 Index
(embed enriched text,                (tokenise raw code,
 store raw + chunk_id in metadata)    persist corpus)

──────────────────────────────────────────────────────────────────

RETRIEVAL QUERY
─────────────────────────────────────────────────────────────────
User Query
  │
  ├─────────────────────┐
  ▼                     ▼
Vector Search         BM25 Search
score = 1/(1+dist)   score normalised to [0,1]
(ChromaDB, top-20)   (rank-bm25, top-20)
  │                     │
  └──────────┬───────────┘
             ▼
     RRF Fusion  (k=60)
     score = Σ weight / (60 + rank)
     vector_weight=0.7  bm25_weight=0.3
             │
             ▼
     Cross-Encoder Reranker  ← optional (BAAI/bge-reranker-base)
     top-20 candidates → top-5 final
             │
             ▼
     Results → API → Frontend
     (with vector_score, bm25_score, fusion score, chunk metadata)
```

### Why This Architecture?

| Problem | Solution |
|---|---|
| Arbitrary text splits break function context | AST chunking at semantic boundaries |
| Embedding model doesn't know *where* code lives | Contextual enrichment prefixes every chunk |
| Vector search misses exact identifiers | BM25 keyword search catches exact names |
| BM25 misses semantic meaning | Vector search covers concepts |
| Neither ranks perfectly | RRF fusion — robust and normalisation-free |
| Fusion still has noise | Cross-encoder reranker for fine-grained relevance |

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | React 18, Vite, Tailwind CSS v4, Framer Motion, Monaco Editor |
| **Backend** | Python 3.11, FastAPI, Motor (async MongoDB) |
| **AST Chunking** | tree-sitter 0.25+ with recursive tree-walk (Python, JS, TS, Java, Go, Rust) |
| **Embeddings** | `sentence-transformers/all-MiniLM-L6-v2` via HuggingFace Inference API |
| **Vector Store** | ChromaDB (embedded, persistent) |
| **Sparse Retrieval** | rank-bm25 (BM25Okapi), corpus persisted in MongoDB |
| **Reranker** | `BAAI/bge-reranker-base` via HuggingFace Inference API (opt-in) |
| **LLM** | Groq API — `llama-3.1-8b-instant` (fast & free) |
| **Orchestration** | Docker Compose |

---

## 🚀 Getting Started

### Prerequisites

- [Docker Desktop](https://www.docker.com/) installed and running
- Free [Groq API Key](https://console.groq.com/) — for the AI assistant
- Free [HuggingFace Token](https://huggingface.co/settings/tokens) — for embeddings

### Setup

```bash
git clone https://github.com/shivam74/LLM-Powered-Semantic-Code-Search-Explainer.git
cd LLM-Powered-Semantic-Code-Search-Explainer

cp .env.example .env
# Edit .env and fill in your GROQ_API_KEY and HUGGINGFACE_API_KEY

docker compose up --build
```

### Access

| Service | URL |
|---|---|
| 🟢 Frontend | [http://localhost:5173](http://localhost:5173) |
| 🔵 API Docs | [http://localhost:8000/docs](http://localhost:8000/docs) |

---

## ⚙️ Configuration (`.env`)

```env
MONGODB_URI=mongodb://mongodb:27017/llm_code_search
JWT_SECRET_KEY=your_secret_here

# LLM providers (Groq recommended — free and fast)
GROQ_API_KEY=your_groq_key
HUGGINGFACE_API_KEY=your_hf_token

# Retrieval tuning (optional — defaults shown)
VECTOR_WEIGHT=0.7          # RRF weight for dense retrieval
BM25_WEIGHT=0.3            # RRF weight for sparse retrieval (must sum to 1.0)
RETRIEVAL_CANDIDATE_K=20   # Candidates from each backend before fusion
RETRIEVAL_TOP_K=5          # Final results returned

# Optional features (disabled by default)
ENABLE_RERANKER=false      # Cross-encoder reranker — adds ~300ms, improves ranking
ENABLE_LLM_ENRICHMENT=false  # LLM-generated summaries at index time — improves recall
```

---

## 📁 Supported Languages

| Language | AST Chunking | Fallback Splitting |
|---|---|---|
| Python | ✅ tree-sitter | — |
| JavaScript / JSX | ✅ tree-sitter | — |
| TypeScript / TSX | ✅ tree-sitter | — |
| Java | ✅ tree-sitter | — |
| Go | ✅ tree-sitter | — |
| Rust | ✅ tree-sitter | — |
| C, C++, C#, Ruby, PHP, Swift, Kotlin | — | ✅ LangChain splitter |
| Markdown, JSON, YAML, TOML, Shell | — | ✅ LangChain splitter |

---

## 📡 API Endpoints

### Core

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/auth/register` | Register a new account |
| POST | `/api/auth/login` | Login (returns JWT) |
| POST | `/api/files/projects` | Create a project |
| GET | `/api/files/projects` | List your projects |
| DELETE | `/api/files/projects/{id}` | Delete a project |
| POST | `/api/files/upload/{project_id}` | Upload and index a file |
| DELETE | `/api/files/project/{id}/file/{fid}` | Delete a file |
| POST | `/api/files/upload/github/{id}` | Import a public GitHub repo |
| POST | `/api/search/` | Hybrid semantic search |
| POST | `/api/chat/` | AI code assistant |

### Retrieval Debug

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/retrieval/debug` | Full score breakdown per chunk |
| GET | `/api/retrieval/chunks/{project_id}` | List all chunk metadata |
| GET | `/api/retrieval/stats/{project_id}` | Index statistics |
| POST | `/api/retrieval/reindex/{project_id}` | Re-index with current pipeline |

---

## 📝 License

MIT License
