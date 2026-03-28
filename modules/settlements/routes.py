"""
modules/settlements/routes.py - Settlement Management Blueprint.

API Routes
----------
POST /api/settlements/generate       - Generate weekly settlements for all active staff
GET  /api/settlements                - List settlements (filterable by user/week)
GET  /api/settlements/<id>           - Get a single settlement with expense detail
GET  /api/settlements/user/<user_id> - Get all settlements for a specific user
GET  /api/settlements/export/csv     - Export settlements as CSV
GET  /api/settlements/export/pdf     - Export settlements as PDF
"""
from __future__ import annotations

import csv
import io
from datetime import datetime

from flask import Blueprint, request, session, jsonify, Response, make_response

from middleware.auth_middleware import login_required, admin_required
from services import settlement_service
from utils.logger import get_logger

log = get_logger(__name__)

# Single authoritative Blueprint instance.
settlements_bp = Blueprint("settlements", __name__)


@settlements_bp.post("/api/settlements/generate")
@admin_required
def api_generate_settlements():
    """Generate weekly settlements for all active staff."""
    body = request.get_json(silent=True) or {}
    admin_id = session["user_id"]

    week_start_str = str(body.get("week_start", "")).strip()
    week_end_str = str(body.get("week_end", "")).strip()

    if not week_start_str or not week_end_str:
        return jsonify({"success": False, "error": "week_start and week_end are required (YYYY-MM-DD)."}), 400

    try:
        week_start = datetime.strptime(week_start_str, "%Y-%m-%d").date()
        week_end = datetime.strptime(week_end_str, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"success": False, "error": "Invalid date format. Use YYYY-MM-DD."}), 400

    if week_start > week_end:
        return jsonify({"success": False, "error": "week_start must be before or equal to week_end."}), 400

    log.info("Generate settlements | admin_id=%s | period=%s to %s", admin_id, week_start, week_end)

    success, error, settlements = settlement_service.generate_weekly_settlement(
        week_start, week_end, generated_by=admin_id
    )
    if not success:
        log.error("Generate settlements failed | error=%s", error)
        return jsonify({"success": False, "error": error}), 400

    return jsonify({"success": True, "settlements": settlements, "count": len(settlements)}), 201


@settlements_bp.get("/api/settlements")
@admin_required
def api_list_settlements():
    """
    List settlements with optional filters.

    Query params: user_id, week_start, week_end.
    """
    filters = {}
    if request.args.get("user_id"):
        filters["user_id"] = request.args["user_id"]
    if request.args.get("week_start"):
        filters["week_start"] = request.args["week_start"]
    if request.args.get("week_end"):
        filters["week_end"] = request.args["week_end"]

    log.info("List settlements | filters=%s", filters)
    settlements = settlement_service.get_settlements(filters if filters else None)
    return jsonify({"success": True, "settlements": settlements})


@settlements_bp.get("/api/settlements/user/<user_id>")
@login_required
def api_user_settlements(user_id: str):
    """Get all settlements for a specific user."""
    role = session.get("role")
    if role != "admin" and session["user_id"] != user_id:
        return jsonify({"success": False, "error": "Access denied."}), 403

    log.info("Get user settlements | user_id=%s | requested_by=%s", user_id, session["user_id"])
    settlements = settlement_service.get_settlements_for_user(user_id)
    return jsonify({"success": True, "settlements": settlements})


@settlements_bp.get("/api/settlements/<settlement_id>")
@login_required
def api_get_settlement(settlement_id: str):
    """Get a single settlement."""
    log.info("Get settlement | settlement_id=%s", settlement_id)
    doc = settlement_service.get_settlement(settlement_id)
    if not doc:
        return jsonify({"success": False, "error": "Settlement not found."}), 404

    role = session.get("role")
    if role != "admin" and doc.get("user_id") != session["user_id"]:
        return jsonify({"success": False, "error": "Access denied."}), 403

    # Add expense_records for modal
    from services.financial_service import get_requests
    expense_records = []
    if doc:
        # Convert week_start and week_end to datetime for filtering
        from datetime import datetime
        week_start = doc.get("week_start")
        week_end = doc.get("week_end")
        try:
            start_dt = datetime.strptime(week_start, "%Y-%m-%d") if week_start else None
            end_dt = datetime.strptime(week_end, "%Y-%m-%d") if week_end else None
        except Exception:
            start_dt = end_dt = None
        expense_records = get_requests({
            "user_id": doc.get("user_id"),
            "category": "shop_expense",
            "status": "approved",
            "start_date": start_dt,
            "end_date": end_dt,
        })
        doc["expense_records"] = expense_records
    return jsonify({"success": True, "settlement": doc})


@settlements_bp.get("/api/settlements/export/csv")
@admin_required
def api_export_settlements_csv():
    """Export settlements as CSV file."""
    filters = {}
    if request.args.get("week_start"):
        filters["week_start"] = request.args["week_start"]
    if request.args.get("week_end"):
        filters["week_end"] = request.args["week_end"]

    log.info("Export settlements CSV | filters=%s", filters)
    settlements = settlement_service.get_settlements(filters if filters else None)

    # Create CSV
    output = io.StringIO()
    writer = csv.writer(output)

    # Header row
    writer.writerow([
        "Staff Name",
        "Period Start",
        "Period End",
        "Base Salary",
        "Overtime Pay",
        "Expenses Reimbursed",
        "Advances Deducted",
        "Net Payable",
        "Hours Worked",
        "OT Hours",
    ])

    # Data rows
    for s in settlements:
        writer.writerow([
            s.get("staff_name") or s.get("full_name") or "-",
            s.get("week_start") or "-",
            s.get("week_end") or "-",
            s.get("base_salary") or s.get("weekly_salary") or 0,
            s.get("overtime_pay") or s.get("overtime") or 0,
            s.get("expenses") or s.get("shop_expenses") or 0,
            s.get("advances") or s.get("personal_advances") or 0,
            s.get("net_payable") or s.get("net_pay") or 0,
            s.get("hours_worked") or "-",
            s.get("ot_hours") or "-",
        ])

    csv_content = output.getvalue()
    output.close()

    # Generate filename with date range
    week_start = filters.get("week_start", "all")
    week_end = filters.get("week_end", "")
    filename = f"settlements_{week_start}_to_{week_end}.csv" if week_end else f"settlements_{week_start}.csv"

    response = make_response(csv_content)
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    return response


@settlements_bp.get("/api/settlements/export/pdf")
@admin_required
def api_export_settlements_pdf():
    """Export settlements as PDF file."""
    filters = {}
    if request.args.get("week_start"):
        filters["week_start"] = request.args["week_start"]
    if request.args.get("week_end"):
        filters["week_end"] = request.args["week_end"]

    log.info("Export settlements PDF | filters=%s", filters)
    settlements = settlement_service.get_settlements(filters if filters else None)

    # Create PDF using ReportLab
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), leftMargin=0.5*inch, rightMargin=0.5*inch)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Heading1"],
        fontSize=16,
        spaceAfter=20,
        alignment=1,  # Center
    )

    elements = []

    # Title
    week_start = filters.get("week_start", "")
    week_end = filters.get("week_end", "")
    period_text = f"{week_start} to {week_end}" if week_start and week_end else "All Periods"
    elements.append(Paragraph(f"Infinity Designer Boutique - Settlements Report", title_style))
    elements.append(Paragraph(f"Period: {period_text}", styles["Normal"]))
    elements.append(Spacer(1, 20))

    # Table data
    table_data = [
        ["Staff Name", "Period", "Base", "OT Pay", "Expenses", "Advances", "Net Payable"],
    ]

    total_base = 0
    total_ot = 0
    total_expenses = 0
    total_advances = 0
    total_net = 0

    for s in settlements:
        base = float(s.get("base_salary") or s.get("weekly_salary") or 0)
        ot = float(s.get("overtime_pay") or s.get("overtime") or 0)
        expenses = float(s.get("expenses") or s.get("shop_expenses") or 0)
        advances = float(s.get("advances") or s.get("personal_advances") or 0)
        net = float(s.get("net_payable") or s.get("net_pay") or 0)

        total_base += base
        total_ot += ot
        total_expenses += expenses
        total_advances += advances
        total_net += net

        ws = s.get("week_start") or ""
        we = s.get("week_end") or ""
        period = f"{ws[:10]} - {we[:10]}" if ws and we else "-"

        table_data.append([
            s.get("staff_name") or s.get("full_name") or "-",
            period,
            f"₹{base:,.0f}",
            f"+₹{ot:,.0f}",
            f"+₹{expenses:,.0f}",
            f"-₹{advances:,.0f}",
            f"₹{net:,.0f}",
        ])

    # Totals row
    table_data.append([
        f"TOTAL ({len(settlements)} records)",
        "",
        f"₹{total_base:,.0f}",
        f"+₹{total_ot:,.0f}",
        f"+₹{total_expenses:,.0f}",
        f"-₹{total_advances:,.0f}",
        f"₹{total_net:,.0f}",
    ])

    # Create table
    table = Table(table_data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4f46e5")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 10),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
        ("TOPPADDING", (0, 0), (-1, 0), 12),
        ("BACKGROUND", (0, 1), (-1, -2), colors.white),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#f3f4f6")),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, 1), (-1, -1), colors.black),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, colors.HexColor("#f9fafb")]),
        ("TOPPADDING", (0, 1), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 8),
    ]))

    elements.append(table)
    elements.append(Spacer(1, 30))

    # Footer
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    elements.append(Paragraph(f"Generated on: {generated_at}", styles["Normal"]))

    doc.build(elements)

    pdf_content = buffer.getvalue()
    buffer.close()

    filename = f"settlements_{week_start}_to_{week_end}.pdf" if week_start and week_end else "settlements.pdf"

    response = make_response(pdf_content)
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    return response
