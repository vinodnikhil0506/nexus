import json
import os
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from pathlib import Path

app = FastAPI()

HTML_DIR = Path(__file__).parent


@app.get("/")
async def root():
    return FileResponse(HTML_DIR / "index.html")


@app.get("/index.html")
async def index_html():
    return FileResponse(HTML_DIR / "index.html")


@app.get("/favicon.ico")
async def favicon():
    return Response(status_code=204)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Self-contained: all state lives beside this server (nexus-workspace/webpages/issue_tracker/).
ISSUES_FILE = Path(__file__).parent / "issues.json"
ISSUE_COUNTER_FILE = Path(__file__).parent / ".issue_counter"
USERS_FILE = Path(__file__).parent / "users.json"
SESSIONS_FILE = Path(__file__).parent / "sessions.json"


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(password: str, hashed: str) -> bool:
    return hash_password(password) == hashed


def generate_api_key() -> str:
    return "tracker_" + secrets.token_urlsafe(32)


def load_users() -> dict:
    if not USERS_FILE.exists():
        return {}
    with open(USERS_FILE) as f:
        return json.load(f)


def save_users(users: dict):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)


def load_sessions() -> dict:
    if not SESSIONS_FILE.exists():
        return {}
    with open(SESSIONS_FILE) as f:
        return json.load(f)


def save_sessions(sessions: dict):
    with open(SESSIONS_FILE, "w") as f:
        json.dump(sessions, f, indent=2)


def create_default_user():
    users = load_users()
    if "admin" not in users:
        users["admin"] = {
            "password": hash_password("admin"),
            "api_keys": []
        }
        save_users(users)


def verify_session(session_id: str) -> Optional[str]:
    sessions = load_sessions()
    session = sessions.get(session_id)
    if not session:
        return None
    if datetime.fromisoformat(session["expires"]) < datetime.utcnow():
        return None
    return session["username"]


def verify_api_key(api_key: str) -> Optional[str]:
    users = load_users()
    for username, user_data in users.items():
        if api_key in user_data.get("api_keys", []):
            return username
    return None


def check_auth(authorization: Optional[str] = None, api_key: Optional[str] = None) -> str:
    if authorization and authorization.startswith("Bearer "):
        session_id = authorization[7:]
        username = verify_session(session_id)
        if username:
            return username

    if api_key:
        username = verify_api_key(api_key)
        if username:
            return username

    raise HTTPException(status_code=401, detail="Unauthorized")


class LoginRequest(BaseModel):
    username: str
    password: str


class Issue(BaseModel):
    id: Optional[int] = None
    title: str
    description: Optional[str] = None
    component: Optional[str] = None
    revision: Optional[str] = None
    firmware: Optional[str] = None
    severity: str
    status: str = "todo"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    comments: Optional[list] = None
    assignee: Optional[str] = None


def load_issues() -> List[dict]:
    if not ISSUES_FILE.exists():
        return []
    with open(ISSUES_FILE) as f:
        return json.load(f)


def save_issues(issues: List[dict]):
    with open(ISSUES_FILE, "w") as f:
        json.dump(issues, f, indent=2)


def get_next_id() -> int:
    if ISSUE_COUNTER_FILE.exists():
        with open(ISSUE_COUNTER_FILE) as f:
            current = int(f.read().strip())
    else:
        current = 0

    next_id = current + 1
    with open(ISSUE_COUNTER_FILE, "w") as f:
        f.write(str(next_id))
    return next_id


@app.post("/api/login")
async def login(request: LoginRequest):
    users = load_users()
    user = users.get(request.username)

    if not user or not verify_password(request.password, user["password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    session_id = secrets.token_urlsafe(32)
    sessions = load_sessions()
    sessions[session_id] = {
        "username": request.username,
        "expires": (datetime.utcnow() + timedelta(days=7)).isoformat()
    }
    save_sessions(sessions)

    return {"session_id": session_id, "username": request.username}


@app.post("/api/logout")
async def logout(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")

    session_id = authorization[7:]
    sessions = load_sessions()
    if session_id in sessions:
        del sessions[session_id]
        save_sessions(sessions)

    return {"message": "Logged out"}


@app.post("/api/generate-key")
async def generate_key(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")

    session_id = authorization[7:]
    username = verify_session(session_id)

    if not username:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    users = load_users()
    api_key = generate_api_key()
    users[username]["api_keys"].append(api_key)
    save_users(users)

    return {"api_key": api_key, "message": "API key generated"}


@app.get("/api/issues")
async def get_issues(authorization: Optional[str] = Header(None),
                     x_api_key: Optional[str] = Header(None)):
    check_auth(authorization, x_api_key)
    issues = load_issues()
    return issues


@app.post("/api/issues")
async def create_issue(issue: Issue,
                      authorization: Optional[str] = Header(None),
                      x_api_key: Optional[str] = Header(None)):
    check_auth(authorization, x_api_key)

    issues = load_issues()
    issue.id = get_next_id()
    issue.created_at = datetime.utcnow().isoformat()
    issue.updated_at = issue.created_at

    issue_dict = issue.model_dump()
    issues.append(issue_dict)
    save_issues(issues)

    return issue_dict


@app.get("/api/issues/{issue_id}")
async def get_issue(issue_id: int,
                   authorization: Optional[str] = Header(None),
                   x_api_key: Optional[str] = Header(None)):
    check_auth(authorization, x_api_key)

    issues = load_issues()
    for issue in issues:
        if issue["id"] == issue_id:
            return issue
    raise HTTPException(status_code=404, detail="Issue not found")


@app.put("/api/issues/{issue_id}")
async def update_issue(issue_id: int, issue: Issue,
                      authorization: Optional[str] = Header(None),
                      x_api_key: Optional[str] = Header(None)):
    check_auth(authorization, x_api_key)

    issues = load_issues()
    for i, existing in enumerate(issues):
        if existing["id"] == issue_id:
            issue_dict = issue.model_dump()
            issue_dict["id"] = issue_id
            issue_dict["created_at"] = existing.get("created_at")
            issue_dict["updated_at"] = datetime.utcnow().isoformat()
            issues[i] = issue_dict
            save_issues(issues)
            return issue_dict

    raise HTTPException(status_code=404, detail="Issue not found")


@app.delete("/api/issues/{issue_id}")
async def delete_issue(issue_id: int,
                      authorization: Optional[str] = Header(None),
                      x_api_key: Optional[str] = Header(None)):
    check_auth(authorization, x_api_key)

    issues = load_issues()
    for i, issue in enumerate(issues):
        if issue["id"] == issue_id:
            issues.pop(i)
            save_issues(issues)
            return {"status": "deleted"}

    raise HTTPException(status_code=404, detail="Issue not found")


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.on_event("startup")
async def startup():
    create_default_user()


if __name__ == "__main__":
    import uvicorn
    create_default_user()
    uvicorn.run(app, host="0.0.0.0", port=8001)
