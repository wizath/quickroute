# QuickRoute 🚀

QuickRoute is a Django-like async web framework built with FastAPI that brings Django's simplicity and elegance to FastAPI's performance and flexibility.

## ✨ Features

- **🏗️ Django-like Patterns**: Familiar models, managers, settings, and middleware
- **⚡ Async by Default**: Built on FastAPI and SQLAlchemy 2.0 with full async support
- **🔐 Built-in Authentication**: JWT-based auth with Django-like user model
- **🌐 WebSocket Support**: Built-in WebSocket system with rooms and broadcasting
- **⏰ Periodic Jobs**: Decorator-based job scheduling system
- **🔌 Plugin System**: Extensible architecture with optional Celery integration
- **🎛️ Admin Panel**: Auto-generated admin interface with JWT authentication
- **🧪 Testing Ready**: Comprehensive testing framework with fixtures
- **🛠️ CLI Tools**: Django-like management commands

## 🚀 Quick Start

### Installation

```bash
# Install QuickRoute
pip install quickroute

# Or install with optional dependencies
pip install quickroute[celery]  # For Celery integration
pip install quickroute[postgres]  # For PostgreSQL support
pip install quickroute[all]      # Install all optional dependencies
```

### Create Your First Project

```bash
# Create a new QuickRoute project
quickroute startproject myproject

# Navigate to your project
cd myproject

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env

# Run the development server
python manage.py runserver
```

### Access Your Application

- **API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **Admin Panel**: http://localhost:8000/admin (after creating superuser)

## 📚 Examples

The `examples/` directory contains comprehensive examples showcasing QuickRoute features:

```bash
cd examples

# Basic app with models, auth, and routes
python basic_app.py

# Admin panel with JWT authentication
python admin_example.py

# Django-like model patterns and operations
python models_example.py

# Complete JWT authentication system
python auth_example.py
```

## 📊 Key Features

### Django-like Models
```python
from fastdjango import QuickRouteModel, User

class BlogPost(QuickRouteModel):
    title = models.CharField(max_length=200)
    content = models.TextField()
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    # Django-like manager
    objects = AsyncModelManager()

    def __str__(self):
        return self.title
```

### JWT Authentication
```python
from fastdjango import create_access_token, get_current_user

@router.post("/login")
async def login(email: str, password: str):
    user = await authenticate_user(email, password)
    token_data = create_access_token(user.id)
    return {"access_token": token_data["token"]}

@router.get("/protected")
async def protected_route(user: User = Depends(get_current_user)):
    return {"message": f"Hello {user.email}!"}
```

### Admin Panel
```python
from fastdjango import setup_admin

# Set up admin with JWT authentication
admin = setup_admin(app, engine, use_jwt_auth=True)

# Access at http://localhost:8000/admin
```

### Periodic Jobs
```python
from fastdjango import periodic

@periodic("every 5 minutes")
async def cleanup_data():
    """Clean up old data every 5 minutes."""
    # Your cleanup logic here
    return {"cleaned": True}
```

### WebSocket Support
```python
from fastdjango import websocket, websocket_room

@websocket("/ws/echo")
async def echo_websocket(websocket, connection):
    await connection.send_json({"type": "welcome"})
    while True:
        data = await connection.receive_json()
        await connection.send_json({"type": "echo", "data": data})
```

## 🔧 Management Commands

QuickRoute provides Django-like commands:

```bash
# Development server
python manage.py runserver

# Database migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Interactive shell
python manage.py shell

# Periodic jobs
python manage.py runjobs
python manage.py list_jobs

# WebSocket management
python manage.py websocket-status

# Plugin management
python manage.py list-plugins
```

## 🎯 Project Structure

```
myproject/
├── app/                           # Main application package
│   ├── models.py               # Database models
│   ├── routers.py              # API routes
│   ├── middleware.py            # Custom middleware
│   ├── main.py                 # FastAPI application setup
│   ├── settings.py             # Application configuration
│   └── database.py             # Database configuration
├── alembic/                      # Database migrations
├── tests/                        # Test suite
├── templates/                    # HTML templates
├── static/                       # Static files
├── requirements.txt              # Python dependencies
├── .env.example                 # Environment variables template
└── manage.py                    # Django-like management script
```

## 🔐 Configuration

Django-like settings with environment variables:

```python
# app/settings.py
from pydantic_settings import BaseSettings

class BaseSettings(BaseSettings):
    SECRET_KEY: str = "your-secret-key"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./db.sqlite"

    # JWT
    JWT_SECRET_KEY: str = "your-jwt-secret"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Optional features
    ENABLE_ADMIN: bool = True
    USE_CELERY: bool = False
```

## 🚀 Deployment

### Production Deployment

```bash
# Install production dependencies
pip install quickroute[postgres]

# Configure production settings
export DJANGO_SETTINGS_MODULE=myproject.settings.Production
export SECRET_KEY=your-production-secret-key
export DATABASE_URL=postgresql://user:password@localhost/dbname

# Run migrations
python manage.py migrate

# Run with Gunicorn
gunicorn app.main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker
```

### Docker Deployment

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y gcc

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Run migrations
RUN python manage.py migrate

# Run the application
CMD ["gunicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## 🛠️ Development

### Local Development

```bash
# Install in development mode
git clone https://github.com/fastdjango/fastdjango.git
cd fastdjango
pip install -e .

# Run the examples
cd examples
python basic_app.py
```

### Testing

```bash
# Run tests
python manage.py test

# Run with coverage
python manage.py test --coverage
```

## 📖 Documentation

- **Examples**: [examples/](examples/)
- **API Reference**: [https://docs.fastdjango.dev](https://docs.fastdjango.dev)
- **GitHub**: [QuickRoute Repository](https://github.com/fastdjango/fastdjango)

## 🤝 Contributing

Contributions are welcome! Please read our contributing guidelines and submit pull requests.

## 📄 License

QuickRoute is licensed under the MIT License.

---

🚀 **Happy coding with QuickRoute!**