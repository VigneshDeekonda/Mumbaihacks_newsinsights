"""
Project Aegis - Research Agent
Gathers evidence from Wikipedia and web search results
"""

import wikipedia
from googlesearch import search
import re
import logging
from typing import Dict, Any, List

from .base_agent import BaseAgent, AgentTask, AgentStatus, TaskPriority

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ResearchAgent(BaseAgent):
    """Agent responsible for gathering evidence from Wikipedia and web searches"""
    
    def __init__(self, agent_id: str = "research_agent_001"):
        super().__init__(agent_id, "ResearchAgent")
        
    def extract_search_terms(self, claim_text: str) -> List[str]:
        """
        Extract key terms from a claim for more effective searching.
        
        Args:
            claim_text (str): The claim text
            
        Returns:
            List[str]: A list of potential search terms
        """
        logger.info(f"[{self.agent_name}] Extracting search terms from claim: {claim_text[:50]}...")
        
        # Remove common words and extract potential key terms
        stop_words = {'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 
                      'do', 'does', 'did', 'will', 'would', 'could', 'should', 'the', 'a', 'an', 
                      'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 
                      'about', 'against', 'between', 'into', 'through', 'during', 'before', 
                      'after', 'above', 'below', 'up', 'down', 'out', 'off', 'over', 'under'}
        
        # Simple tokenization
        words = re.findall(r'\b\w+\b', claim_text.lower())
        key_terms = [word for word in words if word not in stop_words and len(word) > 2]
        
        # Return unique terms
        result = list(set(key_terms))
        logger.info(f"[{self.agent_name}] Extracted {len(result)} search terms: {result[:5]}")
        return result
    
    async def gather_evidence(self, claim_text: str) -> Dict[str, Any]:
        """
        Gather evidence from Wikipedia and web search results for a given claim.
        
        Args:
            claim_text (str): The claim to investigate
            
        Returns:
            Dict[str, Any]: A dictionary containing the research dossier
        """
        logger.info(f"[{self.agent_name}] Gathering evidence for claim: {claim_text[:50]}...")
        
        # Part A: Wikipedia Search
        wikipedia_summary = None
        try:
            logger.info(f"[{self.agent_name}] Starting Wikipedia search")
            # Extract key terms for better search results
            search_terms = self.extract_search_terms(claim_text)
            
            # Try searching with the full claim first
            try:
                wikipedia_summary = wikipedia.summary(claim_text, sentences=3)
                logger.info(f"[{self.agent_name}] Wikipedia summary found using full claim")
            except wikipedia.exceptions.DisambiguationError as e:
                # If there are multiple pages, try the first option
                try:
                    wikipedia_summary = wikipedia.summary(e.options[0], sentences=3)
                    logger.info(f"[{self.agent_name}] Wikipedia summary found using disambiguation option: {e.options[0]}")
                except Exception as ex:
                    logger.warning(f"[{self.agent_name}] Disambiguation option failed: {ex}")
                    # If that fails, try with key terms
                    for term in search_terms[:3]:  # Try first 3 terms
                        try:
                            wikipedia_summary = wikipedia.summary(term, sentences=3)
                            logger.info(f"[{self.agent_name}] Wikipedia summary found using term: {term}")
                            break
                        except Exception as ex2:
                            logger.debug(f"[{self.agent_name}] Term '{term}' search failed: {ex2}")
                            continue
            except wikipedia.exceptions.PageError:
                # If no page is found with the full claim, try with key terms
                logger.info(f"[{self.agent_name}] Full claim not found, trying key terms")
                for term in search_terms[:3]:  # Try first 3 terms
                    try:
                        wikipedia_summary = wikipedia.summary(term, sentences=3)
                        logger.info(f"[{self.agent_name}] Wikipedia summary found using term: {term}")
                        break
                    except Exception as ex:
                        logger.debug(f"[{self.agent_name}] Term '{term}' search failed: {ex}")
                        continue
        except Exception as e:
            # Catch any other Wikipedia-related errors
            logger.error(f"[{self.agent_name}] Wikipedia search error: {e}")
            wikipedia_summary = None
        
        if wikipedia_summary:
            logger.info(f"[{self.agent_name}] Wikipedia summary length: {len(wikipedia_summary)} characters")
        else:
            logger.warning(f"[{self.agent_name}] No Wikipedia summary found")
        
        # Part B: Web Search
        web_snippets = []
        try:
            logger.info(f"[{self.agent_name}] Starting web search for: {claim_text}")
            # Use the googlesearch library to find search results
            # Note: The googlesearch library returns URLs, not snippets
            # It may return empty results due to IP restrictions or rate limiting
            search_results = list(search(claim_text, num_results=3, sleep_interval=1))
            web_snippets = search_results
            logger.info(f"[{self.agent_name}] Web search returned {len(web_snippets)} results")
        except Exception as e:
            # If the search fails, return an empty list
            logger.error(f"[{self.agent_name}] Web search error: {e}")
            web_snippets = []
        
        # Combine findings into a structured dictionary (the "dossier")
        dossier = {
            "wikipedia_summary": wikipedia_summary,
            "web_snippets": web_snippets
        }
        
        logger.info(f"[{self.agent_name}] Evidence gathering complete. Wikipedia: {'Yes' if wikipedia_summary else 'No'}, Web results: {len(web_snippets)}")
        return dossier
    
    async def process_task(self, task: AgentTask) -> Dict[str, Any]:
        """
        Process a task to gather evidence for a claim.
        
        Args:
            task (AgentTask): The task containing the claim to investigate
            
        Returns:
            Dict[str, Any]: The research dossier with evidence
        """
        logger.info(f"[{self.agent_name}] Processing research task {task.task_id}")
        
        # Extract claim text from payload
        claim_text = task.payload.get("claim_text", "")
        
        if not claim_text:
            raise ValueError("No claim text provided in task payload")
        
        # Gather evidence
        evidence_dossier = await self.gather_evidence(claim_text)
        
        return {
            "claim_text": claim_text,
            "research_dossier": evidence_dossier,
            "research_timestamp": task.created_at.isoformat()
        }


# Example usage
if __name__ == "__main__":
    import asyncio
    from datetime import datetime
    
    async def main():
        # Create the research agent
        research_agent = ResearchAgent()
        
        # Create a sample task
        task = AgentTask(
            task_id="research_task_001",
            agent_type="ResearchAgent",
            priority=TaskPriority.NORMAL,
            payload={
                "claim_text": "The Eiffel Tower is located in Berlin"
            },
            created_at=datetime.now()
        )
        
        # Process the task
        result = await research_agent.process_task(task)
        print("Research Agent Result:")
        print(result)
    
    # Run the example
    asyncio.run(main())