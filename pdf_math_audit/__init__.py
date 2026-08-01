"""Audit structurel explicite des glyphes d'un PDF."""

from pdf_math_audit.alignment import DoclingAlignment
from pdf_math_audit.analyzer import analyze_pdf
from pdf_math_audit.contract import ANALYZER_VERSION
from pdf_math_audit.semantic_evaluation import evaluate_regions

__all__ = ["DoclingAlignment", "analyze_pdf", "evaluate_regions"]
__version__ = ANALYZER_VERSION
