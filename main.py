from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import sqlite3

app = FastAPI()

# ===================== CORS =====================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

    # BUSES (route_id OPTIONAL)
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

    conn.commit()
    conn.close()

init_db()

# ===================== AUTH =====================
class LoginRequest(BaseModel):
    username: str
    password: str

USERS = {
    "psdas": {"password": "psdas", "role": "master"},
    "admin1": {"password": "admin1", "role": "admin"},
    "view1": {"password": "view1", "role": "viewer"},
}

@app.post("/login")
def login(data: LoginRequest):
    user = USERS.get(data.username)
    if not user or user["password"] != data.password:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"success": True, "role": user["role"]}

# ===================== DISPLAY MODELS =====================
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

# ===================== BUS MODELS =====================
class BusCreate(BaseModel):
    registration_no: str
    depot: str
    device_id: str

# ===================== ROUTE MODELS =====================
class RouteCreate(BaseModel):
    route_code: str
    from_place: str
    to_place: str

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
