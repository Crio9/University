def test_register_and_login_student(client, db):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "new.student@example.com",
            "password": "secret123",
            "role": "student",
            "full_name": "Новый Студент",
            "faculty": "ФИТ",
            "course": 2,
            "group_name": "ФИТ-201",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "new.student@example.com"
    assert body["role"] == "student"

    login = client.post(
        "/api/v1/auth/login",
        data={"username": "new.student@example.com", "password": "secret123"},
    )
    assert login.status_code == 200
    assert "access_token" in login.json()


def test_register_duplicate_email(client):
    payload = {
        "email": "dup@example.com",
        "password": "secret123",
        "role": "student",
        "full_name": "Dup",
        "faculty": "ФИТ",
        "course": 1,
    }
    assert client.post("/api/v1/auth/register", json=payload).status_code == 201
    assert client.post("/api/v1/auth/register", json=payload).status_code == 400
