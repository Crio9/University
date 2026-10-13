from app.models.dictionaries import Category, Tag


def _register(client, **kwargs):
    return client.post("/api/v1/auth/register", json=kwargs)


def _login_headers(client, email: str, password: str) -> dict[str, str]:
    token = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_feed_returns_only_matching_posts(client, db):
    category = Category(name="Возможности", slug="opportunities")
    tag = Tag(name="IT", slug="it")
    db.add_all([category, tag])
    db.commit()
    db.refresh(category)
    db.refresh(tag)

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

    staff_headers = _login_headers(client, "staff@example.com", "staff123")
    student_headers = _login_headers(client, "fit@example.com", "student123")

    matching = client.post(
        "/api/v1/posts",
        headers=staff_headers,
        json={
            "title": "Для ФИТ 3 курса",
            "body": "Стажировка",
            "category_id": str(category.id),
            "tag_ids": [str(tag.id)],
            "target_roles": ["student"],
            "target_faculties": ["ФИТ"],
            "target_courses": [3],
        },
    )
    assert matching.status_code == 201

    other = client.post(
        "/api/v1/posts",
        headers=staff_headers,
        json={
            "title": "Только Юрфак",
            "body": "Другое",
            "category_id": str(category.id),
            "tag_ids": [],
            "target_roles": ["student"],
            "target_faculties": ["Юрфак"],
            "target_courses": [],
        },
    )
    assert other.status_code == 201

    feed = client.get("/api/v1/posts/feed", headers=student_headers)
    assert feed.status_code == 200
    titles = [item["title"] for item in feed.json()]
    assert "Для ФИТ 3 курса" in titles
    assert "Только Юрфак" not in titles


def test_list_dictionaries(client, db):
    db.add_all(
        [
            Category(name="Новости", slug="news"),
            Tag(name="Наука", slug="science"),
        ]
    )
    db.commit()

    tags = client.get("/api/v1/tags")
    categories = client.get("/api/v1/categories")
    assert tags.status_code == 200
    assert categories.status_code == 200
    assert any(item["slug"] == "science" for item in tags.json())
    assert any(item["slug"] == "news" for item in categories.json())
