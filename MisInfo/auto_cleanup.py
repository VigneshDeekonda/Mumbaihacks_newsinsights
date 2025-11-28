"""
Automatic Database Cleanup Script
Removes all duplicate test claims without prompting

This script deletes claims in the correct order to avoid foreign key constraint violations:
1. First delete from verified_claims (child records)
2. Then delete from raw_claims (parent records)
"""

import os
from dotenv import load_dotenv
from supabase import create_client

# Load environment variables
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env file")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

print("="*60)
print("PROJECT AEGIS - AUTOMATIC DATABASE CLEANUP")
print("="*60)

# Get all claims
response = supabase.table("raw_claims").select("*").execute()
all_claims = getattr(response, 'data', []) if response else []

print(f"\nTotal claims in database: {len(all_claims)}")

# Find duplicate test claims
test_claims = [
    "Breaking: Major earthquake hits city center!",
    "Scientists confirm that drinking water cures all forms of cancer",
    "New government policy will eliminate all taxes starting next month"
]

duplicate_ids = []
for claim in all_claims:
    if isinstance(claim, dict):
        claim_text = claim.get("claim_text", "")
        if isinstance(claim_text, str) and any(test_claim in claim_text for test_claim in test_claims):
            duplicate_ids.append(claim.get("claim_id", 0))

print(f"Found {len(duplicate_ids)} duplicate test claims")

if duplicate_ids:
    print("\nDeleting duplicate claims...")
    
    # Delete from verified_claims first (child records)
    try:
        response = supabase.table("verified_claims").select("*").execute()
        verified_claims = getattr(response, 'data', []) if response else []
        
        verified_deleted = 0
        for verified in verified_claims:
            if isinstance(verified, dict) and verified.get("raw_claim_id") in duplicate_ids:
                supabase.table("verified_claims").delete().eq("verification_id", verified.get("verification_id")).execute()
                verified_deleted += 1
        
        print(f"✓ Deleted {verified_deleted} verified claims")
    except Exception as e:
        print(f"Error cleaning verified_claims: {e}")
    
    # Then delete from raw_claims (parent records)
    deleted_count = 0
    for claim_id in duplicate_ids:
        try:
            supabase.table("raw_claims").delete().eq("claim_id", claim_id).execute()
            deleted_count += 1
            if deleted_count % 10 == 0:
                print(f"  Deleted {deleted_count}/{len(duplicate_ids)} claims...")
        except Exception as e:
            print(f"  ✗ Error deleting claim {claim_id}: {e}")
    
    print(f"✓ Deleted {deleted_count} raw claims")
    
    print(f"\n✅ Cleanup complete! Database is now clean.")
else:
    print("\n✅ No duplicate test claims found!")

print("\n" + "="*60)
print("You can now submit real claims through the frontend!")
print("="*60)
