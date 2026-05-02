from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from supabase import create_client, Client
from datetime import datetime, timedelta, timezone
from typing import Optional
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
def get_messages(user: str, target: str, is_group: bool, last_id: Optional[int] = None):
    try:
        # Heartbeat
        supabase.table("chat_users").upsert(
            {"username": user, "last_seen": "now()", "active_target": target}
        ).execute()

        query = supabase.table("chat_messages").select("*")

        # Filtering logic
        if is_group:
            query = query.eq("recipient", target)
        else:
            query = query.or_(
                f"and(sender.eq.{user},recipient.eq.{target}),and(sender.eq.{target},recipient.eq.{user})"
            )

        # ID-based Delta loading (Much more stable than timestamps)
        if last_id and last_id > 0:
            query = query.gt("id", last_id).order("id")
        else:
            query = query.order("id", descending=True).limit(50)

        res = query.execute()
        data = res.data

        if not last_id:
            data.reverse()

        return data
    except Exception as e:
        print(f"Error: {e}")
        return []


@app.post("/api/send")
def send_message(msg: Msg):
    try:
        supabase.table("chat_messages").insert(msg.dict()).execute()
        return {"status": "sent"}
    except:
        return {"status": "error"}


@app.get("/api/presence")
def get_presence(target: str, is_group: bool, requester: str):
    try:
        threshold = (datetime.now(timezone.utc) - timedelta(seconds=15)).isoformat()
        if is_group:
            res = (
                supabase.table("chat_users")
                .select("username")
                .eq("active_target", target)
                .gt("last_seen", threshold)
                .execute()
            )
        else:
            res = (
                supabase.table("chat_users")
                .select("username")
                .eq("username", target)
                .eq("active_target", requester)
                .gt("last_seen", threshold)
                .execute()
            )
        return [row["username"] for row in res.data]
    except:
        return []


@app.post("/api/admin/stats")
def admin_stats(req: AdminAction):
    if req.user == ADMIN_USER and req.password == ADMIN_PASS:
        u = supabase.table("chat_users").select("*").execute().data
        g = supabase.table("chat_groups").select("*").execute().data
        return {"users": u, "groups": g}
    raise HTTPException(status_code=401)


@app.post("/api/admin/create-group")
def admin_group(req: AdminAction):
    if req.user == ADMIN_USER and req.password == ADMIN_PASS:
        supabase.table("chat_groups").insert({"group_name": req.target}).execute()
        return {"status": "created"}
    raise HTTPException(status_code=401)


@app.post("/api/admin/clear")
def admin_clear(req: AdminAction):
    if req.user == ADMIN_USER and req.password == ADMIN_PASS:
        # Wipes all messages
        supabase.table("chat_messages").delete().gte("id", 0).execute()
        return {"status": "purged"}
    raise HTTPException(status_code=401)


@app.get("/", response_class=HTMLResponse)
async def read_index():
    path = os.path.join(os.getcwd(), "static", "index.html")
    with open(path, "r") as f:
        return f.read()
