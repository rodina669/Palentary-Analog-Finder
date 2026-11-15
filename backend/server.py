from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from matcher import find_matches, list_sites

app = FastAPI(title="Planetary Analog Finder")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class SearchReq(BaseModel):
    body: str
    lat: float
    lon: float
    weights: dict = {}
    exclude_known: bool = False
    k: int = 5


@app.post("/api/search")
def search(req: SearchReq):
    try:
        results = find_matches(
            req.body,
            req.lat,
            req.lon,
            k=max(1, min(req.k, 15)),
            weights=req.weights,
            exclude_known=req.exclude_known,
        )
        return {"results": results}
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@app.get("/api/sites")
def sites(body: str | None = Query(default=None)):
    try:
        return {"sites": list_sites(body)}
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@app.get("/api/health")
def health():
    return {"ok": True, "source": "sites.csv"}
