"""
Comprehensive Test Suite for Library Book Usage Analysis System.
Tests all routes, business logic, validation rules, analytics, and exports.
"""

import unittest
from datetime import date, timedelta
from app import app
import db
from analytics import analysis, charts

class LibrarySystemTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        cls.client = app.test_client()
        # Initialize DB with sample data
        db.init_db()

    def test_01_database_sample_data(self):
        """Verify minimum sample data counts meet project specifications."""
        books = db.query_one("SELECT COUNT(*) as cnt FROM books;")
        borrowers = db.query_one("SELECT COUNT(*) as cnt FROM borrowers;")
        loans = db.query_one("SELECT COUNT(*) as cnt FROM loans;")

        self.assertGreaterEqual(books['cnt'], 15, "Expected at least 15 books.")
        self.assertGreaterEqual(borrowers['cnt'], 10, "Expected at least 10 borrowers.")
        self.assertGreaterEqual(loans['cnt'], 25, "Expected at least 25 loans.")
        print(f" Sample data verified: {books['cnt']} books, {borrowers['cnt']} borrowers, {loans['cnt']} loans.")

    def test_02_dashboard_metrics(self):
        """Verify dashboard route and dynamic metrics calculation."""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Library Book Usage Analysis System", response.data)
        self.assertIn(b"Total Books", response.data)
        self.assertIn(b"Available Copies", response.data)

        metrics = analysis.get_dashboard_metrics()
        self.assertGreater(metrics['total_books'], 0)
        self.assertGreater(metrics['total_borrowers'], 0)
        self.assertGreater(metrics['total_transactions'], 0)
        self.assertGreater(metrics['overdue_loans'], 0)
        print(f" Dashboard metrics verified: {metrics}")

    def test_03_dashboard_api(self):
        """Verify Chart.js REST API payload."""
        response = self.client.get('/api/dashboard-charts')
        self.assertEqual(response.status_code, 200)
        json_data = response.get_json()
        self.assertIn('monthly_trends', json_data)
        self.assertIn('most_borrowed', json_data)
        self.assertIn('category_distribution', json_data)
        self.assertIn('loan_status', json_data)
        self.assertGreater(len(json_data['monthly_trends']['labels']), 0)
        print(" Dashboard Chart.js API payload verified.")

    def test_04_book_management_crud_and_validation(self):
        """Verify book additions, unique ISBN checks, copy constraints, and delete restrictions."""
        # Get CSRF token
        with self.client.session_transaction() as sess:
            csrf_token = sess.get('csrf_token', '')

        # 1. Add valid book
        test_isbn = f"978-99999999{date.today().strftime('%m%d%S')}"
        response = self.client.post('/books', data={
            'csrf_token': csrf_token,
            'isbn': test_isbn,
            'title': 'Automated Test Book',
            'author': 'Test Author',
            'category': 'Computer Science',
            'total_copies': '5',
            'copies_available': '5'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Automated Test Book", response.data)

        # 2. Add duplicate ISBN -> must be rejected
        dup_response = self.client.post('/books', data={
            'csrf_token': csrf_token,
            'isbn': test_isbn,
            'title': 'Duplicate ISBN Book',
            'author': 'Another Author',
            'category': 'Computer Science',
            'total_copies': '3',
            'copies_available': '3'
        }, follow_redirects=True)
        self.assertIn(b"already exists", dup_response.data)

        # Fetch created book
        book = db.query_one("SELECT * FROM books WHERE isbn = %s;", (test_isbn,))
        self.assertIsNotNone(book)

        # 3. Edit book
        edit_response = self.client.post(f'/books/edit/{book["book_id"]}', data={
            'csrf_token': csrf_token,
            'isbn': test_isbn,
            'title': 'Automated Test Book (Updated)',
            'author': 'Test Author Updated',
            'category': 'Computer Science',
            'total_copies': '6',
            'copies_available': '6'
        }, follow_redirects=True)
        self.assertIn(b"successfully updated", edit_response.data)

        # 4. Attempt to delete book with loan history (Book ID 1 has loan history)
        del_fail_resp = self.client.post('/books/delete/1', data={'csrf_token': csrf_token}, follow_redirects=True)
        self.assertIn(b"borrowing record(s) in history", del_fail_resp.data)

        # 5. Delete newly created book with NO loans -> should succeed
        del_ok_resp = self.client.post(f'/books/delete/{book["book_id"]}', data={'csrf_token': csrf_token}, follow_redirects=True)
        self.assertIn(b"deleted successfully", del_ok_resp.data)
        print(" Book management CRUD & validation rules passed.")

    def test_05_borrower_management_crud_and_validation(self):
        """Verify borrower creation, unique roll number, edit, and deletion restrictions."""
        with self.client.session_transaction() as sess:
            csrf_token = sess.get('csrf_token', '')

        test_roll = f"TEST-{date.today().strftime('%m%d%S')}"
        # 1. Add borrower
        response = self.client.post('/borrowers', data={
            'csrf_token': csrf_token,
            'borrower_name': 'Test Student',
            'roll_no': test_roll
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Test Student", response.data)

        # 2. Duplicate roll number -> rejected
        dup_resp = self.client.post('/borrowers', data={
            'csrf_token': csrf_token,
            'borrower_name': 'Another Student',
            'roll_no': test_roll
        }, follow_redirects=True)
        self.assertIn(b"already exists", dup_resp.data)

        # Fetch borrower
        borrower = db.query_one("SELECT * FROM borrowers WHERE roll_no = %s;", (test_roll,))
        self.assertIsNotNone(borrower)

        # 3. Edit borrower
        edit_resp = self.client.post(f'/borrowers/edit/{borrower["borrower_id"]}', data={
            'csrf_token': csrf_token,
            'borrower_name': 'Test Student (Edited)',
            'roll_no': test_roll
        }, follow_redirects=True)
        self.assertIn(b"updated successfully", edit_resp.data)

        # 4. Attempt to delete borrower with active loans (Borrower ID 2 has active loans)
        del_fail_resp = self.client.post('/borrowers/delete/2', data={'csrf_token': csrf_token}, follow_redirects=True)
        self.assertIn(b"active loan(s)", del_fail_resp.data)

        # 5. Delete test borrower without loans -> should succeed
        del_ok_resp = self.client.post(f'/borrowers/delete/{borrower["borrower_id"]}', data={'csrf_token': csrf_token}, follow_redirects=True)
        self.assertIn(b"deleted successfully", del_ok_resp.data)
        print(" Borrower management CRUD & validation rules passed.")

    def test_06_issue_and_return_transaction_consistency(self):
        """Verify book issue decreases available copies by 1 and return increases it by 1."""
        with self.client.session_transaction() as sess:
            csrf_token = sess.get('csrf_token', '')

        # Book ID 9 (Sanford Weisberg, Applied Linear Regression) initially has 4 available copies
        book_before = db.query_one("SELECT copies_available, total_copies FROM books WHERE book_id = 9;")
        initial_available = book_before['copies_available']
        self.assertGreater(initial_available, 0)

        # Issue book to Borrower 1
        issue_resp = self.client.post('/issue', data={
            'csrf_token': csrf_token,
            'book_id': '9',
            'borrower_id': '1',
            'issue_date': date.today().isoformat()
        }, follow_redirects=True)
        self.assertEqual(issue_resp.status_code, 200)

        # Verify copies decreased by exactly 1
        book_after_issue = db.query_one("SELECT copies_available FROM books WHERE book_id = 9;")
        self.assertEqual(book_after_issue['copies_available'], initial_available - 1)

        # Find the newly created active loan
        new_loan = db.query_one(
            "SELECT loan_id, issue_date, due_date, return_date FROM loans WHERE book_id = 9 AND borrower_id = 1 AND return_date IS NULL ORDER BY loan_id DESC;"
        )
        self.assertIsNotNone(new_loan)
        loan_id = new_loan['loan_id']

        # Return the book
        return_resp = self.client.post('/return', data={
            'csrf_token': csrf_token,
            'loan_id': str(loan_id),
            'return_date': date.today().isoformat()
        }, follow_redirects=True)
        self.assertEqual(return_resp.status_code, 200)
        self.assertIn(b"returned successfully", return_resp.data)

        # Verify copies restored by exactly 1
        book_after_return = db.query_one("SELECT copies_available FROM books WHERE book_id = 9;")
        self.assertEqual(book_after_return['copies_available'], initial_available)

        # Verify loan record has return_date set
        loan_returned = db.query_one("SELECT return_date FROM loans WHERE loan_id = %s;", (loan_id,))
        self.assertIsNotNone(loan_returned['return_date'])

        # Attempt to return again -> must fail
        double_return_resp = self.client.post('/return', data={
            'csrf_token': csrf_token,
            'loan_id': str(loan_id),
            'return_date': date.today().isoformat()
        }, follow_redirects=True)
        self.assertIn(b"already been returned", double_return_resp.data)

        # Attempt return date earlier than issue date -> must fail
        # Issue another loan to test invalid date
        self.client.post('/issue', data={
            'csrf_token': csrf_token,
            'book_id': '9',
            'borrower_id': '1',
            'issue_date': date.today().isoformat()
        })
        loan2 = db.query_one("SELECT loan_id FROM loans WHERE book_id = 9 AND borrower_id = 1 AND return_date IS NULL ORDER BY loan_id DESC;")
        earlier_date = (date.today() - timedelta(days=5)).isoformat()
        invalid_return_resp = self.client.post('/return', data={
            'csrf_token': csrf_token,
            'loan_id': str(loan2['loan_id']),
            'return_date': earlier_date
        }, follow_redirects=True)
        self.assertIn(b"cannot be earlier than the issue date", invalid_return_resp.data)

        # Clean up loan2 with valid date
        self.client.post('/return', data={'csrf_token': csrf_token, 'loan_id': str(loan2['loan_id']), 'return_date': date.today().isoformat()})
        print(" Issue & Return atomic transaction consistency verified.")

    def test_07_overdue_analysis(self):
        """Verify overdue loan detection and metrics."""
        overdue_data = analysis.get_overdue_analysis()
        self.assertGreater(overdue_data['total_overdue'], 0)
        self.assertIn('avg_days_overdue', overdue_data['stats'])
        self.assertIn('max_days_overdue', overdue_data['stats'])

        # Route test
        response = self.client.get('/overdue')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Delinquent Loans List", response.data)
        print(f" Overdue loans verified: {overdue_data['total_overdue']} overdue detected.")

    def test_08_reports_and_csv_exports(self):
        """Verify report views and CSV file downloads."""
        report_types = ['most_borrowed', 'overdue', 'monthly', 'category', 'active_loans', 'returned']
        for r_type in report_types:
            # HTML View
            resp = self.client.get(f'/reports?type={r_type}')
            self.assertEqual(resp.status_code, 200)

            # CSV Download
            csv_resp = self.client.get(f'/reports/export/{r_type}')
            self.assertEqual(csv_resp.status_code, 200)
            self.assertEqual(csv_resp.content_type, 'text/csv; charset=utf-8')
            self.assertGreater(len(csv_resp.data), 50)
        print(" All 6 report tables and CSV export streams verified.")

    def test_09_matplotlib_chart_downloads(self):
        """Verify server-side Matplotlib PNG charts download."""
        chart_types = ['monthly', 'most_borrowed', 'category', 'loan_status']
        for c_type in chart_types:
            resp = self.client.get(f'/charts/download/{c_type}')
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.content_type, 'image/png')
            self.assertGreater(len(resp.data), 1000)
        print(" Matplotlib PNG chart rendering and downloads verified.")

    def test_10_settings_update(self):
        """Verify settings page and borrowing period update."""
        with self.client.session_transaction() as sess:
            csrf_token = sess.get('csrf_token', '')

        # Update period to 21 days
        resp = self.client.post('/settings', data={
            'csrf_token': csrf_token,
            'action': 'update_period',
            'borrowing_period': '21'
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"successfully updated to 21 days", resp.data)

        # Check DB
        current_period = db.get_setting('borrowing_period_days')
        self.assertEqual(int(current_period), 21)

        # Reset back to 14 days
        db.set_setting('borrowing_period_days', 14)
        print(" Settings configuration and persistence verified.")

if __name__ == '__main__':
    unittest.main()
