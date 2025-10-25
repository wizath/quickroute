# QuickRoute Tests

Comprehensive test suite for the QuickRoute library.

## Test Structure

```
tests/
├── conftest.py              # Shared pytest fixtures
├── test_auth.py             # Authentication tests
├── test_framework.py        # Framework base tests
├── test_jobs.py             # Job system tests
├── test_managers.py         # Model manager tests
├── test_middleware.py       # Middleware tests
├── test_models.py           # Model tests
├── test_integration.py      # ✨ Integration tests
└── test_cli_integration.py  # ✨ CLI integration tests
```

## Running Tests

### Run All Tests

```bash
# Using pytest directly
pytest

# Using fastdjango CLI
quickroute test
```

### Run Unit Tests Only

```bash
pytest -m unit
```

### Run Integration Tests Only

```bash
pytest -m integration
```

### Run Specific Test File

```bash
pytest tests/test_integration.py
pytest tests/test_cli_integration.py
```

### Run With Coverage

```bash
pytest --cov=fastdjango --cov-report=html --cov-report=term-missing
```

### Run Verbose

```bash
pytest -v
pytest -vv  # Extra verbose
```

### Run Parallel (faster)

```bash
pytest -n auto  # Requires pytest-xdist
```

## Test Markers

Tests are organized with markers for easy filtering:

- `@pytest.mark.unit` - Unit tests
- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.auth` - Authentication tests
- `@pytest.mark.database` - Database tests
- `@pytest.mark.api` - API endpoint tests
- `@pytest.mark.cli` - CLI command tests
- `@pytest.mark.slow` - Slow tests (excluded by default)

### Run Tests by Marker

```bash
# Run all auth tests
pytest -m auth

# Run all database tests
pytest -m database

# Run all API tests
pytest -m api

# Run all CLI tests
pytest -m cli

# Exclude slow tests
pytest -m "not slow"

# Run only integration tests
pytest -m integration
```

## Integration Tests

### What They Test

**test_integration.py** - Full application integration:
- Application lifecycle (startup/shutdown)
- Database integration (SQLite, PostgreSQL ready)
- API endpoint workflows
- Authentication flows (register -> login -> access)
- Protected endpoints with JWT
- Model CRUD operations
- Complete blog API workflow

**test_cli_integration.py** - CLI commands:
- `quickroute version`
- `quickroute test`
- `quickroute startproject`
- Project scaffolding
- Test runner with markers and options

### Running Integration Tests

```bash
# Run all integration tests
pytest -m integration

# Run with verbose output
pytest -m integration -v

# Run specific integration test
pytest tests/test_integration.py::TestFullApplicationFlow::test_complete_blog_api_flow -v

# Run CLI tests
pytest -m cli
```

## Database Tests

### SQLite (default)

All tests use in-memory SQLite by default:

```bash
pytest -m database
```

### PostgreSQL (optional)

To test with PostgreSQL:

```bash
# Start PostgreSQL
docker run -d --name test-postgres \
  -e POSTGRES_USER=test \
  -e POSTGRES_PASSWORD=test \
  -e POSTGRES_DB=test \
  -p 5432:5432 \
  postgres:15-alpine

# Set environment variable
export TEST_DATABASE_URL="postgresql+asyncpg://test:test@localhost:5432/test"

# Run database tests
pytest -m database
```

## Continuous Integration

### GitHub Actions

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:15-alpine
        env:
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
          POSTGRES_DB: test
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -e .[dev,postgres]

      - name: Run unit tests
        run: pytest -m "unit" --cov=fastdjango

      - name: Run integration tests
        run: pytest -m "integration" --cov=fastdjango --cov-append

      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

## Writing Tests

### Unit Test Example

```python
import pytest

@pytest.mark.unit
def test_simple_function():
    from fastdjango.app.auth import hash_password
    hashed = hash_password("password123")
    assert hashed != "password123"
    assert len(hashed) > 20
```

### Integration Test Example

```python
import pytest
from fastdjango import QuickRoute

@pytest.mark.integration
@pytest.mark.asyncio
async def test_api_endpoint():
    app = QuickRoute(title="Test")

    @app.get("/test")
    async def test_route():
        return {"message": "ok"}

    from fastapi.testclient import TestClient
    client = TestClient(app)

    response = client.get("/test")
    assert response.status_code == 200
    assert response.json() == {"message": "ok"}
```

### Database Test Example

```python
import pytest

@pytest.mark.database
@pytest.mark.asyncio
async def test_user_crud(test_db):
    from fastdjango import User
    from fastdjango.app.auth import get_password_hash

    # Create
    user = User(
        email="test@example.com",
        hashed_password=get_password_hash("pass123"),
        is_active=True
    )
    test_db.add(user)
    await test_db.commit()
    await test_db.refresh(user)

    # Read
    assert user.id is not None
    assert user.email == "test@example.com"
```

## Test Coverage

Check test coverage:

```bash
# Generate HTML coverage report
pytest --cov=fastdjango --cov-report=html

# Open in browser
open htmlcov/index.html
```

Target coverage: **80%+**

## Debugging Tests

```bash
# Run with Python debugger
pytest --pdb

# Stop on first failure
pytest -x

# Show local variables on failure
pytest -l

# Run specific test with extra verbosity
pytest tests/test_integration.py::TestAPIIntegration::test_authentication_flow -vv -s
```

## Performance Testing

```bash
# Show slowest tests
pytest --durations=10

# Profile test execution
pytest --profile

# Run only fast tests
pytest -m "not slow"
```

## Test Data

Tests use:
- In-memory SQLite databases (fast, isolated)
- Temporary directories for file operations
- Mock objects for external dependencies
- Fixture data in `conftest.py`

## Contributing

When adding new features:

1. Write unit tests for individual functions
2. Write integration tests for workflows
3. Add appropriate markers
4. Ensure tests pass: `pytest`
5. Check coverage: `pytest --cov=fastdjango`
6. Run integration tests: `pytest -m integration`

## Troubleshooting

**Tests fail with database errors:**
```bash
# Clear test cache
pytest --cache-clear
rm -rf .pytest_cache
```

**Import errors:**
```bash
# Reinstall in development mode
pip install -e .[dev]
```

**Slow tests:**
```bash
# Run in parallel
pip install pytest-xdist
pytest -n auto
```