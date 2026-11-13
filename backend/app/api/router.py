from fastapi import APIRouter

from app.api.routes import admin, auth, catalog, conversations, lessons, progress, pronunciation, tts, vocab, writing

api_router = APIRouter(prefix="/api")
for module in (auth, catalog, lessons, vocab, writing, pronunciation, conversations, progress, tts, admin):
    api_router.include_router(module.router)
