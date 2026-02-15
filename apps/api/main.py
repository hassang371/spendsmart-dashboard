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
