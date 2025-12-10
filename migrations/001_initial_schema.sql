-- Polymarket Trading Agent - Initial Schema Migration
-- Run this in Supabase SQL Editor

-- ============================================
-- EXTENSIONS
-- ============================================
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================
-- MARKETS TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS markets (
  id VARCHAR(255) PRIMARY KEY,
  condition_id VARCHAR(66) NOT NULL UNIQUE,
  question TEXT NOT NULL,
  slug VARCHAR(255) UNIQUE NOT NULL,
  description TEXT,
  
  -- Outcome information
  outcomes JSONB,
  outcome_prices JSONB,
  clob_token_ids JSONB,
  
  -- Status and lifecycle
  active BOOLEAN DEFAULT true,
  closed BOOLEAN DEFAULT false,
  archived BOOLEAN DEFAULT false,
  funded BOOLEAN DEFAULT false,
  ready BOOLEAN DEFAULT false,
  restricted BOOLEAN DEFAULT false,
  
  -- Dates
  start_date_iso TIMESTAMP,
  end_date_iso TIMESTAMP,
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
  accepting_orders_timestamp TIMESTAMP,
  
  -- Trading configuration
  enable_order_book BOOLEAN DEFAULT true,
  order_price_min_tick_size DECIMAL(18, 8),
  order_min_size DECIMAL(18, 8),
  accepting_orders BOOLEAN DEFAULT true,
  neg_risk BOOLEAN DEFAULT false,
  
  -- Volume and liquidity metrics
  volume_num DECIMAL(18, 2),
  liquidity_num DECIMAL(18, 2),
  volume_24hr DECIMAL(18, 2),
  volume_1wk DECIMAL(18, 2),
  volume_1mo DECIMAL(18, 2),
  volume_1yr DECIMAL(18, 2),
  
  -- CLOB-specific volumes
  volume_clob DECIMAL(18, 2),
  volume_24hr_clob DECIMAL(18, 2),
  volume_1wk_clob DECIMAL(18, 2),
  volume_1mo_clob DECIMAL(18, 2),
  volume_1yr_clob DECIMAL(18, 2),
  liquidity_clob DECIMAL(18, 2),
  
  -- Price tracking
  spread DECIMAL(18, 8),
  one_day_price_change DECIMAL(18, 8),
  one_week_price_change DECIMAL(18, 8),
  one_month_price_change DECIMAL(18, 8),
  last_trade_price DECIMAL(18, 8),
  best_bid DECIMAL(18, 8),
  best_ask DECIMAL(18, 8),
  
  -- Resolution information
  resolution_source TEXT,
  resolved_by VARCHAR(42),
  uma_bond DECIMAL(18, 2),
  uma_reward DECIMAL(18, 2),
  uma_resolution_statuses JSONB,
  
  -- Media and presentation
  image TEXT,
  icon TEXT,
  
  -- Categorization
  events JSONB,
  group_item_title VARCHAR(255),
  group_item_threshold DECIMAL(18, 8),
  series_color VARCHAR(50),
  
  -- Feature flags
  new BOOLEAN DEFAULT false,
  featured BOOLEAN DEFAULT false,
  competitive BOOLEAN DEFAULT false,
  cyom BOOLEAN DEFAULT false,
  rfq_enabled BOOLEAN DEFAULT false,
  holding_rewards_enabled BOOLEAN DEFAULT false,
  fees_enabled BOOLEAN DEFAULT false,
  show_gmp_series BOOLEAN DEFAULT false,
  show_gmp_outcome BOOLEAN DEFAULT false,
  
  -- Administrative
  submitted_by VARCHAR(255),
  approved BOOLEAN DEFAULT false,
  pager_duty_notification_enabled BOOLEAN DEFAULT false,
  pending_deployment BOOLEAN DEFAULT false,
  deploying BOOLEAN DEFAULT false,
  
  -- Trading parameters
  market_maker_address VARCHAR(42),
  rewards_min_size DECIMAL(18, 8),
  rewards_max_spread DECIMAL(18, 8)
);

-- Markets indexes
CREATE INDEX idx_markets_condition_id ON markets(condition_id);
CREATE INDEX idx_markets_slug ON markets(slug);
CREATE INDEX idx_markets_status ON markets(active, closed);
CREATE INDEX idx_markets_end_date ON markets(end_date_iso);
CREATE INDEX idx_markets_created_at ON markets(created_at DESC);
CREATE INDEX idx_markets_volume ON markets(volume_num DESC);

COMMENT ON TABLE markets IS 'Core markets table storing all market metadata and real-time pricing';

-- ============================================
-- USERS TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS users (
  proxy_wallet VARCHAR(42) PRIMARY KEY,
  name VARCHAR(255),
  pseudonym VARCHAR(255),
  bio TEXT,
  profile_image TEXT,
  profile_image_optimized TEXT,
  
  -- Trading statistics
  total_trades INTEGER DEFAULT 0,
  total_volume DECIMAL(18, 2) DEFAULT 0,
  total_pnl DECIMAL(18, 2) DEFAULT 0,
  win_rate DECIMAL(5, 2),
  avg_trade_size DECIMAL(18, 2),
  avg_holding_period INTERVAL,
  
  -- Performance metrics
  sharpe_ratio DECIMAL(10, 4),
  roi_percentage DECIMAL(10, 2),
  max_drawdown DECIMAL(10, 2),
  consecutive_wins INTEGER DEFAULT 0,
  consecutive_losses INTEGER DEFAULT 0,
  best_trade_pnl DECIMAL(18, 2),
  worst_trade_pnl DECIMAL(18, 2),
  
  -- Trading behavior patterns
  preferred_markets JSONB,
  avg_position_size DECIMAL(5, 2),
  risk_score DECIMAL(5, 2),
  trading_frequency VARCHAR(20),
  sentiment_bias VARCHAR(20),
  
  -- Time-based performance
  pnl_7d DECIMAL(18, 2),
  pnl_30d DECIMAL(18, 2),
  pnl_90d DECIMAL(18, 2),
  volume_7d DECIMAL(18, 2),
  volume_30d DECIMAL(18, 2),
  
  -- User status
  is_profitable BOOLEAN,
  is_active BOOLEAN DEFAULT true,
  is_whale BOOLEAN DEFAULT false,
  is_successful_trader BOOLEAN DEFAULT false,
  last_trade_at TIMESTAMP,
  
  -- Administrative
  first_seen_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Users indexes
CREATE INDEX idx_users_pnl ON users(total_pnl DESC);
CREATE INDEX idx_users_win_rate ON users(win_rate DESC);
CREATE INDEX idx_users_roi ON users(roi_percentage DESC);
CREATE INDEX idx_users_successful ON users(is_successful_trader) WHERE is_successful_trader = true;
CREATE INDEX idx_users_last_trade ON users(last_trade_at DESC);

COMMENT ON TABLE users IS 'User profiles with calculated trading performance metrics for AI training';

-- ============================================
-- TRADES TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS trades (
  id BIGSERIAL PRIMARY KEY,
  transaction_hash VARCHAR(66) UNIQUE,
  proxy_wallet VARCHAR(42) NOT NULL REFERENCES users(proxy_wallet) ON DELETE CASCADE,
  condition_id VARCHAR(66) NOT NULL,
  slug VARCHAR(255) REFERENCES markets(slug) ON DELETE SET NULL,
  
  -- Trade details
  side VARCHAR(4) NOT NULL CHECK (side IN ('BUY', 'SELL')),
  asset VARCHAR(66),
  outcome VARCHAR(255),
  outcome_index INTEGER,
  size DECIMAL(18, 8) NOT NULL,
  price DECIMAL(18, 8) NOT NULL,
  
  -- Metadata
  timestamp BIGINT NOT NULL,
  datetime TIMESTAMP NOT NULL,
  title TEXT,
  icon TEXT,
  event_slug VARCHAR(255),
  
  -- Calculated fields
  trade_value_usd DECIMAL(18, 2)
);

-- Trades indexes
CREATE INDEX idx_trades_wallet ON trades(proxy_wallet);
CREATE INDEX idx_trades_condition ON trades(condition_id);
CREATE INDEX idx_trades_slug ON trades(slug);
CREATE INDEX idx_trades_datetime ON trades(datetime DESC);
CREATE INDEX idx_trades_wallet_time ON trades(proxy_wallet, datetime DESC);
CREATE INDEX idx_trades_tx_hash ON trades(transaction_hash);
CREATE INDEX idx_trades_side_time ON trades(side, datetime DESC);

COMMENT ON TABLE trades IS 'Individual trade records linked to users and markets';

-- ============================================
-- USER POSITIONS TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS user_positions (
  id BIGSERIAL PRIMARY KEY,
  proxy_wallet VARCHAR(42) NOT NULL REFERENCES users(proxy_wallet) ON DELETE CASCADE,
  condition_id VARCHAR(66) NOT NULL,
  slug VARCHAR(255) REFERENCES markets(slug) ON DELETE SET NULL,
  
  -- Position details
  outcome VARCHAR(255) NOT NULL,
  outcome_index INTEGER NOT NULL,
  asset VARCHAR(66),
  
  -- Position metrics
  current_size DECIMAL(18, 8) NOT NULL,
  avg_entry_price DECIMAL(18, 8) NOT NULL,
  total_invested DECIMAL(18, 2),
  current_value DECIMAL(18, 2),
  unrealized_pnl DECIMAL(18, 2),
  realized_pnl DECIMAL(18, 2) DEFAULT 0,
  
  -- Position lifecycle
  opened_at TIMESTAMP NOT NULL,
  last_updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
  closed_at TIMESTAMP,
  is_open BOOLEAN DEFAULT true,
  
  -- Position classification
  is_redeemable BOOLEAN DEFAULT false,
  is_mergeable BOOLEAN DEFAULT false,
  
  UNIQUE(proxy_wallet, condition_id, outcome)
);

-- Positions indexes
CREATE INDEX idx_positions_wallet_open ON user_positions(proxy_wallet, is_open) WHERE is_open = true;
CREATE INDEX idx_positions_condition ON user_positions(condition_id);
CREATE INDEX idx_positions_closed_at ON user_positions(closed_at DESC);

COMMENT ON TABLE user_positions IS 'Current and historical user positions aggregated from trades';

-- ============================================
-- MARKET SNAPSHOTS TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS market_snapshots (
  id BIGSERIAL PRIMARY KEY,
  condition_id VARCHAR(66) NOT NULL REFERENCES markets(condition_id) ON DELETE CASCADE,
  slug VARCHAR(255) REFERENCES markets(slug) ON DELETE SET NULL,
  
  -- Snapshot time
  snapshot_at TIMESTAMP NOT NULL DEFAULT NOW(),
  
  -- Price data
  outcome_prices JSONB NOT NULL,
  best_bid DECIMAL(18, 8),
  best_ask DECIMAL(18, 8),
  spread DECIMAL(18, 8),
  last_trade_price DECIMAL(18, 8),
  
  -- Volume data
  volume_total DECIMAL(18, 2),
  volume_24hr DECIMAL(18, 2),
  liquidity DECIMAL(18, 2),
  
  -- Market metrics
  num_trades_24hr INTEGER,
  unique_traders_24hr INTEGER
);

-- Snapshots indexes
CREATE INDEX idx_snapshots_market_time ON market_snapshots(condition_id, snapshot_at DESC);
CREATE INDEX idx_snapshots_time ON market_snapshots(snapshot_at DESC);
CREATE INDEX idx_snapshots_slug ON market_snapshots(slug);

COMMENT ON TABLE market_snapshots IS 'Time-series snapshots of market data for trend analysis';

-- ============================================
-- TRADING PATTERNS TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS trading_patterns (
  id BIGSERIAL PRIMARY KEY,
  proxy_wallet VARCHAR(42) REFERENCES users(proxy_wallet) ON DELETE CASCADE,
  pattern_type VARCHAR(50) NOT NULL,
  pattern_name VARCHAR(255) NOT NULL,
  
  -- Pattern characteristics
  description TEXT,
  success_rate DECIMAL(5, 2),
  avg_return DECIMAL(10, 2),
  frequency INTEGER DEFAULT 1,
  
  -- Pattern context
  market_conditions JSONB,
  time_of_day VARCHAR(20),
  
  -- Metadata
  first_observed_at TIMESTAMP NOT NULL,
  last_observed_at TIMESTAMP NOT NULL
);

-- Patterns indexes
CREATE INDEX idx_patterns_wallet ON trading_patterns(proxy_wallet);
CREATE INDEX idx_patterns_type ON trading_patterns(pattern_type);
CREATE INDEX idx_patterns_success ON trading_patterns(success_rate DESC);

COMMENT ON TABLE trading_patterns IS 'Identified trading patterns for AI learning and replication';

-- ============================================
-- TRIGGERS
-- ============================================

-- Auto-update markets.updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_markets_updated_at
BEFORE UPDATE ON markets
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trigger_users_updated_at
BEFORE UPDATE ON users
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

-- Auto-update user stats on new trade
CREATE OR REPLACE FUNCTION update_user_stats_on_trade()
RETURNS TRIGGER AS $$
BEGIN
  -- Upsert user if doesn't exist
  INSERT INTO users (proxy_wallet, first_seen_at, total_trades, last_trade_at)
  VALUES (NEW.proxy_wallet, NEW.datetime, 1, NEW.datetime)
  ON CONFLICT (proxy_wallet) DO UPDATE
  SET 
    total_trades = users.total_trades + 1,
    last_trade_at = NEW.datetime,
    updated_at = NOW();
  
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_user_stats
AFTER INSERT ON trades
FOR EACH ROW
EXECUTE FUNCTION update_user_stats_on_trade();

-- Calculate trade value
CREATE OR REPLACE FUNCTION calculate_trade_value()
RETURNS TRIGGER AS $$
BEGIN
  NEW.trade_value_usd = NEW.size * NEW.price;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_calculate_trade_value
BEFORE INSERT OR UPDATE ON trades
FOR EACH ROW
EXECUTE FUNCTION calculate_trade_value();

-- ============================================
-- FUNCTIONS
-- ============================================

-- Calculate user win rate
CREATE OR REPLACE FUNCTION calculate_user_win_rate(wallet_address VARCHAR)
RETURNS DECIMAL AS $$
  SELECT 
    COALESCE(
      (COUNT(*) FILTER (WHERE realized_pnl > 0)::DECIMAL / 
       NULLIF(COUNT(*) FILTER (WHERE is_open = false), 0)) * 100,
      0
    )
  FROM user_positions
  WHERE proxy_wallet = wallet_address 
    AND is_open = false;
$$ LANGUAGE SQL;

-- Calculate user ROI
CREATE OR REPLACE FUNCTION calculate_user_roi(wallet_address VARCHAR)
RETURNS DECIMAL AS $$
  SELECT 
    COALESCE(
      (SUM(realized_pnl) / NULLIF(SUM(total_invested), 0)) * 100,
      0
    )
  FROM user_positions
  WHERE proxy_wallet = wallet_address;
$$ LANGUAGE SQL;

-- Get user total P&L
CREATE OR REPLACE FUNCTION calculate_user_total_pnl(wallet_address VARCHAR)
RETURNS DECIMAL AS $$
  SELECT 
    COALESCE(
      SUM(realized_pnl) + SUM(COALESCE(unrealized_pnl, 0)),
      0
    )
  FROM user_positions
  WHERE proxy_wallet = wallet_address;
$$ LANGUAGE SQL;

-- Update all user metrics
CREATE OR REPLACE FUNCTION update_user_metrics()
RETURNS void AS $$
BEGIN
  UPDATE users u
  SET 
    win_rate = calculate_user_win_rate(u.proxy_wallet),
    roi_percentage = calculate_user_roi(u.proxy_wallet),
    total_pnl = calculate_user_total_pnl(u.proxy_wallet),
    is_profitable = calculate_user_total_pnl(u.proxy_wallet) > 0,
    total_volume = (
      SELECT COALESCE(SUM(trade_value_usd), 0)
      FROM trades
      WHERE proxy_wallet = u.proxy_wallet
    ),
    updated_at = NOW();
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- VIEWS
-- ============================================

-- Successful traders view
CREATE OR REPLACE VIEW v_successful_traders AS
SELECT 
  proxy_wallet,
  name,
  pseudonym,
  win_rate,
  roi_percentage,
  total_pnl,
  total_trades,
  total_volume,
  last_trade_at
FROM users
WHERE is_successful_trader = true
ORDER BY roi_percentage DESC;

-- Active markets view
CREATE OR REPLACE VIEW v_active_markets AS
SELECT 
  slug,
  question,
  volume_24hr,
  liquidity_num,
  spread,
  one_day_price_change,
  end_date_iso,
  last_trade_price
FROM markets
WHERE active = true 
  AND closed = false
ORDER BY volume_24hr DESC NULLS LAST;

-- Recent trades with user info
CREATE OR REPLACE VIEW v_recent_trades AS
SELECT 
  t.id,
  t.datetime,
  t.side,
  t.outcome,
  t.price,
  t.size,
  t.trade_value_usd,
  t.slug,
  t.title,
  u.pseudonym as trader_name,
  u.win_rate as trader_win_rate,
  u.is_successful_trader
FROM trades t
JOIN users u ON t.proxy_wallet = u.proxy_wallet
ORDER BY t.datetime DESC;

-- ============================================
-- GRANTS (Optional - adjust based on your needs)
-- ============================================
-- GRANT SELECT ON ALL TABLES IN SCHEMA public TO anon;
-- GRANT ALL ON ALL TABLES IN SCHEMA public TO authenticated;
-- GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO authenticated;

-- ============================================
-- INITIAL DATA / SEED (Optional)
-- ============================================
-- You can add any initial data here

COMMIT;

