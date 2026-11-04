"""
Analytics and Statistical Module for Library Book Usage Analysis System.
Utilizes Pandas for data manipulation, grouping, and aggregation.
Utilizes NumPy for statistical calculations (mean, std, median, percentiles).
"""

import pandas as pd
import numpy as np
from datetime import datetime, date
import db

def fetch_dataframes():
    """
    Fetches raw tables from database into Pandas DataFrames.
    Ensures correct types for dates and numbers.
    """
    # Fetch Books
    books_data = db.query_all("SELECT book_id, isbn, title, author, category, total_copies, copies_available FROM books;")
    df_books = pd.DataFrame(books_data)
    if df_books.empty:
        df_books = pd.DataFrame(columns=['book_id', 'isbn', 'title', 'author', 'category', 'total_copies', 'copies_available'])
    else:
        df_books['total_copies'] = pd.to_numeric(df_books['total_copies'], errors='coerce').fillna(0).astype(int)
        df_books['copies_available'] = pd.to_numeric(df_books['copies_available'], errors='coerce').fillna(0).astype(int)

    # Fetch Borrowers
    borrowers_data = db.query_all("SELECT borrower_id, borrower_name, roll_no FROM borrowers;")
    df_borrowers = pd.DataFrame(borrowers_data)
    if df_borrowers.empty:
        df_borrowers = pd.DataFrame(columns=['borrower_id', 'borrower_name', 'roll_no'])

    # Fetch Loans
    loans_data = db.query_all("""
        SELECT l.loan_id, l.book_id, l.borrower_id, l.issue_date, l.due_date, l.return_date,
               b.title, b.author, b.category, b.isbn,
               bw.borrower_name, bw.roll_no
        FROM loans l
        JOIN books b ON l.book_id = b.book_id
        JOIN borrowers bw ON l.borrower_id = bw.borrower_id;
    """)
    df_loans = pd.DataFrame(loans_data)
    if df_loans.empty:
        df_loans = pd.DataFrame(columns=[
            'loan_id', 'book_id', 'borrower_id', 'issue_date', 'due_date', 'return_date',
            'title', 'author', 'category', 'isbn', 'borrower_name', 'roll_no'
        ])
    else:
        # Convert date columns to datetime
        df_loans['issue_date_dt'] = pd.to_datetime(df_loans['issue_date'], errors='coerce')
        df_loans['due_date_dt'] = pd.to_datetime(df_loans['due_date'], errors='coerce')
        df_loans['return_date_dt'] = pd.to_datetime(df_loans['return_date'], errors='coerce')
        
        # Calculate status flags
        today = pd.to_datetime(date.today())
        df_loans['is_returned'] = df_loans['return_date'].notna() & (df_loans['return_date'] != '')
        df_loans['is_active'] = ~df_loans['is_returned']
        df_loans['is_overdue'] = df_loans['is_active'] & (df_loans['due_date_dt'] < today)
        
        # Calculate days overdue for active loans
        df_loans['days_overdue'] = 0
        overdue_mask = df_loans['is_overdue']
        if overdue_mask.any():
            df_loans.loc[overdue_mask, 'days_overdue'] = (
                today - df_loans.loc[overdue_mask, 'due_date_dt']
            ).dt.days.astype(int)

    return df_books, df_borrowers, df_loans

def get_dashboard_metrics():
    """
    Computes key performance indicators for the library dashboard:
    1. Total Books
    2. Total Borrowers
    3. Available Copies
    4. Active Loans
    5. Overdue Loans
    6. Total Borrowing Transactions
    """
    df_books, df_borrowers, df_loans = fetch_dataframes()

    total_books = int(df_books['book_id'].nunique()) if not df_books.empty else 0
    total_copies = int(df_books['total_copies'].sum()) if not df_books.empty else 0
    available_copies = int(df_books['copies_available'].sum()) if not df_books.empty else 0
    total_borrowers = int(df_borrowers['borrower_id'].nunique()) if not df_borrowers.empty else 0
    total_transactions = len(df_loans)
    
    if not df_loans.empty:
        active_loans = int(df_loans['is_active'].sum())
        overdue_loans = int(df_loans['is_overdue'].sum())
        returned_loans = int(df_loans['is_returned'].sum())
    else:
        active_loans = 0
        overdue_loans = 0
        returned_loans = 0

    return {
        'total_books': total_books,
        'total_copies': total_copies,
        'total_borrowers': total_borrowers,
        'available_copies': available_copies,
        'active_loans': active_loans,
        'overdue_loans': overdue_loans,
        'returned_loans': returned_loans,
        'total_transactions': total_transactions
    }

def get_monthly_trends(start_date=None, end_date=None):
    """
    Analyzes monthly borrowing transactions using Pandas and NumPy.
    - Groups loans by Year-Month (e.g. '2026-06')
    - Calculates total books issued each month
    - Computes descriptive statistics (mean, std, median, min, max)
    - Supports date-range filtering
    """
    _, _, df_loans = fetch_dataframes()
    if df_loans.empty:
        return {
            'labels': [],
            'counts': [],
            'table': [],
            'stats': {'mean': 0.0, 'std': 0.0, 'median': 0.0, 'max': 0, 'min': 0, 'total': 0}
        }

    filtered_df = df_loans.copy()
    if start_date:
        filtered_df = filtered_df[filtered_df['issue_date'] >= str(start_date)]
    if end_date:
        filtered_df = filtered_df[filtered_df['issue_date'] <= str(end_date)]

    if filtered_df.empty:
        return {
            'labels': [],
            'counts': [],
            'table': [],
            'stats': {'mean': 0.0, 'std': 0.0, 'median': 0.0, 'max': 0, 'min': 0, 'total': 0}
        }

    # Group by month
    filtered_df['year_month'] = filtered_df['issue_date_dt'].dt.to_period('M').astype(str)
    monthly_grouped = filtered_df.groupby('year_month').agg(
        total_issued=('loan_id', 'count'),
        unique_books=('book_id', 'nunique'),
        unique_borrowers=('borrower_id', 'nunique'),
        returned_count=('is_returned', lambda x: int(x.sum())),
        active_count=('is_active', lambda x: int(x.sum()))
    ).reset_index().sort_values('year_month')

    labels = monthly_grouped['year_month'].tolist()
    counts = monthly_grouped['total_issued'].tolist()

    # NumPy calculations
    counts_arr = np.array(counts, dtype=float)
    stats = {
        'mean': round(float(np.mean(counts_arr)), 2) if len(counts_arr) > 0 else 0.0,
        'std': round(float(np.std(counts_arr, ddof=1)), 2) if len(counts_arr) > 1 else 0.0,
        'median': round(float(np.median(counts_arr)), 2) if len(counts_arr) > 0 else 0.0,
        'max': int(np.max(counts_arr)) if len(counts_arr) > 0 else 0,
        'min': int(np.min(counts_arr)) if len(counts_arr) > 0 else 0,
        'total': int(np.sum(counts_arr)) if len(counts_arr) > 0 else 0
    }

    # Format table records with month names
    table_records = []
    for _, row in monthly_grouped.iterrows():
        try:
            month_dt = datetime.strptime(row['year_month'], '%Y-%m')
            formatted_month = month_dt.strftime('%B %Y')
        except Exception:
            formatted_month = row['year_month']
            
        table_records.append({
            'period': row['year_month'],
            'formatted_month': formatted_month,
            'total_issued': int(row['total_issued']),
            'unique_books': int(row['unique_books']),
            'unique_borrowers': int(row['unique_borrowers']),
            'returned_count': int(row['returned_count']),
            'active_count': int(row['active_count'])
        })

    return {
        'labels': labels,
        'counts': counts,
        'table': table_records,
        'stats': stats
    }

def get_most_borrowed_books(top_n=10):
    """
    Identifies the most borrowed books using loan transaction records.
    Displays Book Title, Author, Category, Total Times Borrowed.
    """
    df_books, _, df_loans = fetch_dataframes()
    if df_loans.empty or df_books.empty:
        return {'labels': [], 'counts': [], 'table': []}

    # Count borrow frequency per book_id
    borrow_counts = df_loans.groupby('book_id').size().reset_index(name='borrow_count')

    # Merge with books dataframe
    merged = pd.merge(df_books, borrow_counts, on='book_id', how='left')
    merged['borrow_count'] = merged['borrow_count'].fillna(0).astype(int)
    
    # Sort descending
    sorted_df = merged.sort_values(by=['borrow_count', 'title'], ascending=[False, True])
    
    if top_n:
        sorted_df = sorted_df.head(top_n)

    labels = sorted_df['title'].tolist()
    counts = sorted_df['borrow_count'].tolist()
    
    # Prepare table dict
    table = sorted_df[['book_id', 'title', 'author', 'category', 'isbn', 'total_copies', 'copies_available', 'borrow_count']].to_dict(orient='records')
    
    return {
        'labels': labels,
        'counts': counts,
        'table': table
    }

def get_category_analysis():
    """
    Analyzes book categories using Pandas and NumPy.
    Displays:
    - Category Name
    - Total Books
    - Total Available Copies
    - Total Borrowing Transactions
    - Borrowing percentage
    """
    df_books, _, df_loans = fetch_dataframes()
    if df_books.empty:
        return {'labels': [], 'counts': [], 'table': [], 'stats': {}}

    # Group books by category
    cat_books = df_books.groupby('category').agg(
        total_books=('book_id', 'count'),
        total_copies=('total_copies', 'sum'),
        total_available=('copies_available', 'sum')
    ).reset_index()

    # Group loans by category
    if not df_loans.empty:
        cat_loans = df_loans.groupby('category').size().reset_index(name='borrow_transactions')
        merged = pd.merge(cat_books, cat_loans, on='category', how='left')
        merged['borrow_transactions'] = merged['borrow_transactions'].fillna(0).astype(int)
    else:
        merged = cat_books.copy()
        merged['borrow_transactions'] = 0

    merged = merged.sort_values(by='borrow_transactions', ascending=False)
    
    total_borrows = merged['borrow_transactions'].sum()
    if total_borrows > 0:
        merged['borrow_percentage'] = (merged['borrow_transactions'] / total_borrows * 100).round(1)
    else:
        merged['borrow_percentage'] = 0.0

    labels = merged['category'].tolist()
    counts = merged['borrow_transactions'].tolist()
    available = merged['total_available'].tolist()
    table = merged.to_dict(orient='records')

    # NumPy statistics on category transactions
    trans_arr = np.array(counts, dtype=float)
    stats = {
        'total_categories': len(merged),
        'mean_transactions': round(float(np.mean(trans_arr)), 2) if len(trans_arr) > 0 else 0.0,
        'std_transactions': round(float(np.std(trans_arr, ddof=1)), 2) if len(trans_arr) > 1 else 0.0,
        'max_transactions': int(np.max(trans_arr)) if len(trans_arr) > 0 else 0,
        'top_category': labels[0] if labels else 'N/A'
    }

    return {
        'labels': labels,
        'counts': counts,
        'available': available,
        'table': table,
        'stats': stats
    }

def get_overdue_analysis(borrower_id=None, category=None, search=None):
    """
    Filters and analyzes overdue loans:
    Loans where return_date IS NULL and due_date < CURDATE()
    """
    _, _, df_loans = fetch_dataframes()
    if df_loans.empty:
        return {'total_overdue': 0, 'overdue_list': [], 'stats': {}}

    overdue_df = df_loans[df_loans['is_overdue']].copy()
    
    if borrower_id:
        overdue_df = overdue_df[overdue_df['borrower_id'] == int(borrower_id)]
    if category:
        overdue_df = overdue_df[overdue_df['category'] == str(category)]
    if search:
        s = search.lower().strip()
        overdue_df = overdue_df[
            overdue_df['title'].str.lower().str.contains(s, na=False) |
            overdue_df['borrower_name'].str.lower().str.contains(s, na=False) |
            overdue_df['roll_no'].str.lower().str.contains(s, na=False)
        ]

    total_overdue = len(overdue_df)
    
    # Sort by days overdue descending
    overdue_df = overdue_df.sort_values('days_overdue', ascending=False)
    
    records = overdue_df[[
        'loan_id', 'book_id', 'title', 'borrower_id', 'borrower_name', 'roll_no',
        'category', 'issue_date', 'due_date', 'days_overdue'
    ]].to_dict(orient='records')

    # Statistics using NumPy
    if total_overdue > 0:
        days_arr = overdue_df['days_overdue'].to_numpy(dtype=float)
        stats = {
            'avg_days_overdue': round(float(np.mean(days_arr)), 1),
            'max_days_overdue': int(np.max(days_arr)),
            'min_days_overdue': int(np.min(days_arr))
        }
    else:
        stats = {'avg_days_overdue': 0, 'max_days_overdue': 0, 'min_days_overdue': 0}

    return {
        'total_overdue': total_overdue,
        'overdue_list': records,
        'stats': stats
    }

def get_active_vs_returned():
    """
    Returns breakdown of loans: Active (on-time), Overdue, and Returned.
    """
    _, _, df_loans = fetch_dataframes()
    if df_loans.empty:
        return {
            'labels': ['Returned', 'Active (On-time)', 'Overdue'],
            'counts': [0, 0, 0],
            'returned_pct': 0.0
        }

    returned = int(df_loans['is_returned'].sum())
    overdue = int(df_loans['is_overdue'].sum())
    # Active on-time = active loans that are NOT overdue
    active_ontime = int((df_loans['is_active'] & ~df_loans['is_overdue']).sum())
    
    total = len(df_loans)
    returned_pct = round((returned / total * 100), 1) if total > 0 else 0.0

    return {
        'labels': ['Returned', 'Active (On-Time)', 'Overdue'],
        'counts': [returned, active_ontime, overdue],
        'returned_pct': returned_pct
    }
