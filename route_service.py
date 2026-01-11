from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import requests
import time

router = APIRouter(prefix="/route", tags=["Route Areas"])

# -------------------- MODELS --------------------

class RouteRequest(BaseModel):
    from_place: str
    to_place: str
    district: str | None = None
    state: str | None = None


class RouteResponse(BaseModel):
    areas: list[str]


# -------------------- HELPERS --------------------

def geocode(place: str):
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": place,
        "format": "json",
        "limit": 1
    }
    headers = {"User-Agent": "bus-route-service"}

    try:
        r = requests.get(url, params=params, headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json()
    except Exception:
        return None

    if not data:
        return None

    return {
        "lat": float(data[0]["lat"]),
        "lng": float(data[0]["lon"])
    }


def get_route_points(start, end):
    url = (
        f"https://router.project-osrm.org/route/v1/driving/"
        f"{start['lng']},{start['lat']};{end['lng']},{end['lat']}"
        "?overview=full&geometries=geojson"
    )

    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception:
        return []

    if not data.get("routes"):
        return []

    return data["routes"][0]["geometry"]["coordinates"]


# 🔥 SPEED IMPROVED
def sample_route(coords, step=20):
    return [coords[i] for i in range(0, len(coords), step)]


def fetch_areas_near(lat, lng):
    query = f"""
    [out:json];
    node["place"~"village|town|suburb|neighbourhood|locality"]
    (around:1800,{lat},{lng});
    out;
    """

    try:
        r = requests.post(
            "https://overpass-api.de/api/interpreter",
            data=query,
            timeout=15,
            headers={"User-Agent": "bus-route-service"}
        )
        r.raise_for_status()
        data = r.json()
    except Exception:
        return []

    names = []
    for el in data.get("elements", []):
        name = el.get("tags", {}).get("name")
        if name:
            names.append(name)

    return names


# -------------------- API --------------------

@router.post("/areas", response_model=RouteResponse)
def get_route_areas(req: RouteRequest):

    # 1️⃣ Build search strings
    from_query = f"{req.from_place}, {req.district or ''}, {req.state or ''}"
    to_query = f"{req.to_place}, {req.district or ''}, {req.state or ''}"

    # 2️⃣ Geocode
    start = geocode(from_query)
    end = geocode(to_query)

    if not start or not end:
        raise HTTPException(status_code=404, detail="Location not found")

    # 3️⃣ Get route
    route_coords = get_route_points(start, end)
    if not route_coords:
        raise HTTPException(status_code=404, detail="Route not found")

    # 4️⃣ Sample route
    samples = sample_route(route_coords, step=20)

    # 5️⃣ Collect nearby areas
    area_set = set()
    area_set.add(req.from_place)

    for lng, lat in samples:
        nearby = fetch_areas_near(lat, lng)
        for a in nearby:
            area_set.add(a)

        # ⏳ minimal delay – frontend delay feel aagadhu
        time.sleep(0.1)

    area_set.add(req.to_place)

    return {"areas": sorted(area_set)}
