import io
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    HAS_ARABIC_SUPPORT = True
except ImportError:
    HAS_ARABIC_SUPPORT = False

def format_text(text, lang="العربية"):
    if lang == "العربية" and HAS_ARABIC_SUPPORT:
        try:
            reshaped_text = arabic_reshaper.reshape(text)
            return get_display(reshaped_text)
        except Exception:
            return text
    return text

def generate_pdf_report(company_name, results, language="العربية"):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    story = []
    styles = getSampleStyleSheet()

    is_ar = (language == "العربية")

    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontSize=18,
        alignment=1,  # Center
        spaceAfter=20,
        textColor=colors.HexColor('#1F4E78')
    )

    header_title = "تقرير تقييم شركة العمرة 1448هـ" if is_ar else "Umrah Company Evaluation Report 1448H"
    story.append(Paragraph(format_text(header_title, language), title_style))
    story.append(Spacer(1, 10))

    # جدول بيانات الشركة
    company_label = "اسم الشركة:" if is_ar else "Company Name:"
    tier_label = "التصنيف المستحق:" if is_ar else "Earned Tier:"
    score_label = "الدرجة النهائية:" if is_ar else "Final Score:"

    data = [
        [format_text(company_label, language), format_text(company_name, language)],
        [format_text(tier_label, language), format_text(str(results['tier']), language)],
        [format_text(score_label, language), f"{results['final_score']}%"]
    ]

    t = Table(data, colWidths=[150, 300])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F2F4F7')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CCCCCC')),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT' if is_ar else 'LEFT'),
        ('PADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t)
    story.append(Spacer(1, 15))

    # جدول تفاصيل المحاور
    p_header1 = "المحور الرئيسي" if is_ar else "Main Pillar"
    p_header2 = "الدرجة المحققة" if is_ar else "Achieved Score"
    
    p1 = "تنوع الباقات (15)" if is_ar else "Package Diversity (15)"
    p2 = "تجربة المعتمر والجودة (45)" if is_ar else "Pilgrim Exp & Quality (45)"
    p3 = "الالتزام بالبرنامج (40)" if is_ar else "Program Commitment (40)"
    inc = "المحفزات والجوائز" if is_ar else "Incentives & Awards"
    pen = "خصم المخالفات" if is_ar else "Severe Penalties"

    pillars_data = [
        [format_text(p_header1, language), format_text(p_header2, language)],
        [format_text(p1, language), f"{results['score_packages']} / 15"],
        [format_text(p2, language), f"{results['score_exp']} / 45"],
        [format_text(p3, language), f"{results['score_prog']} / 40"],
        [format_text(inc, language), f"+{results['total_incentives']}%"],
        [format_text(pen, language), f"-{results['penalties']}%"],
    ]

    t_pillars = Table(pillars_data, colWidths=[250, 200])
    t_pillars.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (1, 0), colors.HexColor('#1F4E78')),
        ('TEXTCOLOR', (0, 0), (1, 0), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CCCCCC')),
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT' if is_ar else 'LEFT'),
        ('PADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t_pillars)

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()
