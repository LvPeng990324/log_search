import os
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)


def parse_query(query):
    include_terms = []
    or_terms = []
    exclude_terms = []

    tokens = query.split()
    if not tokens:
        return include_terms, or_terms, exclude_terms

    current_op = "AND"
    first_term_idx = -1
    for i, token in enumerate(tokens):
        if token.upper() not in ("AND", "OR", "NOT"):
            first_term_idx = i
            break

    if first_term_idx >= 0 and first_term_idx + 1 < len(tokens):
        next_upper = tokens[first_term_idx + 1].upper()
        if next_upper == "OR":
            current_op = "OR"
        elif next_upper == "NOT":
            current_op = "NOT"

    i = 0
    while i < len(tokens):
        token = tokens[i]
        upper = token.upper()

        if upper in ("AND", "OR", "NOT"):
            current_op = upper
            i += 1
            continue

        if current_op == "OR":
            or_terms.append(token)
        elif current_op == "NOT":
            exclude_terms.append(token)
        else:
            include_terms.append(token)

        i += 1

    return include_terms, or_terms, exclude_terms


def line_matches(line, include_terms, or_terms, exclude_terms):
    lower = line.lower()
    if include_terms and not all(t.lower() in lower for t in include_terms):
        return False
    if or_terms and not any(t.lower() in lower for t in or_terms):
        return False
    if exclude_terms and any(t.lower() in lower for t in exclude_terms):
        return False
    return True


def search_files(query, log_dir):
    include_terms, or_terms, exclude_terms = parse_query(query)
    results = []

    if not log_dir or not os.path.isdir(log_dir):
        return results

    for filename in os.listdir(log_dir):
        filepath = os.path.join(log_dir, filename)
        if not os.path.isfile(filepath):
            continue
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                for line_number, line in enumerate(f, start=1):
                    if line_matches(line, include_terms, or_terms, exclude_terms):
                        results.append({
                            "file": filename,
                            "line_number": line_number,
                            "content": line.rstrip("\n")
                        })
        except Exception:
            continue

    return results


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/search", methods=["POST"])
def search():
    data = request.get_json()
    query = data.get("query", "") if data else ""
    log_dir = data.get("path", "") if data else ""
    include_terms, or_terms, exclude_terms = parse_query(query)
    results = search_files(query, log_dir)
    highlight_terms = list(set(include_terms + or_terms))
    return jsonify({"results": results, "total": len(results), "terms": highlight_terms})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
