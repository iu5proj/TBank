"""Tests for the FastAPI application and health endpoint."""


class TestHealthEndpoint:
    """Test basic application health."""

    def test_health_returns_ok(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "zarabotok-backend"

    def test_docs_accessible(self, client):
        response = client.get("/docs")
        assert response.status_code == 200

    def test_openapi_schema_accessible(self, client):
        response = client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()
        assert schema["info"]["title"] == "Заработок API"
        assert schema["info"]["version"] == "0.1.0"

    def test_openapi_has_analyze_endpoint(self, client):
        response = client.get("/openapi.json")
        paths = response.json()["paths"]
        assert "/api/v1/analyze" in paths
        assert "/api/v1/parser/refresh" in paths

    def test_analyze_validation_error_contract(self, client):
        response = client.post("/api/v1/analyze", json={"profile": {"title": ""}})
        assert response.status_code == 422
        data = response.json()
        assert data["status"] == "error"
        assert data["code"] == "VALIDATION_ERROR"

    def test_openapi_has_resume_endpoints(self, client):
        response = client.get("/openapi.json")
        paths = response.json()["paths"]
        assert "/api/v1/resumes" in paths
        assert "/api/v1/resumes/{resume_id}" in paths

    def test_openapi_does_not_expose_legacy_estimates(self, client):
        response = client.get("/openapi.json")
        paths = response.json()["paths"]
        assert "/api/v1/estimates" not in paths
