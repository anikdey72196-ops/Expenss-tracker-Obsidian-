with open("templates/history.html", "r") as f:
    content = f.read()

import re

# Find the delete_expense link
old_link = """<a href="{{ url_for('delete_expense', id=exp.id) }}" class="text-slate-400 hover:text-red-400 transition-colors p-1" title="Delete" onclick="return confirm('Are you sure you want to delete this expense?')">
                                                <span class="material-symbols-outlined text-lg">delete</span>
                                            </a>"""

new_form = """<form method="POST" action="{{ url_for('delete_expense', id=exp.id) }}" class="inline" onsubmit="return confirm('Are you sure you want to delete this expense?');">
                                                <input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/>
                                                <button type="submit" class="text-slate-400 hover:text-red-400 transition-colors p-1" title="Delete">
                                                    <span class="material-symbols-outlined text-lg">delete</span>
                                                </button>
                                            </form>"""

content = content.replace(old_link, new_form)

with open("templates/history.html", "w") as f:
    f.write(content)
