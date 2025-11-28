"""
Project Aegis - Source Profiler Agent
This module contains the logic core for the Source Profiler Agent,
which evaluates the credibility of a source based on metadata heuristics.
"""

import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def calculate_source_score(metadata):
    """
    Calculate a credibility score for a source based on metadata heuristics.
    
    This function analyzes various metadata attributes (account age, follower counts,
    verification status, etc.) to produce a trust score between 0.0 (low trust) and
    1.0 (high trust). The scoring uses weighted heuristics to identify potentially
    suspicious accounts versus credible sources.
    
    Args:
        metadata (dict): A dictionary containing source metadata with the following keys:
            - account_age_days (int): Age of the account in days
            - followers (int): Number of followers
            - following (int): Number of accounts being followed
            - is_verified (bool): Whether the account is verified
    
    Returns:
        float: A credibility score clamped between 0.0 and 1.0, where:
            - 0.0 indicates very low trust/credibility
            - 1.0 indicates very high trust/credibility
    
    Examples:
        >>> # Highly credible source
        >>> credible_metadata = {
        ...     'account_age_days': 1825,
        ...     'followers': 2500000,
        ...     'following': 150,
        ...     'is_verified': True
        ... }
        >>> score = calculate_source_score(credible_metadata)
        >>> print(f"Credible source score: {score}")
        
        >>> # Suspicious source
        >>> suspicious_metadata = {
        ...     'account_age_days': 15,
        ...     'followers': 50,
        ...     'following': 800,
        ...     'is_verified': False
        ... }
        >>> score = calculate_source_score(suspicious_metadata)
        >>> print(f"Suspicious source score: {score}")
    """
    logger.info("[Source Profiler Agent] Calculating source credibility score")
    logger.debug(f"[Source Profiler Agent] Metadata: {metadata}")
    
    # Start with a neutral base score
    score = 0.5
    logger.debug(f"[Source Profiler Agent] Base score: {score}")
    
    # Safely extract metadata with default values
    account_age_days = metadata.get('account_age_days', 0)
    followers = metadata.get('followers', 0)
    following = metadata.get('following', 0)
    is_verified = metadata.get('is_verified', False)
    
    logger.debug(f"[Source Profiler Agent] Extracted metadata - Age: {account_age_days}, Followers: {followers}, Following: {following}, Verified: {is_verified}")
    
    # === VERIFIED STATUS ===
    # Verified accounts receive a significant trust bonus
    if is_verified:
        score += 0.4
        logger.debug(f"[Source Profiler Agent] Verified account bonus: +0.4, Score: {score}")
    
    # === ACCOUNT AGE ===
    # Very new accounts are suspicious
    if account_age_days < 30:
        score -= 0.25
        logger.debug(f"[Source Profiler Agent] New account penalty: -0.25, Score: {score}")
    # Established accounts receive a trust bonus
    elif account_age_days > 365:
        score += 0.1
        logger.debug(f"[Source Profiler Agent] Established account bonus: +0.1, Score: {score}")
    
    # === FOLLOWER RATIO ===
    # Analyze the relationship between followers and following
    if following > 0:  # Avoid division by zero
        # Healthy ratio: many more followers than following
        if followers > following * 5:
            score += 0.1
            logger.debug(f"[Source Profiler Agent] Healthy follower ratio bonus: +0.1, Score: {score}")
        
        # Suspicious ratio: following many more than followers (potential bot behavior)
        if following > followers * 10 and followers < 1000:
            score -= 0.2
            logger.debug(f"[Source Profiler Agent] Suspicious ratio penalty: -0.2, Score: {score}")
    
    # === FOLLOWER COUNT ===
    # Major public figures with large followings
    if followers > 1_000_000:
        score += 0.1
        logger.debug(f"[Source Profiler Agent] High follower count bonus: +0.1, Score: {score}")
    
    # === FINAL CLAMPING ===
    # Ensure score stays within valid bounds [0.0, 1.0]
    original_score = score
    score = max(0.0, min(1.0, score))
    if score != original_score:
        logger.debug(f"[Source Profiler Agent] Score clamped from {original_score} to {score}")
    
    logger.info(f"[Source Profiler Agent] Final credibility score: {score:.4f}")
    return score


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    print("="*70)
    print("PROJECT AEGIS - SOURCE PROFILER AGENT")
    print("Credibility Scoring Examples")
    print("="*70)
    
    # Example 1: Highly Credible Source
    print("\n[Example 1] Highly Credible Source")
    print("-" * 70)
    credible_metadata = {
        'account_age_days': 1825,      # 5 years old
        'followers': 2_500_000,         # 2.5M followers
        'following': 150,               # Following only 150
        'is_verified': True             # Verified account
    }
    print(f"Metadata: {credible_metadata}")
    credible_score = calculate_source_score(credible_metadata)
    print(f"Credibility Score: {credible_score:.2f}")
    print(f"Assessment: {'HIGHLY TRUSTED' if credible_score >= 0.8 else 'TRUSTED'}")
    
    # Example 2: Suspicious Source
    print("\n[Example 2] Suspicious Source")
    print("-" * 70)
    suspicious_metadata = {
        'account_age_days': 15,         # Only 15 days old
        'followers': 50,                # Very few followers
        'following': 800,               # Following many accounts
        'is_verified': False            # Not verified
    }
    print(f"Metadata: {suspicious_metadata}")
    suspicious_score = calculate_source_score(suspicious_metadata)
    print(f"Credibility Score: {suspicious_score:.2f}")
    print(f"Assessment: {'SUSPICIOUS' if suspicious_score < 0.3 else 'LOW TRUST'}")
    
    # Example 3: Moderate Source
    print("\n[Example 3] Moderate Source")
    print("-" * 70)
    moderate_metadata = {
        'account_age_days': 180,        # 6 months old
        'followers': 5000,              # Decent following
        'following': 800,               # Reasonable ratio
        'is_verified': False            # Not verified
    }
    print(f"Metadata: {moderate_metadata}")
    moderate_score = calculate_source_score(moderate_metadata)
    print(f"Credibility Score: {moderate_score:.2f}")
    print(f"Assessment: {'MODERATE TRUST' if 0.4 <= moderate_score < 0.7 else 'NEUTRAL'}")
    
    # Example 4: Missing Data (Edge Case)
    print("\n[Example 4] Missing Data (Edge Case)")
    print("-" * 70)
    incomplete_metadata = {
        'followers': 1000
        # Missing: account_age_days, following, is_verified
    }
    print(f"Metadata: {incomplete_metadata}")
    incomplete_score = calculate_source_score(incomplete_metadata)
    print(f"Credibility Score: {incomplete_score:.2f}")
    print(f"Assessment: Defaults applied for missing data")
    
    print("\n" + "="*70)
    print("Source Profiler Agent - Ready for Deployment")
    print("="*70)