"""
Load Polymarket data into Supabase database
"""

import os
import requests
import pandas as pd
from datetime import datetime
from supabase import create_client, Client
from typing import List, Dict, Any, Optional
import time

# ============================================
# Configuration
# ============================================

# Get from Supabase project settings
SUPABASE_URL = os.environ.get("SUPABASE_URL", "your-project-url.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "your-anon-key")

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ============================================
# API Functions (from your notebook)
# ============================================

def get_markets(active: Optional[bool] = None, closed: Optional[bool] = None, 
                limit: int = 100, offset: int = 0) -> List[Dict]:
    """Fetch markets from Gamma API"""
    url = "https://gamma-api.polymarket.com/markets"
    params = {
        "limit": limit,
        "offset": offset
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
        params["market"] = market
    if event_id:
        params["eventId"] = event_id
    if side:
        params["side"] = side
    
    response = requests.get(url, params=params)
    return response.json()


# ============================================
# Data Transformation Functions
# ============================================

def transform_market_data(market: Dict) -> Dict:
    """Transform market data from API to database schema"""
    return {
        'id': market.get('id'),
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

def upsert_markets(markets: List[Dict]) -> int:
    """Insert or update markets in database"""
    count = 0
    for market in markets:
        try:
            transformed = transform_market_data(market)
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

def load_markets(limit: int = 1000, active_only: bool = False):
    """Load markets from API to database"""
    print(f"Fetching markets (limit={limit}, active_only={active_only})...")
    
    markets = get_markets(active=active_only if active_only else None, limit=limit)
    print(f"Fetched {len(markets)} markets")
    
    print("Upserting markets to database...")
    count = upsert_markets(markets)
    print(f"Upserted {count} markets")
    
    return count


def load_trades(limit: int = 10000, market_slug: Optional[str] = None):
    """Load trades from API to database"""
    print(f"Fetching trades (limit={limit})...")
    
    # Fetch trades in batches
    all_trades = []
    batch_size = 100  # API max per request
    offset = 0
    
    while offset < limit:
        batch_limit = min(batch_size, limit - offset)
        trades_batch = get_trades(
            market=market_slug,
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
    """Take snapshots of all active markets"""
    print("Fetching active markets...")
    markets = get_markets(active=True, limit=1000)
    print(f"Found {len(markets)} active markets")
    
    count = 0
    for market in markets:
        if take_market_snapshot(market):
            count += 1
    
    print(f"Took {count} market snapshots")
    return count


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
        print("   export SUPABASE_URL='your-url'")
        print("   export SUPABASE_KEY='your-key'")
        exit(1)
    
    print("\n1. Loading markets...")
    load_markets(limit=1000, active_only=False)
    
    print("\n2. Loading recent trades...")
    load_trades(limit=5000)
    
    print("\n3. Taking market snapshots...")
    take_snapshots_for_active_markets()
    
    print("\n4. Updating user metrics...")
    update_all_user_metrics()
    
    print("\n" + "=" * 60)
    print("Data loading complete!")
    print("=" * 60)

