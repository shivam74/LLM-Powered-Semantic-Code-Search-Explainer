# 🔍 LLM-Powered Semantic Code Search & AI Code Explainer

A modern, full-stack application that lets you semantically search large codebases using natural language and leverage LLMs to explain, debug, and optimize your code — all in a sleek, VSCode-inspired IDE interface.

---

## 🌟 Features

- **🔎 Semantic Code Search** — Search your codebase using natural language (e.g., *"Where is authentication handled?"*) instead of exact keyword matching. Powered by vector embeddings.
- **🤖 AI Code Explainer** — Select any code snippet and ask the AI to explain its logic, detect bugs, or suggest performance optimizations.
- **📁 Project Management** — Create isolated projects for different codebases. Each project has its own vector index.
- **📤 File Upload** — Upload individual code files (Python, JS, TS, Go, Rust, Java, C++, and more) to be parsed and indexed.
- **🐙 GitHub Repo Import** — Paste any public GitHub repository URL and automatically clone, parse, and index all supported code files in one click.
- **🗑️ Delete Projects & Files** — Remove projects or individual files along with all their associated vector embeddings.
- **💬 Interactive AI Chat** — Chat with an AI assistant that has context about your code. Ask general questions or trigger specific actions (Explain, Find Bugs, Optimize).
- **🖥️ Monaco Editor** — View your code files in a full-featured editor with syntax highlighting for 15+ languages.
- **🔐 JWT Authentication** — Secure, token-based user accounts with full project isolation.

---

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────────────┐    ┌──────────────┐
│  React Frontend │───▶│  FastAPI Backend      │───▶│   MongoDB    │
│  (Vite + Vite)  │    │  (Python 3.11)        │    │  (Metadata)  │
│  Monaco Editor  │    │                       │    └──────────────┘
│  Framer Motion  │    │  ┌─────────────────┐  │    ┌──────────────┐
└─────────────────┘    │  │ LangChain       │  │───▶│   ChromaDB   │
                       │  │ Groq LLM        │  │    │  (Vectors)   │
                       │  │ HF Embeddings   │  │    └──────────────┘
                       │  └─────────────────┘  │
                       └──────────────────────┘
```

| Layer | Technology |
|---|---|
| **Frontend** | React 18, Vite, Tailwind CSS v4, Framer Motion, Monaco Editor |
| **Backend** | Python 3.11, FastAPI, Motor (Async MongoDB driver) |
| **LLM Inference** | Groq API (`llama-3.1-8b-instant`) — fast & free |
| **Embeddings** | `sentence-transformers/all-MiniLM-L6-v2` via HuggingFace Inference API |
| **Vector Database** | ChromaDB (embedded, persistent) |
| **Code Parsing** | LangChain `RecursiveCharacterTextSplitter` with language-aware chunking |
| **Database** | MongoDB (via Docker) |
| **Orchestration** | Docker Compose |

---

## 🚀 Getting Started

### Prerequisites

- [Docker Desktop](https://www.docker.com/) (must be **running**)
- A free [Groq API Key](https://console.groq.com/) (for LLM chat)
- A free [HuggingFace API Token](https://huggingface.co/settings/tokens) (for embeddings)

### Setup Instructions

**1. Clone the repository**
```bash
git clone https://github.com/shivam74/LLM-Powered-Semantic-Code-Search-Explainer.git
cd LLM-Powered-Semantic-Code-Search-Explainer
```

**2. Configure Environment Variables**

Copy the example file and fill in your keys:
```bash
cp .env.example .env
```

Edit `.env`:
```env
MONGODB_URI=mongodb://mongodb:27017/llm_code_search
JWT_SECRET_KEY=your_super_secret_jwt_key_here

# Required for AI chat features
GROQ_API_KEY=your_groq_api_key_here

# Required for semantic search (embeddings)
HUGGINGFACE_API_KEY=your_huggingface_token_here

# Optional fallback
OPENAI_API_KEY=
```

**3. Start the Application**
```bash
docker compose up --build
```
> ⏳ The first build takes several minutes as it downloads Python dependencies and PyTorch. Subsequent starts are instant due to Docker layer caching.

**4. Access the App**

| Service | URL |
|---|---|
| 🟢 Frontend UI | [http://localhost:5173](http://localhost:5173) |
| 🔵 Backend API Docs | [http://localhost:8000/docs](http://localhost:8000/docs) |

---

## 📖 How to Use

### 1. Register & Login
Navigate to the app, create an account, and log in.

### 2. Create a Project
From the Dashboard, click **"+ New Project"** and give it a name. Projects act as isolated search scopes.

### 3. Add Code

**Option A — Upload a File:**
Inside a project, click **"Upload File"** and select any supported code file.

**Option B — Import a GitHub Repository:**
Click **"Import GitHub Repo"**, paste a public GitHub URL (e.g., `https://github.com/expressjs/express`), and click Import. All supported files will be automatically cloned, parsed, and indexed.

### 4. Semantic Search
Use the top search bar to ask questions in natural language:
- *"Where is the routing logic handled?"*
- *"How are HTTP headers parsed?"*
- *"Code that sends JSON responses"*

Results are ranked by semantic similarity, not keyword matching.

### 5. AI Assistant
Select a file in the explorer, highlight code in the editor, then use the right panel to:
- **Explain Code** — Get a detailed explanation of the selected snippet
- **Find Bugs** — Detect vulnerabilities and logic errors
- **Optimize Performance** — Get refactoring suggestions
- **Ask anything** — Chat freely with context about your codebase

### 6. Manage Projects & Files
- Hover over a **project card** on the Dashboard → click the 🗑️ icon to delete it (removes all files and embeddings)
- Hover over a **file** in the sidebar → click the 🗑️ icon to remove it individually

---

## 📁 Supported File Types

`.py` `.js` `.jsx` `.ts` `.tsx` `.java` `.go` `.rs` `.cpp` `.c` `.h` `.cs` `.rb` `.php` `.swift` `.kt` `.md` `.json` `.yaml` `.yml` `.toml` `.sh`

---

## 🛠️ Tech Stack Choices

- **FastAPI** — High performance, async support, automatic OpenAPI docs, and native Pydantic integration.
- **Groq API** — Free, ultra-fast LLM inference (up to 800 tok/s) using `llama-3.1-8b-instant`. No GPU required.
- **HuggingFace Inference API** — Generates semantic embeddings via the `all-MiniLM-L6-v2` model remotely, avoiding heavy local model downloads.
- **ChromaDB** — Open-source embedded vector database that runs inside the Docker container with no external dependencies.
- **LangChain** — Language-aware code chunking (`RecursiveCharacterTextSplitter`) and structured prompt engineering.
- **Monaco Editor** — The engine behind VS Code, providing a premium code viewing experience directly in the browser.
- **Framer Motion** — Smooth, physics-based animations for a polished UI experience.

---

## 🐳 Docker Services

| Container | Image | Port |
|---|---|---|
| `llm_search_frontend` | Node 20 Alpine | `5173` |
| `llm_search_backend` | Python 3.11 Slim | `8000` |
| `llm_search_mongodb` | mongo:latest | `27017` (internal) |

---

## 📝 License

MIT License — feel free to use, modify, and distribute.
