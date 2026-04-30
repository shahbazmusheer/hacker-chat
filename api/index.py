from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from supabase import create_client, Client
from datetime import datetime, timedelta, timezone
import os

app = FastAPI()

# Environment Config
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


class AdminAction(BaseModel):
    user: str
    password: str
    target: str = None


@app.get("/api/messages")
def get_messages(user: str, target: str, is_group: bool):
    try:
        # 1. Automatic 2-Day Cleanup (Applies to ALL chats)
        threshold = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
        supabase.table("chat_messages").delete().lt("created_at", threshold).execute()

        # 2. Update User Activity
        supabase.table("chat_users").upsert(
            {"username": user, "last_seen": "now()"}
        ).execute()

        # 3. Fetch specific history
        if is_group:
            res = (
                supabase.table("chat_messages")
                .select("*")
                .eq("recipient", target)
                .order("created_at")
                .execute()
            )
        else:
            # Filters Private: (Me to Him) OR (Him to Me)
            res = (
                supabase.table("chat_messages")
                .select("*")
                .or_(
                    f"and(sender.eq.{user},recipient.eq.{target}),and(sender.eq.{target},recipient.eq.{user})"
                )
                .order("created_at")
                .execute()
            )
        return res.data
    except:
        return []


@app.post("/api/send")
def send_message(msg: Msg):
    supabase.table("chat_messages").insert(
        {
            "sender": msg.sender,
            "recipient": msg.recipient,
            "content": msg.content,
            "is_group": msg.is_group,
        }
    ).execute()
    return {"status": "sent"}


@app.post("/api/admin/stats")
def get_admin_stats(req: AdminAction):
    if req.user == ADMIN_USER and req.password == ADMIN_PASS:
        users = supabase.table("chat_users").select("*").execute().data
        groups = supabase.table("chat_groups").select("*").execute().data
        return {"users": users, "groups": groups}
    raise HTTPException(status_code=401)


@app.post("/api/admin/create-group")
def create_group(req: AdminAction):
    if req.user == ADMIN_USER and req.password == ADMIN_PASS:
        supabase.table("chat_groups").insert({"group_name": req.target}).execute()
        return {"status": "Group Created"}
    raise HTTPException(status_code=401)


@app.post("/api/admin/clear")
def clear_history(req: AdminAction):
    if req.user == ADMIN_USER and req.password == ADMIN_PASS:
        supabase.table("chat_messages").delete().neq("id", 0).execute()
        return {"status": "Database Wiped"}
    raise HTTPException(status_code=401)


@app.get("/", response_class=HTMLResponse)
async def read_index():
    path = os.path.join(os.getcwd(), "static", "index.html")
    with open(path, "r") as f:
        return f.read()
