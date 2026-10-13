from app.models.dictionaries import Tag


def _auth_headers(client, email: str, password: str) -> dict[str, str]:
    token = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_get_and_update_student_profile(client, db):
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "profile@example.com",
            "password": "secret123",
            "role": "student",
            "full_name": "Профиль Студент",
            "faculty": "ФИТ",
            "course": 2,
        },
    )
    tag = Tag(name="IT", slug="it")
    db.add(tag)
    db.commit()
    db.refresh(tag)

    headers = _auth_headers(client, "profile@example.com", "secret123")
    me = client.get("/api/v1/profiles/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["student_profile"]["faculty"] == "ФИТ"

    updated = client.patch(
        "/api/v1/profiles/me/student",
        headers=headers,
        json={
            "course": 3,
            "group_name": "ФИТ-301",
            "interest_tag_ids": [str(tag.id)],
        },
    )
    assert updated.status_code == 200
    profile = updated.json()["student_profile"]
    assert profile["course"] == 3
    assert profile["group_name"] == "ФИТ-301"
    assert len(profile["interests"]) == 1
    assert profile["interests"][0]["slug"] == "it"
