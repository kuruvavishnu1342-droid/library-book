"""
Matplotlib Chart Generation Module for Library Book Usage Analysis System.
Generates publication-quality charts saved to disk or returned as byte streams for PNG download.
Theme: Light-blue and white with deep navy accents.
"""

import os
import io
import tempfile
os.environ.setdefault('MPLCONFIGDIR', tempfile.gettempdir())
import matplotlib
# Use Agg backend for headless server environments
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from config import Config
from analytics import analysis

# Custom color palette matching the website design
NAVY_PRIMARY = '#1e3a8a'     # Dark blue / Navy
BLUE_ACCENT = '#3b82f6'      # Bright blue
LIGHT_BLUE = '#60a5fa'       # Soft blue
CYAN_ACCENT = '#06b6d4'      # Cyan
TEAL_ACCENT = '#0d9488'      # Teal
ORANGE_WARNING = '#f97316'   # Warning / Overdue
GREEN_SUCCESS = '#10b981'    # Success / Returned
BG_COLOR = '#f8fafc'         # Clean off-white
CARD_BG = '#ffffff'          # Pure white
TEXT_COLOR = '#1e293b'       # Dark slate text
GRID_COLOR = '#e2e8f0'       # Soft border/grid

def _apply_theme(fig, ax):
    """Applies modern clean typography and colors to a Matplotlib plot."""
    fig.patch.set_facecolor(CARD_BG)
    ax.set_facecolor(CARD_BG)
    ax.tick_params(colors=TEXT_COLOR, labelsize=10)
    for spine in ax.spines.values():
        spine.set_color(GRID_COLOR)
        spine.set_linewidth(1)
    ax.grid(color=GRID_COLOR, linestyle='--', linewidth=0.7, alpha=0.7)

def generate_monthly_trend_chart(start_date=None, end_date=None):
    """
    Generates a Line Chart showing Monthly Borrowing Trends.
    Returns BytesIO containing PNG image.
    """
    trend_data = analysis.get_monthly_trends(start_date, end_date)
    labels = trend_data['labels']
    counts = trend_data['counts']

    fig, ax = plt.subplots(figsize=(9, 4.8), dpi=150)
    _apply_theme(fig, ax)

    if labels and counts:
        # Plot line with markers and gradient-like filled area
        line = ax.plot(labels, counts, color=BLUE_ACCENT, marker='o', linewidth=2.8, markersize=7, label='Books Issued')
        ax.fill_between(labels, counts, color=BLUE_ACCENT, alpha=0.15)
        
        # Add data labels above points
        for i, (x, y) in enumerate(zip(labels, counts)):
            ax.annotate(f"{int(y)}", (x, y), textcoords="offset points", xytext=(0, 8),
                        ha='center', fontsize=9, fontweight='bold', color=NAVY_PRIMARY)
        
        ax.yaxis.set_major_locator(ticker.MaxNLocator(integer=True))
    else:
        ax.text(0.5, 0.5, 'No loan transaction data available', ha='center', va='center', color='#64748b', fontsize=12)

    ax.set_title('Monthly Library Book Borrowing Trends', fontsize=13, fontweight='bold', color=NAVY_PRIMARY, pad=15)
    ax.set_xlabel('Month (YYYY-MM)', fontsize=10, fontweight='bold', color=TEXT_COLOR, labelpad=10)
    ax.set_ylabel('Total Transactions Issued', fontsize=10, fontweight='bold', color=TEXT_COLOR, labelpad=10)
    plt.xticks(rotation=30, ha='right')
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format='png', facecolor=fig.get_facecolor(), edgecolor='none', bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    return buf

def generate_most_borrowed_chart(top_n=10):
    """
    Generates a Bar Chart showing the Most Borrowed Books.
    Returns BytesIO containing PNG image.
    """
    data = analysis.get_most_borrowed_books(top_n=top_n)
    raw_labels = data['labels']
    counts = data['counts']

    # Truncate titles if too long for clean display
    labels = [title[:26] + '...' if len(title) > 26 else title for title in raw_labels]

    fig, ax = plt.subplots(figsize=(9, 5.2), dpi=150)
    _apply_theme(fig, ax)

    if labels and counts:
        # Horizontal bar chart for readability with book titles
        y_pos = range(len(labels))
        # Invert to have top book at the top
        y_pos = list(reversed(y_pos))
        
        colors = [NAVY_PRIMARY if i == 0 else BLUE_ACCENT for i in range(len(labels))]
        bars = ax.barh(y_pos, counts, color=colors, height=0.6, edgecolor='none')
        ax.set_yticks(y_pos)
        ax.set_yticklabels(labels, fontsize=9.5, fontweight='500')

        # Add count labels on ends of bars
        for bar in bars:
            width = bar.get_width()
            ax.text(width + 0.15, bar.get_y() + bar.get_height()/2, f"{int(width)} loans",
                    ha='left', va='center', fontsize=9, fontweight='bold', color=NAVY_PRIMARY)

        ax.xaxis.set_major_locator(ticker.MaxNLocator(integer=True))
        ax.set_xlim(0, max(counts) * 1.25 if counts else 5)
    else:
        ax.text(0.5, 0.5, 'No loan records found', ha='center', va='center', color='#64748b', fontsize=12)

    ax.set_title(f'Top {top_n} Most Borrowed Books', fontsize=13, fontweight='bold', color=NAVY_PRIMARY, pad=15)
    ax.set_xlabel('Borrow Frequency (Total Loans)', fontsize=10, fontweight='bold', color=TEXT_COLOR, labelpad=10)
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format='png', facecolor=fig.get_facecolor(), edgecolor='none', bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    return buf

def generate_category_pie_chart():
    """
    Generates a Pie Chart showing Borrowing Distribution by Category.
    Returns BytesIO containing PNG image.
    """
    data = analysis.get_category_analysis()
    labels = data['labels']
    counts = data['counts']

    fig, ax = plt.subplots(figsize=(8, 5.5), dpi=150)
    fig.patch.set_facecolor(CARD_BG)

    palette = [NAVY_PRIMARY, BLUE_ACCENT, CYAN_ACCENT, TEAL_ACCENT, '#6366f1', '#8b5cf6', '#ec4899']
    if labels and any(counts):
        # Filter out categories with 0 loans for clean pie
        filtered = [(l, c) for l, c in zip(labels, counts) if c > 0]
        if filtered:
            p_labels, p_counts = zip(*filtered)
            wedges, texts, autotexts = ax.pie(
                p_counts,
                labels=p_labels,
                autopct='%1.1f%%',
                startangle=140,
                colors=palette[:len(p_labels)],
                textprops={'fontsize': 9, 'color': TEXT_COLOR},
                wedgeprops={'edgecolor': '#ffffff', 'linewidth': 2}
            )
            for autotext in autotexts:
                autotext.set_color('#ffffff')
                autotext.set_weight('bold')
        else:
            ax.text(0.5, 0.5, 'No category transactions recorded', ha='center', va='center', color='#64748b')
    else:
        ax.text(0.5, 0.5, 'No category data available', ha='center', va='center', color='#64748b')

    ax.set_title('Book Borrowing Transactions by Category', fontsize=13, fontweight='bold', color=NAVY_PRIMARY, pad=15)
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format='png', facecolor=fig.get_facecolor(), edgecolor='none', bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    return buf

def generate_loan_status_chart():
    """
    Generates a Doughnut Chart of Active vs Returned Loans.
    Returns BytesIO containing PNG image.
    """
    data = analysis.get_active_vs_returned()
    labels = data['labels']
    counts = data['counts']

    fig, ax = plt.subplots(figsize=(7, 5), dpi=150)
    fig.patch.set_facecolor(CARD_BG)

    colors = [GREEN_SUCCESS, BLUE_ACCENT, ORANGE_WARNING]

    if counts and any(counts):
        wedges, texts, autotexts = ax.pie(
            counts,
            labels=labels,
            autopct='%1.1f%%',
            startangle=90,
            colors=colors,
            pctdistance=0.75,
            textprops={'fontsize': 9, 'color': TEXT_COLOR},
            wedgeprops={'edgecolor': '#ffffff', 'linewidth': 2, 'width': 0.45}
        )
        for autotext in autotexts:
            autotext.set_color('#ffffff')
            autotext.set_weight('bold')
    else:
        ax.text(0.5, 0.5, 'No loan transactions recorded', ha='center', va='center', color='#64748b')

    ax.set_title('Loan Status Breakdown (Active vs Returned vs Overdue)', fontsize=12, fontweight='bold', color=NAVY_PRIMARY, pad=15)
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format='png', facecolor=fig.get_facecolor(), edgecolor='none', bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    return buf
