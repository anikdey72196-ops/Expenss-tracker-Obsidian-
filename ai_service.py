import json
import requests
import time
from imports import (
    Blueprint, request, jsonify, session,
    db, Expense, datetime, date, timedelta, os
)
from flask import Response, stream_with_context

ai_bp = Blueprint('ai', __name__, url_prefix='/ai')

OLLAMA_BASE_URL = os.environ.get('OLLAMA_BASE_URL', 'http://localhost:11434')
# Use qwen2.5-coder:7b as default for fast response times; fallback to gemma4:12b if configured
OLLAMA_MODEL = os.environ.get('OLLAMA_MODEL', 'qwen2.5-coder:7b')

_rate_limit_cache = {}
RATE_LIMIT_SECONDS = 3  # Reduced to 3 seconds for better UX


def _check_rate_limit(user_id):
    """Returns True if rate limited, False if OK."""
    now = time.time()
    key = f"ai_rate_{user_id}"
    last_time = _rate_limit_cache.get(key, 0)
    if now - last_time < RATE_LIMIT_SECONDS:
        return True
    _rate_limit_cache[key] = now
    return False


def _get_expense_summary(user_id):
    """Build a spending summary string for the AI context."""
    today = date.today()
    first_of_month = today.replace(day=1)

    # This month's expenses
    this_month_expenses = Expense.query.filter(
        Expense.user_id == user_id,
        Expense.date >= first_of_month
    ).all()

    # Last month
    last_month_end = first_of_month - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)
    last_month_expenses = Expense.query.filter(
        Expense.user_id == user_id,
        Expense.date >= last_month_start,
        Expense.date <= last_month_end
    ).all()

    # 3 months ago for trends
    three_months_ago = first_of_month - timedelta(days=90)
    all_recent = Expense.query.filter(
        Expense.user_id == user_id,
        Expense.date >= three_months_ago
    ).order_by(Expense.date.desc()).all()

    # Category breakdown this month
    category_totals = {}
    this_month_total = 0.0
    for exp in this_month_expenses:
        category_totals[exp.category] = category_totals.get(exp.category, 0) + exp.amount
        this_month_total += exp.amount

    last_month_total = sum(exp.amount for exp in last_month_expenses)

    # Daily spending this month
    days_elapsed = max((today - first_of_month).days + 1, 1)
    daily_avg = this_month_total / days_elapsed

    # Build summary
    lines = []
    lines.append(f"=== FINANCIAL SUMMARY FOR CONTEXT ===")
    lines.append(f"Today's Date: {today.strftime('%B %d, %Y')}")
    lines.append(f"Days into this month: {days_elapsed}")
    lines.append(f"")
    lines.append(f"THIS MONTH's SPENDING: ₹{this_month_total:,.2f}")
    lines.append(f"LAST MONTH's TOTAL: ₹{last_month_total:,.2f}")
    lines.append(f"DAILY AVERAGE (this month): ₹{daily_avg:,.2f}")

    if last_month_total > 0:
        pct_change = ((this_month_total - last_month_total) / last_month_total) * 100
        lines.append(f"MONTH-OVER-MONTH CHANGE: {pct_change:+.1f}%")

    lines.append(f"")
    lines.append(f"CATEGORY BREAKDOWN (this month):")
    sorted_cats = sorted(category_totals.items(), key=lambda x: x[1], reverse=True)
    for cat, total in sorted_cats:
        pct = (total / this_month_total * 100) if this_month_total > 0 else 0
        lines.append(f"  - {cat}: ₹{total:,.2f} ({pct:.1f}%)")

    if not sorted_cats:
        lines.append(f"  No expenses recorded this month yet.")

    # Recent transactions (last 10)
    lines.append(f"")
    lines.append(f"RECENT TRANSACTIONS (last 10):")
    recent_10 = all_recent[:10]
    for exp in recent_10:
        lines.append(f"  - {exp.date.strftime('%b %d')}: ₹{exp.amount:,.2f} on {exp.category} - {exp.description or 'No description'}")

    if not recent_10:
        lines.append(f"  No recent transactions.")

    return "\n".join(lines), {
        'this_month_total': this_month_total,
        'last_month_total': last_month_total,
        'daily_avg': daily_avg,
        'days_elapsed': days_elapsed,
        'category_totals': category_totals,
        'num_expenses_this_month': len(this_month_expenses),
    }


def _get_active_model():
    """Determine active Ollama model, falling back to installed models if needed."""
    model = os.environ.get('OLLAMA_MODEL', 'qwen2.5-coder:7b')
    try:
        resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        if resp.status_code == 200:
            models = [m.get('name', '') for m in resp.json().get('models', [])]
            if model in models:
                return model
            for m in models:
                if any(k in m.lower() for k in ['qwen', 'coder', 'gemma', 'llama', 'mistral']):
                    return m
            if models:
                return models[0]
    except Exception:
        pass
    return model


def _call_ollama(messages, stream=False, num_predict=256, timeout=300):
    """Call the Ollama chat API with auto-resolved model and timeout handling."""
    url = f"{OLLAMA_BASE_URL}/api/chat"
    model_name = _get_active_model()
    payload = {
        "model": model_name,
        "messages": messages,
        "stream": stream,
        "options": {
            "temperature": 0.5,
            "num_predict": num_predict,
        }
    }

    if stream:
        resp = requests.post(url, json=payload, stream=True, timeout=timeout)
        resp.raise_for_status()
        return resp
    else:
        resp = requests.post(url, json=payload, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        return data.get('message', {}).get('content', '')


def _build_system_prompt(summary_text):
    """Build concise system prompt for financial advice."""
    return f"""You are Obsidian AI, a smart personal financial advisor.

Your instructions:
- Analyze the user's spending data below
- Give short, direct financial advice (2-3 sentences max)
- Always use ₹ (Indian Rupees)
- Never make up data — only reference what is in the summary

{summary_text}"""


@ai_bp.route('/chat', methods=['POST'])
def chat():
    """Handle AI chat messages with streaming response and timeout protection."""
    if 'user_id' not in session:
        return jsonify({"error": "Please login first"}), 401

    user_id = session['user_id']

    if _check_rate_limit(user_id):
        return jsonify({"error": "Please wait a few seconds before sending another message."}), 429

    data = request.get_json()
    if not data or not data.get('message'):
        return jsonify({"error": "Message is required"}), 400

    user_message = data['message'].strip()
    if len(user_message) > 500:
        return jsonify({"error": "Message too long (max 500 characters)"}), 400

    try:
        summary_text, _ = _get_expense_summary(user_id)

        messages = [
            {"role": "system", "content": _build_system_prompt(summary_text)},
            {"role": "user", "content": user_message}
        ]

        def generate():
            try:
                resp = _call_ollama(messages, stream=True, num_predict=256, timeout=300)
                for line in resp.iter_lines():
                    if line:
                        chunk = json.loads(line)
                        msg = chunk.get('message', {})
                        content = msg.get('content', '')
                        
                        # Send content if available
                        if content:
                            yield f"data: {json.dumps({'content': content})}\n\n"
                            
                        if chunk.get('done', False):
                            yield f"data: {json.dumps({'done': True})}\n\n"
                            break

            except requests.exceptions.Timeout:
                yield f"data: {json.dumps({'error': 'The AI model took too long to respond (timeout). It might be loading into memory — please try sending your message again!'})}\n\n"
            except requests.exceptions.ConnectionError:
                yield f"data: {json.dumps({'error': 'Cannot connect to Ollama. Please ensure Ollama is running (`ollama serve`).'})}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'error': f'AI generation error: {str(e)}'})}\n\n"

        return Response(
            stream_with_context(generate()),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'X-Accel-Buffering': 'no',
            }
        )

    except requests.exceptions.ConnectionError:
        return jsonify({"error": "Cannot connect to Ollama. Make sure it is running."}), 503
    except Exception as e:
        return jsonify({"error": f"Service error: {str(e)}"}), 500


@ai_bp.route('/insights', methods=['GET'])
def insights():
    """Generate AI-powered spending insights with fast fallback."""
    if 'user_id' not in session:
        return jsonify({"error": "Please login first"}), 401

    user_id = session['user_id']

    # Cache key (30 minutes TTL)
    cache_key = f"ai_insights_{user_id}"
    cached = session.get(cache_key)
    force_refresh = request.args.get('refresh') == 'true'

    if cached and not force_refresh:
        cached_time = session.get(f"{cache_key}_time", 0)
        if time.time() - cached_time < 1800:
            return jsonify(cached)

    try:
        summary_text, stats = _get_expense_summary(user_id)

        if stats['num_expenses_this_month'] == 0:
            result = {
                'predicted_total': 0,
                'budget_status': 'neutral',
                'tips': ["Start tracking your expenses to get AI-powered insights! 📊"],
                'trend': 'stable',
                'summary': 'No expenses recorded this month yet. Add expenses to see predictions!'
            }
            return jsonify(result)

        # Fast math predictions
        today = date.today()
        days_in_month = (today.replace(month=today.month % 12 + 1, day=1) - timedelta(days=1)).day if today.month < 12 else 31
        predicted_total = stats['daily_avg'] * days_in_month

        # Budget status
        if stats['last_month_total'] > 0:
            if predicted_total > stats['last_month_total'] * 1.2:
                budget_status = 'danger'
            elif predicted_total > stats['last_month_total']:
                budget_status = 'warning'
            else:
                budget_status = 'good'
        else:
            budget_status = 'neutral'

        # Trend
        if stats['last_month_total'] > 0:
            change_pct = ((stats['this_month_total'] - stats['last_month_total']) / stats['last_month_total']) * 100
            if change_pct > 10:
                trend = 'up'
            elif change_pct < -10:
                trend = 'down'
            else:
                trend = 'stable'
        else:
            trend = 'stable'

        # Try LLM for fast tips with short predict limit and 30s timeout
        tips = None
        try:
            tip_messages = [
                {"role": "system", "content": f"Based on spending: {summary_text}\nOutput ONLY a JSON array of 3 short financial tips."},
                {"role": "user", "content": "Give me 3 short saving tips as a JSON array of 3 strings."}
            ]
            tip_response = _call_ollama(tip_messages, stream=False, num_predict=120, timeout=30)
            tip_response = tip_response.strip()
            if tip_response.startswith('```'):
                tip_response = tip_response.split('\n', 1)[1] if '\n' in tip_response else tip_response
                tip_response = tip_response.rsplit('```', 1)[0]
                tip_response = tip_response.strip()
            parsed_tips = json.loads(tip_response)
            if isinstance(parsed_tips, list) and len(parsed_tips) > 0:
                tips = [str(t) for t in parsed_tips[:3]]
        except Exception:
            # Fast rule-based fallback if LLM is slow/times out
            tips = _generate_fallback_tips(stats)

        if not tips:
            tips = _generate_fallback_tips(stats)

        result = {
            'predicted_total': round(predicted_total, 2),
            'budget_status': budget_status,
            'tips': tips,
            'trend': trend,
            'this_month_total': round(stats['this_month_total'], 2),
            'last_month_total': round(stats['last_month_total'], 2),
            'daily_avg': round(stats['daily_avg'], 2),
            'days_remaining': max(days_in_month - stats['days_elapsed'], 0),
            'summary': f"At your current pace of ₹{stats['daily_avg']:,.0f}/day, you're projected to spend ₹{predicted_total:,.0f} this month."
        }

        # Cache result
        session[cache_key] = result
        session[f"{cache_key}_time"] = time.time()

        return jsonify(result)

    except Exception as e:
        # Fallback if anything fails
        return jsonify({
            'predicted_total': 0,
            'budget_status': 'neutral',
            'tips': ['Keep tracking expenses for AI insights!'],
            'trend': 'stable',
            'summary': 'AI insights loading error.'
        })


def _generate_fallback_tips(stats):
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


@ai_bp.route('/health', methods=['GET'])
def health():
    """Check if Ollama is reachable."""
    try:
        resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        resp.raise_for_status()
        models = resp.json().get('models', [])
        model_names = [m.get('name', '') for m in models]
        return jsonify({
            "status": "connected",
            "models": model_names,
            "active_model": OLLAMA_MODEL
        })
    except Exception:
        return jsonify({
            "status": "disconnected",
            "error": "Cannot reach Ollama server"
        }), 503
