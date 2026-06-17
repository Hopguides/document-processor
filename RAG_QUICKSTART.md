# 🚀 RAG System Quick Start

## Overview
Simple RAG (Retrieval-Augmented Generation) system built on your existing document processor. Get a working chat interface in minutes!

## ✅ What's Ready
- ✅ Document ingestion to Pinecone vector DB
- ✅ Multi-provider LLM support (OpenAI, Gemini, Claude)  
- ✅ Modern chat UI
- ✅ REST API endpoints
- ✅ Docker deployment

## 🏃‍♂️ Quick Start (2 minutes)

### 1. Start the System
```bash
cd document-processor
python src/main.py
```

### 2. Configure API Keys
Open http://localhost:5001 and add your API keys:
- OpenAI API Key (required)
- Pinecone API Key (required)

### 3. Upload Documents
Use the web interface to upload and process documents into vector database.

### 4. Start Chatting!
Go to **http://localhost:5001/chat** and ask questions about your documents.

## 🧪 Test the System
```bash
# Run automated tests
python test_rag.py
```

## 🐳 Docker Deployment
```bash
# 1. Copy environment file
cp .env.example .env

# 2. Edit .env with your API keys
# OPENAI_API_KEY=sk-...
# PINECONE_API_KEY=...

# 3. Start with Docker
docker-compose up -d

# Access at http://localhost:5001/chat
```

## 🎯 API Endpoints

### Health Check
```bash
curl http://localhost:5001/api/rag/health
```

### Chat Query
```bash
curl -X POST http://localhost:5001/api/rag/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What are the main requirements?",
    "provider": "openai",
    "model": "gpt-3.5-turbo"
  }'
```

### Available Providers
```bash
curl http://localhost:5001/api/rag/providers
```

## 🔧 System Architecture

```
User Query → Chat UI → RAG API → Pinecone Search → LLM → Response
```

1. **Chat UI** (`/chat`) - Modern chat interface
2. **RAG API** (`/api/rag/query`) - Handles questions
3. **Pinecone** - Vector search for relevant documents  
4. **LLM** - Generates answers (OpenAI/Gemini/Claude)

## 📁 File Structure
```
src/
├── static/
│   ├── index.html      # Main admin interface
│   └── chat.html       # Chat interface 🆕
├── routes/
│   └── rag.py          # RAG endpoints 🆕
└── main.py             # Flask app
```

## 🛠️ Configuration

### Environment Variables
```bash
OPENAI_API_KEY=sk-...           # Required for embeddings
PINECONE_API_KEY=...            # Required for vector DB
PINECONE_ENVIRONMENT=us-east-1-aws
GOOGLE_API_KEY=...              # Optional for Gemini
ANTHROPIC_API_KEY=...           # Optional for Claude
```

### Local Development
The system reads API keys from:
1. Environment variables (production)
2. `src/api_keys.json` file (development)

## 🚦 System Status
- ✅ Document processing 
- ✅ Vector database (Pinecone)
- ✅ Multi-LLM support
- ✅ Chat interface
- ✅ Docker deployment
- ✅ Health monitoring

## 🎉 You're Done!
Your RAG system is ready. Ask questions about your documents at:
**http://localhost:5001/chat**

## 🔮 Next Steps
- Add streaming responses
- Implement conversation memory
- Add file upload to chat
- Citation highlighting
- Export chat history

---
*Built in 4-6 hours on existing document processor foundation* 💪