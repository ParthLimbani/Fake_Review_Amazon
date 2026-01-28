"""
Bright Data Service
===================
Handles all communication with Bright Data's Amazon Reviews API.

Why Bright Data?
- Provides structured review data without direct scraping
- Handles rate limiting and anti-bot measures
- Returns clean JSON data ready for processing
- Ethical: Uses official data collection methods

API Documentation: https://docs.brightdata.com/
"""

import logging
import httpx
import asyncio
from typing import List, Dict, Optional, Any
from datetime import datetime

from config import settings

logger = logging.getLogger(__name__)


class BrightDataService:
    """
    Service class for fetching Amazon reviews via Bright Data API.
    
    Uses the scrape endpoint which returns results synchronously
    after the scraping is complete.
    """
    
    def __init__(self):
        """Initialize the Bright Data service with API credentials."""
        self.api_token = settings.BRIGHT_DATA_API_TOKEN
        # Updated dataset ID for Amazon reviews scraping
        self.dataset_id = "gd_le8e811kzy4ggddlq"
        self.base_url = "https://api.brightdata.com/datasets/v3"
        
        # HTTP client configuration - longer timeout for scraping
        self.timeout = httpx.Timeout(180.0)  # 3 minute timeout for scraping
        
    def is_configured(self) -> bool:
        """Check if API credentials are configured."""
        return bool(self.api_token) and self.api_token != "your_api_token_here"
    
    async def fetch_reviews(self, asin: str, product_url: str) -> tuple[List[Dict[str, Any]], bool]:
        """
        Fetch reviews for a product from Bright Data API.
        
        Args:
            asin: Amazon Standard Identification Number
            product_url: Full Amazon product URL
            
        Returns:
            Tuple of (reviews list, is_demo_data boolean)
            
        Flow:
        1. Call scrape endpoint with product URL
        2. Wait for results (synchronous)
        3. Parse and return standardized review data
        """
        logger.info(f"🔄 Starting Bright Data fetch for ASIN: {asin}")
        logger.info(f"📍 Product URL: {product_url}")
        
        if not self.is_configured():
            logger.warning("⚠️ Bright Data not configured, using sample data")
            return self._get_sample_reviews_for_product(asin, product_url), True
        
        try:
            # Call the scrape endpoint
            reviews = await self._scrape_reviews(product_url)
            
            if reviews and len(reviews) > 0:
                # Standardize the review format
                standardized = self._standardize_reviews(reviews)
                logger.info(f"✅ Fetched and standardized {len(standardized)} reviews")
                return standardized, False
            else:
                logger.warning("⚠️ No reviews returned from API, using sample data")
                return self._get_sample_reviews_for_product(asin, product_url), True
                
        except Exception as e:
            logger.error(f"❌ Bright Data API error: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            # Fallback to sample data for development
            logger.info("📦 Using sample reviews for development")
            return self._get_sample_reviews_for_product(asin, product_url), True
    
    async def _scrape_reviews(self, product_url: str) -> Optional[List[Dict]]:
        """
        Scrape reviews using Bright Data's scrape endpoint.
        
        This endpoint triggers a scrape job and waits for results.
        The API returns the scraped data directly when complete.
        """
        endpoint = f"{self.base_url}/scrape"
        
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }
        
        # Request body format matching Bright Data documentation
        # Using 'input' wrapper as per API docs
        payload = [
            {
                "url": product_url
            }
        ]
        
        params = {
            "dataset_id": self.dataset_id,
            "notify": "false",  # Don't use webhooks, wait for response
            "include_errors": "true",
            "format": "json"
        }
        
        logger.info(f"📡 Calling Bright Data Scrape API...")
        logger.info(f"🔗 Endpoint: {endpoint}")
        logger.info(f"📦 Payload: {payload}")
        logger.info(f"🔑 Token (first 8 chars): {self.api_token[:8]}...")
        
        import json
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                endpoint,
                headers=headers,
                content=json.dumps(payload),
                params=params
            )
            
            logger.info(f"📨 Response status: {response.status_code}")
            logger.info(f"📨 Response text: {response.text[:500]}")
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"✅ API response received: {type(data)}")
                
                # Response is typically a list of review objects
                if isinstance(data, list):
                    logger.info(f"📊 Received {len(data)} items from API")
                    return data
                
                # Sometimes it might be wrapped in an object
                if isinstance(data, dict):
                    # Check for reviews array
                    if "reviews" in data:
                        return data["reviews"]
                    # Check for data array
                    if "data" in data:
                        return data["data"]
                    # Check for snapshot_id (async response)
                    if "snapshot_id" in data:
                        logger.info(f"📋 Got snapshot_id, polling for results...")
                        return await self._poll_for_results(data["snapshot_id"])
                    
                    # Return as single-item list if it looks like a product
                    if "url" in data or "asin" in data:
                        return [data]
                
                logger.warning(f"⚠️ Unexpected response format: {data}")
                return None
                
            elif response.status_code == 202:
                # Async processing - need to poll
                data = response.json()
                if "snapshot_id" in data:
                    logger.info(f"📋 Async response, polling for results...")
                    return await self._poll_for_results(data["snapshot_id"])
                return None
            else:
                logger.error(f"❌ API error: {response.status_code} - {response.text}")
                return None
    
    async def _poll_for_results(self, snapshot_id: str, max_attempts: int = 60) -> Optional[List[Dict]]:
        """
        Poll for async job results.
        
        Bright Data may process requests asynchronously.
        This method polls until results are ready or timeout.
        """
        endpoint = f"{self.base_url}/snapshot/{snapshot_id}"
        
        headers = {
            "Authorization": f"Bearer {self.api_token}"
        }
        
        params = {"format": "json"}
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for attempt in range(max_attempts):
                logger.info(f"🔄 Polling for results (attempt {attempt + 1}/{max_attempts})...")
                
                response = await client.get(endpoint, headers=headers, params=params)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Check if still processing
                    if isinstance(data, dict) and data.get("status") == "running":
                        await asyncio.sleep(3)  # Wait 3 seconds before next poll
                        continue
                    
                    # Results ready
                    if isinstance(data, list):
                        logger.info(f"✅ Polling complete, got {len(data)} items")
                        return data
                    return data.get("reviews", data.get("data", []))
                    
                elif response.status_code == 202:
                    # Still processing
                    await asyncio.sleep(3)
                    continue
                else:
                    logger.error(f"❌ Polling error: {response.status_code} - {response.text}")
                    return None
            
            logger.error("❌ Polling timeout - results not ready")
            return None
    
    def _standardize_reviews(self, reviews: List[Dict]) -> List[Dict[str, Any]]:
        """
        Standardize review data to a consistent format.
        
        Bright Data returns reviews in various formats depending on the dataset.
        This normalizes all fields to our expected format.
        
        Expected Bright Data fields:
        - review_text, review_title, rating, author_name, date, verified_purchase
        - Could also be: text, title, stars, reviewer_name, etc.
        """
        standardized = []
        product_title = ""
        product_image = ""
        
        for i, review in enumerate(reviews):
            try:
                # Skip if this is a product object without reviews
                if "reviews" in review and isinstance(review["reviews"], list):
                    # This is a product wrapper, extract reviews from it
                    product_title = review.get("title", review.get("product_title", ""))
                    product_image = review.get("image", review.get("product_image", review.get("main_image", "")))
                    
                    for sub_review in review["reviews"]:
                        std = self._parse_single_review(sub_review, i, product_title, product_image)
                        if std:
                            standardized.append(std)
                    continue
                
                # Parse as individual review
                std_review = self._parse_single_review(review, i, product_title, product_image)
                if std_review:
                    standardized.append(std_review)
                    
            except Exception as e:
                logger.warning(f"⚠️ Failed to standardize review {i}: {e}")
                continue
        
        logger.info(f"📊 Standardized {len(standardized)} reviews")
        return standardized
    
    def _parse_single_review(self, review: Dict, index: int, product_title: str = "", product_image: str = "") -> Optional[Dict[str, Any]]:
        """
        Parse a single review into standardized format.
        Handles various field name variations from Bright Data.
        """
        try:
            # Extract rating - try multiple field names
            rating = review.get("rating") or review.get("stars") or review.get("review_rating") or 3.0
            # Handle string ratings like "4.0 out of 5 stars"
            if isinstance(rating, str):
                import re
                match = re.search(r'(\d+\.?\d*)', rating)
                rating = float(match.group(1)) if match else 3.0
            rating = float(rating)
            
            # Extract text content
            text = (
                review.get("review_text") or 
                review.get("text") or 
                review.get("body") or 
                review.get("content") or 
                review.get("review") or
                ""
            )
            
            # Extract title
            title = (
                review.get("review_title") or 
                review.get("title") or 
                review.get("headline") or 
                ""
            )
            
            # Extract reviewer name
            reviewer_name = (
                review.get("author_name") or 
                review.get("reviewer_name") or 
                review.get("author") or 
                review.get("name") or 
                review.get("reviewer") or
                "Anonymous"
            )
            
            # Extract date
            date = (
                review.get("date") or 
                review.get("review_date") or 
                review.get("created_at") or 
                review.get("timestamp") or
                str(datetime.now().date())
            )
            
            # Extract verified purchase status
            verified = review.get("verified_purchase", review.get("verified", False))
            if isinstance(verified, str):
                verified = verified.lower() in ["true", "yes", "verified"]
            
            # Extract helpful votes
            helpful = review.get("helpful_votes") or review.get("helpful_count") or review.get("helpful") or 0
            if isinstance(helpful, str):
                import re
                match = re.search(r'(\d+)', helpful)
                helpful = int(match.group(1)) if match else 0
            
            # Extract product info if available
            prod_title = product_title or review.get("product_title", review.get("title", ""))
            prod_image = product_image or review.get("product_image", review.get("image", review.get("main_image", "")))
            
            std_review = {
                "review_id": review.get("review_id", review.get("id", f"review_{index}")),
                "reviewer_name": reviewer_name,
                "rating": rating,
                "title": title,
                "text": text,
                "date": date,
                "verified_purchase": bool(verified),
                "helpful_votes": int(helpful) if helpful else 0,
                "images": review.get("images", review.get("review_images", [])),
                "product_title": prod_title,
                "product_image": prod_image
            }
            
            return std_review
            
        except Exception as e:
            logger.warning(f"⚠️ Error parsing review: {e}")
            return None
    
    def _get_sample_reviews(self) -> List[Dict[str, Any]]:
        """
        Return sample reviews for development and testing.
        
        IMPORTANT: These are synthetic reviews for development only.
        Real analysis requires actual API data.
        
        Sample includes mix of genuine and fake patterns for testing.
        """
        sample_reviews = [
            # Genuine reviews (varied, specific, balanced)
            {
                "review_id": "R1GENUINE001",
                "reviewer_name": "Priya Sharma",
                "rating": 4.0,
                "title": "Good product but some minor issues",
                "text": "I've been using this for about 3 weeks now. The build quality is decent and it works as advertised. However, I noticed the battery life is slightly less than claimed - getting about 6 hours instead of 8. The sound quality is good for the price point. Delivery was on time. Would recommend for casual use but maybe look elsewhere for professional use.",
                "date": "2025-01-15",
                "verified_purchase": True,
                "helpful_votes": 12
            },
            {
                "review_id": "R1GENUINE002",
                "reviewer_name": "Rajesh Kumar",
                "rating": 3.0,
                "title": "Average performance, not worth the hype",
                "text": "After reading all the positive reviews, I had high expectations. Reality is it's just an average product. Does the job but nothing special. The packaging was nice but the product itself feels a bit cheap. I've used similar products from other brands that were better. Not bad, but not great either. Return process was hassle-free though.",
                "date": "2025-01-10",
                "verified_purchase": True,
                "helpful_votes": 8
            },
            {
                "review_id": "R1GENUINE003",
                "reviewer_name": "Anita Desai",
                "rating": 5.0,
                "title": "Exceeded expectations!",
                "text": "Bought this after comparing with 3 other similar products. This one stood out for the features vs price ratio. Setup took about 30 minutes following the manual. Been using for 2 months and no issues. The customer support was helpful when I had questions about settings. Only minor complaint is the cable could be longer. Overall very satisfied with my purchase.",
                "date": "2025-01-08",
                "verified_purchase": True,
                "helpful_votes": 25
            },
            {
                "review_id": "R1GENUINE004",
                "reviewer_name": "Vikram Singh",
                "rating": 2.0,
                "title": "Disappointed with quality",
                "text": "Received the product and was immediately disappointed. The photos online looked much better. Material feels flimsy and I doubt it will last long. Tried contacting seller but no response yet. Will update if things improve but as of now would not recommend. Expected much better for this price range.",
                "date": "2025-01-05",
                "verified_purchase": True,
                "helpful_votes": 15
            },
            
            # Fake reviews (suspicious patterns)
            {
                "review_id": "R1FAKE001",
                "reviewer_name": "Happy Customer123",
                "rating": 5.0,
                "title": "BEST PRODUCT EVER!!!",
                "text": "Amazing product! Best quality! Must buy! Everyone should buy this! 5 stars! Perfect in every way! No complaints at all! Buy it now! You won't regret it! Best purchase ever! Highly recommended! A+++! Super happy!",
                "date": "2025-01-20",
                "verified_purchase": False,
                "helpful_votes": 0
            },
            {
                "review_id": "R1FAKE002",
                "reviewer_name": "Review Verified User",
                "rating": 5.0,
                "title": "Perfect product must buy immediately",
                "text": "This product is perfect. I am very satisfied customer. The quality is best. Everyone in my family loves it. We bought 10 more for gifts. Best value for money. No other product compares. Buy without thinking!",
                "date": "2025-01-19",
                "verified_purchase": False,
                "helpful_votes": 1
            },
            {
                "review_id": "R1FAKE003",
                "reviewer_name": "John D.",
                "rating": 5.0,
                "title": "Excellent",
                "text": "Good product. Nice quality. Fast delivery. Recommended.",
                "date": "2025-01-18",
                "verified_purchase": False,
                "helpful_votes": 0
            },
            {
                "review_id": "R1FAKE004",
                "reviewer_name": "Satisfied Buyer",
                "rating": 5.0,
                "title": "Worth every penny",
                "text": "Best product in market. Superior quality than competitors. My life changed after using this. Cannot imagine living without it now. Every home needs one. Revolutionary product. Game changer. Innovation at its best!",
                "date": "2025-01-17",
                "verified_purchase": False,
                "helpful_votes": 2
            },
            {
                "review_id": "R1FAKE005",
                "reviewer_name": "TestReviewer",
                "rating": 5.0,
                "title": "Amazing Amazing Amazing",
                "text": "Amazing product amazing quality amazing price amazing delivery amazing packaging amazing everything. What more can I say? Just amazing!",
                "date": "2025-01-16",
                "verified_purchase": False,
                "helpful_votes": 0
            },
            
            # More genuine reviews for balance
            {
                "review_id": "R1GENUINE005",
                "reviewer_name": "Meera Patel",
                "rating": 4.0,
                "title": "Solid purchase with minor quirks",
                "text": "Used this for a month before reviewing. Overall satisfied. The product does what it claims. Setup was straightforward. A few things could be better - the instructions were confusing in parts and the app could use improvement. But for the price, it's a fair deal. Would buy again.",
                "date": "2025-01-12",
                "verified_purchase": True,
                "helpful_votes": 18
            },
            {
                "review_id": "R1GENUINE006",
                "reviewer_name": "Arjun Nair",
                "rating": 4.0,
                "title": "Good for beginners",
                "text": "As someone new to this category, I found this product easy to use. It's not the most advanced option but perfect for starting out. The learning curve is gentle and the results are satisfactory. Might upgrade to a better model later but for now this serves my needs well.",
                "date": "2025-01-11",
                "verified_purchase": True,
                "helpful_votes": 10
            },
            {
                "review_id": "R1GENUINE007",
                "reviewer_name": "Deepak Reddy",
                "rating": 3.0,
                "title": "Mixed feelings",
                "text": "There are things I like and dislike about this product. The design is sleek and modern. Performance is adequate. But it heats up quickly during extended use which is concerning. Also the warranty process seems complicated. It's okay for the price but don't expect miracles.",
                "date": "2025-01-09",
                "verified_purchase": True,
                "helpful_votes": 22
            }
        ]
        
        # Add product info to reviews
        for review in sample_reviews:
            review["product_title"] = "Sample Product - Wireless Bluetooth Headphones"
            review["product_image"] = "https://via.placeholder.com/300x300?text=Product+Image"
        
        return sample_reviews
    
    def _get_sample_reviews_for_product(self, asin: str, product_url: str) -> List[Dict[str, Any]]:
        """
        Get sample reviews with product-specific info from ASIN/URL.
        Uses the actual ASIN to generate more realistic demo data.
        """
        # Get base sample reviews
        sample_reviews = self._get_sample_reviews()
        
        # Try to get product image from Amazon's image CDN
        # Amazon's standard image URL format
        product_image = f"https://m.media-amazon.com/images/I/41placeholder.jpg"
        
        # Use ASIN in the product title to make it feel more real
        product_title = f"Amazon Product (ASIN: {asin})"
        
        # Update all reviews with the actual product info
        for review in sample_reviews:
            review["product_title"] = product_title
            review["product_image"] = product_image
            review["asin"] = asin
            review["product_url"] = product_url
        
        logger.info(f"📦 Generated sample reviews for ASIN: {asin}")
        return sample_reviews
