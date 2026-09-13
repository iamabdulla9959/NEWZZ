import asyncio
import os
import sys

# Add the api directory to sys.path so we can import the FastAPI app's logic
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../api")))

from sqlalchemy.orm import Session
from app.db import SessionLocal
from app.routers.feed import get_feed

def run_test_case(db: Session, name: str, kwargs: dict):
    print(f"=== Running Test Case: {name} ===")
    print(f"Args: {kwargs}")
    
    # Run the get_feed logic directly
    feed_out = get_feed(db=db, **kwargs)
    
    print(f"Total Results: {feed_out.total}")
    print(f"Fallback Used: {feed_out.fallback_used}")
    print(f"Fallback Level: {feed_out.fallback_level}")
    print(f"Items Returned: {len(feed_out.items)}")
    
    word_counts = []
    source_counts = []
    promotional_count = 0
    categories = {}
    
    for item in feed_out.items:
        word_count = len(item.summary.split())
        word_counts.append(word_count)
        source_counts.append(len(item.sources))
        
        # Check if priority score is 1 (we don't have priority score in CardOut, but objective_score could be an indicator)
        # Assuming we can just measure length and sources for now
        categories[item.category] = categories.get(item.category, 0) + 1
        
    if word_counts:
        avg_words = sum(word_counts) / len(word_counts)
        print(f"Avg Summary Length: {avg_words:.1f} words")
        print(f"Min/Max Words: {min(word_counts)} / {max(word_counts)}")
    
    if source_counts:
        avg_sources = sum(source_counts) / len(source_counts)
        print(f"Avg Sources per article: {avg_sources:.1f}")
        
    print("Categories Breakdown:")
    for cat, count in categories.items():
        print(f"  - {cat}: {count}")
    print("\n")


def main():
    db = SessionLocal()
    try:
        # Test Case 1: Visakhapatnam For You (All categories)
        run_test_case(db, "Visakhapatnam For You", {
            "categories": "all",
            "district": "Visakhapatnam",
            "state": "Andhra Pradesh",
            "device_id": "test_device_1",
            "offset": 0,
            "limit": 50,
        })
        
        # Test Case 2: Other District For You (Missing district fallback)
        run_test_case(db, "Other District For You", {
            "categories": "all",
            "district": "Srikakulam",
            "state": "Andhra Pradesh",
            "device_id": "test_device_1",
            "offset": 0,
            "limit": 50,
        })
        
        # Test Case 3: Visakhapatnam Politics
        run_test_case(db, "Visakhapatnam Politics", {
            "categories": "politics",
            "district": "Visakhapatnam",
            "state": "Andhra Pradesh",
            "device_id": "test_device_1",
            "offset": 0,
            "limit": 50,
        })
        
        # Test Case 4: Visakhapatnam Tech (Often triggers fallback to State or National)
        run_test_case(db, "Visakhapatnam Tech", {
            "categories": "tech",
            "district": "Visakhapatnam",
            "state": "Andhra Pradesh",
            "device_id": "test_device_1",
            "offset": 0,
            "limit": 50,
        })
        
        # Test Case 5: Visakhapatnam Local (District) category fallback check
        run_test_case(db, "Visakhapatnam Local (district category)", {
            "categories": "district",
            "district": "Visakhapatnam",
            "state": "Andhra Pradesh",
            "device_id": "test_device_1",
            "offset": 0,
            "limit": 50,
        })

    finally:
        db.close()


if __name__ == "__main__":
    main()
