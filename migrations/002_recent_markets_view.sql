-- ============================================================================
-- Migration: Create recent_markets view for markets from past 90 days
-- ============================================================================
-- This provides a fast way to query only recent markets (created in last 90 days)
-- 
-- Two options provided:
-- 1. Materialized View (faster queries, needs periodic refresh)
-- 2. Regular View (always up-to-date, slightly slower)
-- ============================================================================

-- OPTION 1: MATERIALIZED VIEW (Recommended for performance)
-- ============================================================================
-- Pros: Fast queries, physical storage, can be indexed
-- Cons: Needs to be refreshed periodically (REFRESH MATERIALIZED VIEW)

CREATE MATERIALIZED VIEW IF NOT EXISTS recent_markets AS
SELECT 
    m.*,
    e.title as event_title,
    e.active as event_active,
    e.closed as event_closed,
    -- Computed column: final_outcome based on which outcome price is closer to 1
    CASE
        WHEN ((m.outcome_prices#>>'{}')::jsonb->>0)::numeric > ((m.outcome_prices#>>'{}')::jsonb->>1)::numeric
        THEN LOWER((m.outcomes#>>'{}')::jsonb->>0)
        ELSE LOWER((m.outcomes#>>'{}')::jsonb->>1)
    END as final_outcome
FROM markets m
LEFT JOIN events e ON m.event_id = e.id
WHERE 
    -- Markets created in the past 90 days
    m.created_at >= NOW() - INTERVAL '90 days';

-- Create indexes on the materialized view for faster queries
CREATE INDEX IF NOT EXISTS idx_recent_markets_condition_id 
    ON recent_markets(condition_id);

CREATE INDEX IF NOT EXISTS idx_recent_markets_active 
    ON recent_markets(active);

CREATE INDEX IF NOT EXISTS idx_recent_markets_created_at 
    ON recent_markets(created_at);

CREATE INDEX IF NOT EXISTS idx_recent_markets_event_id 
    ON recent_markets(event_id);

CREATE INDEX IF NOT EXISTS idx_recent_markets_final_outcome 
    ON recent_markets(final_outcome);

-- Grant permissions
GRANT SELECT ON recent_markets TO anon, authenticated;

COMMENT ON MATERIALIZED VIEW recent_markets IS 
    'Materialized view containing markets created in the past 90 days with computed final_outcome column. Refresh periodically using: REFRESH MATERIALIZED VIEW recent_markets;';


-- ============================================================================
-- OPTION 2: REGULAR VIEW (Alternative - always up-to-date)
-- ============================================================================
-- Uncomment if you prefer a regular view instead
-- Regular views are always current but slightly slower

/*
CREATE OR REPLACE VIEW recent_markets_live AS
SELECT 
    m.*,
    e.title as event_title,
    e.active as event_active,
    e.closed as event_closed
FROM markets m
LEFT JOIN events e ON m.event_id = e.id
WHERE 
    m.created_at >= NOW() - INTERVAL '90 days';

GRANT SELECT ON recent_markets_live TO anon, authenticated;

COMMENT ON VIEW recent_markets_live IS 
    'Live view of markets created in the past 90 days. Always up-to-date.';
*/


-- ============================================================================
-- Helper Function: Refresh the materialized view
-- ============================================================================

CREATE OR REPLACE FUNCTION refresh_recent_markets()
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    REFRESH MATERIALIZED VIEW recent_markets;
    
    RAISE NOTICE 'Materialized view recent_markets refreshed successfully';
END;
$$;

COMMENT ON FUNCTION refresh_recent_markets() IS 
    'Refreshes the recent_markets materialized view. Call this after bulk data updates or on a schedule.';

-- Grant execute permission
GRANT EXECUTE ON FUNCTION refresh_recent_markets() TO anon, authenticated;


-- ============================================================================
-- Optional: Auto-refresh trigger (careful with performance!)
-- ============================================================================
-- Uncomment if you want automatic refresh on market updates
-- WARNING: This can be slow if you have many updates

/*
CREATE OR REPLACE FUNCTION trigger_refresh_recent_markets()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    -- Only refresh if significant time has passed since last refresh
    -- This prevents too frequent refreshes
    PERFORM pg_advisory_lock(12345);
    
    IF NOT EXISTS (
        SELECT 1 FROM pg_stat_user_tables 
        WHERE schemaname = 'public' 
        AND relname = 'recent_markets'
        AND last_autovacuum > NOW() - INTERVAL '5 minutes'
    ) THEN
        REFRESH MATERIALIZED VIEW recent_markets;
    END IF;
    
    PERFORM pg_advisory_unlock(12345);
    
    RETURN NULL;
END;
$$;

-- Trigger on markets table updates
CREATE TRIGGER after_market_update_refresh_recent
AFTER INSERT OR UPDATE ON markets
FOR EACH STATEMENT
EXECUTE FUNCTION trigger_refresh_recent_markets();
*/

