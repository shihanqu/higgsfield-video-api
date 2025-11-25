from fastapi import APIRouter

from .auth.router import router as auth_router
from .higgsfield.router import router as higgsfield_router
from .restart import router as restart_router
from .results import router as results_router

api_router = APIRouter(prefix="/api")

api_router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
api_router.include_router(higgsfield_router, prefix="/higgsfield", tags=["Higgsfield"])
api_router.include_router(results_router, prefix="", tags=["Results"])
api_router.include_router(restart_router, prefix="", tags=["Task Management"])
