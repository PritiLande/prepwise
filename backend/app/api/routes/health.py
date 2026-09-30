from fastapi import APIRouter

# APIRouter is like a mini-app: we define routes here and plug them into main.py later.
router = APIRouter()


@router.get("/health")
def health_check():
    # This endpoint exists so we can confirm the server is running.
    # Load-balancers and CI pipelines call it to verify the service is alive.
    return {"status": "ok"}
