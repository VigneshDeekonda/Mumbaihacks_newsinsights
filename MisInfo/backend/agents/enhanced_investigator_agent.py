
import logging
from typing import Dict, Any
import json
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.base_agent import BaseAgent, AgentTask, AgentStatus, TaskPriority
from backend.prompts import INVESTIGATOR_MANDATE
from utils.cache_manager import cache_manager
from utils.fact_check_databases import fact_check_db
from utils.ml_analyzers import ner_analyzer, sentiment_analyzer, topic_classifier

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EnhancedInvestigatorAgent(BaseAgent):
    """
    Enhanced Investigator Agent with:
    - Claim caching to avoid redundant API calls
    - Fact-checking database integration
    - Local ML enrichment (NER, sentiment, topics)
    - Optimized Gemini prompts
    """
    
    def __init__(self, agent_id: str = "enhanced_investigator_001", gemini_api_key: str = None, supabase_client=None):
        super().__init__(agent_id, "EnhancedInvestigatorAgent")
        self.gemini_api_key = gemini_api_key or os.getenv("GEMINI_API_KEY")
        self.use_gemini = self.gemini_api_key is not None
        self.supabase_client = supabase_client
        
        # Statistics
        self.stats = {
            "cache_hits": 0,
            "fact_db_hits": 0,
            "gemini_calls": 0,
            "total_analyses": 0
        }
        
        if self.use_gemini:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.gemini_api_key)
                self.model = genai.GenerativeModel('gemini-2.0-flash-exp')
                logger.info(f"[{self.agent_name}] Gemini API configured successfully")
            except ImportError:
                logger.warning(f"[{self.agent_name}] Google Generative AI library not installed")
                self.use_gemini = False
            except Exception as e:
                logger.error(f"[{self.agent_name}] Error configuring Gemini API: {e}")
                self.use_gemini = False
        else:
            logger.info(f"[{self.agent_name}] No Gemini API key found, using optimized fallback")
    
    async def enrich_case_file(self, case_file: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich case file with local ML analysis"""
        claim_text = case_file.get("claim_text", "")
        
        # Add NER entities
        entities = ner_analyzer.extract_entities(claim_text)
        case_file["entities"] = entities
        
        # Add sentiment analysis
        sentiment = sentiment_analyzer.analyze(claim_text)
        case_file["sentiment"] = sentiment
        
        # Add topic classification
        topic = topic_classifier.classify(claim_text)
        case_file["topic"] = topic
        
        logger.info(f"[{self.agent_name}] Case file enriched with local ML analysis")
        return case_file
    
    async def check_cache(self, claim_text: str) -> Dict[str, Any]:
        """Check if claim has been analyzed before"""
        cached_result = cache_manager.check_similar_claim(claim_text)
        
        if cached_result:
            self.stats["cache_hits"] += 1
            logger.info(f"[{self.agent_name}] ✅ CACHE HIT - Reusing previous analysis")
            return cached_result
        
        return None
    
    async def check_fact_databases(self, claim_text: str) -> Dict[str, Any]:
        """Check fact-checking databases before using AI"""
        db_result = await fact_check_db.check_all_databases(claim_text)
        
        if db_result:
            self.stats["fact_db_hits"] += 1
            logger.info(f"[{self.agent_name}] ✅ FACT-CHECK DB HIT - Found in {db_result['source']}")
            
            # Convert to standard format
            return {
                "verdict": db_result["verdict"],
                "confidence": db_result["confidence"],
                "reasoning": f"Found in {db_result['source']} fact-checking database. {db_result.get('url', '')}"
            }
        
        return None
    
    def create_optimized_prompt(self, case_file: Dict[str, Any]) -> str:
        """Create an optimized, comprehensive prompt for Gemini"""
        
        # Extract all available context
        claim_text = case_file.get("claim_text", "")
        text_suspicion = case_file.get("text_suspicion_score", 0.5)
        source_credibility = case_file.get("source_credibility_score", 0.5)
        research_dossier = case_file.get("research_dossier", {})
        entities = case_file.get("entities", {})
        sentiment = case_file.get("sentiment", {})
        topic = case_file.get("topic", {})
        
        # Build comprehensive prompt
        prompt = f"""{INVESTIGATOR_MANDATE}

CLAIM TO ANALYZE:
"{claim_text}"

CONTEXT & ANALYSIS:
1. ML Text Analysis: Suspicion Score = {text_suspicion:.2f} (0=trustworthy, 1=suspicious)
2. Source Credibility: Score = {source_credibility:.2f} (0=unreliable, 1=reliable)
3. Topic: {topic.get('primary_topic', 'unknown')} (confidence: {topic.get('confidence', 0):.2f})
4. Sentiment: {sentiment.get('label', 'unknown')} (manipulation risk: {sentiment.get('manipulation_risk', 'unknown')})

EXTRACTED ENTITIES:
- People: {', '.join(entities.get('people', [])) or 'None'}
- Places: {', '.join(entities.get('places', [])) or 'None'}
- Organizations: {', '.join(entities.get('organizations', [])) or 'None'}
- Dates: {', '.join(entities.get('dates', [])) or 'None'}

RESEARCH EVIDENCE:
Wikipedia Summary: {research_dossier.get('wikipedia_summary', 'No summary available')[:500]}
Web Search Results: {len(research_dossier.get('web_snippets', []))} sources found

REQUIRED OUTPUT (JSON format):
{{
    "verdict": "True" | "False" | "Misleading",
    "confidence": 0.0-1.0,
    "reasoning": "2-3 sentence explanation citing specific evidence"
}}

Analyze comprehensively and respond ONLY with valid JSON."""

        return prompt
    
    async def analyze_with_gemini(self, case_file: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze using Gemini API with optimized prompt"""
        if not self.use_gemini:
            raise RuntimeError("Gemini API not configured")
        
        try:
            # Create optimized prompt
            prompt = self.create_optimized_prompt(case_file)
            
            logger.info(f"[{self.agent_name}] Calling Gemini API...")
            self.stats["gemini_calls"] += 1
            
            # Call Gemini API
            response = await self.model.generate_content_async(prompt)
            
            # Parse JSON response
            result = json.loads(response.text)
            
            logger.info(f"[{self.agent_name}] ✅ Gemini analysis completed")
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"[{self.agent_name}] Error parsing Gemini response: {e}")
            raise ValueError(f"Invalid JSON response from Gemini: {e}")
        except Exception as e:
            logger.error(f"[{self.agent_name}] Gemini analysis failed: {e}")
            raise RuntimeError(f"Gemini analysis failed: {e}")
    
    def analyze_with_fallback(self, case_file: Dict[str, Any]) -> Dict[str, Any]:
        """Enhanced fallback analysis using all available data"""
        logger.info(f"[{self.agent_name}] Using enhanced fallback analysis")
        
        text_suspicion = case_file.get("text_suspicion_score", 0.5)
        source_credibility = case_file.get("source_credibility_score", 0.5)
        sentiment = case_file.get("sentiment", {})
        research_dossier = case_file.get("research_dossier", {})
        
        # More sophisticated logic
        wikipedia_summary = research_dossier.get("wikipedia_summary", "").lower()
        has_contradicting_evidence = any(word in wikipedia_summary for word in ["false", "not", "incorrect", "myth"])
        
        # Decision logic
        if text_suspicion > 0.8 and source_credibility < 0.3:
            verdict = "False"
            confidence = 0.85
            reasoning = "High ML suspicion score combined with low source credibility strongly indicates misinformation."
        elif text_suspicion < 0.3 and source_credibility > 0.7:
            verdict = "True"
            confidence = 0.80
            reasoning = "Low suspicion score and high source credibility suggest authentic information."
        elif has_contradicting_evidence:
            verdict = "False"
            confidence = 0.75
            reasoning = "Research evidence contradicts the claim based on Wikipedia and web sources."
        elif sentiment.get("manipulation_risk") == "HIGH":
            verdict = "Misleading"
            confidence = 0.70
            reasoning = "High emotional manipulation detected with mixed evidence indicators."
        else:
            verdict = "Misleading"
            confidence = 0.60
            reasoning = "Mixed indicators suggest the claim may be partially true or misleading."
        
        return {
            "verdict": verdict,
            "confidence": confidence,
            "reasoning": reasoning
        }
    
    async def process_task(self, task: AgentTask) -> Dict[str, Any]:
        """Process investigation task with optimization pipeline"""
        logger.info(f"[{self.agent_name}] Processing investigation task {task.task_id}")
        self.stats["total_analyses"] += 1
        
        # Extract case file
        case_file_json = task.payload.get("case_file_json", "{}")
        
        try:
            case_file = json.loads(case_file_json)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in case_file_json: {e}")
        
        claim_text = case_file.get("claim_text", "")
        claim_id = case_file.get("claim_id")
        
        # OPTIMIZATION PIPELINE
        
        # Step 1: Check cache
        cached_result = await self.check_cache(claim_text)
        if cached_result:
            return {
                "case_file": case_file,
                "investigation_result": cached_result,
                "investigation_timestamp": task.created_at.isoformat(),
                "source": "cache"
            }
        
        # Step 2: Check fact-checking databases
        db_result = await self.check_fact_databases(claim_text)
        if db_result:
            # Cache the result
            cache_manager.cache_claim_result(claim_text, db_result)
            
            return {
                "case_file": case_file,
                "investigation_result": db_result,
                "investigation_timestamp": task.created_at.isoformat(),
                "source": "fact_check_database"
            }
        
        # Step 3: Enrich case file with local ML
        case_file = await self.enrich_case_file(case_file)
        
        # Step 4: Use Gemini or fallback
        if self.use_gemini:
            try:
                result = await self.analyze_with_gemini(case_file)
                source = "gemini"
            except Exception as e:
                logger.warning(f"[{self.agent_name}] Gemini failed, using fallback: {e}")
                
                # Increment retry count if applicable
                if claim_id and self.supabase_client:
                    self.increment_retry_count(claim_id)
                
                result = self.analyze_with_fallback(case_file)
                source = "fallback"
        else:
            result = self.analyze_with_fallback(case_file)
            source = "fallback"
        
        # Cache the result
        cache_manager.cache_claim_result(claim_text, result)
        
        # Log statistics
        logger.info(f"[{self.agent_name}] Stats - Cache: {self.stats['cache_hits']}, "
                   f"FactDB: {self.stats['fact_db_hits']}, Gemini: {self.stats['gemini_calls']}, "
                   f"Total: {self.stats['total_analyses']}")
        
        return {
            "case_file": case_file,
            "investigation_result": result,
            "investigation_timestamp": task.created_at.isoformat(),
            "source": source
        }
    
    def increment_retry_count(self, claim_id: int):
        """Increment retry count for failed Gemini calls"""
        if not self.supabase_client:
            return
        
        try:
            response = self.supabase_client.table("raw_claims").select("retry_count").eq("claim_id", claim_id).execute()
            
            if response.data:
                current_retry_count = response.data[0].get("retry_count", 0)
                new_retry_count = current_retry_count + 1
                
                update_data = {
                    "retry_count": new_retry_count,
                    "status": "investigation_failed"
                }
                
                self.supabase_client.table("raw_claims").update(update_data).eq("claim_id", claim_id).execute()
                logger.info(f"[{self.agent_name}] Incremented retry_count to {new_retry_count} for claim {claim_id}")
                
                log_entry = {
                    "log_message": f"Investigation failed for claim {claim_id}. Retry count: {new_retry_count}/3"
                }
                self.supabase_client.table("system_logs").insert(log_entry).execute()
        except Exception as e:
            logger.error(f"[{self.agent_name}] Error incrementing retry count: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get agent statistics"""
        total = self.stats["total_analyses"]
        if total == 0:
            return self.stats
        
        return {
            **self.stats,
            "cache_hit_rate": f"{(self.stats['cache_hits']/total)*100:.1f}%",
            "fact_db_hit_rate": f"{(self.stats['fact_db_hits']/total)*100:.1f}%",
            "gemini_usage_rate": f"{(self.stats['gemini_calls']/total)*100:.1f}%",
            "optimization_rate": f"{((total - self.stats['gemini_calls'])/total)*100:.1f}%"
        }


# Example usage
if __name__ == "__main__":
    import asyncio
    from datetime import datetime
    
    async def main():
        agent = EnhancedInvestigatorAgent()
        
        # Test case
        case_file = {
            "claim_text": "Breaking: Major earthquake hits city center!",
            "text_suspicion_score": 0.93,
            "source_credibility_score": 0.05,
            "research_dossier": {
                "wikipedia_summary": "No recent seismic activity reported in the region.",
                "web_snippets": []
            }
        }
        
        task = AgentTask(
            task_id="test_001",
            agent_type="EnhancedInvestigatorAgent",
            priority=TaskPriority.HIGH,
            payload={"case_file_json": json.dumps(case_file)},
            created_at=datetime.now()
        )
        
        result = await agent.process_task(task)
        print(json.dumps(result, indent=2))
        print("\nAgent Statistics:")
        print(json.dumps(agent.get_stats(), indent=2))
    
    asyncio.run(main())
