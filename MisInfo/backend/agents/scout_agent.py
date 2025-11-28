import asyncio
import json
import logging
import os
from typing import List, Dict, Any, Optional, Set
import httpx
from .base_agent import BaseAgent, AgentTask, AgentStatus, TaskPriority

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ScoutAgent(BaseAgent):
    """Agent responsible for discovering new claims"""
    
    def __init__(self, agent_id: str = "scout_agent_001"):
        super().__init__(agent_id, "ScoutAgent")
        # Removed self.discovered_claims = set() - now using persistent database checking
        
        # Log API key presence at startup
        newsdata_api_key = os.getenv("NEWSDATA_API_KEY")
        if newsdata_api_key:
            logger.info(f"[{self.agent_name}] NEWSDATA_API_KEY: ✓ (length: {len(newsdata_api_key)})")
        else:
            logger.info(f"[{self.agent_name}] NEWSDATA_API_KEY: ✗")
        
        guardian_api_key = os.getenv("GUARDIAN_API_KEY")
        if guardian_api_key:
            logger.info(f"[{self.agent_name}] GUARDIAN_API_KEY: ✓ (length: {len(guardian_api_key)})")
        else:
            logger.info(f"[{self.agent_name}] GUARDIAN_API_KEY: ✗")
        
        # Suspicious keywords that indicate potential misinformation
        self.suspicious_keywords = [
            "miracle cure", "doctors hate", "secret", "they don't want you to know",
            "conspiracy", "hoax", "fake", "exposed", "truth revealed", "shocking",
            "banned", "censored", "cover up", "hidden", "suppressed",
            "cure cancer", "cure all", "100% effective", "guaranteed",
            "big pharma", "mainstream media lies", "wake up", "sheeple",
            "breaking", "urgent", "alert", "warning", "must read"
        ]
        
        # Domains known for posting misinformation
        self.unreliable_domains = [
            'infowars.com', 'naturalnews.com', 'dailywire.com', 'breitbart.com',
            'theonion.com', 'empirenews.net', 'nationalreport.net', 'newsmutiny.com',
            'duffelblog.com', 'clickhole.com', 'borowitzreport.com', 'chicksonright.com',
            'conservativetribune.com', 'dcclothesline.com', 'godlikeproductions.com',
            'govtslaves.info', 'iceagenow.info', 'lewrockwell.com', 'libertymovementradio.com',
            'libertytalk.fm', 'prisonplanet.com', 'rawstory.com', 'redflagnews.com',
            'rense.com', 'rumormillnews.com', 'sott.net', 'thedailysheeple.com',
            'theforbiddenknowledge.com', 'truthfrequencyradio.com', 'wakingupwisconsin.com',
            'whatreallyhappened.com', 'worldtruth.tv', 'zerohedge.com', 'activistpost.com',
            'beforeitsnews.com', 'bients.com', 'collective-evolution.com', 'consciouslifenews.com',
            'davidwolfe.com', 'endtimeheadlines.org', 'globalresearch.ca', 'govtslaves.com',
            'healthimpactnews.com', 'healthnutnews.com', 'in5d.com', 'infiniteunknown.net',
            'informationclearinghouse.info', 'intellihub.com', 'investmentwatchblog.com',
            'jonesreport.com', 'kingworldnews.com', 'naturalblaze.com', 'naturalnewsblogs.com',
            'neonnettle.com', 'newstarget.com', 'nowtheendbegins.com', 'oilgeopolitics.net',
            'presstv.com', 'prisonplanet.tv', 'realjewnews.com', 'redstate.com',
            'rt.com', 'shtfplan.com', 'silverdoctors.com', 'silverstealers.net',
            'sonsoflibertyradio.com', 'thedailymash.co.uk', 'thefreethoughtproject.com',
            'thelibertybeacon.com', 'themindunleashed.com', 'truthdig.com', 'truthwiki.org',
            'ufoholic.com', 'unz.com', 'veteranstoday.com', 'washingtonsblog.com',
            'wearechange.org', 'whatdoesitmean.com', 'whowhatwhy.org', 'wikispooks.com',
            'worldnewspolitics.com', 'yournewswire.com', 'zengardner.com', 'zerohedge.com'
        ]
        
    async def process_task(self, task: AgentTask) -> Dict[str, Any]:
        """
        Process a task to discover new claims from real news sources.
        This method maintains compatibility with the base class.
        
        Args:
            task (AgentTask): The task to process
            
        Returns:
            Dict[str, Any]: The discovered claims
        """
        # Call the enhanced method with no existing URLs (for backward compatibility)
        return await self.process_task_with_urls(task, set())
    
    async def process_task_with_urls(self, task: AgentTask, existing_claim_urls: Optional[Set[str]] = None) -> Dict[str, Any]:
        """
        Process a task to discover new claims from real news sources with persistent duplicate checking.
        
        Args:
            task (AgentTask): The task to process
            existing_claim_urls (Set[str]): Set of URLs that already exist in the database to avoid duplicates
            
        Returns:
            Dict[str, Any]: The discovered claims
        """
        logger.info(f"[{self.agent_name}] Processing discovery task {task.task_id}")
        
        # Discover claims from NewsAPI
        discovered_claims = []
        
        # Use empty set if None provided
        if existing_claim_urls is None:
            existing_claim_urls = set()
        
        try:
            # Removed NEWS_API_KEY check since we're no longer using NewsAPI.org
            newsdata_api_key = os.getenv("NEWSDATA_API_KEY")
            guardian_api_key = os.getenv("GUARDIAN_API_KEY")
            
            # Search for controversial/fact-checkable topics with suspicious keywords
            search_queries = [
                "conspiracy OR hoax OR fake news",
                "vaccine microchip OR vaccine tracking",
                "climate change hoax OR climate conspiracy",
                "election fraud OR stolen election",
                "miracle cure OR secret cure OR doctors hate",
                "breaking news OR urgent alert"
            ]
            
            if newsdata_api_key or guardian_api_key:
                # Use async httpx client for non-blocking I/O
                async with httpx.AsyncClient(timeout=10.0) as client:
                    # Removed NewsAPI.org integration section
                    
                    # Fetch from Newsdata.io if key is available
                    if newsdata_api_key:
                        logger.info(f"[{self.agent_name}] Starting Newsdata.io discovery")
                        # Loop through every query in the search_queries list
                        for query in search_queries:
                            try:
                                # Make request to Newsdata.io API
                                response = await client.get(
                                    "https://newsdata.io/api/1/news",
                                    params={
                                        "apikey": newsdata_api_key,
                                        "q": query,
                                        "language": "en"
                                    }
                                )
                                
                                # Add delay to respect rate limits
                                await asyncio.sleep(1)
                                
                                if response.status_code == 200:
                                    data = response.json()
                                    articles = data.get("results", [])
                                    logger.info(f"[{self.agent_name}] Newsdata.io - Found {len(articles)} articles for query: {query}")
                                    
                                    for article in articles:
                                        title = article.get("title", "")
                                        description = article.get("description", "")
                                        url = article.get("link", "")
                                        source_id = article.get("source_id", "Unknown")
                                        creator = article.get("creator", ["Unknown"])
                                        source_name = creator[0] if creator and isinstance(creator, list) and len(creator) > 0 else source_id
                                        pub_date = article.get("pubDate", "")
                                        
                                        # Use title or description as claim
                                        claim_text = title if title else description
                                        
                                        if not claim_text or len(claim_text) < 20:
                                            continue
                                        
                                        # Check if URL already exists in database (persistent duplicate checking)
                                        if url in existing_claim_urls:
                                            logger.info(f"[{self.agent_name}] Skipping duplicate claim from Newsdata.io URL: {url}")
                                            continue
                                        
                                        # Check for suspicious keywords
                                        is_suspicious = any(keyword in claim_text.lower() for keyword in self.suspicious_keywords)
                                        
                                        # Filter out reputable sources reporting normally
                                        reputable_sources = ["Reuters", "Associated Press", "BBC News", "NPR", "The Guardian", "CNN", "BBC"]
                                        is_reputable = any(rep_source in source_name for rep_source in reputable_sources)
                                        
                                        # Check if source is from an unreliable domain
                                        is_unreliable_domain = any(domain in url.lower() for domain in self.unreliable_domains)
                                        
                                        # Discover if: suspicious keywords OR unreliable domain OR (controversial topic AND not reputable source)
                                        # Always discover a few claims even if not suspicious to ensure we have content
                                        if is_suspicious or is_unreliable_domain or (len(discovered_claims) < 10 and not is_reputable) or len(discovered_claims) < 5:
                                            logger.info(f"[{self.agent_name}] ✓ Discovering from Newsdata.io: {claim_text[:60]}... (suspicious={is_suspicious}, unreliable_domain={is_unreliable_domain}, source={source_name})")
                                            discovered_claims.append({
                                                "claim_text": claim_text[:200],  # Limit length
                                                "source_metadata_json": json.dumps({
                                                    "source_url": url,
                                                    "source_name": source_name,
                                                    "published_at": pub_date,
                                                    "discovered_via": "Newsdata.io"
                                                })
                                            })
                                            
                                            # Increase the total limit of claims found per cycle
                                            if len(discovered_claims) >= 15:
                                                break
                                else:
                                    logger.warning(f"[{self.agent_name}] Newsdata.io API returned status code {response.status_code} for query: {query}")
                                    
                            except httpx.TimeoutException:
                                logger.warning(f"[{self.agent_name}] Newsdata.io request timed out for query: {query}")
                            except httpx.RequestError as e:
                                logger.warning(f"[{self.agent_name}] Error fetching from Newsdata.io for query '{query}': {e}")
                            except httpx.HTTPStatusError as e:
                                logger.warning(f"[{self.agent_name}] HTTP error from Newsdata.io for query '{query}': {e}")
                            except Exception as e:
                                logger.warning(f"[{self.agent_name}] Unexpected error in Newsdata.io discovery for query '{query}': {e}")
                                
                            # If we've reached our limit, break out of the query loop as well
                            if len(discovered_claims) >= 15:
                                break
                    
                    # Fetch from The Guardian if key is available
                    if guardian_api_key:
                        logger.info(f"[{self.agent_name}] Starting The Guardian discovery")
                        # Loop through every query in the search_queries list
                        # The Guardian might need simpler keywords
                        guardian_queries = [
                            "conspiracy",
                            "hoax",
                            "fake news",
                            "vaccine",
                            "climate change",
                            "election",
                            "miracle cure",
                            "breaking news"
                        ]
                        
                        for query in guardian_queries:
                            try:
                                # Make request to The Guardian API
                                response = await client.get(
                                    "https://content.guardianapis.com/search",
                                    params={
                                        "api-key": guardian_api_key,
                                        "q": query,
                                        "show-fields": "headline,bodyText",
                                        "order-by": "newest"
                                    }
                                )
                                
                                # Add delay to respect rate limits (1.1 seconds as per requirement)
                                await asyncio.sleep(1.1)
                                
                                if response.status_code == 200:
                                    data = response.json()
                                    articles = data.get("response", {}).get("results", [])
                                    logger.info(f"[{self.agent_name}] The Guardian - Found {len(articles)} articles for query: {query}")
                                    
                                    for article in articles:
                                        headline = article.get("fields", {}).get("headline", "")
                                        web_url = article.get("webUrl", "")
                                        body_text = article.get("fields", {}).get("bodyText", "")
                                        pub_date = article.get("webPublicationDate", "")
                                        
                                        # Use headline as claim
                                        claim_text = headline
                                        
                                        if not claim_text or len(claim_text) < 20:
                                            continue
                                        
                                        # Check if URL already exists in database (persistent duplicate checking)
                                        if web_url in existing_claim_urls:
                                            logger.info(f"[{self.agent_name}] Skipping duplicate claim from The Guardian URL: {web_url}")
                                            continue
                                        
                                        # Check for suspicious keywords
                                        is_suspicious = any(keyword in claim_text.lower() for keyword in self.suspicious_keywords)
                                        
                                        # Filter out reputable sources reporting normally
                                        # The Guardian is a reputable source, so we'll set is_reputable to True
                                        is_reputable = True
                                        
                                        # Check if source is from an unreliable domain (shouldn't be for The Guardian)
                                        is_unreliable_domain = any(domain in web_url.lower() for domain in self.unreliable_domains)
                                        
                                        # Discover if: suspicious keywords OR unreliable domain OR (controversial topic AND not reputable source)
                                        # Always discover a few claims even if not suspicious to ensure we have content
                                        if is_suspicious or is_unreliable_domain or (len(discovered_claims) < 10 and not is_reputable) or len(discovered_claims) < 5:
                                            logger.info(f"[{self.agent_name}] ✓ Discovering from The Guardian: {claim_text[:60]}... (suspicious={is_suspicious}, unreliable_domain={is_unreliable_domain})")
                                            discovered_claims.append({
                                                "claim_text": claim_text[:200],  # Limit length
                                                "source_metadata_json": json.dumps({
                                                    "source_url": web_url,
                                                    "source_name": "The Guardian",
                                                    "published_at": pub_date,
                                                    "discovered_via": "The Guardian"
                                                })
                                            })
                                            
                                            # Increase the total limit of claims found per cycle
                                            if len(discovered_claims) >= 15:
                                                break
                                else:
                                    logger.warning(f"[{self.agent_name}] The Guardian API returned status code {response.status_code} for query: {query}")
                                    
                            except httpx.TimeoutException:
                                logger.warning(f"[{self.agent_name}] The Guardian request timed out for query: {query}")
                            except httpx.RequestError as e:
                                logger.warning(f"[{self.agent_name}] Error fetching from The Guardian for query '{query}': {e}")
                            except httpx.HTTPStatusError as e:
                                logger.warning(f"[{self.agent_name}] HTTP error from The Guardian for query '{query}': {e}")
                            except Exception as e:
                                logger.warning(f"[{self.agent_name}] Unexpected error in The Guardian discovery for query '{query}': {e}")
                                
                            # If we've reached our limit, break out of the query loop as well
                            if len(discovered_claims) >= 15:
                                break
                                
            else:
                logger.warning(f"[{self.agent_name}] No API keys configured (NEWSDATA_API_KEY or GUARDIAN_API_KEY)")
                
        except Exception as e:
            logger.error(f"[{self.agent_name}] Error in discovery: {e}")
        
        # Updated logging message to reflect that NewsAPI.org is no longer being used
        logger.info(f"[{self.agent_name}] Discovered {len(discovered_claims)} potential claims from Newsdata.io and The Guardian")
        
        return {
            "claims": discovered_claims,
            "discovery_timestamp": task.created_at.isoformat()
        }


# Example usage
if __name__ == "__main__":
    import asyncio
    from datetime import datetime
    
    async def main():
        # Create the scout agent
        scout_agent = ScoutAgent()
        
        # Create a sample task
        task = AgentTask(
            task_id="discovery_task_001",
            agent_type="ScoutAgent",
            priority=TaskPriority.NORMAL,
            payload={},
            created_at=datetime.now()
        )
        
        # Process the task
        result = await scout_agent.process_task(task)
        print("Scout Agent Result:")
        print(json.dumps(result, indent=2))
    
    # Run the example
    asyncio.run(main())