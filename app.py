import os
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)


def tokenize_query(query):
    """按空格分词，双引号内的内容作为一个整体 token。"""
    tokens = []
    i = 0
    n = len(query)
    while i < n:
        if query[i] == '"':
            j = i + 1
            while j < n and query[j] != '"':
                j += 1
            tokens.append(query[i + 1:j])
            i = j + 1
        elif query[i].isspace():
            i += 1
        else:
            j = i
            while j < n and not query[j].isspace():
                j += 1
            tokens.append(query[i:j])
            i = j
    return tokens


def parse_query(query):
    include_terms = []
    or_terms = []
    exclude_terms = []

    tokens = tokenize_query(query)
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


def _match_time(filepath, start_time, end_time):
    if start_time is None and end_time is None:
        return True
    try:
        mtime_ms = os.path.getmtime(filepath) * 1000
        if start_time is not None and mtime_ms < start_time:
            return False
        if end_time is not None and mtime_ms > end_time:
            return False
        return True
    except Exception:
        return False


def _search_single_file(filepath, include_terms, or_terms, exclude_terms, start_time, end_time, dir_name):
    if not os.path.isfile(filepath):
        return []
    if not _match_time(filepath, start_time, end_time):
        return []

    results = []
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            for line_number, line in enumerate(f, start=1):
                if line_matches(line, include_terms, or_terms, exclude_terms):
                    results.append({
                        "dir": dir_name,
                        "file": os.path.basename(filepath),
                        "line_number": line_number,
                        "content": line.rstrip("\n")
                    })
    except Exception:
        pass
    return results


def search_files(query, log_dirs, start_time=None, end_time=None):
    include_terms, or_terms, exclude_terms = parse_query(query)
    results = []

    if isinstance(log_dirs, str):
        log_dirs = [log_dirs]

    for log_dir in log_dirs:
        if not log_dir:
            continue

        # 如果路径指向具体文件，则直接检索该文件
        if os.path.isfile(log_dir):
            results.extend(_search_single_file(
                log_dir, include_terms, or_terms, exclude_terms,
                start_time, end_time, os.path.dirname(log_dir)
            ))
            continue

        if not os.path.isdir(log_dir):
            continue

        for filename in os.listdir(log_dir):
            filepath = os.path.join(log_dir, filename)
            results.extend(_search_single_file(
                filepath, include_terms, or_terms, exclude_terms,
                start_time, end_time, log_dir
            ))

    return results


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/search", methods=["POST"])
def search():
    data = request.get_json()
    query = data.get("query", "") if data else ""
    paths = data.get("paths", []) if data else []
    start_time = data.get("start_time")
    end_time = data.get("end_time")
    try:
        start_time = int(start_time) if start_time is not None else None
    except (ValueError, TypeError):
        start_time = None
    try:
        end_time = int(end_time) if end_time is not None else None
    except (ValueError, TypeError):
        end_time = None

    include_terms, or_terms, exclude_terms = parse_query(query)
    results = search_files(query, paths, start_time=start_time, end_time=end_time)
    highlight_terms = list(set(include_terms + or_terms))
    return jsonify({"results": results, "total": len(results), "terms": highlight_terms})


@app.route("/api/list_dir", methods=["POST"])
def list_dir():
    data = request.get_json()
    path = data.get("path", "") if data else ""

    if not path or not os.path.isdir(path):
        return jsonify({"items": []})

    try:
        items = []
        for entry in os.scandir(path):
            items.append({
                "name": entry.name,
                "is_dir": entry.is_dir()
            })
        # 目录在前，文件在后，按名称排序
        items.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))
        return jsonify({"items": items})
    except Exception:
        return jsonify({"items": []})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
