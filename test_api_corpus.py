from tests.helpers import login


async def titles(client, headers, query=""):
    r = await client.get(f"/api/v1/corpus{query}", headers=headers)
    assert r.status_code == 200, r.text
    return {i["title"] for i in r.json()["items"]}


async def test_visibility_matrix(client):
    reader, reviewer = await login(client, "l1@t.mg"), await login(client, "r1@t.mg")
    other_reviewer = await login(client, "r2@t.mg")
    # lecteur de l'org 1 : public (toutes organisations) + restreint de son organisation, pas le privé
    assert await titles(client, reader) == {"Archive publique", "Archive restreinte", "Archive publique org2"}
    # relecteur de l'org 1 : voit aussi le privé de son organisation
    assert await titles(client, reviewer) == {"Archive publique", "Archive restreinte", "Archive privée", "Archive publique org2"}
    # relecteur de l'org 2 : ne voit ni le restreint ni le privé de l'org 1
    assert await titles(client, other_reviewer) == {"Archive publique", "Archive publique org2", "Archive restreinte org2"}


async def test_detail_respects_visibility(client, ids):
    reader, other = await login(client, "l1@t.mg"), await login(client, "r2@t.mg")
    assert (await client.get(f"/api/v1/corpus/{ids['k_pub']}", headers=other)).status_code == 200      # public d'une autre org
    assert (await client.get(f"/api/v1/corpus/{ids['k_res']}", headers=other)).status_code == 404      # restreint d'une autre org
    assert (await client.get(f"/api/v1/corpus/{ids['k_priv']}", headers=reader)).status_code == 404    # privé, lecteur
    d = (await client.get(f"/api/v1/corpus/{ids['k_pub']}", headers=reader)).json()
    assert d["source"]["license"] == "CC BY-SA 4.0" and d["editable"] is False and d["revisions_count"] == 0


async def test_filters_and_search(client):
    h = await login(client, "r1@t.mg")
    assert await titles(client, h, "?genre=hira_gasy") == {"Archive restreinte"}
    assert await titles(client, h, "?region=imerina") == {"Archive publique"}                      # insensible à la casse
    assert await titles(client, h, "?access_level=private") == {"Archive privée"}
    assert await titles(client, h, "?q=privée") == {"Archive privée"}
    assert await titles(client, h, "?q=zzzintrouvable") == set()
    assert (await client.get("/api/v1/corpus?genre=poeme", headers=h)).status_code == 422
    page = (await client.get("/api/v1/corpus?size=2&page=1", headers=h)).json()
    assert page["total"] == 4 and len(page["items"]) == 2 and page["items"][0]["excerpt"]


async def test_search_for_percent_sign_is_literal(client):
    h = await login(client, "r1@t.mg")
    assert await titles(client, h, "?q=%25") == set()          # « % » est cherché tel quel, ce n'est pas un joker


async def test_patch_creates_revision_bumps_version_and_changes_search(client, ids):
    h = await login(client, "r1@t.mg")
    new = "Texte corrigé par le relecteur, avec un mot unique : fanitsiana."
    d = (await client.patch(f"/api/v1/corpus/{ids['k_res']}", headers=h, json={"content": new})).json()
    assert d["content"] == new and d["version"] == 2 and d["revisions_count"] == 1 and d["editable"] is True
    assert await titles(client, h, "?q=fanitsiana") == {"Archive restreinte"}                      # la révision est cherchable
    revs = (await client.get(f"/api/v1/corpus/{ids['k_res']}/revisions", headers=h)).json()
    assert len(revs) == 1 and revs[0]["author"] == "r1@t.mg"
    again = (await client.patch(f"/api/v1/corpus/{ids['k_res']}", headers=h, json={"content": new})).json()
    assert again["version"] == 2                                                                  # même contenu : pas de nouvelle révision


async def test_patch_metadata_and_validation(client, ids):
    h = await login(client, "r1@t.mg")
    d = (await client.patch(f"/api/v1/corpus/{ids['k_res']}", headers=h, json={"genre": "tantara", "access_level": "public"})).json()
    assert d["genre"] == "tantara" and d["access_level"] == "public" and d["version"] == 1
    assert (await client.patch(f"/api/v1/corpus/{ids['k_res']}", headers=h, json={})).status_code == 400
    assert (await client.patch(f"/api/v1/corpus/{ids['k_res']}", headers=h, json={"access_level": "secret"})).status_code == 422


async def test_editing_is_limited_to_own_organisation_and_reviewers(client, ids):
    reader, other = await login(client, "l1@t.mg"), await login(client, "r2@t.mg")
    new = {"content": "Tentative de modification par une autre organisation, qui doit échouer."}
    assert (await client.patch(f"/api/v1/corpus/{ids['k_pub']}", headers=other, json=new)).status_code == 403     # visible mais pas à lui
    assert (await client.patch(f"/api/v1/corpus/{ids['k_pub']}", headers=reader, json=new)).status_code == 403    # rôle insuffisant
    assert (await client.get(f"/api/v1/corpus/{ids['k_pub']}/revisions", headers=other)).status_code == 403
    assert (await client.patch(f"/api/v1/corpus/{ids['k_res']}", headers=other, json=new)).status_code == 404     # invisible
