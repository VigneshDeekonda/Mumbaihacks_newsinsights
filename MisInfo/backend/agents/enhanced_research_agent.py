"""
Project Aegis - Enhanced Research Agent
Multi-API integration for comprehensive evidence gathering
"""

import asyncio
import logging
import os
import sys
import re
from typing import Dict, Any, List, Set
import requests

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.base_agent import BaseAgent, AgentTask, AgentStatus, TaskPriority

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EnhancedResearchAgent(BaseAgent):
    """
    Enhanced Research Agent that integrates multiple free APIs:
    1. NewsAPI - News coverage verification
    2. Google Fact Check API - Existing fact-checks
    3. PubMed - Medical/health literature
    4. arXiv - Scientific papers
    5. Reddit - Community discussions
    6. Wikipedia - General knowledge base
    """
    
    def __init__(self, agent_id: str = "enhanced_research_001"):
        super().__init__(agent_id, "EnhancedResearchAgent")
        
        # Load API keys from environment variables
        import os
        self.news_api_key = os.getenv("NEWS_API_KEY")
        self.google_factcheck_api_key = os.getenv("GOOGLE_FACT_CHECK_API_KEY")
        self.reddit_client_id = os.getenv("REDDIT_CLIENT_ID")
        self.reddit_client_secret = os.getenv("REDDIT_CLIENT_SECRET")
        self.pubmed_email = os.getenv("PUBMED_EMAIL", "project.aegis@example.com")
        
        # Initialize spaCy NLP model for entity recognition (optional)
        self.nlp = None
        self._init_spacy()
        
        # Log environment variable loading
        logger.info(f"[{self.agent_name}] Environment variables loaded:")
        logger.info(f"[{self.agent_name}] NEWS_API_KEY: {'✓' if self.news_api_key else '✗'} (length: {len(self.news_api_key) if self.news_api_key else 0})")
        logger.info(f"[{self.agent_name}] GOOGLE_FACT_CHECK_API_KEY: {'✓' if self.google_factcheck_api_key else '✗'}")
        logger.info(f"[{self.agent_name}] REDDIT_CLIENT_ID: {'✓' if self.reddit_client_id else '✗'}")
        logger.info(f"[{self.agent_name}] REDDIT_CLIENT_SECRET: {'✓' if self.reddit_client_secret else '✗'}")
        logger.info(f"[{self.agent_name}] PUBMED_EMAIL: {self.pubmed_email}")
        
        # Initialize API clients
        self._init_reddit_client()
        self._init_pubmed()
        self._init_arxiv()
        self._init_wikipedia()
        
        # Log API availability
        self._log_api_status()
    
    def _init_spacy(self):
        """Initialize spaCy NLP model for entity recognition"""
        try:
            import spacy
            # Try to load the English model
            try:
                self.nlp = spacy.load("en_core_web_sm")
                logger.info(f"[{self.agent_name}] spaCy NLP model initialized")
            except OSError:
                logger.warning(f"[{self.agent_name}] spaCy English model not found. Install with: python -m spacy download en_core_web_sm")
        except ImportError:
            logger.warning(f"[{self.agent_name}] spaCy not installed. Install with: pip install spacy")
    
    def _init_reddit_client(self):
        """Initialize Reddit asyncpraw client"""
        self.reddit_client = None
        
        if self.reddit_client_id and self.reddit_client_secret:
            try:
                import asyncpraw
                self.reddit_client = asyncpraw.Reddit(
                    client_id=self.reddit_client_id,
                    client_secret=self.reddit_client_secret,
                    user_agent="ProjectAegis/1.0 (Enhanced Research Agent)"
                )
                logger.info(f"[{self.agent_name}] Reddit API initialized with asyncpraw")
            except ImportError:
                logger.warning(f"[{self.agent_name}] asyncpraw not installed. Install with: pip install asyncpraw")
            except Exception as e:
                logger.error(f"[{self.agent_name}] Error initializing Reddit client: {e}")
        else:
            logger.warning(f"[{self.agent_name}] Reddit credentials not found in environment")
    
    def _init_pubmed(self):
        """Initialize PubMed/Entrez"""
        self.pubmed_available = False
        
        try:
            from Bio import Entrez
            Entrez.email = self.pubmed_email
            self.Entrez = Entrez
            self.pubmed_available = True
            logger.info(f"[{self.agent_name}] PubMed API initialized")
        except ImportError:
            logger.warning(f"[{self.agent_name}] BioPython not installed. Install with: pip install biopython")
        except Exception as e:
            logger.error(f"[{self.agent_name}] Error initializing PubMed: {e}")
    
    def _init_arxiv(self):
        """Initialize arXiv client"""
        self.arxiv_available = False
        
        try:
            import arxiv
            self.arxiv = arxiv
            self.arxiv_available = True
            logger.info(f"[{self.agent_name}] arXiv API initialized")
        except ImportError:
            logger.warning(f"[{self.agent_name}] arxiv library not installed. Install with: pip install arxiv")
        except Exception as e:
            logger.error(f"[{self.agent_name}] Error initializing arXiv: {e}")
    
    def _init_wikipedia(self):
        """Initialize Wikipedia client"""
        self.wikipedia_available = False
        
        try:
            import wikipedia
            self.wikipedia = wikipedia
            self.wikipedia_available = True
            logger.info(f"[{self.agent_name}] Wikipedia API initialized")
        except ImportError:
            logger.warning(f"[{self.agent_name}] wikipedia library not installed. Install with: pip install wikipedia")
        except Exception as e:
            logger.error(f"[{self.agent_name}] Error initializing Wikipedia: {e}")
    
    def _log_api_status(self):
        """Log which APIs are available"""
        status = {
            "NewsAPI": "✓" if self.news_api_key else "✗",
            "Google Fact Check": "✓" if self.google_factcheck_api_key else "✗",
            "Reddit": "✓" if self.reddit_client else "✗",
            "PubMed": "✓" if self.pubmed_available else "✗",
            "arXiv": "✓" if self.arxiv_available else "✗",
            "Wikipedia": "✓" if self.wikipedia_available else "✗"
        }
        logger.info(f"[{self.agent_name}] API Status: {status}")
    
    def _extract_entities_simple(self, claim_text: str) -> List[str]:
        """Simple entity extraction using basic NLP techniques"""
        # Split into words and filter out common stop words
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were',
            'be', 'been', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'must',
            'can', 'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they', 'me', 'him', 'her', 'us', 'them'
        }
        
        # Basic tokenization
        words = re.findall(r'\b\w+\b', claim_text.lower())
        
        # Filter out stop words and short words
        entities = [word.capitalize() for word in words if len(word) > 2 and word not in stop_words]
        
        # Remove duplicates while preserving order
        seen = set()
        unique_entities = []
        for entity in entities:
            if entity not in seen:
                seen.add(entity)
                unique_entities.append(entity)
        
        return unique_entities[:5]  # Return top 5 entities
    
    def _extract_entities_spacy(self, claim_text: str) -> List[str]:
        """Extract entities using spaCy NLP model"""
        if not self.nlp:
            return self._extract_entities_simple(claim_text)
        
        try:
            doc = self.nlp(claim_text)
            entities = []
            
            # Extract named entities (GPE = Geopolitical Entity, LOC = Location, ORG = Organization, PERSON)
            for ent in doc.ents:
                if ent.label_ in ["GPE", "LOC", "ORG", "PERSON", "NORP", "EVENT"]:
                    entities.append(ent.text)
            
            # Also extract noun chunks for additional context
            for chunk in doc.noun_chunks:
                if len(chunk.text.split()) <= 3:  # Keep short noun phrases
                    entities.append(chunk.text)
            
            # Remove duplicates while preserving order
            seen = set()
            unique_entities = []
            for entity in entities:
                clean_entity = entity.strip()
                if clean_entity and clean_entity not in seen:
                    seen.add(clean_entity)
                    unique_entities.append(clean_entity)
            
            return unique_entities[:5]  # Return top 5 entities
        except Exception as e:
            logger.warning(f"[{self.agent_name}] Error in spaCy entity extraction: {e}")
            return self._extract_entities_simple(claim_text)
    
    def _generate_refined_query(self, claim_text: str) -> str:
        """Generate a refined search query based on the claim text"""
        # Extract entities using spaCy or simple method
        entities = self._extract_entities_spacy(claim_text)
        
        if not entities:
            # If no entities found, use the original claim text (truncated)
            return claim_text[:100]
        
        # Combine entities into a meaningful query
        # For example: "India moon landing" from "India is on moon"
        if len(entities) == 1:
            return entities[0]
        elif len(entities) == 2:
            return f"{entities[0]} {entities[1]}"
        else:
            # For more entities, create a more focused query
            return " ".join(entities[:3])
    
    def _filter_wikipedia_result(self, wiki_result: Dict, original_claim: str) -> Dict:
        """Filter Wikipedia results for relevance to the original claim"""
        if not wiki_result.get("found", False) or not wiki_result.get("summary", ""):
            return wiki_result
        
        summary = wiki_result["summary"].lower()
        original_claim_lower = original_claim.lower()
        
        # Extract key entities from the original claim
        key_entities = self._extract_entities_spacy(original_claim)
        
        # If no entities extracted, check for basic keyword overlap
        if not key_entities:
            # Simple keyword matching
            claim_words = set(re.findall(r'\b\w+\b', original_claim_lower))
            summary_words = set(re.findall(r'\b\w+\b', summary))
            
            # Check for significant overlap
            overlap = len(claim_words.intersection(summary_words))
            if overlap < max(1, len(claim_words) // 3):
                # Not enough overlap, mark as not found
                return {"found": False, "summary": "", "url": ""}
            return wiki_result
        
        # Check if key entities appear in the summary
        relevant_entity_count = 0
        for entity in key_entities:
            if entity.lower() in summary:
                relevant_entity_count += 1
        
        # If less than half of the key entities are found, consider it irrelevant
        if relevant_entity_count < max(1, len(key_entities) // 2):
            return {"found": False, "summary": "", "url": ""}
        
        return wiki_result
    
    async def search_wikipedia(self, query: str) -> Dict:
        """Search Wikipedia for relevant information about a query"""
        if not self.wikipedia_available:
            return {"found": False, "summary": "", "url": ""}
        
        try:
            logger.debug(f"[{self.agent_name}] Searching Wikipedia for: {query}")
            
            # Search for relevant Wikipedia pages
            results = self.wikipedia.search(query, results=3)  # Get more results to choose from
            
            if results:
                # Try each result until we find a relevant one
                for result in results:
                    try:
                        summary = self.wikipedia.summary(result, sentences=3)
                        page = self.wikipedia.page(result)
                        
                        # Check if this result is relevant
                        if summary:
                            return {
                                "found": True,
                                "summary": summary,
                                "url": page.url
                            }
                    except self.wikipedia.exceptions.DisambiguationError as e:
                        # Try the first option from disambiguation
                        try:
                            summary = self.wikipedia.summary(e.options[0], sentences=3)
                            page = self.wikipedia.page(e.options[0])
                            if summary:
                                return {
                                    "found": True,
                                    "summary": summary,
                                    "url": page.url
                                }
                        except:
                            continue
                    except self.wikipedia.exceptions.PageError:
                        continue
                    except Exception:
                        continue
                        
                # If we get here, none of the results were suitable
                logger.warning(f"[{self.agent_name}] No suitable Wikipedia results found for query: {query}")
                return {"found": False, "summary": "", "url": ""}
            else:
                logger.warning(f"[{self.agent_name}] No Wikipedia results found for query: {query}")
                return {"found": False, "summary": "", "url": ""}
                
        except self.wikipedia.exceptions.DisambiguationError as e:
            logger.warning(f"[{self.agent_name}] DisambiguationError at search level for query '{query}': {e}")
            return {"found": False, "summary": "", "url": ""}
        except self.wikipedia.exceptions.PageError as e:
            logger.warning(f"[{self.agent_name}] PageError at search level for query '{query}': {e}")
            return {"found": False, "summary": "", "url": ""}
        except Exception as e:
            logger.warning(f"[{self.agent_name}] General error searching Wikipedia for query '{query}': {e}")
            return {"found": False, "summary": "", "url": ""}
    
    async def _search_newsapi(self, claim_text: str) -> Dict[str, Any]:
        """Search NewsAPI for related news coverage"""
        if not self.news_api_key:
            return {"error": "NewsAPI key not configured"}
        
        try:
            logger.debug(f"[{self.agent_name}] Searching NewsAPI...")
            
            response = requests.get(
                "https://newsapi.org/v2/everything",
                params={
                    "q": claim_text[:100],  # Limit query length
                    "apiKey": self.news_api_key,
                    "language": "en",
                    "sortBy": "relevancy",
                    "pageSize": 5
                },
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                articles = data.get('articles', [])
                
                return {
                    "headlines": [a['title'] for a in articles],
                    "sources": [a['source']['name'] for a in articles],
                    "urls": [a['url'] for a in articles],
                    "total_results": data.get('totalResults', 0)
                }
            else:
                return {"error": f"NewsAPI returned status {response.status_code}"}
                
        except requests.Timeout:
            return {"error": "NewsAPI request timed out"}
        except Exception as e:
            logger.error(f"[{self.agent_name}] NewsAPI error: {e}")
            return {"error": str(e)}
    
    async def _search_google_factcheck(self, claim_text: str) -> Dict[str, Any]:
        """Search Google Fact Check Tools API"""
        if not self.google_factcheck_api_key:
            return {"error": "Google Fact Check API key not configured"}
        
        try:
            logger.debug(f"[{self.agent_name}] Searching Google Fact Check...")
            
            response = requests.get(
                "https://factchecktools.googleapis.com/v1alpha1/claims:search",
                params={
                    "query": claim_text[:100],
                    "key": self.google_factcheck_api_key,
                    "languageCode": "en"
                },
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                claims = data.get('claims', [])
                
                if claims:
                    first_claim = claims[0]
                    claim_review = first_claim.get('claimReview', [{}])[0]
                    
                    return {
                        "found": True,
                        "verdict": claim_review.get('textualRating', 'Unknown'),
                        "source": claim_review.get('publisher', {}).get('name', 'Unknown'),
                        "url": claim_review.get('url', ''),
                        "claim_date": first_claim.get('claimDate', 'Unknown')
                    }
                else:
                    return {"found": False, "message": "No fact-checks found"}
            else:
                return {"error": f"Google Fact Check API returned status {response.status_code}"}
                
        except requests.Timeout:
            return {"error": "Google Fact Check API request timed out"}
        except Exception as e:
            logger.error(f"[{self.agent_name}] Google Fact Check error: {e}")
            return {"error": str(e)}
    
    async def _search_pubmed(self, claim_text: str) -> Dict[str, Any]:
        """Search PubMed for medical/health literature"""
        if not self.pubmed_available:
            return {"error": "PubMed not available (BioPython not installed)"}
        
        try:
            logger.debug(f"[{self.agent_name}] Searching PubMed...")
            
            # Search PubMed
            handle = self.Entrez.esearch(
                db="pubmed",
                term=claim_text[:100],
                retmax=5
            )
            record = self.Entrez.read(handle)
            handle.close()
            
            # Extract article IDs - BioPython returns special XML objects
            article_ids = list(record.get("IdList", []))  # type: ignore
            
            if article_ids:
                # Fetch article details
                handle = self.Entrez.efetch(
                    db="pubmed",
                    id=article_ids,
                    rettype="abstract",
                    retmode="text"
                )
                abstracts = handle.read()
                handle.close()
                
                # Extract count
                total_count = int(record.get("Count", len(article_ids)))  # type: ignore
                
                return {
                    "article_ids": article_ids,
                    "total_found": total_count,
                    "abstracts_preview": abstracts[:500] if abstracts else "No abstracts available"
                }
            else:
                return {"article_ids": [], "total_found": 0, "message": "No articles found"}
                
        except Exception as e:
            logger.error(f"[{self.agent_name}] PubMed error: {e}")
            return {"error": str(e)}
    
    async def _search_arxiv(self, claim_text: str) -> Dict[str, Any]:
        """Search arXiv for scientific papers"""
        if not self.arxiv_available:
            return {"error": "arXiv not available (arxiv library not installed)"}
        
        try:
            logger.debug(f"[{self.agent_name}] Searching arXiv...")
            
            # Search arXiv
            search = self.arxiv.Search(
                query=claim_text[:100],
                max_results=5,
                sort_by=self.arxiv.SortCriterion.Relevance
            )
            
            papers = []
            for result in search.results():
                papers.append({
                    "title": result.title,
                    "summary": result.summary[:200] + "...",
                    "published": result.published.strftime("%Y-%m-%d"),
                    "authors": [author.name for author in result.authors[:3]],
                    "url": result.entry_id
                })
            
            return {
                "papers": papers,
                "total_found": len(papers)
            }
            
        except Exception as e:
            logger.error(f"[{self.agent_name}] arXiv error: {e}")
            return {"error": str(e)}
    
    async def _search_reddit(self, claim_text: str) -> Dict[str, Any]:
        """Search Reddit for community discussions"""
        if not self.reddit_client:
            return {"error": "Reddit client not configured"}
        
        try:
            logger.debug(f"[{self.agent_name}] Searching Reddit...")
            
            # Search relevant subreddits
            subreddits = ['news', 'worldnews', 'science', 'skeptic', 'OutOfTheLoop']
            discussions = []
            
            for subreddit_name in subreddits:
                try:
                    subreddit = await self.reddit_client.subreddit(subreddit_name)
                    
                    # Search posts
                    async for post in subreddit.search(claim_text[:100], limit=2):
                        discussions.append({
                            "title": post.title,
                            "subreddit": subreddit_name,
                            "score": post.score,
                            "num_comments": post.num_comments,
                            "url": f"https://reddit.com{post.permalink}",
                            "created": post.created_utc
                        })
                except Exception as sub_error:
                    logger.debug(f"[{self.agent_name}] Error searching r/{subreddit_name}: {sub_error}")
                    continue
            
            return {
                "discussions": discussions,
                "total_found": len(discussions),
                "subreddits_searched": subreddits
            }
            
        except Exception as e:
            logger.error(f"[{self.agent_name}] Reddit error: {e}")
            return {"error": str(e)}
    
    async def comprehensive_research(self, claim_text: str) -> Dict[str, Any]:
        """
        Perform comprehensive research across all available APIs in parallel.
        
        Args:
            claim_text: The claim to research
            
        Returns:
            Dictionary containing results from all APIs
        """
        logger.info(f"[{self.agent_name}] Starting comprehensive research for: {claim_text[:50]}...")
        
        # Generate refined search query
        refined_query = self._generate_refined_query(claim_text)
        logger.info(f"[{self.agent_name}] Refined search query: {refined_query}")
        
        # Execute all API searches in parallel using the refined query
        results = await asyncio.gather(
            self._search_newsapi(refined_query),
            self._search_google_factcheck(refined_query),
            self._search_pubmed(refined_query),
            self._search_arxiv(refined_query),
            self._search_reddit(refined_query),
            self.search_wikipedia(refined_query),
            return_exceptions=True  # Don't let one failure stop others
        )
        
        # Filter Wikipedia result for relevance (only if it's not an exception and is a dict)
        processed_results = list(results)
        if not isinstance(results[5], Exception) and isinstance(results[5], dict):
            filtered_wiki_result = self._filter_wikipedia_result(results[5], claim_text)
            processed_results[5] = filtered_wiki_result
        
        # Construct comprehensive dossier
        dossier = {
            "news_coverage": processed_results[0] if not isinstance(processed_results[0], Exception) else {"error": str(processed_results[0])},
            "fact_check_databases": processed_results[1] if not isinstance(processed_results[1], Exception) else {"error": str(processed_results[1])},
            "medical_literature_pubmed": processed_results[2] if not isinstance(processed_results[2], Exception) else {"error": str(processed_results[2])},
            "scientific_literature_arxiv": processed_results[3] if not isinstance(processed_results[3], Exception) else {"error": str(processed_results[3])},
            "community_discussions_reddit": processed_results[4] if not isinstance(processed_results[4], Exception) else {"error": str(processed_results[4])},
            "wikipedia_summary": processed_results[5] if not isinstance(processed_results[5], Exception) else {"error": str(processed_results[5])}
        }
        
        # Log summary
        successful_apis = sum(1 for v in dossier.values() if isinstance(v, dict) and "error" not in v)
        logger.info(f"[{self.agent_name}] Research complete: {successful_apis}/6 APIs successful")
        
        return dossier
    
    async def process_task(self, task: AgentTask) -> Dict[str, Any]:
        """
        Process a research task.
        
        Args:
            task: AgentTask containing claim_text in payload
            
        Returns:
            Dictionary with research results
        """
        logger.info(f"[{self.agent_name}] Processing research task {task.task_id}")
        
        claim_text = task.payload.get("claim_text", "")
        
        if not claim_text:
            raise ValueError("claim_text is required in task payload")
        
        # Perform comprehensive research
        research_dossier = await self.comprehensive_research(claim_text)
        
        return {
            "claim_text": claim_text,
            "research_dossier": research_dossier,
            "research_timestamp": task.created_at.isoformat()
        }


# Example usage and testing
if __name__ == "__main__":
    import json
    from datetime import datetime
    
    async def test_enhanced_research():
        """Test the Enhanced Research Agent"""
        
        # Create agent
        agent = EnhancedResearchAgent()
        
        # Test claim
        test_claim = "COVID-19 vaccines are effective at preventing severe illness"
        
        print(f"\n{'='*60}")
        print(f"Testing Enhanced Research Agent")
        print(f"{'='*60}\n")
        print(f"Claim: {test_claim}\n")
        
        # Create task
        task = AgentTask(
            task_id="test_research_001",
            agent_type="EnhancedResearchAgent",
            priority=TaskPriority.NORMAL,
            payload={"claim_text": test_claim},
            created_at=datetime.now()
        )
        
        # Process task
        result = await agent.process_task(task)
        
        # Display results
        print("\n" + "="*60)
        print("RESEARCH RESULTS")
        print("="*60 + "\n")
        
        dossier = result['research_dossier']
        
        for api_name, api_result in dossier.items():
            print(f"\n{api_name.upper().replace('_', ' ')}:")
            print("-" * 40)
            if "error" in api_result:
                print(f"❌ Error: {api_result['error']}")
            else:
                print(f"✅ Success")
                print(json.dumps(api_result, indent=2)[:300] + "...")
        
        print("\n" + "="*60)
        print("Test Complete")
        print("="*60)
    
    # Run test
    asyncio.run(test_enhanced_research())