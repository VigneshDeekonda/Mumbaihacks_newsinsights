import logging
from typing import Dict, Any
import joblib
import os
import numpy as np
import re
from scipy.sparse import csr_matrix, hstack

from .base_agent import BaseAgent, AgentTask, AgentStatus, TaskPriority

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def text_length(text):
    """Returns character length of text."""
    try:
        return len(str(text))
    except:
        return 0


def sentence_count(text):
    """Returns number of sentences using nltk.sent_tokenize."""
    try:
        # Import nltk inside function to avoid import issues
        import importlib
        nltk = importlib.import_module('nltk')
        
        # Download required NLTK data (if not already present)
        try:
            nltk.data.find('punkt')
        except LookupError:
            try:
                nltk.download('punkt', quiet=True)
            except:
                pass
        return len(nltk.sent_tokenize(str(text)))
    except:
        return 0


def avg_word_length(text):
    """Returns average word length using nltk.word_tokenize."""
    try:
        # Import nltk inside function to avoid import issues
        import importlib
        nltk = importlib.import_module('nltk')
        
        # Download required NLTK data (if not already present)
        try:
            nltk.data.find('punkt')
        except LookupError:
            try:
                nltk.download('punkt', quiet=True)
            except:
                pass
        words = nltk.word_tokenize(str(text))
        if len(words) == 0:
            return 0
        return np.mean([len(word) for word in words])
    except:
        return 0


def uppercase_ratio(text):
    """Returns the ratio of uppercase characters to total characters."""
    try:
        text_str = str(text)
        if len(text_str) == 0:
            return 0
        uppercase_count = sum(1 for c in text_str if c.isupper())
        return uppercase_count / len(text_str)
    except:
        return 0


def exclamation_count(text):
    """Returns the count of exclamation marks."""
    try:
        return str(text).count('!')
    except:
        return 0


def suspicious_keyword_count(text):
    """Count occurrences of suspicious keywords in the text."""
    try:
        suspicious_keywords = [
            "conspiracy", "hoax", "secret cure", "fake", "exposed", "they don't want you to know",
            "miracle cure", "doctors hate", "cover up", "hidden", "suppressed", "banned",
            "censored", "shocking", "urgent", "alert", "warning", "must read", "breaking",
            "insider", "leak", "proof", "evidence", "undeniable", "truth", "revealed"
        ]
        
        # Compile regex patterns for efficiency
        patterns = [re.compile(re.escape(keyword), re.IGNORECASE) for keyword in suspicious_keywords]
        
        text_str = str(text)
        count = 0
        for pattern in patterns:
            count += len(pattern.findall(text_str))
        return count
    except:
        return 0


def sentiment_score(text):
    """Use VADER to get the compound sentiment score."""
    try:
        # Import nltk inside function to avoid import issues
        import importlib
        nltk = importlib.import_module('nltk')
        
        # Download required NLTK data (if not already present)
        try:
            nltk.data.find('vader_lexicon')
        except LookupError:
            try:
                nltk.download('vader_lexicon', quiet=True)
            except:
                pass
            
        SentimentIntensityAnalyzer = getattr(importlib.import_module('nltk.sentiment'), 'SentimentIntensityAnalyzer')
        analyzer = SentimentIntensityAnalyzer()
        scores = analyzer.polarity_scores(str(text))
        return scores['compound']
    except:
        return 0


def get_text_features(text_series):
    """
    Apply all feature engineering functions to a list of text.
    
    Args:
        text_series: List of text data
        
    Returns:
        numpy array containing engineered features
    """
    features = np.array([
        [text_length(text), sentence_count(text), avg_word_length(text), 
         uppercase_ratio(text), exclamation_count(text), 
         suspicious_keyword_count(text), sentiment_score(text)]
        for text in text_series
    ])
    
    # Handle potential NaN/inf values
    features = np.nan_to_num(features, nan=0.0, posinf=0.0, neginf=0.0)
    
    return features


class AnalystAgent(BaseAgent):
    """Agent responsible for analyzing claim text using ML models"""
    
    def __init__(self, agent_id: str = "analyst_agent_001", model_path: str = "backend"):
        super().__init__(agent_id, "AnalystAgent")
        
        # Use backend as the default model directory since that's where the models are located
        self.model_path = model_path
            
        self.vectorizer = None
        self.scaler = None
        self.classifier = None
        self.load_models()
        
    def load_models(self):
        """Load the ML models from disk"""
        try:
            # Try to load the enhanced models first (v2)
            vectorizer_path_v2 = os.path.join(self.model_path, "vectorizer_v2.pkl")
            scaler_path_v2 = os.path.join(self.model_path, "scaler_v2.pkl")
            classifier_path_v2 = os.path.join(self.model_path, "classifier_v2.pkl")
            
            # Check if v2 models exist
            if os.path.exists(vectorizer_path_v2) and os.path.exists(scaler_path_v2) and os.path.exists(classifier_path_v2):
                self.vectorizer = joblib.load(vectorizer_path_v2)
                self.scaler = joblib.load(scaler_path_v2)
                self.classifier = joblib.load(classifier_path_v2)
                logger.info(f"[{self.agent_name}] Enhanced ML models (v2) loaded successfully")
            else:
                # Fall back to original models
                vectorizer_path = os.path.join(self.model_path, "vectorizer.pkl")
                classifier_path = os.path.join(self.model_path, "classifier.pkl")
                
                # Log the absolute paths and current working directory for debugging
                logger.info(f"[{self.agent_name}] Current working directory: {os.getcwd()}")
                logger.info(f"[{self.agent_name}] Attempting to load vectorizer from: {os.path.abspath(vectorizer_path)}")
                logger.info(f"[{self.agent_name}] Attempting to load classifier from: {os.path.abspath(classifier_path)}")
                
                # Check if files exist before trying to load them
                if not os.path.exists(vectorizer_path):
                    logger.warning(f"[{self.agent_name}] Vectorizer file not found at: {os.path.abspath(vectorizer_path)}")
                if not os.path.exists(classifier_path):
                    logger.warning(f"[{self.agent_name}] Classifier file not found at: {os.path.abspath(classifier_path)}")
                
                self.vectorizer = joblib.load(vectorizer_path)
                self.classifier = joblib.load(classifier_path)
                logger.info(f"[{self.agent_name}] Original ML models loaded successfully")
                
        except FileNotFoundError as e:
            logger.warning(f"[{self.agent_name}] Warning: vectorizer.pkl or classifier.pkl not found - {e}")
        except Exception as e:
            logger.error(f"[{self.agent_name}] Error loading ML models: {e}")
    
    async def process_task(self, task: AgentTask) -> Dict[str, Any]:
        """
        Process a task to analyze claim text.
        
        Args:
            task (AgentTask): The task containing the claim text to analyze
            
        Returns:
            Dict[str, Any]: The analysis results including suspicion score
        """
        logger.info(f"[{self.agent_name}] Processing analysis task {task.task_id}")
        
        # Extract claim text from payload
        claim_text = task.payload.get("claim_text", "")
        
        if not claim_text:
            raise ValueError("No claim text provided in task payload")
        
        logger.info(f"[{self.agent_name}] Analyzing claim: {claim_text[:50]}...")
        
        # Fail honestly if models not available instead of returning neutral score
        if self.vectorizer is None or self.classifier is None:
            logger.error(f"[{self.agent_name}] Critical error: ML models not loaded, cannot perform analysis")
            return {
                "claim_text": claim_text,
                "text_suspicion_score": None,
                "status": "analysis_failed",
                "error": "ML models not loaded",
                "analysis_timestamp": task.created_at.isoformat()
            }
        
        try:
            # Check if we're using the enhanced model (has scaler)
            if self.scaler is not None:
                # Enhanced model with feature engineering
                logger.debug(f"[{self.agent_name}] Using enhanced model with feature engineering")
                
                # Vectorize the claim text
                claim_vector_tfidf = self.vectorizer.transform([claim_text])
                
                # Extract engineered features
                engineered_features = get_text_features([claim_text])
                engineered_features_scaled = self.scaler.transform(engineered_features)
                engineered_features_sparse = csr_matrix(engineered_features_scaled)
                
                # Combine features
                claim_vector_combined = hstack([claim_vector_tfidf, engineered_features_sparse])
                
                # Predict probability for class 1 (misinformation/fake)
                suspicion_probability = self.classifier.predict_proba(claim_vector_combined)[0][1]
                logger.info(f"[{self.agent_name}] Text suspicion score (enhanced model): {suspicion_probability:.4f}")
            else:
                # Original model
                logger.debug(f"[{self.agent_name}] Using original model")
                
                # Vectorize the claim text
                claim_vector = self.vectorizer.transform([claim_text])
                logger.debug(f"[{self.agent_name}] Claim vectorized successfully")
                
                # Predict probability for class 1 (misinformation/fake)
                suspicion_probability = self.classifier.predict_proba(claim_vector)[0][1]
                logger.info(f"[{self.agent_name}] Text suspicion score: {suspicion_probability:.4f}")
            
            return {
                "claim_text": claim_text,
                "text_suspicion_score": float(suspicion_probability),
                "analysis_timestamp": task.created_at.isoformat()
            }
            
        except Exception as e:
            logger.error(f"[{self.agent_name}] Error during analysis: {e}")
            # Fail honestly on error instead of returning neutral score
            return {
                "claim_text": claim_text,
                "text_suspicion_score": None,
                "status": "analysis_failed",
                "error": str(e),
                "analysis_timestamp": task.created_at.isoformat()
            }


# Example usage
if __name__ == "__main__":
    import asyncio
    from datetime import datetime
    
    async def main():
        # Create the analyst agent
        analyst_agent = AnalystAgent()
        
        # Create a sample task
        task = AgentTask(
            task_id="analysis_task_001",
            agent_type="AnalystAgent",
            priority=TaskPriority.NORMAL,
            payload={
                "claim_text": "This is a test claim to analyze for misinformation"
            },
            created_at=datetime.now()
        )
        
        # Process the task
        result = await analyst_agent.process_task(task)
        print("Analyst Agent Result:")
        print(result)
    
    # Run the example
    asyncio.run(main())