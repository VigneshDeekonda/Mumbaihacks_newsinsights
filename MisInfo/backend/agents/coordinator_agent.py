import asyncio
import json
import logging
from typing import Dict, Any, List
from datetime import datetime
from uuid import uuid4

from .base_agent import AgentCoordinator, AgentTask, TaskPriority
from .scout_agent import ScoutAgent
from .analyst_agent import AnalystAgent
from .research_agent import ResearchAgent
from .source_profiler_agent import SourceProfilerAgent
from .investigator_agent import InvestigatorAgent
from .herald_agent import HeraldAgent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CoordinatorAgent:
    """Agent responsible for coordinating the entire fact-checking workflow"""
    
    def __init__(self, supabase_client=None, model_path=".", websocket_manager=None,
                 scout_agent=None, analyst_agent=None, research_agent=None, 
                 source_agent=None, investigator_agent=None, herald_agent=None):
        self.supabase_client = supabase_client
        self.model_path = model_path
        self.websocket_manager = websocket_manager
        self.coordinator = AgentCoordinator()
        
        # Initialize all agents (use provided agents or create new ones)
        self.scout_agent = scout_agent or ScoutAgent()
        self.analyst_agent = analyst_agent or AnalystAgent(model_path=model_path)
        self.research_agent = research_agent or ResearchAgent()
        self.source_profiler_agent = source_agent or SourceProfilerAgent()
        self.investigator_agent = investigator_agent or InvestigatorAgent()
        self.herald_agent = herald_agent or HeraldAgent()
        
        # Register all agents with the coordinator
        self.coordinator.register_agent(self.scout_agent)
        self.coordinator.register_agent(self.analyst_agent)
        self.coordinator.register_agent(self.research_agent)
        self.coordinator.register_agent(self.source_profiler_agent)
        self.coordinator.register_agent(self.investigator_agent)
        self.coordinator.register_agent(self.herald_agent)
        
        logger.info("CoordinatorAgent initialized with all agents registered")
    
    def generate_task_id(self) -> str:
        """Generate a unique task ID"""
        return f"task_{uuid4().hex[:8]}"
    
    async def start(self):
        """Start the coordinator loop"""
        logger.info("Coordinator loop started...")
        
        # Get or create an active event
        active_event_id = await self.get_or_create_active_event()
        
        # Counter to track discovery cycles
        discovery_cycle = 0
        
        while True:
            try:
                # Wait for 15 seconds before next cycle (changed from 30 to 15 seconds)
                await asyncio.sleep(15)
                logger.info("Coordinator loop running...")
                
                # === SCOUT AGENT DISCOVERY ===
                # Call Scout Agent to discover new claims every 2 cycles (every 30 seconds)
                # This limits the discovery rate to prevent overwhelming the system
                discovery_cycle = (discovery_cycle + 1) % 2
                if discovery_cycle == 0 and self.scout_agent and self.supabase_client and active_event_id:
                    try:
                        logger.info("=== DISCOVERY PHASE ===")
                        
                        # Get existing claim URLs from database for duplicate checking
                        existing_claim_urls = set()
                        try:
                            response = self.supabase_client.table("raw_claims").select("source_metadata_json").execute()
                            if response.data:
                                for claim_data in response.data:
                                    try:
                                        metadata = json.loads(claim_data["source_metadata_json"])
                                        url = metadata.get("source_url")
                                        if url:
                                            existing_claim_urls.add(url)
                                    except json.JSONDecodeError:
                                        continue
                            logger.info(f"[Coordinator] Loaded {len(existing_claim_urls)} existing claim URLs for duplicate checking")
                        except Exception as db_error:
                            logger.warning(f"[Coordinator] Could not load existing claim URLs: {db_error}")
                        
                        # Call Scout Agent with existing URLs for persistent duplicate checking
                        scout_task = AgentTask(
                            task_id=self.generate_task_id(),
                            agent_type="ScoutAgent",
                            priority=TaskPriority.NORMAL,
                            payload={},
                            created_at=datetime.now()
                        )
                        
                        # Use the new method that accepts existing URLs
                        if hasattr(self.scout_agent, 'process_task_with_urls'):
                            scout_result = await self.scout_agent.process_task_with_urls(scout_task, existing_claim_urls)
                        else:
                            # Fallback to original method for compatibility
                            scout_result = await self.scout_agent.process_task(scout_task)
                            
                        discovered_claims = scout_result.get("claims", [])
                        discovery_timestamp = scout_result.get("discovery_timestamp", datetime.now().isoformat())
                        
                        logger.info(f"[Coordinator] Scout discovered {len(discovered_claims)} potential claims at {discovery_timestamp}")
                        
                        # Limit to 1 claim per discovery cycle to control update rate
                        claims_to_process = discovered_claims[:1] if discovered_claims else []
                        
                        # Insert discovered claims into database
                        inserted_count = 0
                        duplicate_count = 0
                        
                        for claim in claims_to_process:
                            try:
                                # Construct claim data for database
                                claim_data = {
                                    "event_id": active_event_id,
                                    "claim_text": claim["claim_text"],
                                    "source_metadata_json": claim["source_metadata_json"],
                                    "status": "pending_initial_analysis"
                                }
                                
                                # Insert into raw_claims table
                                response = self.supabase_client.table("raw_claims").insert(claim_data).execute()
                                
                                if response.data:
                                    inserted_count += 1
                                    claim_id = response.data[0].get("claim_id")
                                    logger.info(f"[Coordinator] Inserted claim {claim_id}: {claim['claim_text'][:50]}...")
                                    
                                    # Log this insertion
                                    log_entry = {
                                        "log_message": f"Scout discovered and inserted new claim: {claim['claim_text'][:50]}..."
                                    }
                                    self.supabase_client.table("system_logs").insert(log_entry).execute()
                                    
                            except Exception as insert_error:
                                # Handle duplicate entries or other database errors
                                error_msg = str(insert_error)
                                if "duplicate" in error_msg.lower() or "unique" in error_msg.lower():
                                    duplicate_count += 1
                                    logger.debug(f"[Coordinator] Duplicate claim skipped: {claim['claim_text'][:50]}...")
                                else:
                                    logger.error(f"[Coordinator] Error inserting claim: {insert_error}")
                                continue
                        
                        # Log discovery summary
                        if inserted_count > 0 or duplicate_count > 0:
                            log_entry = {
                                "log_message": f"Scout discovery cycle: {len(claims_to_process)} processed, {inserted_count} new, {duplicate_count} duplicates."
                            }
                            self.supabase_client.table("system_logs").insert(log_entry).execute()
                            logger.info(f"[Coordinator] Discovery summary: {len(claims_to_process)} processed, {inserted_count} new, {duplicate_count} duplicates")
                        
                    except Exception as scout_error:
                        logger.error(f"[Coordinator] Error in Scout Agent discovery: {scout_error}")
                        # Log the error
                        try:
                            log_entry = {
                                "log_message": f"Scout Agent error: {str(scout_error)[:100]}..."
                            }
                            if self.supabase_client:
                                self.supabase_client.table("system_logs").insert(log_entry).execute()
                        except:
                            pass
                
                # Run a cycle of the coordinator agent
                results = await self.run_cycle(active_event_id)
                
                # Broadcast results to WebSocket connections if manager is available
                if results and self.websocket_manager:
                    message = {
                        "type": "claim_updates",
                        "count": len(results),
                        "timestamp": datetime.now().isoformat()
                    }
                    await self.websocket_manager.broadcast(message)
                    
            except Exception as e:
                logger.error(f"[Coordinator] Error in coordinator loop: {e}")
                # Log the error
                try:
                    log_entry = {
                        "log_message": f"Coordinator loop error: {str(e)[:100]}..."
                    }
                    if self.supabase_client:
                        self.supabase_client.table("system_logs").insert(log_entry).execute()
                except:
                    pass
                await asyncio.sleep(5)  # Short delay before retrying

    async def get_or_create_active_event(self):
        """Get or create an active event for claim processing"""
        if not self.supabase_client:
            return None
            
        try:
            # Check if an active event already exists
            response = self.supabase_client.table("events").select("event_id").eq("status", "active").execute()
            
            if response.data:
                # Use existing active event
                event_id = response.data[0]["event_id"]
                logger.info(f"Using existing active event (ID: {event_id})")
                return event_id
            else:
                # Create a new default event
                event_data = {
                    "event_name": "Live Monitoring",
                    "status": "active"
                }
                response = self.supabase_client.table("events").insert(event_data).execute()
                event_id = response.data[0]["event_id"] if response.data else None
                logger.info(f"Created new active event (ID: {event_id})")
                return event_id
                
        except Exception as e:
            logger.error(f"Error getting or creating active event: {e}")
            return None

    async def discover_claims(self) -> List[Dict[str, Any]]:
        """Discover new claims using the Scout Agent"""
        logger.info("=== DISCOVERY PHASE ===")
        
        task = AgentTask(
            task_id=self.generate_task_id(),
            agent_type="ScoutAgent",
            priority=TaskPriority.NORMAL,
            payload={},
            created_at=datetime.now()
        )
        
        result = await self.scout_agent.process_task(task)
        claims = result.get("claims", [])
        logger.info(f"Discovered {len(claims)} new claims")
        
        return claims
    
    async def analyze_claim(self, claim: Dict[str, Any]) -> Dict[str, Any]:
        """Perform initial analysis on a claim"""
        logger.info("=== INITIAL ANALYSIS PHASE ===")
        
        claim_text = claim["claim_text"]
        source_metadata_json = claim["source_metadata_json"]
        
        # Analyze text with Analyst Agent
        analyst_task = AgentTask(
            task_id=self.generate_task_id(),
            agent_type="AnalystAgent",
            priority=TaskPriority.NORMAL,
            payload={"claim_text": claim_text},
            created_at=datetime.now()
        )
        
        analyst_result = await self.analyst_agent.process_task(analyst_task)
        
        # Handle honest failure from AnalystAgent
        text_suspicion_score = analyst_result.get("text_suspicion_score")
        if text_suspicion_score is None:
            status = analyst_result.get("status", "unknown")
            error = analyst_result.get("error", "Unknown error")
            logger.error(f"AnalystAgent failed to analyze claim: {status} - {error}")
            # Set a default score that indicates failure for downstream processing
            text_suspicion_score = None
        else:
            logger.info(f"Text suspicion score: {text_suspicion_score:.4f}")
        
        # Profile source with Source Profiler Agent
        profiler_task = AgentTask(
            task_id=self.generate_task_id(),
            agent_type="SourceProfilerAgent",
            priority=TaskPriority.NORMAL,
            payload={"source_metadata_json": source_metadata_json},
            created_at=datetime.now()
        )
        
        profiler_result = await self.source_profiler_agent.process_task(profiler_task)
        source_credibility_score = profiler_result["source_credibility_score"]
        logger.info(f"Source credibility score: {source_credibility_score:.4f}")
        
        return {
            "claim_text": claim_text,
            "source_metadata_json": source_metadata_json,
            "text_suspicion_score": text_suspicion_score,
            "source_credibility_score": source_credibility_score
        }
    
    async def gather_evidence(self, claim_data: Dict[str, Any]) -> Dict[str, Any]:
        """Gather evidence for a claim using the Research Agent"""
        logger.info("=== EVIDENCE GATHERING PHASE ===")
        
        claim_text = claim_data["claim_text"]
        
        research_task = AgentTask(
            task_id=self.generate_task_id(),
            agent_type="ResearchAgent",
            priority=TaskPriority.NORMAL,
            payload={"claim_text": claim_text},
            created_at=datetime.now()
        )
        
        research_result = await self.research_agent.process_task(research_task)
        research_dossier = research_result["research_dossier"]
        logger.info(f"Evidence gathered: {len(research_dossier.get('web_snippets', []))} web results")
        
        claim_data["research_dossier"] = research_dossier
        return claim_data
    
    async def investigate_claim(self, claim_data: Dict[str, Any]) -> Dict[str, Any]:
        """Investigate a claim using the Investigator Agent"""
        logger.info("=== INVESTIGATION PHASE ===")
        
        # Create case file for investigator
        case_file = {
            "claim_text": claim_data["claim_text"],
            "text_suspicion_score": claim_data["text_suspicion_score"],
            "source_credibility_score": claim_data["source_credibility_score"],
            "research_dossier": claim_data["research_dossier"]
        }
        
        investigator_task = AgentTask(
            task_id=self.generate_task_id(),
            agent_type="InvestigatorAgent",
            priority=TaskPriority.HIGH,
            payload={"case_file_json": json.dumps(case_file)},
            created_at=datetime.now()
        )
        
        investigator_result = await self.investigator_agent.process_task(investigator_task)
        investigation_result = investigator_result["investigation_result"]
        logger.info(f"Investigation verdict: {investigation_result['verdict']}")
        
        claim_data["investigation_result"] = investigation_result
        return claim_data
    
    async def generate_alert(self, claim_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate public alert using the Herald Agent"""
        logger.info("=== ALERT GENERATION PHASE ===")
        
        investigation_result = claim_data["investigation_result"]
        
        herald_task = AgentTask(
            task_id=self.generate_task_id(),
            agent_type="HeraldAgent",
            priority=TaskPriority.NORMAL,
            payload={"investigator_report_json": json.dumps(investigation_result)},
            created_at=datetime.now()
        )
        
        herald_result = await self.herald_agent.process_task(herald_task)
        public_alert = herald_result["public_alert"]
        logger.info(f"Public alert generated: {public_alert[:50]}...")
        
        claim_data["public_alert"] = public_alert
        return claim_data
    
    async def process_pending_initial_analysis(self):
        """Process claims pending initial analysis"""
        if not self.supabase_client:
            return
        
        logger.info("=== INITIAL ANALYSIS PHASE ===")
        try:
            response = self.supabase_client.table("raw_claims").select("*").eq("status", "pending_initial_analysis").execute()
            pending_claims = response.data
            logger.info(f"[Coordinator] Found {len(pending_claims)} claims for initial analysis")
            
            for claim in pending_claims:
                claim_id = claim["claim_id"]
                claim_text = claim["claim_text"]
                source_metadata_json = claim["source_metadata_json"]
                
                logger.info(f"[Coordinator] Analyzing claim {claim_id}: {claim_text[:50]}...")
                
                # Run analyst agent
                analyst_task = AgentTask(
                    task_id=self.generate_task_id(),
                    agent_type="AnalystAgent",
                    priority=TaskPriority.NORMAL,
                    payload={"claim_text": claim_text},
                    created_at=datetime.now()
                )
                analyst_result = await self.analyst_agent.process_task(analyst_task)
                
                # Handle honest failure from AnalystAgent
                text_suspicion_score = analyst_result.get("text_suspicion_score")
                if text_suspicion_score is None:
                    status = analyst_result.get("status", "unknown")
                    error = analyst_result.get("error", "Unknown error")
                    logger.error(f"[Coordinator] AnalystAgent failed for claim {claim_id}: {status} - {error}")
                    # Mark claim for manual review when analysis fails
                    update_data = {
                        "status": "pending_manual_review",
                        "analysis_error": f"Analysis failed: {error}"
                    }
                    self.supabase_client.table("raw_claims").update(update_data).eq("claim_id", claim_id).execute()
                    logger.info(f"[Coordinator] Claim {claim_id} marked for manual review due to analysis failure")
                    continue  # Skip to next claim
                
                # Run source profiler agent
                profiler_task = AgentTask(
                    task_id=self.generate_task_id(),
                    agent_type="SourceProfilerAgent",
                    priority=TaskPriority.NORMAL,
                    payload={"source_metadata_json": source_metadata_json},
                    created_at=datetime.now()
                )
                profiler_result = await self.source_profiler_agent.process_task(profiler_task)
                source_credibility_score = profiler_result["source_credibility_score"]
                
                # Add safety check for None scores or specific status
                if text_suspicion_score is None or source_credibility_score is None:
                    logger.warning(f"[Coordinator] Claim {claim_id} has missing scores (Analysis: {text_suspicion_score}, Source: {source_credibility_score}). Skipping processing.")
                    continue  # Skip to next claim
                
                # Check if source credibility score is neutral (0.5) and trigger Gemini source check
                if source_credibility_score == 0.5:
                    logger.info(f"[Coordinator] Triggering Gemini source credibility check for claim {claim_id}")
                    
                    # Extract source name and URL from profiler result
                    source_metadata = profiler_result.get("source_metadata", {})
                    source_name = source_metadata.get("source_name", "Unknown Source")
                    source_url = source_metadata.get("source_url", "")
                    
                    # Call the new investigator method to assess source credibility
                    gemini_score = await self.investigator_agent.assess_source_credibility(source_name, source_url)
                    logger.info(f"[Coordinator] Gemini source credibility score for '{source_name}': {gemini_score}")
                    
                    # Update the source_credibility_score variable with the Gemini score
                    source_credibility_score = gemini_score
                
                # Update claim with scores
                update_data = {
                    "text_suspicion_score": text_suspicion_score,
                    "source_credibility_score": source_credibility_score,
                    "status": "pending_fusion_decision"
                }
                self.supabase_client.table("raw_claims").update(update_data).eq("claim_id", claim_id).execute()
                logger.info(f"[Coordinator] Claim {claim_id} updated with scores")

        except Exception as e:
            logger.error(f"[Coordinator] Error in initial analysis: {e}")
    
    async def process_fusion_decision(self):
        """Process claims at fusion decision point"""
        if not self.supabase_client:
            return
        
        logger.info("=== FUSION DECISION PHASE ===")
        try:
            response = self.supabase_client.table("raw_claims").select("*").eq("status", "pending_fusion_decision").execute()
            fusion_claims = response.data
            logger.info(f"[Coordinator] Found {len(fusion_claims)} claims for fusion decision")
            
            for claim in fusion_claims:
                claim_id = claim["claim_id"]
                # Retrieve scores using .get() to avoid KeyError
                text_suspicion_score = claim.get("text_suspicion_score")
                source_credibility_score = claim.get("source_credibility_score")
                
                # Check if either score is None and handle appropriately
                if text_suspicion_score is None or source_credibility_score is None:
                    logger.warning(f"[Coordinator] Claim {claim_id} has missing scores (Analysis: {text_suspicion_score}, Source: {source_credibility_score}). Skipping fusion decision.")
                    # Optionally, you could update the status here to 'error' or 'needs_review'
                    # Example: await self.update_claim_status(claim_id, 'error', error_message="Missing scores for fusion")
                    continue  # Skip to the next claim
                
                # Archive low-risk claims
                if text_suspicion_score < 0.2 and source_credibility_score > 0.8:
                    update_data = {"status": "archived"}
                    self.supabase_client.table("raw_claims").update(update_data).eq("claim_id", claim_id).execute()
                    
                    log_entry = {"log_message": f"Claim {claim_id} archived due to low suspicion and high credibility scores"}
                    self.supabase_client.table("system_logs").insert(log_entry).execute()
                    logger.info(f"[Coordinator] Claim {claim_id} archived")
                else:
                    # Gather evidence using Enhanced Research Agent (multi-API)
                    claim_text = claim["claim_text"]
                    logger.info(f"[Coordinator] Gathering evidence for claim {claim_id} using multi-API research")
                    
                    # Create a task for the research agent
                    research_task = AgentTask(
                        task_id=self.generate_task_id(),
                        agent_type="EnhancedResearchAgent",
                        priority=TaskPriority.NORMAL,
                        payload={"claim_text": claim_text},
                        created_at=datetime.now()
                    )
                    
                    # Process the task with the research agent
                    research_result = await self.research_agent.process_task(research_task)
                    research_dossier = research_result["research_dossier"]
                    
                    # Update with comprehensive research dossier
                    update_data = {
                        "research_dossier_json": json.dumps(research_dossier),
                        "status": "pending_final_decision"
                    }
                    self.supabase_client.table("raw_claims").update(update_data).eq("claim_id", claim_id).execute()
                    
                    log_entry = {"log_message": f"Claim {claim_id} escalated for research gathering"}
                    self.supabase_client.table("system_logs").insert(log_entry).execute()
                    logger.info(f"[Coordinator] Claim {claim_id} escalated to final decision")
                    
        except Exception as e:
            logger.error(f"[Coordinator] Error in fusion decision: {e}")
    
    async def process_final_decision(self):
        """Process claims at final decision point with stricter escalation logic"""
        if not self.supabase_client:
            return
        
        logger.info("=== FINAL DECISION PHASE ===")
        try:
            response = self.supabase_client.table("raw_claims").select("*").eq("status", "pending_final_decision").execute()
            final_decision_claims = response.data
            logger.info(f"[Coordinator] Found {len(final_decision_claims)} claims for final decision")
            
            for claim in final_decision_claims:
                claim_id = claim["claim_id"]
                claim_text = claim.get("claim_text", "")
                # Retrieve scores using .get() to avoid KeyError
                text_suspicion_score = claim.get("text_suspicion_score")
                source_credibility_score = claim.get("source_credibility_score")
                
                # Add safety check for None scores
                if text_suspicion_score is None or source_credibility_score is None:
                    logger.error(f"[Coordinator] Claim {claim_id} reached final decision with missing scores. Setting status to error.")
                    try:
                        self.supabase_client.table("raw_claims").update({
                            "status": "error",
                            "analysis_error": "Missing scores at final decision"
                        }).eq("claim_id", claim_id).execute()
                    except Exception as db_error:
                        logger.error(f"[Coordinator] Failed to update status for claim {claim_id} with missing scores: {db_error}")
                    continue # Skip processing this claim further
                
                research_dossier_json = claim.get("research_dossier_json", "{}")
                
                try:
                    research_dossier = json.loads(research_dossier_json)
                except Exception as e:
                    logger.error(f"[Coordinator] Error parsing research dossier: {e}")
                    research_dossier = {}
                
                # Extract data from enhanced research dossier
                wikipedia_summary = research_dossier.get("wikipedia_summary", "")
                web_snippets = research_dossier.get("web_snippets", [])
                
                # NEW: Check fact-checking databases result
                fact_check_db = research_dossier.get("fact_check_databases", {})
                fact_check_found = fact_check_db.get("found", False)
                fact_check_verdict = fact_check_db.get("verdict", "").lower()
                
                # NEW: Check news coverage
                news_coverage = research_dossier.get("news_coverage", {})
                news_sources = news_coverage.get("sources", [])
                credible_news_count = len([s for s in news_sources if s in ["Reuters", "AP", "BBC", "CNN"]])
                
                # RELAXED ESCALATION LOGIC: Check if either condition is met
                if (text_suspicion_score > 0.85 and source_credibility_score < 0.3) or \
                   (text_suspicion_score > 0.7 and (wikipedia_summary and (("contradict" in wikipedia_summary.lower()) or 
                    ("false" in wikipedia_summary.lower()) or ("not" in wikipedia_summary.lower())) or credible_news_count == 0)):
                    # Already fact-checked as false - no need to escalate
                    should_escalate = True
                    logger.info(f"[Coordinator] Claim {claim_id} meets relaxed escalation criteria and will be escalated to investigator")
                elif fact_check_found and fact_check_verdict in ["false", "pants on fire"]:
                    # Already fact-checked as false - no need to escalate
                    should_escalate = False
                    logger.info(f"[Coordinator] Claim {claim_id} already fact-checked as False by {fact_check_db.get('source')}")
                elif fact_check_found and fact_check_verdict in ["true", "mostly true"]:
                    # Already fact-checked as true - no need to escalate
                    should_escalate = False
                    logger.info(f"[Coordinator] Claim {claim_id} already fact-checked as True by {fact_check_db.get('source')}")
                else:
                    should_escalate = False
                
                if should_escalate:
                    # Escalate to investigator
                    update_data = {"status": "escalated_to_investigator"}
                    self.supabase_client.table("raw_claims").update(update_data).eq("claim_id", claim_id).execute()
                    
                    log_entry = {"log_message": f"Claim {claim_id} escalated to investigator agent for expert analysis"}
                    self.supabase_client.table("system_logs").insert(log_entry).execute()
                    logger.info(f"[Coordinator] Claim {claim_id} escalated to investigator")
                else:
                    # Resolve by fusion agent using enhanced multi-source evidence
                    
                    # Priority 1: Use fact-check database verdict if available
                    if fact_check_found:
                        if "false" in fact_check_verdict or "pants on fire" in fact_check_verdict:
                            verdict = "False"
                            explanation = f"Fact-checked as False by {fact_check_db.get('source', 'fact-checkers')}. {fact_check_db.get('url', '')}"
                        elif "true" in fact_check_verdict:
                            verdict = "True"
                            explanation = f"Fact-checked as True by {fact_check_db.get('source', 'fact-checkers')}. {fact_check_db.get('url', '')}"
                        else:
                            verdict = "Misleading"
                            explanation = f"Fact-checked as {fact_check_verdict} by {fact_check_db.get('source', 'fact-checkers')}."
                    
                    # Priority 2: Check credible news coverage
                    elif credible_news_count >= 3:
                        verdict = "True"
                        explanation = f"Confirmed by {credible_news_count} credible news sources including {', '.join(news_sources[:3])}."
                    
                    # Priority 3: ML scores + source credibility (ADJUSTED THRESHOLDS)
                    elif text_suspicion_score > 0.8:
                        verdict = "False"
                        explanation = f"High suspicion score ({text_suspicion_score:.0%}) indicates likely misinformation."
                    elif text_suspicion_score > 0.6 and source_credibility_score < 0.6:
                        verdict = "False"
                        explanation = f"Moderate-high suspicion score and low source credibility indicate likely misinformation."
                    elif text_suspicion_score > 0.7:
                        verdict = "False"
                        explanation = f"High suspicion score ({text_suspicion_score:.0%}) indicates likely misinformation regardless of source credibility."
                    elif text_suspicion_score < 0.2 and source_credibility_score > 0.6:
                        verdict = "True"
                        explanation = "Low suspicion score and high source credibility suggest authentic information."
                    elif text_suspicion_score < 0.4 and source_credibility_score > 0.5:
                        verdict = "True"
                        explanation = "Low-moderate suspicion score and reasonable source credibility suggest authentic information."
                    elif text_suspicion_score < 0.3:
                        verdict = "True"
                        explanation = f"Low suspicion score ({text_suspicion_score:.0%}) is a strong indicator of authentic information, even with neutral source credibility."
                    
                    # Priority 4: Wikipedia contradiction
                    elif wikipedia_summary and (("false" in wikipedia_summary.lower()) or ("not" in wikipedia_summary.lower())):
                        verdict = "False"
                        explanation = "Wikipedia and research evidence contradict the claim."
                    
                    # Refined Default: More specific explanation for misleading
                    else:
                        verdict = "Misleading"
                        explanation = f"Scores are inconclusive (Suspicion: {text_suspicion_score:.2f}, Source: {source_credibility_score:.2f}) and no strong corroborating or refuting evidence found in research."
                    
                    dossier_data = {
                        "claim_text": claim_text,
                        "text_suspicion_score": text_suspicion_score,
                        "source_credibility_score": source_credibility_score,
                        "research_dossier": research_dossier
                    }
                    
                    result_data = {
                        "raw_claim_id": claim_id,
                        "verification_status": verdict,
                        "explanation": explanation,
                        "dossier": dossier_data
                    }
                    
                    self.supabase_client.table("verified_claims").insert(result_data).execute()
                    
                    update_data = {"status": "resolved_by_fusion"}
                    self.supabase_client.table("raw_claims").update(update_data).eq("claim_id", claim_id).execute()
                    
                    log_entry = {"log_message": f"Claim {claim_id} resolved by fusion agent"}
                    self.supabase_client.table("system_logs").insert(log_entry).execute()
                    logger.info(f"[Coordinator] Claim {claim_id} resolved by fusion agent with verdict: {verdict}")
                    
        except Exception as e:
            logger.error(f"[Coordinator] Error in final decision: {e}")
    
    async def process_investigator_escalation(self):
        """Process claims escalated to investigator with retry limit"""
        if not self.supabase_client:
            return
        
        logger.info("=== EXPERT CONSULTATION PHASE ===")
        try:
            # Only select claims with retry_count < 3
            response = self.supabase_client.table("raw_claims").select("*").eq("status", "escalated_to_investigator").execute()
            
            # Filter claims with retry_count < 3
            expert_claims = [claim for claim in response.data if claim.get("retry_count", 0) < 3]
            logger.info(f"[Coordinator] Found {len(expert_claims)} claims for expert consultation (retry_count < 3)")
            
            for claim in expert_claims:
                claim_id = claim["claim_id"]
                claim_text = claim["claim_text"]
                text_suspicion_score = claim.get("text_suspicion_score", 0.5)
                source_credibility_score = claim.get("source_credibility_score", 0.5)
                research_dossier_json = claim.get("research_dossier_json", "{}")
                
                try:
                    research_dossier = json.loads(research_dossier_json)
                except Exception as e:
                    logger.error(f"[Coordinator] Error parsing research dossier: {e}")
                    research_dossier = {}
                
                # Create case file for investigator
                case_file = {
                    "claim_id": claim_id,  # Include claim_id for retry tracking
                    "claim_text": claim_text,
                    "text_suspicion_score": text_suspicion_score,
                    "source_credibility_score": source_credibility_score,
                    "research_dossier": research_dossier
                }
                
                # Call investigator agent
                logger.info(f"[Coordinator] Calling investigator agent for claim {claim_id}")
                investigator_task = AgentTask(
                    task_id=self.generate_task_id(),
                    agent_type="InvestigatorAgent",
                    priority=TaskPriority.HIGH,
                    payload={"case_file_json": json.dumps(case_file)},
                    created_at=datetime.now()
                )
                
                try:
                    investigator_result = await self.investigator_agent.process_task(investigator_task)
                    investigation_result = investigator_result["investigation_result"]
                    
                    # Call herald agent
                    logger.info(f"[Coordinator] Calling herald agent for claim {claim_id}")
                    herald_task = AgentTask(
                        task_id=self.generate_task_id(),
                        agent_type="HeraldAgent",
                        priority=TaskPriority.NORMAL,
                        payload={"investigator_report_json": json.dumps(investigation_result)},
                        created_at=datetime.now()
                    )
                    herald_result = await self.herald_agent.process_task(herald_task)
                    
                    # Save results
                    dossier_data = {
                        "claim_text": claim_text,
                        "text_suspicion_score": text_suspicion_score,
                        "source_credibility_score": source_credibility_score,
                        "research_dossier": research_dossier
                    }
                    
                    result_data = {
                        "raw_claim_id": claim_id,
                        "verification_status": investigation_result["verdict"],
                        "explanation": investigation_result["reasoning"],
                        "dossier": dossier_data
                    }
                    
                    self.supabase_client.table("verified_claims").insert(result_data).execute()
                    logger.info(f"[Coordinator] Verified claim inserted for claim {claim_id}")
                    
                    # Update status to resolved
                    update_data = {"status": "resolved_by_investigator"}
                    self.supabase_client.table("raw_claims").update(update_data).eq("claim_id", claim_id).execute()
                    logger.info(f"[Coordinator] Claim {claim_id} marked as resolved")
                    
                except Exception as e:
                    logger.error(f"[Coordinator] Investigator failed for claim {claim_id}: {e}")
                    # The investigator agent will handle retry increment
                    
        except Exception as e:
            logger.error(f"[Coordinator] Error in expert consultation: {e}")
    
    async def run_cycle(self, event_id=None):
        """Run a single cycle of the coordinator loop with database-driven workflow"""
        try:
            logger.info("Coordinator cycle started")
            
            # Process claims at each stage of the pipeline
            await self.process_pending_initial_analysis()
            await self.process_fusion_decision()
            await self.process_final_decision()
            await self.process_investigator_escalation()
            
            logger.info("Coordinator cycle completed")
            return []
            
        except Exception as e:
            logger.error(f"Error in coordinator cycle: {e}")
            return []


# Example usage
if __name__ == "__main__":
    import asyncio
    
    async def main():
        # Create the coordinator agent
        coordinator_agent = CoordinatorAgent()
        
        # Run a single cycle
        results = await coordinator_agent.run_cycle()
        print(f"Processed {len(results)} claims")
        
        # Print results
        for i, result in enumerate(results):
            print(f"\n--- Claim {i+1} Results ---")
            print(f"Claim: {result['claim_text'][:50]}...")
            print(f"Text Suspicion Score: {result['text_suspicion_score']:.4f}")
            print(f"Source Credibility Score: {result['source_credibility_score']:.4f}")
            if "investigation_result" in result:
                print(f"Verdict: {result['investigation_result']['verdict']}")
                print(f"Confidence: {result['investigation_result']['confidence']:.2f}")
            if "public_alert" in result:
                print(f"Alert: {result['public_alert']}")
    
    # Run the example
    asyncio.run(main())