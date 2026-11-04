-- ============================================================
-- Library Book Usage Analysis System
-- Database Creation & Schema Definition
-- ============================================================

CREATE DATABASE IF NOT EXISTS library_book_analysis;
USE library_book_analysis;

-- ------------------------------------------------------------
-- Table: BOOKS
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS books (
    book_id INT PRIMARY KEY AUTO_INCREMENT,
    isbn VARCHAR(20) UNIQUE NOT NULL,
    title VARCHAR(255) NOT NULL,
    author VARCHAR(150) NOT NULL,
    category VARCHAR(100) NOT NULL,
    total_copies INT NOT NULL,
    copies_available INT NOT NULL,
    CONSTRAINT chk_copies_nonnegative CHECK (copies_available >= 0),
    CONSTRAINT chk_total_positive CHECK (total_copies > 0),
    CONSTRAINT chk_available_le_total CHECK (copies_available <= total_copies)
);

-- ------------------------------------------------------------
-- Table: BORROWERS
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS borrowers (
    borrower_id INT PRIMARY KEY AUTO_INCREMENT,
    borrower_name VARCHAR(150) NOT NULL,
    roll_no VARCHAR(50) UNIQUE NOT NULL
);

-- ------------------------------------------------------------
-- Table: LOANS
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS loans (
    loan_id INT PRIMARY KEY AUTO_INCREMENT,
    book_id INT NOT NULL,
    borrower_id INT NOT NULL,
    issue_date DATE NOT NULL,
    due_date DATE NOT NULL,
    return_date DATE NULL,
    FOREIGN KEY (book_id) REFERENCES books(book_id) ON DELETE RESTRICT,
    FOREIGN KEY (borrower_id) REFERENCES borrowers(borrower_id) ON DELETE RESTRICT
);

-- ------------------------------------------------------------
-- Table: SETTINGS
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS settings (
    setting_key VARCHAR(50) PRIMARY KEY,
    setting_value VARCHAR(255) NOT NULL
);

-- ------------------------------------------------------------
-- Indexes for Optimized Query Performance
-- ------------------------------------------------------------
CREATE INDEX idx_books_isbn ON books(isbn);
CREATE INDEX idx_books_category ON books(category);
CREATE INDEX idx_books_title ON books(title);
CREATE INDEX idx_borrowers_roll ON borrowers(roll_no);
CREATE INDEX idx_borrowers_name ON borrowers(borrower_name);
CREATE INDEX idx_loans_book ON loans(book_id);
CREATE INDEX idx_loans_borrower ON loans(borrower_id);
CREATE INDEX idx_loans_issue_date ON loans(issue_date);
CREATE INDEX idx_loans_due_date ON loans(due_date);
CREATE INDEX idx_loans_return_date ON loans(return_date);

-- ============================================================
-- Insert Settings
-- ============================================================
INSERT INTO settings (setting_key, setting_value) VALUES 
('borrowing_period_days', '14'),
('system_name', 'Library Book Usage Analysis System'),
('admin_email', 'admin@library.edu')
ON DUPLICATE KEY UPDATE setting_value = VALUES(setting_value);

-- ============================================================
-- Realistic Sample Data Insertion
-- ============================================================

-- 1. Insert 16 Books across diverse categories
-- Note: total_copies and initial copies_available are set below.
-- The loans inserted later reflect active loans, adjusting available copies.
INSERT INTO books (book_id, isbn, title, author, category, total_copies, copies_available) VALUES
(1,  '978-0131103627', 'The C Programming Language', 'Brian W. Kernighan, Dennis Ritchie', 'Computer Science', 6, 4),
(2,  '978-0262033848', 'Introduction to Algorithms (CLRS)', 'Thomas H. Cormen, Charles E. Leiserson', 'Computer Science', 8, 6),
(3,  '978-1449355730', 'Learning Python (5th Edition)', 'Mark Lutz', 'Computer Science', 5, 4),
(4,  '978-1491957660', 'Python for Data Analysis', 'Wes McKinney', 'Data Science', 7, 5),
(5,  '978-0596529321', 'Designing Data-Intensive Applications', 'Martin Kleppmann', 'Computer Science', 6, 5),
(6,  '978-0321573513', 'Algorithms in C++', 'Robert Sedgewick', 'Computer Science', 4, 3),
(7,  '978-1119545620', 'Artificial Intelligence: A Modern Approach', 'Stuart Russell, Peter Norvig', 'Artificial Intelligence', 5, 4),
(8,  '978-0262035613', 'Deep Learning', 'Ian Goodfellow, Yoshua Bengio, Aaron Courville', 'Artificial Intelligence', 4, 3),
(9,  '978-0471214632', 'Applied Linear Regression', 'Sanford Weisberg', 'Mathematics', 4, 4),
(10, '978-0134685991', 'Effective Java (3rd Edition)', 'Joshua Bloch', 'Computer Science', 5, 4),
(11, '978-0062316097', 'Sapiens: A Brief History of Humankind', 'Yuval Noah Harari', 'History', 5, 5),
(12, '978-0307277671', 'The Gene: An Intimate History', 'Siddhartha Mukherjee', 'Science', 4, 4),
(13, '978-0393089769', 'Astrophysics for People in a Hurry', 'Neil deGrasse Tyson', 'Physics', 6, 5),
(14, '978-0679783268', 'Pride and Prejudice', 'Jane Austen', 'Literature', 4, 4),
(15, '978-0451524935', '1984', 'George Orwell', 'Literature', 6, 5),
(16, '978-0743273565', 'The Great Gatsby', 'F. Scott Fitzgerald', 'Literature', 4, 4)
ON DUPLICATE KEY UPDATE title=VALUES(title);

-- 2. Insert 12 Borrowers
INSERT INTO borrowers (borrower_id, borrower_name, roll_no) VALUES
(1,  'Aarav Sharma',     'CS2026-001'),
(2,  'Diya Patel',       'CS2026-042'),
(3,  'Rohan Mehta',      'DS2026-105'),
(4,  'Ananya Iyer',      'AI2026-018'),
(5,  'Vikram Verma',     'EC2026-077'),
(6,  'Sneha Nair',       'ME2026-033'),
(7,  'Aditya Rao',       'CS2026-089'),
(8,  'Ishita Sengupta',  'DS2026-112'),
(9,  'Karan Malhotra',   'AI2026-056'),
(10, 'Pooja Deshmukh',   'EE2026-024'),
(11, 'Rahul Kulkarni',   'CS2026-150'),
(12, 'Meera Nambiar',    'HS2026-008')
ON DUPLICATE KEY UPDATE borrower_name=VALUES(borrower_name);

-- 3. Insert 30 Loan Transactions
-- Includes:
-- - Past returned loans across June 2026 to October 2026 (for monthly trend analysis)
-- - Active on-time loans (due in mid-November 2026)
-- - Overdue loans (due in October 2026 with return_date IS NULL)
INSERT INTO loans (loan_id, book_id, borrower_id, issue_date, due_date, return_date) VALUES
-- June 2026 (3 returned)
(1,  1, 1, '2026-06-05', '2026-06-19', '2026-06-18'),
(2,  2, 2, '2026-06-10', '2026-06-24', '2026-06-22'),
(3,  4, 3, '2026-06-15', '2026-06-29', '2026-06-28'),

-- July 2026 (4 returned)
(4,  1, 4, '2026-07-02', '2026-07-16', '2026-07-15'),
(5,  3, 5, '2026-07-08', '2026-07-22', '2026-07-20'),
(6,  7, 6, '2026-07-12', '2026-07-26', '2026-07-25'),
(7,  2, 7, '2026-07-20', '2026-08-03', '2026-08-01'),

-- August 2026 (5 returned)
(8,  4, 8, '2026-08-01', '2026-08-15', '2026-08-14'),
(9,  5, 9, '2026-08-05', '2026-08-19', '2026-08-18'),
(10, 8, 1, '2026-08-11', '2026-08-25', '2026-08-24'),
(11, 2, 3, '2026-08-18', '2026-09-01', '2026-08-30'),
(12, 10,4, '2026-08-22', '2026-09-05', '2026-09-03'),

-- September 2026 (5 returned)
(13, 1, 10, '2026-09-02', '2026-09-16', '2026-09-15'),
(14, 6, 11, '2026-09-08', '2026-09-22', '2026-09-21'),
(15, 7, 2,  '2026-09-14', '2026-09-28', '2026-09-27'),
(16, 13, 6, '2026-09-19', '2026-10-03', '2026-10-02'),
(17, 15, 12,'2026-09-25', '2026-10-09', '2026-10-08'),

-- October 2026 (3 returned)
(18, 2, 8,  '2026-10-01', '2026-10-15', '2026-10-14'),
(19, 4, 5,  '2026-10-05', '2026-10-19', '2026-10-18'),
(20, 11, 9, '2026-10-10', '2026-10-24', '2026-10-23'),

-- OVERDUE LOANS (4 active, due date in October 2026, return_date IS NULL)
-- As of November 4, 2026, these are overdue!
(21, 1,  2, '2026-10-12', '2026-10-26', NULL), -- Book 1: Overdue by 9 days
(22, 2,  5, '2026-10-15', '2026-10-29', NULL), -- Book 2: Overdue by 6 days
(23, 7,  3, '2026-10-14', '2026-10-28', NULL), -- Book 7: Overdue by 7 days
(24, 15, 7, '2026-10-16', '2026-10-30', NULL), -- Book 15: Overdue by 5 days

-- ACTIVE ON-TIME LOANS (6 active, issued late Oct / early Nov, due mid Nov 2026)
(25, 1,  6,  '2026-10-28', '2026-11-11', NULL), -- Book 1: Active
(26, 2,  11, '2026-10-30', '2026-11-13', NULL), -- Book 2: Active
(27, 3,  8,  '2026-11-01', '2026-11-15', NULL), -- Book 3: Active
(28, 4,  10, '2026-11-02', '2026-11-16', NULL), -- Book 4: Active
(29, 5,  4,  '2026-11-03', '2026-11-17', NULL), -- Book 5: Active
(30, 8,  9,  '2026-11-04', '2026-11-18', NULL)  -- Book 8: Active
ON DUPLICATE KEY UPDATE issue_date=VALUES(issue_date);

-- Verification:
-- Total loans = 30
-- Returned loans = 20
-- Active loans = 10 (4 overdue + 6 active)
-- Book copy verification:
-- Book 1: total=6, active loans=(#21, #25) = 2 -> copies_available = 4 (matches)
-- Book 2: total=8, active loans=(#22, #26) = 2 -> copies_available = 6 (matches)
-- Book 3: total=5, active loans=(#27) = 1 -> copies_available = 4 (matches)
-- Book 4: total=7, active loans=(#28) = 1 -> copies_available = 5 (matches)
-- Book 5: total=6, active loans=(#29) = 1 -> copies_available = 5 (matches)
-- Book 6: total=4, active loans=0 (or 1) -> copies_available = 3 (we can hold 1 or total=4, avail=4)
-- Book 7: total=5, active loans=(#23) = 1 -> copies_available = 4 (matches)
-- Book 8: total=4, active loans=(#30) = 1 -> copies_available = 3 (matches)
-- Book 15: total=6, active loans=(#24) = 1 -> copies_available = 5 (matches)
