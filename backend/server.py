from fastapi import FastAPI, APIRouter, HTTPException, UploadFile, File, Form, Depends, WebSocket, WebSocketDisconnect
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
app = FastAPI(title="Civic Issue Reporting API")

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
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = "pending"  # pending, assigned, in_progress, resolved, closed
    priority: int = 1  # 1-5 scale
    severity_score: float = 0.0
    auto_routed_department_id: Optional[str] = None

class ReportCreate(BaseModel):
    title: str
    description: str
    location: str
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
        """Analyze issue description and image to determine department, priority, and issue type"""
        try:
            # Import here to avoid issues if emergentintegrations is not installed
            from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent
            
            # Create AI chat instance
            chat = LlmChat(
                api_key=self.gemini_api_key,
                session_id=f"analysis_{uuid.uuid4()}",
                system_message="""You are an AI assistant specialized in analyzing civic issues and municipal problems. 
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
                {
                  "department": "Department Name",
                  "issue_type": "specific issue category",
                  "priority": 3,
                  "severity_score": 0.7,
                  "reasoning": "Brief explanation of the analysis"
                }"""
            ).with_model("gemini", "gemini-2.0-flash")
            
            # Prepare message
            message_text = f"Analyze this civic issue: {description}"
            file_contents = []
            
            if image_base64:
                image_content = ImageContent(image_base64=image_base64)
                file_contents.append(image_content)
                message_text += "\n\nPlease also analyze the attached image to help with classification."
            
            user_message = UserMessage(
                text=message_text,
                file_contents=file_contents if file_contents else None
            )
            
            # Get AI response
            response = await chat.send_message(user_message)
            
            # Parse JSON response - handle markdown code blocks
            try:
                # Remove markdown code blocks if present
                clean_response = response.strip()
                if clean_response.startswith('```json'):
                    clean_response = clean_response[7:]  # Remove ```json
                if clean_response.endswith('```'):
                    clean_response = clean_response[:-3]  # Remove ```
                clean_response = clean_response.strip()
                
                analysis = json.loads(clean_response)
                return analysis
            except json.JSONDecodeError as e:
                logging.error(f"JSON parsing failed for response: {response[:200]}... Error: {e}")
                # Fallback if response is not proper JSON
                return {
                    "department": "Public Works Department",
                    "issue_type": "general",
                    "priority": 2,
                    "severity_score": 0.5,
                    "reasoning": f"AI analysis JSON parsing failed: {str(e)}"
                }
                
        except Exception as e:
            logging.error(f"AI analysis failed: {e}")
            # Fallback analysis
            return {
                "department": "Public Works Department",
                "issue_type": "general",
                "priority": 2,
                "severity_score": 0.5,
                "reasoning": f"AI analysis failed: {str(e)}"
            }

ai_service = AIAnalysisService()

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

# Report management
@api_router.post("/reports")
async def create_report(
    title: str = Form(...),
    description: str = Form(...),
    location: str = Form(...),
    user_id: str = Form(...),
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
    attachments = await db.attachments.find({"report_id": report_id}).to_list(100)
    
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
        "attachments": [Attachment(**att) for att in attachments],
        "history": [ReportHistory(**parse_from_mongo(hist)) for hist in history],
        "user": User(**parse_from_mongo(user)) if user else None,
        "department": Department(**department) if department else None
    }

@api_router.patch("/reports/{report_id}/status")
async def update_report_status(
    report_id: str,
    new_status: str = Form(...),
    actor_id: str = Form(...),
    note: str = Form("")
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
    
    # Add to history
    history = ReportHistory(
        report_id=report_id,
        actor_id=actor_id,
        old_status=old_status,
        new_status=new_status,
        note=note
    )
    history_mongo = prepare_for_mongo(history.dict())
    await db.report_history.insert_one(history_mongo)
    
    return {"message": "Status updated successfully"}

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

@app.on_event("startup")
async def startup_event():
    """Initialize departments on startup"""
    try:
        existing_count = await db.departments.count_documents({})
        if existing_count == 0:
            department_objects = [Department(**dept_data) for dept_data in DEPARTMENTS]
            department_dicts = [prepare_for_mongo(dept.dict()) for dept in department_objects]
            await db.departments.insert_many(department_dicts)
            logger.info(f"Initialized {len(DEPARTMENTS)} departments")
    except Exception as e:
        logger.error(f"Failed to initialize departments: {e}")

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()