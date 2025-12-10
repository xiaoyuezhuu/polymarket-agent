"""
Analyze trading patterns from successful Polymarket traders
"""

import os
import pandas as pd
from supabase import create_client, Client
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
import json

# ============================================
# Configuration
# ============================================

SUPABASE_URL = os.environ.get("SUPABASE_URL", "your-project-url.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "your-anon-key")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ============================================
# Analysis Functions
# ============================================

def get_successful_traders(min_trades: int = 50, min_win_rate: float = 55.0, 
                           min_roi: float = 10.0) -> pd.DataFrame:
    """
    Get list of successful traders based on criteria
    """
    query = supabase.table('users').select('*').execute()
    df = pd.DataFrame(query.data)
    
    if df.empty:
        return df
    
    # Filter successful traders
    successful = df[
        (df['total_trades'] >= min_trades) &
        (df['win_rate'] >= min_win_rate) &
        (df['roi_percentage'] >= min_roi)
    ].copy()
    
    successful = successful.sort_values('roi_percentage', ascending=False)
    
    return successful


def analyze_early_entry_pattern(trader_address: str) -> Dict:
    """
    Analyze if a trader has early entry pattern (entering markets early)
    """
    # Get trader's trades
    trades_query = supabase.table('trades').select('*').eq(
        'proxy_wallet', trader_address
    ).execute()
    
    if not trades_query.data:
        return {}
    
    trades_df = pd.DataFrame(trades_query.data)
    trades_df['datetime'] = pd.to_datetime(trades_df['datetime'])
    
    # Get market information for these trades
    results = []
    
    for slug in trades_df['slug'].unique():
        if not slug:
            continue
            
        # Get first trade time for this market (from all users)
        first_trade_query = supabase.table('trades').select('datetime').eq(
            'slug', slug
        ).order('datetime').limit(1).execute()
        
        if first_trade_query.data:
            first_trade_time = pd.to_datetime(first_trade_query.data[0]['datetime'])
            
            # Get trader's first trade on this market
            trader_first_trade = trades_df[trades_df['slug'] == slug]['datetime'].min()
            
            hours_after_market_start = (trader_first_trade - first_trade_time).total_seconds() / 3600
            
            results.append({
                'slug': slug,
                'hours_after_start': hours_after_market_start,
                'was_early': hours_after_market_start < 24  # Within first 24 hours
            })
    
    if not results:
        return {}
    
    results_df = pd.DataFrame(results)
    
    return {
        'pattern_type': 'early_entry',
        'total_markets': len(results),
        'early_entries': results_df['was_early'].sum(),
        'early_entry_rate': results_df['was_early'].mean() * 100,
        'avg_hours_after_start': results_df['hours_after_start'].mean()
    }


def analyze_contrarian_pattern(trader_address: str) -> Dict:
    """
    Analyze if trader takes contrarian positions
    """
    trades_query = supabase.table('trades').select('*').eq(
        'proxy_wallet', trader_address
    ).execute()
    
    if not trades_query.data:
        return {}
    
    trades_df = pd.DataFrame(trades_query.data)
    trades_df['datetime'] = pd.to_datetime(trades_df['datetime'])
    
    contrarian_count = 0
    total_analyzed = 0
    
    for _, trade in trades_df.iterrows():
        if not trade['slug'] or not trade['outcome']:
            continue
            
        # Get consensus at time of trade (outcome with most trades in previous 24h)
        time_window_start = trade['datetime'] - timedelta(hours=24)
        
        consensus_query = supabase.table('trades').select('outcome').eq(
            'slug', trade['slug']
        ).gte('datetime', time_window_start.isoformat()).lt(
            'datetime', trade['datetime'].isoformat()
        ).execute()
        
        if not consensus_query.data or len(consensus_query.data) < 5:
            continue
            
        consensus_df = pd.DataFrame(consensus_query.data)
        consensus_outcome = consensus_df['outcome'].mode()[0] if not consensus_df.empty else None
        
        if consensus_outcome and trade['outcome'] != consensus_outcome:
            contrarian_count += 1
        
        total_analyzed += 1
    
    if total_analyzed == 0:
        return {}
    
    return {
        'pattern_type': 'contrarian',
        'total_analyzed': total_analyzed,
        'contrarian_trades': contrarian_count,
        'contrarian_rate': (contrarian_count / total_analyzed) * 100
    }


def analyze_position_sizing(trader_address: str) -> Dict:
    """
    Analyze trader's position sizing strategy
    """
    trades_query = supabase.table('trades').select('*').eq(
        'proxy_wallet', trader_address
    ).execute()
    
    if not trades_query.data:
        return {}
    
    trades_df = pd.DataFrame(trades_query.data)
    trades_df['trade_value_usd'] = pd.to_numeric(trades_df['trade_value_usd'], errors='coerce')
    
    return {
        'pattern_type': 'position_sizing',
        'avg_position_size': trades_df['trade_value_usd'].mean(),
        'median_position_size': trades_df['trade_value_usd'].median(),
        'std_position_size': trades_df['trade_value_usd'].std(),
        'max_position_size': trades_df['trade_value_usd'].max(),
        'min_position_size': trades_df['trade_value_usd'].min(),
        'total_trades': len(trades_df),
        'position_sizing_consistency': trades_df['trade_value_usd'].std() / trades_df['trade_value_usd'].mean()
    }


def analyze_trading_frequency(trader_address: str) -> Dict:
    """
    Analyze trading frequency and timing patterns
    """
    trades_query = supabase.table('trades').select('*').eq(
        'proxy_wallet', trader_address
    ).order('datetime').execute()
    
    if not trades_query.data:
        return {}
    
    trades_df = pd.DataFrame(trades_query.data)
    trades_df['datetime'] = pd.to_datetime(trades_df['datetime'])
    
    # Calculate time between trades
    trades_df = trades_df.sort_values('datetime')
    time_diffs = trades_df['datetime'].diff().dt.total_seconds() / 3600  # hours
    
    # Extract time features
    trades_df['hour'] = trades_df['datetime'].dt.hour
    trades_df['day_of_week'] = trades_df['datetime'].dt.dayofweek
    
    return {
        'pattern_type': 'frequency',
        'total_trades': len(trades_df),
        'days_active': (trades_df['datetime'].max() - trades_df['datetime'].min()).days,
        'avg_trades_per_day': len(trades_df) / max((trades_df['datetime'].max() - trades_df['datetime'].min()).days, 1),
        'avg_hours_between_trades': time_diffs.mean(),
        'median_hours_between_trades': time_diffs.median(),
        'most_active_hour': trades_df['hour'].mode()[0] if not trades_df.empty else None,
        'most_active_day': trades_df['day_of_week'].mode()[0] if not trades_df.empty else None,
    }


def get_trader_performance_by_market_type(trader_address: str) -> pd.DataFrame:
    """
    Analyze performance across different types of markets
    """
    query = f"""
        SELECT 
            m.events,
            COUNT(t.id) as trade_count,
            AVG(up.realized_pnl) as avg_pnl,
            SUM(CASE WHEN up.realized_pnl > 0 THEN 1 ELSE 0 END)::float / 
                NULLIF(COUNT(*), 0) * 100 as win_rate
        FROM trades t
        JOIN markets m ON t.slug = m.slug
        LEFT JOIN user_positions up ON t.proxy_wallet = up.proxy_wallet 
            AND t.slug = up.slug
        WHERE t.proxy_wallet = '{trader_address}'
            AND up.is_open = false
        GROUP BY m.events
    """
    
    # Note: This is a complex query - might need adjustment based on actual schema
    # For now, return basic market analysis
    
    trades_query = supabase.table('trades').select(
        '*, markets!inner(events, question)'
    ).eq('proxy_wallet', trader_address).execute()
    
    if not trades_query.data:
        return pd.DataFrame()
    
    df = pd.DataFrame(trades_query.data)
    return df


def identify_all_patterns_for_trader(trader_address: str) -> Dict:
    """
    Run all pattern analyses for a trader
    """
    print(f"\nAnalyzing patterns for trader: {trader_address}")
    
    patterns = {
        'trader_address': trader_address,
        'analysis_timestamp': datetime.utcnow().isoformat(),
        'patterns': []
    }
    
    # Get trader info
    trader_query = supabase.table('users').select('*').eq(
        'proxy_wallet', trader_address
    ).execute()
    
    if trader_query.data:
        trader_info = trader_query.data[0]
        patterns['trader_info'] = {
            'pseudonym': trader_info.get('pseudonym'),
            'win_rate': trader_info.get('win_rate'),
            'roi_percentage': trader_info.get('roi_percentage'),
            'total_trades': trader_info.get('total_trades'),
            'total_pnl': trader_info.get('total_pnl'),
        }
    
    # Run pattern analyses
    print("  - Analyzing early entry pattern...")
    early_entry = analyze_early_entry_pattern(trader_address)
    if early_entry:
        patterns['patterns'].append(early_entry)
    
    print("  - Analyzing contrarian pattern...")
    contrarian = analyze_contrarian_pattern(trader_address)
    if contrarian:
        patterns['patterns'].append(contrarian)
    
    print("  - Analyzing position sizing...")
    position_sizing = analyze_position_sizing(trader_address)
    if position_sizing:
        patterns['patterns'].append(position_sizing)
    
    print("  - Analyzing trading frequency...")
    frequency = analyze_trading_frequency(trader_address)
    if frequency:
        patterns['patterns'].append(frequency)
    
    return patterns


def store_identified_pattern(trader_address: str, pattern: Dict):
    """
    Store identified pattern in database
    """
    pattern_record = {
        'proxy_wallet': trader_address,
        'pattern_type': pattern.get('pattern_type'),
        'pattern_name': f"{pattern.get('pattern_type')}_{trader_address[:8]}",
        'description': json.dumps(pattern),
        'success_rate': pattern.get('early_entry_rate') or pattern.get('contrarian_rate'),
        'frequency': pattern.get('total_analyzed') or pattern.get('total_trades'),
        'first_observed_at': datetime.utcnow().isoformat(),
        'last_observed_at': datetime.utcnow().isoformat()
    }
    
    try:
        result = supabase.table('trading_patterns').insert(pattern_record).execute()
        return True
    except Exception as e:
        print(f"Error storing pattern: {e}")
        return False


# ============================================
# Main Analysis Pipeline
# ============================================

def run_pattern_analysis(min_trades: int = 50):
    """
    Main function to analyze patterns for all successful traders
    """
    print("=" * 60)
    print("Trading Pattern Analysis")
    print("=" * 60)
    
    # Get successful traders
    print("\n1. Identifying successful traders...")
    successful_traders = get_successful_traders(min_trades=min_trades)
    
    if successful_traders.empty:
        print("No successful traders found. Adjust criteria or load more data.")
        return
    
    print(f"Found {len(successful_traders)} successful traders")
    print("\nTop 10 by ROI:")
    print(successful_traders[['pseudonym', 'win_rate', 'roi_percentage', 'total_trades']].head(10))
    
    # Analyze patterns for top traders
    print("\n2. Analyzing patterns for top traders...")
    
    all_patterns = []
    
    for idx, trader in successful_traders.head(10).iterrows():
        patterns = identify_all_patterns_for_trader(trader['proxy_wallet'])
        all_patterns.append(patterns)
        
        # Store patterns in database
        for pattern in patterns.get('patterns', []):
            store_identified_pattern(trader['proxy_wallet'], pattern)
    
    # Summary
    print("\n" + "=" * 60)
    print("Pattern Analysis Complete")
    print("=" * 60)
    
    print(f"\nAnalyzed {len(all_patterns)} traders")
    print("\nCommon patterns identified:")
    
    pattern_counts = {}
    for trader_patterns in all_patterns:
        for pattern in trader_patterns.get('patterns', []):
            ptype = pattern.get('pattern_type')
            pattern_counts[ptype] = pattern_counts.get(ptype, 0) + 1
    
    for ptype, count in pattern_counts.items():
        print(f"  - {ptype}: {count} traders")
    
    return all_patterns


if __name__ == "__main__":
    # Check configuration
    if SUPABASE_URL == "your-project-url.supabase.co":
        print("\n⚠️  Please set SUPABASE_URL and SUPABASE_KEY environment variables!")
        exit(1)
    
    # Run analysis
    patterns = run_pattern_analysis(min_trades=50)
    
    # Save results to JSON
    if patterns:
        with open('trading_patterns_analysis.json', 'w') as f:
            json.dump(patterns, f, indent=2, default=str)
        print("\n✅ Results saved to trading_patterns_analysis.json")

