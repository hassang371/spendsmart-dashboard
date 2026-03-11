from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.core.problem_detail import ProblemDetail, problem_response

app = FastAPI()


@app.get("/error/dict")
def route_dict_error():
    return problem_response(
        status_code=400,
        title="Bad Request",
        detail="Missing parameters",
        type="https://example.com/errors/bad-request",
        instance="/error/dict",
    )


@app.get("/error/pydantic")
def route_pydantic_error():
    pd = ProblemDetail(
        type="https://example.com/errors/invalid",
        title="Invalid Entity",
        status=422,
        detail="Data validation failed",
        instance="/error/pydantic",
        errors=[{"field": "email", "msg": "invalid format"}],
    )
    return problem_response(
        status_code=pd.status,
        title=pd.title,
        detail=pd.detail,
        type=pd.type,
        instance=pd.instance,
        errors=pd.errors,
    )


client = TestClient(app)


def test_problem_response_dict():
    response = client.get("/error/dict")
    assert response.status_code == 400
    assert response.headers["content-type"] == "application/problem+json"

    data = response.json()
    assert data["type"] == "https://example.com/errors/bad-request"
    assert data["title"] == "Bad Request"
    assert data["status"] == 400
    assert data["detail"] == "Missing parameters"
    assert data["instance"] == "/error/dict"


def test_problem_response_pydantic_schema():
    response = client.get("/error/pydantic")
    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"

    data = response.json()
    assert data["type"] == "https://example.com/errors/invalid"
    assert data["title"] == "Invalid Entity"
    assert data["status"] == 422
    assert data["detail"] == "Data validation failed"
    assert data["instance"] == "/error/pydantic"
    assert data["errors"] == [{"field": "email", "msg": "invalid format"}]
    assert "request_id" not in data or data["request_id"] is None
