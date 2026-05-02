from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from supabase import create_client, Client
from datetime import datetime, timezone
from typing import Optional, List
import os

app = FastAPI()

# Config
URL = os.environ.get("SUPABASE_URL")
KEY = os.environ.get("SUPABASE_KEY")
ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "hacker123")

supabase: Client = create_client(URL, KEY) if URL and KEY else None


class Msg(BaseModel):
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


@app.get("/api/messages")
def get_messages(user: str, target: str, is_group: bool, last_id: int = 0):
    if not supabase:
        return []
    try:
        # Heartbeat
        supabase.table("chat_users").upsert(
            {"username": user, "last_seen": "now()", "active_target": target}
        ).execute()

        query = supabase.table("chat_messages").select("*")
        if is_group:
            query = query.eq("recipient", target)
        else:
            query = query.or_(
                f"and(sender.eq.{user},recipient.eq.{target}),and(sender.eq.{target},recipient.eq.{user})"
            )

        # Load only new messages
        if last_id > 0:
            res = query.gt("id", last_id).order("id").execute()
        else:
            res = query.order("id", descending=True).limit(50).execute()
            res.data.reverse()

        return res.data
    except Exception as e:
        return [{"sender": "SYSTEM", "content": f"DATABASE_ERROR: {str(e)}"}]


@app.post("/api/send")
def send_message(msg: Msg):
    try:
        supabase.table("chat_messages").insert(msg.dict()).execute()
        return {"status": "sent"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/api/presence")
def get_presence(target: str, is_group: bool, requester: str):
    try:
        # 15 second threshold
        res = (
            supabase.table("chat_users")
            .select("username")
            .eq("active_target", target)
            .execute()
        )
        return [row["username"] for row in res.data]
    except:
        return []


# Admin Panel Functions
@app.post("/api/admin/stats")
def admin_stats(req: AdminAction):
    if req.user == ADMIN_USER and req.password == ADMIN_PASS:
        u = supabase.table("chat_users").select("*").execute().data
        g = supabase.table("chat_groups").select("*").execute().data
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
    with open("static/index.html", "r") as f:
        return f.read()
