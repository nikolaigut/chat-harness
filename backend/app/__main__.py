import os

import uvicorn

if __name__ == "__main__":
    # uvloop handles subprocesses incorrectly inside uvicorn's reloader worker,
    # causing podman run -d to hang. Use the asyncio loop by default.
    uvicorn.run(
        "app.main:app",
        host=os.environ.get("UVICORN_HOST", "0.0.0.0"),
        port=int(os.environ.get("UVICORN_PORT", "8000")),
        reload=os.environ.get("UVICORN_RELOAD", "").lower() == "true",
        loop=os.environ.get("UVICORN_LOOP", "asyncio"),
    )
