import json
import hashlib
import secrets
import string
from pathlib import Path
from typing import Optional, List
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

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

DB_FILE = Path(__file__).parent / "regression_db.json"
USERS_FILE = Path(__file__).parent / "users.json"
SESSIONS_FILE = Path(__file__).parent / "sessions.json"
PROJECTS_FILE = Path(__file__).parent / "projects.json"


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(password: str, hashed: str) -> bool:
    return hash_password(password) == hashed


def generate_api_key() -> str:
    chars = string.ascii_letters + string.digits + "-_"
    return "regression_db_" + "".join(secrets.choice(chars) for _ in range(32))


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


def load_projects() -> List[dict]:
    if not PROJECTS_FILE.exists():
        return []
    with open(PROJECTS_FILE) as f:
        return json.load(f)


def save_projects(projects: List[dict]):
    with open(PROJECTS_FILE, "w") as f:
        json.dump(projects, f, indent=2)


def create_default_projects():
    projects = load_projects()
    default_projects = ["PCIE_GEN5", "HBM3", "RISCV_CORE", "DDR5_PHY", "INTERCONNECT"]

    if not projects:
        projects = [{"name": p, "created_at": datetime.utcnow().isoformat()} for p in default_projects]
        save_projects(projects)


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


class RegressionResult(BaseModel):
    regression_id: str
    block_name: str
    test_name: str
    status: str
    seed: Optional[str] = None
    simulation_tool: Optional[str] = None
    error_signature: Optional[str] = None
    failing_module_hierarchy: Optional[str] = None
    wave_path: Optional[str] = None
    debug_status: Optional[str] = None
    debug_owner: Optional[str] = None
    issue_tracker_id: Optional[int] = None


class LoginRequest(BaseModel):
    username: str
    password: str


def load_db() -> List[dict]:
    if not DB_FILE.exists():
        return []
    with open(DB_FILE) as f:
        return json.load(f)


def save_db(data: List[dict]):
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=2)


@app.get("/")
async def root():
    return FileResponse(Path(__file__).parent / "index.html")


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

    return {"api_key": api_key, "message": "API key generated. Use this in the X-API-Key header."}


@app.get("/api/projects")
async def get_projects():
    return load_projects()


@app.post("/api/projects")
async def create_project(project: dict, authorization: Optional[str] = Header(None),
                        x_api_key: Optional[str] = Header(None)):
    check_auth(authorization, x_api_key)

    projects = load_projects()
    project_name = project.get("name", "").strip()

    if not project_name:
        raise HTTPException(status_code=400, detail="Project name is required")

    if any(p.get("name") == project_name for p in projects):
        raise HTTPException(status_code=400, detail="Project already exists")

    new_project = {
        "name": project_name,
        "created_at": datetime.utcnow().isoformat()
    }
    projects.append(new_project)
    save_projects(projects)

    return new_project


def check_auth(authorization: Optional[str] = None, api_key: Optional[str] = None) -> Optional[str]:
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


@app.get("/api/regressions")
async def get_regressions(block: Optional[str] = None, status: Optional[str] = None,
                         authorization: Optional[str] = Header(None),
                         x_api_key: Optional[str] = Header(None)):
    check_auth(authorization, x_api_key)

    data = load_db()

    if block:
        data = [d for d in data if d.get("block_name") == block]
    if status:
        data = [d for d in data if d.get("status") == status]

    return data


@app.post("/api/regressions")
async def create_regression(result: RegressionResult,
                           authorization: Optional[str] = Header(None),
                           x_api_key: Optional[str] = Header(None)):
    check_auth(authorization, x_api_key)

    if result.status not in ["Passed", "Failed"]:
        raise HTTPException(status_code=400, detail="Status must be 'Passed' or 'Failed'")

    data = load_db()

    new_record = {
        "id": len(data) + 1,
        "regression_id": result.regression_id,
        "block_name": result.block_name,
        "test_name": result.test_name,
        "status": result.status,
        "seed": result.seed,
        "simulation_tool": result.simulation_tool,
        "error_signature": result.error_signature,
        "failing_module_hierarchy": result.failing_module_hierarchy,
        "wave_path": result.wave_path,
        "debug_status": result.debug_status,
        "debug_owner": result.debug_owner,
        "issue_tracker_id": result.issue_tracker_id,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat()
    }

    data.append(new_record)
    save_db(data)

    return new_record


@app.get("/api/regressions/{result_id}")
async def get_regression(result_id: int,
                        authorization: Optional[str] = Header(None),
                        x_api_key: Optional[str] = Header(None)):
    check_auth(authorization, x_api_key)

    data = load_db()

    for item in data:
        if item.get("id") == result_id:
            return item

    raise HTTPException(status_code=404, detail="Regression not found")


@app.put("/api/regressions/{result_id}")
async def update_regression(result_id: int, result: RegressionResult,
                           authorization: Optional[str] = Header(None),
                           x_api_key: Optional[str] = Header(None)):
    check_auth(authorization, x_api_key)

    if result.status not in ["Passed", "Failed"]:
        raise HTTPException(status_code=400, detail="Status must be 'Passed' or 'Failed'")

    data = load_db()

    for item in data:
        if item.get("id") == result_id:
            # PASSED tests are read-only: only allow debug fields to be modified
            if item.get("status") == "Passed":
                item["debug_status"] = result.debug_status
                item["debug_owner"] = result.debug_owner
                item["issue_tracker_id"] = result.issue_tracker_id
            else:
                # Non-passed tests: allow full updates
                item["regression_id"] = result.regression_id
                item["block_name"] = result.block_name
                item["test_name"] = result.test_name
                item["status"] = result.status
                item["seed"] = result.seed
                item["simulation_tool"] = result.simulation_tool
                item["error_signature"] = result.error_signature
                item["failing_module_hierarchy"] = result.failing_module_hierarchy
                item["wave_path"] = result.wave_path
                item["debug_status"] = result.debug_status
                item["debug_owner"] = result.debug_owner
                item["issue_tracker_id"] = result.issue_tracker_id

            item["updated_at"] = datetime.utcnow().isoformat()
            save_db(data)
            return item

    raise HTTPException(status_code=404, detail="Regression not found")


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.on_event("startup")
async def startup():
    create_default_user()
    create_default_projects()


if __name__ == "__main__":
    import uvicorn
    create_default_user()
    create_default_projects()
    uvicorn.run(app, host="0.0.0.0", port=8000)
