# Polymarket Trading Agent Database Design

## Overview

This database schema is designed to support an AI trading agent that learns from successful Polymarket traders and identifies profitable trading patterns.

## Database Visualization

You can visualize this schema using:
- **dbdiagram.io**: Paste the contents of `database_design.dbml` into [dbdiagram.io](https://dbdiagram.io/)
- **VSCode Extension**: Install "DBML Viewer" extension

## Core Tables

### 1. **markets**
Stores all market metadata, pricing, and volume information.

**Key Features:**
- Comprehensive market data including volumes, liquidity, and price tracking
- Time-series volume data (24hr, 1wk, 1mo, 1yr) for trend analysis
- Price change tracking (1 day, 1 week, 1 month)
- Resolution and UMA data for understanding market outcomes

**Indexes optimized for:**
- Finding active/closed markets quickly
- Querying by volume for high-activity markets
- Time-based queries for recent markets

### 2. **users**
Stores trader profiles with calculated performance metrics.

**Key Features:**
- **Trading Statistics**: Total trades, volume, P&L
- **Performance Metrics**: Win rate, ROI, Sharpe ratio, max drawdown
- **Behavior Patterns**: Preferred markets, risk score, trading frequency
- **Time-based Performance**: 7d, 30d, 90d P&L and volume
- **Success Indicators**: Flags for profitable/successful traders

**Critical for AI Training:**
- `is_successful_trader`: Boolean flag to identify users to learn from
- `trading_patterns`: JSON field for behavioral patterns
- Performance metrics to weight user influence on AI decisions

**Suggested Success Criteria:**
```sql
-- Update successful trader flag
UPDATE users 
SET is_successful_trader = true 
WHERE win_rate > 55 
  AND total_trades > 50
  AND roi_percentage > 10
  AND total_pnl > 1000;
```

### 3. **trades**
Individual trade records linked to users and markets.

**Key Features:**
- Complete trade details (side, size, price, outcome)
- Links to both users (proxy_wallet) and markets (slug, condition_id)
- Calculated trade value in USD
- Blockchain transaction hash for verification

**Indexes optimized for:**
- User trade history queries
- Market-specific trade analysis
- Time-based pattern recognition
- Fast lookups by transaction hash

### 4. **user_positions**
Aggregated position data derived from trades.

**Key Features:**
- Current and historical positions
- Realized and unrealized P&L tracking
- Position lifecycle (opened, updated, closed)
- Average entry price calculation

**Use Cases:**
- Calculate open positions for each user
- Track position performance over time
- Identify winning/losing positions
- Pattern analysis: entry/exit timing

### 5. **market_snapshots**
Time-series data for market prices and activity.

**Key Features:**
- Regular snapshots of market state
- Price evolution tracking
- Volume and liquidity trends
- Trader activity metrics

**Suggested Snapshot Frequency:**
- Every 1 hour for active markets
- Every 24 hours for low-activity markets

**Use Cases:**
- Price trend analysis
- Volatility calculation
- Optimal entry/exit timing
- Market momentum indicators

### 6. **trading_patterns**
Identified patterns from successful traders.

**Pattern Types:**
- `early_entry`: Entering positions before price movement
- `contrarian`: Betting against market consensus
- `momentum`: Following price trends
- `mean_reversion`: Betting on price corrections
- `volatility_timing`: Entering during high volatility

**Use Cases:**
- AI feature engineering
- Pattern-based trade signals
- Success rate analysis by pattern type

## Key Relationships

```
users (proxy_wallet) <── trades (proxy_wallet)
                      └─ user_positions (proxy_wallet)
                      └─ trading_patterns (proxy_wallet)

markets (slug) <── trades (slug)
               └─ user_positions (slug)
               └─ market_snapshots (slug)

markets (condition_id) <── market_snapshots (condition_id)
```

## Data Pipeline Strategy

### 1. Initial Load
```python
# Load markets
markets_df → INSERT INTO markets

# Load trades
trades_df → INSERT INTO trades
         → Trigger: Update user statistics
         → Trigger: Update user_positions
```

### 2. Ongoing Updates
```python
# Hourly: Update active markets
fetch_markets(active=True) → UPDATE markets

# Every 15 minutes: Fetch new trades
fetch_recent_trades() → INSERT INTO trades

# Hourly: Take market snapshots
for market in active_markets:
    INSERT INTO market_snapshots

# Daily: Calculate user metrics
UPDATE users SET 
  win_rate = calculate_win_rate(),
  roi_percentage = calculate_roi(),
  ...
```

### 3. Pattern Recognition
```python
# Daily: Identify patterns
for user in successful_users:
    patterns = analyze_trading_patterns(user)
    INSERT INTO trading_patterns
```

## Recommended PostgreSQL/Supabase Configuration

### Materialized Views

```sql
-- Top performing traders (refresh daily)
CREATE MATERIALIZED VIEW top_traders AS
SELECT 
  proxy_wallet,
  name,
  win_rate,
  roi_percentage,
  total_pnl,
  total_trades
FROM users
WHERE is_successful_trader = true
ORDER BY roi_percentage DESC;

-- Market momentum (refresh hourly)
CREATE MATERIALIZED VIEW market_momentum AS
SELECT 
  m.slug,
  m.question,
  m.volume_24hr,
  m.one_day_price_change,
  COUNT(t.id) as trade_count_24hr
FROM markets m
LEFT JOIN trades t ON m.slug = t.slug 
  AND t.datetime > NOW() - INTERVAL '24 hours'
GROUP BY m.slug, m.question, m.volume_24hr, m.one_day_price_change;
```

### Useful Indexes

```sql
-- For finding successful trader patterns
CREATE INDEX idx_users_success_metrics 
ON users(is_successful_trader, win_rate, roi_percentage) 
WHERE is_successful_trader = true;

-- For time-series analysis
CREATE INDEX idx_trades_datetime_wallet 
ON trades(datetime DESC, proxy_wallet);

-- For market trend analysis
CREATE INDEX idx_snapshots_market_recent 
ON market_snapshots(condition_id, snapshot_at DESC);
```

### Database Functions

```sql
-- Calculate user win rate
CREATE OR REPLACE FUNCTION calculate_user_win_rate(wallet_address VARCHAR)
RETURNS DECIMAL AS $$
  SELECT 
    (COUNT(*) FILTER (WHERE up.realized_pnl > 0)::DECIMAL / 
     NULLIF(COUNT(*), 0)) * 100
  FROM user_positions up
  WHERE up.proxy_wallet = wallet_address 
    AND up.is_open = false;
$$ LANGUAGE SQL;

-- Get user ROI
CREATE OR REPLACE FUNCTION calculate_user_roi(wallet_address VARCHAR)
RETURNS DECIMAL AS $$
  SELECT 
    (SUM(realized_pnl) / NULLIF(SUM(total_invested), 0)) * 100
  FROM user_positions
  WHERE proxy_wallet = wallet_address;
$$ LANGUAGE SQL;
```

### Triggers

```sql
-- Auto-update user statistics on new trade
CREATE OR REPLACE FUNCTION update_user_stats()
RETURNS TRIGGER AS $$
BEGIN
  UPDATE users 
  SET 
    total_trades = total_trades + 1,
    last_trade_at = NEW.datetime,
    updated_at = NOW()
  WHERE proxy_wallet = NEW.proxy_wallet;
  
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_user_stats
AFTER INSERT ON trades
FOR EACH ROW
EXECUTE FUNCTION update_user_stats();
```

## AI Training Data Queries

### 1. Get Successful Trader Patterns
```sql
SELECT 
  u.proxy_wallet,
  u.win_rate,
  u.roi_percentage,
  t.slug,
  t.side,
  t.price,
  t.size,
  t.datetime,
  m.volume_24hr,
  m.spread,
  m.one_day_price_change
FROM trades t
JOIN users u ON t.proxy_wallet = u.proxy_wallet
JOIN markets m ON t.slug = m.slug
WHERE u.is_successful_trader = true
  AND u.total_trades > 100
ORDER BY u.roi_percentage DESC, t.datetime;
```

### 2. Identify Early Entry Winners
```sql
WITH market_first_trades AS (
  SELECT 
    slug,
    MIN(datetime) as first_trade_time
  FROM trades
  GROUP BY slug
)
SELECT 
  t.*,
  up.realized_pnl,
  EXTRACT(EPOCH FROM (t.datetime - mft.first_trade_time)) / 3600 as hours_after_market_start
FROM trades t
JOIN market_first_trades mft ON t.slug = mft.slug
JOIN user_positions up ON t.proxy_wallet = up.proxy_wallet 
  AND t.slug = up.slug
WHERE up.realized_pnl > 0
  AND up.is_open = false
ORDER BY hours_after_market_start;
```

### 3. Contrarian Success Analysis
```sql
-- Find traders who bet against the crowd and won
WITH market_consensus AS (
  SELECT 
    slug,
    outcome,
    COUNT(*) as trade_count
  FROM trades
  WHERE datetime > NOW() - INTERVAL '7 days'
  GROUP BY slug, outcome
)
SELECT 
  t.proxy_wallet,
  t.slug,
  t.outcome,
  up.realized_pnl,
  mc.trade_count
FROM trades t
JOIN user_positions up ON t.proxy_wallet = up.proxy_wallet 
  AND t.slug = up.slug
JOIN market_consensus mc ON t.slug = mc.slug 
  AND t.outcome != (
    SELECT outcome 
    FROM market_consensus 
    WHERE slug = t.slug 
    ORDER BY trade_count DESC 
    LIMIT 1
  )
WHERE up.realized_pnl > 0
  AND up.is_open = false;
```

## Next Steps

1. **Deploy to Supabase:**
   - Convert DBML to SQL (use dbdiagram.io export or manual conversion)
   - Run migration scripts in Supabase SQL editor
   - Set up row-level security policies if needed

2. **Create ETL Pipeline:**
   - Script to fetch data from Polymarket API
   - Transform and load into database
   - Schedule with cron or Supabase functions

3. **Implement Calculations:**
   - User metrics calculation scripts
   - Pattern recognition algorithms
   - Position tracking logic

4. **Build AI Training Pipeline:**
   - Feature engineering from database
   - Model training on successful patterns
   - Prediction storage and validation

5. **Create Monitoring Dashboard:**
   - Track data freshness
   - Monitor successful trader metrics
   - Visualize market trends

## Performance Considerations

- **Partitioning**: Consider partitioning `trades` and `market_snapshots` by date for better query performance
- **Archiving**: Move old closed market data to archive tables
- **Caching**: Use materialized views for expensive aggregate queries
- **Batch Updates**: Update user metrics in batches rather than real-time
- **Connection Pooling**: Use pgBouncer for connection management

## Security Recommendations

- Enable Row Level Security (RLS) in Supabase
- Create read-only users for AI model queries
- Encrypt sensitive user data
- Audit log for data modifications
- Rate limit API access to database

