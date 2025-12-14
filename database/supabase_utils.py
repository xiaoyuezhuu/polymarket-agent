"""
Utility functions for interacting with Supabase
"""

from typing import List, Dict, Any, Optional
from supabase import Client


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

