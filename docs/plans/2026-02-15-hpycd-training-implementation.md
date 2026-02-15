# HpyCD Training & Localhost Deployment Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement Docker Compose-based localhost deployment with async Celery training workers, inference endpoints, and health monitoring for the HpyCD model.

**Architecture:** Docker Compose with 4 services (API on 8000, Redis on 6379, Celery Worker, optional Flower on 5555). Training runs asynchronously via Celery jobs. Model checkpoints persisted to Docker volumes.

**Tech Stack:** Python 3.11, FastAPI, Celery, Redis, Docker, Docker Compose

---

## Task 1: Create Project Requirements File

**Files:**

- Create: `requirements.txt`

**Step 1: Write requirements with all dependencies**

```txt
# FastAPI & Server
fastapi>=0.115.0
uvicorn[standard]>=0.34.0
python-multipart>=0.0.20

# Celery & Async
celery[redis]>=5.3.0
redis>=5.0.0

# Data & ML
torch>=2.1.0
transformers>=4.35.0
sentence-transformers>=2.2.0
numpy>=1.24.0
pandas>=2.0.0
geoopt>=0.5.0
scikit-learn>=1.3.0
tqdm>=4.66.0

# Database & API
supabase>=2.0.0
httpx>=0.28.0

# File Parsing
openpyxl>=3.1.0
xlrd>=2.0.1
msoffcrypto-tool>=6.0.0

# Utils
python-dotenv>=1.0.0
pydantic>=2.0.0
```

**Step 2: Commit**

```bash
git add requirements.txt
git commit -m "chore: add project requirements for training pipeline"
```

---

## Task 2: Create Environment Configuration

**Files:**

- Create: `.env.local`
- Create: `.env.example`

**Step 1: Write .env.local**

```bash
# API Configuration
API_PORT=8000
API_HOST=0.0.0.0
API_WORKERS=1

# Redis Configuration
REDIS_URL=redis://redis:6379/0
REDIS_PORT=6379

# Supabase Configuration
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_KEY=your-service-key

# Training Configuration
MODEL_CHECKPOINT_DIR=/app/checkpoints
DEFAULT_EPOCHS=50
DEFAULT_BATCH_SIZE=32
DEFAULT_LEARNING_RATE=0.0001

# Worker Configuration
CELERY_WORKERS=2
CELERY_LOG_LEVEL=INFO
CELERY_TASK_ALWAYS_EAGER=False

# Flower (Celery Monitoring)
FLOWER_PORT=5555
```

**Step 2: Write .env.example (without secrets)**

```bash
# Copy this to .env.local and fill in your values

# API Configuration
API_PORT=8000
API_HOST=0.0.0.0

# Redis Configuration
REDIS_URL=redis://redis:6379/0

# Supabase Configuration
SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_KEY=

# Training Configuration
MODEL_CHECKPOINT_DIR=/app/checkpoints
DEFAULT_EPOCHS=50
```

**Step 3: Commit**

```bash
git add .env.local .env.example
git commit -m "chore: add environment configuration templates"
```

---

## Task 3: Create Celery Application Configuration

**Files:**

- Create: `apps/api/celery_app.py`

**Step 1: Write Celery app with Redis broker**

```python
"""Celery application configuration for async training jobs."""

import os
from celery import Celery

# Use Redis as broker and backend
redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")

celery_app = Celery(
    "scale_training",
    broker=redis_url,
    backend=redis_url,
    include=["apps.api.tasks.training_tasks"],
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max per task
    worker_prefetch_multiplier=1,  # Process one task at a time per worker
    result_expires=3600 * 24,  # Results expire after 24 hours
)

# Optional: Configure task routing
celery_app.conf.task_routes = {
    "apps.api.tasks.training_tasks.*": {"queue": "training"},
}

if __name__ == "__main__":
    celery_app.start()
```

**Step 2: Commit**

```bash
git add apps/api/celery_app.py
git commit -m "feat: add Celery app configuration with Redis broker"
```

---

## Task 4: Create Training Tasks Module

**Files:**

- Create: `apps/api/tasks/__init__.py`
- Create: `apps/api/tasks/training_tasks.py`

**Step 1: Create **init**.py**

```python
"""Async task modules for SCALE API."""
```

**Step 2: Write training_tasks.py with async training logic**

```python
"""Celery tasks for async model training."""

import logging
from typing import List, Dict, Optional
from celery import shared_task
from celery.exceptions import MaxRetriesExceededError

from packages.categorization.training_pipeline import (
    HypCDTrainingPipeline,
    TrainingConfig,
)
from packages.categorization.backends.cloud import CloudBackend

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def train_model_task(
    self,
    texts: List[str],
    labels: List[int],
    user_id: str,
    job_id: str,
    epochs: int = 50,
    batch_size: int = 32,
    learning_rate: float = 1e-4,
    checkpoint_dir: str = "/app/checkpoints",
) -> Dict:
    """
    Async task to train HpyCD model.
    
    Args:
        texts: List of transaction descriptions
        labels: List of category labels
        user_id: User ID for job tracking
        job_id: Training job ID in database
        epochs: Number of training epochs
        batch_size: Batch size for training
        learning_rate: Learning rate
        checkpoint_dir: Directory to save checkpoints
        
    Returns:
        Dictionary with training results and metrics
    """
    try:
        logger.info(f"Starting training job {job_id} for user {user_id}")
        
        # Create training config
        config = TrainingConfig(
            epochs=epochs,
            batch_size=batch_size,
            learning_rate=learning_rate,
            checkpoint_dir=f"{checkpoint_dir}/{user_id}",
            checkpoint_frequency=5,
            num_classes=len(set(labels)),
        )
        
        # Initialize pipeline
        pipeline = HypCDTrainingPipeline(config)
        
        # Data loader function
        def data_loader():
            return texts, labels
        
        # Run training
        metrics = pipeline.train(data_loader)
        
        # Export final model
        model_path = f"{checkpoint_dir}/{user_id}/final_model.pt"
        pipeline.export_model(model_path)
        
        logger.info(f"Training job {job_id} completed successfully")
        
        return {
            "status": "completed",
            "job_id": job_id,
            "user_id": user_id,
            "metrics": metrics,
            "model_path": model_path,
        }
        
    except Exception as exc:
        logger.error(f"Training job {job_id} failed: {exc}")
        
        # Retry on failure
        try:
            self.retry(exc=exc)
        except MaxRetriesExceededError:
            logger.error(f"Max retries exceeded for job {job_id}")
            return {
                "status": "failed",
                "job_id": job_id,
                "user_id": user_id,
                "error": str(exc),
            }


@shared_task
def classify_transaction_task(
    text: str,
    model_path: str,
    backend_type: str = "cloud",
) -> Dict:
    """
    Classify a single transaction using a trained model.
    
    Args:
        text: Transaction description
        model_path: Path to trained model
        backend_type: Backend type ('cloud' or 'mobile')
        
    Returns:
        Dictionary with prediction and confidence
    """
    import torch
    from packages.categorization.hypcd import HypCDClassifier
    
    try:
        # Initialize backend
        if backend_type == "cloud":
            from packages.categorization.backends.cloud import CloudBackend
            backend = CloudBackend()
        else:
            from packages.categorization.backends.mobile import MobileBackend
            backend = MobileBackend()
        
        # Load model
        checkpoint = torch.load(model_path, map_location="cpu")
        
        # Initialize classifier
        classifier = HypCDClassifier(
            backend=backend,
            num_classes=checkpoint["config"]["num_classes"],
            proj_dim=checkpoint["config"]["proj_dim"],
            backend_type=backend_type,
        )
        classifier.load_state_dict(checkpoint["classifier"])
        classifier.eval()
        
        # Get embedding and predict
        with torch.no_grad():
            embedding = backend.embed(text).unsqueeze(0)
            hyp_embedding = classifier.embedder.projector(embedding)
            logits = classifier.classifier(hyp_embedding)
            probs = torch.softmax(logits, dim=-1)
            pred_idx = torch.argmax(probs, dim=-1).item()
            confidence = probs[0][pred_idx].item()
        
        # Map to category name
        category = classifier.labels[pred_idx]
        
        return {
            "category": category,
            "confidence": confidence,
            "all_probabilities": {
                label: prob.item()
                for label, prob in zip(classifier.labels, probs[0])
            },
        }
        
    except Exception as exc:
        logger.error(f"Classification failed: {exc}")
        return {
            "category": "Uncategorized",
            "confidence": 0.0,
            "error": str(exc),
        }
```

**Step 3: Commit**

```bash
git add apps/api/tasks/__init__.py apps/api/tasks/training_tasks.py
git commit -m "feat: add Celery training and classification tasks"
```

---

## Task 5: Create Classification Router

**Files:**

- Create: `apps/api/routers/classify.py`
- Create: `apps/api/tests/test_classify.py`

**Step 1: Write classify router**

```python
"""Router for model inference/classification endpoints."""

import os
import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from supabase import Client

from apps.api.deps import get_user_client
from apps.api.tasks.training_tasks import classify_transaction_task

router = APIRouter(tags=["classification"])
logger = logging.getLogger(__name__)

CHECKPOINT_DIR = os.getenv("MODEL_CHECKPOINT_DIR", "/app/checkpoints")


class ClassifyRequest(BaseModel):
    """Request to classify a transaction."""
    description: str
    use_latest_model: bool = True
    model_path: Optional[str] = None


class ClassifyResponse(BaseModel):
    """Classification response."""
    category: str
    confidence: float
    model_used: str


class BatchClassifyRequest(BaseModel):
    """Request to classify multiple transactions."""
    descriptions: List[str]
    use_latest_model: bool = True


class BatchClassifyResponse(BaseModel):
    """Batch classification response."""
    predictions: List[ClassifyResponse]


@router.post("/classify", response_model=ClassifyResponse)
async def classify_transaction(
    request: ClassifyRequest,
    client: Client = Depends(get_user_client),
):
    """
    Classify a single transaction description.
    
    Uses the latest trained model for the user by default.
    """
    try:
        user_response = client.auth.get_user()
        if not user_response or not user_response.user:
            raise HTTPException(status_code=401, detail="Invalid bearer token")
        user_id = user_response.user.id
        
        # Determine model path
        if request.use_latest_model:
            model_path = f"{CHECKPOINT_DIR}/{user_id}/latest_checkpoint.pt"
        else:
            model_path = request.model_path
        
        if not model_path or not os.path.exists(model_path):
            raise HTTPException(
                status_code=400,
                detail="No trained model found. Please train a model first.",
            )
        
        # Run classification task synchronously (fast inference)
        result = classify_transaction_task.delay(
            text=request.description,
            model_path=model_path,
            backend_type="cloud",
        ).get(timeout=30)
        
        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])
        
        return ClassifyResponse(
            category=result["category"],
            confidence=result["confidence"],
            model_used=model_path,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Classification failed: {e}")
        raise HTTPException(status_code=500, detail="Classification failed")


@router.post("/classify/batch", response_model=BatchClassifyResponse)
async def classify_batch(
    request: BatchClassifyRequest,
    client: Client = Depends(get_user_client),
):
    """Classify multiple transactions in batch."""
    try:
        user_response = client.auth.get_user()
        if not user_response or not user_response.user:
            raise HTTPException(status_code=401, detail="Invalid bearer token")
        user_id = user_response.user.id
        
        model_path = f"{CHECKPOINT_DIR}/{user_id}/latest_checkpoint.pt"
        
        if not os.path.exists(model_path):
            raise HTTPException(
                status_code=400,
                detail="No trained model found.",
            )
        
        # Process all descriptions
        predictions = []
        for desc in request.descriptions:
            result = classify_transaction_task.delay(
                text=desc,
                model_path=model_path,
                backend_type="cloud",
            ).get(timeout=30)
            
            predictions.append(ClassifyResponse(
                category=result.get("category", "Uncategorized"),
                confidence=result.get("confidence", 0.0),
                model_used=model_path,
            ))
        
        return BatchClassifyResponse(predictions=predictions)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Batch classification failed: {e}")
        raise HTTPException(status_code=500, detail="Batch classification failed")


@router.get("/models")
async def list_models(client: Client = Depends(get_user_client)):
    """List available trained models for the user."""
    try:
        user_response = client.auth.get_user()
        if not user_response or not user_response.user:
            raise HTTPException(status_code=401, detail="Invalid bearer token")
        user_id = user_response.user.id
        
        user_checkpoint_dir = f"{CHECKPOINT_DIR}/{user_id}"
        
        if not os.path.exists(user_checkpoint_dir):
            return {"models": []}
        
        models = []
        for filename in os.listdir(user_checkpoint_dir):
            if filename.endswith(".pt"):
                filepath = os.path.join(user_checkpoint_dir, filename)
                stat = os.stat(filepath)
                models.append({
                    "name": filename,
                    "path": filepath,
                    "size_mb": round(stat.st_size / (1024 * 1024), 2),
                    "created_at": stat.st_mtime,
                })
        
        return {"models": sorted(models, key=lambda x: x["created_at"], reverse=True)}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list models: {e}")
        raise HTTPException(status_code=500, detail="Failed to list models")
```

**Step 2: Write test file**

```python
"""Tests for classification router."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch

from apps.api.main import app

client = TestClient(app)


@pytest.fixture
def mock_user_client():
    """Mock authenticated user client."""
    mock_client = Mock()
    mock_user = Mock()
    mock_user.id = "test-user-123"
    mock_client.auth.get_user.return_value = Mock(user=mock_user)
    return mock_client


class TestClassifyEndpoint:
    """Tests for /classify endpoint."""
    
    def test_classify_no_auth(self):
        """Test classification without authentication."""
        response = client.post("/api/v1/classify", json={
            "description": "Test transaction",
            "use_latest_model": True,
        })
        assert response.status_code == 401
    
    @patch("apps.api.routers.classify.classify_transaction_task")
    @patch("apps.api.deps.get_user_client")
    def test_classify_success(self, mock_get_client, mock_task, mock_user_client):
        """Test successful classification."""
        mock_get_client.return_value = mock_user_client
        mock_task.delay.return_value.get.return_value = {
            "category": "Food & Dining",
            "confidence": 0.95,
        }
        
        with patch("os.path.exists", return_value=True):
            response = client.post("/api/v1/classify", json={
                "description": "Starbucks coffee",
                "use_latest_model": True,
            })
        
        assert response.status_code == 200
        data = response.json()
        assert data["category"] == "Food & Dining"
        assert data["confidence"] == 0.95
```

**Step 3: Commit**

```bash
git add apps/api/routers/classify.py apps/api/tests/test_classify.py
git commit -m "feat: add classification router with inference endpoints"
```

---

## Task 6: Update Training Router for Async

**Files:**

- Modify: `apps/api/routers/training.py`

**Step 1: Add async training endpoint**

Add to imports:

```python
from apps.api.tasks.training_tasks import train_model_task
```

Replace the `/train` endpoint (lines 242-350) with async version:

```python
@router.post("/train")
async def train_model_async(
    epochs: int = 10,
    batch_size: int = 32,
    learning_rate: float = 1e-4,
    client: Client = Depends(get_user_client),
):
    """
    Start async training job for HypCD model.
    
    Returns immediately with job_id. Check status via /training/status/{job_id}.
    """
    try:
        user_response = client.auth.get_user()
        if not user_response or not user_response.user:
            raise HTTPException(status_code=401, detail="Invalid bearer token")
        user_id = user_response.user.id
        
        # Fetch user's labeled transactions
        res = (
            client.table("transactions")
            .select("description, category")
            .eq("user_id", user_id)
            .not_.is_("category", None)
            .execute()
        )
        
        if not res.data or len(res.data) < 10:
            raise HTTPException(
                status_code=400,
                detail="Need at least 10 labeled transactions for training.",
            )
        
        # Prepare data
        texts = [tx["description"] for tx in res.data]
        
        # Map categories to labels
        from packages.categorization.constants import CATEGORIES
        category_to_idx = {cat: idx for idx, cat in enumerate(CATEGORIES)}
        labels = [category_to_idx.get(tx["category"], 0) for tx in res.data]
        
        # Create training job record
        job_data = {
            "user_id": user_id,
            "status": "pending",
            "logs": f"Queued training with {len(res.data)} samples...",
        }
        job_res = client.table("training_jobs").insert(job_data).execute()
        job_id = job_res.data[0]["id"]
        
        # Queue async training task
        task = train_model_task.delay(
            texts=texts,
            labels=labels,
            user_id=user_id,
            job_id=job_id,
            epochs=epochs,
            batch_size=batch_size,
            learning_rate=learning_rate,
        )
        
        # Update job with task_id
        client.table("training_jobs").update({
            "celery_task_id": task.id,
            "status": "queued",
        }).eq("id", job_id).execute()
        
        return {
            "status": "queued",
            "message": f"Training job queued with {len(res.data)} samples",
            "job_id": job_id,
            "task_id": task.id,
            "epochs": epochs,
            "samples": len(res.data),
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to queue training: {e}")
        raise HTTPException(status_code=500, detail="Failed to queue training job")
```

**Step 2: Commit**

```bash
git add apps/api/routers/training.py
git commit -m "feat: update training router for async Celery jobs"
```

---

## Task 7: Update Main App to Include New Routers

**Files:**

- Modify: `apps/api/main.py`

**Step 1: Add classify router import and registration**

```python
"""SCALE API Gateway — FastAPI entry point."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apps.api.routers import forecast, health, ingestion, training, classify

app = FastAPI(
    title="SCALE API Gateway",
    description="Bridges the Python intelligence layer to the Next.js frontend.",
    version="0.2.0",
)

# CORS — allow the Next.js dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(health.router, prefix="/api/v1")
app.include_router(ingestion.router, prefix="/api/v1")
app.include_router(forecast.router, prefix="/api/v1")
app.include_router(training.router, prefix="/api/v1")
app.include_router(classify.router, prefix="/api/v1")
```

**Step 2: Commit**

```bash
git add apps/api/main.py
git commit -m "feat: register classification router in main app"
```

---

## Task 8: Create Dockerfile

**Files:**

- Create: `Dockerfile`

**Step 1: Write multi-stage Dockerfile**

```dockerfile
# Build stage
FROM python:3.11-slim as builder

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Runtime stage
FROM python:3.11-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /root/.local /root/.local

# Make sure scripts in .local are usable
ENV PATH=/root/.local/bin:$PATH

# Copy application code
COPY apps/ ./apps/
COPY packages/ ./packages/
COPY .env.local ./

# Create checkpoint directory
RUN mkdir -p /app/checkpoints

# Expose API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/api/v1/health')" || exit 1

# Default command
CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Step 2: Commit**

```bash
git add Dockerfile
git commit -m "feat: add Dockerfile with multi-stage build"
```

---

## Task 9: Create Docker Compose Configuration

**Files:**

- Create: `docker-compose.yml`

**Step 1: Write docker-compose.yml**

```yaml
version: "3.8"

services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 3

  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - REDIS_URL=redis://redis:6379/0
      - SUPABASE_URL=${SUPABASE_URL}
      - SUPABASE_ANON_KEY=${SUPABASE_ANON_KEY}
      - SUPABASE_SERVICE_KEY=${SUPABASE_SERVICE_KEY}
      - MODEL_CHECKPOINT_DIR=/app/checkpoints
    volumes:
      - ./checkpoints:/app/checkpoints
    depends_on:
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s

  worker:
    build: .
    command: celery -A apps.api.celery_app worker --loglevel=info --queues=training
    environment:
      - REDIS_URL=redis://redis:6379/0
      - SUPABASE_URL=${SUPABASE_URL}
      - SUPABASE_ANON_KEY=${SUPABASE_ANON_KEY}
      - SUPABASE_SERVICE_KEY=${SUPABASE_SERVICE_KEY}
      - MODEL_CHECKPOINT_DIR=/app/checkpoints
      - C_FORCE_ROOT=true  # Allow running as root in container
    volumes:
      - ./checkpoints:/app/checkpoints
    depends_on:
      redis:
        condition: service_healthy
    deploy:
      replicas: 2

  flower:
    image: mher/flower:latest
    ports:
      - "5555:5555"
    environment:
      - CELERY_BROKER_URL=redis://redis:6379/0
      - FLOWER_PORT=5555
    depends_on:
      - redis
      - worker

volumes:
  redis_data:
  checkpoints:
```

**Step 2: Commit**

```bash
git add docker-compose.yml
git commit -m "feat: add docker-compose with Redis, API, Celery workers, and Flower"
```

---

## Task 10: Create Startup Scripts

**Files:**

- Create: `scripts/start-local.sh`
- Create: `scripts/stop-local.sh`

**Step 1: Write start-local.sh**

```bash
#!/bin/bash
# Start SCALE API with training infrastructure locally

set -e

echo "🚀 Starting SCALE API Local Development Environment..."

# Check if .env.local exists
if [ ! -f .env.local ]; then
    echo "❌ .env.local not found. Copy from .env.example and configure."
    exit 1
fi

# Create checkpoint directory
mkdir -p checkpoints

# Build and start services
echo "📦 Building Docker images..."
docker-compose build

echo "🟢 Starting services..."
docker-compose up -d

echo "⏳ Waiting for services to be healthy..."
sleep 10

# Check health
echo "🏥 Checking service health..."
if curl -s http://localhost:8000/api/v1/health > /dev/null; then
    echo "✅ API is healthy"
else
    echo "⚠️ API health check failed. Check logs: docker-compose logs api"
fi

echo ""
echo "🎉 SCALE API is running!"
echo "   API: http://localhost:8000"
echo "   Flower (Celery UI): http://localhost:5555"
echo "   Health: http://localhost:8000/api/v1/health"
echo ""
echo "Useful commands:"
echo "   View logs: docker-compose logs -f"
echo "   Stop: ./scripts/stop-local.sh"
```

**Step 2: Write stop-local.sh**

```bash
#!/bin/bash
# Stop SCALE API local development environment

echo "🛑 Stopping SCALE API services..."

docker-compose down

echo "✅ Services stopped. Checkpoints preserved in ./checkpoints/"
```

**Step 3: Make scripts executable and commit**

```bash
chmod +x scripts/start-local.sh scripts/stop-local.sh
git add scripts/
git commit -m "feat: add convenience scripts for local development"
```

---

## Task 11: Update Health Check Endpoint

**Files:**

- Modify: `apps/api/routers/health.py`

**Step 1: Enhance health check with service status**

```python
"""Health check router with dependency checks."""

from fastapi import APIRouter
from apps.api.celery_app import celery_app

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    """
    Comprehensive health check including dependencies.
    
    Returns status of API, Redis, and Celery workers.
    """
    status = {
        "status": "healthy",
        "services": {
            "api": "up",
            "redis": "unknown",
            "celery": "unknown",
        },
    }
    
    # Check Redis
    try:
        celery_app.backend.client.ping()
        status["services"]["redis"] = "up"
    except Exception:
        status["services"]["redis"] = "down"
        status["status"] = "degraded"
    
    # Check Celery workers
    try:
        stats = celery_app.control.inspect().stats()
        if stats:
            status["services"]["celery"] = "up"
            status["services"]["workers"] = list(stats.keys())
        else:
            status["services"]["celery"] = "no_workers"
    except Exception:
        status["services"]["celery"] = "down"
    
    return status
```

**Step 2: Commit**

```bash
git add apps/api/routers/health.py
git commit -m "feat: enhance health check with Redis and Celery status"
```

---

## Task 12: Test the Complete Setup

**Step 1: Run tests**

```bash
# Run API tests
pytest apps/api/tests/ -v

# Run categorization tests  
pytest packages/categorization/tests/ -v
```

**Step 2: Test Docker Compose**

```bash
# Start services
./scripts/start-local.sh

# Wait for startup
sleep 15

# Test health endpoint
curl http://localhost:8000/api/v1/health

# Expected: {"status":"healthy","services":{"api":"up","redis":"up","celery":"up"}}

# Stop services
./scripts/stop-local.sh
```

**Step 3: Commit any final changes**

```bash
git commit -m "test: verify complete localhost deployment"
```

---

## Summary

This implementation plan provides:

1. **Containerization** - Dockerfile and docker-compose.yml
2. **Async Architecture** - Celery workers with Redis job queue
3. **Inference Endpoints** - `/classify` for using trained models
4. **Health Monitoring** - Enhanced health checks
5. **Local Dev Tools** - Convenient startup scripts

**Next Steps After Implementation:**

- Run `./scripts/start-local.sh` to start the full stack
- Access API at <http://localhost:8000>
- Monitor Celery at <http://localhost:5555>
- Test training via POST `/api/v1/train`
- Test inference via POST `/api/v1/classify`
