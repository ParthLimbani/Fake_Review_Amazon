"""
Integration Test Script
=======================
Tests the complete flow from URL to results.
"""

import asyncio
import logging
import json
from services.bright_data_service import BrightDataService
from services.analysis_service import AnalysisService
from utils.asin_extractor import extract_asin

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_amazon_url_analysis():
    """Test complete analysis flow with an Amazon URL."""
    
    # Test URLs
    test_urls = [
        "https://www.amazon.in/dp/B0CX59KV2R",
        "https://www.amazon.in/Apple-iPhone-15-128-GB/dp/B0CHX1W1XY",
        "https://www.amazon.in/dp/B094NC89P9"
    ]
    
    bright_data = BrightDataService()
    analysis = AnalysisService()
    
    logger.info("=" * 80)
    logger.info("INTEGRATION TEST: Amazon URL to Analysis Results")
    logger.info("=" * 80)
    
    for url in test_urls:
        logger.info(f"\n{'=' * 80}")
        logger.info(f"Testing URL: {url}")
        logger.info(f"{'=' * 80}\n")
        
        # Step 1: Extract ASIN
        asin = extract_asin(url)
        logger.info(f"✅ Step 1: Extracted ASIN: {asin}")
        
        if not asin:
            logger.error("❌ ASIN extraction failed!")
            continue
        
        # Step 2: Fetch reviews
        try:
            reviews, is_demo = await bright_data.fetch_reviews(asin, url)
            logger.info(f"✅ Step 2: Fetched {len(reviews)} reviews (Demo: {is_demo})")
            
            if reviews:
                logger.info(f"   First review preview:")
                first_review = reviews[0]
                for key, value in list(first_review.items())[:5]:
                    logger.info(f"   - {key}: {str(value)[:100]}")
        except Exception as e:
            logger.error(f"❌ Step 2 failed: {e}")
            continue
        
        # Step 3: Run analysis
        try:
            result = await analysis.analyze_reviews(
                asin=asin,
                url=url,
                reviews=reviews,
                is_demo_data=is_demo
            )
            logger.info(f"✅ Step 3: Analysis complete")
            logger.info(f"   Metrics:")
            logger.info(f"   - Total reviews: {result['metrics']['total_reviews']}")
            logger.info(f"   - Fake percentage: {result['metrics']['fake_percentage']}%")
            logger.info(f"   - Authenticity grade: {result['metrics']['authenticity_grade']}")
            logger.info(f"   - Is demo data: {result.get('is_demo_data', False)}")
            
            # Verify required fields
            required_fields = [
                'success', 'asin', 'product_title', 'product_url', 
                'metrics', 'patterns', 'summary', 'reviews', 'is_demo_data'
            ]
            
            missing = [f for f in required_fields if f not in result]
            if missing:
                logger.error(f"❌ Missing required fields: {missing}")
            else:
                logger.info(f"✅ All required fields present")
                
        except Exception as e:
            logger.error(f"❌ Step 3 failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            continue
        
        logger.info(f"\n{'=' * 80}")
        logger.info(f"✅ TEST PASSED for {url}")
        logger.info(f"{'=' * 80}\n")


async def test_api_connection():
    """Test direct Bright Data API connection."""
    
    logger.info("\n" + "=" * 80)
    logger.info("TESTING BRIGHT DATA API CONNECTION")
    logger.info("=" * 80 + "\n")
    
    import httpx
    import json
    from config import settings
    
    url = "https://api.brightdata.com/datasets/v3/scrape"
    
    headers = {
        "Authorization": f"Bearer {settings.BRIGHT_DATA_API_TOKEN}",
        "Content-Type": "application/json"
    }
    
    payload = [
        {
            "url": "https://www.amazon.in/dp/B0CX59KV2R"
        }
    ]
    
    params = {
        "dataset_id": settings.BRIGHT_DATA_DATASET_ID,
        "notify": "false",
        "include_errors": "true",
        "format": "json"
    }
    
    logger.info(f"📡 API Endpoint: {url}")
    logger.info(f"🔑 Token (first 10 chars): {settings.BRIGHT_DATA_API_TOKEN[:10]}...")
    logger.info(f"📦 Dataset ID: {settings.BRIGHT_DATA_DATASET_ID}")
    logger.info(f"📄 Payload: {json.dumps(payload, indent=2)}")
    
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
            response = await client.post(
                url,
                headers=headers,
                content=json.dumps(payload),
                params=params
            )
            
            logger.info(f"\n📨 Response Status: {response.status_code}")
            logger.info(f"📨 Response Headers: {dict(response.headers)}")
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"✅ API Call Successful!")
                logger.info(f"📊 Response Type: {type(data)}")
                if isinstance(data, list):
                    logger.info(f"📊 Items Count: {len(data)}")
                    if len(data) > 0:
                        logger.info(f"📊 First Item Keys: {list(data[0].keys())}")
                elif isinstance(data, dict):
                    logger.info(f"📊 Response Keys: {list(data.keys())}")
            else:
                logger.error(f"❌ API Call Failed")
                logger.error(f"Error: {response.text}")
                
    except Exception as e:
        logger.error(f"❌ Exception: {e}")
        import traceback
        logger.error(traceback.format_exc())


if __name__ == "__main__":
    print("\n🧪 Starting Integration Tests...\n")
    
    # Run tests
    asyncio.run(test_api_connection())
    asyncio.run(test_amazon_url_analysis())
    
    print("\n✅ All tests completed!\n")
