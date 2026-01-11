from fastapi import FastAPI, HTTPException, Query, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import sqlite3
from route_service import router as route_router

app = FastAPI()

# ===================== CORS =====================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(route_router)
# ===================== DATABASE =====================
DB_NAME = "displays.db"

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()

    # DISPLAYS
    cur.execute("""
        CREATE TABLE IF NOT EXISTS displays (
            deviceId TEXT PRIMARY KEY,
            displayName TEXT,
            locationName TEXT,
            installerName TEXT,
            latitude TEXT,
            longitude TEXT,
            method TEXT
        )
    """)

    # ROUTES
    cur.execute("""
        CREATE TABLE IF NOT EXISTS routes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            route_code TEXT UNIQUE,
            from_place TEXT,
            to_place TEXT
        )
    """)

    # BUSES
    cur.execute("""
        CREATE TABLE IF NOT EXISTS buses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            registration_no TEXT UNIQUE,
            depot TEXT,
            device_id TEXT UNIQUE,
            route_id INTEGER NULL,
            FOREIGN KEY (route_id) REFERENCES routes(id)
        )
    """)

    # USERS
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            role TEXT,
            is_active INTEGER DEFAULT 1,
            created_by TEXT
        )
    """)

    conn.commit()
    conn.close()

init_db()

# ===================== AUTH =====================
class LoginRequest(BaseModel):
    username: str
    password: str

@app.get("/__init_master")
def init_master():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM users")
    count = cur.fetchone()[0]

    if count > 0:
        raise HTTPException(status_code=400, detail="Users already exist")

    cur.execute("""
        INSERT INTO users (username, password, role, is_active)
        VALUES ('master', 'master123', 'master', 1)
    """)
    
    conn.commit()
    
    conn.close()
    print("Success")

    return {"success": True, "message": "Master user created"}


@app.post("/login")
def login(data: LoginRequest):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT username, password, role, is_active FROM users WHERE username=?",
        (data.username,)
    )
    user = cur.fetchone()

    print("user",data.username)
    print("password",data.password)
    conn.close()

    # ❌ USER NOT FOUND
    if not user:
        raise HTTPException(status_code=403, detail="Unauthorized user")

    # ❌ PASSWORD WRONG
    if user["password"] != data.password:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # ❌ INACTIVE USER
    if user["is_active"] != 1:
        raise HTTPException(status_code=403, detail="User is inactive")

    # ✅ SUCCESS
    return {
        "success": True,
        "username": user["username"],
        "role": user["role"]
    }

# ===================== MODELS =====================
class DisplayInstall(BaseModel):
    deviceId: str
    displayName: str
    locationName: str
    installerName: Optional[str] = None
    latitude: str
    longitude: str
    method: str

class DisplayUpdate(BaseModel):
    displayName: Optional[str] = None
    locationName: Optional[str] = None
    installerName: Optional[str] = None
    latitude: Optional[str] = None
    longitude: Optional[str] = None

class BusCreate(BaseModel):
    registration_no: str
    depot: str
    device_id: str

class RouteCreate(BaseModel):
    route_code: str
    from_place: str
    to_place: str

class UserCreate(BaseModel):
    username: str
    password: str
    role: str
    is_active: Optional[bool] = True
    created_by: Optional[str] = None

class UserUpdate(BaseModel):
    role: Optional[str]
    is_active: Optional[bool]

# ===================== DISPLAYS =====================
@app.post("/displays")
def add_display(data: DisplayInstall):
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO displays VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            data.deviceId,
            data.displayName,
            data.locationName,
            data.installerName,
            data.latitude,
            data.longitude,
            data.method
        ))
        conn.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Display already exists")
    finally:
        conn.close()
    return {"success": True}

@app.get("/displays")
def get_displays():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM displays")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.get("/displays/count")
def get_display_count():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM displays")
    count = cur.fetchone()[0]
    conn.close()
    return {"total": count}

@app.delete("/displays/{device_id}")
def delete_display(device_id: str):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM displays WHERE deviceId=?", (device_id,))
    conn.commit()
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Display not found")
    conn.close()
    return {"success": True}

@app.put("/displays/{device_id}")
def update_display(device_id: str, data: DisplayUpdate):
    conn = get_db()
    cur = conn.cursor()
    fields, values = [], []
    for k, v in data.dict(exclude_unset=True).items():
        fields.append(f"{k}=?")
        values.append(v)
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")
    values.append(device_id)
    cur.execute(f"UPDATE displays SET {', '.join(fields)} WHERE deviceId=?", values)
    conn.commit()
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Display not found")
    conn.close()
    return {"success": True}

# ===================== BUSES =====================
@app.post("/buses")
def add_bus(data: BusCreate):
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO buses (registration_no, depot, device_id)
            VALUES (?, ?, ?)
        """, (
            data.registration_no,
            data.depot,
            data.device_id
        ))
        conn.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Bus already exists")
    finally:
        conn.close()
    return {"success": True}

@app.get("/buses")
def get_buses():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM buses")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.get("/buses/count")
def get_bus_count():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM buses")
    count = cur.fetchone()[0]
    conn.close()
    return {"total": count}

@app.delete("/buses/{bus_id}")
def delete_bus(bus_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM buses WHERE id=?", (bus_id,))
    conn.commit()
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Bus not found")
    conn.close()
    return {"success": True}

# ===================== ROUTES =====================
@app.post("/routes")
def add_route(data: RouteCreate):
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO routes (route_code, from_place, to_place)
            VALUES (?, ?, ?)
        """, (
            data.route_code,
            data.from_place,
            data.to_place
        ))
        conn.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Route already exists")
    finally:
        conn.close()
    return {"success": True}

@app.get("/routes")
def list_routes():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM routes")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.get("/routes/count")
def route_count():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM routes")
    count = cur.fetchone()[0]
    conn.close()
    return {"total": count}

@app.delete("/routes/{route_id}")
def delete_route(route_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM routes WHERE id=?", (route_id,))
    conn.commit()
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Route not found")
    conn.close()
    return {"success": True}

# ===================== USERS =====================
@app.post("/users/create")
def create_user(data: UserCreate):
    role = data.role.lower()

    if data.created_by:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT role FROM users WHERE username=?", (data.created_by,))
        creator = cur.fetchone()
        conn.close()

        if not creator:
            raise HTTPException(status_code=403, detail="Invalid creator")

        creator_role = creator["role"].lower()

        if creator_role == "viewer":
            raise HTTPException(status_code=403, detail="Viewer cannot create users")

        if creator_role == "admin" and role == "master":
            raise HTTPException(status_code=403, detail="Admin cannot create master")

    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO users (username, password, role, is_active, created_by)
            VALUES (?, ?, ?, ?, ?)
        """, (
            data.username,
            data.password,
            role,   # ✅ lowercase stored
            1 if data.is_active else 0,
            data.created_by
        ))
        conn.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="User already exists")
    finally:
        conn.close()

    return {"success": True}


@app.get("/users")
def list_users():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, username, role, is_active, created_by FROM users")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ===================== USER EDIT (MASTER ONLY) =====================
@app.put("/users/{user_id}")
def update_user(
    user_id: int,
    data: UserUpdate,
    editor_username: Optional[str] = Query(None),
    x_username: Optional[str] = Header(None)   # 🔧 FIX
):
    editor = editor_username or x_username     # 🔧 FIX
    if not editor:
        raise HTTPException(status_code=403, detail="Editor username required")

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT role FROM users WHERE username=?", (editor,))
    editor_row = cur.fetchone()

    if not editor_row or editor_row["role"].lower() != "master":
        raise HTTPException(status_code=403, detail="Only master can edit users")

    cur.execute("SELECT role, is_active FROM users WHERE id=?", (user_id,))
    target = cur.fetchone()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    new_role = data.role.lower() if data.role else target["role"]

    cur.execute("""
        UPDATE users SET role=?, is_active=?
        WHERE id=?
    """, (
        new_role,
        1 if data.is_active else target["is_active"],
        user_id
    ))

    conn.commit()
    conn.close()
    return {"success": True}


# ===================== USER DELETE (MASTER ONLY) =====================
@app.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    editor_username: Optional[str] = Query(None),
    x_username: Optional[str] = Header(None)   # 🔧 FIX
):
    editor = editor_username or x_username     # 🔧 FIX
    if not editor:
        raise HTTPException(status_code=403, detail="Editor username required")

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT role FROM users WHERE username=?", (editor,))
    editor_row = cur.fetchone()

    if not editor_row or editor_row["role"].lower() != "master":
        raise HTTPException(status_code=403, detail="Only master can delete users")

    cur.execute("DELETE FROM users WHERE id=?", (user_id,))
    conn.commit()

    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="User not found")

    conn.close()
    return {"success": True}
