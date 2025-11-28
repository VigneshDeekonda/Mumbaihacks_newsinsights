"""
Project Aegis - Investigator Agent
Expert fact-checking agent that analyzes evidence and makes final determinations
"""

import logging
from typing import Dict, Any, Optional
import json
import os
import urllib.parse

from .base_agent import BaseAgent, AgentTask, AgentStatus, TaskPriority
from backend.prompts import INVESTIGATOR_MANDATE

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class InvestigatorAgent(BaseAgent):
    """Agent responsible for expert fact-checking analysis"""
    
    def __init__(self, agent_id: str = "investigator_agent_001", gemini_api_key: Optional[str] = None, supabase_client=None):
        super().__init__(agent_id, "InvestigatorAgent")
        self.gemini_api_key = gemini_api_key or os.getenv("GEMINI_API_KEY")
        self.use_gemini = self.gemini_api_key is not None
        self.supabase_client = supabase_client
        
        if self.use_gemini:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.gemini_api_key)
                # Use a more stable model name
                self.model = genai.GenerativeModel('gemini-2.5-pro')
                logger.info(f"[{self.agent_name}] Gemini API configured successfully")
            except ImportError:
                logger.warning(f"[{self.agent_name}] Google Generative AI library not installed, using mock implementation")
                self.use_gemini = False
            except Exception as e:
                logger.error(f"[{self.agent_name}] Error configuring Gemini API: {e}")
                self.use_gemini = False
        else:
            logger.info(f"[{self.agent_name}] No Gemini API key found, using mock implementation")
    
    async def assess_source_credibility(self, source_name: str, source_url: str) -> float:
        """
        Assess the credibility of a news source using the Gemini model.
        
        Args:
            source_name (str): The name of the news source
            source_url (str): The URL of the news source
            
        Returns:
            float: A credibility score between 0.0 (very unreliable) and 1.0 (very reliable)
        """
        # Handle case where Gemini is not available
        if not self.use_gemini:
            logger.warning(f"[{self.agent_name}] Gemini not available, returning default credibility score of 0.5")
            return 0.5
        
        try:
            # Extract domain name from URL
            domain_name = ""
            try:
                parsed_url = urllib.parse.urlparse(source_url)
                domain_name = parsed_url.netloc or parsed_url.path
            except Exception as e:
                logger.warning(f"[{self.agent_name}] Error parsing URL '{source_url}': {e}")
                domain_name = source_url  # Fallback to using the full URL
            
            # Construct prompt for Gemini
            prompt = f"Please assess the general credibility of the news source named '{source_name}' often found at the domain '{domain_name}'. Consider factors like journalistic standards, reputation for accuracy, potential bias, and ownership. Provide a credibility score between 0.0 (very unreliable) and 1.0 (very reliable) and a brief justification. Respond ONLY with JSON like: {{\"score\": 0.X, \"justification\": \"Brief reason...\"}}"
            
            logger.info(f"[{self.agent_name}] Assessing credibility for source '{source_name}' at domain '{domain_name}'")
            
            # Send prompt to Gemini model
            response = await self.model.generate_content_async(prompt)
            
            # Parse the response
            try:
                result = json.loads(response.text)
                score = result.get("score")
                justification = result.get("justification", "")
                
                # Validate score
                if isinstance(score, (int, float)) and 0.0 <= score <= 1.0:
                    logger.info(f"[{self.agent_name}] Source credibility assessment for '{source_name}': score={score}, justification='{justification}'")
                    return float(score)
                else:
                    logger.warning(f"[{self.agent_name}] Invalid score '{score}' returned from Gemini for source '{source_name}', defaulting to 0.5")
                    return 0.5
                    
            except json.JSONDecodeError as e:
                logger.warning(f"[{self.agent_name}] Error parsing JSON response from Gemini for source '{source_name}': {e}, defaulting to 0.5")
                return 0.5
                
        except Exception as e:
            logger.error(f"[{self.agent_name}] Error during source credibility assessment for '{source_name}': {e}")
            return 0.5
    
    async def analyze_with_gemini(self, case_file: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze a case file using the Gemini API.
        
        Args:
            case_file (Dict[str, Any]): The case file containing claim and evidence
            
        Returns:
            Dict[str, Any]: The analysis results from Gemini
        """
        if not self.use_gemini:
            raise RuntimeError("Gemini API not configured")
        
        try:
            # Format the case file as JSON for the prompt
            case_file_json = json.dumps(case_file, indent=2)
            
            # Create the full prompt
            prompt = f"{INVESTIGATOR_MANDATE}\n\nCASE FILE:\n{case_file_json}"
            
            logger.info(f"[{self.agent_name}] Sending case to Gemini for analysis")
            
            # Call the Gemini API
            response = await self.model.generate_content_async(prompt)
            
            # Parse the JSON response
            result = json.loads(response.text)
            
            logger.info(f"[{self.agent_name}] Gemini analysis completed successfully")
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"[{self.agent_name}] Error parsing Gemini response as JSON: {e}")
            raise ValueError(f"Invalid JSON response from Gemini: {e}")
        except Exception as e:
            logger.error(f"[{self.agent_name}] Error during Gemini analysis: {e}")
            raise RuntimeError(f"Gemini analysis failed: {e}")
    
    def analyze_with_mock(self, case_file: Dict[str, Any]) -> Dict[str, Any]:
        """
        Mock analysis implementation for demonstration purposes.
        
        Args:
            case_file (Dict[str, Any]): The case file containing claim and evidence
            
        Returns:
            Dict[str, Any]: The mock analysis results
        """
        logger.info(f"[{self.agent_name}] Using mock analysis implementation")
        
        # Extract key information from case file
        claim_text = case_file.get("claim_text", "")
        text_suspicion_score = case_file.get("text_suspicion_score", 0.5)
        source_credibility_score = case_file.get("source_credibility_score", 0.5)
        research_dossier = case_file.get("research_dossier", {})
        
        logger.info(f"[{self.agent_name}] Scores - Text: {text_suspicion_score:.4f}, Source: {source_credibility_score:.4f}")
        
        # Simple mock logic based on scores
        if text_suspicion_score > 0.8 and source_credibility_score < 0.3:
            verdict = "False"
            confidence = 0.9
            reasoning = "High suspicion score and low source credibility indicate misinformation."
        elif text_suspicion_score < 0.3 and source_credibility_score > 0.7:
            verdict = "True"
            confidence = 0.8
            reasoning = "Low suspicion score and high source credibility suggest authentic information."
        else:
            verdict = "Misleading"
            confidence = 0.6
            reasoning = "Mixed indicators require further investigation for complete accuracy."
        
        result = {
            "verdict": verdict,
            "confidence": confidence,
            "reasoning": reasoning
        }
        
        logger.info(f"[{self.agent_name}] Verdict: {verdict}, Confidence: {confidence:.2f}")
        return result
    
    def increment_retry_count(self, claim_id: int):
        """
        Increment the retry_count for a claim and update its status.
        
        Args:
            claim_id (int): The ID of the claim to update
        """
        if not self.supabase_client:
            logger.warning(f"[{self.agent_name}] Cannot increment retry count - no Supabase client")
            return
        
        try:
            # Get current retry count
            response = self.supabase_client.table("raw_claims").select("retry_count").eq("claim_id", claim_id).execute()
            
            if response.data:
                current_retry_count = response.data[0].get("retry_count", 0)
                new_retry_count = current_retry_count + 1
                
                # Update retry count and status
                update_data = {
                    "retry_count": new_retry_count,
                    "status": "investigation_failed"
                }
                
                self.supabase_client.table("raw_claims").update(update_data).eq("claim_id", claim_id).execute()
                logger.info(f"[{self.agent_name}] Incremented retry_count to {new_retry_count} for claim {claim_id}")
                
                # Log the failure
                log_entry = {
                    "log_message": f"Investigation failed for claim {claim_id}. Retry count: {new_retry_count}/3"
                }
                self.supabase_client.table("system_logs").insert(log_entry).execute()
            else:
                logger.error(f"[{self.agent_name}] Claim {claim_id} not found in database")
                
        except Exception as e:
            logger.error(f"[{self.agent_name}] Error incrementing retry count: {e}")
    
    async def process_task(self, task: AgentTask) -> Dict[str, Any]:
        """
        Process a task to investigate a claim.
        
        Args:
            task (AgentTask): The task containing the case file to investigate
            
        Returns:
            Dict[str, Any]: The investigation results
        """
        logger.info(f"[{self.agent_name}] Processing investigation task {task.task_id}")
        
        # Extract case file from payload
        case_file_json = task.payload.get("case_file_json", "{}")
        
        try:
            case_file = json.loads(case_file_json)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in case_file_json: {e}")
        
        # Extract claim_id for retry tracking
        claim_id = case_file.get("claim_id")
        
        # Perform analysis using either Gemini or mock implementation
        if self.use_gemini:
            try:
                result = await self.analyze_with_gemini(case_file)
            except Exception as e:
                logger.error(f"[{self.agent_name}] Gemini analysis failed: {e}")
                
                # Increment retry count if we have claim_id and supabase client
                if claim_id and self.supabase_client:
                    self.increment_retry_count(claim_id)
                
                # Re-raise the exception to let coordinator know it failed
                raise RuntimeError(f"Investigator analysis failed: {e}")
        else:
            result = self.analyze_with_mock(case_file)
        
        return {
            "case_file": case_file,
            "investigation_result": result,
            "investigation_timestamp": task.created_at.isoformat()
        }


# Example usage
if __name__ == "__main__":
    import asyncio
    from datetime import datetime
    
    async def main():
        # Create the investigator agent
        investigator_agent = InvestigatorAgent()
        
        # Create a sample case file
        sample_case_file = {
            "claim_text": "The Earth is flat",
            "text_suspicion_score": 0.95,
            "source_credibility_score": 0.1,
            "research_dossier": {
                "wikipedia_summary": "Earth is the third planet from the Sun and the only astronomical object known to harbor life.",
                "web_snippets": [
                    "NASA evidence for spherical Earth",
                    "Ships disappearing hull-first over horizon proves Earth is round"
                ]
            }
        }
        
        # Create a sample task
        task = AgentTask(
            task_id="investigation_task_001",
            agent_type="InvestigatorAgent",
            priority=TaskPriority.HIGH,
            payload={
                "case_file_json": json.dumps(sample_case_file)
            },
            created_at=datetime.now()
        )
        
        # Process the task
        result = await investigator_agent.process_task(task)
        print("Investigator Agent Result:")
        print(json.dumps(result, indent=2))
    
    # Run the example
    asyncio.run(main())