# main.py

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from passlib.context import CryptContext
from sqlalchemy import select
import secrets
import string
from database import engine, metadata
from models import users
from typing import Dict

app = FastAPI()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

metadata.create_all(engine)

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory store for active connections
active_connections: Dict[str, WebSocket] = {}

# Dependency to get database connection
def get_db():
    from sqlalchemy.orm import sessionmaker
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def generate_unique_id(db):
    characters = string.ascii_letters + string.digits
    while True:
        user_id = ''.join(secrets.choice(characters) for _ in range(8))
        query = select([users.c.user_id]).where(users.c.user_id == user_id)
        result = db.execute(query).fetchone()
        if result is None:
            return user_id

@app.post("/register")
async def register(username: str, email: str, password: str, db=Depends(get_db)):
    if not username or not email or not password:
        raise HTTPException(status_code=400, detail="All fields are required.")

    query = select([users]).where((users.c.username == username) | (users.c.email == email))
    result = db.execute(query).fetchone()
    if result:
        raise HTTPException(status_code=400, detail="Username or email already exists.")

    hashed_password = pwd_context.hash(password)
    user_id = generate_unique_id(db)
    insert_query = users.insert().values(
        username=username,
        email=email,
        hashed_password=hashed_password,
        user_id=user_id
    )
    db.execute(insert_query)
    db.commit()
    return {"success": True, "user_id": user_id}

@app.post("/login")
async def login(identifier: str, password: str, db=Depends(get_db)):
    if not identifier or not password:
        raise HTTPException(status_code=400, detail="All fields are required.")

    query = select([users]).where((users.c.username == identifier) | (users.c.email == identifier))
    user = db.execute(query).fetchone()

    if user and pwd_context.verify(password, user.hashed_password):
        return {"success": True, "user_id": user.user_id}
    else:
        raise HTTPException(status_code=401, detail="Invalid credentials.")

@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    await websocket.accept()
    active_connections[user_id] = websocket
    try:
        while True:
            data = await websocket.receive_json()
            if data.get("action") == "send_file":
                recipient = data.get("recipient")
                await send_file(data, recipient)
    except WebSocketDisconnect:
        del active_connections[user_id]

async def send_file(data, recipient):
    recipient_ws = None
    # Find recipient WebSocket
    if recipient in active_connections:
        recipient_ws = active_connections[recipient]
    else:
        # Optionally, you can search by username or email in the database
        pass

    if recipient_ws:
        await recipient_ws.send_json({
            "action": "receive_file",
            "data": data
        })
    else:
        sender_ws = active_connections.get(data.get("sender"))
        if sender_ws:
            await sender_ws.send_json({
                "action": "error",
                "message": "Recipient not found or not connected."
            })
