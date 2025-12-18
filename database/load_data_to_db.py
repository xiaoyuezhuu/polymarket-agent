"""
Load Polymarket data into Supabase database
"""

import os
import sys
from pathlib import Path
import requests
import pandas as pd
from datetime import datetime
from supabase import create_client, Client
from typing import List, Dict, Any, Optional
import time

# Load environment variables from .env file in project root
from dotenv import load_dotenv

# Import Supabase utility functions
from database.supabase_utils import retrieve_all_rows

# Get the project root directory (parent of database/)
project_root = Path(__file__).parent.parent
dotenv_path = project_root / '.env'

# Load .env file
load_dotenv(dotenv_path)

# ============================================
# Configuration
# ============================================

# Get from Supabase project settings or .env file
SUPABASE_URL = os.environ.get("SUPABASE_URL", "your-project-url.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "your-anon-key")

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ============================================
# API Functions (from your notebook)
# ============================================

def get_events(active: Optional[bool] = None, closed: Optional[bool] = None, 
               limit: int = 100, offset: int = 0) -> List[Dict]:
    """
    Fetch events from Gamma API
    Events contain nested markets (1 for SMP, multiple for GMP)
    """
    url = "https://gamma-api.polymarket.com/events"
    params = {
        "limit": limit,
        "offset": offset,
        "ascending": False
    }
    
    if active is not None:
        params["active"] = str(active).lower()
    if closed is not None:
        params["closed"] = str(closed).lower()
    
    response = requests.get(url, params=params)
    return response.json()


def get_markets(active: Optional[bool] = None, closed: Optional[bool] = None, 
                limit: int = 100, offset: int = 0) -> List[Dict]:
    """
    DEPRECATED: Fetch markets from Gamma API
    
    ⚠️  WARNING: This function is deprecated. Use get_events() instead.
    Markets should be loaded from events to maintain proper event-market relationships.
    Direct market API doesn't provide event_id, so we can't link them properly.
    """
    url = "https://gamma-api.polymarket.com/markets"
    params = {
        "limit": limit,
        "offset": offset,
        "ascending": False
    }
    
    if active is not None:
        params["active"] = str(active).lower()
    if closed is not None:
        params["closed"] = str(closed).lower()
    
    response = requests.get(url, params=params)
    return response.json()


def get_trades(user: Optional[str] = None, market: Optional[str] = None, 
               event_id: Optional[str] = None, side: Optional[str] = None,
               limit: int = 100, offset: int = 0) -> List[Dict]:
    """Fetch trades from Data API"""
    url = "https://data-api.polymarket.com/trades"
    params = {
        "limit": limit,
        "offset": offset
    }
    
    if user:
        params["user"] = user
    if market:
        params["market"] = market # market condition id
    if event_id:
        params["eventId"] = event_id
    if side:
        params["side"] = side
    
    response = requests.get(url, params=params)
    return response.json()


# ============================================
# Data Transformation Functions
# ============================================

def transform_event_data(event: Dict) -> Dict:
    """Transform event data from API to database schema"""
    # Determine event type based on market count
    markets = event.get('markets', [])
    event_type = 'SMP' if len(markets) == 1 else 'GMP' if len(markets) > 1 else None
    
    return {
        'id': event.get('id'),
        'ticker': event.get('ticker'),
        'slug': event.get('slug'),
        'title': event.get('title'),
        'description': event.get('description'),
        'event_type': event_type,
        'market_count': len(markets),
        'active': event.get('active', True),
        'closed': event.get('closed', False),
        'archived': event.get('archived', False),
        'new': event.get('new', False),
        'featured': event.get('featured', False),
        'restricted': event.get('restricted', False),
        'start_date': event.get('startDate'),
        'creation_date': event.get('creationDate'),
        'end_date': event.get('endDate'),
        'created_at': event.get('createdAt'),
        'updated_at': event.get('updatedAt'),
        'liquidity': event.get('liquidity'),
        'volume': event.get('volume'),
        'volume_24hr': event.get('volume24hr'),
        'volume_1wk': event.get('volume1wk'),
        'volume_1mo': event.get('volume1mo'),
        'volume_1yr': event.get('volume1yr'),
        'open_interest': event.get('openInterest'),
        'liquidity_clob': event.get('liquidityClob'),
        'image': event.get('image'),
        'icon': event.get('icon'),
        'enable_order_book': event.get('enableOrderBook', True),
        'competitive': event.get('competitive'),
        'comment_count': event.get('commentCount', 0),
        'cyom': event.get('cyom', False),
        'show_all_outcomes': event.get('showAllOutcomes', True),
        'show_market_images': event.get('showMarketImages', True),
        'enable_neg_risk': event.get('enableNegRisk', False),
        'automatically_active': event.get('automaticallyActive', True),
        'neg_risk_augmented': event.get('negRiskAugmented', False),
        'pending_deployment': event.get('pendingDeployment', False),
        'deploying': event.get('deploying', False),
        'tags': event.get('tags'),
        'resolution_source': event.get('resolutionSource'),
    }


def transform_market_data(market: Dict, event_id: str = None) -> Dict:
    """Transform market data from API to database schema"""
    return {
        'id': market.get('id'),
        'event_id': event_id,  # Link to parent event
        'condition_id': market.get('conditionId') or market.get('condition_id'),
        'question': market.get('question'),
        'slug': market.get('slug'),
        'description': market.get('description'),
        'outcomes': market.get('outcomes'),
        'outcome_prices': market.get('outcomePrices'),
        'clob_token_ids': market.get('clobTokenIds'),
        'active': market.get('active', True),
        'closed': market.get('closed', False),
        'archived': market.get('archived', False),
        'funded': market.get('funded', False),
        'ready': market.get('ready', False),
        'restricted': market.get('restricted', False),
        'start_date_iso': market.get('startDateIso') or market.get('startDate'),
        'end_date_iso': market.get('endDateIso') or market.get('endDate'),
        'created_at': market.get('createdAt'),
        'updated_at': market.get('updatedAt'),
        'accepting_orders_timestamp': market.get('acceptingOrdersTimestamp'),
        'enable_order_book': market.get('enableOrderBook', True),
        'order_price_min_tick_size': market.get('orderPriceMinTickSize'),
        'order_min_size': market.get('orderMinSize'),
        'accepting_orders': market.get('acceptingOrders', True),
        'neg_risk': market.get('negRisk', False),
        'volume_num': market.get('volumeNum') or market.get('volume'),
        'liquidity_num': market.get('liquidityNum') or market.get('liquidity'),
        'volume_24hr': market.get('volume24hr'),
        'volume_1wk': market.get('volume1wk'),
        'volume_1mo': market.get('volume1mo'),
        'volume_1yr': market.get('volume1yr'),
        'volume_clob': market.get('volumeClob'),
        'volume_24hr_clob': market.get('volume24hrClob'),
        'volume_1wk_clob': market.get('volume1wkClob'),
        'volume_1mo_clob': market.get('volume1moClob'),
        'volume_1yr_clob': market.get('volume1yrClob'),
        'liquidity_clob': market.get('liquidityClob'),
        'spread': market.get('spread'),
        'one_day_price_change': market.get('oneDayPriceChange'),
        'one_week_price_change': market.get('oneWeekPriceChange'),
        'one_month_price_change': market.get('oneMonthPriceChange'),
        'last_trade_price': market.get('lastTradePrice'),
        'best_bid': market.get('bestBid'),
        'best_ask': market.get('bestAsk'),
        'resolution_source': market.get('resolutionSource'),
        'resolved_by': market.get('resolvedBy'),
        'uma_bond': market.get('umaBond'),
        'uma_reward': market.get('umaReward'),
        'uma_resolution_statuses': market.get('umaResolutionStatuses'),
        'image': market.get('image'),
        'icon': market.get('icon'),
        'events': market.get('events'),
        'group_item_title': market.get('groupItemTitle'),
        'group_item_threshold': market.get('groupItemThreshold'),
        'series_color': market.get('seriesColor'),
        'new': market.get('new', False),
        'featured': market.get('featured', False),
        'competitive': market.get('competitive', False),
        'cyom': market.get('cyom', False),
        'rfq_enabled': market.get('rfqEnabled', False),
        'holding_rewards_enabled': market.get('holdingRewardsEnabled', False),
        'fees_enabled': market.get('feesEnabled', False),
        'show_gmp_series': market.get('showGmpSeries', False),
        'show_gmp_outcome': market.get('showGmpOutcome', False),
        'submitted_by': market.get('submitted_by'),
        'approved': market.get('approved', False),
        'pager_duty_notification_enabled': market.get('pagerDutyNotificationEnabled', False),
        'pending_deployment': market.get('pendingDeployment', False),
        'deploying': market.get('deploying', False),
        'market_maker_address': market.get('marketMakerAddress'),
        'rewards_min_size': market.get('rewardsMinSize'),
        'rewards_max_spread': market.get('rewardsMaxSpread'),
    }


def transform_trade_data(trade: Dict) -> Dict:
    """Transform trade data from API to database schema"""
    timestamp = trade.get('timestamp')
    datetime_val = pd.to_datetime(timestamp, unit='s') if timestamp else None
    
    return {
        'transaction_hash': trade.get('transactionHash'),
        'proxy_wallet': trade.get('proxyWallet'),
        'condition_id': trade.get('conditionId'),
        'slug': trade.get('slug'),
        'side': trade.get('side'),
        'asset': trade.get('asset'),
        'outcome': trade.get('outcome'),
        'outcome_index': trade.get('outcomeIndex'),
        'size': trade.get('size'),
        'price': trade.get('price'),
        'timestamp': timestamp,
        'datetime': datetime_val.isoformat() if datetime_val else None,
        'title': trade.get('title'),
        'icon': trade.get('icon'),
        'event_slug': trade.get('eventSlug'),
    }


def transform_user_data(trade: Dict) -> Dict:
    """Extract user data from trade"""
    return {
        'proxy_wallet': trade.get('proxyWallet'),
        'name': trade.get('name'),
        'pseudonym': trade.get('pseudonym'),
        'bio': trade.get('bio'),
        'profile_image': trade.get('profileImage'),
        'profile_image_optimized': trade.get('profileImageOptimized'),
    }


# ============================================
# Database Loading Functions
# ============================================

def upsert_events(events: List[Dict]) -> int:
    """Insert or update events in database"""
    count = 0
    for event in events:
        try:
            transformed = transform_event_data(event)
            # Remove None values to avoid overwriting with nulls
            transformed = {k: v for k, v in transformed.items() if v is not None}
            
            result = supabase.table('events').upsert(
                transformed,
                on_conflict='slug'
            ).execute()
            count += 1
        except Exception as e:
            print(f"Error upserting event {event.get('slug')}: {e}")
    
    return count


def upsert_markets(markets: List[Dict], event_id: str = None) -> int:
    """
    DEPRECATED: Insert or update markets in database
    
    ⚠️  WARNING: This function is deprecated.
    Markets should be loaded via load_events_with_markets() to maintain event-market relationships.
    """
    count = 0
    for market in markets:
        try:
            transformed = transform_market_data(market, event_id=event_id)
            # Remove None values to avoid overwriting with nulls
            transformed = {k: v for k, v in transformed.items() if v is not None}
            
            result = supabase.table('markets').upsert(
                transformed,
                on_conflict='slug'
            ).execute()
            count += 1
        except Exception as e:
            print(f"Error upserting market {market.get('slug')}: {e}")
    
    return count


def upsert_users(users_data: List[Dict]) -> int:
    """Insert or update users in database"""
    count = 0
    for user_data in users_data:
        try:
            # Remove None values
            user_data = {k: v for k, v in user_data.items() if v is not None}
            
            if not user_data.get('proxy_wallet'):
                continue
                
            result = supabase.table('users').upsert(
                user_data,
                on_conflict='proxy_wallet'
            ).execute()
            count += 1
        except Exception as e:
            print(f"Error upserting user {user_data.get('proxy_wallet')}: {e}")
    
    return count


def insert_trades(trades: List[Dict]) -> int:
    """Insert trades into database"""
    count = 0
    for trade in trades:
        try:
            transformed = transform_trade_data(trade)
            # Remove None values
            transformed = {k: v for k, v in transformed.items() if v is not None}
            
            # Skip if missing required fields
            if not all([transformed.get('proxy_wallet'), 
                       transformed.get('side'),
                       transformed.get('size'),
                       transformed.get('price'),
                       transformed.get('timestamp')]):
                continue
            
            result = supabase.table('trades').insert(transformed).execute()
            count += 1
        except Exception as e:
            # Skip duplicate transaction hashes
            if 'duplicate' in str(e).lower():
                continue
            print(f"Error inserting trade: {e}")
    
    return count


def take_market_snapshot(market: Dict) -> bool:
    """Take a snapshot of current market state"""
    try:
        snapshot = {
            'condition_id': market.get('conditionId') or market.get('condition_id'),
            'slug': market.get('slug'),
            'snapshot_at': datetime.utcnow().isoformat(),
            'outcome_prices': market.get('outcomePrices'),
            'best_bid': market.get('bestBid'),
            'best_ask': market.get('bestAsk'),
            'spread': market.get('spread'),
            'last_trade_price': market.get('lastTradePrice'),
            'volume_total': market.get('volumeNum') or market.get('volume'),
            'volume_24hr': market.get('volume24hr'),
            'liquidity': market.get('liquidityNum') or market.get('liquidity'),
        }
        
        # Remove None values
        snapshot = {k: v for k, v in snapshot.items() if v is not None}
        
        result = supabase.table('market_snapshots').insert(snapshot).execute()
        return True
    except Exception as e:
        print(f"Error taking snapshot for {market.get('slug')}: {e}")
        return False


# ============================================
# Main ETL Functions
# ============================================

def load_events_with_markets(limit: int = 1000, active_only: bool = False):
    """
    Load events from API with their nested markets.
    This is the ONLY way to load data - it preserves event-market relationships.
    
    Process:
    1. Fetch events from Gamma API (events contain nested markets)
    2. Store events in events table
    3. Extract nested markets from each event
    4. Add parent event_id to each market
    5. Store markets in markets table with event_id link
    """
    print(f"Fetching events from API (limit={limit}, active_only={active_only})...")
    
    events = get_events(active=active_only if active_only else None, limit=limit)
    print(f"✓ Fetched {len(events)} events")
    
    # Step 1: Upsert events to database
    print("\nStep 1: Storing events...")
    event_count = upsert_events(events)
    print(f"✓ Upserted {event_count} events")
    
    # Step 2: Extract and process markets from nested data
    print("\nStep 2: Processing nested markets...")
    market_count = 0
    
    for event in events:
        event_id = event.get('id')
        markets = event.get('markets', [])
        
        if not markets:
            print(f"  ⚠️  Event {event.get('slug')} has no markets")
            continue
        
        # Process each nested market
        for market in markets:
            try:
                # Transform market data and inject event_id
                transformed = transform_market_data(market, event_id=event_id)
                
                # Remove None values
                transformed = {k: v for k, v in transformed.items() if v is not None}
                
                # Ensure event_id is present (required foreign key)
                if not transformed.get('event_id'):
                    print(f"  ⚠️  Market {market.get('slug')} missing event_id, skipping...")
                    continue
                
                # Upsert to database
                result = supabase.table('markets').upsert(
                    transformed,
                    on_conflict='slug'
                ).execute()
                
                market_count += 1
                
            except Exception as e:
                print(f"  ✗ Error upserting market {market.get('slug')}: {e}")
    
    print(f"✓ Upserted {market_count} markets")
    
    # Summary
    print(f"\n{'='*60}")
    print(f"Summary:")
    print(f"  Events: {event_count}")
    print(f"  Markets: {market_count}")
    print(f"  Avg markets per event: {market_count/event_count:.2f}" if event_count > 0 else "  Avg: N/A")
    print(f"{'='*60}")
    
    return event_count, market_count


def load_trades(limit: int = 10000, market_condition_id: Optional[str] = None):
    """Load trades from API to database"""
    print(f"Fetching trades (limit={limit})...")
    
    # Fetch trades in batches
    all_trades = []
    batch_size = 100  # API max per request
    offset = 0
    
    while offset < limit:
        batch_limit = min(batch_size, limit - offset)
        trades_batch = get_trades(
            market=market_condition_id,
            limit=batch_limit, 
            offset=offset
        )
        
        if not trades_batch:
            break
            
        all_trades.extend(trades_batch)
        print(f"Fetched {len(all_trades)} trades so far...")
        offset += batch_limit
        
        # Rate limiting
        time.sleep(0.5)
    
    print(f"Total trades fetched: {len(all_trades)}")
    
    # Extract and upsert users first
    print("Extracting user data...")
    users = [transform_user_data(trade) for trade in all_trades]
    unique_users = {u['proxy_wallet']: u for u in users if u.get('proxy_wallet')}
    print(f"Found {len(unique_users)} unique users")
    
    print("Upserting users...")
    user_count = upsert_users(list(unique_users.values()))
    print(f"Upserted {user_count} users")
    
    # Insert trades
    print("Inserting trades...")
    trade_count = insert_trades(all_trades)
    print(f"Inserted {trade_count} trades")
    
    return trade_count


def take_snapshots_for_active_markets():
    """Take snapshots of all active markets from active events"""
    print("Fetching active events with markets...")
    events = get_events(active=True, limit=1000)
    print(f"Found {len(events)} active events")
    
    count = 0
    total_markets = 0
    
    for event in events:
        markets = event.get('markets', [])
        total_markets += len(markets)
        
        for market in markets:
            if take_market_snapshot(market):
                count += 1
    
    print(f"Processed {total_markets} markets from {len(events)} events")
    print(f"Took {count} market snapshots")
    return count



    """
    Load trades for markets that don't have any trades yet in the database.
    
    This function:
    1. Identifies condition_ids in markets table that have no corresponding trades
    2. Fetches all trades for each missing market
    3. Inserts trades and upserts associated users
    
    Args:
        batch_size: Number of trades to fetch per API call (max 100)
        rate_limit_delay: Delay in seconds between API calls
    
    Returns:
        tuple: (markets_processed, users_added, trades_added)
    """
    print("=" * 70)
    print("Loading trades for markets without trade data...")
    print("=" * 70)
    
    # Step 1: Get all condition_ids from markets (using helper to bypass 1000 row limit)
    print("\n→ Fetching all condition_ids from markets table...")
    try:
        markets_rows = retrieve_all_rows(
            supabase,
            'markets',
            columns='condition_id'
        )
        all_condition_ids = set(
            row['condition_id'] for row in markets_rows 
            if row.get('condition_id')
        )
        print(f"✓ Found {len(all_condition_ids)} markets with condition_ids")
    except Exception as e:
        print(f"✗ Error fetching markets: {e}")
        return 0, 0, 0
    
    # Step 2: Get condition_ids that already have trades (using helper)
    print("\n→ Checking which markets already have trades...")
    try:
        trades_rows = retrieve_all_rows(
            supabase,
            'trades',
            columns='condition_id'
        )
        existing_condition_ids = set(
            row['condition_id'] for row in trades_rows 
            if row.get('condition_id')
        )
        print(f"✓ Found {len(existing_condition_ids)} markets with existing trades")
    except Exception as e:
        print(f"✗ Error fetching existing trades: {e}")
        return 0, 0, 0
    
    # Step 3: Find markets without trades
    missing_condition_ids = list(all_condition_ids - existing_condition_ids)
    print(f"\n📊 {len(missing_condition_ids)} markets need trade data loaded")
    
    if not missing_condition_ids:
        print("✓ All markets already have trades!")
        return 0, 0, 0
    
    # Step 4: Load trades for each missing market
    total_trades_added = 0
    markets_processed = 0
    all_users = {}
    
    for idx, condition_id in enumerate(missing_condition_ids, 1):
        print(f"\n📈 Market {idx}/{len(missing_condition_ids)}: {condition_id[:16]}...")
        print("-" * 70)
        
        offset = 0
        market_trades = 0
        batch_num = 1
        
        # Paginate through all trades for this market
        while True:
            try:
                # Fetch trades batch
                trades_batch = get_trades(
                    market=condition_id,
                    limit=batch_size,
                    offset=offset
                )
                
                # No more trades for this market
                if not trades_batch or len(trades_batch) == 0:
                    break
                
                print(f"  → Batch {batch_num}: {len(trades_batch)} trades fetched")
                
                # Collect user data
                for trade in trades_batch:
                    user_data = transform_user_data(trade)
                    wallet = user_data.get('proxy_wallet')
                    if wallet:
                        all_users[wallet] = user_data
                
                # Insert trades
                batch_count = 0
                for trade in trades_batch:
                    try:
                        transformed = transform_trade_data(trade)
                        transformed = {k: v for k, v in transformed.items() if v is not None}
                        
                        # Skip if missing required fields
                        if not all([
                            transformed.get('proxy_wallet'),
                            transformed.get('side'),
                            transformed.get('size'),
                            transformed.get('price'),
                            transformed.get('timestamp')
                        ]):
                            continue
                        
                        supabase.table('trades').insert(transformed).execute()
                        batch_count += 1
                        
                    except Exception as e:
                        # Skip duplicates
                        if 'duplicate' in str(e).lower():
                            continue
                
                market_trades += batch_count
                total_trades_added += batch_count
                print(f"  ✓ Inserted {batch_count} trades (market total: {market_trades})")
                
                # Move to next batch
                offset += batch_size
                batch_num += 1
                
                # If fewer than batch_size, we're done
                if len(trades_batch) < batch_size:
                    break
                
                # Rate limiting
                time.sleep(rate_limit_delay)
                
            except Exception as e:
                print(f"  ⚠️  Error: {e}")
                break
        
        markets_processed += 1
        print(f"  ✓ Market complete: {market_trades} trades")
        
        # Periodic rate limiting
        if idx % 10 == 0:
            print(f"  ⏳ Rate limiting (3s)...")
            time.sleep(3)
    
    # Step 5: Upsert all collected users
    print("\n" + "-" * 70)
    print("Upserting collected users...")
    users_added = upsert_users(list(all_users.values()))
    print(f"✓ Upserted {users_added} users")
    
    # Summary
    print("\n" + "=" * 70)
    print("TRADES LOADING COMPLETE")
    print("=" * 70)
    print(f"  Markets Processed:   {markets_processed:,}")
    print(f"  Users Added:         {users_added:,}")
    print(f"  Trades Added:        {total_trades_added:,}")
    if markets_processed > 0:
        print(f"  Avg Trades/Market:   {total_trades_added/markets_processed:.2f}")
    print("=" * 70)
    
    return markets_processed, users_added, total_trades_add

def update_all_user_metrics():
    """Update calculated metrics for all users"""
    print("Updating user metrics...")
    try:
        result = supabase.rpc('update_user_metrics').execute()
        print("User metrics updated successfully")
        return True
    except Exception as e:
        print(f"Error updating user metrics: {e}")
        return False


# ============================================
# Main Script
# ============================================

if __name__ == "__main__":
    print("=" * 60)
    print("Polymarket Data Loader")
    print("=" * 60)
    
    # Check configuration
    if SUPABASE_URL == "your-project-url.supabase.co":
        print("\n⚠️  Please set SUPABASE_URL and SUPABASE_KEY environment variables!")
        exit(1)
    
    print(f"\n✓ Connected to Supabase: {SUPABASE_URL}")
    
    print("\n" + "=" * 60)
    print("STEP 1: Loading Events with Nested Markets")
    print("=" * 60)
    event_count, market_count = load_events_with_markets(limit=1000, active_only=False)
    
    print("\n" + "=" * 60)
    print("STEP 2: Loading Recent Trades")
    print("=" * 60)
    trade_count = load_trades(limit=5000)
    
    print("\n" + "=" * 60)
    print("STEP 3: Taking Market Snapshots")
    print("=" * 60)
    snapshot_count = take_snapshots_for_active_markets()
    
    print("\n" + "=" * 60)
    print("STEP 4: Updating User Metrics")
    print("=" * 60)
    update_all_user_metrics()
    
    print("\n" + "=" * 60)
    print("✅ DATA LOADING COMPLETE!")
    print("=" * 60)
    print(f"  Events:    {event_count}")
    print(f"  Markets:   {market_count}")
    print(f"  Trades:    {trade_count}")
    print(f"  Snapshots: {snapshot_count}")
    print("=" * 60)

