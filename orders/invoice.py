from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
    Image,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from io import BytesIO
from django.http import HttpResponse
from decimal import Decimal
from datetime import date, timedelta


def generate_invoice_pdf(order):
    """
    Generate PDF invoice for an order
    Returns: HttpResponse with PDF
    """
    # Create BytesIO buffer
    buffer = BytesIO()

    # Create PDF
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=30,
        leftMargin=30,
        topMargin=30,
        bottomMargin=30,
    )

    # Container for PDF elements
    elements = []

    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Heading1"],
        fontSize=24,
        textColor=colors.HexColor("#1e40af"),
        spaceAfter=12,
        alignment=TA_CENTER,
    )

    heading_style = ParagraphStyle(
        "CustomHeading",
        parent=styles["Heading2"],
        fontSize=14,
        textColor=colors.HexColor("#1e40af"),
        spaceAfter=6,
        spaceBefore=12,
    )

    normal_style = styles["Normal"]

    # Title
    elements.append(Paragraph("TIMESTAMP INVOICE", title_style))
    elements.append(Spacer(1, 0.2 * inch))

    # Company Info
    company_info = f"""
    <b>Timestamp Watches</b><br/>
    123 Watch Street, Kannur<br/>
    Kerala, India - 670001<br/>
    Email: info@timestamp.com<br/>
    Phone: +91 1234567890<br/>
    GST: 32XXXXX1234X1ZX
    """
    elements.append(Paragraph(company_info, normal_style))
    elements.append(Spacer(1, 0.3 * inch))

    estimated_delivery = order.created_at.date() + timedelta(days=7)

    # Invoice Details and Customer Info Table
    # Order Status and Payment Status
    info_data = [
        ["Invoice Details", "Customer Details"],
        [
            (
                f"Invoice No: {order.order_id}\n"
                f"Date: {order.created_at.strftime('%d %B %Y')}\n"
                f"Order Status: {order.get_status_display()}\n"
                f"Payment Status: {order.payment_status.capitalize()}\n"
                f"Payment Method: {order.get_payment_method_display()}\n"
                f"Estimated Delivery: {estimated_delivery.strftime('%d %B %Y')}"
            ),
            (
                f"{order.full_name}\n"
                f"{order.street_address}\n"
                f"{order.city}, {order.state}\n"
                f"{order.postal_code}\n"
                f"Phone: {order.mobile}"
            ),
        ],
    ]


    info_table = Table(info_data, colWidths=[3 * inch, 3 * inch])
    info_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e0e7ff")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#1e40af")),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 12),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                ("TOPPADDING", (0, 0), (-1, 0), 8),
                ("VALIGN", (0, 1), (-1, -1), "TOP"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 1), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 1), (-1, -1), 12),
                ("BOTTOMPADDING", (0, 1), (-1, -1), 12),
            ]
        )
    )
    elements.append(info_table)
    elements.append(Spacer(1, 0.3 * inch))

    # Order Items Table
    elements.append(Paragraph("Order Items", heading_style))

    # Table header
    items_data = [["#", "Product", "Colour", "Price", "Qty", "Total"]]

    active_items = order.items.exclude(status__in=["cancelled", "returned"])

    # Add items
    for idx, item in enumerate(active_items, 1):
        items_data.append(
            [
                str(idx),
                item.product_name,
                item.variant_colour,
                f"₹{item.price}",
                str(item.quantity),
                f"₹{item.get_total()}",
            ]
        )

    items_table = Table(
        items_data,
        colWidths=[0.5 * inch, 2.5 * inch, 1 * inch, 1 * inch, 0.7 * inch, 1 * inch],
    )
    items_table.setStyle(
        TableStyle(
            [
                # Header
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e40af")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 10),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                ("TOPPADDING", (0, 0), (-1, 0), 8),
                # Body
                ("ALIGN", (0, 1), (0, -1), "CENTER"),
                ("ALIGN", (3, 1), (-1, -1), "RIGHT"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 1), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 1), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 1), (-1, -1), 6),
                # Alternating row colors
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [colors.white, colors.HexColor("#f9fafb")],
                ),
            ]
        )
    )
    elements.append(items_table)
    elements.append(Spacer(1, 0.3 * inch))

    # Totals Table
    totals_data = [
        [
            "Subtotal(Before Discount):",
            f"₹{order.subtotal + order.discount_amount + order.coupon_discount}",
        ],
        [
            "Offer Discount:",
            f"- ₹{order.discount_amount}",
        ],  # discount from product offers
    ]

    # Show coupon discount only if used
    if order.coupon_discount > 0:
        totals_data.append(["Coupon Discount:", f"- ₹{order.coupon_discount}"])

    totals_data += [
        ["Shipping:", f"₹{order.shipping_charge}"],
        ["", ""],
        ["Grand Total:", f"₹{order.total_amount}"],
    ]

    totals_table = Table(totals_data, colWidths=[4.5 * inch, 1.5 * inch])
    totals_table.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (0, -1), "RIGHT"),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("FONTNAME", (0, 0), (-1, -2), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -2), 10),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, -1), (-1, -1), 12),
                ("TEXTCOLOR", (0, -1), (-1, -1), colors.HexColor("#1e40af")),
                ("LINEABOVE", (0, -1), (-1, -1), 2, colors.HexColor("#1e40af")),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    elements.append(totals_table)
    elements.append(Spacer(1, 0.5 * inch))

    # Footer
    footer_style = ParagraphStyle(
        "Footer",
        parent=normal_style,
        fontSize=8,
        textColor=colors.grey,
        alignment=TA_CENTER,
    )

    footer_text = """
    <b>Terms & Conditions:</b><br/>
    1. Items once sold cannot be exchanged or refunded except for manufacturing defects.<br/>
    2. Returns accepted within 7 days of delivery with valid reason.<br/>
    3. Product warranty as per manufacturer's terms.<br/>
    <br/>
    Thank you for shopping with Timestamp!<br/>
    For queries: support@timestamp.com | +91 1234567890
    """
    elements.append(Paragraph(footer_text, footer_style))

    # Build PDF
    doc.build(elements)

    # Get PDF value
    pdf = buffer.getvalue()
    buffer.close()

    # Create HTTP response
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="invoice_{order.order_id}.pdf"'
    )
    response.write(pdf)

    return response
