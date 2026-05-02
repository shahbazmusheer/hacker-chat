from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from supabase import create_client, Client
from datetime import datetime, timedelta, timezone
from typing import Optional, List
import os

app = FastAPI()

# Config
URL = os.environ.get("SUPABASE_URL")
KEY = os.environ.get("SUPABASE_KEY")
ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "hacker123")

supabase: Client = create_client(URL, KEY) if URL and KEY else None


# --- REQUEST MODELS ---
class MessageRequest(BaseModel):
    user: str
    target: str
    is_group: bool
    last_id: Optional[int] = 0


class PresenceRequest(BaseModel):
    target: str
    is_group: bool
    requester: str


class MsgSendRequest(BaseModel):
    sender: str
    recipient: str
    content: str
    is_group: bool
    parent_sender: Optional[str] = None
    parent_content: Optional[str] = None


class AdminAction(BaseModel):
    user: str
    password: str
    target: Optional[str] = None


# --- API ENDPOINTS (ALL POST) ---


@app.post("/api/messages")
def fetch_messages(req: MessageRequest):
    try:
        # Heartbeat update
        supabase.table("chat_users").upsert(
            {"username": req.user, "last_seen": "now()", "active_target": req.target}
        ).execute()

        # Build Query
        query = supabase.table("chat_messages").select("*")
        if req.is_group:
            query = query.eq("recipient", req.target)
        else:
            query = query.or_(
                f"and(sender.eq.{req.user},recipient.eq.{req.target}),and(sender.eq.{req.target},recipient.eq.{req.user})"
            )

        if req.last_id and req.last_id > 0:
            res = query.gt("id", req.last_id).order("id").execute()
            return res.data
        else:
            res = query.order("id", desc=True).limit(50).execute()
            data = res.data
            data.reverse()
            return data
    except:
        return []


@app.post("/api/send")
def send_message(msg: MsgSendRequest):
    try:
        supabase.table("chat_messages").insert(msg.dict()).execute()
        return {"status": "sent"}
    except:
        return {"status": "error"}


@app.post("/api/presence")
def fetch_presence(req: PresenceRequest):
    try:
        threshold = (datetime.now(timezone.utc) - timedelta(seconds=15)).isoformat()
        if req.is_group:
            res = (
                supabase.table("chat_users")
                .select("username")
                .eq("active_target", req.target)
                .gt("last_seen", threshold)
                .execute()
            )
        else:
            res = (
                supabase.table("chat_users")
                .select("username")
                .eq("username", req.target)
                .eq("active_target", req.requester)
                .gt("last_seen", threshold)
                .execute()
            )
        return [row["username"] for row in res.data]
    except:
        return []


@app.post("/api/admin/stats")
def admin_stats(req: AdminAction):
    if req.user == ADMIN_USER and req.password == ADMIN_PASS:
        # Get last 10 users and groups
        u = (
            supabase.table("chat_users")
            .select("*")
            .order("last_seen", desc=True)
            .limit(10)
            .execute()
            .data
        )
        g = (
            supabase.table("chat_groups")
            .select("*")
            .order("created_at", desc=True)
            .limit(10)
            .execute()
            .data
        )
        return {"users": u, "groups": g}
    raise HTTPException(status_code=401)


@app.post("/api/admin/clear")
def admin_clear(req: AdminAction):
    if req.user == ADMIN_USER and req.password == ADMIN_PASS:
        supabase.table("chat_messages").delete().gte("id", 0).execute()
        return {"status": "purged"}
    raise HTTPException(status_code=401)


@app.get("/", response_class=HTMLResponse)
async def read_index():
    path = os.path.join(os.getcwd(), "static", "index.html")
    with open(path, "r") as f:
        return f.read()
