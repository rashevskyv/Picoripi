"""Tests for Picoripi Companion Server API and StorageManager."""
from pathlib import Path
import pytest

pytest.importorskip("fastapi")
from starlette.testclient import TestClient

from companion.server.main import create_app
from companion.server.models import GlossaryEntryUpdate
from companion.server.storage import StorageManager, sanitize_project_name


@pytest.fixture
def temp_companion_env(tmp_path: Path):
    data_dir = tmp_path / "companion_data"
    data_dir.mkdir()
    auth_token = "secret_pin_123"
    storage = StorageManager(data_dir)
    app = create_app(data_dir=data_dir, auth_token=auth_token)
    client = TestClient(app)
    return storage, client, auth_token


def test_sanitize_project_name():
    assert sanitize_project_name("Zelda: Twilight Princess") == "Zelda__Twilight_Princess"
    assert sanitize_project_name("  TP_UA  ") == "TP_UA"
    assert sanitize_project_name("   ") == "default_project"


def test_storage_manager_lifecycle(tmp_path: Path):
    storage = StorageManager(tmp_path)
    glossary_data = [
        {
            "original": "Master Sword",
            "translation": "Вищий меч",
            "section": "Items",
            "status": "confirmed",
            "translation_variants": [{"translation": "Вищий меч", "rationale": "Canon"}],
        },
        {
            "original": "Green Chu Jelly",
            "translation": "",
            "section": "Items",
            "status": "translated",
            "translation_variants": [
                {"translation": "Залізе зеленого чу", "rationale": "AI option 1"},
                {"translation": "Слиз зеленого чу", "rationale": "AI option 2"},
            ],
        },
    ]
    occurrences_data = {
        "Master Sword": [{"line_text": "Draw the Master Sword!", "kind": "spoken", "ref_text": "Вытащи Высший меч!"}]
    }

    # Save project
    summary = storage.save_project("Zelda TP", glossary_data, occurrences=occurrences_data)
    assert summary.name == "Zelda TP"
    assert summary.total_terms == 2
    assert summary.confirmed_terms == 1
    assert summary.needs_review_terms == 1

    # Verify retrieval
    loaded = storage.get_glossary("Zelda TP")
    assert len(loaded) == 2
    assert loaded[0]["original"] == "Master Sword"

    occs = storage.get_occurrences("Zelda TP", "Master Sword")
    assert len(occs) == 1
    assert occs[0]["ref_text"] == "Вытащи Высший меч!"

    # Update entry
    update = GlossaryEntryUpdate(
        original="Green Chu Jelly",
        translation="Слиз зеленого чу",
        status="confirmed",
        user_notes="Confirmed via mobile",
    )
    updated = storage.update_entry("Zelda TP", update)
    assert updated is not None
    assert updated["translation"] == "Слиз зеленого чу"
    assert updated["status"] == "confirmed"
    assert updated["user_notes"] == "Confirmed via mobile"

    # Verify backup exists after update
    project_dir = tmp_path / "projects" / "Zelda_TP"
    assert (project_dir / "glossary.json.bak").exists()

    # Re-check stats
    projects = storage.list_projects()
    assert len(projects) == 1
    assert projects[0].confirmed_terms == 2
    assert projects[0].needs_review_terms == 0


def test_api_health_and_auth(temp_companion_env):
    storage, client, token = temp_companion_env

    # Health
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

    # Login failure
    r = client.post("/api/auth/login", json={"token": "wrong_pin"})
    assert r.status_code == 401

    # Login success
    r = client.post("/api/auth/login", json={"token": token})
    assert r.status_code == 200
    assert r.json()["success"] is True

    # Unauthorized requests
    r = client.get("/api/projects")
    assert r.status_code == 401


def test_api_sync_flow_and_filtering(temp_companion_env):
    storage, client, token = temp_companion_env
    auth_header = {"Authorization": f"Bearer {token}"}

    sample_glossary = [
        {
            "original": "Link",
            "translation": "Лінк",
            "section": "Characters",
            "status": "confirmed",
            "translation_variants": [
                {"translation": "Лінк", "rationale": "Canon"},
                {"translation": "Линк", "rationale": "Alternative"},
            ],
            "notes": "Hero of Time",
        },
        {
            "original": "Midna",
            "translation": "Мідна",
            "section": "Characters",
            "status": "translated",
            "translation_variants": [{"translation": "Мідна", "rationale": "Phonetic"}],
            "notes": "Twilight Princess",
        },
        {
            "original": "Ordon Village",
            "translation": "Село Ордон",
            "section": "Locations",
            "status": "confirmed",
            "notes": "Starting village",
        },
    ]

    sample_occurrences = {
        "Midna": [{"line_text": "Hey, Link! Look over here!", "kind": "spoken", "ref_text": "Эй, Линк!"}]
    }

    # 1. Push project
    push_payload = {
        "project_name": "Twilight Princess",
        "glossary": sample_glossary,
        "occurrences": sample_occurrences,
    }
    r = client.post("/api/sync/push", json=push_payload, headers=auth_header)
    assert r.status_code == 200
    assert r.json()["total_terms"] == 3

    # 2. List projects
    r = client.get("/api/projects", headers=auth_header)
    assert r.status_code == 200
    projects = r.json()
    assert len(projects) == 1
    assert projects[0]["name"] == "Twilight Princess"
    assert projects[0]["total_terms"] == 3
    assert projects[0]["needs_review_terms"] == 1

    # 3. Filter glossary by category
    r = client.get("/api/glossary?project=Twilight+Princess&category=Locations", headers=auth_header)
    assert r.status_code == 200
    res = r.json()
    assert len(res["entries"]) == 1
    assert res["entries"][0]["original"] == "Ordon Village"
    assert "Characters" in res["categories"]
    assert "Locations" in res["categories"]

    # 4. Filter by needs_review
    r = client.get("/api/glossary?project=Twilight+Princess&needs_review=true", headers=auth_header)
    assert r.status_code == 200
    res = r.json()
    assert len(res["entries"]) == 1
    assert res["entries"][0]["original"] == "Midna"

    # 5. Search
    r = client.get("/api/glossary?project=Twilight+Princess&search=hero", headers=auth_header)
    assert r.status_code == 200
    res = r.json()
    assert len(res["entries"]) == 1
    assert res["entries"][0]["original"] == "Link"

    # 6. Get term detail with occurrences
    r = client.get("/api/glossary/entry?project=Twilight+Princess&term=Midna", headers=auth_header)
    assert r.status_code == 200
    detail = r.json()
    assert detail["entry"]["original"] == "Midna"
    assert len(detail["occurrences"]) == 1
    assert detail["occurrences"][0]["ref_text"] == "Эй, Линк!"

    # 7. Update term (confirm on mobile)
    update_payload = {
        "original": "Midna",
        "translation": "Мідна",
        "status": "confirmed",
        "user_notes": "Approved from mobile test",
    }
    r = client.put("/api/glossary/entry?project=Twilight+Princess", json=update_payload, headers=auth_header)
    assert r.status_code == 200
    assert r.json()["entry"]["status"] == "confirmed"
    assert r.json()["entry"]["user_notes"] == "Approved from mobile test"

    # 8. Pull updated project
    r = client.get("/api/sync/pull?project=Twilight+Princess", headers=auth_header)
    assert r.status_code == 200
    pulled = r.json()
    assert pulled["total_terms"] == 3
    midna_entry = next(e for e in pulled["glossary"] if e["original"] == "Midna")
    assert midna_entry["status"] == "confirmed"
    assert midna_entry["user_notes"] == "Approved from mobile test"

    # 9. Verify that after Midna is confirmed, needs_review filter returns 0 entries
    r = client.get("/api/glossary?project=Twilight+Princess&needs_review=true", headers=auth_header)
    assert r.status_code == 200
    res = r.json()
    assert len(res["entries"]) == 0
    assert res["needs_review_count"] == 0
