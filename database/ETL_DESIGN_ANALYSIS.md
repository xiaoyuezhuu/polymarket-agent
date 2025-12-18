# ETL Design Analysis for Polymarket Real-Time Syncing

## Current Design Assessment

### ✅ What Works Well

1. **Incremental Loading by Market**
   - `load_trades_from_markets()` only loads trades for markets without existing data
   - Avoids redundant API calls and duplicate processing
   - Good for initial backfill

2. **Proper Foreign Key Relationships**
   - Events → Markets → Trades hierarchy is maintained
   - Ensures data integrity

3. **Idempotent Operations**
   - Using `upsert` for events, markets, and users
   - Handles re-runs gracefully

### ⚠️ Limitations for Real-Time Syncing

1. **Binary Check (Has Trades vs No Trades)**
   - Current design: "Does this market have ANY trades?"
   - Problem: Once a market has 1 trade, it never gets updated again
   - **Missing**: Incremental updates for existing markets

2. **No Timestamp Tracking**
   - No way to know when data was last updated
   - Can't identify "stale" markets that need refreshing
   - Can't resume from last sync point

3. **Full Table Scans**
   - Queries all condition_ids from both tables
   - Inefficient as data grows (thousands of markets)

4. **No Prioritization**
   - Treats all markets equally
   - Active markets need more frequent updates than closed ones

## Recommended Design for Real-Time Syncing

### Architecture: Hybrid Batch + Streaming

```
┌─────────────────────────────────────────────────────────┐
│                   REAL-TIME SYNC SYSTEM                  │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  1. PRIORITY QUEUE (Active Markets)                      │
│     - Update every 1-5 minutes                           │
│     - Fetch only new trades (timestamp > last_sync)      │
│                                                           │
│  2. REGULAR SYNC (Recently Closed Markets)               │
│     - Update every 1-6 hours                             │
│     - Check for final trades                             │
│                                                           │
│  3. BACKFILL (Historical/New Markets)                    │
│     - Run once for new markets                           │
│     - Your current load_trades_from_markets() logic      │
│                                                           │
└─────────────────────────────────────────────────────────┘
```

### Database Schema Additions

```sql
-- Add to markets table
ALTER TABLE markets ADD COLUMN last_trade_sync_at TIMESTAMPTZ;
ALTER TABLE markets ADD COLUMN last_trade_count INTEGER DEFAULT 0;
ALTER TABLE markets ADD COLUMN sync_priority TEXT DEFAULT 'normal'; 
  -- 'high' (active), 'normal' (recent), 'low' (closed), 'archived'

-- Create index for efficient queries
CREATE INDEX idx_markets_sync_priority ON markets(sync_priority, last_trade_sync_at);
CREATE INDEX idx_trades_timestamp ON trades(timestamp);
```

### Improved ETL Functions

#### 1. **Incremental Sync for Active Markets**

```python
def sync_active_markets(max_markets: int = 100):
    """
    Sync trades for active markets incrementally.
    Only fetches trades newer than last sync.
    """
    # Get active markets ordered by staleness
    query = """
        SELECT condition_id, last_trade_sync_at, slug
        FROM markets
        WHERE active = true
        ORDER BY last_trade_sync_at ASC NULLS FIRST
        LIMIT %s
    """
    
    for market in markets:
        # Get latest trade timestamp for this market
        last_trade = get_latest_trade_timestamp(market['condition_id'])
        
        # Fetch only new trades
        new_trades = fetch_trades_since(
            condition_id=market['condition_id'],
            since_timestamp=last_trade
        )
        
        # Insert new trades
        insert_trades(new_trades)
        
        # Update sync metadata
        update_market_sync_metadata(
            condition_id=market['condition_id'],
            trade_count=len(new_trades)
        )
```

#### 2. **Smart Priority Management**

```python
def update_market_priorities():
    """
    Automatically adjust sync priorities based on market state.
    Run this periodically (e.g., every hour).
    """
    # Active markets with recent volume → high priority
    supabase.table('markets').update({
        'sync_priority': 'high'
    }).eq('active', True).gt('volume_24hr', 1000).execute()
    
    # Recently closed markets → normal priority (for 7 days)
    supabase.table('markets').update({
        'sync_priority': 'normal'
    }).eq('closed', True).gte(
        'end_date_iso', 
        (datetime.now() - timedelta(days=7)).isoformat()
    ).execute()
    
    # Old closed markets → low priority
    supabase.table('markets').update({
        'sync_priority': 'low'
    }).eq('closed', True).lt(
        'end_date_iso',
        (datetime.now() - timedelta(days=7)).isoformat()
    ).execute()
```

#### 3. **Efficient Backfill for New Markets**

```python
def backfill_new_markets():
    """
    Load historical trades for markets that have never been synced.
    This is your current logic, but with metadata tracking.
    """
    # Markets with no sync timestamp = never synced
    new_markets = supabase.table('markets')\
        .select('condition_id')\
        .is_('last_trade_sync_at', 'null')\
        .execute()
    
    for market in new_markets:
        # Full historical load (your current logic)
        load_all_trades_for_market(market['condition_id'])
        
        # Mark as synced
        update_market_sync_metadata(market['condition_id'])
```

### Recommended Sync Schedule

```python
# Cron-like scheduler
schedule = {
    'every_1_minute': sync_active_markets(max_markets=50),  # High priority
    'every_15_minutes': sync_active_markets(max_markets=200),  # All active
    'every_1_hour': sync_recently_closed_markets(),
    'every_6_hours': backfill_new_markets(),
    'every_24_hours': update_market_priorities(),
}
```

## Implementation Roadmap

### Phase 1: Add Metadata (Immediate)
- [ ] Add `last_trade_sync_at` column to markets
- [ ] Add `sync_priority` column to markets
- [ ] Create indexes

### Phase 2: Incremental Sync (Week 1)
- [ ] Implement `sync_active_markets()` with timestamp filtering
- [ ] Add helper: `get_latest_trade_timestamp(condition_id)`
- [ ] Add helper: `update_market_sync_metadata()`

### Phase 3: Priority System (Week 2)
- [ ] Implement `update_market_priorities()`
- [ ] Create separate sync functions for each priority level
- [ ] Add monitoring/logging

### Phase 4: Scheduler (Week 3)
- [ ] Set up task scheduler (APScheduler, Celery, or cron)
- [ ] Add error handling and retry logic
- [ ] Implement alerting for sync failures

### Phase 5: Optimization (Ongoing)
- [ ] Add connection pooling
- [ ] Implement batch inserts (bulk operations)
- [ ] Add caching layer for frequently accessed data
- [ ] Monitor API rate limits and adjust accordingly

## Performance Considerations

### Current Approach
- **Initial Load**: Good for one-time backfill
- **Updates**: ❌ Inefficient (full re-scan every time)
- **Scalability**: ❌ Degrades with data growth

### Recommended Approach
- **Initial Load**: Same as current (backfill)
- **Updates**: ✅ Only fetch new data since last sync
- **Scalability**: ✅ O(active_markets) instead of O(all_markets)

### API Rate Limiting
- Polymarket likely has rate limits
- Prioritization ensures you sync most important data first
- If rate-limited, high-priority markets still get updated

## Alternative: WebSocket/Streaming

For true real-time (sub-second latency), consider:

```python
# Polymarket may have a WebSocket API (check docs)
async def stream_trades():
    async with websocket.connect('wss://...') as ws:
        async for trade in ws:
            insert_trade(trade)
```

**Pros**: Instant updates, no polling
**Cons**: More complex, requires persistent connection, may not have historical data

## Conclusion

Your current design is **good for initial data loading** but **not optimal for real-time syncing**.

**Key Changes Needed**:
1. ✅ Track when each market was last synced
2. ✅ Fetch only new trades (incremental)
3. ✅ Prioritize active markets
4. ✅ Use different update frequencies for different market states

This will reduce API calls by 90%+ and keep your data fresh where it matters most.

