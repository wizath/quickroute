#!/usr/bin/env python3
"""
QuickRoute Models Example

This example demonstrates Django-like model patterns and operations.
Shows how to work with model managers, queries, and relationships.
"""

import asyncio
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Boolean, Integer, DateTime, Text
from datetime import datetime

# Import from QuickRoute library
from quickroute import QuickRoute, UserManager, AsyncModelManager
from quickroute.database import Base
from quickroute.settings import BaseSettings


# 1. Configure Settings
class Settings(BaseSettings):
    """Settings for models example."""

    QUICKROUTE_TITLE = "QuickRoute Models Demo"
    QUICKROUTE_DESCRIPTION = "Demonstrating Django-like model patterns"
    QUICKROUTE_VERSION = "1.0.0"

    DATABASE_URL = "sqlite+aiosqlite:///./models_example.db"


# 2. Create Settings Instance
settings = Settings()


# 3. Define Custom Models
class Department(Base):
    """Department model example."""

    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Django-like manager
    objects = AsyncModelManager()

    def __str__(self):
        return self.name


class Employee(Base):
    """Employee model with foreign key relationship."""

    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(primary_key=True)
    first_name: Mapped[str] = mapped_column(String(50), nullable=False)
    last_name: Mapped[str] = mapped_column(String(50), nullable=False)
    email: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    phone: Mapped[str] = mapped_column(String(20))
    hire_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    salary: Mapped[int] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    department_id: Mapped[int] = mapped_column(Integer, nullable=False)

    # Django-like manager
    objects = AsyncModelManager()

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def full_name(self):
        """Django-like property."""
        return f"{self.first_name} {self.last_name}"


class Project(Base):
    """Project model with many-to-many relationship."""

    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text)
    start_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    end_date: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    budget: Mapped[int] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Django-like manager
    objects = AsyncModelManager()

    def __str__(self):
        return self.name


# 4. Create QuickRoute App
app = QuickRoute(
    title="QuickRoute Models Demo", description="Demonstrating Django-like model patterns"
)


# 5. API Routes for Model Operations
from quickroute import Router

router = Router(prefix="/api", tags=["models"])


@router.get("/departments")
async def list_departments():
    """List all departments."""
    departments = await Department.objects.all()
    return {"departments": departments}


@router.post("/departments")
async def create_department(name: str, description: str):
    """Create a new department."""
    department = await Department.objects.create(name=name, description=description)
    return {"department": department, "message": "Department created successfully"}


@router.get("/employees")
async def list_employees(active_only: bool = True):
    """List employees with optional filtering."""
    if active_only:
        employees = await Employee.objects.filter(is_active=True).all()
    else:
        employees = await Employee.objects.all()

    return {"employees": employees}


@router.post("/employees")
async def create_employee(
    first_name: str, last_name: str, email: str, department_id: int, salary: int, phone: str = None
):
    """Create a new employee."""
    employee = await Employee.objects.create(
        first_name=first_name,
        last_name=last_name,
        email=email,
        phone=phone,
        department_id=department_id,
        salary=salary,
    )
    return {"employee": employee, "message": "Employee created successfully"}


@router.get("/employees/{employee_id}")
async def get_employee(employee_id: int):
    """Get a specific employee."""
    employee = await Employee.objects.get(id=employee_id)
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    return {"employee": employee}


@router.put("/employees/{employee_id}")
async def update_employee(employee_id: int, **kwargs):
    """Update an employee."""
    employee = await Employee.objects.get(id=employee_id)
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    # Update fields
    for field, value in kwargs.items():
        if hasattr(employee, field):
            setattr(employee, field, value)

    # In a real implementation, you'd save the changes
    return {"employee": employee, "message": "Employee updated successfully"}


@router.delete("/employees/{employee_id}")
async def delete_employee(employee_id: int):
    """Delete an employee (soft delete by setting inactive)."""
    employee = await Employee.objects.get(id=employee_id)
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    employee.is_active = False
    # In a real implementation, you'd save the changes
    return {"message": "Employee deactivated successfully"}


@router.get("/projects")
async def list_projects():
    """List all projects."""
    projects = await Project.objects.all()
    return {"projects": projects}


@router.get("/stats")
async def get_model_stats():
    """Get statistics for all models."""
    dept_count = await Department.objects.count()
    emp_count = await Employee.objects.filter(is_active=True).count()
    proj_count = await Project.objects.filter(is_active=True).count()

    return {"departments": dept_count, "active_employees": emp_count, "active_projects": proj_count}


# 6. Model Operations Demo
async def demonstrate_model_operations():
    """Demonstrate Django-like model operations."""
    print("\n📊 QuickRoute Model Operations Demo")
    print("=" * 50)

    # Create a user manager for user operations
    user_manager = UserManager()

    # 1. User Operations
    print("\n👤 User Operations:")
    try:
        # Create a demo user
        user = await user_manager.create_user(
            email="manager@example.com", password="demo123", is_active=True
        )
        print(f"✅ Created user: {user.email}")
    except:
        print("ℹ️  Demo user already exists")

    # 2. Department Operations
    print("\n🏢 Department Operations:")

    # Create departments
    departments = [
        {"name": "Engineering", "description": "Software development and IT"},
        {"name": "Marketing", "description": "Marketing and sales"},
        {"name": "HR", "description": "Human resources and recruitment"},
    ]

    for dept_data in departments:
        try:
            dept = await Department.objects.create(**dept_data)
            print(f"✅ Created department: {dept.name}")
        except:
            print(f"ℹ️  Department '{dept_data['name']}' already exists")

    # 3. Employee Operations
    print("\n👷 Employee Operations:")

    # Get departments for foreign key
    eng_dept = await Department.objects.filter(name="Engineering").first()
    if eng_dept:
        # Create employees
        employees = [
            {
                "first_name": "John",
                "last_name": "Doe",
                "email": "john@example.com",
                "department_id": eng_dept.id,
                "salary": 75000,
                "phone": "555-0101",
            },
            {
                "first_name": "Jane",
                "last_name": "Smith",
                "email": "jane@example.com",
                "department_id": eng_dept.id,
                "salary": 85000,
                "phone": "555-0102",
            },
        ]

        for emp_data in employees:
            try:
                emp = await Employee.objects.create(**emp_data)
                print(f"✅ Created employee: {emp.full_name}")
            except:
                print(
                    f"ℹ️  Employee '{emp_data['first_name']} {emp_data['last_name']}' already exists"
                )

    # 4. Query Operations
    print("\n🔍 Query Operations:")

    # Count operations
    dept_count = await Department.objects.count()
    emp_count = await Employee.objects.count()
    print(f"📊 Total departments: {dept_count}")
    print(f"👥 Total employees: {emp_count}")

    # Filter operations
    active_employees = await Employee.objects.filter(is_active=True).all()
    print(f"✅ Active employees: {len(active_employees)}")

    # Get operations
    eng_employees = await Employee.objects.filter(department_id=eng_dept.id).all()
    print(f"🔧 Engineering employees: {len(eng_employees)}")

    # 5. Project Operations
    print("\n📋 Project Operations:")

    projects = [
        {
            "name": "Website Redesign",
            "description": "Complete overhaul of company website",
            "budget": 50000,
        },
        {
            "name": "Mobile App",
            "description": "Native mobile application development",
            "budget": 100000,
        },
    ]

    for proj_data in projects:
        try:
            project = await Project.objects.create(**proj_data)
            print(f"✅ Created project: {project.name}")
        except:
            print(f"ℹ️  Project '{proj_data['name']}' already exists")

    print("\n🎯 Model Operations Summary:")
    print("✅ Django-like model creation")
    print("✅ Manager pattern implementation")
    print("✅ QuerySet-like operations")
    print("✅ Filter and get operations")
    print("✅ Foreign key relationships")
    print("✅ Model properties")
    print("✅ String representations")


# 7. Include Router
app.include_router(router)


# 8. Main Function
async def main():
    """Initialize database and demonstrate model operations."""
    # Create demo data and demonstrate operations
    await demonstrate_model_operations()

    print("\n🚀 QuickRoute Models Demo")
    print("=" * 40)
    print("📚 Available API endpoints:")
    print("  GET    /api/departments    - List all departments")
    print("  POST   /api/departments    - Create department")
    print("  GET    /api/employees     - List employees")
    print("  POST   /api/employees     - Create employee")
    print("  GET    /api/employees/{id} - Get employee")
    print("  PUT    /api/employees/{id} - Update employee")
    print("  DELETE /api/employees/{id} - Deactivate employee")
    print("  GET    /api/projects       - List projects")
    print("  GET    /api/stats          - Get statistics")
    print("\n📖 API docs: http://localhost:8000/docs")
    print("🚀 Running on http://localhost:8000")


if __name__ == "__main__":
    import uvicorn
    from fastapi import HTTPException

    # Run the demo
    asyncio.run(main())

    # Run the server
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=True)
