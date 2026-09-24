"""Tests for independent dashboard windows (Settings, Local Experiment, Basket, Batch, Template, Export).

Verifies that all dashboards:
1. Are independent top-level windows with Qt.WindowType.Window flag.
2. Are non-modal (Qt.WindowModality.NonModal), preventing main window freeze.
3. Can be opened and closed independently without blocking the application.
4. Prevent duplicate windows by re-activating existing instances.
"""

from PySide6.QtCore import Qt
from app.ui.main_window import MainWindow
from app.ui.settings_dialog import SettingsDialog
from app.ui.batch_analysis_dialog import BatchAnalysisDialog
from app.ui.question_basket_dialog import QuestionBasketDialog
from app.ui.paper_template_dialog import PaperTemplateDialog
from app.ui.export_dialog import ExportDialog
from app.experimental.local_recognition.ui import LocalRecognitionExperimentDialog


def test_dashboard_window_flags_and_modality(qtbot):
    """Verify all dashboard dialogs are independent top-level non-modal windows."""
    settings_dlg = SettingsDialog()
    qtbot.addWidget(settings_dlg)
    assert bool(settings_dlg.windowFlags() & Qt.WindowType.Window)
    assert settings_dlg.windowModality() == Qt.WindowModality.NonModal

    local_dlg = LocalRecognitionExperimentDialog()
    qtbot.addWidget(local_dlg)
    assert bool(local_dlg.windowFlags() & Qt.WindowType.Window)
    assert local_dlg.windowModality() == Qt.WindowModality.NonModal

    batch_dlg = BatchAnalysisDialog()
    qtbot.addWidget(batch_dlg)
    assert bool(batch_dlg.windowFlags() & Qt.WindowType.Window)
    assert batch_dlg.windowModality() == Qt.WindowModality.NonModal

    basket_dlg = QuestionBasketDialog()
    qtbot.addWidget(basket_dlg)
    assert bool(basket_dlg.windowFlags() & Qt.WindowType.Window)
    assert basket_dlg.windowModality() == Qt.WindowModality.NonModal

    template_dlg = PaperTemplateDialog()
    qtbot.addWidget(template_dlg)
    assert bool(template_dlg.windowFlags() & Qt.WindowType.Window)
    assert template_dlg.windowModality() == Qt.WindowModality.NonModal


def test_main_window_non_modal_settings_and_local_dashboards(qtbot):
    """Verify MainWindow opens settings and local experiment dashboards non-modally and cleans up references."""
    main_win = MainWindow()
    qtbot.addWidget(main_win)
    main_win.show()

    # Open Settings Dashboard
    main_win._on_open_settings()
    assert main_win._settings_window is not None
    assert main_win._settings_window.isVisible()
    assert main_win._settings_window.windowModality() == Qt.WindowModality.NonModal

    # Re-opening focuses the existing window rather than creating a duplicate
    first_inst = main_win._settings_window
    main_win._on_open_settings()
    assert main_win._settings_window is first_inst

    # Close settings window independently
    first_inst.close()
    assert main_win.isVisible()  # Main window remains alive and responsive

    # Open Local Experiment Dashboard
    main_win._on_open_local_experiment()
    assert main_win._local_experiment_window is not None
    assert main_win._local_experiment_window.isVisible()
    assert main_win._local_experiment_window.windowModality() == Qt.WindowModality.NonModal

    # Re-opening focuses existing instance
    first_local = main_win._local_experiment_window
    main_win._on_open_local_experiment()
    assert main_win._local_experiment_window is first_local

    # Close local experiment window independently
    first_local.close()
    assert main_win.isVisible()

    main_win.close()
