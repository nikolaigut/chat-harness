

async def test_health(client):
    r = await client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


async def test_create_and_list_chats(client):
    r = await client.post("/api/chats", json={"name": "E2E Test", "agent": "devin"})
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "E2E Test"
    assert body["selected_agent"] == "devin"
    assert body["status"] == "running"
    chat_id = body["id"]

    r = await client.get("/api/chats")
    assert r.status_code == 200
    chats = r.json()
    assert any(c["id"] == chat_id for c in chats)


async def test_send_message_mock(client):
    r = await client.post("/api/chats", json={"name": "Mock Chat"})
    assert r.status_code == 200
    chat_id = r.json()["id"]

    r = await client.post(
        f"/api/chats/{chat_id}/message", json={"message": "Hello, agent!"}
    )
    assert r.status_code == 200
    body = r.json()
    assert "events" in body
    assert any(e["role"] == "assistant" for e in body["events"])

    r = await client.get(f"/api/chats/{chat_id}/events")
    assert r.status_code == 200
    events = r.json()
    assert any(e["role"] == "user" and e["content"] == "Hello, agent!" for e in events)
    assert any(e["role"] == "system" for e in events)
    assert any(e["role"] == "assistant" for e in events)


async def test_usage_and_browser_endpoints(client):
    r = await client.post("/api/chats", json={"name": "Usage Test"})
    assert r.status_code == 200
    chat_id = r.json()["id"]

    r = await client.get(f"/api/chats/{chat_id}/usage?agent=devin")
    assert r.status_code == 200
    body = r.json()
    assert body["agent"] == "devin"

    r = await client.get(f"/api/chats/{chat_id}/browser")
    assert r.status_code == 200
    assert "url" in r.json()


async def test_unknown_chat(client):
    r = await client.get("/api/chats/does-not-exist")
    assert r.status_code == 404
