from contextlib import asynccontextmanager
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.database import init_db
from backend.routers import auth_router, sessions, templates, upload
from backend.routers import suggest
from backend.routers import stress_test


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    from backend.database import SessionLocal
    from backend.models.template import Template
    db = SessionLocal()
    try:
        default = db.query(Template).filter(Template.is_default == True).first()
        if not default:
            from backend.engine.default_personas import LEMNISCA_DEFAULT_AGENTS
            db.add(Template(
                name="Lemnisca Default",
                description="6-agent fermentation brainstorming panel",
                agents=LEMNISCA_DEFAULT_AGENTS,
                settings={
                    "max_rounds": 50,
                    "temperature": 0.70,
                    "gate_start_round": 10,
                    "overseer_interval": 10,
                    "min_rounds_before_convergence": 45,
                    "prd_panel_rounds": 10,
                },
                mode="product",
                is_default=True,
            ))
            db.commit()
    finally:
        db.close()
    yield


app = FastAPI(title="Symposium", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router)
app.include_router(sessions.router)
app.include_router(templates.router)
app.include_router(upload.router)
app.include_router(suggest.router)
app.include_router(stress_test.router)
