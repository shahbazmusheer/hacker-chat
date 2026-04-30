from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from supabase import create_client, Client
from datetime import datetime, timedelta, timezone
import os

app = FastAPI()

URL = os.environ.get("SUPABASE_URL")
KEY = os.environ.get("SUPABASE_KEY")
# Set a default password here or in Vercel Env Variables
ADMIN_PASSWORD = os.environ.get("CHAT_ADMIN_PASS", "@H4CK3R1155")

supabase: Client = create_client(URL, KEY) if URL and KEY else None


class Msg(BaseModel):
    sender: str
    content: str


class ClearReq(BaseModel):
    password: str


@app.get("/api/messages")
def get_messages():
    if not supabase:
        return []
    try:
        threshold = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
        supabase.table("chat_messages").delete().lt("created_at", threshold).execute()
        response = (
            supabase.table("chat_messages").select("*").order("created_at").execute()
        )
        return response.data
    except:
        return []


@app.post("/api/send")
def send_message(msg: Msg):
    try:
        supabase.table("chat_messages").insert(
            {"sender": msg.sender, "content": msg.content}
        ).execute()
        return {"status": "success"}
    except:
        return {"status": "error"}


@app.post("/api/clear")
def clear_history(req: ClearReq):
    if req.password == ADMIN_PASSWORD:
        try:
            # Delete all rows where ID is greater than 0
            supabase.table("chat_messages").delete().neq("id", 0).execute()
            return {"status": "cleared"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    return {"status": "unauthorized"}


@app.get("/", response_class=HTMLResponse)
async def read_index():
    path = os.path.join(os.getcwd(), "static", "index.html")
    with open(path, "r") as f:
        return f.read()
