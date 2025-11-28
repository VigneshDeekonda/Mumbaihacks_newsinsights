import os
import json
import asyncio
from datetime import datetime
from typing import List, Optional
from dotenv import load_dotenv
import pandas as pd
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from supabase import create_client, Client
import joblib
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

# Import agent logic functions and variables
from backend.agents.scout_agent import ScoutAgent
from backend.agents.analyst_agent import AnalystAgent
from backend.agents.research_agent import ResearchAgent
from backend.agents.source_profiler_agent import SourceProfilerAgent
from backend.agents.investigator_agent import InvestigatorAgent
from backend.agents.herald_agent import HeraldAgent
from backend.agents.coordinator_agent import CoordinatorAgent
from backend.prompts import INVESTIGATOR_MANDATE, HERALD_PROTOCOL
from backend.websocket_manager import ConnectionManager

# Define Pydantic Response Models
class UpdateResponse(BaseModel):
    verification_id: int
    raw_claim_id: int
    verification_status: str
    explanation: str
    dossier: Optional[dict]
    timestamp_verified: datetime


class LogResponse(BaseModel):
    log_id: int
    timestamp: datetime
    log_message: str


# Initialize FastAPI app
app = FastAPI(
    title="Project Backend",
    description="Backend API for Project OSINT and threat analysis system",
    version="1.0.0"
)

# Configure CORS middleware to allow all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global variables for Supabase client and agents
supabase_client: Client = None
vectorizer = None
classifier = None
# Create a global instance of the connection manager
manager = ConnectionManager()
# Initialize specialist agents
analyst_agent = None
source_agent = None
research_agent = None
investigator_agent = None
herald_agent = None
# Initialize the coordinator agent
coordinator = None

# Load environment variables
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")


@app.on_event("startup")
async def startup_event():
    """Initialize Supabase client, load ML models, and start agents on startup"""
    global supabase_client, vectorizer, classifier, manager
    global analyst_agent, source_agent, research_agent, investigator_agent, herald_agent, coordinator
    
    logger.info("=== PROJECT AEGIS STARTUP ===")
    
    # Initialize Supabase client
    if SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY:
        try:
            supabase_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
            logger.info("Supabase client initialized successfully")
            logger.info(f"Supabase URL: {SUPABASE_URL}")
            
            # Test Supabase connection
            try:
                response = supabase_client.table("events").select("event_id").limit(1).execute()
                logger.info("Supabase connection test successful")
            except Exception as e:
                logger.error(f"Supabase connection test failed: {e}")
        except Exception as e:
            logger.error(f"Error initializing Supabase client: {e}")
    else:
        logger.warning("Warning: Supabase credentials not found in environment variables")
    
    # Load ML models
    try:
        vectorizer = joblib.load("backend/vectorizer.pkl")
        classifier = joblib.load("backend/classifier.pkl")
        logger.info("ML models loaded successfully")
    except FileNotFoundError:
        logger.warning("Warning: vectorizer.pkl or classifier.pkl not found")
    except Exception as e:
        logger.error(f"Error loading ML models: {e}")
    
    # Check Gemini API key
    if GEMINI_API_KEY:
        logger.info("Gemini API key found in environment variables")
        logger.info(f"Gemini API key (first 10 chars): {GEMINI_API_KEY[:10]}...")
    else:
        logger.warning("Warning: Gemini API key not found in environment variables")
    
    # Initialize instances of all specialist agents
    try:
        analyst_agent = AnalystAgent(model_path="backend")
        source_agent = SourceProfilerAgent()
        research_agent = ResearchAgent()
        investigator_agent = InvestigatorAgent(gemini_api_key=GEMINI_API_KEY)
        herald_agent = HeraldAgent()
        logger.info("Specialist agents initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing specialist agents: {e}")
    
    # Initialize the CoordinatorAgent
    try:
        coordinator = CoordinatorAgent(
            supabase_client=supabase_client,
            model_path="backend",
            websocket_manager=manager,
            analyst_agent=analyst_agent,
            source_agent=source_agent,
            research_agent=research_agent,
            investigator_agent=investigator_agent,
            herald_agent=herald_agent
        )
        logger.info("Coordinator agent initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing coordinator agent: {e}")
    
    # Start the Coordinator's autonomous loop as a background task
    if coordinator:
        logger.info("Starting coordinator loop...")
        asyncio.create_task(coordinator.start())
    else:
        logger.error("Coordinator not initialized, cannot start loop")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time dashboard updates"""
    # Accept the connection
    await manager.connect(websocket)
    
    try:
        # Keep the connection alive by sending periodic ping messages
        while True:
            # Send a ping message to keep the connection alive
            await websocket.send_text("ping")
            # Wait for 25 seconds before sending the next ping
            await asyncio.sleep(25)
    except Exception as e:
        logger.info(f"WebSocket connection closed: {e}")
    finally:
        # Disconnect the websocket
        manager.disconnect(websocket)


@app.get("/")
async def health_check():
    """Health check endpoint to verify server is running"""
    logger.info("Health check endpoint called")
    return {"status": "Project backend is running"}


@app.get("/updates", response_model=List[UpdateResponse])
async def get_updates():
    """Get the 20 most recent verified claims for the public dashboard"""
    global supabase_client
    
    logger.info("Get updates endpoint called")
    
    if supabase_client is None:
        logger.error("Supabase client not initialized")
        return {"error": "Supabase client not initialized"}
    
    try:
        # Query the verified_claims table
        response = (supabase_client.table("verified_claims")
                   .select("verification_id, raw_claim_id, verification_status, explanation, dossier, timestamp_verified")
                   .order("timestamp_verified", desc=True)
                   .limit(20)
                   .execute())
        
        # Transform the data to match the UpdateResponse model
        updates = []
        for item in response.data:
            update = UpdateResponse(
                verification_id=item.get("verification_id", 0),
                raw_claim_id=item.get("raw_claim_id", 0),
                verification_status=item.get("verification_status", "Unknown"),
                explanation=item.get("explanation", ""),
                dossier=item.get("dossier", None),
                timestamp_verified=item.get("timestamp_verified", datetime.now())
            )
            updates.append(update)
        
        logger.info(f"Returning {len(updates)} verified claims")
        return updates
    except Exception as e:
        logger.error(f"Error fetching updates: {e}")
        return {"error": "Failed to fetch updates"}


@app.get("/agent-status", response_model=List[LogResponse])
async def get_agent_status():
    """Get the 10 most recent agent status logs for the public dashboard"""
    global supabase_client
    
    logger.info("Get agent status endpoint called")
    
    if supabase_client is None:
        logger.error("Supabase client not initialized")
        return {"error": "Supabase client not initialized"}
    
    try:
        # Query the system_logs table
        response = (supabase_client.table("system_logs")
                   .select("log_id, timestamp, log_message")
                   .order("timestamp", desc=True)
                   .limit(10)
                   .execute())
        
        # Transform the data to match the LogResponse model
        logs = []
        for item in response.data:
            log = LogResponse(
                log_id=item.get("log_id", 0),
                timestamp=item.get("timestamp", datetime.now()),
                log_message=item.get("log_message", "")
            )
            logs.append(log)
        
        logger.info(f"Returning {len(logs)} agent status logs")
        return logs
    except Exception as e:
        logger.error(f"Error fetching agent status: {e}")
        return {"error": "Failed to fetch agent status"}


# Example endpoint to demonstrate Supabase integration
@app.get("/test-db")
async def test_database():
    """Test endpoint to verify Supabase connection"""
    if supabase_client is None:
        return {"error": "Supabase client not initialized"}
    
    try:
        # Test query on events table
        response = supabase_client.table("events").select("event_id, event_name").limit(1).execute()
        return {"status": "Database connection successful", "data": response.data}
    except Exception as e:
        return {"error": f"Database connection failed: {str(e)}"}


# Demo Injection Endpoint
class DemoClaim(BaseModel):
    claim_text: str
    source_metadata_json: str


class SubmitClaim(BaseModel):
    claim_text: str
    source_url: str = ""


@app.post("/api/submit-claim")
async def submit_claim(claim: SubmitClaim):
    """Public endpoint for submitting claims from the frontend"""
    global supabase_client
    
    if supabase_client is None:
        return {"error": "Supabase client not initialized"}
    
    try:
        # Get the default event ID
        event_response = supabase_client.table("events").select("event_id").limit(1).execute()
        if not event_response.data:
            return {"error": "No events found in database"}
        
        default_event_id = event_response.data[0]["event_id"]
        
        # Create source metadata
        source_metadata = {
            "source_url": claim.source_url or "manual_submission",
            "submitted_via": "web_form",
            "account_age_days": 365,
            "followers": 1000,
            "following": 500,
            "is_verified": False
        }
        
        # Insert the claim
        claim_data = {
            "event_id": default_event_id,
            "claim_text": claim.claim_text,
            "source_metadata_json": json.dumps(source_metadata),
            "status": "pending_initial_analysis"
        }
        
        response = supabase_client.table("raw_claims").insert(claim_data).execute()
        
        # Log this action
        log_entry = {
            "log_message": f"Claim submitted via web form: {claim.claim_text[:50]}..."
        }
        supabase_client.table("system_logs").insert(log_entry).execute()
        
        return {
            "status": "success",
            "message": "Claim submitted successfully",
            "claim_id": response.data[0]["claim_id"] if response.data else None
        }
    except Exception as e:
        logger.error(f"Error submitting claim: {e}")
        return {"error": f"Failed to submit claim: {str(e)}"}


@app.post("/seed-demo-claim")
async def seed_demo_claim(claim: DemoClaim):
    """Insert a demo claim directly into the raw_claims table to trigger agent processing"""
    global supabase_client
    
    if supabase_client is None:
        return {"error": "Supabase client not initialized"}
    
    try:
        # Get the default event ID (assuming there's at least one event)
        event_response = supabase_client.table("events").select("event_id").limit(1).execute()
        if not event_response.data:
            return {"error": "No events found in database"}
        
        default_event_id = event_response.data[0]["event_id"]
        
        # Insert the demo claim into raw_claims table with status='pending_initial_analysis'
        claim_data = {
            "event_id": default_event_id,
            "claim_text": claim.claim_text,
            "source_metadata_json": claim.source_metadata_json,
            "status": "pending_initial_analysis"
        }
        
        response = supabase_client.table("raw_claims").insert(claim_data).execute()
        
        # Log this action
        log_entry = {
            "log_message": f"Demo claim injected: {claim.claim_text[:50]}..."
        }
        supabase_client.table("system_logs").insert(log_entry).execute()
        
        return {
            "status": "success",
            "message": "Demo claim inserted successfully",
            "claim_id": response.data[0]["claim_id"] if response.data else None
        }
    except Exception as e:
        print(f"Error inserting demo claim: {e}")
        return {"error": f"Failed to insert demo claim: {str(e)}"}

