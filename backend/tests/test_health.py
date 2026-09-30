from fastapi.testclient import TestClient

from app.main import app

# TestClient wraps our FastAPI app so we can send HTTP requests
# in tests WITHOUT actually starting a server on a port.
client = TestClient(app)


def test_health_returns_ok():
    # Send a real GET request through the test client
    response = client.get("/health")

    # The server must reply with HTTP 200
    assert response.status_code == 200

    # The body must be exactly {"status": "ok"}
    assert response.json() == {"status": "ok"}
