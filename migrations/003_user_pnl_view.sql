-- ============================================================================
-- Migration: Create user_pnl_90d view for calculating user P&L
-- ============================================================================
-- This view calculates Profit and Loss (PNL) for each user per market
-- based on trades in the last 90 days
-- 
-- CORRECTED PNL Formula (Cash Flow Method):
-- PNL = (Value of Holdings + Cash from Sales) - (Total Cash Spent)
-- 
-- Where:
-- - Value of Holdings = Net Position × Final Value ($1 for winner, $0 for loser)
-- - Cash from Sales = Total proceeds from all SELL transactions
-- - Total Cash Spent = Total cost of all BUY transactions
-- 
-- This eliminates the need for COGS calculation and provides a clearer
-- cash-in vs cash-out accounting method.
-- ============================================================================

-- Main PNL view using CTEs as MATERIALIZED VIEW for fast access
-- Note: Refresh periodically using: REFRESH MATERIALIZED VIEW user_pnl_90d;
CREATE MATERIALIZED VIEW user_pnl_90d AS
WITH trades_recent AS (
    SELECT 
        t.*,
        m.final_outcome,
        LOWER(t.outcome) as outcome_lower
    FROM trades t
    INNER JOIN recent_markets m ON t.condition_id = m.condition_id
    WHERE t.timestamp >= EXTRACT(EPOCH FROM (NOW() - INTERVAL '90 days'))
),
-- Calculate aggregates per user, market, outcome
position_aggregates AS (
    SELECT
        proxy_wallet,
        condition_id,
        outcome_lower,
        final_outcome,
        -- Net position = total buys - total sells
        SUM(CASE WHEN side = 'BUY' THEN size ELSE 0 END) - 
        SUM(CASE WHEN side = 'SELL' THEN size ELSE 0 END) as net_position,
        
        -- Total cost of buys (price * size for all buys)
        SUM(CASE WHEN side = 'BUY' THEN price * size ELSE 0 END) as total_buy_cost,
        
        -- Total shares bought
        SUM(CASE WHEN side = 'BUY' THEN size ELSE 0 END) as total_shares_bought,
        
        -- Average cost basis (ACB) for COGS calculation
        CASE 
            WHEN SUM(CASE WHEN side = 'BUY' THEN size ELSE 0 END) > 0 
            THEN SUM(CASE WHEN side = 'BUY' THEN price * size ELSE 0 END) / 
                 SUM(CASE WHEN side = 'BUY' THEN size ELSE 0 END)
            ELSE 0 
        END as avg_cost_basis,
        
        -- Total proceeds from sales (price * size for all sells)
        SUM(CASE WHEN side = 'SELL' THEN price * size ELSE 0 END) as total_sale_proceeds,
        
        -- Total shares sold
        SUM(CASE WHEN side = 'SELL' THEN size ELSE 0 END) as total_shares_sold,
        
        -- Trade count
        COUNT(*) as trade_count
    FROM trades_recent
    GROUP BY proxy_wallet, condition_id, outcome_lower, final_outcome
),
-- Aggregate positions by user and market
position_summary AS (
    -- Group by user and market to get positions for both outcomes
    SELECT
        proxy_wallet,
        condition_id,
        final_outcome,
        
        -- Net positions by outcome
        SUM(CASE WHEN outcome_lower = LOWER(final_outcome) THEN net_position ELSE 0 END) as net_position_winning,
        SUM(CASE WHEN outcome_lower != LOWER(final_outcome) THEN net_position ELSE 0 END) as net_position_losing,
        
        -- Sale proceeds by outcome
        SUM(CASE WHEN outcome_lower = LOWER(final_outcome) THEN total_sale_proceeds ELSE 0 END) as proceeds_winning,
        SUM(CASE WHEN outcome_lower != LOWER(final_outcome) THEN total_sale_proceeds ELSE 0 END) as proceeds_losing,
        
        -- COGS by outcome (ACB × shares sold)
        SUM(CASE WHEN outcome_lower = LOWER(final_outcome) THEN avg_cost_basis * total_shares_sold ELSE 0 END) as cogs_winning,
        SUM(CASE WHEN outcome_lower != LOWER(final_outcome) THEN avg_cost_basis * total_shares_sold ELSE 0 END) as cogs_losing,  -- Kept for reference only
        
        -- Total buy costs (all outcomes)
        SUM(total_buy_cost) as total_buy_cost,
        
        -- Trade statistics
        SUM(trade_count) as total_trades,
        SUM(total_shares_bought) as total_shares_bought,
        SUM(total_shares_sold) as total_shares_sold
        
    FROM position_aggregates
    WHERE final_outcome IS NOT NULL  -- Only include resolved markets
    GROUP BY proxy_wallet, condition_id, final_outcome
)
-- Final calculation
SELECT
    ps.proxy_wallet,
    ps.condition_id,
    ps.final_outcome,
    
    -- Position details
    ps.net_position_winning,
    ps.net_position_losing,
    ps.net_position_winning + ps.net_position_losing as net_position_total,
    
    -- Value of final positions
    -- Winning side: $1.00 per share, Losing side: $0.00 per share
    ps.net_position_winning * 1.00 as position_value_winning,
    ps.net_position_losing * 0.00 as position_value_losing,
    (ps.net_position_winning * 1.00) + (ps.net_position_losing * 0.00) as total_position_value,
    
    -- Realized gains from sales
    (ps.proceeds_winning - ps.cogs_winning) as realized_pnl_winning,
    (ps.proceeds_losing - ps.cogs_losing) as realized_pnl_losing,
    (ps.proceeds_winning - ps.cogs_winning) + (ps.proceeds_losing - ps.cogs_losing) as total_realized_pnl,
    
    -- Total PNL Calculation (Cash Flow Method)
    -- PNL = (Value of Holdings + Cash from Sales) - (Total Cash Spent)
    (
        ((ps.net_position_winning * 1.00) + (ps.net_position_losing * 0.00)) +  -- Final Redemption Value
        (ps.proceeds_winning + ps.proceeds_losing)                              -- Cash In from Sales
    ) 
    - ps.total_buy_cost                                                         -- Cash Out for Buys
    as pnl,
    
    -- Cost breakdown
    ps.total_buy_cost,
    ps.proceeds_winning + ps.proceeds_losing as total_sale_proceeds,
    ps.cogs_winning + ps.cogs_losing as total_cogs,
    
    -- Trade statistics
    ps.total_trades,
    ps.total_shares_bought,
    ps.total_shares_sold,
    
    -- ROI (Return on Investment) as percentage  
    CASE 
        WHEN ps.total_buy_cost > 0 
        THEN (
            (((ps.net_position_winning * 1.00) + (ps.net_position_losing * 0.00)) + 
             (ps.proceeds_winning + ps.proceeds_losing)) 
            - ps.total_buy_cost
        ) / ps.total_buy_cost * 100
        ELSE NULL
    END as roi_percent,
    
    -- Metadata
    NOW() as calculated_at
    
FROM position_summary ps
WHERE ps.total_trades > 0;  -- Only include users who actually traded

-- Create indexes on materialized view
CREATE INDEX idx_user_pnl_90d_wallet ON user_pnl_90d(proxy_wallet);
CREATE INDEX idx_user_pnl_90d_condition ON user_pnl_90d(condition_id);
CREATE INDEX idx_user_pnl_90d_pnl ON user_pnl_90d(pnl);
CREATE INDEX idx_user_pnl_90d_roi ON user_pnl_90d(roi_percent);

-- Grant permissions
GRANT SELECT ON user_pnl_90d TO anon, authenticated;

COMMENT ON MATERIALIZED VIEW user_pnl_90d IS 
    'Calculated Profit and Loss (PNL) for each user per resolved market based on trades in the last 90 days using cash flow method: 
    PNL = (Value of Holdings + Cash from Sales) - Total Cash Spent. 
    Includes position value, sale proceeds, and total PNL with ROI percentage.
    Refresh periodically using: REFRESH MATERIALIZED VIEW user_pnl_90d;';


-- ============================================================================
-- Aggregate view: User total PNL across all markets (MATERIALIZED)
-- ============================================================================

CREATE MATERIALIZED VIEW user_total_pnl_90d AS
SELECT
    proxy_wallet,
    COUNT(DISTINCT condition_id) as markets_traded,
    SUM(total_trades) as total_trades,
    SUM(total_shares_bought) as total_shares_bought,
    SUM(total_shares_sold) as total_shares_sold,
    
    -- PNL aggregates
    SUM(pnl) as total_pnl,
    AVG(pnl) as avg_pnl_per_market,
    MAX(pnl) as max_pnl_market,
    MIN(pnl) as min_pnl_market,
    
    -- Cost aggregates
    SUM(total_buy_cost) as total_invested,
    SUM(total_sale_proceeds) as total_proceeds,
    SUM(total_position_value) as total_position_value,
    
    -- Performance metrics
    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as profitable_markets,
    SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as losing_markets,
    SUM(CASE WHEN pnl = 0 THEN 1 ELSE 0 END) as breakeven_markets,
    
    -- Win rate
    CASE 
        WHEN COUNT(DISTINCT condition_id) > 0 
        THEN SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END)::numeric / COUNT(DISTINCT condition_id) * 100
        ELSE NULL
    END as win_rate_percent,
    
    -- Overall ROI
    CASE 
        WHEN SUM(total_buy_cost) > 0 
        THEN SUM(pnl) / SUM(total_buy_cost) * 100
        ELSE NULL
    END as overall_roi_percent,
    
    NOW() as calculated_at
    
FROM user_pnl_90d
GROUP BY proxy_wallet;

-- Create indexes on materialized view
CREATE INDEX idx_user_total_pnl_90d_wallet ON user_total_pnl_90d(proxy_wallet);
CREATE INDEX idx_user_total_pnl_90d_total_pnl ON user_total_pnl_90d(total_pnl);
CREATE INDEX idx_user_total_pnl_90d_roi ON user_total_pnl_90d(overall_roi_percent);
CREATE INDEX idx_user_total_pnl_90d_win_rate ON user_total_pnl_90d(win_rate_percent);

-- Grant permissions
GRANT SELECT ON user_total_pnl_90d TO anon, authenticated;

COMMENT ON MATERIALIZED VIEW user_total_pnl_90d IS 
    'Aggregated PNL metrics for each user across all markets traded in the last 90 days. 
    Includes total PNL, win rate, ROI, and performance statistics.
    Refresh periodically using: REFRESH MATERIALIZED VIEW user_total_pnl_90d;';


-- ============================================================================
-- Helper function: Refresh both PNL materialized views
-- ============================================================================

CREATE OR REPLACE FUNCTION refresh_pnl_views()
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    REFRESH MATERIALIZED VIEW user_pnl_90d;
    REFRESH MATERIALIZED VIEW user_total_pnl_90d;
    RAISE NOTICE 'PNL materialized views refreshed successfully';
END;
$$;

COMMENT ON FUNCTION refresh_pnl_views() IS 
    'Refreshes both PNL materialized views (user_pnl_90d and user_total_pnl_90d). 
    Call this after loading new trade data or when you need updated PNL calculations.';

GRANT EXECUTE ON FUNCTION refresh_pnl_views() TO anon, authenticated;

