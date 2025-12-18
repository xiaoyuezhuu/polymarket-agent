"""
Utility functions for interacting with Supabase
"""

from typing import List, Dict, Any, Optional
from supabase import Client
import time
import time


def retrieve_all_rows(
    supabase: Client,
    table_name: str,
    columns: str = "*",
    filters: Optional[Dict[str, Any]] = None,
    order_by: Optional[str] = None,
    ascending: bool = True,
    batch_size: int = 1000
) -> List[Dict[str, Any]]:
    """
    Retrieve all rows from a Supabase table, bypassing the default 1000 row limit.
    
    This function automatically handles pagination to fetch all rows from a table.
    
    Args:
        supabase: Supabase client instance
        table_name: Name of the table to query
        columns: Columns to select (default: "*" for all columns)
        filters: Optional dict of filters to apply (e.g., {"active": True})
        order_by: Optional column name to order by
        ascending: Sort order when order_by is specified (default: True)
        batch_size: Number of rows to fetch per batch (default: 1000, max supported by Supabase)
    
    Returns:
        List of all rows as dictionaries
    
    Example:
        # Get all active markets
        markets = retrieve_all_rows(
            supabase, 
            "markets",
            columns="condition_id,question,active",
            filters={"active": True}
        )
        
        # Get all users ordered by total volume
        users = retrieve_all_rows(
            supabase,
            "users",
            order_by="total_volume",
            ascending=False
        )
    """
    all_rows = []
    offset = 0
    
    while True:
        # Build the query
        query = supabase.table(table_name).select(columns)
        
        # Apply filters if provided
        if filters:
            for column, value in filters.items():
                query = query.eq(column, value)
        
        # Apply ordering if provided
        if order_by:
            query = query.order(order_by, desc=(not ascending))
        
        # Apply pagination
        query = query.range(offset, offset + batch_size - 1)
        
        # Execute query
        response = query.execute()
        batch = response.data
        
        # If no rows returned, we've fetched everything
        if not batch or len(batch) == 0:
            break
        
        all_rows.extend(batch)
        
        # If we got fewer rows than batch_size, we've reached the end
        if len(batch) < batch_size:
            break
        
        # Move to next batch
        offset += batch_size
    
    return all_rows


def retrieve_all_distinct_values(
    supabase: Client,
    table_name: str,
    column_name: str,
    filters: Optional[Dict[str, Any]] = None
) -> List[Any]:
    """
    Retrieve all distinct values for a specific column from a Supabase table.
    
    Args:
        supabase: Supabase client instance
        table_name: Name of the table to query
        column_name: Name of the column to get distinct values from
        filters: Optional dict of filters to apply
    
    Returns:
        List of distinct values
    
    Example:
        # Get all unique condition_ids from markets
        condition_ids = retrieve_all_distinct_values(
            supabase,
            "markets",
            "condition_id"
        )
    """
    rows = retrieve_all_rows(
        supabase,
        table_name,
        columns=column_name,
        filters=filters
    )
    
    # Extract unique values
    distinct_values = list(set(row[column_name] for row in rows if row.get(column_name) is not None))
    
    return distinct_values


def refresh_recent_markets(supabase: Client) -> bool:
    """
    Refresh the recent_markets materialized view.
    
    Call this function after bulk data updates to ensure the recent_markets
    view has the latest data.
    
    Args:
        supabase: Supabase client instance
    
    Returns:
        True if refresh was successful, False otherwise
    
    Example:
        # After loading new markets
        load_events_with_markets(limit=1000)
        
        # Refresh the view
        refresh_recent_markets(supabase)
    """
    try:
        supabase.rpc('refresh_recent_markets').execute()
        print("✓ Materialized view 'recent_markets' refreshed successfully")
        return True
    except Exception as e:
        print(f"✗ Error refreshing recent_markets view: {e}")
        return False


def refresh_pnl_views(supabase: Client) -> bool:
    """
    Refresh the PNL materialized views (user_pnl_90d and user_total_pnl_90d).
    
    Call this function after loading new trade data to update PNL calculations.
    
    Args:
        supabase: Supabase client instance
    
    Returns:
        True if refresh was successful, False otherwise
    
    Example:
        # After loading trades
        load_trades_from_markets()
        
        # Refresh PNL calculations
        refresh_pnl_views(supabase)
    """
    try:
        supabase.rpc('refresh_pnl_views').execute()
        print("✓ PNL materialized views refreshed successfully")
        return True
    except Exception as e:
        print(f"✗ Error refreshing PNL views: {e}")
        return False


def get_recent_markets_count(supabase: Client) -> int:
    """
    Get the count of markets in the recent_markets view.
    
    Args:
        supabase: Supabase client instance
    
    Returns:
        Number of markets in recent_markets view
    """
    try:
        result = supabase.table('recent_markets').select('*', count='exact').execute()
        return result.count if hasattr(result, 'count') else len(result.data)
    except Exception as e:
        print(f"✗ Error getting recent_markets count: {e}")
        return 0


def bulk_insert(
    supabase: Client,
    table_name: str,
    records: List[Dict[str, Any]],
    chunk_size: int = 1000,
    ignore_duplicates: bool = True,
    show_progress: bool = False
) -> int:
    """
    Bulk insert records into a Supabase table with automatic chunking.
    Much faster than inserting one-by-one.
    
    Args:
        supabase: Supabase client instance
        table_name: Name of the table to insert into
        records: List of records (dicts) to insert
        chunk_size: Number of records per chunk (default: 1000)
        ignore_duplicates: If True, skip duplicate key errors (default: True)
        show_progress: If True, print progress messages (default: False)
    
    Returns:
        Number of successfully inserted records
    
    Example:
        trades = [
            {"proxy_wallet": "0x123...", "side": "BUY", "price": 0.5, ...},
            {"proxy_wallet": "0x456...", "side": "SELL", "price": 0.6, ...},
            # ... thousands more
        ]
        count = bulk_insert(supabase, "trades", trades, chunk_size=500)
        print(f"Inserted {count} trades")
    """
    if not records:
        return 0
    
    total_inserted = 0
    num_chunks = (len(records) + chunk_size - 1) // chunk_size
    
    if show_progress:
        print(f"  → Bulk inserting {len(records)} records in {num_chunks} chunks of {chunk_size}...")
    
    for i in range(0, len(records), chunk_size):
        chunk = records[i:i + chunk_size]
        chunk_num = (i // chunk_size) + 1
        
        try:
            result = supabase.table(table_name).insert(chunk).execute()
            inserted = len(result.data) if result.data else len(chunk)
            total_inserted += inserted
            
            if show_progress:
                print(f"    ✓ Chunk {chunk_num}/{num_chunks}: inserted {inserted}/{len(chunk)} records")
                
        except Exception as e:
            error_msg = str(e).lower()
            
            if show_progress:
                print(f"    ⚠️  Chunk {chunk_num}/{num_chunks}: bulk failed - {str(e)[:100]}")
            
            # Strategy: Try smaller chunks first (100 records) before one-by-one
            if len(chunk) > 100:
                if show_progress:
                    print(f"    → Trying smaller chunks (100 records)...")
                
                small_chunk_size = 100
                for j in range(0, len(chunk), small_chunk_size):
                    small_chunk = chunk[j:j + small_chunk_size]
                    try:
                        result = supabase.table(table_name).insert(small_chunk).execute()
                        inserted = len(result.data) if result.data else len(small_chunk)
                        total_inserted += inserted
                        if show_progress:
                            print(f"      ✓ Small chunk: inserted {inserted}/{len(small_chunk)}")
                    except Exception as e_small:
                        # If small chunk also fails, go one-by-one for this small chunk
                        for record in small_chunk:
                            try:
                                supabase.table(table_name).insert(record).execute()
                                total_inserted += 1
                            except Exception as e2:
                                if ignore_duplicates and ('duplicate' in str(e2).lower() or 'unique' in str(e2).lower()):
                                    continue
                continue  # Skip the one-by-one section below
            
            # For smaller chunks or if small chunks failed, try inserting records one-by-one as fallback
            if show_progress:
                print(f"    → Trying one-by-one insertion for {len(chunk)} records...")
            
            one_by_one_inserted = 0
            duplicates_skipped = 0
            for idx, record in enumerate(chunk):
                try:
                    supabase.table(table_name).insert(record).execute()
                    total_inserted += 1
                    one_by_one_inserted += 1
                    
                    # Show progress every 100 records for large chunks
                    if show_progress and one_by_one_inserted % 100 == 0:
                        print(f"      ... {one_by_one_inserted}/{len(chunk)} inserted")
                        
                except Exception as e2:
                    error_msg2 = str(e2).lower()
                    if ignore_duplicates and ('duplicate' in error_msg2 or 'unique' in error_msg2):
                        duplicates_skipped += 1
                        continue
                    # Skip record with other errors
                    if show_progress and idx < 5:  # Only show first 5 errors
                        print(f"      ✗ Error: {str(e2)[:80]}")
            
            if show_progress:
                print(f"    ✓ One-by-one: inserted {one_by_one_inserted}/{len(chunk)} records ({duplicates_skipped} duplicates skipped)")
    
    return total_inserted


def bulk_upsert(
    supabase: Client,
    table_name: str,
    records: List[Dict[str, Any]],
    on_conflict: str,
    chunk_size: int = 1000,
    show_progress: bool = False
) -> int:
    """
    Bulk upsert (insert or update) records into a Supabase table.
    
    Args:
        supabase: Supabase client instance
        table_name: Name of the table to upsert into
        records: List of records (dicts) to upsert
        on_conflict: Column name(s) to check for conflicts (e.g., "id" or "proxy_wallet")
        chunk_size: Number of records per chunk (default: 1000)
        show_progress: If True, print progress messages (default: False)
    
    Returns:
        Number of successfully upserted records
    
    Example:
        users = [
            {"proxy_wallet": "0x123...", "total_trades": 10, ...},
            {"proxy_wallet": "0x456...", "total_trades": 5, ...},
        ]
        count = bulk_upsert(supabase, "users", users, on_conflict="proxy_wallet")
    """
    if not records:
        return 0
    
    total_upserted = 0
    num_chunks = (len(records) + chunk_size - 1) // chunk_size
    
    for i in range(0, len(records), chunk_size):
        chunk = records[i:i + chunk_size]
        chunk_num = (i // chunk_size) + 1
        
        try:
            result = supabase.table(table_name).upsert(
                chunk,
                on_conflict=on_conflict
            ).execute()
            
            upserted = len(result.data) if result.data else len(chunk)
            total_upserted += upserted
            
            if show_progress:
                print(f"  ✓ Chunk {chunk_num}/{num_chunks}: upserted {upserted} records")
                
        except Exception as e:
            if show_progress:
                print(f"  ⚠️  Chunk {chunk_num}/{num_chunks}: error - {e}")
            
            # Fallback to one-by-one
            for record in chunk:
                try:
                    supabase.table(table_name).upsert(
                        record,
                        on_conflict=on_conflict
                    ).execute()
                    total_upserted += 1
                except Exception as e2:
                    if show_progress:
                        print(f"    ✗ Error upserting record: {e2}")
    
    return total_upserted

