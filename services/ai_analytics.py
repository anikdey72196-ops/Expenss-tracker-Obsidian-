import time
from datetime import date, timedelta
from models import Expense

_rate_limit_cache = {}
RATE_LIMIT_SECONDS = 3


def check_rate_limit(user_id):
    """Returns True if rate limited, False if OK."""
    now = time.time()
    key = f"ai_rate_{user_id}"
    last_time = _rate_limit_cache.get(key, 0)
    if now - last_time < RATE_LIMIT_SECONDS:
        return True
    _rate_limit_cache[key] = now
    return False


def get_expense_summary(user_id):
    """Build a spending summary string for AI context."""
    today = date.today()
    first_of_month = today.replace(day=1)

    this_month_expenses = Expense.query.filter(
        Expense.user_id == user_id,
        Expense.date >= first_of_month
    ).all()

    last_month_end = first_of_month - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)
    last_month_expenses = Expense.query.filter(
        Expense.user_id == user_id,
        Expense.date >= last_month_start,
        Expense.date <= last_month_end
    ).all()

    three_months_ago = first_of_month - timedelta(days=90)
    all_recent = Expense.query.filter(
        Expense.user_id == user_id,
        Expense.date >= three_months_ago
    ).order_by(Expense.date.desc()).all()

    category_totals = {}
    this_month_total = 0.0
    for exp in this_month_expenses:
        category_totals[exp.category] = category_totals.get(exp.category, 0) + exp.amount
        this_month_total += exp.amount

    last_month_total = sum(exp.amount for exp in last_month_expenses)
    days_elapsed = max((today - first_of_month).days + 1, 1)
    daily_avg = this_month_total / days_elapsed

    lines = [
        "=== FINANCIAL SUMMARY FOR CONTEXT ===",
        f"Today's Date: {today.strftime('%B %d, %Y')}",
        f"Days into this month: {days_elapsed}",
        "",
        f"THIS MONTH's SPENDING: ₹{this_month_total:,.2f}",
        f"LAST MONTH's TOTAL: ₹{last_month_total:,.2f}",
        f"DAILY AVERAGE (this month): ₹{daily_avg:,.2f}"
    ]

    if last_month_total > 0:
        pct_change = ((this_month_total - last_month_total) / last_month_total) * 100
        lines.append(f"MONTH-OVER-MONTH CHANGE: {pct_change:+.1f}%")

    lines.append("")
    lines.append("CATEGORY BREAKDOWN (this month):")
    sorted_cats = sorted(category_totals.items(), key=lambda x: x[1], reverse=True)
    for cat, total in sorted_cats:
        pct = (total / this_month_total * 100) if this_month_total > 0 else 0
        lines.append(f"  - {cat}: ₹{total:,.2f} ({pct:.1f}%)")

    if not sorted_cats:
        lines.append("  No expenses recorded this month yet.")

    lines.append("")
    lines.append("RECENT TRANSACTIONS (last 10):")
    recent_10 = all_recent[:10]
    for exp in recent_10:
        lines.append(f"  - {exp.date.strftime('%b %d')}: ₹{exp.amount:,.2f} on {exp.category} - {exp.description or 'No description'}")

    if not recent_10:
        lines.append("  No recent transactions.")

    return "\n".join(lines), {
        'this_month_total': this_month_total,
        'last_month_total': last_month_total,
        'daily_avg': daily_avg,
        'days_elapsed': days_elapsed,
        'category_totals': category_totals,
        'num_expenses_this_month': len(this_month_expenses),
    }


def generate_fallback_tips(stats):
    """Generate smart rule-based tips immediately without waiting for LLM."""
    tips = []
    sorted_cats = sorted(stats['category_totals'].items(), key=lambda x: x[1], reverse=True)

    if sorted_cats:
        top_cat, top_amount = sorted_cats[0]
        tips.append(f"Your highest spending category is {top_cat} (₹{top_amount:,.0f}). Consider setting a target for this category.")

    if stats['last_month_total'] > 0:
        if stats['this_month_total'] > stats['last_month_total']:
            tips.append(f"You have passed last month's total of ₹{stats['last_month_total']:,.0f}. Try reducing non-essential expenses.")
        else:
            remaining = stats['last_month_total'] - stats['this_month_total']
            tips.append(f"You have ₹{remaining:,.0f} left before reaching last month's total.")

    if stats['daily_avg'] > 0:
        tips.append(f"Your average daily spending is ₹{stats['daily_avg']:,.0f}/day.")

    if not tips:
        tips.append("Track your daily expenses regularly to get personalized insights!")

    return tips[:3]


def build_system_prompt(summary_text):
    """Build concise system prompt for financial advice."""
    return f"""You are Obsidian AI, a smart personal financial advisor.

Your instructions:
- Analyze the user's spending data below
- Give short, direct financial advice (2-3 sentences max)
- Always use ₹ (Indian Rupees)
- Never make up data — only reference what is in the summary

{summary_text}"""
