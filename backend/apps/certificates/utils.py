
"""
Certificate PDF Generation Utilities

This module provides functions for generating professional certificate PDFs
for course completion using ReportLab library.

Features:
    - Dark theme with purple accent colors
    - Professional layout with shadows and borders
    - Portuguese date formatting
    - Automatic directory creation
    - Custom signature blocks
    - Validation code generation

Main Functions:
    - generate_certificate_pdf(certificate): Creates PDF file for certificate
    - generate_certificate_code(): Generates unique validation code (WSS-YYYY-XXXXXX)

Usage Example:
    >>> from apps.certificates.models import Certificate
    >>> cert = Certificate.objects.get(id=1)
    >>> pdf_path = generate_certificate_pdf(cert)
    >>> print(pdf_path)  # 'certificates/2026/03/WSS-2026-ABC123.pdf'

Design:
    - Page size: A4 Landscape (842 x 595 points)
    - Color scheme: Dark background (#0F0F14) with purple accents (#2F1064)
    - Layout: Card-based design with glow effects
    - Fonts: Helvetica family (Regular, Bold, BoldOblique, Oblique)

Dependencies:
    - ReportLab: PDF generation library
    - Django: Settings and file handling
    - Python datetime: Date formatting
"""

import os
import random
import string

from datetime import datetime
from django.conf import settings
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, white, Color
from reportlab.pdfgen import canvas
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import Paragraph
from reportlab.lib.styles import ParagraphStyle

# Palet of colors
COLOR_BG          = HexColor("#0F0F14")
COLOR_SURFACE     = HexColor("#16161F")
COLOR_BORDER      = HexColor("#1E1E2E")
COLOR_ACCENT      = HexColor("#2F1064")
COLOR_ACCENT_SOFT = HexColor("#3A2E5E")
COLOR_TEXT        = HexColor("#E2E8F0")
COLOR_MUTED       = HexColor("#64748B")
COLOR_LINE        = HexColor("#2D2D3F")

# Helpers 
def _pt_date(date_obj):
    """
    Format date in Portuguese: DD de mês de YYYY
    
    Args:
        date_obj: datetime object to format
        
    Returns:
        str: Formatted date string
    """
    months = [
        "", "janeiro", "fevereiro", "março", "abril", "maio", "junho",
        "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",  
    ]

    return f"{date_obj.day:02d} de {months[date_obj.month]} de {date_obj.year}"

def _draw_background(canvas_obj, w, h):
    """
    Draw dark background with purple ambient glow effect
    
    Args:
        canvas_obj: ReportLab Canvas object
        w: Page width in points
        h: Page height in points
    """
    canvas_obj.setFillColor(COLOR_BG)
    canvas_obj.rect(0, 0, w, h, fill=1, stroke=0)

    # Purple ambient glow (simulated with semi-transparent circles)
    glow_steps = 18
    for i in range(glow_steps):
        t = (glow_steps - i) / glow_steps
        alpha = t * 0.04
        r = (80 + i * 7) * mm
        glow_color = Color(0.48, 0.23, 0.93, alpha=alpha)
        canvas_obj.setFillColor(glow_color)
        canvas_obj.circle(0, h, r, fill=1, stroke=0)

def _draw_card(canvas_obj, w, h):
    """
    Draw certificate card with shadow, border and top accent line
    
    Args:
        canvas_obj: ReportLab Canvas object
        w: Page width in points
        h: Page height in points
    """
    pad_x = 18 * mm
    pad_y  = 14 * mm
    card_w = w - 2 * pad_x
    card_h = h - 2 * pad_y
    radius = 3 * mm

    # Subtle shadow
    canvas_obj.setFillColor(HexColor("#08080C"))
    canvas_obj.roundRect(pad_x + 1 * mm, pad_y - 1 * mm, card_w, card_h, radius, fill=1, stroke=0)

    # Card
    canvas_obj.setFillColor(COLOR_SURFACE)
    canvas_obj.roundRect(pad_x, pad_y, card_w, card_h, radius, fill=1, stroke=0)

    # Border
    canvas_obj.setStrokeColor(COLOR_BORDER)
    canvas_obj.setLineWidth(0.8)
    canvas_obj.roundRect(pad_x, pad_y, card_w, card_h, radius, fill=0, stroke=1)

    # Top line
    canvas_obj.setStrokeColor(COLOR_ACCENT)
    canvas_obj.setLineWidth(2)
    canvas_obj.line(pad_x + radius, pad_y + card_h, pad_x + card_w - radius, pad_y + card_h)

def _draw_accent_bar(canvas_obj, h):
    """
    Draw vertical accent bar on the left side
    
    Args:
        canvas_obj: ReportLab Canvas object
        h: Page height in points
    """
    bar_x  = 22 * mm
    bar_y  = 22 * mm
    bar_h  = h - 44 * mm
    bar_w  = 2.5 * mm
    radius = 1.5 * mm

    canvas_obj.setFillColor(COLOR_ACCENT)
    canvas_obj.roundRect(bar_x, bar_y, bar_w, bar_h, radius, fill=1, stroke=0)

def _thin_divider(canvas_obj, cx, y, half_w):
    """
    Draw horizontal divider line with accent circle in center
    
    Args:
        canvas_obj: ReportLab Canvas object
        cx: Center X position
        y: Y position for the line
        half_w: Half width of the line from center
    """
    canvas_obj.setStrokeColor(COLOR_LINE)
    canvas_obj.setLineWidth(0.6)
    canvas_obj.line(cx - half_w, y, cx + half_w, y)
    canvas_obj.setFillColor(COLOR_ACCENT)
    canvas_obj.circle(cx, y, 1.2 * mm, fill=1, stroke=0)

def _draw_signature_block(canvas_obj, sig_x, sig_y, sig_w, name, role):
    """
    Draw signature block with line, name and role
    
    Args:
        canvas_obj: ReportLab Canvas object
        sig_x: Signature block X position
        sig_y: Signature block Y position
        sig_w: Signature block width
        name: Name to display
        role: Role/title to display below name
    """
    center = sig_x + sig_w / 2
    canvas_obj.setStrokeColor(COLOR_LINE)
    canvas_obj.setLineWidth(0.6)
    canvas_obj.line(sig_x, sig_y, sig_x + sig_w, sig_y)

    canvas_obj.setStrokeColor(COLOR_ACCENT)
    canvas_obj.setLineWidth(1.5)
    canvas_obj.line(sig_x, sig_y, sig_x + 6 * mm, sig_y)

    canvas_obj.setFont("Helvetica-Bold", 9)
    canvas_obj.setFillColor(COLOR_TEXT)
    canvas_obj.drawCentredString(center, sig_y - 5.5 * mm, name)

    canvas_obj.setFont("Helvetica", 7.5)
    canvas_obj.setFillColor(COLOR_MUTED)
    canvas_obj.drawCentredString(center, sig_y - 10 * mm, role)

# Main method
def generate_certificate_pdf(certificate):
    """
    Generate certificate PDF with ReportLab
    
    Creates a professional certificate with dark theme, purple accents,
    student information, course details, and validation code.
    
    Args:
        certificate: Certificate model instance with enrollment relationship
        
    Returns:
        str: Relative path to generated PDF file (relative to MEDIA_ROOT)
        
    Example:
        >>> cert = Certificate.objects.get(id=1)
        >>> pdf_path = generate_certificate_pdf(cert)
        >>> print(pdf_path)  # 'certificates/2026/03/WSS-2026-ABC123.pdf'
    """
    # Extract data from certificate model
    student_name = certificate.student_name
    course_title = certificate.course_title
    instructor_name = certificate.instructor_name
    completion_date = certificate.completion_date
    certificate_code = certificate.certificate_code
    
    # Validate completion_date before using it
    if completion_date is None:
        completion_date = datetime.today()
    
    # Create directory structure if it doesn't exist
    pdf_dir = os.path.join(settings.MEDIA_ROOT, completion_date.strftime('certificates/%Y/%m/'))
    os.makedirs(pdf_dir, exist_ok=True)
    pdf_path = os.path.join(pdf_dir, f'{certificate_code}.pdf')
    
    page_w, page_h = landscape(A4)
    cx = page_w / 2

    canvas_obj = canvas.Canvas(pdf_path, pagesize=landscape(A4))
    canvas_obj.setTitle(f"Certificado — {course_title}")
    canvas_obj.setAuthor(instructor_name)
    canvas_obj.setSubject("Certificado de Conclusão de Curso")

    # base layers
    _draw_background(canvas_obj, page_w, page_h)
    _draw_card(canvas_obj, page_w, page_h)
    _draw_accent_bar(canvas_obj, page_h)

    # Institution
    inst_y = page_h - 24 * mm
    canvas_obj.setFont("Helvetica", 8)
    canvas_obj.setFillColor(COLOR_MUTED)
    canvas_obj.drawCentredString(cx, inst_y, instructor_name.upper())

    # decorative point
    canvas_obj.setFillColor(COLOR_ACCENT)
    canvas_obj.circle(cx, inst_y - 5 * mm, 1 * mm, fill=1, stroke=0)

    # spaced label
    label_y = inst_y - 13 * mm
    canvas_obj.setFont("Helvetica", 9)
    canvas_obj.setFillColor(COLOR_ACCENT_SOFT)
    canvas_obj.drawCentredString(cx, label_y, "C E R T I F I C A D O   D E   C O N C L U S Ã O")

    _thin_divider(canvas_obj, cx, label_y - 6 * mm, 55 * mm)

    # We certify that
    cert_y = label_y - 17 * mm
    canvas_obj.setFont("Helvetica", 11)
    canvas_obj.setFillColor(COLOR_MUTED)
    canvas_obj.drawCentredString(cx, cert_y, "Certificamos que")

    # Student name
    name_y = cert_y - 14 * mm
    canvas_obj.setFont("Helvetica-BoldOblique", 26)
    canvas_obj.setFillColor(COLOR_TEXT)
    canvas_obj.drawCentredString(cx, name_y, student_name)

    name_w = canvas_obj.stringWidth(student_name, "Helvetica-BoldOblique", 26)
    underline_pad = 8 * mm
    canvas_obj.setStrokeColor(COLOR_ACCENT)
    canvas_obj.setLineWidth(1)
    canvas_obj.line(cx - name_w / 2 - underline_pad, name_y - 2.5 * mm,
                    cx + name_w / 2 + underline_pad, name_y - 2.5 * mm)

    # Body
    body_y = name_y - 16 * mm
    body_style = ParagraphStyle(
        "body",
        fontName="Helvetica",
        fontSize=11,
        leading=17,
        textColor=COLOR_MUTED,
        alignment=TA_CENTER,
    )
    body_text = (
         f'concluiu o curso de '
         f'<font color="#A78BFA"><b>{course_title}</b></font>'
         f', cumprindo todos os requisitos exigidos.' 
    )
    para = Paragraph(body_text, body_style)
    para_w = 170 * mm
    para_h = para.wrap(para_w, 40 * mm)[1]
    para.drawOn(canvas_obj, cx - para_w / 2, body_y - para_h)

    # Date
    date_y = body_y - para_h - 10 * mm
    canvas_obj.setFont("Helvetica-Oblique", 9)
    canvas_obj.setFillColor(COLOR_MUTED)
    canvas_obj.drawCentredString(cx, date_y, _pt_date(completion_date))

    # Divide before the signatures
    sig_div_y = date_y - 10 * mm
    _thin_divider(canvas_obj, cx, sig_div_y, 90 * mm)

    # Signatures
    sig_y  = sig_div_y - 14 * mm
    sig_w  = 65 * mm
    gap    = 28 * mm
    left_x = cx - sig_w - gap / 2
    right_x = cx + gap / 2

    _draw_signature_block(canvas_obj, left_x,  sig_y, sig_w,
                          instructor_name, "Instrutor Responsável")
    
    # baseboard
    canvas_obj.setFont("Helvetica", 7)
    canvas_obj.setFillColor(COLOR_MUTED)
    canvas_obj.drawCentredString(
        cx, 10 * mm,
        f"Nº {certificate_code}   ·   {_pt_date(completion_date)}   ·   {instructor_name}",
    )

    canvas_obj.save()

    relative_path = os.path.join(
        completion_date.strftime('certificates/%Y/%m/'),
        f'{certificate_code}.pdf'
    )
    return relative_path

def generate_certificate_code():
    """
    Generate unique certificate validation code
    
    Format: WSS-YYYY-XXXXXX
    - WSS: Platform identifier
    - YYYY: Current year
    - XXXXXX: 6 random alphanumeric characters (uppercase)
    
    Returns:
        str: Unique certificate code (15 characters)
        
    Example:
        >>> code = generate_certificate_code()
        >>> print(code)  # 'WSS-2026-A1B2C3'
    """
    
    from apps.certificates.models import Certificate

    PREFIX = "WSS"
    CHARS  = string.ascii_uppercase + string.digits  # A-Z + 0-9
    year   = datetime.now().year

    while True:
        random_part = "".join(random.choices(CHARS, k=6))
        code = f"{PREFIX}-{year}-{random_part}"

        if not Certificate.objects.filter(certificate_code=code).exists():
            return code