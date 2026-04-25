from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from auth.database import SessionLocal, init_db
from auth.routers import auth, config, users
from auth.services import seed_defaults


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    with SessionLocal() as db:
        seed_defaults(db)
    yield


app = FastAPI(
    title="Auth",
    version="0.2.0",
    description="Servico de autenticacao OTP + JWT. Fonte de verdade para identidade e roles.",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url=None,
    openapi_tags=[
        {"name": "auth", "description": "Autenticacao: check, register, OTP, login, refresh, discovery"},
        {"name": "users", "description": "Usuarios: roles, transicoes"},
        {"name": "config", "description": "Configuracao do servico"},
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(config.router)
app.include_router(auth.router)
app.include_router(users.router)
