from fastapi import FastAPI, APIRouter, HTTPException, UploadFile, File, Form, Depends, WebSocket, WebSocketDisconnect
from contextlib import asynccontextmanager
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
import uuid
from datetime import datetime, timezone
import base64
import io
from PIL import Image
import asyncio
import json

# Load environment variables
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ.get('DB_NAME', 'civic_reports')]

# Create the main app without a prefix
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    try:
        # Initialize departments
        existing_count = await db.departments.count_documents({})
        if existing_count == 0:
            department_objects = [Department(**dept_data) for dept_data in DEPARTMENTS]
            department_dicts = [prepare_for_mongo(dept.dict()) for dept in department_objects]
            await db.departments.insert_many(department_dicts)
            logger.info(f"Initialized {len(DEPARTMENTS)} departments")

        # Add demo users
        demo_users = [
            User(name="Alice", email="alice@example.com", role="citizen"),
            User(name="Bob", email="bob@example.com", role="citizen"),
        ]
        await db.users.insert_many([prepare_for_mongo(u.dict()) for u in demo_users])

        # Get department IDs
        departments = await db.departments.find().to_list(100)
        dept_map = {d["name"]: d["id"] for d in departments}

        # Add demo reports
        demo_reports = [
            # High priority
            Report(user_id=demo_users[0].id, title="Major Water Leak", description="Water is flooding the street.", location="Main St", latitude=28.6139, longitude=77.2090, issue_type="water leak", priority=5, severity_score=0.95, auto_routed_department_id=dept_map.get("Utilities Department")),
            # Medium priority
            Report(user_id=demo_users[1].id, title="Broken Streetlight", description="Streetlight not working.", location="Park Ave", latitude=28.6140, longitude=77.2091, issue_type="lighting", priority=3, severity_score=0.6, auto_routed_department_id=dept_map.get("Public Works Department")),
            Report(user_id=demo_users[0].id, title="Overflowing Garbage Bin", description="Garbage bin is overflowing.", location="Market Rd", latitude=28.6150, longitude=77.2092, issue_type="garbage", priority=3, severity_score=0.5, auto_routed_department_id=dept_map.get("Sanitation Department")),
            Report(user_id=demo_users[1].id, title="Pothole", description="Large pothole on the road.", location="Highway 1", latitude=28.6160, longitude=77.2093, issue_type="road damage", priority=3, severity_score=0.7, auto_routed_department_id=dept_map.get("Public Works Department")),
            # Low priority
            Report(user_id=demo_users[0].id, title="Graffiti on Wall", description="Graffiti spotted.", location="School St", latitude=28.6170, longitude=77.2094, issue_type="graffiti", priority=2, severity_score=0.3, auto_routed_department_id=dept_map.get("Code Enforcement")),
            Report(user_id=demo_users[1].id, title="Park Bench Broken", description="Bench in park is broken.", location="Central Park", latitude=28.6180, longitude=77.2095, issue_type="bench", priority=2, severity_score=0.2, auto_routed_department_id=dept_map.get("Parks & Recreation")),
            Report(user_id=demo_users[0].id, title="Tree Branch Fallen", description="Branch blocking sidewalk.", location="Elm St", latitude=28.6190, longitude=77.2096, issue_type="tree", priority=2, severity_score=0.4, auto_routed_department_id=dept_map.get("Public Works Department")),
            Report(user_id=demo_users[1].id, title="Dog Barking", description="Dog barking at night.", location="Maple St", latitude=28.6200, longitude=77.2097, issue_type="noise", priority=2, severity_score=0.1, auto_routed_department_id=dept_map.get("Code Enforcement")),
        ]
        await db.reports.insert_many([prepare_for_mongo(r.dict()) for r in demo_reports])
        logger.info("Demo issues added to database.")
    except Exception as e:
        logger.error(f"Failed to initialize departments or demo data: {e}")
    yield
    # Shutdown logic
    client.close()

app = FastAPI(title="Civic Issue Reporting API", lifespan=lifespan)

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Security
security = HTTPBearer()

# Pydantic Models
class User(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    email: str
    phone: Optional[str] = None
    role: str = "citizen"  # citizen, admin, department_staff
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class UserCreate(BaseModel):
    name: str
    email: str
    phone: Optional[str] = None
    role: str = "citizen"

class Department(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    contact_email: str
    geo_coverage_area: str
    
class Report(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    title: str
    description: str
    issue_type: str
    location: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = "pending"  # pending, assigned, in_progress, resolved, closed
    priority: int = 1  # 1-5 scale
    severity_score: float = 0.0
    auto_routed_department_id: Optional[str] = None

class ReportCreate(BaseModel):
    title: str
    description: str
    location: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    issue_type: Optional[str] = None

class Attachment(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    report_id: str
    file_url: str
    content_type: str
    size: int
    thumbnail_url: Optional[str] = None

class Assignment(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    report_id: str
    dept_id: str
    assigned_to: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ReportHistory(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    report_id: str
    actor_id: str
    old_status: str
    new_status: str
    note: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# Initialize departments on startup
DEPARTMENTS = [
    {"name": "Public Works Department", "contact_email": "publicworks@city.gov", "geo_coverage_area": "citywide"},
    {"name": "Sanitation Department", "contact_email": "sanitation@city.gov", "geo_coverage_area": "citywide"},
    {"name": "Utilities Department", "contact_email": "utilities@city.gov", "geo_coverage_area": "citywide"},
    {"name": "Planning & Zoning Department", "contact_email": "planning@city.gov", "geo_coverage_area": "citywide"},
    {"name": "Engineering & Construction", "contact_email": "engineering@city.gov", "geo_coverage_area": "citywide"},
    {"name": "Health Department", "contact_email": "health@city.gov", "geo_coverage_area": "citywide"},
    {"name": "Police Department", "contact_email": "police@city.gov", "geo_coverage_area": "citywide"},
    {"name": "Fire Department", "contact_email": "fire@city.gov", "geo_coverage_area": "citywide"},
    {"name": "Parks & Recreation", "contact_email": "parks@city.gov", "geo_coverage_area": "citywide"},
    {"name": "Code Enforcement", "contact_email": "codeenforcement@city.gov", "geo_coverage_area": "citywide"},
    {"name": "Emergency Management", "contact_email": "emergency@city.gov", "geo_coverage_area": "citywide"},
    {"name": "Information Technology", "contact_email": "it@city.gov", "geo_coverage_area": "citywide"},
    {"name": "Economic Development", "contact_email": "economic@city.gov", "geo_coverage_area": "citywide"},
    {"name": "Transportation Department", "contact_email": "transport@city.gov", "geo_coverage_area": "citywide"},
    {"name": "Environmental Services", "contact_email": "environment@city.gov", "geo_coverage_area": "citywide"}
]

# AI Analysis Service using Gemini
class AIAnalysisService:
    def __init__(self):
        self.gemini_api_key = os.environ.get('GEMINI_API_KEY')
        
    async def analyze_issue_with_ai(self, description: str, image_base64: Optional[str] = None):
        """Analyze issue description and image to determine department, priority, and issue type using Gemini API"""
        import httpx
        prompt = f"""
        You are an AI assistant specialized in analyzing civic issues and municipal problems.
        Your task is to analyze user-reported civic issues and provide structured output for municipal routing.
        Based on the description and image (if provided), you should:
        1. Identify the most appropriate municipal department
        2. Determine the priority level (1-5, where 5 is most urgent)
        3. Classify the issue type
        4. Calculate a severity score (0.0-1.0)
        Available departments:
        - Public Works Department (roads, infrastructure, drainage)
        - Sanitation Department (garbage, waste, cleanliness)
        - Utilities Department (water, electricity, utilities)
        - Planning & Zoning Department (permits, zoning, development)
        - Engineering & Construction (construction issues, building problems)
        - Health Department (health hazards, public health)
        - Police Department (safety, security, crime)
        - Fire Department (fire hazards, emergency situations)
        - Parks & Recreation (parks, recreational facilities)
        - Code Enforcement (violations, code compliance)
        - Emergency Management (disasters, emergencies)
        - Information Technology (technology issues)
        - Economic Development (business, economic issues)
        - Transportation Department (traffic, transportation)
        - Environmental Services (environmental issues, pollution)
        Respond ONLY with JSON in this exact format:
        {{
          "department": "Department Name",
          "issue_type": "specific issue category",
          "priority": 3,
          "severity_score": 0.7,
          "reasoning": "Brief explanation of the analysis"
        }}
        """
        if image_base64:
            prompt += "\n\nImage (base64): " + image_base64
        prompt += f"\n\nDescription: {description}"

        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent"
        headers = {"Content-Type": "application/json"}
        api_key = self.gemini_api_key
        payload = {
            "contents": [{"parts": [{"text": prompt}]}]
        }
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(f"{url}?key={api_key}", json=payload, headers=headers, timeout=30)
                response.raise_for_status()
                data = response.json()
                # Extract the model's reply
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                clean_response = text.strip()
                if clean_response.startswith('```json'):
                    clean_response = clean_response[7:]
                if clean_response.endswith('```'):
                    clean_response = clean_response[:-3]
                clean_response = clean_response.strip()
                analysis = json.loads(clean_response)
                return analysis
        except Exception as e:
            logging.error(f"Gemini API analysis failed: {e}")
            return {
                "department": "Public Works Department",
                "issue_type": "general",
                "priority": 2,
                "severity_score": 0.5,
                "reasoning": f"Gemini API analysis failed: {str(e)}"
            }

ai_service = AIAnalysisService()

# WebSocket Connection Manager for real-time notifications
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
        
    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)
        
    def disconnect(self, websocket: WebSocket, user_id: str):
        if user_id in self.active_connections:
            self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
    
    async def send_personal_message(self, message: str, user_id: str):
        if user_id in self.active_connections:
            disconnected = []
            for connection in self.active_connections[user_id]:
                try:
                    await connection.send_text(message)
                except:
                    disconnected.append(connection)
            # Remove disconnected connections
            for conn in disconnected:
                self.active_connections[user_id].remove(conn)
    
    async def broadcast_to_admins(self, message: str):
        # Send to all admin users (in a real app, you'd track admin user IDs)
        admin_user_ids = ["admin_123"]  # Mock admin IDs
        for admin_id in admin_user_ids:
            await self.send_personal_message(message, admin_id)
    
    async def broadcast_all(self, message: str):
        for user_connections in self.active_connections.values():
            disconnected = []
            for connection in user_connections:
                try:
                    await connection.send_text(message)
                except:
                    disconnected.append(connection)
            # Remove disconnected connections
            for conn in disconnected:
                user_connections.remove(conn)

manager = ConnectionManager()

# Utility functions
def prepare_for_mongo(data):
    """Prepare data for MongoDB storage"""
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, datetime):
                data[key] = value.isoformat()
    return data

def parse_from_mongo(item):
    """Parse data from MongoDB"""
    if isinstance(item, dict):
        for key, value in item.items():
            if key.endswith('_at') and isinstance(value, str):
                try:
                    item[key] = datetime.fromisoformat(value)
                except:
                    pass
    return item

# API Routes
@api_router.get("/")
async def root():
    return {"message": "Civic Issue Reporting API"}

# User management
@api_router.post("/users", response_model=User)
async def create_user(user_data: UserCreate):
    user_dict = user_data.dict()
    user = User(**user_dict)
    user_mongo = prepare_for_mongo(user.dict())
    await db.users.insert_one(user_mongo)
    return user

@api_router.get("/users", response_model=List[User])
async def get_users():
    users = await db.users.find().to_list(1000)
    return [User(**parse_from_mongo(user)) for user in users]

@api_router.get("/users/{user_id}", response_model=User)
async def get_user(user_id: str):
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return User(**parse_from_mongo(user))

# Department management
@api_router.get("/departments", response_model=List[Department])
async def get_departments():
    departments = await db.departments.find().to_list(1000)
    return [Department(**dept) for dept in departments]

@api_router.post("/departments/initialize")
async def initialize_departments():
    """Initialize default departments"""
    existing_count = await db.departments.count_documents({})
    if existing_count == 0:
        department_objects = [Department(**dept_data) for dept_data in DEPARTMENTS]
        department_dicts = [prepare_for_mongo(dept.dict()) for dept in department_objects]
        await db.departments.insert_many(department_dicts)
        return {"message": f"Initialized {len(DEPARTMENTS)} departments"}
    return {"message": "Departments already initialized"}

# WebSocket endpoint for real-time notifications
@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    await manager.connect(websocket, user_id)
    try:
        while True:
            # Keep connection alive
            data = await websocket.receive_text()
            # Echo back for connection testing
            await websocket.send_text(f"Message received: {data}")
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)

# Report management
@api_router.post("/reports")
async def create_report(
    title: str = Form(...),
    description: str = Form(...),
    location: str = Form(...),
    user_id: str = Form(...),
    latitude: Optional[float] = Form(None),
    longitude: Optional[float] = Form(None),
    issue_type: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None)
):
    """Create a new report with optional image analysis"""
    
    # Handle image upload and analysis
    image_base64 = None
    attachment_id = None
    
    if image:
        # Read and process image
        image_content = await image.read()
        image_base64 = base64.b64encode(image_content).decode('utf-8')
        
        # Store attachment
        attachment = Attachment(
            report_id="temp",  # Will be updated after report creation
            file_url=f"data:{image.content_type};base64,{image_base64}",
            content_type=image.content_type,
            size=len(image_content)
        )
        attachment_id = attachment.id
    
    # AI Analysis
    ai_analysis = await ai_service.analyze_issue_with_ai(description, image_base64)
    
    # Find department by name
    department = await db.departments.find_one({"name": ai_analysis["department"]})
    department_id = department["id"] if department else None
    
    # Create report
    report_data = {
        "user_id": user_id,
        "title": title,
        "description": description,
        "location": location,
        "latitude": latitude,
        "longitude": longitude,
        "issue_type": ai_analysis["issue_type"],
        "priority": ai_analysis["priority"],
        "severity_score": ai_analysis["severity_score"],
        "auto_routed_department_id": department_id
    }
    
    report = Report(**report_data)
    report_mongo = prepare_for_mongo(report.dict())
    await db.reports.insert_one(report_mongo)
    
    # Update and store attachment if exists
    if attachment_id and image:
        attachment.report_id = report.id
        attachment_mongo = prepare_for_mongo(attachment.dict())
        await db.attachments.insert_one(attachment_mongo)
    
    # Create initial report history
    history = ReportHistory(
        report_id=report.id,
        actor_id=user_id,
        old_status="",
        new_status="pending",
        note=f"Report created. AI Analysis: {ai_analysis['reasoning']}"
    )
    history_mongo = prepare_for_mongo(history.dict())
    await db.report_history.insert_one(history_mongo)
    
    # Send real-time notification to user
    user_notification = {
        "type": "report_created",
        "message": f"Your report '{title}' has been submitted and analyzed",
        "report_id": report.id,
        "priority": ai_analysis["priority"],
        "department": ai_analysis["department"]
    }
    await manager.send_personal_message(json.dumps(user_notification), user_id)
    
    # Send real-time notification to admins for high priority reports
    if ai_analysis["priority"] >= 4:
        admin_notification = {
            "type": "high_priority_report",
            "message": f"High priority report: {title}",
            "report_id": report.id,
            "priority": ai_analysis["priority"],
            "location": location,
            "department": ai_analysis["department"]
        }
        await manager.broadcast_to_admins(json.dumps(admin_notification))
    
    return {
        "report": report,
        "ai_analysis": ai_analysis,
        "message": "Report created successfully"
    }

@api_router.get("/reports", response_model=List[Report])
async def get_reports(
    user_id: Optional[str] = None,
    status: Optional[str] = None,
    department_id: Optional[str] = None,
    limit: int = 50
):
    """Get reports with optional filtering"""
    query = {}
    
    if user_id:
        query["user_id"] = user_id
    if status:
        query["status"] = status
    if department_id:
        query["auto_routed_department_id"] = department_id
    
    reports = await db.reports.find(query).sort("created_at", -1).limit(limit).to_list(limit)
    return [Report(**parse_from_mongo(report)) for report in reports]

@api_router.get("/reports/{report_id}")
async def get_report(report_id: str):
    """Get detailed report with attachments and history"""
    report = await db.reports.find_one({"id": report_id})
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    # Get attachments
    attachment_docs = await db.attachments.find({"report_id": report_id}).to_list(100)
    attachments = []
    for att in attachment_docs:
        clean_attachment = {k: v for k, v in att.items() if k != "_id"}
        attachments.append(Attachment(**clean_attachment))
    
    # Get history
    history = await db.report_history.find({"report_id": report_id}).sort("created_at", 1).to_list(100)
    
    # Get user info
    user = await db.users.find_one({"id": report["user_id"]})
    
    # Get department info
    department = None
    if report.get("auto_routed_department_id"):
        department = await db.departments.find_one({"id": report["auto_routed_department_id"]})
    
    return {
        "report": Report(**parse_from_mongo(report)),
        "attachments": attachments,
        "history": [ReportHistory(**parse_from_mongo(hist)) for hist in history],
        "user": User(**parse_from_mongo(user)) if user else None,
        "department": Department(**department) if department else None
    }

@api_router.patch("/reports/{report_id}/status")
async def update_report_status(
    report_id: str,
    new_status: str = Form(...),
    actor_id: str = Form(...),
    note: str = Form(""),
    resolution_image: Optional[UploadFile] = File(None)
):
    """Update report status"""
    report = await db.reports.find_one({"id": report_id})
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    old_status = report["status"]
    
    # Update report
    await db.reports.update_one(
        {"id": report_id},
        {"$set": {"status": new_status}}
    )

    # Store resolution attachment if provided
    attachment = None
    if resolution_image:
        file_bytes = await resolution_image.read()
        if file_bytes:
            encoded_file = base64.b64encode(file_bytes).decode("utf-8")
            attachment = Attachment(
                report_id=report_id,
                file_url=f"data:{resolution_image.content_type};base64,{encoded_file}",
                content_type=resolution_image.content_type,
                size=len(file_bytes)
            )
            attachment_mongo = prepare_for_mongo(attachment.dict())
            await db.attachments.insert_one(attachment_mongo)

    history_note = note.strip()
    if attachment:
        proof_note = "Proof attachment uploaded."
        history_note = f"{history_note} {proof_note}".strip() if history_note else proof_note

    # Add to history
    history = ReportHistory(
        report_id=report_id,
        actor_id=actor_id,
        old_status=old_status,
        new_status=new_status,
        note=history_note
    )
    history_mongo = prepare_for_mongo(history.dict())
    await db.report_history.insert_one(history_mongo)

    # Send real-time notification to report owner
    status_notification = {
        "type": "status_update",
        "message": f"Your report status changed from {old_status} to {new_status}",
        "report_id": report_id,
        "old_status": old_status,
        "new_status": new_status,
        "note": history_note
    }
    await manager.send_personal_message(json.dumps(status_notification), report["user_id"])
    
    return {"message": "Status updated successfully"}

@api_router.get("/reports/map")
async def get_reports_for_map():
    """Get reports with coordinates for map display"""
    reports = await db.reports.find({
        "latitude": {"$exists": True, "$ne": None},
        "longitude": {"$exists": True, "$ne": None}
    }).to_list(1000)
    
    map_reports = []
    for report in reports:
        # Get user info
        user = await db.users.find_one({"id": report["user_id"]})
        # Get department info
        department = None
        if report.get("auto_routed_department_id"):
            department = await db.departments.find_one({"id": report["auto_routed_department_id"]})
        
        map_reports.append({
            "id": report["id"],
            "title": report["title"],
            "description": report["description"],
            "location": report["location"],
            "latitude": report["latitude"],
            "longitude": report["longitude"],
            "status": report["status"],
            "priority": report["priority"],
            "issue_type": report["issue_type"],
            "created_at": report["created_at"],
            "user_name": user["name"] if user else "Unknown",
            "department_name": department["name"] if department else "Unassigned"
        })
    
    return map_reports

@api_router.get("/dashboard/stats")
async def get_dashboard_stats():
    """Get dashboard statistics"""
    total_reports = await db.reports.count_documents({})
    pending_reports = await db.reports.count_documents({"status": "pending"})
    resolved_reports = await db.reports.count_documents({"status": "resolved"})
    in_progress_reports = await db.reports.count_documents({"status": "in_progress"})
    
    # Get recent resolved reports
    recent_resolved = await db.reports.find(
        {"status": "resolved"}
    ).sort("created_at", -1).limit(10).to_list(10)
    
    # Get high priority pending reports
    high_priority = await db.reports.find(
        {"status": {"$in": ["pending", "assigned"]}, "priority": {"$gte": 4}}
    ).sort("priority", -1).limit(10).to_list(10)
    
    return {
        "total_reports": total_reports,
        "pending_reports": pending_reports,
        "resolved_reports": resolved_reports,
        "in_progress_reports": in_progress_reports,
        "recent_resolved": [Report(**parse_from_mongo(r)) for r in recent_resolved],
        "high_priority": [Report(**parse_from_mongo(r)) for r in high_priority]
    }

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)