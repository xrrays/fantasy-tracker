"""Local read-only league dashboard API. Run with python -m backend.server."""
from fastapi import FastAPI, HTTPException, Request
from starlette.middleware.trustedhost import TrustedHostMiddleware
from .service import DashboardService
from .cache import DashboardCache
from .yahoo_client import YahooClient
from pathlib import Path
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app):
    global service
    from .keys import LEAGUE_ID
    from . import keys
    cache = DashboardCache(Path(__file__).resolve().parents[1] / 'data' / 'dashboard.sqlite3')
    service = DashboardService(YahooClient(store=cache), store=cache, league_key=LEAGUE_ID)
    service.favorite_team_key = getattr(keys, 'FAVORITE_TEAM_KEY', None)
    yield

app = FastAPI(title='RAY Local Dashboard', docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=['127.0.0.1', 'localhost'])
service = DashboardService()


@app.middleware('http')
async def local_only(request: Request, call_next):
    # The Vite proxy supplies this header, which external browser form submissions cannot set.
    origin = request.headers.get('origin')
    if request.method == 'POST' and (request.headers.get('X-Ray-Local') != '1' or
            origin not in (None, 'http://127.0.0.1:5174', 'http://localhost:5174')):
        from fastapi.responses import JSONResponse
        return JSONResponse({'detail': 'Use the local dashboard to refresh.'}, status_code=403)
    response = await call_next(request)
    response.headers['Cache-Control'] = 'no-store'
    return response


@app.get('/api/v1/dashboard')
def dashboard():
    return service.snapshot()


@app.post('/api/v1/refresh')
def refresh():
    service.start()
    return service.snapshot()


@app.post('/api/v1/recent/{days}')
def recent(days: int):
    if days not in (7, 14, 30):
        raise HTTPException(400, 'Choose 7, 14, or 30 days.')
    service.start(days)
    return service.snapshot()


@app.post('/api/v1/trades/refresh')
def trade_refresh():
    service.start('trades')
    return service.snapshot()


@app.post('/api/v1/credited/refresh')
def credited_refresh():
    service.start('credited')
    return service.snapshot()


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=8001, log_level='warning')
