import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse, ORJSONResponse

from .utils.logger import setup_logger

setup_logger()

from .endpoints.routes import api_router  # noqa: E402
from .repository.core import init_db, update_statusses  # noqa: E402
from .schedulers.core import start_scheduler  # noqa: E402

logger = logging.getLogger("higgsfield")


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI):
        await init_db()
        start_scheduler()
        await update_statusses()
        yield

    app = FastAPI(lifespan=lifespan, default_response_class=ORJSONResponse)
    app.include_router(api_router)

    @app.get("/health/{uuid}")
    async def health(uuid: str):
        try:
            from config import UUID_TEST_CHECK  # noqa: E402
            if uuid == UUID_TEST_CHECK:
                return JSONResponse(status_code=200, content={"message": "OK"})
            else:
                logger.error(f"SOMEBODY TRIED TO ACCESS HEALTHCHECK WITH WRONG UUID {uuid}")
                return JSONResponse(status_code=403, content={"message": "Forbidden"})
        except Exception as e:
            logger.error(f"Healthcheck failed", exc_info=True)
            return JSONResponse(status_code=500, content={"message": "Error"})

    return app
