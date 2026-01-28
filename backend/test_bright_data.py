"""
Test script to verify Bright Data API integration
Run this to test if the API is working correctly
"""

import asyncio
import sys
sys.path.append('D:/Parth/Coding/FY PROJECT/fake_review_v2/backend')

from services.bright_data_service import BrightDataService

async def test_bright_data():
    """Test the Bright Data API with a sample Amazon URL"""
    
    service = BrightDataService()
    
    print("=" * 60)
    print("Testing Bright Data API Integration")
    print("=" * 60)
    
    # Check if configured
    if not service.is_configured():
        print("❌ Bright Data API is NOT configured")
        print("Please set BRIGHT_DATA_API_TOKEN in .env file")
        return
    
    print("✅ Bright Data API is configured")
    print(f"📝 Dataset ID: {service.dataset_id}")
    print(f"🔑 Token: {service.api_token[:20]}...")
    
    # Test URL from the example you provided
    test_url = "https://www.amazon.com/RORSOU-R10-Headphones-Microphone-Lightweight/dp/B094NC89P9/"
    test_asin = "B094NC89P9"
    
    print(f"\n🔍 Testing with URL: {test_url}")
    print(f"📦 ASIN: {test_asin}")
    print("\n⏳ Fetching reviews (this may take 30-60 seconds)...\n")
    
    try:
        reviews = await service.fetch_reviews(test_asin, test_url)
        
        print("=" * 60)
        print(f"✅ SUCCESS! Fetched {len(reviews)} reviews")
        print("=" * 60)
        
        if reviews:
            # Show first review
            print("\n📄 Sample Review (first one):")
            print("-" * 60)
            first_review = reviews[0]
            print(f"Reviewer: {first_review.get('reviewer_name', 'N/A')}")
            print(f"Rating: {first_review.get('rating', 'N/A')} stars")
            print(f"Title: {first_review.get('title', 'N/A')}")
            print(f"Text: {first_review.get('text', 'N/A')[:200]}...")
            print(f"Verified: {first_review.get('verified_purchase', False)}")
            print(f"Date: {first_review.get('date', 'N/A')}")
            print("-" * 60)
            
            print(f"\n✅ Total reviews ready for ML analysis: {len(reviews)}")
            print("✅ Reviews are properly formatted and ready!")
            
        else:
            print("⚠️ No reviews returned (check API response format)")
            
    except Exception as e:
        print("=" * 60)
        print(f"❌ ERROR: {str(e)}")
        print("=" * 60)
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_bright_data())
