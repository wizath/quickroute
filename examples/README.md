# QuickRoute Examples

This directory contains examples showcasing the features of the QuickRoute library.

## 🚀 Quick Start

```bash
# Install QuickRoute
pip install quickroute

# Run the basic example
cd examples
python basic_app.py
```

## 📁 Examples

### 1. `minimal_postgres.py` ⭐ **START HERE**
- **Single-file production-ready app**
- PostgreSQL support with SQLite fallback
- JWT authentication built-in
- Docker deployment ready
- **Perfect for quick deploys to Railway, Render, Fly.io**
- See [DEPLOY.md](DEPLOY.md) for deployment guide

### 2. `basic_app.py`
- Basic QuickRoute application setup
- User model with Django-like managers
- JWT authentication endpoints
- Simple API routes

### 3. `admin_example.py`
- SQLAdmin integration with JWT authentication
- User management interface
- Django-like admin panel

### 4. `models_example.py`
- Django-like model definitions
- Model managers and queries
- CRUD operations

### 5. `auth_example.py`
- JWT authentication system
- User registration and login
- Protected routes

### 6. `test_example.py`
- Testing with QuickRoute test framework
- Unit and integration tests
- Database fixtures

## 🔧 Running Examples

### Quick Start (Minimal PostgreSQL Example)

```bash
# Install with PostgreSQL support
pip install quickroute[postgres]

# Run locally (uses SQLite)
python minimal_postgres.py

# Run with PostgreSQL
export DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/db
export SECRET_KEY=your-secret-key
python minimal_postgres.py

# Or use Docker Compose
docker-compose up
```

### Other Examples

Each example can be run independently:

```bash
# Run basic app
python basic_app.py

# Run admin example
python admin_example.py

# Run models example
python models_example.py

# Run auth example
python auth_example.py

# Run tests
python test_example.py
```

## 📚 What You'll Learn

- **Django-like Patterns**: Models, managers, settings
- **JWT Authentication**: Secure token-based auth
- **Admin Panel**: SQLAdmin with JWT integration
- **Async Operations**: Modern async/await patterns
- **FastAPI Integration**: Best of both worlds
- **Production Deployment**: PostgreSQL, Docker, Cloud platforms

## 🚀 Production Deployment

The minimal example is production-ready! Deploy to:

- **Railway** - `railway up` (see [DEPLOY.md](DEPLOY.md))
- **Render** - Connect repo, auto-deploy
- **Fly.io** - `fly launch && fly deploy`
- **Docker** - `docker-compose up`
- **Any VPS** - Just needs Python 3.10+

See [DEPLOY.md](DEPLOY.md) for complete deployment guide with examples for all platforms.

## 🛠️ Requirements

```bash
# Minimal install
pip install quickroute

# With PostgreSQL support
pip install quickroute[postgres]

# Everything (admin, postgres, celery, etc.)
pip install quickroute[all]
```

This installs all optional dependencies including:
- SQLAdmin for admin panel
- PostgreSQL and MySQL drivers
- Celery for background jobs

Enjoy building with QuickRoute! 🚀