# LLM-Powered Semantic Code Search & AI Code Explainer

A modern, full-stack application built to semantically search large codebases and leverage LLMs (OpenAI / HuggingFace) to explain, debug, and optimize your code.

## 🌟 Features

- **Semantic Code Search**: Upload code files (Python, JS, C++, Java) and search using natural language.
- **AI Code Explainer**: Select snippets of code and ask the AI to explain the logic.
- **Bug Detection & Optimization**: AI-powered vulnerability detection and performance suggestions.
- **Interactive IDE Interface**: Built-in Monaco editor with syntax highlighting and side-by-side AI chat.
- **Authentication**: Secure JWT-based user authentication and project isolation.
- **Modern UI**: Sleek, responsive, and animated dark-mode interface built with Tailwind CSS & Framer Motion.

## 🏗️ Architecture

- **Frontend**: React, Vite, Tailwind CSS v4, Framer Motion, Monaco Editor.
- **Backend**: Python, FastAPI, Motor (Async MongoDB).
- **Vector Database**: ChromaDB for fast semantic retrieval.
- **Embeddings**: `all-MiniLM-L6-v2` via SentenceTransformers.
- **LLM Orchestration**: LangChain for structured prompt engineering and conversational context.
- **Deployment**: Docker Compose for easy, consistent orchestration.

## 🚀 Getting Started

### Prerequisites

- [Docker](https://www.docker.com/) and Docker Compose
- An API Key from [OpenAI](https://platform.openai.com/) OR [HuggingFace](https://huggingface.co/settings/tokens)

### Setup Instructions

1. **Clone the repository** (if not already local).
2. **Configure Environment Variables**:
   Open the `.env.example` file in the root directory, rename it to `.env`, and fill in your API keys:
   ```env
   MONGODB_URI=mongodb://mongodb:27017/llm_code_search
   JWT_SECRET_KEY=your_super_secret_jwt_key_here
   
   # Provide AT LEAST ONE of these keys:
   OPENAI_API_KEY=your_openai_api_key_here
   HUGGINGFACE_API_KEY=your_huggingface_api_key_here
   ```
   *(Note: The system prioritizes HuggingFace if both are provided based on user preference for free tiers, but defaults to OpenAI if configured).*

3. **Start the Application using Docker**:
   ```bash
   docker-compose up --build -d
   ```

4. **Access the App**:
   - **Frontend UI**: [http://localhost:5173](http://localhost:5173)
   - **Backend API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)

### How to Use

1. Navigate to the Frontend UI and **Register** a new account.
2. Create a new **Project** from the Dashboard.
3. Inside the project, click **Upload File** to add code files.
4. The backend will automatically parse, chunk, and embed the code into ChromaDB.
5. Use the top **Search Bar** to ask semantic questions (e.g., "Where is authentication handled?").
6. Click on a file to view it in the editor. Highlight code and use the **AI Assistant** sidebar to explain, optimize, or detect bugs!

## 🛠️ Tech Stack Choices
- **FastAPI**: Chosen for its high performance, async support, and native Pydantic integration.
- **LangChain**: Simplifies swapping between OpenAI and HuggingFace models while providing excellent text-splitters for code parsing.
- **ChromaDB**: An open-source, embedded vector database that runs seamlessly within a Docker container without external dependencies.
- **Monaco Editor**: The core editor behind VSCode, providing an unparalleled code viewing experience on the web.

## 📝 License
MIT License
