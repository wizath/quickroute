# QuickRoute Quick Deploy Guide

## Minimal Single-File PostgreSQL Deployment

### Option 1: Local Development (SQLite)

```bash
# Install QuickRoute
pip install quickroute

# Run the app
python minimal_postgres.py

# Visit http://localhost:8000
```

The app automatically uses SQLite for local development.

---

### Option 2: Local with PostgreSQL

```bash
# Install with PostgreSQL support
pip install quickroute[postgres]

# Start PostgreSQL (using Docker)
docker run -d \
  --name postgres \
  -e POSTGRES_USER=fastdjango \
  -e POSTGRES_PASSWORD=fastdjango123 \
  -e POSTGRES_DB=fastdjango \
  -p 5432:5432 \
  postgres:15-alpine

# Set environment variables
export DATABASE_URL="postgresql+asyncpg://fastdjango:fastdjango123@localhost:5432/fastdjango"
export SECRET_KEY="your-secret-key-here"

# Run the app
python minimal_postgres.py
```

---

### Option 3: Docker Compose (Recommended)

```bash
# Start everything (app + PostgreSQL)
docker-compose up -d

# View logs
docker-compose logs -f

# Stop everything
docker-compose down

# Stop and remove data
docker-compose down -v
```

App runs on http://localhost:8000

---

### Option 4: Production Deployment (Railway, Render, Fly.io)

#### Railway.app

```bash
# Install Railway CLI
npm i -g @railway/cli

# Login
railway login

# Initialize project
railway init

# Add PostgreSQL
railway add postgresql

# Set environment variables
railway variables set SECRET_KEY=your-secret-key-here

# Deploy
railway up
```

#### Render.com

1. Create new Web Service
2. Connect your repo
3. Set build command: `pip install quickroute[postgres]`
4. Set start command: `python minimal_postgres.py`
5. Add PostgreSQL database
6. Set environment variables:
   - `DATABASE_URL` (auto-set by Render)
   - `SECRET_KEY`

#### Fly.io

```bash
# Install flyctl
curl -L https://fly.io/install.sh | sh

# Login
fly auth login

# Launch app
fly launch

# Add PostgreSQL
fly postgres create

# Attach database
fly postgres attach

# Deploy
fly deploy
```

---

### Environment Variables

```bash
# Required for production
SECRET_KEY=your-random-secret-key-minimum-32-characters

# Database (auto-configured by platforms)
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db

# Optional
PORT=8000
DEBUG=False
```

---

### Testing the API

#### Register a user
```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"password123"}'
```

#### Login
```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"password123"}'
```

#### Create a post
```bash
curl -X POST http://localhost:8000/posts \
  -H "Content-Type: application/json" \
  -d '{"title":"Hello World","content":"My first post"}'
```

#### List posts
```bash
curl http://localhost:8000/posts
```

---

### Adding Features

The minimal example is just a starting point. Extend it by:

1. **Add more models** - Just define SQLAlchemy models
2. **Add authentication** - Already has JWT auth built-in
3. **Add admin panel** - Import and configure SQLAdmin
4. **Add WebSockets** - Use QuickRoute's WebSocket support
5. **Add background jobs** - Use QuickRoute's job system
6. **Add file uploads** - Use FastAPI's UploadFile

---

### Migrations

For production, use Alembic for database migrations:

```bash
# Initialize Alembic
alembic init alembic

# Create migration
alembic revision --autogenerate -m "Initial migration"

# Apply migration
alembic upgrade head
```

Or use the QuickRoute CLI:

```bash
quickroute migrate "Initial migration"
```

---

### Security Checklist

Before deploying to production:

- ✅ Set strong `SECRET_KEY` (32+ random characters)
- ✅ Use environment variables for secrets
- ✅ Set `DEBUG=False`
- ✅ Use HTTPS (most platforms provide this)
- ✅ Configure CORS if needed
- ✅ Set up database backups
- ✅ Enable connection pooling for PostgreSQL
- ✅ Monitor your application

---

### Performance Tips

1. **Connection Pooling** - PostgreSQL handles this automatically with asyncpg
2. **Caching** - Add Redis for caching frequently accessed data
3. **CDN** - Use CDN for static files
4. **Database Indexes** - Add indexes to frequently queried columns
5. **Background Tasks** - Use Celery or QuickRoute jobs for long-running tasks

---

### Troubleshooting

**Database connection errors:**
```bash
# Check PostgreSQL is running
docker ps

# Check connection string
echo $DATABASE_URL

# Test connection
psql $DATABASE_URL
```

**Module not found:**
```bash
# Make sure QuickRoute is installed with PostgreSQL support
pip install quickroute[postgres]
```

**Port already in use:**
```bash
# Use different port
export PORT=8001
python minimal_postgres.py
```