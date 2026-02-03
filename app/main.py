from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager  # ✅ correct import

from app.auth.routes import router as auth_router
from app.chat.routes import router as chat_router
from app.db.session import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 🔹 Startup
    init_db()
    yield
    # 🔹 Shutdown (nothing yet)


app = FastAPI(
    title="Health Bot",
    lifespan=lifespan,   # ✅ THIS WAS MISSING
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(chat_router)


@app.get("/")
def health_check():
    return {"status": "running"}
