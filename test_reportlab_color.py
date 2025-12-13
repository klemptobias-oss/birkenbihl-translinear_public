#!/usr/bin/env python
"""Test if ReportLab Paragraph supports <font color> tags in NESTED tables."""

from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# Create PDF
doc = SimpleDocTemplate("test_reportlab_color.pdf", pagesize=A4)
styles = getSampleStyleSheet()
story = []

# Test 1: Simple paragraph with <font color>
style1 = ParagraphStyle('Test1', parent=styles['Normal'])
p1 = Paragraph('<font color="#FF0000">RED TEXT</font> <font color="#0000FF">BLUE TEXT</font> BLACK TEXT', style1)
story.append(p1)

# Test 2: Paragraph in Table with <font color>
style2 = ParagraphStyle('Test2', parent=styles['Normal'])
p2 = Paragraph('<font color="#00FF00">GREEN</font> TEXT', style2)
table = Table([[p2]], colWidths=[200])
story.append(table)

# Test 3: NESTED Table with <font color> (wie in build_tables_for_alternatives!)
style3 = ParagraphStyle('Test3', parent=styles['Normal'])
# Erstelle nested paragraphs (wie trans in build_tables_for_alternatives)
translation_paragraphs = []
translation_paragraphs.append([Paragraph('<font color="#FF0000">NESTED RED</font>', style3)])
translation_paragraphs.append([Paragraph('<font color="#1E90FF">NESTED BLUE</font>', style3)])
translation_paragraphs.append([Paragraph('<font color="#9370DB">NESTED PURPLE</font>', style3)])

# Nested table
nested_table = Table(translation_paragraphs, colWidths=[None])
# Outer table
outer_table = Table([[nested_table]], colWidths=[200])
story.append(outer_table)

# Build PDF
doc.build(story)
print("✓ Test PDF created: test_reportlab_color.pdf")
