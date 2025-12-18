"""
Initial Data Loading Script for Polymarket Trading Agent

This script loads ALL historical data from Polymarket API with proper pagination.
Only run this once to initialize the database with historical data.
For regular updates, use load_data_to_db.py with specific limits.
"""

import sys
from pathlib import Path
from dotenv import load_dotenv
import time

# Load environment variables
project_root = Path(__file__).parent.parent
dotenv_path = project_root / '.env'
load_dotenv(dotenv_path)

# Import functions from load_data_to_db.py
from database.load_data_to_db import (
    get_events,
    get_trades,
    upsert_events,
    upsert_markets,
    transform_market_data,
    transform_user_data,
    upsert_users,
    insert_trades,
    transform_trade_data,
    take_snapshots_for_active_markets,
    update_all_user_metrics,
    supabase,
    SUPABASE_URL
)

# Import Supabase utility functions
from database.supabase_utils import retrieve_all_distinct_values


def init_load_all_events_with_markets(batch_size: int = 100, start_offset: int = 0):
    """
    Load ALL events with their nested markets from Polymarket API with pagination.
    
    Args:
        batch_size: Number of events to fetch per API call (max 100)
        start_offset: Starting offset for pagination (useful for resuming failed loads)
    
    Returns:
        tuple: (total_events_loaded, total_markets_loaded)
    """
    print("=" * 70)
    print("INITIALIZING: Loading ALL Events with Markets (Paginated)")
    if start_offset > 0:
        print(f"🔄 RESUMING from offset {start_offset}")
    print("=" * 70)
    
    offset = start_offset
    total_events = 0
    total_markets = 0
    batch_num = 1 if start_offset == 0 else (start_offset // batch_size) + 1
    
    while True:
        print(f"\n📦 Batch {batch_num} (offset={offset}, limit={batch_size})")
        print("-" * 70)
        
        try:
            # Fetch events batch
            print(f"  → Fetching events...")
            events_batch = get_events(
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
            
            # Step 1: Upsert events
            print(f"  → Upserting events to database...")
            event_count = upsert_events(events_batch)
            total_events += event_count
            print(f"  ✓ Upserted {event_count} events (total: {total_events})")
            
            # Step 2: Process nested markets
            print(f"  → Processing nested markets...")
            batch_markets = 0
            
            for event in events_batch:
                event_id = event.get('id')
                markets = event.get('markets', [])
                
                if not markets:
                    continue
                
                # Process each nested market
                for market in markets:
                    try:
                        # Transform and inject event_id
                        transformed = transform_market_data(market, event_id=event_id)
                        transformed = {k: v for k, v in transformed.items() if v is not None}
                        
                        if not transformed.get('event_id'):
                            continue
                        
                        # Upsert to database
                        supabase.table('markets').upsert(
                            transformed,
                            on_conflict='slug'
                        ).execute()
                        
                        batch_markets += 1
                        
                    except Exception as e:
                        print(f"    ⚠️  Error upserting market {market.get('slug')}: {e}")
            
            total_markets += batch_markets
            print(f"  ✓ Upserted {batch_markets} markets (total: {total_markets})")
            
            # Prepare for next batch
            offset += batch_size
            batch_num += 1
            
            # Rate limiting - be respectful to the API
            print(f"  ⏳ Rate limiting (2s)...")
            time.sleep(2)
            
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


def init_load_all_trades_by_market(batch_size: int = 100, start_market_index: int = 0):
    """
    Load ALL trades from Polymarket API by iterating through each market's condition_id.
    This approach ensures we get all trades for each market.
    
    Args:
        batch_size: Number of trades to fetch per API call (max 100)
        start_market_index: Starting market index for resuming (useful for resuming failed loads)
    
    Returns:
        tuple: (total_users_loaded, total_trades_loaded, markets_processed)
    """
    print("\n" + "=" * 70)
    print("INITIALIZING: Loading ALL Trades by Market (Paginated)")
    if start_market_index > 0:
        print(f"🔄 RESUMING from market index {start_market_index}")
    print("=" * 70)
    
    # Step 1: Get all condition_ids from markets table
    print(f"\n→ Retrieving all condition_ids from markets table...")
    try:
        condition_ids = retrieve_all_distinct_values(
            supabase,
            "markets",
            "condition_id"
        )
        print(f"✓ Found {len(condition_ids)} unique markets with condition_ids")
    except Exception as e:
        print(f"✗ Error retrieving condition_ids: {e}")
        return 0, 0, 0
    
    # Filter out None values and start from the specified index
    condition_ids = [cid for cid in condition_ids if cid is not None]
    condition_ids = condition_ids[start_market_index:]
    
    total_trades_inserted = 0
    all_users = {}  # Keep track of unique users
    markets_processed = 0
    
    # Step 2: Iterate through each condition_id and fetch its trades
    for market_idx, condition_id in enumerate(condition_ids, start=start_market_index + 1):
        print(f"\n📊 Market {market_idx}/{len(condition_ids) + start_market_index}: {condition_id}")
        print("-" * 70)
        
        offset = 0
        market_trades_count = 0
        batch_num = 1
        
        # Paginate through all trades for this market
        while True:
            try:
                # Fetch trades for this specific market
                print(f"  → Batch {batch_num}: Fetching trades (offset={offset})...")
                trades_batch = get_trades(
                    market=condition_id,
                    limit=batch_size,
                    offset=offset
                )
                
                # Check if we got any data
                if not trades_batch or len(trades_batch) == 0:
                    print(f"  ✓ No more trades for this market")
                    break
                
                print(f"  ✓ Fetched {len(trades_batch)} trades")
                
                # Extract and collect user data
                batch_users = [transform_user_data(trade) for trade in trades_batch]
                for user in batch_users:
                    wallet = user.get('proxy_wallet')
                    if wallet:
                        all_users[wallet] = user
                
                # Upsert users BEFORE inserting trades (to satisfy foreign key constraint)
                if batch_users:
                    batch_user_count = upsert_users(batch_users)
                    print(f"  ✓ Upserted {batch_user_count} users for this batch")
                
                # Insert trades directly using batch insert
                batch_trade_count = insert_trades(trades_batch)
                
                market_trades_count += batch_trade_count
                total_trades_inserted += batch_trade_count
                print(f"  ✓ Inserted {batch_trade_count} trades (market total: {market_trades_count})")
                
                # Prepare for next batch
                offset += batch_size
                batch_num += 1
                
                # If we got fewer than batch_size, we've reached the end
                if len(trades_batch) < batch_size:
                    break
                
            except Exception as e:
                print(f"  ⚠️  Error fetching trades for market {condition_id}: {e}")
                break
        
        markets_processed += 1
        print(f"  ✓ Market complete: {market_trades_count} trades")
        
        # Rate limiting between markets
        if market_idx % 10 == 0:  # Every 10 markets
            print(f"  ⏳ Rate limiting (3s)...")
            time.sleep(3)
        else:
            time.sleep(0.5)  # Small delay between markets
    
    # Final validation: ensure all collected users are in database
    print("\n" + "-" * 70)
    print("Final validation: ensuring all users are in database...")
    user_count = len(all_users)
    print(f"✓ Total unique users collected: {user_count}")
    
    # Summary
    print("\n" + "=" * 70)
    print("TRADES LOADING COMPLETE")
    print("=" * 70)
    print(f"  Markets Processed:     {markets_processed:,}")
    print(f"  Total Users Loaded:    {user_count:,}")
    print(f"  Total Trades Loaded:   {total_trades_inserted:,}")
    if markets_processed > 0:
        print(f"  Avg Trades/Market:     {total_trades_inserted/markets_processed:.2f}")
    print("=" * 70)
    
    return user_count, total_trades_inserted, markets_processed


def run_full_initialization(events_start_offset: int = 0, trades_start_market_index: int = 0):
    """
    Run complete initialization: load all events, markets, and trades.
    Then take snapshots and update metrics.
    
    Args:
        events_start_offset: Starting offset for events pagination (for resuming)
        trades_start_market_index: Starting market index for trades pagination (for resuming)
    """
    print("\n" + "🚀" * 35)
    print("POLYMARKET DATA INITIALIZATION - FULL LOAD")
    print("🚀" * 35)
    
    # Check configuration
    if SUPABASE_URL == "your-project-url.supabase.co":
        print("\n❌ ERROR: Please set SUPABASE_URL and SUPABASE_KEY in .env file!")
        sys.exit(1)
    
    print(f"\n✓ Connected to Supabase: {SUPABASE_URL}")
    
    start_time = time.time()
    
    # Step 1: Load all events with markets
    print("\n" + "=" * 70)
    print("PHASE 1: Events & Markets")
    print("=" * 70)
    total_events, total_markets = init_load_all_events_with_markets(
        batch_size=100,
        start_offset=events_start_offset
    )
    
    # Step 2: Load all trades by market
    print("\n" + "=" * 70)
    print("PHASE 2: Trades & Users (by Market)")
    print("=" * 70)
    total_users, total_trades, markets_processed = init_load_all_trades_by_market(
        batch_size=100,
        start_market_index=trades_start_market_index
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
    print("INITIALIZATION COMPLETE!")
    print("🎉" * 35)
    print(f"\n📊 Summary:")
    print(f"  Events:                {total_events:,}")
    print(f"  Markets:               {total_markets:,}")
    print(f"  Markets w/ Trades:     {markets_processed:,}")
    print(f"  Users:                 {total_users:,}")
    print(f"  Trades:                {total_trades:,}")
    print(f"  Snapshots:             {snapshot_count:,}")
    print(f"\n⏱️  Time Elapsed:          {elapsed/60:.2f} minutes")
    print("=" * 70)


if __name__ == "__main__":
    print("\n⚠️  WARNING: This script will load ALL historical data from Polymarket.")
    print("⚠️  This may take a significant amount of time and API calls.")
    print("⚠️  Make sure you have a clean database or are okay with upserting data.\n")
    
    response = input("Continue? (yes/no): ").strip().lower()
    
    if response == 'yes':
        run_full_initialization()
    else:
        print("\n❌ Initialization cancelled.")
        sys.exit(0)

