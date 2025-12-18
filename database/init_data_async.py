"""
Optimized Async Data Loading Script for Polymarket Trading Agent

This script uses async/await and concurrent processing to load data much faster.
Processes multiple markets in parallel while respecting API rate limits.
"""

import sys
import asyncio
import aiohttp
from pathlib import Path
from dotenv import load_dotenv
import time
from typing import List, Dict, Optional
from collections import defaultdict

# Load environment variables
project_root = Path(__file__).parent.parent
dotenv_path = project_root / '.env'
load_dotenv(dotenv_path)

# Import functions from load_data_to_db.py
from database.load_data_to_db import (
    get_events,
    upsert_events,
    transform_market_data,
    transform_user_data,
    transform_trade_data,
    transform_event_data,
    upsert_users,
    take_snapshots_for_active_markets,
    update_all_user_metrics,
    supabase,
    SUPABASE_URL
)

# Import Supabase utility functions
from database.supabase_utils import retrieve_all_distinct_values, bulk_insert, bulk_upsert


# ============================================
# Async API Functions
# ============================================

async def fetch_events_async(
    session: aiohttp.ClientSession,
    active: Optional[bool] = None,
    closed: Optional[bool] = None,
    limit: int = 100,
    offset: int = 0
) -> List[Dict]:
    """Async version of get_events"""
    url = "https://gamma-api.polymarket.com/events"
    params = {
        "limit": str(limit),
        "offset": str(offset),
        "ascending": "false"  # Convert boolean to string
    }
    
    if active is not None:
        params["active"] = str(active).lower()
    if closed is not None:
        params["closed"] = str(closed).lower()
    
    try:
        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as response:
            if response.status == 200:
                return await response.json()
            elif response.status == 429:  # Rate limited
                print(f"⚠️  Rate limited on events API, waiting 5s...")
                await asyncio.sleep(5)
                return []
            else:
                print(f"⚠️  Events API returned status {response.status}")
                return []
    except asyncio.TimeoutError:
        print(f"⚠️  Timeout fetching events...")
        return []
    except Exception as e:
        print(f"⚠️  Error fetching events: {type(e).__name__}: {e}")
        return []


async def fetch_events_async(
    session: aiohttp.ClientSession,
    active: Optional[bool] = None,
    closed: Optional[bool] = None,
    limit: int = 100,
    offset: int = 0
) -> List[Dict]:
    """Async version of get_events"""
    url = "https://gamma-api.polymarket.com/events"
    params = {
        "limit": str(limit),
        "offset": str(offset),
        "ascending": "false"  # Convert boolean to string for aiohttp
    }
    
    if active is not None:
        params["active"] = str(active).lower()
    if closed is not None:
        params["closed"] = str(closed).lower()
    
    try:
        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as response:
            if response.status == 200:
                return await response.json()
            elif response.status == 429:  # Rate limited
                print(f"⚠️  Rate limited on events API, waiting 5s...")
                await asyncio.sleep(5)
                return []
            else:
                print(f"⚠️  Events API returned status {response.status}")
                return []
    except asyncio.TimeoutError:
        print(f"⚠️  Timeout fetching events...")
        return []
    except Exception as e:
        print(f"⚠️  Error fetching events: {type(e).__name__}: {e}")
        return []


async def fetch_trades_async(
    session: aiohttp.ClientSession,
    market: str,
    limit: int = 100,
    offset: int = 0
) -> List[Dict]:
    """Async version of get_trades"""
    url = "https://data-api.polymarket.com/trades"
    params = {
        "market": market,
        "limit": limit,
        "offset": offset
    }
    
    try:
        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as response:
            if response.status == 200:
                return await response.json()
            elif response.status == 429:  # Rate limited
                print(f"⚠️  Rate limited, waiting 5s...")
                await asyncio.sleep(5)
                return []
            else:
                # Don't print for every error, just return empty
                return []
    except asyncio.TimeoutError:
        print(f"⚠️  Timeout fetching trades for market {market[:20]}...")
        return []
    except Exception as e:
        # Only print unexpected errors
        if "timeout" not in str(e).lower():
            print(f"⚠️  Error fetching trades: {type(e).__name__}")
        return []


async def fetch_all_trades_for_market(
    session: aiohttp.ClientSession,
    condition_id: str,
    market_name: str = "",
    batch_size: int = 100,
    max_trades_per_market: int = 10000  # Limit to prevent hanging
) -> tuple[List[Dict], int]:
    """
    Fetch all trades for a single market using async pagination
    Returns: (trades_list, total_count)
    """
    all_trades = []
    offset = 0
    fetches = 0
    
    while True:
        trades_batch = await fetch_trades_async(
            session,
            market=condition_id,
            limit=batch_size,
            offset=offset
        )
        
        if not trades_batch or len(trades_batch) == 0:
            break
        
        all_trades.extend(trades_batch)
        offset += batch_size
        fetches += 1
        
        # Progress indicator for large markets
        if fetches % 10 == 0:
            print(f"    ... {market_name[:20]} fetched {len(all_trades)} trades so far...")
        
        # Safety limit to prevent hanging on huge markets
        if len(all_trades) >= max_trades_per_market:
            print(f"    ⚠️  {market_name[:20]} hit limit of {max_trades_per_market} trades, stopping...")
            break
        
        # If we got fewer than batch_size, we've reached the end
        if len(trades_batch) < batch_size:
            break
    
    return all_trades, len(all_trades)


def upsert_markets_batch(markets: List[Dict], event_id: str) -> int:
    """
    Upsert a batch of markets for an event into the database
    Returns: number of markets upserted
    """
    if not markets:
        return 0
    
    market_records = []
    for market in markets:
        try:
            # Transform market data and inject event_id
            transformed = transform_market_data(market, event_id=event_id)
            
            # Remove None values
            transformed = {k: v for k, v in transformed.items() if v is not None}
            
            # Ensure event_id is present (required foreign key)
            if not transformed.get('event_id'):
                continue
            
            market_records.append(transformed)
            
        except Exception as e:
            print(f"    ⚠️  Error transforming market {market.get('slug')}: {e}")
    
    if not market_records:
        return 0
    
    # Bulk upsert markets
    count = bulk_upsert(
        supabase,
        "markets",
        market_records,
        on_conflict="slug",
        chunk_size=100
    )
    
    return count


def upsert_events_batch(events: List[Dict]) -> int:
    """
    Bulk upsert a batch of events into the database
    Returns: number of events upserted
    """
    if not events:
        return 0
    
    event_records = []
    for event in events:
        try:
            # Transform event data
            transformed = transform_event_data(event)
            
            # Remove None values
            transformed = {k: v for k, v in transformed.items() if v is not None}
            
            event_records.append(transformed)
            
        except Exception as e:
            print(f"    ⚠️  Error transforming event {event.get('slug')}: {e}")
    
    if not event_records:
        return 0
    
    # Bulk upsert events
    count = bulk_upsert(
        supabase,
        "events",
        event_records,
        on_conflict="slug",
        chunk_size=100
    )
    
    return count


def upsert_markets_batch(markets: List[Dict], event_id: str) -> int:
    """
    Bulk upsert a batch of markets for an event into the database
    Returns: number of markets upserted
    """
    if not markets:
        return 0
    
    market_records = []
    for market in markets:
        try:
            # Transform market data and inject event_id
            transformed = transform_market_data(market, event_id=event_id)
            
            # Remove None values
            transformed = {k: v for k, v in transformed.items() if v is not None}
            
            # Ensure event_id is present (required foreign key)
            if not transformed.get('event_id'):
                continue
            
            market_records.append(transformed)
            
        except Exception as e:
            print(f"    ⚠️  Error transforming market {market.get('slug')}: {e}")
    
    if not market_records:
        return 0
    
    # Bulk upsert markets
    count = bulk_upsert(
        supabase,
        "markets",
        market_records,
        on_conflict="slug",
        chunk_size=100
    )
    
    return count


def insert_trades_batch(trades: List[Dict]) -> tuple[int, int]:
    """
    Insert a batch of trades and their users into database using BULK operations
    Returns: (user_count, trade_count)
    """
    if not trades:
        return 0, 0
    
    # Extract and bulk upsert users first (users table uses proxy_wallet as PK)
    users = [transform_user_data(trade) for trade in trades]
    unique_users = {u['proxy_wallet']: u for u in users if u.get('proxy_wallet')}
    user_records = [
        {k: v for k, v in user.items() if v is not None}
        for user in unique_users.values()
    ]
    user_count = bulk_upsert(
        supabase,
        "users",
        user_records,
        on_conflict="proxy_wallet",
        chunk_size=500
    )
    
    # Transform and filter trades
    valid_trades = []
    for trade in trades:
        transformed = transform_trade_data(trade)
        transformed = {k: v for k, v in transformed.items() if v is not None}
        
        # Skip if missing required fields
        if all([
            transformed.get('proxy_wallet'),
            transformed.get('side'),
            transformed.get('size'),
            transformed.get('price'),
            transformed.get('timestamp')
        ]):
            valid_trades.append(transformed)
    
    # Bulk insert trades
    # Note: transaction_hash is NOT unique (one tx can have multiple trades)
    # Show progress for large batches
    show_progress = len(valid_trades) > 1000
    
    trade_count = bulk_insert(
        supabase,
        "trades",
        valid_trades,
        chunk_size=500,
        ignore_duplicates=True,
        show_progress=show_progress
    )
    
    return user_count, trade_count


async def process_market_batch(
    session: aiohttp.ClientSession,
    markets_batch: List[str],
    semaphore: asyncio.Semaphore,
    batch_idx: int,
    timeout_seconds: int = 180
) -> tuple[int, int, int]:
    """
    Process a batch of markets concurrently
    Returns: (total_users, total_trades, markets_processed)
    """
    async with semaphore:
        print(f"\n📦 Processing batch {batch_idx} ({len(markets_batch)} markets)...")
        batch_start = time.time()
        
        # Fetch trades for all markets in this batch concurrently with timeout
        tasks = [
            fetch_all_trades_for_market(
                session, 
                condition_id,
                market_name=f"Market-{idx+1}",
                max_trades_per_market=10000
            )
            for idx, condition_id in enumerate(markets_batch)
        ]
        
        try:
            results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=timeout_seconds
            )
        except asyncio.TimeoutError:
            print(f"  ⚠️  Batch {batch_idx} timed out after {timeout_seconds}s, skipping...")
            return 0, 0, 0
        
        # Process results and insert to database
        total_users = 0
        total_trades = 0
        markets_with_trades = 0
        
        for idx, (condition_id, result) in enumerate(zip(markets_batch, results)):
            if isinstance(result, Exception):
                print(f"  ⚠️  Market {idx+1}/{len(markets_batch)}: Error - {result}")
                continue
                
            trades, count = result
            if count > 0:
                if count > 1000:
                    print(f"  ⚡ Market {idx+1}/{len(markets_batch)}: {condition_id[:20]}... - {count} trades (LARGE, inserting...)")
                else:
                    print(f"  ✓ Market {idx+1}/{len(markets_batch)}: {condition_id[:20]}... - {count} trades", end="")
                
                start_insert = time.time()
                users, inserted = insert_trades_batch(trades)
                elapsed_insert = time.time() - start_insert
                
                total_users += users
                total_trades += inserted
                markets_with_trades += 1
                
                if count <= 1000:
                    if inserted < count:
                        print(f" → inserted {inserted}/{count} ({elapsed_insert:.1f}s)")
                    else:
                        print(f" → inserted {inserted} ({elapsed_insert:.1f}s)")
                else:
                    print(f"  ✓ Inserted {inserted}/{count} trades ({elapsed_insert:.1f}s, {inserted/elapsed_insert:.0f} trades/s)")
            else:
                print(f"  ○ Market {idx+1}/{len(markets_batch)}: {condition_id[:20]}... - no trades")
        
        elapsed = time.time() - batch_start
        print(f"  ✓ Batch {batch_idx} complete: {markets_with_trades}/{len(markets_batch)} markets, {total_trades} trades ({elapsed:.1f}s)")
        return total_users, total_trades, markets_with_trades

async def init_load_all_events_with_markets_async(
    batch_size: int = 100,
    start_offset: int = 0
):
    """
    Async version: Load ALL events with their nested markets from Polymarket API with pagination.
    Uses bulk operations for faster loading.
    
    Args:
        batch_size: Number of events to fetch per API call (max 100)
        start_offset: Starting offset for pagination (useful for resuming failed loads)
    
    Returns:
        tuple: (total_events_loaded, total_markets_loaded)
    """
    print("=" * 70)
    print("INITIALIZING: Loading ALL Events with Markets (ASYNC)")
    if start_offset > 0:
        print(f"🔄 RESUMING from offset {start_offset}")
    print("=" * 70)
    
    offset = start_offset
    total_events = 0
    total_markets = 0
    batch_num = 1 if start_offset == 0 else (start_offset // batch_size) + 1
    
    connector = aiohttp.TCPConnector(limit=10)
    timeout = aiohttp.ClientTimeout(total=30, connect=10)
    
    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        while True:
            print(f"\n📦 Batch {batch_num} (offset={offset}, limit={batch_size})")
            print("-" * 70)
            
            try:
                # Fetch events batch
                print(f"  → Fetching events...")
                events_batch = await fetch_events_async(
                    session,
                    active=None,  # Get all events (active and inactive)
                    closed=None,  # Get all events (closed and open)
                    limit=batch_size,
                    offset=offset
                )
                
                # Check if we got any data
                if not events_batch or len(events_batch) == 0:
                    print(f"  ✓ No more events to fetch. Pagination complete!")
                    break
                
                print(f"  ✓ Fetched {len(events_batch)} events")
                
                # Step 1: Bulk upsert events
                event_count = upsert_events_batch(events_batch)
                total_events += event_count
                print(f"  ✓ Bulk upserted {event_count} events (total: {total_events})")
                
                # Step 2: Process nested markets
                print(f"  → Processing nested markets...")
                batch_markets = 0
                
                # Group events by whether they have markets
                events_with_markets = [e for e in events_batch if e.get('markets')]
                
                if events_with_markets:
                    # Process markets for each event
                    for event in events_with_markets:
                        event_id = event.get('id')
                        markets = event.get('markets', [])
                        
                        if markets:
                            # Bulk upsert all markets for this event
                            count = upsert_markets_batch(markets, event_id)
                            batch_markets += count
                
                total_markets += batch_markets
                print(f"  ✓ Upserted {batch_markets} markets (total: {total_markets})")
                
                # Prepare for next batch
                offset += batch_size
                batch_num += 1
                
                # Rate limiting - be respectful to the API
                print(f"  ⏳ Rate limiting (1s)...")
                await asyncio.sleep(1)
                
            except Exception as e:
                print(f"  ✗ Error in batch {batch_num}: {e}")
                print(f"  ⚠️  Stopping pagination. Progress saved.")
                break
    
    # Summary
    print("\n" + "=" * 70)
    print("EVENTS & MARKETS LOADING COMPLETE")
    print("=" * 70)
    print(f"  Total Events Loaded:   {total_events:,}")
    print(f"  Total Markets Loaded:  {total_markets:,}")
    if total_events > 0:
        print(f"  Avg Markets/Event:     {total_markets/total_events:.2f}")
    print("=" * 70)
    
    return total_events, total_markets


async def init_load_all_trades_async(
    max_concurrent_markets: int = 10,
    markets_per_batch: int = 5,
    start_market_index: int = 0
):
    """
    Async version: Load ALL trades from Polymarket by processing multiple markets concurrently
    
    Args:
        max_concurrent_markets: Maximum number of concurrent API requests
        markets_per_batch: Number of markets to process in each batch
        start_market_index: Starting market index for resuming
    
    Returns:
        tuple: (total_users, total_trades, markets_processed)
    """
    print("\n" + "=" * 70)
    print("INITIALIZING: Loading ALL Trades (ASYNC - OPTIMIZED)")
    print(f"Concurrency: {max_concurrent_markets} | Batch size: {markets_per_batch}")
    if start_market_index > 0:
        print(f"🔄 RESUMING from market index {start_market_index}")
    print("=" * 70)
    
    # Step 1: Get all condition_ids from markets table
    print(f"\n→ Retrieving all condition_ids from recent_markets table...")
    try:
        condition_ids = retrieve_all_distinct_values(
            supabase,
            "recent_markets",
            "condition_id"
        )
        print(f"✓ Found {len(condition_ids)} unique recent_markets with condition_ids")
    except Exception as e:
        print(f"✗ Error retrieving condition_ids: {e}")
        return 0, 0, 0
    
    # Filter out None values and start from the specified index
    condition_ids = [cid for cid in condition_ids if cid is not None]
    condition_ids = condition_ids[start_market_index:]
    
    if not condition_ids:
        print("No markets to process!")
        return 0, 0, 0
    
    print(f"→ Processing {len(condition_ids)} markets...")
    
    # Step 2: Process markets in batches with concurrency control
    semaphore = asyncio.Semaphore(max_concurrent_markets)
    total_users_loaded = 0
    total_trades_loaded = 0
    total_markets_processed = 0
    
    # Split markets into batches
    market_batches = [
        condition_ids[i:i + markets_per_batch]
        for i in range(0, len(condition_ids), markets_per_batch)
    ]
    
    print(f"→ Split into {len(market_batches)} batches of {markets_per_batch} markets each")
    
    start_time = time.time()
    
    # Create aiohttp session with connection pooling
    connector = aiohttp.TCPConnector(limit=max_concurrent_markets)
    timeout = aiohttp.ClientTimeout(total=30, connect=10)  # 30s total, 10s connect timeout
    
    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        # Process batches sequentially (but markets within each batch concurrently)
        for batch_idx, markets_batch in enumerate(market_batches, start=1):
            try:
                users, trades, markets = await process_market_batch(
                    session,
                    markets_batch,
                    semaphore,
                    batch_idx
                )
                
                total_users_loaded += users
                total_trades_loaded += trades
                total_markets_processed += markets
                
                # Progress update
                elapsed = time.time() - start_time
                rate = total_markets_processed / elapsed if elapsed > 0 else 0
                remaining = len(condition_ids) - total_markets_processed
                eta = remaining / rate if rate > 0 else 0
                
                print(f"  📊 Progress: {total_markets_processed}/{len(condition_ids)} markets "
                      f"({total_markets_processed/len(condition_ids)*100:.1f}%) | "
                      f"Rate: {rate:.1f} markets/s | ETA: {eta/60:.1f} min")
                
                # Small delay between batches to be respectful
                if batch_idx < len(market_batches):
                    await asyncio.sleep(0.5)
                    
            except Exception as e:
                print(f"⚠️  Error processing batch {batch_idx}: {e}")
                continue
    
    # Summary
    elapsed = time.time() - start_time
    print("\n" + "=" * 70)
    print("ASYNC TRADES LOADING COMPLETE")
    print("=" * 70)
    print(f"  Markets Processed:     {total_markets_processed:,}")
    print(f"  Total Trades Loaded:   {total_trades_loaded:,}")
    print(f"  Unique Users:          {total_users_loaded:,}")
    if total_markets_processed > 0:
        print(f"  Avg Trades/Market:     {total_trades_loaded/total_markets_processed:.2f}")
    print(f"  Time Elapsed:          {elapsed/60:.2f} minutes")
    print(f"  Speed:                 {total_markets_processed/elapsed:.2f} markets/sec")
    print("=" * 70)
    
    return total_users_loaded, total_trades_loaded, total_markets_processed


def run_full_initialization_async(
    events_start_offset: int = 0,
    trades_start_market_index: int = 0,
    max_concurrent: int = 10,
    markets_per_batch: int = 5
):
    """
    Run complete async initialization: load all events, markets, and trades.
    
    Args:
        events_start_offset: Starting offset for events pagination
        trades_start_market_index: Starting market index for trades
        max_concurrent: Max concurrent API requests
        markets_per_batch: Markets to process per batch
    """
    print("\n" + "🚀" * 35)
    print("POLYMARKET DATA INITIALIZATION - ASYNC OPTIMIZED")
    print("🚀" * 35)
    
    # Check configuration
    if SUPABASE_URL == "your-project-url.supabase.co":
        print("\n❌ ERROR: Please set SUPABASE_URL and SUPABASE_KEY in .env file!")
        sys.exit(1)
    
    print(f"\n✓ Connected to Supabase: {SUPABASE_URL}")
    
    start_time = time.time()
    
    # Step 1: Load all events with markets (ASYNC!)
    print("\n" + "=" * 70)
    print("PHASE 1: Events & Markets (ASYNC)")
    print("=" * 70)
    total_events, total_markets = asyncio.run(
        init_load_all_events_with_markets_async(
            batch_size=100,
            start_offset=events_start_offset
        )
    )
    
    # Step 2: Load all trades by market (ASYNC!)
    print("\n" + "=" * 70)
    print("PHASE 2: Trades & Users (ASYNC)")
    print("=" * 70)
    total_users, total_trades, markets_processed = asyncio.run(
        init_load_all_trades_async(
            max_concurrent_markets=max_concurrent,
            markets_per_batch=markets_per_batch,
            start_market_index=trades_start_market_index
        )
    )
    
    # Step 3: Take market snapshots for active markets
    print("\n" + "=" * 70)
    print("PHASE 3: Market Snapshots")
    print("=" * 70)
    snapshot_count = take_snapshots_for_active_markets()
    
    # Step 4: Update user metrics
    print("\n" + "=" * 70)
    print("PHASE 4: User Metrics")
    print("=" * 70)
    update_all_user_metrics()
    
    # Final summary
    elapsed = time.time() - start_time
    print("\n" + "🎉" * 35)
    print("ASYNC INITIALIZATION COMPLETE!")
    print("🎉" * 35)
    print(f"\n📊 Summary:")
    print(f"  Events:                {total_events:,}")
    print(f"  Markets:               {total_markets:,}")
    print(f"  Markets w/ Trades:     {markets_processed:,}")
    print(f"  Users:                 {total_users:,}")
    print(f"  Trades:                {total_trades:,}")
    print(f"  Snapshots:             {snapshot_count:,}")
    print(f"\n⏱️  Time Elapsed:          {elapsed/60:.2f} minutes")
    print(f"⚡  Speedup vs Sync:       ~{max_concurrent}x faster")
    print("=" * 70)


if __name__ == "__main__":
    print("\n⚠️  WARNING: This is the ASYNC OPTIMIZED version.")
    print("⚠️  This will load ALL historical data from Polymarket using concurrent requests.")
    print("⚠️  Make sure you have a clean database or are okay with upserting data.\n")
    
    response = input("Continue? (yes/no): ").strip().lower()
    
    if response == 'yes':
        # Adjust these parameters based on your needs
        # max_concurrent: Higher = faster, but be respectful to API
        # markets_per_batch: Number of markets to process together
        run_full_initialization_async(
            max_concurrent=15,      # Process 15 markets concurrently
            markets_per_batch=10    # Group 10 markets per batch
        )
    else:
        print("\n❌ Initialization cancelled.")
        sys.exit(0)

