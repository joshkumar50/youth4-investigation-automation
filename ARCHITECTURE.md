# Architecture — Investigation Intelligence Platform

## System Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                         PRESENTATION LAYER                        │
│                                                                    │
│   React 18 + TypeScript + Vite + Tailwind                        │
│   React Query (server state) + Zustand (client state)             │
│   Framer Motion (animations) + Recharts (charts) + D3 (graph)    │
└──────────────────────────────┬───────────────────────────────────┘
                               │ REST API (HTTP/JSON)
                               │ Auto token refresh interceptor
┌──────────────────────────────▼───────────────────────────────────┐
│                           API GATEWAY                             │
│                                                                    │
│   FastAPI 0.111 — async Python API framework                     │
│   • JWT Authentication (python-jose + bcrypt)                    │
│   • Request validation (Pydantic v2)                              │
│   • CORS middleware                                               │
│   • GZip compression                                              │
│   • Structured logging (structlog)                                │
│   • Custom exception handlers                                     │
│   • OpenAPI docs (/docs)                                          │
└────────┬──────────────────────────────────┬──────────────────────┘
         │                                  │
┌────────▼────────┐               ┌─────────▼──────────────────────┐
│  Business Logic │               │        TASK QUEUE               │
│  Layer          │               │                                  │
│                 │   Publishes   │   Celery 5 + Redis 7            │
│ • AuthService   │ ──────────►  │   3 Queues:                      │
│ • CaseService   │               │   • evidence_processing          │
│ • EvidenceSvc   │               │   • ai_tasks                    │
│ • CopilotSvc    │               │   • graph_tasks                 │
│ • ReportService │               │                                  │
└────────┬────────┘               └─────────┬──────────────────────┘
         │                                  │
┌────────▼──────────────────────────────────▼──────────────────────┐
│                       AI / ML PIPELINE                            │
│                                                                    │
│  Worker 1: OCR Task                                               │
│    Tesseract OCR → PyMuPDF → EXIF extraction → Chat parser       │
│                                                                    │
│  Worker 2: NLP Task                                               │
│    spaCy en_core_web_sm → Regex patterns → Threat scoring        │
│                                                                    │
│  Worker 3: Embedding Task                                         │
│    Sentence Transformers (all-MiniLM-L6-v2) → ChromaDB           │
│                                                                    │
│  Worker 4: Timeline Task                                          │
│    Temporal extraction → Date parsing → Event classification     │
│                                                                    │
│  Worker 5: Graph Task                                             │
│    Entity co-occurrence → Relationship mapping → NetworkX         │
│                                                                    │
│  Worker 6: AI Summary Task                                        │
│    Ollama/Llama3 → RAG with ChromaDB → Structured insights       │
└────────┬──────────────────────────────────────────────────────────┘
         │
┌────────▼──────────────────────────────────────────────────────────┐
│                      PERSISTENCE LAYER                             │
│                                                                    │
│  PostgreSQL 16        │  MinIO                │  ChromaDB          │
│  (primary store)      │  (file storage)       │  (vector store)    │
│  • users              │  • evidence files     │  • text embeddings │
│  • cases              │  • reports            │  • semantic search │
│  • evidence           │                       │                    │
│  • entities           │  Redis 7              │                    │
│  • relationships      │  (message broker)     │                    │
│  • timeline_events    │  • Celery queue       │                    │
│  • investigation_notes│  • result backend     │                    │
└───────────────────────────────────────────────────────────────────┘
```

## Data Flow

```
Evidence Upload
    │
    ▼
MinIO Storage (file saved)
    │
    ▼
Evidence DB Record Created (status: PENDING)
    │
    ▼
Celery Task Dispatched
    │
    ├── OCR Task → extracted_text saved to DB
    │       │
    │       ├── NLP Task → entities saved to entities table
    │       │
    │       ├── Embedding Task → text chunks → ChromaDB
    │       │
    │       ├── Timeline Task → events saved to timeline_events
    │       │
    │       └── Graph Task → relationships saved to entity_relationships
    │
    └── Evidence status → COMPLETED
```

## Key Design Patterns

| Pattern | Implementation |
|---------|---------------|
| Repository Pattern | `BaseRepository[T]` generic base class |
| Service Layer | Business logic isolated from routers |
| DTOs | Pydantic v2 schemas for all API contracts |
| Dependency Injection | FastAPI `Depends()` for DB, auth, storage |
| Task Queue | Celery with named queues and retry logic |
| Graceful Degradation | Ollama fallback to rule-based responses |
| Storage Abstraction | `StorageService` wraps MinIO with retry |
| Async/Sync Bridge | Async FastAPI ↔ Sync Celery via DB |

## Technology Justifications

| Technology | Why |
|-----------|-----|
| FastAPI | Async Python, auto OpenAPI, Pydantic v2 |
| PostgreSQL | JSONB for flexible metadata, full ACID |
| Celery + Redis | Battle-tested async task processing |
| MinIO | S3-compatible, self-hosted, scalable |
| ChromaDB | Purpose-built for embeddings + similarity |
| Ollama | Local LLM inference, no API costs |
| Sentence Transformers | Lightweight, CPU-friendly embeddings |
| spaCy | Production NLP, fastest NER available |
| React + Vite | Fast development, TypeScript-first |
| Tailwind | Design system in code, no CSS files |
