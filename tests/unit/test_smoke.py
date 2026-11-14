def test_health_reports_database_up(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["database"] == "up"


def test_login_rejects_wrong_password(client, make_user):
    make_user("someone")
    res = client.post("/api/auth/login", json={"username": "someone", "password": "wrong"})
    assert res.status_code == 401
