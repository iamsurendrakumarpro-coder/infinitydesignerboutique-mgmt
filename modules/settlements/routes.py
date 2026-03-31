"""
modules/settlements/routes.py - Settlement Management Blueprint.

API Routes
----------
POST /api/settlements/generate       - Generate weekly settlements for all active staff
GET  /api/settlements                - List settlements (filterable by user/week)
GET  /api/settlements/<id>           - Get a single settlement
GET  /api/settlements/<id>/daily-summary - Daily attendance breakdown for a settlement
GET  /api/settlements/user/<user_id> - Get all settlements for a specific user
GET  /api/settlements/export/csv     - Export settlements as CSV
GET  /api/settlements/export/pdf     - Export settlements as PDF
"""
from __future__ import annotations

import csv
import io
import os
import platform
from datetime import datetime, date as date_type

from flask import Blueprint, request, session, jsonify, Response, make_response

from middleware.auth_middleware import login_required, admin_required
from services import settlement_service
from utils.logger import get_logger

log = get_logger(__name__)

# Single authoritative Blueprint instance.
settlements_bp = Blueprint("settlements", __name__)


def _register_pdf_font():
    """Register a Unicode TrueType font that supports ₹ for PDF export."""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    candidates = []
    if platform.system() == "Windows":
        windir = os.environ.get("WINDIR", r"C:\Windows")
        fonts_dir = os.path.join(windir, "Fonts")
        candidates = [
            (os.path.join(fonts_dir, "calibri.ttf"), "UniFont",
             os.path.join(fonts_dir, "calibrib.ttf"), "UniFont-Bold"),
            (os.path.join(fonts_dir, "arial.ttf"), "UniFont",
             os.path.join(fonts_dir, "arialbd.ttf"), "UniFont-Bold"),
        ]
    else:
        candidates = [
            ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "UniFont",
             "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "UniFont-Bold"),
            ("/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf", "UniFont",
             "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf", "UniFont-Bold"),
        ]

    for regular_path, regular_name, bold_path, bold_name in candidates:
        if os.path.exists(regular_path):
            try:
                pdfmetrics.registerFont(TTFont(regular_name, regular_path))
                if os.path.exists(bold_path):
                    pdfmetrics.registerFont(TTFont(bold_name, bold_path))
                else:
                    pdfmetrics.registerFont(TTFont(bold_name, regular_path))
                return regular_name, bold_name
            except Exception:
                continue

    return "Helvetica", "Helvetica-Bold"


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


@settlements_bp.put("/api/settlements/<settlement_id>/settle")
@admin_required
def api_mark_settlement(settlement_id: str):
    """Mark a settlement as settled (full or partial)."""
    body = request.get_json(silent=True) or {}
    amount = body.get("amount_settled")
    if amount is None:
        return jsonify({"success": False, "error": "amount_settled is required."}), 400

    try:
        amount = float(amount)
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "amount_settled must be a number."}), 400

    if amount < 0:
        return jsonify({"success": False, "error": "amount_settled cannot be negative."}), 400

    admin_id = session["user_id"]
    result = settlement_service.mark_settlement(settlement_id, amount, admin_id)
    if not result:
        return jsonify({"success": False, "error": "Settlement not found."}), 404

    return jsonify({"success": True, "settlement": result})


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

    page_str = str(request.args.get("page", "1")).strip()
    page_size_str = str(request.args.get("page_size", "100")).strip()
    try:
        page = max(int(page_str), 1)
        page_size = max(1, min(int(page_size_str), 500))
    except ValueError:
        return jsonify({"success": False, "error": "page and page_size must be integers."}), 400

    log.info("List settlements | filters=%s | page=%d | page_size=%d", filters, page, page_size)
    paged = settlement_service.get_settlements_page(filters if filters else None, page=page, page_size=page_size)
    return jsonify(
        {
            "success": True,
            "settlements": paged["items"],
            "pagination": {
                "page": paged["page"],
                "page_size": paged["page_size"],
                "total": paged["total"],
                "has_more": paged["has_more"],
            },
        }
    )


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

    return jsonify({"success": True, "settlement": doc})


@settlements_bp.get("/api/settlements/<settlement_id>/daily-summary")
@login_required
def api_settlement_daily_summary(settlement_id: str):
    """Daily attendance breakdown for a settlement period."""
    doc = settlement_service.get_settlement(settlement_id)
    if not doc:
        return jsonify({"success": False, "error": "Settlement not found."}), 404

    role = session.get("role")
    if role != "admin" and doc.get("user_id") != session["user_id"]:
        return jsonify({"success": False, "error": "Access denied."}), 403

    from services.attendance_service import get_attendance_history
    from services.settings_service import get_working_config
    from datetime import timedelta

    user_id = doc["user_id"]
    week_start_str = doc.get("week_start", "")
    week_end_str = doc.get("week_end", "")

    try:
        start_d = datetime.strptime(week_start_str, "%Y-%m-%d").date()
        end_d = datetime.strptime(week_end_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "Invalid settlement dates."}), 400

    records = get_attendance_history(user_id, start_d, end_d)
    config = get_working_config()
    standard_hours = config.get("standard_hours_per_day", 8)
    overtime_grace_minutes = int(config.get("overtime_grace_minutes", 30) or 30)

    # Build a map keyed by date string
    records_map = {}
    for r in records:
        date_str = r.get("date", "")
        records_map[date_str] = r

    # Build daily summary for each day in range
    daily = []
    current = start_d
    while current <= end_d:
        date_str = current.strftime("%Y-%m-%d")
        rec = records_map.get(date_str)
        day_name = current.strftime("%a")

        if rec and rec.get("punch_in"):
            mins = rec.get("duration_minutes", 0)
            hours = round(mins / 60.0, 2)
            threshold_minutes = (standard_hours * 60) + overtime_grace_minutes
            ot_hours = round(max(0, hours - standard_hours), 2) if mins > threshold_minutes else 0
            short_hours = round(max(0, standard_hours - hours), 2) if hours < standard_hours and hours > 0 else 0

            if rec.get("status") == "in":
                status_tag = "working"
            elif ot_hours > 0:
                status_tag = "overtime"
            elif short_hours > 0.5:
                status_tag = "short"
            else:
                status_tag = "normal"

            daily.append({
                "date": date_str,
                "day": day_name,
                "punch_in": rec.get("punch_in"),
                "punch_out": rec.get("punch_out"),
                "duration_minutes": mins,
                "hours_worked": hours,
                "ot_hours": ot_hours,
                "short_hours": short_hours,
                "status": status_tag,
            })
        else:
            daily.append({
                "date": date_str,
                "day": day_name,
                "punch_in": None,
                "punch_out": None,
                "duration_minutes": 0,
                "hours_worked": 0,
                "ot_hours": 0,
                "short_hours": 0,
                "status": "absent",
            })

        current += timedelta(days=1)

    return jsonify({
        "success": True,
        "staff_name": doc.get("full_name", ""),
        "week_start": week_start_str,
        "week_end": week_end_str,
        "standard_hours": standard_hours,
        "daily": daily,
    })


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
    """Export settlements as detailed PDF with attendance and financial line items per staff."""
    filters = {}
    if request.args.get("week_start"):
        filters["week_start"] = request.args["week_start"]
    if request.args.get("week_end"):
        filters["week_end"] = request.args["week_end"]

    include_details_raw = str(request.args.get("include_details", "0")).strip().lower()
    include_details = include_details_raw in {"1", "true", "yes", "y"}

    try:
        from services.settings_service import get_app_config
        app_config = get_app_config()
        boutique_name = str(app_config.get("boutique_name") or "").strip() or "Infinity Designer Boutique"
    except Exception:
        boutique_name = "Infinity Designer Boutique"

    log.info("Export settlements PDF | filters=%s | include_details=%s", filters, include_details)
    settlements = settlement_service.get_settlements(filters if filters else None)

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak,
        HRFlowable,
    )
    from services.settings_service import get_working_config
    from services.attendance_service import get_attendance_history
    from datetime import timedelta

    if include_details:
        from services.financial_service import get_approved_requests_for_period
        from services.overtime_service import get_approved_overtime_for_period

    font_regular, font_bold = _register_pdf_font()
    config = get_working_config()
    standard_hours = config.get("standard_hours_per_day", 8)
    overtime_grace_minutes = int(config.get("overtime_grace_minutes", 30) or 30)

    # Brand colors
    brand_primary = colors.HexColor("#e11d48")
    brand_light = colors.HexColor("#fff1f2")
    brand_dark = colors.HexColor("#881337")
    accent_green = colors.HexColor("#059669")
    accent_amber = colors.HexColor("#d97706")
    accent_red = colors.HexColor("#dc2626")
    row_alt = colors.HexColor("#fef2f2")
    gray_bg = colors.HexColor("#f9fafb")
    gray_border = colors.HexColor("#e5e7eb")

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=landscape(A4),
        leftMargin=0.5 * inch, rightMargin=0.5 * inch,
        topMargin=0.5 * inch, bottomMargin=0.5 * inch,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "PDFTitle", parent=styles["Heading1"],
        fontName=font_bold, fontSize=18, spaceAfter=6,
        alignment=1, textColor=brand_dark,
    )
    subtitle_style = ParagraphStyle(
        "PDFSubtitle", parent=styles["Normal"],
        fontName=font_regular, fontSize=10, spaceAfter=4,
        alignment=1, textColor=colors.HexColor("#6b7280"),
    )
    section_style = ParagraphStyle(
        "SectionHeading", parent=styles["Heading2"],
        fontName=font_bold, fontSize=12, spaceBefore=16,
        spaceAfter=6, textColor=brand_dark,
    )
    normal_style = ParagraphStyle(
        "PDFNormal", parent=styles["Normal"],
        fontName=font_regular, fontSize=9,
    )
    footer_style = ParagraphStyle(
        "PDFFooter", parent=styles["Normal"],
        fontName=font_regular, fontSize=8,
        textColor=colors.HexColor("#9ca3af"),
    )

    elements = []

    def _fmt_record_date(value, fallback: str = "-") -> str:
        if value is None:
            return fallback
        if hasattr(value, "strftime"):
            return value.strftime("%Y-%m-%d")
        text = str(value)
        return text[:10] if len(text) >= 10 else text

    def _recompute_hours(user_id: str | None, ws: str, we: str) -> tuple[float, float]:
        """Compute total worked and OT hours from attendance for a settlement period."""
        if not user_id or not ws or not we:
            return 0.0, 0.0
        try:
            start_d = datetime.strptime(ws, "%Y-%m-%d").date()
            end_d = datetime.strptime(we, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            return 0.0, 0.0

        records = get_attendance_history(user_id, start_d, end_d)
        total_hours = 0.0
        total_ot_hours = 0.0
        for rec in records:
            mins = float(rec.get("duration_minutes", 0) or 0)
            if mins <= 0:
                continue
            h = round(mins / 60.0, 2)
            total_hours += h
            threshold_minutes = (float(standard_hours) * 60.0) + float(overtime_grace_minutes)
            total_ot_hours += max(0.0, h - float(standard_hours)) if mins > threshold_minutes else 0.0
        return round(total_hours, 2), round(total_ot_hours, 2)

    # --- Page 1: Summary ---------------------------------------------------
    week_start = filters.get("week_start", "")
    week_end = filters.get("week_end", "")
    period_text = f"{week_start} to {week_end}" if week_start and week_end else "All Periods"

    elements.append(Paragraph(boutique_name, title_style))
    elements.append(Paragraph("Weekly Settlement Report", subtitle_style))
    elements.append(Paragraph(
        "Mode: Detailed" if include_details else "Mode: Summary",
        subtitle_style,
    ))
    elements.append(Paragraph(f"Period: {period_text}", subtitle_style))
    elements.append(Spacer(1, 16))
    elements.append(HRFlowable(
        width="100%", thickness=1, color=brand_primary,
        spaceAfter=16, spaceBefore=4,
    ))

    # Summary table
    summary_header = [
        Paragraph("<b>Staff Name</b>", normal_style),
        Paragraph("<b>Period</b>", normal_style),
        Paragraph("<b>Base</b>", normal_style),
        Paragraph("<b>OT Pay</b>", normal_style),
        Paragraph("<b>Advances</b>", normal_style),
        Paragraph("<b>Net Payable</b>", normal_style),
        Paragraph("<b>Hours</b>", normal_style),
        Paragraph("<b>OT Hrs</b>", normal_style),
    ]
    summary_data = [summary_header]

    total_base = total_ot = total_advances = total_net = 0

    for s in settlements:
        base = float(s.get("base_pay") or s.get("base_salary") or s.get("weekly_salary") or 0)
        ot = float(s.get("overtime_pay") or s.get("overtime") or 0)
        advances = float(s.get("advances") or s.get("personal_advances") or 0)
        net = float(s.get("net_payable") or s.get("net_pay") or 0)
        ws = s.get("week_start") or ""
        we = s.get("week_end") or ""
        hrs, ot_hrs = _recompute_hours(s.get("user_id"), ws, we)

        total_base += base
        total_ot += ot
        total_advances += advances
        total_net += net

        period = f"{ws} - {we}" if ws and we else "-"

        summary_data.append([
            s.get("staff_name") or s.get("full_name") or "-",
            period,
            f"\u20b9{base:,.0f}",
            f"+\u20b9{ot:,.0f}",
            f"-\u20b9{advances:,.0f}",
            f"\u20b9{net:,.0f}",
            f"{hrs:.1f}",
            f"{ot_hrs:.1f}",
        ])

    summary_data.append([
        Paragraph(f"<b>TOTAL ({len(settlements)} staff)</b>", normal_style),
        "",
        f"\u20b9{total_base:,.0f}",
        f"+\u20b9{total_ot:,.0f}",
        f"-\u20b9{total_advances:,.0f}",
        f"\u20b9{total_net:,.0f}",
        "", "",
    ])

    col_widths = [1.75 * inch, 1.5 * inch, 0.9 * inch, 0.9 * inch,
                  0.95 * inch, 1.1 * inch, 0.7 * inch, 0.7 * inch]
    summary_table = Table(summary_data, colWidths=col_widths, repeatRows=1)
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), brand_primary),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), font_bold),
        ("FONTNAME", (0, 1), (-1, -1), font_regular),
        ("FONTNAME", (0, -1), (-1, -1), font_bold),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 10),
        ("TOPPADDING", (0, 0), (-1, 0), 10),
        ("BACKGROUND", (0, -1), (-1, -1), brand_light),
        ("TEXTCOLOR", (0, 1), (-1, -1), colors.black),
        ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.5, gray_border),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, gray_bg]),
        ("TOPPADDING", (0, 1), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 7),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    elements.append(summary_table)

    # --- Per-Employee Summary ----------------------------------------------
    for s in settlements:
        staff_name = s.get("staff_name") or s.get("full_name") or "-"
        ws = s.get("week_start") or "-"
        we = s.get("week_end") or "-"
        user_id = s.get("user_id")
        base = float(s.get("base_pay") or s.get("base_salary") or s.get("weekly_salary") or 0)
        ot = float(s.get("overtime_pay") or s.get("overtime") or 0)
        advances = float(s.get("advances") or s.get("personal_advances") or 0)
        net = float(s.get("net_payable") or s.get("net_pay") or 0)
        hours = float(s.get("hours_worked") or 0)
        ot_hours = float(s.get("ot_hours") or 0)
        settled = float(s.get("amount_settled") or 0)
        pending = max(0.0, net - settled)

        # Recompute hours from attendance so metric table and daily table stay consistent.
        recomputed_hours, recomputed_ot_hours = _recompute_hours(user_id, ws if ws != "-" else "", we if we != "-" else "")
        if recomputed_hours or recomputed_ot_hours:
            hours = recomputed_hours
            ot_hours = recomputed_ot_hours

        elements.append(PageBreak())
        elements.append(Paragraph(f"Employee Summary - {staff_name}", section_style))
        elements.append(Paragraph(f"Period: {ws} to {we}", footer_style))
        elements.append(Spacer(1, 8))
        elements.append(Paragraph("Payroll Snapshot", footer_style))
        elements.append(Spacer(1, 4))

        emp_data = [
            [Paragraph("<b>Metric</b>", normal_style), Paragraph("<b>Value</b>", normal_style)],
            ["Base Pay", f"\u20b9{base:,.2f}"],
            ["Overtime Pay", f"\u20b9{ot:,.2f}"],
            ["Advances", f"\u20b9{advances:,.2f}"],
            ["Net Payable", f"\u20b9{net:,.2f}"],
            ["Amount Settled", f"\u20b9{settled:,.2f}"],
            ["Pending", f"\u20b9{pending:,.2f}"],
            ["Hours Worked", f"{hours:.2f} h"],
            ["OT Hours", f"{ot_hours:.2f} h"],
        ]
        emp_table = Table(emp_data, colWidths=[2.2 * inch, 2.2 * inch], repeatRows=1)
        emp_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), brand_dark),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), font_bold),
            ("FONTNAME", (0, 1), (-1, -1), font_regular),
            ("GRID", (0, 0), (-1, -1), 0.5, gray_border),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, gray_bg]),
            ("ALIGN", (1, 1), (1, -1), "RIGHT"),
            ("TEXTCOLOR", (1, 4), (1, 4), colors.HexColor("#065f46")),
            ("TEXTCOLOR", (1, 6), (1, 6), colors.HexColor("#b45309")),
            ("BACKGROUND", (0, 4), (-1, 4), colors.HexColor("#ecfdf5")),
            ("BACKGROUND", (0, 6), (-1, 6), colors.HexColor("#fffbeb")),
            ("LINEABOVE", (0, 4), (-1, 4), 0.8, gray_border),
            ("LINEBELOW", (0, 6), (-1, 6), 0.8, gray_border),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        elements.append(emp_table)

        # Daily attendance summary (login/logout + hours + OT) for the employee.
        if user_id and ws != "-" and we != "-":
            try:
                start_d = datetime.strptime(ws, "%Y-%m-%d").date()
                end_d = datetime.strptime(we, "%Y-%m-%d").date()
            except (ValueError, TypeError):
                start_d = end_d = None

            if start_d and end_d:
                records = get_attendance_history(user_id, start_d, end_d)
                records_map = {r.get("date", ""): r for r in records}

                daily_data = [[
                    Paragraph("<b>Date</b>", normal_style),
                    Paragraph("<b>Day</b>", normal_style),
                    Paragraph("<b>Login</b>", normal_style),
                    Paragraph("<b>Logout</b>", normal_style),
                    Paragraph("<b>Normal Hrs</b>", normal_style),
                    Paragraph("<b>OT Hrs</b>", normal_style),
                    Paragraph("<b>Total Hrs</b>", normal_style),
                    Paragraph("<b>Status</b>", normal_style),
                ]]

                total_normal_hrs = 0.0
                total_ot_hrs = 0.0
                row_status_styles = []

                current = start_d
                row_idx = 1
                while current <= end_d:
                    date_str = current.strftime("%Y-%m-%d")
                    day_name = current.strftime("%a")
                    rec = records_map.get(date_str)

                    if rec and rec.get("punch_in"):
                        mins = float(rec.get("duration_minutes", 0) or 0)
                        hours = round(mins / 60.0, 2)
                        normal_hrs = round(min(hours, float(standard_hours)), 2)
                        threshold_minutes = (float(standard_hours) * 60.0) + float(overtime_grace_minutes)
                        ot_hrs = round(max(0.0, hours - float(standard_hours)), 2) if mins > threshold_minutes else 0.0
                        total_normal_hrs += normal_hrs
                        total_ot_hrs += ot_hrs

                        punch_in_str = rec.get("punch_in", "-")
                        punch_out_str = rec.get("punch_out", "-") or "Still In"
                        if isinstance(punch_in_str, str) and len(punch_in_str) > 10:
                            punch_in_str = punch_in_str[11:16] if "T" in punch_in_str else punch_in_str[-8:-3] if len(punch_in_str) > 8 else punch_in_str
                        if isinstance(punch_out_str, str) and len(punch_out_str) > 10 and punch_out_str != "Still In":
                            punch_out_str = punch_out_str[11:16] if "T" in punch_out_str else punch_out_str[-8:-3] if len(punch_out_str) > 8 else punch_out_str

                        status_text = "Present"
                        if ot_hrs > 0:
                            status_text = "Overtime"
                        elif punch_out_str == "Still In":
                            status_text = "Working"

                        daily_data.append([
                            date_str,
                            day_name,
                            punch_in_str,
                            punch_out_str,
                            f"{normal_hrs:.2f}",
                            f"{ot_hrs:.2f}" if ot_hrs > 0 else "0",
                            f"{(normal_hrs + ot_hrs):.2f}",
                            status_text,
                        ])
                        if status_text == "Overtime":
                            row_status_styles.append(("BACKGROUND", (0, row_idx), (-1, row_idx), colors.HexColor("#ecfdf5")))
                            row_status_styles.append(("TEXTCOLOR", (7, row_idx), (7, row_idx), colors.HexColor("#047857")))
                        elif status_text == "Working":
                            row_status_styles.append(("BACKGROUND", (0, row_idx), (-1, row_idx), colors.HexColor("#eff6ff")))
                            row_status_styles.append(("TEXTCOLOR", (7, row_idx), (7, row_idx), colors.HexColor("#1d4ed8")))
                        else:
                            row_status_styles.append(("TEXTCOLOR", (7, row_idx), (7, row_idx), colors.HexColor("#334155")))
                    else:
                        daily_data.append([date_str, day_name, "-", "-", "0", "0", "0", "Absent"])
                        row_status_styles.append(("BACKGROUND", (0, row_idx), (-1, row_idx), colors.HexColor("#fffbeb")))
                        row_status_styles.append(("TEXTCOLOR", (7, row_idx), (7, row_idx), colors.HexColor("#b45309")))

                    current += timedelta(days=1)
                    row_idx += 1

                daily_data.append([
                    Paragraph("<b>Total</b>", normal_style),
                    "",
                    "",
                    "",
                    f"{total_normal_hrs:.2f}",
                    f"{total_ot_hrs:.2f}",
                    f"{(total_normal_hrs + total_ot_hrs):.2f}",
                    "",
                ])

                elements.append(Spacer(1, 8))
                elements.append(Paragraph("Day-wise Attendance Summary", footer_style))
                elements.append(Spacer(1, 4))
                daily_table = Table(
                    daily_data,
                    colWidths=[0.95 * inch, 0.5 * inch, 0.75 * inch, 0.75 * inch, 0.75 * inch, 0.6 * inch, 0.75 * inch, 0.75 * inch],
                    repeatRows=1,
                )
                daily_table.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), brand_primary),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), font_bold),
                    ("FONTNAME", (0, 1), (-1, -1), font_regular),
                    ("FONTNAME", (0, -1), (-1, -1), font_bold),
                    ("BACKGROUND", (0, -1), (-1, -1), brand_light),
                    ("GRID", (0, 0), (-1, -1), 0.4, gray_border),
                    ("ALIGN", (4, 1), (6, -1), "RIGHT"),
                    ("ALIGN", (7, 1), (7, -1), "CENTER"),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, gray_bg]),
                    ("TEXTCOLOR", (7, 1), (7, -1), colors.HexColor("#334155")),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ] + row_status_styles))
                elements.append(daily_table)

    # --- Per-Staff Daily Breakdown -----------------------------------------
    if include_details:
        for s in settlements:
            user_id = s.get("user_id")
            staff_name = s.get("staff_name") or s.get("full_name") or "-"
            ws = s.get("week_start") or ""
            we = s.get("week_end") or ""

            if not user_id or not ws or not we:
                continue

            try:
                start_d = datetime.strptime(ws, "%Y-%m-%d").date()
                end_d = datetime.strptime(we, "%Y-%m-%d").date()
            except (ValueError, TypeError):
                continue

            records = get_attendance_history(user_id, start_d, end_d)
            records_map = {r.get("date", ""): r for r in records}

            elements.append(PageBreak())
            elements.append(Paragraph(
                f"Daily Attendance — {staff_name}",
                section_style,
            ))
            elements.append(Paragraph(f"Period: {ws} to {we}", footer_style))
            elements.append(Spacer(1, 10))

            daily_header = [
                Paragraph("<b>Date</b>", normal_style),
                Paragraph("<b>Day</b>", normal_style),
                Paragraph("<b>Login</b>", normal_style),
                Paragraph("<b>Logout</b>", normal_style),
                Paragraph("<b>Hours</b>", normal_style),
                Paragraph("<b>OT Hours</b>", normal_style),
                Paragraph("<b>Short</b>", normal_style),
                Paragraph("<b>Status</b>", normal_style),
            ]
            daily_data = [daily_header]
            total_day_hrs = 0
            total_day_ot = 0
            days_present = 0

            current = start_d
            row_idx = 1
            row_styles = []
            while current <= end_d:
                date_str = current.strftime("%Y-%m-%d")
                day_name = current.strftime("%a")
                rec = records_map.get(date_str)

                if rec and rec.get("punch_in"):
                    days_present += 1
                    mins = rec.get("duration_minutes", 0)
                    hours = round(mins / 60.0, 2)
                    threshold_minutes = (standard_hours * 60) + overtime_grace_minutes
                    ot_h = round(max(0, hours - standard_hours), 2) if mins > threshold_minutes else 0
                    short_h = round(max(0, standard_hours - hours), 2) if hours < standard_hours and hours > 0 else 0
                    total_day_hrs += hours
                    total_day_ot += ot_h

                    punch_in_str = rec.get("punch_in", "-")
                    punch_out_str = rec.get("punch_out", "-") or "Still In"

                    # Format timestamps — take just time portion
                    if isinstance(punch_in_str, str) and len(punch_in_str) > 10:
                        punch_in_str = punch_in_str[11:16] if "T" in punch_in_str else punch_in_str[-8:-3] if len(punch_in_str) > 8 else punch_in_str
                    if isinstance(punch_out_str, str) and len(punch_out_str) > 10 and punch_out_str != "Still In":
                        punch_out_str = punch_out_str[11:16] if "T" in punch_out_str else punch_out_str[-8:-3] if len(punch_out_str) > 8 else punch_out_str

                    if ot_h > 0:
                        status_text = "OVERTIME"
                        row_styles.append(("BACKGROUND", (0, row_idx), (-1, row_idx), colors.HexColor("#ecfdf5")))
                        row_styles.append(("TEXTCOLOR", (7, row_idx), (7, row_idx), accent_green))
                    elif short_h > 0.5:
                        status_text = "SHORT"
                        row_styles.append(("BACKGROUND", (0, row_idx), (-1, row_idx), colors.HexColor("#fef2f2")))
                        row_styles.append(("TEXTCOLOR", (7, row_idx), (7, row_idx), accent_red))
                    elif punch_out_str == "Still In":
                        status_text = "WORKING"
                        row_styles.append(("TEXTCOLOR", (7, row_idx), (7, row_idx), accent_amber))
                    else:
                        status_text = "OK"

                    daily_data.append([
                        date_str, day_name, punch_in_str, punch_out_str,
                        f"{hours:.1f}h", f"{ot_h:.1f}h" if ot_h > 0 else "-",
                        f"{short_h:.1f}h" if short_h > 0 else "-", status_text,
                    ])
                else:
                    daily_data.append([
                        date_str, day_name, "-", "-", "-", "-", "-", "ABSENT",
                    ])
                    row_styles.append(("BACKGROUND", (0, row_idx), (-1, row_idx), colors.HexColor("#fef3c7")))
                    row_styles.append(("TEXTCOLOR", (7, row_idx), (7, row_idx), accent_amber))

                row_idx += 1
                current += timedelta(days=1)

            # Totals row for daily
            daily_data.append([
                Paragraph(f"<b>Total</b>", normal_style),
                f"{days_present} days", "", "",
                f"{total_day_hrs:.1f}h",
                f"{total_day_ot:.1f}h" if total_day_ot > 0 else "-",
                "", "",
            ])

            daily_col_widths = [1.1 * inch, 0.6 * inch, 0.9 * inch, 0.9 * inch,
                                0.7 * inch, 0.7 * inch, 0.7 * inch, 0.9 * inch]
            daily_table = Table(daily_data, colWidths=daily_col_widths, repeatRows=1)

            base_style = [
                ("BACKGROUND", (0, 0), (-1, 0), brand_dark),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), font_bold),
                ("FONTNAME", (0, 1), (-1, -1), font_regular),
                ("FONTNAME", (0, -1), (-1, -1), font_bold),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("BACKGROUND", (0, -1), (-1, -1), brand_light),
                ("ALIGN", (4, 0), (-1, -1), "CENTER"),
                ("GRID", (0, 0), (-1, -1), 0.5, gray_border),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
            base_style.extend(row_styles)
            daily_table.setStyle(TableStyle(base_style))
            elements.append(daily_table)

            overtime_records = get_approved_overtime_for_period(user_id, start_d, end_d)
            advance_records = get_approved_requests_for_period(user_id, start_d, end_d, "personal_advance")

            elements.append(Spacer(1, 10))
            elements.append(Paragraph("Approved Overtime Line Items", section_style))
            if overtime_records:
                overtime_data = [[
                    Paragraph("<b>Date</b>", normal_style),
                    Paragraph("<b>OT Minutes</b>", normal_style),
                    Paragraph("<b>OT Hours</b>", normal_style),
                    Paragraph("<b>Payout</b>", normal_style),
                ]]
                overtime_total = 0.0
                for rec in overtime_records:
                    mins = float(rec.get("overtime_minutes") or 0)
                    payout = float(rec.get("calculated_payout") or 0)
                    overtime_total += payout
                    overtime_data.append([
                        rec.get("date") or "-",
                        f"{mins:.0f}",
                        f"{(mins / 60.0):.2f}",
                        f"\u20b9{payout:,.2f}",
                    ])
                overtime_data.append([
                    Paragraph("<b>Total</b>", normal_style),
                    "",
                    "",
                    f"\u20b9{overtime_total:,.2f}",
                ])
                overtime_table = Table(overtime_data, colWidths=[1.3 * inch, 1.1 * inch, 1.0 * inch, 1.1 * inch], repeatRows=1)
                overtime_table.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), brand_dark),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), font_bold),
                    ("FONTNAME", (0, 1), (-1, -1), font_regular),
                    ("FONTNAME", (0, -1), (-1, -1), font_bold),
                    ("BACKGROUND", (0, -1), (-1, -1), brand_light),
                    ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                    ("GRID", (0, 0), (-1, -1), 0.5, gray_border),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]))
                elements.append(overtime_table)
            else:
                elements.append(Paragraph("No approved overtime records in this period.", footer_style))

            elements.append(Spacer(1, 8))
            elements.append(Paragraph("Approved Advances (Deducted)", section_style))
            if advance_records:
                advance_data = [[
                    Paragraph("<b>Date</b>", normal_style),
                    Paragraph("<b>Notes</b>", normal_style),
                    Paragraph("<b>Amount</b>", normal_style),
                ]]
                advance_total = 0.0
                for rec in advance_records:
                    amount = float(rec.get("amount") or 0)
                    advance_total += amount
                    advance_data.append([
                        _fmt_record_date(rec.get("created_at")),
                        rec.get("notes") or "-",
                        f"\u20b9{amount:,.2f}",
                    ])
                advance_data.append([
                    Paragraph("<b>Total</b>", normal_style),
                    "",
                    f"\u20b9{advance_total:,.2f}",
                ])
                advance_table = Table(advance_data, colWidths=[1.1 * inch, 4.7 * inch, 1.1 * inch], repeatRows=1)
                advance_table.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), brand_dark),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), font_bold),
                    ("FONTNAME", (0, 1), (-1, -1), font_regular),
                    ("FONTNAME", (0, -1), (-1, -1), font_bold),
                    ("BACKGROUND", (0, -1), (-1, -1), brand_light),
                    ("ALIGN", (2, 0), (2, -1), "RIGHT"),
                    ("GRID", (0, 0), (-1, -1), 0.5, gray_border),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]))
                elements.append(advance_table)
            else:
                elements.append(Paragraph("No approved personal advances in this period.", footer_style))

            # Staff settlement summary line
            net = float(s.get("net_payable") or s.get("net_pay") or 0)
            elements.append(Spacer(1, 8))
            elements.append(Paragraph(
                f"Net Payable: <b>\u20b9{net:,.0f}</b> &nbsp;|&nbsp; "
                f"Standard: {standard_hours}h/day &nbsp;|&nbsp; "
                f"Records: OT {len(overtime_records)}, Advances {len(advance_records)}",
                normal_style,
            ))

    # --- Footer ------------------------------------------------------------
    elements.append(Spacer(1, 24))
    elements.append(HRFlowable(
        width="100%", thickness=0.5, color=gray_border,
        spaceAfter=8, spaceBefore=8,
    ))
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    elements.append(Paragraph(
        f"Generated on {generated_at} &nbsp;|&nbsp; {boutique_name}",
        footer_style,
    ))

    doc.build(elements)

    pdf_content = buffer.getvalue()
    buffer.close()

    filename = f"settlements_{week_start}_to_{week_end}.pdf" if week_start and week_end else "settlements.pdf"
    if not include_details:
        filename = filename.replace(".pdf", "_summary.pdf")

    response = make_response(pdf_content)
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    return response
