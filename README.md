# Polydictions

A Telegram bot for tracking and analyzing Polymarket prediction markets in real-time.

## Features

- **Real-time Monitoring**: Automatic notifications for new Polymarket events
- **Market Analysis**: Detailed event statistics including liquidity, volume, and current odds
- **AI Context**: Market context powered by Polymarket's API
- **Smart Filtering**: Filter events by custom keywords and categories
- **Price Alerts**: Get notified when prices cross your thresholds
- **Watchlist**: Track specific events with personalized updates
- **News Monitoring**: Receive relevant news for watched markets
- **REST API**: External access for integrations (Chrome extension, web apps)
- **Pause/Resume**: Control notifications on-demand

## Commands

| Command | Description |
|---------|-------------|
| `/start` | Subscribe to event notifications |
| `/deal <link>` | Analyze a specific Polymarket event |
| `/watchlist` | Show your watched events |
| `/watch <slug>` | Add event to watchlist |
| `/interval <minutes>` | Set news update interval (3-1440) |
| `/alerts` | Show your price alerts |
| `/alert <slug> <condition> <threshold>` | Set price alert (e.g., `/alert btc-price > 50`) |
| `/keywords <words>` | Set keyword filters |
| `/categories` | Show/set category filters |
| `/pause` | Pause notifications |
| `/resume` | Resume notifications |
| `/help` | Show help information |

## Installation

### Prerequisites

- Python 3.11 or higher
- A Telegram Bot Token from [@BotFather](https://t.me/BotFather)

### Quick Start with Docker (Recommended)

1. Clone the repository:
```bash
git clone https://github.com/yourusername/polydictions.git
cd polydictions
```

2. Create environment file:
```bash
cp .env.example .env
# Edit .env with your settings
```

3. Run with Docker Compose:
```bash
docker-compose up -d
```

### Manual Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/polydictions.git
cd polydictions
```

2. Create virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# or
.venv\Scripts\activate     # Windows
```

3. Install dependencies:
```bash
pip install -e ".[dev]"
```

4. Create environment file:
```bash
cp .env.example .env
# Edit .env with your bot token and other settings
```

5. Initialize the database:
```bash
alembic upgrade head
```

6. Run the bot:
```bash
python -m src.main
```

## Configuration

All configuration is done via environment variables. See `.env.example` for all options:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `BOT_TOKEN` | Yes | - | Telegram Bot API token |
| `DATABASE_URL` | No | `sqlite+aiosqlite:///./data/polydictions.db` | Database connection URL |
| `API_HOST` | No | `0.0.0.0` | API server host |
| `API_PORT` | No | `8080` | API server port |
| `API_SECRET_KEY` | Yes* | - | Secret key for API authentication |
| `CHANNEL_ID` | No | - | Telegram channel ID for broadcasts |
| `LOG_LEVEL` | No | `INFO` | Logging level |
| `MONITOR_INTERVAL` | No | `60` | Event monitor interval (seconds) |
| `ALERT_CHECK_INTERVAL` | No | `30` | Price alert check interval (seconds) |
| `NEWS_CHECK_INTERVAL` | No | `300` | News check interval (seconds) |

*Required if using API features

## Project Structure

```
polydictions/
├── src/
│   ├── __init__.py
│   ├── main.py              # Application entry point
│   ├── api/
│   │   ├── __init__.py
│   │   └── server.py        # REST API server with auth
│   ├── bot/
│   │   ├── __init__.py
│   │   ├── bot.py           # Main bot class
│   │   ├── handlers/        # Command handlers
│   │   │   ├── common.py    # /start, /help, /pause, /resume
│   │   │   ├── deal.py      # /deal command
│   │   │   ├── watchlist.py # /watchlist, /watch
│   │   │   ├── alerts.py    # /alerts, /alert
│   │   │   └── filters.py   # /keywords, /categories
│   │   └── middlewares/     # Bot middlewares
│   │       ├── errors.py    # Error handling
│   │       ├── rate_limit.py# Rate limiting
│   │       └── database.py  # DB session injection
│   ├── config/
│   │   ├── __init__.py
│   │   ├── settings.py      # Pydantic settings
│   │   └── constants.py     # Application constants
│   ├── database/
│   │   ├── __init__.py
│   │   ├── models.py        # SQLAlchemy models
│   │   ├── connection.py    # Database connection
│   │   └── repository.py    # Data access layer
│   ├── services/
│   │   ├── __init__.py
│   │   ├── polymarket.py    # Polymarket API client
│   │   ├── event_monitor.py # New event monitoring
│   │   ├── alert_monitor.py # Price alert monitoring
│   │   └── news_monitor.py  # News monitoring
│   └── utils/
│       ├── __init__.py
│       ├── http.py          # HTTP client with proper SSL
│       ├── formatters.py    # Message formatting
│       ├── helpers.py       # Utility functions
│       └── validators.py    # Input validation
├── tests/
│   ├── __init__.py
│   ├── conftest.py          # Pytest fixtures
│   ├── unit/
│   │   ├── test_validators.py
│   │   ├── test_helpers.py
│   │   └── test_repository.py
│   └── integration/
│       └── __init__.py
├── migrations/              # Alembic migrations
├── data/                    # Database files (gitignored)
├── .env.example             # Environment template
├── .gitignore
├── .pre-commit-config.yaml  # Pre-commit hooks
├── docker-compose.yml       # Docker Compose config
├── Dockerfile               # Docker image
├── pyproject.toml           # Project configuration
└── README.md
```

## Development

### Setup Development Environment

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration
```

### Code Quality

```bash
# Format code
black src tests

# Lint code
ruff check src tests

# Type checking
mypy src
```

## API Usage

The bot exposes a REST API for external integrations.

### Authentication

All API requests require HMAC authentication:

```python
import hmac
import hashlib

user_id = "123456789"
secret_key = "your_api_secret_key"

auth_hash = hmac.new(
    secret_key.encode(),
    user_id.encode(),
    hashlib.sha256
).hexdigest()

# Include in request headers
headers = {
    "X-User-Id": user_id,
    "X-Auth-Hash": auth_hash
}
```

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check (no auth required) |
| GET | `/api/user/settings` | Get user settings |
| POST | `/api/user/settings` | Update user settings |
| GET | `/api/user/watchlist` | Get user watchlist |
| POST | `/api/user/watchlist` | Add to watchlist |
| DELETE | `/api/user/watchlist/{slug}` | Remove from watchlist |
| GET | `/api/user/alerts` | Get user alerts |
| POST | `/api/user/alerts` | Create alert |
| DELETE | `/api/user/alerts/{id}` | Delete alert |

## Usage Examples

### Analyze an Event
```
/deal https://polymarket.com/event/presidential-election-winner-2024
```

### Set Keyword Filters
```
/keywords btc, eth, crypto
/keywords "artificial intelligence", tech
/keywords clear
```

### Set Price Alerts
```
/alert btc-100k > 60
/alert election-2024 < 30
```

### Manage Watchlist
```
/watch presidential-election
/watchlist
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests and linting (`pytest && ruff check src`)
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

## License

This project is open source and available under the MIT License.

## Disclaimer

This bot is for informational purposes only. Always do your own research before making any predictions or financial decisions.
