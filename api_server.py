"""
Simple HTTP API server for Chrome extension sync
"""
import json
import logging
from aiohttp import web
from pathlib import Path

logger = logging.getLogger(__name__)

WATCHLIST_FILE = "watchlist.json"

class APIServer:
    def __init__(self, host: str = "0.0.0.0", port: int = 8765):
        self.host = host
        self.port = port
        self.app = web.Application()
        self.setup_routes()

    def setup_routes(self):
        self.app.router.add_get("/api/watchlist/{user_id}", self.get_watchlist)
        self.app.router.add_post("/api/watchlist/{user_id}", self.update_watchlist)
        self.app.router.add_get("/api/events", self.get_events)
        self.app.router.add_get("/api/new-markets", self.get_new_markets)
        self.app.router.add_options("/{path:.*}", self.handle_options)

        # Add CORS middleware
        self.app.middlewares.append(self.cors_middleware)

    @web.middleware
    async def cors_middleware(self, request, handler):
        response = await handler(request)
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-Telegram-User-Id'
        return response

    async def handle_options(self, request):
        return web.Response(status=200)

    async def get_watchlist(self, request):
        """Get user's watchlist"""
        user_id = request.match_info.get('user_id')

        try:
            if Path(WATCHLIST_FILE).exists():
                with open(WATCHLIST_FILE, 'r') as f:
                    data = json.load(f)
                    user_watchlist = data.get(str(user_id), [])
                    return web.json_response({
                        "success": True,
                        "watchlist": user_watchlist
                    })
            return web.json_response({"success": True, "watchlist": []})
        except Exception as e:
            logger.error(f"Error getting watchlist: {e}")
            return web.json_response({"success": False, "error": str(e)}, status=500)

    async def update_watchlist(self, request):
        """Update user's watchlist from extension"""
        user_id = request.match_info.get('user_id')

        try:
            body = await request.json()
            slugs = body.get('slugs', [])

            # Load existing data
            data = {}
            if Path(WATCHLIST_FILE).exists():
                with open(WATCHLIST_FILE, 'r') as f:
                    data = json.load(f)

            # Update user's watchlist
            data[str(user_id)] = slugs

            # Save
            with open(WATCHLIST_FILE, 'w') as f:
                json.dump(data, f, indent=2)

            return web.json_response({"success": True})
        except Exception as e:
            logger.error(f"Error updating watchlist: {e}")
            return web.json_response({"success": False, "error": str(e)}, status=500)

    async def get_events(self, request):
        """Proxy to Polymarket API with caching"""
        import aiohttp

        limit = request.query.get('limit', '200')

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"https://gamma-api.polymarket.com/events?limit={limit}&active=true&closed=false",
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    events = await resp.json()
                    return web.json_response(events)
        except Exception as e:
            logger.error(f"Error fetching events: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def get_new_markets(self, request):
        """Get recently posted new markets (same as Telegram channel)"""
        posted_events_file = Path("posted_events.json")

        try:
            if posted_events_file.exists():
                with open(posted_events_file, 'r') as f:
                    data = json.load(f)
                    events = data.get('events', [])
                    return web.json_response({
                        "success": True,
                        "events": events
                    })
            return web.json_response({"success": True, "events": []})
        except Exception as e:
            logger.error(f"Error getting new markets: {e}")
            return web.json_response({"success": False, "error": str(e)}, status=500)

    async def start(self):
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, self.host, self.port)
        await site.start()
        logger.info(f"API server started on http://{self.host}:{self.port}")
        return runner
