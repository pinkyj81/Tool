from __future__ import annotations

import math
import os
from datetime import datetime

import pyodbc
from flask import Flask, flash, jsonify, redirect, render_template, request, url_for


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static"),
)
app.secret_key = os.environ.get("TOOLREPLACE_SECRET_KEY", "toolreplace-dev-secret")

DEFAULT_SAUP_CODE = os.environ.get("TOOLREPLACE_DEFAULT_SAUPCODE", "001")
DEFAULT_ENTRY_ID = os.environ.get("TOOLREPLACE_DEFAULT_ENTRYID", "mobile")


COLUMNS = [
    "SaupCode",
    "SeqNo",
    "GongJung",
    "inDate",
    "LineCode",
    "GongNo",
    "BoxNo",
    "ToolCode",
    "ProdSpec",
    "TNum",
    "CodeNo",
    "Install",
    "CGubun",
    "Qty",
    "GaGongQty",
    "Worker",
    "EndGu",
    "BiGo",
    "EntryId",
    "EntryDate",
]


def get_db_connection() -> pyodbc.Connection:
    conn_str = (
        f"DRIVER={{ODBC Driver 18 for SQL Server}};"
        f"SERVER={os.environ.get('TOOLREPLACE_DB_SERVER', 'ms1901.gabiadb.com')};"
        f"DATABASE={os.environ.get('TOOLREPLACE_DB_DATABASE', 'yujincast')};"
        f"UID={os.environ.get('TOOLREPLACE_DB_USERNAME', 'pinkyj81')};"
        f"PWD={os.environ.get('TOOLREPLACE_DB_PASSWORD', 'zoskek38!!')};"
        "Encrypt=yes;"
        "TrustServerCertificate=yes;"
    )
    return pyodbc.connect(conn_str)


def to_nullable_text(value: str | None) -> str | None:
    text = (value or "").strip()
    return text if text else None


def to_nullable_number(value: str | None) -> int | None:
    text = (value or "").strip()
    if not text:
        return None
    return int(float(text))


def fetch_install_options(tool_code: str | None = None, limit: int = 200) -> list[str]:
    where_clause = ""
    params: list[object] = []
    code = (tool_code or "").strip()
    if code:
        # Prefer exact tool match first, then partial for flexible search.
        where_clause = " AND (ToolCode = ? OR ToolCode LIKE ?)"
        params.extend([code, f"%{code}%"])

    sql = f"""
        SELECT TOP {limit} LTRIM(RTRIM(Install)) AS Install
        FROM dbo.ToolReplace
        WHERE ISNULL(LTRIM(RTRIM(Install)), '') <> ''
        {where_clause}
        GROUP BY LTRIM(RTRIM(Install))
        ORDER BY LTRIM(RTRIM(Install))
    """

    conn = get_db_connection()
    try:
        rows = conn.cursor().execute(sql, params).fetchall()
    finally:
        conn.close()

    return [str(row[0]).strip() for row in rows if row and row[0] is not None]


def fetch_worker_options(limit: int = 200) -> list[str]:
    sql = f"""
        SELECT TOP {limit} LTRIM(RTRIM(Worker)) AS Worker
        FROM dbo.ToolReplace
        WHERE ISNULL(LTRIM(RTRIM(Worker)), '') <> ''
        GROUP BY LTRIM(RTRIM(Worker))
        ORDER BY LTRIM(RTRIM(Worker))
    """

    conn = get_db_connection()
    try:
        rows = conn.cursor().execute(sql).fetchall()
    finally:
        conn.close()

    return [str(row[0]).strip() for row in rows if row and row[0] is not None]


def parse_filters() -> tuple[list[str], list[object], dict[str, str]]:
    saup_code = (request.args.get("saup_code") or "").strip()
    seq_no = (request.args.get("seq_no") or "").strip()
    tool_code = (request.args.get("tool_code") or "").strip()
    line_code = (request.args.get("line_code") or "").strip()
    install = (request.args.get("install") or "").strip()
    from_date = (request.args.get("from_date") or "").strip()
    to_date = (request.args.get("to_date") or "").strip()

    where_parts: list[str] = []
    params: list[object] = []

    if saup_code:
        where_parts.append("SaupCode LIKE ?")
        params.append(f"%{saup_code}%")
    if seq_no:
        where_parts.append("SeqNo LIKE ?")
        params.append(f"%{seq_no}%")
    if tool_code:
        where_parts.append("ToolCode LIKE ?")
        params.append(f"%{tool_code}%")
    if line_code:
        where_parts.append("LineCode LIKE ?")
        params.append(f"%{line_code}%")
    if install:
        where_parts.append("Install LIKE ?")
        params.append(f"%{install}%")
    if from_date:
        where_parts.append("TRY_CONVERT(date, inDate) >= ?")
        params.append(from_date)
    if to_date:
        where_parts.append("TRY_CONVERT(date, inDate) <= ?")
        params.append(to_date)

    filters = {
        "saup_code": saup_code,
        "seq_no": seq_no,
        "tool_code": tool_code,
        "line_code": line_code,
        "install": install,
        "from_date": from_date,
        "to_date": to_date,
    }
    return where_parts, params, filters


@app.route("/health")
def health():
    try:
        conn = get_db_connection()
        conn.close()
        return {"status": "healthy"}, 200
    except Exception as exc:  # pragma: no cover
        return {"status": "unhealthy", "error": str(exc)}, 500


@app.route("/api/install-options")
def install_options():
    tool_code = (request.args.get("tool_code") or "").strip()
    try:
        options = fetch_install_options(tool_code=tool_code)
        return jsonify({"success": True, "options": options})
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc), "options": []}), 500


@app.route("/")
def home():
    return redirect(url_for("mobile_register"))


@app.route("/list")
def index():
    page = max(int(request.args.get("page", 1)), 1)
    per_page = 30

    where_parts, params, filters = parse_filters()
    where_clause = " WHERE " + " AND ".join(where_parts) if where_parts else ""

    count_sql = f"SELECT COUNT(*) FROM dbo.ToolReplace{where_clause}"
    data_sql = f"""
        SELECT {", ".join(COLUMNS)}
        FROM dbo.ToolReplace
        {where_clause}
        ORDER BY TRY_CONVERT(datetime, EntryDate) DESC, SeqNo DESC
        OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
    """

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        total_count = cur.execute(count_sql, params).fetchone()[0]

        offset = (page - 1) * per_page
        rows = cur.execute(data_sql, [*params, offset, per_page]).fetchall()
    finally:
        conn.close()

    total_pages = max(math.ceil(total_count / per_page), 1)
    if page > total_pages:
        page = total_pages

    return render_template(
        "index.html",
        columns=COLUMNS,
        rows=rows,
        filters=filters,
        page=page,
        per_page=per_page,
        total_count=total_count,
        total_pages=total_pages,
    )


def generate_mobile_seq_no() -> str:
    now = datetime.now()
    # Keep SeqNo below varchar(20): M + yymmddHHMMSS + msec(3)
    return f"M{now.strftime('%y%m%d%H%M%S')}{int(now.microsecond / 1000):03d}"


@app.route("/mobile/new", methods=["GET", "POST"])
def mobile_register():
    selected_tool_code = (request.form.get("ToolCode") or request.args.get("tool_code") or "").strip()
    install_options = fetch_install_options(tool_code=selected_tool_code)
    worker_options = fetch_worker_options()

    if request.method == "POST":
        form = request.form
        try:
            saup_code = to_nullable_text(form.get("SaupCode")) or DEFAULT_SAUP_CODE
            seq_no = generate_mobile_seq_no()
            in_date = to_nullable_text(form.get("inDate")) or datetime.now().strftime("%Y-%m-%d")
            line_code = to_nullable_text(form.get("LineCode"))
            tool_code = to_nullable_text(form.get("ToolCode"))
            install = to_nullable_text(form.get("Install"))
            qty = to_nullable_number(form.get("Qty"))
            ga_gong_qty = to_nullable_number(form.get("GaGongQty"))
            worker = to_nullable_text(form.get("Worker"))
            bi_go = to_nullable_text(form.get("BiGo"))
            entry_id = to_nullable_text(form.get("EntryId")) or DEFAULT_ENTRY_ID

            if not line_code and not tool_code:
                raise ValueError("LineCode 또는 ToolCode는 입력하세요.")

            sql = """
                INSERT INTO dbo.ToolReplace (
                    SaupCode, SeqNo, GongJung, inDate, LineCode, GongNo, BoxNo,
                    ToolCode, ProdSpec, TNum, CodeNo, Install, CGubun, Qty,
                    GaGongQty, Worker, EndGu, BiGo, EntryId, EntryDate
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """

            values = [
                saup_code,
                seq_no,
                to_nullable_text(form.get("GongJung")),
                in_date,
                line_code,
                to_nullable_text(form.get("GongNo")),
                to_nullable_text(form.get("BoxNo")),
                tool_code,
                to_nullable_text(form.get("ProdSpec")),
                to_nullable_text(form.get("TNum")),
                to_nullable_text(form.get("CodeNo")),
                install,
                to_nullable_text(form.get("CGubun")),
                qty,
                ga_gong_qty,
                worker,
                to_nullable_text(form.get("EndGu")),
                bi_go,
                entry_id,
                datetime.now(),
            ]

            conn = get_db_connection()
            try:
                conn.cursor().execute(sql, values)
                conn.commit()
            finally:
                conn.close()

            flash("모바일 등록 완료", "success")
            return redirect(url_for("mobile_register"))
        except Exception as exc:
            flash(f"등록 실패: {exc}", "danger")

    initial = {
        "SaupCode": DEFAULT_SAUP_CODE,
        "EntryId": DEFAULT_ENTRY_ID,
        "inDate": datetime.now().strftime("%Y-%m-%d"),
        "ToolCode": selected_tool_code,
        "Install": (request.form.get("Install") or "").strip() if request.method == "POST" else "",
        "Worker": (request.form.get("Worker") or "").strip() if request.method == "POST" else "",
    }
    return render_template(
        "mobile_register.html",
        initial=initial,
        install_options=install_options,
        worker_options=worker_options,
    )


@app.route("/new", methods=["GET", "POST"])
def create_row():
    if request.method == "POST":
        form = request.form
        try:
            data = {
                "SaupCode": to_nullable_text(form.get("SaupCode")),
                "SeqNo": to_nullable_text(form.get("SeqNo")),
                "GongJung": to_nullable_text(form.get("GongJung")),
                "inDate": to_nullable_text(form.get("inDate")),
                "LineCode": to_nullable_text(form.get("LineCode")),
                "GongNo": to_nullable_text(form.get("GongNo")),
                "BoxNo": to_nullable_text(form.get("BoxNo")),
                "ToolCode": to_nullable_text(form.get("ToolCode")),
                "ProdSpec": to_nullable_text(form.get("ProdSpec")),
                "TNum": to_nullable_text(form.get("TNum")),
                "CodeNo": to_nullable_text(form.get("CodeNo")),
                "Install": to_nullable_text(form.get("Install")),
                "CGubun": to_nullable_text(form.get("CGubun")),
                "Qty": to_nullable_number(form.get("Qty")),
                "GaGongQty": to_nullable_number(form.get("GaGongQty")),
                "Worker": to_nullable_text(form.get("Worker")),
                "EndGu": to_nullable_text(form.get("EndGu")),
                "BiGo": to_nullable_text(form.get("BiGo")),
                "EntryId": to_nullable_text(form.get("EntryId")),
            }

            if not data["SaupCode"] or not data["SeqNo"]:
                raise ValueError("SaupCode, SeqNo는 필수입니다.")

            entry_date_input = to_nullable_text(form.get("EntryDate"))
            if entry_date_input:
                parsed_dt = datetime.strptime(entry_date_input, "%Y-%m-%d %H:%M:%S")
            else:
                parsed_dt = datetime.now()

            sql = """
                INSERT INTO dbo.ToolReplace (
                    SaupCode, SeqNo, GongJung, inDate, LineCode, GongNo, BoxNo,
                    ToolCode, ProdSpec, TNum, CodeNo, Install, CGubun, Qty,
                    GaGongQty, Worker, EndGu, BiGo, EntryId, EntryDate
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            values = [
                data["SaupCode"], data["SeqNo"], data["GongJung"], data["inDate"],
                data["LineCode"], data["GongNo"], data["BoxNo"], data["ToolCode"],
                data["ProdSpec"], data["TNum"], data["CodeNo"], data["Install"],
                data["CGubun"], data["Qty"], data["GaGongQty"], data["Worker"],
                data["EndGu"], data["BiGo"], data["EntryId"], parsed_dt,
            ]

            conn = get_db_connection()
            try:
                conn.cursor().execute(sql, values)
                conn.commit()
            finally:
                conn.close()

            flash("등록되었습니다.", "success")
            return redirect(url_for("index"))
        except Exception as exc:
            flash(f"등록 실패: {exc}", "danger")

    return render_template("form.html", mode="new", row=None)


@app.route("/edit", methods=["GET", "POST"])
def edit_row():
    saup_code = (request.values.get("saup_code") or "").strip()
    seq_no = (request.values.get("seq_no") or "").strip()

    if not saup_code or not seq_no:
        flash("수정 대상 키가 없습니다.", "danger")
        return redirect(url_for("index"))

    if request.method == "POST":
        form = request.form
        try:
            entry_date_input = to_nullable_text(form.get("EntryDate"))
            parsed_dt = datetime.strptime(entry_date_input, "%Y-%m-%d %H:%M:%S") if entry_date_input else None

            sql = """
                UPDATE dbo.ToolReplace
                SET GongJung=?, inDate=?, LineCode=?, GongNo=?, BoxNo=?,
                    ToolCode=?, ProdSpec=?, TNum=?, CodeNo=?, Install=?,
                    CGubun=?, Qty=?, GaGongQty=?, Worker=?, EndGu=?, BiGo=?,
                    EntryId=?, EntryDate=?
                WHERE SaupCode=? AND SeqNo=?
            """
            values = [
                to_nullable_text(form.get("GongJung")),
                to_nullable_text(form.get("inDate")),
                to_nullable_text(form.get("LineCode")),
                to_nullable_text(form.get("GongNo")),
                to_nullable_text(form.get("BoxNo")),
                to_nullable_text(form.get("ToolCode")),
                to_nullable_text(form.get("ProdSpec")),
                to_nullable_text(form.get("TNum")),
                to_nullable_text(form.get("CodeNo")),
                to_nullable_text(form.get("Install")),
                to_nullable_text(form.get("CGubun")),
                to_nullable_number(form.get("Qty")),
                to_nullable_number(form.get("GaGongQty")),
                to_nullable_text(form.get("Worker")),
                to_nullable_text(form.get("EndGu")),
                to_nullable_text(form.get("BiGo")),
                to_nullable_text(form.get("EntryId")),
                parsed_dt,
                saup_code,
                seq_no,
            ]

            conn = get_db_connection()
            try:
                conn.cursor().execute(sql, values)
                conn.commit()
            finally:
                conn.close()

            flash("수정되었습니다.", "success")
            return redirect(url_for("index"))
        except Exception as exc:
            flash(f"수정 실패: {exc}", "danger")

    conn = get_db_connection()
    try:
        sql = f"SELECT {', '.join(COLUMNS)} FROM dbo.ToolReplace WHERE SaupCode=? AND SeqNo=?"
        row = conn.cursor().execute(sql, saup_code, seq_no).fetchone()
    finally:
        conn.close()

    if not row:
        flash("대상 데이터를 찾을 수 없습니다.", "danger")
        return redirect(url_for("index"))

    return render_template("form.html", mode="edit", row=row)


@app.route("/delete", methods=["POST"])
def delete_row():
    saup_code = (request.form.get("saup_code") or "").strip()
    seq_no = (request.form.get("seq_no") or "").strip()

    if not saup_code or not seq_no:
        flash("삭제 대상 키가 없습니다.", "danger")
        return redirect(url_for("index"))

    conn = get_db_connection()
    try:
        conn.cursor().execute(
            "DELETE FROM dbo.ToolReplace WHERE SaupCode=? AND SeqNo=?",
            saup_code,
            seq_no,
        )
        conn.commit()
    finally:
        conn.close()

    flash("삭제되었습니다.", "success")
    return redirect(url_for("index"))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    app.run(host="0.0.0.0", port=port, debug=True)
