"""
modules/financial/routes.py - Financial Requests Blueprint.

API Routes
----------
POST  /api/financial/requests       - Create a financial request (any logged-in user)
GET   /api/financial/requests       - List requests (staff sees own; admin/manager can filter)
GET   /api/financial/requests/<id>  - Get a single request (own or admin)
PATCH /api/financial/requests/<id>  - Manager/admin approve/reject a pending request
GET   /api/financial/reimbursements - Admin list of approved shop expenses
PATCH /api/financial/reimbursements/<id>/mark-paid - Admin marks reimbursement paid
GET   /api/financial/reimbursements/export/csv - Admin reimbursement export CSV
GET   /api/financial/reimbursements/export/pdf - Admin reimbursement export PDF
"""
from __future__ import annotations

import csv
import io
import os
import platform
import uuid
from datetime import datetime

from flask import Blueprint, request, session, jsonify, make_response

from middleware.auth_middleware import login_required, admin_required, manager_or_admin_required
from services import financial_service
from utils.logger import get_logger
from utils.storage_provider import upload_bytes

log = get_logger(__name__)

financial_bp = Blueprint("financial", __name__)


def _register_pdf_font():
    """Register a Unicode TrueType font that supports rupee symbol for PDF export."""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    candidates = []
    if platform.system() == "Windows":
        windir = os.environ.get("WINDIR", r"C:\Windows")
        fonts_dir = os.path.join(windir, "Fonts")
        candidates = [
            (
                os.path.join(fonts_dir, "calibri.ttf"),
                "UniFont",
                os.path.join(fonts_dir, "calibrib.ttf"),
                "UniFont-Bold",
            ),
            (
                os.path.join(fonts_dir, "arial.ttf"),
                "UniFont",
                os.path.join(fonts_dir, "arialbd.ttf"),
                "UniFont-Bold",
            ),
        ]
    else:
        candidates = [
            (
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "UniFont",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "UniFont-Bold",
            ),
            (
                "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
                "UniFont",
                "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
                "UniFont-Bold",
            ),
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


@financial_bp.post("/api/financial/requests")
@login_required
def api_create_request():
    """Create a financial request (shop_expense or personal_advance)."""
    content_type = (request.content_type or "").lower()
    is_multipart = "multipart/form-data" in content_type

    if is_multipart:
        body = request.form.to_dict(flat=True)
    else:
        body = request.get_json(silent=True) or {}

    user_id = session["user_id"]

    if is_multipart:
        request_type = str(body.get("type", "")).strip()
        if request_type == "shop_expense":
            category = str(body.get("category", "")).strip().lower()
            bill_file = request.files.get("bill_image")
            # Bill is required for shop expenses except the 'food' category (Food / Tea)
            if category != 'food' and bill_file is None:
                return jsonify({"success": False, "error": "Bill image is required for shop expenses."}), 400

            if bill_file is not None:
                bill_bytes = bill_file.read()
                if not bill_bytes:
                    return jsonify({"success": False, "error": "Uploaded bill file is empty."}), 400
                if len(bill_bytes) > 10 * 1024 * 1024:
                    return jsonify({"success": False, "error": "Bill file must be 10 MB or smaller."}), 400

                mime = str(bill_file.mimetype or "").lower()
                allowed_mime = {"image/jpeg", "image/png", "image/webp", "application/pdf"}
                if mime and mime not in allowed_mime:
                    return jsonify({"success": False, "error": "Only JPG, PNG, WEBP or PDF bills are allowed."}), 400

                original_name = bill_file.filename or "bill"
                safe_name = "".join(ch if (ch.isalnum() or ch in {"-", "_", "."}) else "_" for ch in original_name)
                storage_path = f"financial/bills/{user_id}/{uuid.uuid4()}_{safe_name}"
                ok, err, meta = upload_bytes(storage_path, bill_bytes, content_type=(mime or "application/octet-stream"))
                if not ok:
                    log.error("Bill upload failed | user_id=%s | error=%s", user_id, err)
                    return jsonify({"success": False, "error": "Bill upload failed. Please try again."}), 500

                body["gcs_path"] = meta.get("storage_path", "")

    log.info("Create financial request | user_id=%s | type=%s | payload=%s", user_id, body.get("type"), body)

    success, error, doc = financial_service.create_request(user_id, body)
    if not success:
        log.error("Create financial request failed | user_id=%s | error=%s", user_id, error)
        return jsonify({"success": False, "error": error}), 400

    return jsonify({"success": True, "request": doc}), 201


@financial_bp.get("/api/financial/requests")
@login_required
def api_list_requests():
    """
    List financial requests.

    Query params:
        status  : pending | approved | rejected
        user_id : Filter by user (admin/manager only; others see own only)
    """
    role = session.get("role")
    filters = {}

    status_filter = request.args.get("status")
    if status_filter:
        filters["status"] = status_filter

    category_filter = request.args.get("category")
    if category_filter:
        filters["category"] = category_filter

    type_filter = request.args.get("type")
    if type_filter:
        filters["type"] = type_filter

    reimbursement_status = request.args.get("reimbursement_status")
    if reimbursement_status:
        filters["reimbursement_status"] = reimbursement_status

    start_date = request.args.get("start_date")
    if start_date:
        filters["start_date"] = start_date

    end_date = request.args.get("end_date")
    if end_date:
        filters["end_date"] = end_date

    if role in {"admin", "manager"}:
        uid = request.args.get("user_id")
        if uid:
            filters["user_id"] = uid
    else:
        filters["user_id"] = session["user_id"]

    log.info("List financial requests | role=%s | filters=%s", role, filters)
    docs = financial_service.get_requests(filters if filters else None)
    return jsonify({"success": True, "requests": docs})


@financial_bp.get("/api/financial/reimbursements")
@admin_required
def api_list_reimbursements():
    """List approved shop-expense reimbursements for admin review/payment."""
    filters = {
        "type": "shop_expense",
        "status": "approved",
    }

    reimbursement_status = request.args.get("reimbursement_status", "").strip()
    if reimbursement_status:
        filters["reimbursement_status"] = reimbursement_status

    user_id = request.args.get("user_id", "").strip()
    if user_id:
        filters["user_id"] = user_id

    start_date = request.args.get("start_date", "").strip()
    if start_date:
        filters["start_date"] = start_date

    end_date = request.args.get("end_date", "").strip()
    if end_date:
        filters["end_date"] = end_date

    reimbursements = financial_service.get_requests(filters)
    log.info("List reimbursements | filters=%s | count=%d", filters, len(reimbursements))
    return jsonify({"success": True, "reimbursements": reimbursements})


@financial_bp.patch("/api/financial/reimbursements/<request_id>/mark-paid")
@admin_required
def api_mark_reimbursement_paid(request_id: str):
    """Mark an approved shop-expense reimbursement as paid."""
    body = request.get_json(silent=True) or {}
    notes = str(body.get("notes", "")).strip()
    admin_id = session["user_id"]

    success, error = financial_service.mark_reimbursed(request_id, admin_id, notes)
    if not success:
        log.error("Mark reimbursement paid failed | request_id=%s | error=%s", request_id, error)
        return jsonify({"success": False, "error": error}), 400

    return jsonify({"success": True, "request_id": request_id})


@financial_bp.get("/api/financial/reimbursements/export/csv")
@admin_required
def api_export_reimbursements_csv():
    """Export reimbursements as CSV."""
    filters = {
        "type": "shop_expense",
        "status": "approved",
    }
    reimbursement_status = request.args.get("reimbursement_status", "").strip()
    if reimbursement_status:
        filters["reimbursement_status"] = reimbursement_status
    user_id = request.args.get("user_id", "").strip()
    if user_id:
        filters["user_id"] = user_id
    start_date = request.args.get("start_date", "").strip()
    if start_date:
        filters["start_date"] = start_date
    end_date = request.args.get("end_date", "").strip()
    if end_date:
        filters["end_date"] = end_date

    rows = financial_service.get_requests(filters)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Request ID",
        "Staff Name",
        "Category",
        "Amount",
        "Request Date",
        "Reimbursement Status",
        "Reimbursed Date",
        "Bill URL",
    ])
    for r in rows:
        writer.writerow([
            r.get("request_id") or "",
            r.get("requester_name") or r.get("staff_name") or "-",
            r.get("category") or "-",
            r.get("amount") or 0,
            r.get("created_at") or "-",
            r.get("reimbursement_status") or "pending",
            r.get("reimbursed_at") or "-",
            r.get("receipt_url") or "",
        ])

    response = make_response(output.getvalue())
    output.close()
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    response.headers["Content-Disposition"] = "attachment; filename=reimbursements.csv"
    return response


@financial_bp.get("/api/financial/reimbursements/export/pdf")
@admin_required
def api_export_reimbursements_pdf():
    """Export reimbursements as PDF with the same visual language as settlements export."""
    filters = {
        "type": "shop_expense",
        "status": "approved",
    }
    reimbursement_status = request.args.get("reimbursement_status", "").strip()
    if reimbursement_status:
        filters["reimbursement_status"] = reimbursement_status
    user_id = request.args.get("user_id", "").strip()
    if user_id:
        filters["user_id"] = user_id
    start_date = request.args.get("start_date", "").strip()
    if start_date:
        filters["start_date"] = start_date
    end_date = request.args.get("end_date", "").strip()
    if end_date:
        filters["end_date"] = end_date

    rows = financial_service.get_requests(filters)

    try:
        from services.settings_service import get_app_config
        app_config = get_app_config()
        boutique_name = str(app_config.get("boutique_name") or "").strip() or "Infinity Designer Boutique"
    except Exception:
        boutique_name = "Infinity Designer Boutique"

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable, PageBreak

    font_regular, font_bold = _register_pdf_font()

    brand_primary = colors.HexColor("#e11d48")
    brand_light = colors.HexColor("#fff1f2")
    brand_dark = colors.HexColor("#881337")
    gray_bg = colors.HexColor("#f9fafb")
    gray_border = colors.HexColor("#e5e7eb")

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=0.5 * inch,
        rightMargin=0.5 * inch,
        topMargin=0.5 * inch,
        bottomMargin=0.5 * inch,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "PDFTitle",
        parent=styles["Heading1"],
        fontName=font_bold,
        fontSize=18,
        spaceAfter=6,
        alignment=1,
        textColor=brand_dark,
    )
    subtitle_style = ParagraphStyle(
        "PDFSubtitle",
        parent=styles["Normal"],
        fontName=font_regular,
        fontSize=10,
        spaceAfter=4,
        alignment=1,
        textColor=colors.HexColor("#6b7280"),
    )
    normal_style = ParagraphStyle(
        "PDFNormal",
        parent=styles["Normal"],
        fontName=font_regular,
        fontSize=8,
    )

    if start_date and end_date:
        report_label = f"{start_date} to {end_date}"
    elif start_date:
        report_label = f"From {start_date}"
    elif end_date:
        report_label = f"Until {end_date}"
    else:
        report_label = "All"

    elements = [
        Paragraph(boutique_name, title_style),
        Paragraph("Reimbursements Report", subtitle_style),
        Paragraph(f"Period: {report_label}", subtitle_style),
        Spacer(1, 12),
        HRFlowable(width="100%", thickness=1, color=brand_primary, spaceAfter=12, spaceBefore=4),
    ]

    table_data = [[
        Paragraph("<b>Staff Name</b>", normal_style),
        Paragraph("<b>Category</b>", normal_style),
        Paragraph("<b>Amount</b>", normal_style),
        Paragraph("<b>Requested</b>", normal_style),
        Paragraph("<b>Status</b>", normal_style),
        Paragraph("<b>Reimbursed</b>", normal_style),
    ]]

    total_amount = 0.0
    for r in rows:
        amount = float(r.get("amount") or 0)
        total_amount += amount
        created_raw = r.get("created_at") or ""
        reimbursed_raw = r.get("reimbursed_at") or ""

        try:
            created_fmt = datetime.fromisoformat(str(created_raw)).strftime("%d %b %Y") if created_raw else "-"
        except (ValueError, TypeError):
            created_fmt = str(created_raw)[:10] if created_raw else "-"

        try:
            reimbursed_fmt = datetime.fromisoformat(str(reimbursed_raw)).strftime("%d %b %Y") if reimbursed_raw else "-"
        except (ValueError, TypeError):
            reimbursed_fmt = str(reimbursed_raw)[:10] if reimbursed_raw else "-"

        table_data.append([
            r.get("requester_name") or r.get("staff_name") or "-",
            r.get("category") or "-",
            f"\u20b9{amount:,.0f}",
            created_fmt,
            (r.get("reimbursement_status") or "pending").title(),
            reimbursed_fmt,
        ])

    table_data.append([
        Paragraph(f"<b>TOTAL ({len(rows)} requests)</b>", normal_style),
        "",
        f"\u20b9{total_amount:,.0f}",
        "",
        "",
        "",
    ])

    table = Table(
        table_data,
        colWidths=[2.7 * inch, 1.4 * inch, 1.2 * inch, 1.3 * inch, 1.0 * inch, 1.3 * inch],
        repeatRows=1,
    )
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), brand_primary),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), font_bold),
        ("FONTNAME", (0, 1), (-1, -1), font_regular),
        ("FONTNAME", (0, -1), (-1, -1), font_bold),
        ("BACKGROUND", (0, -1), (-1, -1), brand_light),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.4, gray_border),
        ("ALIGN", (2, 1), (2, -1), "RIGHT"),
        ("ALIGN", (4, 1), (4, -1), "CENTER"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, gray_bg]),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    elements.append(table)

    # Per-employee reimbursement summaries.
    grouped: dict[str, list[dict]] = {}
    for r in rows:
        staff_name = str(r.get("requester_name") or r.get("staff_name") or "Unknown Staff")
        grouped.setdefault(staff_name, []).append(r)

    for staff_name in sorted(grouped.keys()):
        staff_rows = grouped[staff_name]
        total_staff_amount = sum(float(item.get("amount") or 0) for item in staff_rows)
        paid_count = sum(1 for item in staff_rows if str(item.get("reimbursement_status") or "").lower() == "paid")
        pending_count = len(staff_rows) - paid_count

        elements.append(PageBreak())
        elements.append(Paragraph(f"Employee Summary - {staff_name}", title_style))
        elements.append(Paragraph(f"Period: {report_label}", subtitle_style))
        elements.append(Spacer(1, 8))

        summary_data = [
            [Paragraph("<b>Metric</b>", normal_style), Paragraph("<b>Value</b>", normal_style)],
            ["Total Requests", str(len(staff_rows))],
            ["Paid", str(paid_count)],
            ["Pending", str(pending_count)],
            ["Total Amount", f"\u20b9{total_staff_amount:,.2f}"],
        ]
        summary_table = Table(summary_data, colWidths=[2.4 * inch, 2.4 * inch], repeatRows=1)
        summary_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), brand_dark),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), font_bold),
            ("FONTNAME", (0, 1), (-1, -1), font_regular),
            ("GRID", (0, 0), (-1, -1), 0.4, gray_border),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, gray_bg]),
            ("ALIGN", (1, 1), (1, -1), "RIGHT"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        elements.append(summary_table)
        elements.append(Spacer(1, 10))

        detail_data = [[
            Paragraph("<b>Category</b>", normal_style),
            Paragraph("<b>Amount</b>", normal_style),
            Paragraph("<b>Requested</b>", normal_style),
            Paragraph("<b>Status</b>", normal_style),
            Paragraph("<b>Reimbursed</b>", normal_style),
        ]]

        for r in staff_rows:
            amount = float(r.get("amount") or 0)
            created_raw = r.get("created_at") or ""
            reimbursed_raw = r.get("reimbursed_at") or ""
            try:
                created_fmt = datetime.fromisoformat(str(created_raw)).strftime("%d %b %Y") if created_raw else "-"
            except (ValueError, TypeError):
                created_fmt = str(created_raw)[:10] if created_raw else "-"
            try:
                reimbursed_fmt = datetime.fromisoformat(str(reimbursed_raw)).strftime("%d %b %Y") if reimbursed_raw else "-"
            except (ValueError, TypeError):
                reimbursed_fmt = str(reimbursed_raw)[:10] if reimbursed_raw else "-"

            detail_data.append([
                r.get("category") or "-",
                f"\u20b9{amount:,.0f}",
                created_fmt,
                (r.get("reimbursement_status") or "pending").title(),
                reimbursed_fmt,
            ])

        detail_table = Table(detail_data, colWidths=[2.0 * inch, 1.2 * inch, 1.5 * inch, 1.2 * inch, 1.5 * inch], repeatRows=1)
        detail_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), brand_primary),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), font_bold),
            ("FONTNAME", (0, 1), (-1, -1), font_regular),
            ("GRID", (0, 0), (-1, -1), 0.4, gray_border),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, gray_bg]),
            ("ALIGN", (1, 1), (1, -1), "RIGHT"),
            ("ALIGN", (3, 1), (3, -1), "CENTER"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        elements.append(detail_table)

    elements.append(Spacer(1, 12))
    elements.append(Paragraph(
        f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | {boutique_name}",
        subtitle_style,
    ))

    doc.build(elements)

    response = make_response(buffer.getvalue())
    buffer.close()
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = "attachment; filename=reimbursements.pdf"
    return response


@financial_bp.get("/api/financial/requests/<request_id>")
@login_required
def api_get_request(request_id: str):
    """Get a single financial request."""
    log.info("Get financial request | request_id=%s", request_id)
    doc = financial_service.get_request(request_id)
    if not doc:
        return jsonify({"success": False, "error": "Request not found."}), 404

    role = session.get("role")
    if role not in {"admin", "manager"} and doc.get("user_id") != session["user_id"]:
        return jsonify({"success": False, "error": "Access denied."}), 403

    return jsonify({"success": True, "request": doc})


@financial_bp.patch("/api/financial/requests/<request_id>")
@manager_or_admin_required
def api_review_request(request_id: str):
    """Manager/admin approve or reject a financial request."""
    body = request.get_json(silent=True) or {}
    action = str(body.get("action", "")).strip().lower()
    notes = str(body.get("admin_notes", body.get("notes", "")).strip())
    reviewer_id = session["user_id"]

    if action not in ("approve", "reject"):
        return jsonify({"success": False, "error": "Action must be 'approve' or 'reject'."}), 400

    log.info("Review financial request | request_id=%s | action=%s | reviewer_id=%s", request_id, action, reviewer_id)

    if action == "approve":
        success, error = financial_service.approve_request(request_id, reviewer_id, notes)
    else:
        success, error = financial_service.reject_request(request_id, reviewer_id, notes)

    if not success:
        log.error("Review financial request failed | request_id=%s | error=%s", request_id, error)
        return jsonify({"success": False, "error": error}), 400

    return jsonify({"success": True, "action": action})
