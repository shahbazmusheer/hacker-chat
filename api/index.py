from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from supabase import create_client, Client
from datetime import datetime, timedelta, timezone
from typing import Optional
import os

app = FastAPI()

# Configuration
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
def get_messages(user: str, target: str, is_group: bool, last_ts: Optional[str] = None):
    try:
        # Heartbeat & Presence
        supabase.table("chat_users").upsert({"username": user, "last_seen": "now()", "active_target": target}).execute()
        
        # 48h Auto-Cleanup
        threshold = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
        supabase.table("chat_messages").delete().lt("created_at", threshold).execute()

        # Delta Fetch Logic
        query = supabase.table("chat_messages").select("*")
        if is_group:
            query = query.eq("recipient", target)
        else:
            query = query.or_(f"and(sender.eq.{user},recipient.eq.{target}),and(sender.eq.{target},recipient.eq.{user})")
        
        if last_ts:
            query = query.gt("created_at", last_ts)
        
        res = query.order("created_at").execute()
        return res.data
    except Exception as e: return []

@app.get("/api/presence")
def get_presence(target: str, is_group: bool, requester: str):
    threshold = (datetime.now(timezone.utc) - timedelta(seconds=15)).isoformat()
    if is_group:
        res = supabase.table("chat_users").select("username").eq("active_target", target).gt("last_seen", threshold).execute()
    else:
        res = supabase.table("chat_users").select("username").eq("username", target).eq("active_target", requester).gt("last_seen", threshold).execute()
    return [row['username'] for row in res.data]

@app.post("/api/send")
def send_message(msg: Msg):
    supabase.table("chat_messages").insert(msg.dict()).execute()
    return {"status": "sent"}

# --- ADMIN ENDPOINTS ---
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
        supabase.table("chat_messages").delete().gte("id", 0).execute()
        return {"status": "purged"}
    raise HTTPException(status_code=401)

@app.get("/", response_class=HTMLResponse)
async def read_index():
    with open("static/index.html", "r") as f: return f.read()