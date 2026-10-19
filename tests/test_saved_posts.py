def _register(client, **kwargs):
    return client.post("/api/v1/auth/register", json=kwargs)


def _headers(client, email: str, password: str) -> dict[str, str]:
    token = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _seed_staff_and_student(client):
    _register(
        client,
        email="staff@example.com",
        password="staff123",
        role="staff",
        full_name="Staff",
        department="Dean",
    )
    _register(
        client,
        email="fit@example.com",
        password="student123",
        role="student",
        full_name="FIT Student",
        faculty="ФИТ",
        course=3,
    )
    return (
        _headers(client, "staff@example.com", "staff123"),
        _headers(client, "fit@example.com", "student123"),
    )


def _create_post(client, staff_headers, category_id) -> str:
    response = client.post(
        "/api/v1/posts",
        headers=staff_headers,
        json={
            "title": "Для всех студентов",
            "body": "Общая новость",
            "category_id": str(category_id),
            "target_roles": ["student"],
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_feed_exposes_is_saved_flag(client, db):
    from app.models.dictionaries import Category

    category = Category(name="Новости", slug="news")
    db.add(category)
    db.commit()
    db.refresh(category)

    staff_headers, student_headers = _seed_staff_and_student(client)
    post_id = _create_post(client, staff_headers, category.id)

    feed = client.get("/api/v1/posts/feed", headers=student_headers).json()
    assert feed and feed[0]["is_saved"] is False

    saved = client.post(f"/api/v1/posts/{post_id}/save", headers=student_headers)
    assert saved.status_code == 200
    assert saved.json()["is_saved"] is True

    feed = client.get("/api/v1/posts/feed", headers=student_headers).json()
    assert feed[0]["is_saved"] is True


def test_save_is_idempotent_and_saved_list(client, db):
    from app.models.dictionaries import Category

    category = Category(name="Новости", slug="news")
    db.add(category)
    db.commit()
    db.refresh(category)

    staff_headers, student_headers = _seed_staff_and_student(client)
    post_id = _create_post(client, staff_headers, category.id)

    assert client.post(f"/api/v1/posts/{post_id}/save", headers=student_headers).status_code == 200
    assert client.post(f"/api/v1/posts/{post_id}/save", headers=student_headers).status_code == 200

    listing = client.get("/api/v1/posts/saved", headers=student_headers)
    assert listing.status_code == 200
    assert [item["id"] for item in listing.json()] == [post_id]
    assert listing.json()[0]["is_saved"] is True


def test_unsave_removes_from_saved_list(client, db):
    from app.models.dictionaries import Category

    category = Category(name="Новости", slug="news")
    db.add(category)
    db.commit()
    db.refresh(category)

    staff_headers, student_headers = _seed_staff_and_student(client)
    post_id = _create_post(client, staff_headers, category.id)

    client.post(f"/api/v1/posts/{post_id}/save", headers=student_headers)
    removed = client.delete(f"/api/v1/posts/{post_id}/save", headers=student_headers)
    assert removed.status_code == 200
    assert removed.json()["is_saved"] is False
    assert client.get("/api/v1/posts/saved", headers=student_headers).json() == []


def test_save_unknown_post_returns_404(client, db):
    _staff_headers, student_headers = _seed_staff_and_student(client)
    missing = "00000000-0000-0000-0000-000000000000"
    assert client.post(f"/api/v1/posts/{missing}/save", headers=student_headers).status_code == 404


def test_save_requires_authentication(client, db):
    from app.models.dictionaries import Category

    category = Category(name="Новости", slug="news")
    db.add(category)
    db.commit()
    db.refresh(category)
    staff_headers, _ = _seed_staff_and_student(client)
    post_id = _create_post(client, staff_headers, category.id)
    assert client.post(f"/api/v1/posts/{post_id}/save").status_code == 401
