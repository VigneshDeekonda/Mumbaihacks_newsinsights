import logging
from typing import Dict, Any
import json
from datetime import datetime
import whois
from urllib.parse import urlparse

from .base_agent import BaseAgent, AgentTask, AgentStatus, TaskPriority

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SourceProfilerAgent(BaseAgent):
    """Agent responsible for evaluating source credibility based on metadata"""
    
    def __init__(self, agent_id: str = "source_profiler_agent_001"):
        super().__init__(agent_id, "SourceProfilerAgent")
        
        # Expanded reputable sources list
        self.REPUTABLE_SOURCES = [
            "Reuters", "Associated Press", "BBC News", "NPR", "The Guardian", "Plos.org",
            "Al Jazeera", "CNN", "CBS News", "ABC News", "NBC News", "PBS NewsHour",
            "The New York Times", "The Washington Post", "The Wall Street Journal",
            "Bloomberg", "Financial Times", "Forbes", "AP News",
            "BBC World News", "France 24", "DW News", "NHK World", "TRT World",
            "Al Arabiya", "Sky News", "ITV News", "Channel 4 News", "CTV News",
            "CBC News", "ABC Australia", "Radio Canada", "Euronews", "CGTN",
            "Xinhua News", "Kyodo News", "TASS", "RIA Novosti", "Anadolu Agency",
            "Phys.org", "ScienceDaily", "Nature", "Scientific American", "Wired",
            "TechCrunch", "The Verge", "Ars Technica", "MIT Technology Review",
            "Harvard Business Review", "The Economist", "Foreign Affairs",
            # Additional reputable sources
            "Agence France-Presse", "Deutsche Welle", "Voice of America", "Radio Free Europe",
            "The Christian Science Monitor", "ProPublica", "Center for Public Integrity",
            "Investigative Reporters and Editors", "International Consortium of Investigative Journalists",
            "The Atlantic", "Time Magazine", "Newsweek", "U.S. News & World Report",
            "Los Angeles Times", "Chicago Tribune", "The Boston Globe", "Miami Herald",
            "The Seattle Times", "The Denver Post", "Houston Chronicle", "Dallas Morning News",
            "Philadelphia Inquirer", "Minneapolis Star-Tribune", "The Oregonian", "Arizona Republic",
            "The Plain Dealer", "The Kansas City Star", "St. Louis Post-Dispatch", "Tampa Bay Times",
            "The Mercury News", "Star-Ledger", "Milwaukee Journal Sentinel", "The Sacramento Bee",
            "McClatchy", "Gannett", "Hearst Communications", "Advance Publications",
            "Lee Enterprises", "The McClatchy Company", "Gray Television", "Tegna Inc.",
            "Sinclair Broadcast Group", "Nexstar Media Group", "The E.W. Scripps Company",
            "Fox Corporation", "Warner Bros. Discovery", "Comcast", "Disney",
            "Snopes", "PolitiFact", "FactCheck.org", "Washington Post Fact Checker",
            "BBC Reality Check", "Reuters Fact Check", "AP Fact Check", "Full Fact",
            "Africa Check", "Chequeado", "Faktisk.no", "Correctiv",
            "Pagella Politica", "Verificado", "Boom Live", "AltNews",
            "Lead Stories", "21st Century Wire", "Check Your Fact", "Climate Feedback",
            "SciCheck", "The Conversation", "Retraction Watch", "Our World in Data",
            # Additional major news organizations
            "USA Today", "The Hill", "Politico", "Axios", "Vox", "FiveThirtyEight",
            "Mother Jones", "The Intercept", "Slate", "Salon", "The New Republic",
            "National Review", "The Weekly Standard", "Reason Magazine", "The Nation",
            "Der Spiegel", "Le Monde", "El País", "La Repubblica", "Le Figaro",
            "The Globe and Mail", "The Sydney Morning Herald", "The Age", "Yomiuri Shimbun",
            "Asahi Shimbun", "The Straits Times", "South China Morning Post", "Arab News",
            "Al-Hayat", "Asharq Al-Awsat", "Al-Monitor", "Middle East Eye",
            "Haaretz", "Ynet", "The Times of India", "The Hindu", "China Daily",
            "The Moscow Times", "Komsomolskaya Pravda", "Pravda", "Izvestia"
        ]
        
        # Expanded unreliable domains list
        self.UNRELIABLE_DOMAINS = [
            "infowars.com", "naturalnews.com", "dailywire.com", "breitbart.com", 
            "rt.com", "freerepublic.com", "theonion.com", "empirenews.net",
            "duffelblog.com", "clickhole.com", "borowitzreport.com", "newsmutiny.com",
            "dailykos.com", "redstate.com", "wnd.com", "newsmax.com", "oann.com",
            "zerohedge.com", "pravda.ru", "sputniknews.com", "beforeitsnews.com",
            "activistpost.com", "truthdig.com", "truthout.org", "alternet.org",
            "commondreams.org", "counterpunch.org", "davidicke.com", "prisonplanet.com",
            "globalresearch.ca", "whatreallyhappened.com", "presstv.ir", "moonofalabama.org",
            "consortiumnews.com", "mintpressnews.com", "blackagendareport.com", "truth11.com",
            "yournewswire.com", "collective-evolution.com", "wakingtimes.com", "preventdisease.com",
            "healthimpactnews.com", "naturalblaze.com", "theblaze.com", "dailycaller.com",
            "foxnews.com", "news.ycombinator.com", "drudgereport.com", "thegatewaypundit.com",
            "jonesreport.com", "lewrockwell.com", "antiwar.com", "ronpaulinstitute.org",
            # Additional unreliable domains
            "beforeitsnews.com", "dcclothesline.com", "disclose.tv", "endingthefed.com",
            "godlikeproductions.com", "govtslaves.info", "greanvillepost.com", "hangthebankers.com",
            "henrymakow.com", "humansarefree.com", "investmentwatchblog.com", "jewishvirtuallibrary.org",
            "lewrockwell.com", "libertyblitzkrieg.com", "libertymovementradio.com", "libertynews.com",
            "libertytalk.fm", "livefreelivenatural.com", "marcorubio.com", "naturalnews.com",
            "newscorpse.com", "newstarget.com", "nowtheendbegins.com", "occupydemocrats.com",
            "off-guardian.org", "oilgeopolitics.net", "patriotrising.com", "pjmedia.com",
            "prisonplanet.com", "prisonplanet.tv", "randpaul.com", "rawforbeauty.com",
            "redflagnews.com", "rense.com", "rumormillnews.com", "sott.net",
            "thedailysheeple.com", "theforbiddenknowledge.com", "thelibertybeacon.com", "themindunleashed.com",
            "thenewamerican.com", "therussophile.org", "thinkprogress.org", "tomfernandez28.com",
            "trueactivist.com", "truthfrequencyradio.com", "twitchy.com", "unz.com",
            "usuncut.com", "vdare.com", "veteranstoday.com", "washingtonsblog.com",
            "weeklyworldnews.com", "whatreallyhappened.com", "whydontyoutrythis.com", "wikileaks.org",
            "willyloman.wordpress.com", "worldtruth.tv", "zerohedge.com", "zootfeed.com",
            "naturalnewsblogs.com", "healthnutnews.com", "revolutions2040.com", "thetruthaboutcancer.com",
            "collectivelyconscious.net", "dineal.com", "foodbabe.com", "mercola.com",
            "organicconsumers.org", "responsibletechnology.org", "sustainablepulse.com", "truthaboutvaccines.com",
            "vaccinationinformationnetwork.com", "cherrylightning.com", "collective-evolution.com", "wakingtimes.com",
            "geoengineeringwatch.org", "in5d.com", "spiritualdaily.com", "ascensionwithearth.com",
            "shiftfrequency.com", "soulfulvision.com", "thedailymind.com", "thepharmaceuticalindustry.com",
            "ancient-code.com", "davidwolfe.com", "thetruthwins.com", "undergroundhealth.com",
            "govtslaves.com", "nibiruandthecomingdeception.com", "thecosmicunion.com", "theeventchronicle.com",
            "thetrumpet.com", "worldpeacehq.com", "realfarmacy.com", "therundownlive.com",
            "truthstreammedia.com", "vigilantcitizen.com", "wakingupwisconsin.com", "2012portal.blogspot.com",
            # Additional known problematic domains
            "gatewaypundit.com", "worldnetdaily.com", "palmerreport.com", "occupydemocrats.com",
            "addictinginfo.com", "rightwingnews.com", "conservativetribune.com", "usapoliticstoday.com",
            "libertywritersnews.com", "allenbwest.com", "thedailybeast.com", "huffingtonpost.com",
            "slate.com", "dailykos.com", "motherjones.com", "thinkprogress.org",
            "crooksandliars.com", "mediamatters.org", "sourcewatch.org", "opensecrets.org",
            "sunlightfoundation.com", "factcheck.org", "politifact.com", "snopes.com",
            "urban.org", "brookings.edu", "cato.org", "heritage.org",
            "americanthinker.com", "townhall.com", "freebeacon.com", "washingtontimes.com",
            "nationalreview.com", "weeklystandard.com", "reason.com", "realclearpolitics.com"
        ]
        
        # Note: These lists are examples and require ongoing curation to maintain accuracy and relevance
        
    def calculate_source_score(self, metadata: Dict[str, Any]) -> float:
        """
        Calculate a credibility score for a source based on domain reputation with weighted scoring.
        
        Args:
            metadata (Dict[str, Any]): A dictionary containing source metadata
            
        Returns:
            float: A credibility score based on source reputation
        """
        logger.info(f"[{self.agent_name}] Calculating source credibility score with weighted approach")
        logger.debug(f"[{self.agent_name}] Metadata: {metadata}")
        
        # Extract source name and URL from metadata
        source_name = metadata.get('source_name', '')
        source_url = metadata.get('source_url', '')
        
        logger.debug(f"[{self.agent_name}] Source name: {source_name}, Source URL: {source_url}")
        
        # Start with a base neutral score
        base_score = 0.5
        score = base_score
        
        # Check if the source_name is in REPUTABLE_SOURCES
        if source_name in self.REPUTABLE_SOURCES:
            score += 0.3  # Reduced from 0.4 to prevent extremely high scores
            logger.info(f"[{self.agent_name}] Reputable source found: {source_name}, adding 0.3 to score")
            
        # Check if any part of UNRELIABLE_DOMAINS is in the source_url
        for unreliable_domain in self.UNRELIABLE_DOMAINS:
            if unreliable_domain in source_url:
                score -= 0.3  # Reduced from 0.4 to prevent extremely low scores
                logger.info(f"[{self.agent_name}] Unreliable domain found: {unreliable_domain} in {source_url}, subtracting 0.3 from score")
                break  # Only apply penalty once
                
        # Optional: Domain age check
        try:
            if source_url:
                # Extract domain from URL
                parsed_url = urlparse(source_url)
                domain = parsed_url.netloc or parsed_url.path
                
                if domain:
                    # Get domain information with timeout
                    domain_info = whois.whois(domain, timeout=5)
                    
                    # Check if creation_date exists
                    if 'creation_date' in domain_info and domain_info['creation_date']:
                        creation_date = domain_info['creation_date']
                        
                        # Handle case where creation_date might be a list
                        if isinstance(creation_date, list):
                            creation_date = creation_date[0]
                            
                        # Calculate age in days
                        if creation_date:
                            age_days = (datetime.now() - creation_date).days
                            
                            # If domain is less than 6 months old, subtract 0.2 from score
                            if age_days < 180:
                                score -= 0.2
                                logger.info(f"[{self.agent_name}] Domain {domain} is less than 6 months old ({age_days} days), subtracting 0.2 from score")
                            # If domain is less than a year old, subtract 0.1 from score
                            elif age_days < 365:
                                score -= 0.1
                                logger.info(f"[{self.agent_name}] Domain {domain} is less than a year old ({age_days} days), subtracting 0.1 from score")
        except Exception as e:
            logger.warning(f"[{self.agent_name}] Error checking domain age: {e}")
            # Continue with score calculation even if domain age check fails
                
        # Clamp score between 0.0 and 1.0
        final_score = max(0.0, min(1.0, score))
        
        logger.info(f"[{self.agent_name}] Final calculated source credibility score: {final_score:.2f} (base: {base_score}, modifiers: {final_score - base_score:+.2f})")
        return final_score
    
    async def process_task(self, task: AgentTask) -> Dict[str, Any]:
        """
        Process a task to evaluate source credibility.
        
        Args:
            task (AgentTask): The task containing source metadata to evaluate
            
        Returns:
            Dict[str, Any]: The credibility score and evaluation details
        """
        logger.info(f"[{self.agent_name}] Processing source profiling task {task.task_id}")
        
        # Extract source metadata from payload
        source_metadata_json = task.payload.get("source_metadata_json", "{}")
        
        try:
            source_metadata = json.loads(source_metadata_json)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in source_metadata_json: {e}")
        
        # Calculate credibility score
        credibility_score = self.calculate_source_score(source_metadata)
        
        return {
            "source_metadata": source_metadata,
            "source_credibility_score": credibility_score,
            "evaluation_timestamp": task.created_at.isoformat()
        }