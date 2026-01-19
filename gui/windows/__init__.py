"""
Windows Package - マルチウィンドウGUIコンポーネント
"""
from app.gui.windows.dashboard import DashboardView
from app.gui.windows.sitemap_viewer import SitemapViewerFrame, SitemapViewerWindow
from app.gui.windows.comparison_matrix import ComparisonMatrixFrame, ComparisonMatrixWindow
from app.gui.windows.detail_inspector import DetailInspectorFrame, DetailInspectorWindow
from app.gui.windows.report_editor import ReportEditorFrame, ReportEditorWindow

__all__ = [
    "DashboardView",
    "SitemapViewerFrame",
    "SitemapViewerWindow",
    "ComparisonMatrixFrame",
    "ComparisonMatrixWindow",
    "DetailInspectorFrame",
    "DetailInspectorWindow",
    "ReportEditorFrame",
    "ReportEditorWindow",
]
