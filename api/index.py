from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from supabase import create_client, Client
from datetime import datetime, timedelta, timezone
import os

app = FastAPI()

# Configuration from Environment Variables
URL = os.environ.get("SUPABASE_URL")
KEY = os.environ.get("SUPABASE_KEY")

# Initialize Supabase
supabase: Client = create_client(URL, KEY) if URL and KEY else None


class Msg(BaseModel):
    sender: str
    content: str


@app.get("/api/messages")
def get_messages():
    if not supabase:
        return []
    try:
        # 1. Auto-cleanup: Delete messages older than 2 days
        threshold = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
        supabase.table("chat_messages").delete().lt("created_at", threshold).execute()

        # 2. Fetch current messages
        response = (
            supabase.table("chat_messages").select("*").order("created_at").execute()
        )
        return response.data
    except:
        return []


@app.post("/api/send")
def send_message(msg: Msg):
    if not supabase:
        return {"status": "error"}
    try:
        payload = {"sender": msg.sender, "content": msg.content}
        supabase.table("chat_messages").insert(payload).execute()
        return {"status": "success"}
    except:
        return {"status": "error"}


@app.get("/", response_class=HTMLResponse)
async def read_index():
    # Path logic works for both local and Vercel
    path = os.path.join(os.getcwd(), "static", "index.html")
    with open(path, "r") as f:
        return f.read()
