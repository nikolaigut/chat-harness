from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.db import get_database
from app.services.chat_service import ChatService

router = APIRouter(prefix="/chats", tags=["chats"])


class ChatCreate(BaseModel):
    name: str
    agent: str | None = None


class ChatMessage(BaseModel):
    message: str
    agent: str | None = None


@router.post("", response_model=dict)
async def create_chat(body: ChatCreate):
    service = ChatService()
    chat = await service.create_chat(body.name, body.agent)
    return {
        "id": chat.id,
        "name": chat.name,
        "selected_agent": chat.selected_agent,
        "status": chat.status,
        "container_id": chat.container_id,
    }


@router.get("")
async def list_chats():
    db = get_database()
    chats = await db.list_chats()
    return [
        {
            "id": c.id,
            "name": c.name,
            "selected_agent": c.selected_agent,
            "status": c.status,
            "container_id": c.container_id,
            "last_active_at": c.last_active_at,
        }
        for c in chats
    ]


@router.get("/{chat_id}")
async def get_chat(chat_id: str):
    db = get_database()
    chat = await db.get_chat(chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    return {
        "id": chat.id,
        "name": chat.name,
        "selected_agent": chat.selected_agent,
        "status": chat.status,
        "container_id": chat.container_id,
        "workspace_dir": chat.workspace_dir,
        "last_active_at": chat.last_active_at,
    }


@router.get("/{chat_id}/events")
async def get_chat_events(chat_id: str):
    db = get_database()
    events = await db.get_events(chat_id)
    return [
        {
            "id": e.id,
            "role": e.role,
            "content": e.content,
            "reasoning": e.reasoning,
            "tool_calls": e.tool_calls,
            "browser_action": e.browser_action,
            "created_at": e.created_at,
        }
        for e in events
    ]


@router.post("/{chat_id}/message")
async def send_message(chat_id: str, body: ChatMessage):
    service = ChatService()
    chat = await service.get_chat(chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    events = []
    async for event in service.send_message(chat_id, body.message, body.agent):
        events.append(
            {
                "id": event.id,
                "role": event.role,
                "content": event.content,
                "reasoning": event.reasoning,
                "tool_calls": event.tool_calls,
                "browser_action": event.browser_action,
                "created_at": event.created_at,
            }
        )
    return {"events": events}


@router.post("/{chat_id}/snapshot")
async def snapshot_chat(chat_id: str):
    service = ChatService()
    await service.stop_inactive()
    return {"ok": True}


@router.get("/{chat_id}/browser")
async def get_browser_url(chat_id: str):
    from app.podman import PodmanManager

    chat = await get_database().get_chat(chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    if not chat.container_id:
        return {"url": None}
    pm = PodmanManager()
    port = await pm.get_browser_port(chat.container_id)
    if not port:
        return {"url": None}
    return {
        "url": f"http://localhost:{port}/vnc.html?autoconnect=true&resize=scale",
    }


@router.get("/{chat_id}/usage")
async def get_usage(chat_id: str, agent: str = Query(default="devin")):
    from app.agents.router import AgentRouter

    chat = await get_database().get_chat(chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    if not chat.container_id:
        return {"agent": agent, "remaining": None, "total": None, "model": None}
    router = AgentRouter(chat.container_id)
    usage = await router.check_quota(agent)
    return {
        "agent": agent,
        "remaining": usage.remaining,
        "total": usage.total,
        "model": usage.model,
    }
