import uuid

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from tests.conftest import ADMIN

H = ADMIN


def _convert(api: TestClient, name: str) -> dict:  # type: ignore[type-arg]
    return api.post("/api/names/convert", json={"name": name}).json()  # type: ignore[no-any-return]


# --- historial -------------------------------------------------------------------------------


def test_history_lists_newest_first_and_paginates(api: TestClient) -> None:
    for n in ("Hist Uno", "Hist Dos", "Hist Tres"):
        _convert(api, n)
    page = api.get("/api/requests", params={"q": "hist", "page_size": 2}).json()
    assert page["total"] == 3 and len(page["items"]) == 2
    assert page["items"][0]["input_name"] == "Hist Tres"
    assert page["items"][0]["ja_text"] and page["items"][0]["zh_text"]
    second = api.get("/api/requests", params={"q": "hist", "page_size": 2, "page": 2}).json()
    assert [i["input_name"] for i in second["items"]] == ["Hist Uno"]


def test_history_get_one_and_404(api: TestClient) -> None:
    created = _convert(api, "Carlos")
    got = api.get(f"/api/requests/{created['request_id']}").json()
    assert got == created
    r = api.get(f"/api/requests/{uuid.uuid4()}")
    assert (r.status_code, r.json()["error"]["code"]) == (404, "request_not_found")
    assert (
        api.get("/api/requests", params={"page": 0}).json()["error"]["code"] == "validation_error"
    )


# --- autenticación ---------------------------------------------------------------------------


def test_admin_requires_token(api: TestClient) -> None:
    for headers in ({}, {"X-Admin-Token": "otro"}):
        r = api.get("/api/admin/names", headers=headers)
        assert (r.status_code, r.json()["error"]["code"]) == (401, "unauthorized")
    assert api.get("/api/admin/names", headers=H).status_code == 200


def test_admin_and_robot_are_open_when_no_token_is_configured(
    api: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "admin_token", "")
    assert api.get("/api/admin/names").status_code == 200
    assert api.get("/api/robot/config").status_code == 200
    monkeypatch.setattr(settings, "admin_token", "otro")  # y con token configurado, se exige
    assert api.get("/api/admin/names").status_code == 401


# --- diccionario: añadir un nombre y verlo verificado en la conversión -----------------------

NEW_NAME = {
    "display_name": "Zacarías",
    "gender": "m",
    "transliterations": [
        {"script": "zh", "text": "安娜", "reading": "ān nà"},
        {"script": "ja", "text": "サカリアス", "reading": "sakariasu"},
    ],
}


def test_new_name_shows_up_verified_in_conversion(api: TestClient) -> None:
    before = _convert(api, "Zacarías")
    assert before["zh"][0]["source"] == "algorithm" and before["zh"][0]["verified"] is False

    r = api.post("/api/admin/names", json=NEW_NAME, headers=H)
    assert r.status_code == 201
    created = r.json()
    assert created["name_es"] == "zacarias" and created["verified"] is True
    assert created["missing_glyphs"] == []

    after = _convert(api, "zacarias")
    assert after["zh"][0] == {
        **after["zh"][0],
        "text": "安娜",
        "source": "dictionary",
        "verified": True,
    }
    assert after["ja"][0]["text"] == "サカリアス" and after["ja"][0]["verified"] is True
    assert after["ja"][0]["source"] == "dictionary"


def test_name_crud_verify_and_duplicates(api: TestClient) -> None:
    body = {**NEW_NAME, "display_name": "Ludovico", "verified": False}
    created = api.post("/api/admin/names", json=body, headers=H).json()
    nid = created["id"]
    assert created["verified"] is False
    assert (
        api.post("/api/admin/names", json=body, headers=H).json()["error"]["code"] == "name_exists"
    )

    ver = api.post(f"/api/admin/names/{nid}/verify", json={"verified": True}, headers=H).json()
    assert ver["verified"] and all(t["verified"] for t in ver["transliterations"])

    upd = {**body, "display_name": "Ludovico", "gender": "f", "verified": True}
    upd["transliterations"] = [{"script": "zh", "text": "安", "reading": "ān"}]
    out = api.put(f"/api/admin/names/{nid}", json=upd, headers=H).json()
    assert out["gender"] == "f" and len(out["transliterations"]) == 1

    listed = api.get("/api/admin/names", params={"q": "ludov", "verified": True}, headers=H).json()
    assert [i["id"] for i in listed["items"]] == [nid]
    assert api.delete(f"/api/admin/names/{nid}", headers=H).status_code == 204
    assert (
        api.delete(f"/api/admin/names/{nid}", headers=H).json()["error"]["code"] == "name_not_found"
    )


def test_name_validation_and_missing_glyph_warning(api: TestClient) -> None:
    for bad in ("Ana María", "Ana123", ""):
        r = api.post("/api/admin/names", json={**NEW_NAME, "display_name": bad}, headers=H)
        assert r.status_code == 422, bad
    rare = {
        **NEW_NAME,
        "display_name": "Raro",
        "transliterations": [{"script": "zh", "text": "龘", "reading": "dá"}],
    }
    out = api.post("/api/admin/names", json=rare, headers=H).json()
    assert out["missing_glyphs"] == ["龘"]


# --- tabla silábica --------------------------------------------------------------------------

SYL = {"script": "zh", "syllable_es": "zu", "output": "祖", "reading": "zǔ", "meaning": "ancestro"}


def test_syllable_crud(api: TestClient) -> None:
    row = api.post("/api/admin/syllables", json=SYL, headers=H)
    assert row.status_code == 201
    sid = row.json()["id"]
    assert (
        api.post("/api/admin/syllables", json=SYL, headers=H).json()["error"]["code"]
        == "syllable_exists"
    )

    changed = {**SYL, "connotation": "avoid", "score": 5}
    out = api.put(f"/api/admin/syllables/{sid}", json=changed, headers=H).json()
    assert out["connotation"] == "avoid" and out["score"] == 5

    found = api.get(
        "/api/admin/syllables",
        params={"script": "zh", "q": "zu", "connotation": "avoid"},
        headers=H,
    ).json()
    assert [i["id"] for i in found["items"]] == [sid]
    assert api.delete(f"/api/admin/syllables/{sid}", headers=H).status_code == 204
    assert api.put(f"/api/admin/syllables/{sid}", json=SYL, headers=H).status_code == 404


def test_syllable_validation(api: TestClient) -> None:
    bad = api.post("/api/admin/syllables", json={**SYL, "syllable_es": "Zu!"}, headers=H)
    assert bad.json()["error"]["code"] == "validation_error"
    bad = api.post("/api/admin/syllables", json={**SYL, "score": 101}, headers=H)
    assert bad.status_code == 422


def test_avoid_edit_takes_effect_in_conversion(api: TestClient) -> None:
    # marcar como `avoid` el carácter preferido de «ta» cambia el resultado del algoritmo
    top = _convert(api, "Tabo")["zh"][0]["text"]
    assert top.startswith("塔")
    rows = api.get("/api/admin/syllables", params={"script": "zh", "q": "塔"}, headers=H).json()[
        "items"
    ]
    row = rows[0]
    body = {
        k: row[k]
        for k in ("script", "syllable_es", "output", "reading", "meaning", "gender_hint", "score")
    }
    api.put(f"/api/admin/syllables/{row['id']}", json={**body, "connotation": "avoid"}, headers=H)
    assert "塔" not in "".join(o["text"] for o in _convert(api, "Tabo")["zh"])
    api.put(
        f"/api/admin/syllables/{row['id']}",
        json={**body, "connotation": row["connotation"]},
        headers=H,
    )


# --- pendientes de revisión ------------------------------------------------------------------


def test_pending_lists_unknown_names_and_promotion_clears_them(api: TestClient) -> None:
    _convert(api, "Pendiente")
    _convert(api, "Carlos")  # está en el diccionario: no es pendiente
    items = api.get("/api/admin/pending", headers=H).json()
    names = [i["input_name"] for i in items]
    assert "Pendiente" in names and "Carlos" not in names
    item = next(i for i in items if i["input_name"] == "Pendiente")
    assert item["zh"]["text"] and item["ja"]["romaji"]

    body = {
        "display_name": "Pendiente",
        "transliterations": [
            {"script": "zh", "text": item["zh"]["text"], "reading": item["zh"]["pinyin"]},
            {"script": "ja", "text": item["ja"]["text"], "reading": item["ja"]["romaji"]},
        ],
    }
    assert api.post("/api/admin/names", json=body, headers=H).status_code == 201
    after = [i["input_name"] for i in api.get("/api/admin/pending", headers=H).json()]
    assert "Pendiente" not in after
