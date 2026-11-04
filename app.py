"""
Library Book Usage Analysis System
Full-Stack Flask Web Application
"""

import os
import io
import csv
import secrets
from datetime import datetime, date, timedelta
from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, jsonify, send_file, session, abort
)

from config import Config
import db
from analytics import analysis, charts

app = Flask(__name__)
app.config.from_object(Config)

# Ensure session secret key is set
if not app.secret_key:
    app.secret_key = secrets.token_hex(32)

# Initialize database on startup
with app.app_context():
    try:
        db.init_db()
    except Exception as e:
        print(f"Initial DB check warning: {e}")

# -------------------------------------------------------------
# CSRF Protection Helpers
# -------------------------------------------------------------
@app.before_request
def csrf_protect():
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(16)
    
    # Check CSRF token for state-modifying requests
    if request.method in ('POST', 'PUT', 'DELETE'):
        # Allow JSON API requests or check token
        submitted_token = request.form.get('csrf_token') or request.headers.get('X-CSRF-Token')
        if not submitted_token or submitted_token != session.get('csrf_token'):
            # Flash error and abort
            if request.is_json:
                return jsonify({'error': 'Invalid or missing CSRF token'}), 403
            flash('Security validation (CSRF) failed. Please try again.', 'danger')
            return redirect(request.referrer or url_for('dashboard'))

@app.context_processor
def inject_globals():
    """Injects common template variables."""
    borrowing_period = db.get_setting('borrowing_period_days', Config.DEFAULT_BORROW_DAYS)
    return {
        'csrf_token': session.get('csrf_token', ''),
        'borrowing_period': int(borrowing_period),
        'db_status': db.get_db_status(),
        'today_date': date.today().isoformat(),
        'app_name': 'Library Book Usage Analysis System'
    }

# -------------------------------------------------------------
# Dashboard Route
# -------------------------------------------------------------
@app.route('/')
def dashboard():
    """Main dashboard displaying summary cards, charts, and recent activity."""
    metrics = analysis.get_dashboard_metrics()
    
    # Recent loan transactions (last 6)
    recent_loans = db.query_all("""
        SELECT l.loan_id, l.issue_date, l.due_date, l.return_date,
               b.title, b.category, bw.borrower_name, bw.roll_no
        FROM loans l
        JOIN books b ON l.book_id = b.book_id
        JOIN borrowers bw ON l.borrower_id = bw.borrower_id
        ORDER BY l.loan_id DESC
        LIMIT 6;
    """)

    # Enrich recent loans with overdue status
    today = date.today().isoformat()
    for loan in recent_loans:
        loan['is_returned'] = bool(loan['return_date'])
        loan['is_overdue'] = (not loan['is_returned']) and (str(loan['due_date']) < today)

    return render_template(
        'dashboard.html',
        metrics=metrics,
        recent_loans=recent_loans,
        active_page='dashboard'
    )

# -------------------------------------------------------------
# Book Management Routes
# -------------------------------------------------------------
@app.route('/books', methods=['GET', 'POST'])
def books():
    """View all books with search, filter, and Add Book functionality."""
    if request.method == 'POST':
        # Add new book
        isbn = request.form.get('isbn', '').strip()
        title = request.form.get('title', '').strip()
        author = request.form.get('author', '').strip()
        category = request.form.get('category', '').strip()
        total_copies_raw = request.form.get('total_copies', '').strip()
        available_copies_raw = request.form.get('copies_available', '').strip()

        # Validation
        errors = []
        if not isbn or not title or not author or not category or not total_copies_raw:
            errors.append("All fields except available copies are required.")
        
        try:
            total_copies = int(total_copies_raw)
            if total_copies <= 0:
                errors.append("Total copies must be greater than zero.")
        except ValueError:
            errors.append("Total copies must be a valid positive integer.")
            total_copies = 0

        # Available copies default to total copies if not specified
        if available_copies_raw:
            try:
                copies_available = int(available_copies_raw)
                if copies_available < 0:
                    errors.append("Available copies cannot be negative.")
                elif copies_available > total_copies:
                    errors.append("Available copies cannot exceed total copies.")
            except ValueError:
                errors.append("Available copies must be a valid integer.")
                copies_available = total_copies
        else:
            copies_available = total_copies

        # Check unique ISBN
        existing_isbn = db.query_one("SELECT book_id FROM books WHERE isbn = %s;", (isbn,))
        if existing_isbn:
            errors.append(f"A book with ISBN '{isbn}' already exists in the system.")

        if errors:
            for err in errors:
                flash(err, 'danger')
            return redirect(url_for('books'))

        # Insert book
        try:
            db.execute_statement(
                """
                INSERT INTO books (isbn, title, author, category, total_copies, copies_available)
                VALUES (%s, %s, %s, %s, %s, %s);
                """,
                (isbn, title, author, category, total_copies, copies_available)
            )
            flash(f"Book '{title}' successfully added with {total_copies} copies.", 'success')
        except Exception as e:
            flash(f"Database error adding book: {str(e)}", 'danger')

        return redirect(url_for('books'))

    # GET Request: Filter & Search
    search = request.args.get('search', '').strip()
    category_filter = request.args.get('category', '').strip()

    sql = "SELECT * FROM books WHERE 1=1"
    params = []

    if category_filter:
        sql += " AND category = %s"
        params.append(category_filter)

    if search:
        sql += " AND (title LIKE %s OR author LIKE %s OR isbn LIKE %s OR category LIKE %s)"
        pattern = f"%{search}%"
        params.extend([pattern, pattern, pattern, pattern])

    sql += " ORDER BY book_id DESC;"
    books_list = db.query_all(sql, params)

    # Categories for filter dropdown
    categories = db.query_all("SELECT DISTINCT category FROM books ORDER BY category;")

    return render_template(
        'books.html',
        books=books_list,
        categories=[c['category'] for c in categories],
        search=search,
        selected_category=category_filter,
        active_page='books'
    )

@app.route('/books/edit/<int:book_id>', methods=['POST'])
def edit_book(book_id):
    """Edit book details."""
    book = db.query_one("SELECT * FROM books WHERE book_id = %s;", (book_id,))
    if not book:
        flash("Book not found.", 'danger')
        return redirect(url_for('books'))

    isbn = request.form.get('isbn', '').strip()
    title = request.form.get('title', '').strip()
    author = request.form.get('author', '').strip()
    category = request.form.get('category', '').strip()
    total_copies_raw = request.form.get('total_copies', '').strip()
    available_copies_raw = request.form.get('copies_available', '').strip()

    errors = []
    if not isbn or not title or not author or not category or not total_copies_raw or not available_copies_raw:
        errors.append("All fields are required.")

    try:
        total_copies = int(total_copies_raw)
        copies_available = int(available_copies_raw)
        if total_copies <= 0:
            errors.append("Total copies must be greater than zero.")
        if copies_available < 0:
            errors.append("Available copies cannot be negative.")
        if copies_available > total_copies:
            errors.append("Available copies cannot exceed total copies.")
            
        # Check active loans constraint: total - available cannot be less than currently active loans
        active_loans = db.query_one("SELECT COUNT(*) as cnt FROM loans WHERE book_id = %s AND return_date IS NULL;", (book_id,))
        active_count = active_loans['cnt'] if active_loans else 0
        if total_copies - copies_available < active_count:
            errors.append(f"Cannot adjust copies: Book currently has {active_count} active loan(s).")
    except ValueError:
        errors.append("Copies must be valid integers.")

    # Unique ISBN check (excluding this book)
    existing_isbn = db.query_one("SELECT book_id FROM books WHERE isbn = %s AND book_id != %s;", (isbn, book_id))
    if existing_isbn:
        errors.append(f"ISBN '{isbn}' is already assigned to another book.")

    if errors:
        for err in errors:
            flash(err, 'danger')
        return redirect(url_for('books'))

    try:
        db.execute_statement(
            """
            UPDATE books 
            SET isbn = %s, title = %s, author = %s, category = %s, total_copies = %s, copies_available = %s
            WHERE book_id = %s;
            """,
            (isbn, title, author, category, total_copies, copies_available, book_id)
        )
        flash(f"Book '{title}' successfully updated.", 'success')
    except Exception as e:
        flash(f"Database error updating book: {str(e)}", 'danger')

    return redirect(url_for('books'))

@app.route('/books/delete/<int:book_id>', methods=['POST'])
def delete_book(book_id):
    """Delete book only when no loan history prevents deletion."""
    book = db.query_one("SELECT * FROM books WHERE book_id = %s;", (book_id,))
    if not book:
        flash("Book not found.", 'danger')
        return redirect(url_for('books'))

    # Check loan history
    loan_history = db.query_one("SELECT COUNT(*) as cnt FROM loans WHERE book_id = %s;", (book_id,))
    if loan_history and loan_history['cnt'] > 0:
        flash(f"Cannot delete '{book['title']}': This book has {loan_history['cnt']} borrowing record(s) in history.", 'danger')
        return redirect(url_for('books'))

    try:
        db.execute_statement("DELETE FROM books WHERE book_id = %s;", (book_id,))
        flash(f"Book '{book['title']}' was deleted successfully.", 'success')
    except Exception as e:
        flash(f"Failed to delete book: {str(e)}", 'danger')

    return redirect(url_for('books'))

# -------------------------------------------------------------
# Borrower Management Routes
# -------------------------------------------------------------
@app.route('/borrowers', methods=['GET', 'POST'])
def borrowers():
    """View borrowers, search, and Add Borrower."""
    if request.method == 'POST':
        borrower_name = request.form.get('borrower_name', '').strip()
        roll_no = request.form.get('roll_no', '').strip()

        errors = []
        if not borrower_name or not roll_no:
            errors.append("Borrower name and roll number are required.")

        # Check unique roll number
        existing = db.query_one("SELECT borrower_id FROM borrowers WHERE roll_no = %s;", (roll_no,))
        if existing:
            errors.append(f"A borrower with Roll Number '{roll_no}' already exists.")

        if errors:
            for err in errors:
                flash(err, 'danger')
            return redirect(url_for('borrowers'))

        try:
            db.execute_statement(
                "INSERT INTO borrowers (borrower_name, roll_no) VALUES (%s, %s);",
                (borrower_name, roll_no)
            )
            flash(f"Borrower '{borrower_name}' ({roll_no}) added successfully.", 'success')
        except Exception as e:
            flash(f"Database error adding borrower: {str(e)}", 'danger')

        return redirect(url_for('borrowers'))

    # GET Request: search & list with loan counts
    search = request.args.get('search', '').strip()
    sql = """
        SELECT bw.borrower_id, bw.borrower_name, bw.roll_no,
               COUNT(l.loan_id) as total_loans,
               SUM(CASE WHEN l.return_date IS NULL THEN 1 ELSE 0 END) as active_loans
        FROM borrowers bw
        LEFT JOIN loans l ON bw.borrower_id = l.borrower_id
        WHERE 1=1
    """
    params = []
    if search:
        sql += " AND (bw.borrower_name LIKE %s OR bw.roll_no LIKE %s)"
        pattern = f"%{search}%"
        params.extend([pattern, pattern])

    sql += " GROUP BY bw.borrower_id, bw.borrower_name, bw.roll_no ORDER BY bw.borrower_id DESC;"
    borrowers_list = db.query_all(sql, params)

    return render_template(
        'borrowers.html',
        borrowers=borrowers_list,
        search=search,
        active_page='borrowers'
    )

@app.route('/borrowers/edit/<int:borrower_id>', methods=['POST'])
def edit_borrower(borrower_id):
    """Edit borrower details."""
    borrower = db.query_one("SELECT * FROM borrowers WHERE borrower_id = %s;", (borrower_id,))
    if not borrower:
        flash("Borrower not found.", 'danger')
        return redirect(url_for('borrowers'))

    borrower_name = request.form.get('borrower_name', '').strip()
    roll_no = request.form.get('roll_no', '').strip()

    errors = []
    if not borrower_name or not roll_no:
        errors.append("Borrower name and roll number cannot be empty.")

    # Unique check excluding self
    existing = db.query_one("SELECT borrower_id FROM borrowers WHERE roll_no = %s AND borrower_id != %s;", (roll_no, borrower_id))
    if existing:
        errors.append(f"Roll Number '{roll_no}' is already used by another borrower.")

    if errors:
        for err in errors:
            flash(err, 'danger')
        return redirect(url_for('borrowers'))

    try:
        db.execute_statement(
            "UPDATE borrowers SET borrower_name = %s, roll_no = %s WHERE borrower_id = %s;",
            (borrower_name, roll_no, borrower_id)
        )
        flash(f"Borrower '{borrower_name}' updated successfully.", 'success')
    except Exception as e:
        flash(f"Error updating borrower: {str(e)}", 'danger')

    return redirect(url_for('borrowers'))

@app.route('/borrowers/delete/<int:borrower_id>', methods=['POST'])
def delete_borrower(borrower_id):
    """Delete borrower only when they have NO active loans."""
    borrower = db.query_one("SELECT * FROM borrowers WHERE borrower_id = %s;", (borrower_id,))
    if not borrower:
        flash("Borrower not found.", 'danger')
        return redirect(url_for('borrowers'))

    # Check for active loans
    active_loans = db.query_one(
        "SELECT COUNT(*) as cnt FROM loans WHERE borrower_id = %s AND return_date IS NULL;",
        (borrower_id,)
    )
    if active_loans and active_loans['cnt'] > 0:
        flash(f"Cannot delete '{borrower['borrower_name']}': Borrower currently has {active_loans['cnt']} active loan(s). Please return the books first.", 'danger')
        return redirect(url_for('borrowers'))

    # Check total history
    total_loans = db.query_one("SELECT COUNT(*) as cnt FROM loans WHERE borrower_id = %s;", (borrower_id,))
    if total_loans and total_loans['cnt'] > 0:
        flash(f"Cannot delete '{borrower['borrower_name']}': Borrower has {total_loans['cnt']} past borrowing transaction(s) recorded in audit history.", 'warning')
        return redirect(url_for('borrowers'))

    try:
        db.execute_statement("DELETE FROM borrowers WHERE borrower_id = %s;", (borrower_id,))
        flash(f"Borrower '{borrower['borrower_name']}' deleted successfully.", 'success')
    except Exception as e:
        flash(f"Failed to delete borrower: {str(e)}", 'danger')

    return redirect(url_for('borrowers'))

# -------------------------------------------------------------
# Issue Book Management Routes
# -------------------------------------------------------------
@app.route('/issue', methods=['GET', 'POST'])
def issue_book():
    """Issue a book to a borrower with atomic transaction."""
    period_days = int(db.get_setting('borrowing_period_days', Config.DEFAULT_BORROW_DAYS))

    if request.method == 'POST':
        book_id_raw = request.form.get('book_id')
        borrower_id_raw = request.form.get('borrower_id')
        issue_date_str = request.form.get('issue_date', '').strip()

        errors = []
        if not book_id_raw or not borrower_id_raw:
            errors.append("Please select both a book and a borrower.")

        try:
            book_id = int(book_id_raw)
            borrower_id = int(borrower_id_raw)
        except (ValueError, TypeError):
            errors.append("Invalid book or borrower ID selected.")
            book_id = None
            borrower_id = None

        # Issue date validation
        today = date.today()
        if issue_date_str:
            try:
                issue_date = datetime.strptime(issue_date_str, '%Y-%m-%d').date()
                if issue_date > today:
                    errors.append("Issue date cannot be in the future.")
            except ValueError:
                errors.append("Invalid issue date format. Use YYYY-MM-DD.")
                issue_date = today
        else:
            issue_date = today

        # Calculate due date
        due_date = issue_date + timedelta(days=period_days)

        if not errors:
            # Check book exists and has available copies
            book = db.query_one("SELECT * FROM books WHERE book_id = %s;", (book_id,))
            borrower = db.query_one("SELECT * FROM borrowers WHERE borrower_id = %s;", (borrower_id,))

            if not book:
                errors.append("The selected book does not exist.")
            elif book['copies_available'] <= 0:
                errors.append(f"No copies available for '{book['title']}'. (Available: 0/{book['total_copies']}).")

            if not borrower:
                errors.append("The selected borrower does not exist.")

        if errors:
            for err in errors:
                flash(err, 'danger')
            return redirect(url_for('issue_book'))

        # Perform atomic issue transaction
        try:
            operations = [
                # 1. Insert loan record
                (
                    """
                    INSERT INTO loans (book_id, borrower_id, issue_date, due_date, return_date)
                    VALUES (%s, %s, %s, %s, NULL);
                    """,
                    (book_id, borrower_id, issue_date.isoformat(), due_date.isoformat())
                ),
                # 2. Decrease available copies by 1
                (
                    """
                    UPDATE books
                    SET copies_available = copies_available - 1
                    WHERE book_id = %s AND copies_available > 0;
                    """,
                    (book_id,)
                )
            ]
            db.execute_transaction(operations)
            flash(
                f"Successfully issued '{book['title']}' to {borrower['borrower_name']} ({borrower['roll_no']}). Due date: {due_date.strftime('%b %d, %Y')}.",
                'success'
            )
            return redirect(url_for('return_book'))
        except Exception as e:
            flash(f"Transaction failed during book issue: {str(e)}", 'danger')
            return redirect(url_for('issue_book'))

    # GET Request: Fetch available books and all borrowers
    books_available = db.query_all("SELECT * FROM books WHERE copies_available > 0 ORDER BY title;")
    all_books = db.query_all("SELECT * FROM books ORDER BY title;")
    borrowers_list = db.query_all("SELECT * FROM borrowers ORDER BY borrower_name;")

    today_str = date.today().isoformat()
    default_due_str = (date.today() + timedelta(days=period_days)).isoformat()

    return render_template(
        'issue_book.html',
        books_available=books_available,
        all_books=all_books,
        borrowers=borrowers_list,
        today_date=today_str,
        default_due_date=default_due_str,
        period_days=period_days,
        active_page='issue'
    )

# -------------------------------------------------------------
# Return Book Management Routes
# -------------------------------------------------------------
@app.route('/return', methods=['GET', 'POST'])
def return_book():
    """Display active loans and process book return."""
    if request.method == 'POST':
        loan_id_raw = request.form.get('loan_id')
        return_date_str = request.form.get('return_date', '').strip()

        errors = []
        try:
            loan_id = int(loan_id_raw)
        except (ValueError, TypeError):
            errors.append("Invalid loan ID specified.")
            loan_id = None

        if not errors:
            loan = db.query_one("""
                SELECT l.*, b.title, b.book_id, bw.borrower_name
                FROM loans l
                JOIN books b ON l.book_id = b.book_id
                JOIN borrowers bw ON l.borrower_id = bw.borrower_id
                WHERE l.loan_id = %s;
            """, (loan_id,))

            if not loan:
                errors.append("Loan transaction record not found.")
            elif loan['return_date'] is not None and str(loan['return_date']).strip() != '':
                errors.append(f"This loan (ID #{loan_id}) has already been returned on {loan['return_date']}.")

        if not errors:
            today = date.today()
            if return_date_str:
                try:
                    return_date = datetime.strptime(return_date_str, '%Y-%m-%d').date()
                except ValueError:
                    return_date = today
            else:
                return_date = today

            issue_date = datetime.strptime(str(loan['issue_date'])[:10], '%Y-%m-%d').date()
            if return_date < issue_date:
                errors.append(f"Return date ({return_date}) cannot be earlier than the issue date ({issue_date}).")

        if errors:
            for err in errors:
                flash(err, 'danger')
            return redirect(url_for('return_book'))

        # Atomic return transaction: Update loan return_date & Increment copies_available
        try:
            operations = [
                # 1. Update loan
                (
                    "UPDATE loans SET return_date = %s WHERE loan_id = %s AND return_date IS NULL;",
                    (return_date.isoformat(), loan_id)
                ),
                # 2. Increase available copies
                (
                    "UPDATE books SET copies_available = copies_available + 1 WHERE book_id = %s AND copies_available < total_copies;",
                    (loan['book_id'],)
                )
            ]
            db.execute_transaction(operations)
            flash(
                f"Book '{loan['title']}' returned successfully by {loan['borrower_name']}. Copies available incremented.",
                'success'
            )
        except Exception as e:
            flash(f"Transaction failed during book return: {str(e)}", 'danger')

        return redirect(url_for('return_book'))

    # GET Request: Filter & Search active loans
    search = request.args.get('search', '').strip()
    sql = """
        SELECT l.loan_id, l.book_id, l.borrower_id, l.issue_date, l.due_date, l.return_date,
               b.title, b.author, b.category, b.isbn,
               bw.borrower_name, bw.roll_no
        FROM loans l
        JOIN books b ON l.book_id = b.book_id
        JOIN borrowers bw ON l.borrower_id = bw.borrower_id
        WHERE l.return_date IS NULL
    """
    params = []
    if search:
        sql += " AND (b.title LIKE %s OR bw.borrower_name LIKE %s OR bw.roll_no LIKE %s)"
        pattern = f"%{search}%"
        params.extend([pattern, pattern, pattern])

    sql += " ORDER BY l.due_date ASC;"
    active_loans = db.query_all(sql, params)

    today = date.today()
    for item in active_loans:
        due = datetime.strptime(str(item['due_date'])[:10], '%Y-%m-%d').date()
        item['is_overdue'] = due < today
        item['days_overdue'] = (today - due).days if item['is_overdue'] else 0

    return render_template(
        'return_book.html',
        active_loans=active_loans,
        search=search,
        today_date=today.isoformat(),
        active_page='return'
    )

# -------------------------------------------------------------
# Overdue Loans Analysis Route
# -------------------------------------------------------------
@app.route('/overdue')
def overdue():
    """Overdue loans page with filtering and summary metrics."""
    borrower_id = request.args.get('borrower_id')
    category = request.args.get('category')
    search = request.args.get('search')

    data = analysis.get_overdue_analysis(
        borrower_id=borrower_id,
        category=category,
        search=search
    )

    borrowers_list = db.query_all("SELECT DISTINCT borrower_id, borrower_name, roll_no FROM borrowers ORDER BY borrower_name;")
    categories = db.query_all("SELECT DISTINCT category FROM books ORDER BY category;")

    return render_template(
        'overdue.html',
        overdue_loans=data['overdue_list'],
        total_overdue=data['total_overdue'],
        stats=data['stats'],
        borrowers=borrowers_list,
        categories=[c['category'] for c in categories],
        selected_borrower=borrower_id,
        selected_category=category,
        search=search or '',
        active_page='overdue'
    )

# -------------------------------------------------------------
# Analytics Page Route
# -------------------------------------------------------------
@app.route('/analytics')
def analytics_view():
    """Analytics page showing most borrowed, monthly trends, and categories."""
    top_n = int(request.args.get('top_n', 10))
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')

    most_borrowed = analysis.get_most_borrowed_books(top_n=top_n)
    monthly_trends = analysis.get_monthly_trends(start_date=start_date or None, end_date=end_date or None)
    category_data = analysis.get_category_analysis()

    return render_template(
        'analytics.html',
        most_borrowed=most_borrowed,
        monthly_trends=monthly_trends,
        category_data=category_data,
        top_n=top_n,
        start_date=start_date,
        end_date=end_date,
        active_page='analytics'
    )

# -------------------------------------------------------------
# Reports and CSV Export Routes
# -------------------------------------------------------------
@app.route('/reports')
def reports():
    """Reports page with table previews, date filters, and CSV downloads."""
    report_type = request.args.get('type', 'most_borrowed')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')

    report_title = "Library Report"
    records = []
    headers = []

    if report_type == 'most_borrowed':
        report_title = "Most Borrowed Books Report"
        data = analysis.get_most_borrowed_books(top_n=50)
        records = data['table']
        headers = ['Book ID', 'Title', 'Author', 'Category', 'ISBN', 'Total Copies', 'Available', 'Times Borrowed']
    elif report_type == 'overdue':
        report_title = "Overdue Loans Report"
        data = analysis.get_overdue_analysis()
        records = data['overdue_list']
        headers = ['Loan ID', 'Book Title', 'Borrower Name', 'Roll No', 'Category', 'Issue Date', 'Due Date', 'Days Overdue']
    elif report_type == 'monthly':
        report_title = "Monthly Borrowing Report"
        data = analysis.get_monthly_trends(start_date=start_date or None, end_date=end_date or None)
        records = data['table']
        headers = ['Month Period', 'Month Name', 'Total Issued', 'Unique Books', 'Unique Borrowers', 'Returned Count', 'Active Count']
    elif report_type == 'category':
        report_title = "Category-Wise Analysis Report"
        data = analysis.get_category_analysis()
        records = data['table']
        headers = ['Category', 'Total Books', 'Total Copies', 'Available Copies', 'Borrow Transactions', 'Borrow %']
    elif report_type == 'active_loans':
        report_title = "Active Loans Report"
        records = db.query_all("""
            SELECT l.loan_id, b.title, b.author, b.category, bw.borrower_name, bw.roll_no,
                   l.issue_date, l.due_date
            FROM loans l
            JOIN books b ON l.book_id = b.book_id
            JOIN borrowers bw ON l.borrower_id = bw.borrower_id
            WHERE l.return_date IS NULL
            ORDER BY l.due_date ASC;
        """)
        headers = ['Loan ID', 'Book Title', 'Author', 'Category', 'Borrower Name', 'Roll No', 'Issue Date', 'Due Date']
    elif report_type == 'returned':
        report_title = "Returned Books Report"
        sql = """
            SELECT l.loan_id, b.title, b.author, b.category, bw.borrower_name, bw.roll_no,
                   l.issue_date, l.due_date, l.return_date
            FROM loans l
            JOIN books b ON l.book_id = b.book_id
            JOIN borrowers bw ON l.borrower_id = bw.borrower_id
            WHERE l.return_date IS NOT NULL
        """
        params = []
        if start_date:
            sql += " AND l.issue_date >= %s"
            params.append(start_date)
        if end_date:
            sql += " AND l.issue_date <= %s"
            params.append(end_date)
        sql += " ORDER BY l.return_date DESC;"
        records = db.query_all(sql, params)
        headers = ['Loan ID', 'Book Title', 'Author', 'Category', 'Borrower Name', 'Roll No', 'Issue Date', 'Due Date', 'Return Date']

    return render_template(
        'reports.html',
        report_type=report_type,
        report_title=report_title,
        records=records,
        headers=headers,
        start_date=start_date,
        end_date=end_date,
        active_page='reports'
    )

@app.route('/reports/export/<report_type>')
def export_csv(report_type):
    """Exports any report as downloadable CSV."""
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')

    output = io.StringIO()
    writer = csv.writer(output)

    if report_type == 'most_borrowed':
        filename = "most_borrowed_books_report.csv"
        writer.writerow(['Book ID', 'Title', 'Author', 'Category', 'ISBN', 'Total Copies', 'Available Copies', 'Times Borrowed'])
        for row in analysis.get_most_borrowed_books(top_n=100)['table']:
            writer.writerow([row['book_id'], row['title'], row['author'], row['category'], row['isbn'], row['total_copies'], row['copies_available'], row['borrow_count']])

    elif report_type == 'overdue':
        filename = "overdue_loans_report.csv"
        writer.writerow(['Loan ID', 'Book Title', 'Borrower Name', 'Roll No', 'Category', 'Issue Date', 'Due Date', 'Days Overdue'])
        for row in analysis.get_overdue_analysis()['overdue_list']:
            writer.writerow([row['loan_id'], row['title'], row['borrower_name'], row['roll_no'], row['category'], row['issue_date'], row['due_date'], row['days_overdue']])

    elif report_type == 'monthly':
        filename = "monthly_borrowing_report.csv"
        writer.writerow(['Period', 'Month', 'Total Issued', 'Unique Books', 'Unique Borrowers', 'Returned Count', 'Active Count'])
        for row in analysis.get_monthly_trends(start_date or None, end_date or None)['table']:
            writer.writerow([row['period'], row['formatted_month'], row['total_issued'], row['unique_books'], row['unique_borrowers'], row['returned_count'], row['active_count']])

    elif report_type == 'category':
        filename = "category_analysis_report.csv"
        writer.writerow(['Category', 'Total Books', 'Total Copies', 'Available Copies', 'Borrow Transactions', 'Borrow %'])
        for row in analysis.get_category_analysis()['table']:
            writer.writerow([row['category'], row['total_books'], row['total_copies'], row['total_available'], row['borrow_transactions'], row['borrow_percentage']])

    elif report_type == 'active_loans':
        filename = "active_loans_report.csv"
        writer.writerow(['Loan ID', 'Book Title', 'Author', 'Category', 'Borrower Name', 'Roll No', 'Issue Date', 'Due Date'])
        rows = db.query_all("""
            SELECT l.loan_id, b.title, b.author, b.category, bw.borrower_name, bw.roll_no, l.issue_date, l.due_date
            FROM loans l JOIN books b ON l.book_id = b.book_id JOIN borrowers bw ON l.borrower_id = bw.borrower_id
            WHERE l.return_date IS NULL ORDER BY l.due_date ASC;
        """)
        for r in rows:
            writer.writerow([r['loan_id'], r['title'], r['author'], r['category'], r['borrower_name'], r['roll_no'], r['issue_date'], r['due_date']])

    else: # returned
        filename = "returned_books_report.csv"
        writer.writerow(['Loan ID', 'Book Title', 'Author', 'Category', 'Borrower Name', 'Roll No', 'Issue Date', 'Due Date', 'Return Date'])
        rows = db.query_all("""
            SELECT l.loan_id, b.title, b.author, b.category, bw.borrower_name, bw.roll_no, l.issue_date, l.due_date, l.return_date
            FROM loans l JOIN books b ON l.book_id = b.book_id JOIN borrowers bw ON l.borrower_id = bw.borrower_id
            WHERE l.return_date IS NOT NULL ORDER BY l.return_date DESC;
        """)
        for r in rows:
            writer.writerow([r['loan_id'], r['title'], r['author'], r['category'], r['borrower_name'], r['roll_no'], r['issue_date'], r['due_date'], r['return_date']])

    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8-sig')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=filename
    )

# -------------------------------------------------------------
# Matplotlib PNG Chart Downloads
# -------------------------------------------------------------
@app.route('/charts/download/<chart_type>')
def download_chart(chart_type):
    """Generates and downloads Matplotlib analytical charts as PNG."""
    if chart_type == 'monthly':
        buf = charts.generate_monthly_trend_chart()
        filename = 'monthly_borrowing_trends.png'
    elif chart_type == 'most_borrowed':
        top_n = int(request.args.get('top_n', 10))
        buf = charts.generate_most_borrowed_chart(top_n=top_n)
        filename = 'most_borrowed_books.png'
    elif chart_type == 'category':
        buf = charts.generate_category_pie_chart()
        filename = 'category_distribution.png'
    elif chart_type == 'loan_status':
        buf = charts.generate_loan_status_chart()
        filename = 'loan_status_breakdown.png'
    else:
        abort(404)

    return send_file(
        buf,
        mimetype='image/png',
        as_attachment=True,
        download_name=filename
    )

# -------------------------------------------------------------
# REST APIs for Chart.js Interactive Graphs
# -------------------------------------------------------------
@app.route('/api/dashboard-charts')
def api_dashboard_charts():
    """Returns aggregated datasets for all 4 dashboard Chart.js widgets."""
    trends = analysis.get_monthly_trends()
    most_borrowed = analysis.get_most_borrowed_books(top_n=8)
    category = analysis.get_category_analysis()
    loan_status = analysis.get_active_vs_returned()

    return jsonify({
        'monthly_trends': {
            'labels': trends['labels'],
            'counts': trends['counts']
        },
        'most_borrowed': {
            'labels': most_borrowed['labels'],
            'counts': most_borrowed['counts']
        },
        'category_distribution': {
            'labels': category['labels'],
            'counts': category['counts']
        },
        'loan_status': {
            'labels': loan_status['labels'],
            'counts': loan_status['counts']
        }
    })

@app.route('/api/monthly-trends')
def api_monthly_trends():
    start = request.args.get('start')
    end = request.args.get('end')
    return jsonify(analysis.get_monthly_trends(start, end))

@app.route('/api/most-borrowed')
def api_most_borrowed():
    top = int(request.args.get('top', 10))
    return jsonify(analysis.get_most_borrowed_books(top_n=top))

# -------------------------------------------------------------
# Settings Route
# -------------------------------------------------------------
@app.route('/settings', methods=['GET', 'POST'])
def settings():
    """Settings page for configuring borrowing duration and viewing DB status."""
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'update_period':
            period_raw = request.form.get('borrowing_period', '').strip()
            try:
                period = int(period_raw)
                if period <= 0:
                    flash("Borrowing duration must be greater than zero days.", 'danger')
                elif period > 365:
                    flash("Borrowing duration cannot exceed 365 days.", 'danger')
                else:
                    db.set_setting('borrowing_period_days', period)
                    flash(f"Default borrowing duration successfully updated to {period} days.", 'success')
            except ValueError:
                flash("Please provide a valid integer number of days.", 'danger')

        elif action == 'test_db':
            status = db.get_db_status()
            if status['connected']:
                flash(f"Database connection healthy! Connected to {status['active_engine']} ({status['version']}).", 'success')
            else:
                flash(f"Database connection issue: {status.get('error', 'Unknown error')}", 'danger')

        return redirect(url_for('settings'))

    period = int(db.get_setting('borrowing_period_days', Config.DEFAULT_BORROW_DAYS))
    db_info = db.get_db_status()

    return render_template(
        'settings.html',
        borrowing_period=period,
        db_info=db_info,
        active_page='settings'
    )

# -------------------------------------------------------------
# Error Handlers
# -------------------------------------------------------------
@app.errorhandler(404)
def page_not_found(e):
    return render_template('base.html', not_found=True, active_page=''), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('base.html', server_error=True, active_page=''), 500

if __name__ == '__main__':
    # Start web server on port 5000
    app.run(host='127.0.0.1', port=5000, debug=False)
