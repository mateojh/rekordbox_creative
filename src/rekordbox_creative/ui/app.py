"""Application window and main UI entry point (UI-001).

Creates the main window with menu bar, toolbar, canvas, and side panels.
Orchestrates communication between canvas, panels, and backend engines.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from uuid import UUID

from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QToolBar,
    QWidget,
)

from rekordbox_creative.db.database import Database
from rekordbox_creative.db.models import (
    SuggestionStrategy,
    Track,
)
from rekordbox_creative.db.preferences import PreferencesManager
from rekordbox_creative.graph.graph import TrackGraph
from rekordbox_creative.graph.layout import force_directed_layout, scatter_layout
from rekordbox_creative.graph.pathfinding import optimal_order
from rekordbox_creative.suggestions.engine import SuggestionEngine
from rekordbox_creative.ui.canvas import GraphCanvas
from rekordbox_creative.ui.dialogs.export import pick_export_path
from rekordbox_creative.ui.dialogs.folder_picker import pick_music_folder
from rekordbox_creative.ui.panels.inspector import InspectorPanel
from rekordbox_creative.ui.panels.playlist import PlaylistPanel
from rekordbox_creative.ui.panels.settings import SettingsPanel
from rekordbox_creative.ui.panels.suggestions import SuggestionPanel

logger = logging.getLogger(__name__)

# Dark theme stylesheet
DARK_STYLESHEET = """
QMainWindow { background: #1A1A2E; }
QToolBar { background: #0F0F23; border: none; spacing: 4px; }
QStatusBar { background: #0F0F23; color: #888888; font-size: 11px; }
QMenuBar { background: #0F0F23; color: #E0E0E0; }
QMenuBar::item:selected { background: #16213E; }
QMenu { background: #0F0F23; color: #E0E0E0; border: 1px solid #333; }
QMenu::item:selected { background: #00D4FF; color: #000; }
QTabWidget::pane { background: #0F0F23; border: none; }
QTabBar::tab {
    background: #0F0F23; color: #888888;
    padding: 6px 16px; border: none; border-bottom: 2px solid transparent;
}
QTabBar::tab:selected { color: #00D4FF; border-bottom: 2px solid #00D4FF; }
QTabBar::tab:hover { color: #E0E0E0; }
QSplitter::handle { background: #333; width: 2px; }
QLineEdit {
    background: #1A1A2E; color: #E0E0E0;
    border: 1px solid #333; border-radius: 4px;
    padding: 4px 8px;
}
QLineEdit:focus { border-color: #00D4FF; }
"""


class AnalysisWorker(QThread):
    """Background thread for audio analysis (UI-018, PERF-003)."""

    progress = pyqtSignal(int, int, str)  # current, total, filename
    finished = pyqtSignal(list)  # list of Track
    error = pyqtSignal(str)

    def __init__(self, folder: str, db: Database, parent=None) -> None:
        super().__init__(parent)
        self.folder = folder
        self.db = db
        self._tracks: list[Track] = []
        self._last_progress_time: float = 0.0

    def run(self) -> None:
        try:
            from rekordbox_creative.analysis.cache_manager import AnalysisCacheManager
            from rekordbox_creative.analysis.processor import AudioProcessor
            from rekordbox_creative.analysis.scanner import AudioScanner

            # Recursively find all audio files (mp3, wav, flac, etc.)
            scanner = AudioScanner(self.folder)
            files = scanner.scan()
            logger.info("Found %d audio files in %s", len(files), self.folder)

            if not files:
                self.finished.emit([])
                return

            # Filter out already-analyzed files
            cache = AnalysisCacheManager(self.db)
            to_analyze = cache.filter_uncached(files)

            # Get already cached tracks
            cached_tracks = self.db.get_all_tracks()
            self._tracks = list(cached_tracks)

            if not to_analyze:
                logger.info("All %d files already cached", len(files))
                self.finished.emit(self._tracks)
                return

            logger.info("%d new files to analyze", len(to_analyze))

            # Analyze new files in parallel with throttled progress reporting
            processor = AudioProcessor()

            def progress_cb(filename: str, current: int, total: int) -> None:
                # Throttle progress signals to ~4 per second to avoid UI flooding
                now = time.monotonic()
                if now - self._last_progress_time >= 0.25 or current == total:
                    self._last_progress_time = now
                    self.progress.emit(current, total, filename)

            result = processor.analyze_batch_parallel(
                to_analyze, progress_callback=progress_cb
            )

            # Store new tracks in database
            for track in result.tracks:
                try:
                    self.db.insert_track(track)
                except Exception:
                    # Track may already exist (race condition), try update
                    try:
                        self.db.update_track(track)
                    except Exception:
                        logger.warning("Could not store track: %s", track.filename)
                self._tracks.append(track)

            if result.errors:
                logger.warning(
                    "%d files failed analysis: %s",
                    len(result.errors),
                    [str(e.file_path.name) for e in result.errors[:5]],
                )

            self.finished.emit(self._tracks)
        except Exception as e:
            logger.exception("Analysis failed")
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    """Main application window implementing UI-001."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        super().__init__()
        logger.info("MainWindow.__init__ start")
        self.setWindowTitle("Rekordbox Creative")
        self.setMinimumSize(1024, 768)
        self.resize(1400, 900)
        self.setStyleSheet(DARK_STYLESHEET)

        # Backend state
        self._db_path = str(db_path) if db_path else "rekordbox_creative.db"
        self._db = Database(self._db_path)
        self._prefs = PreferencesManager(self._db)
        self._graph = TrackGraph()
        self._suggestion_engine = SuggestionEngine()
        self._all_tracks: dict[UUID, Track] = {}
        self._sequence: list[Track] = []
        self._selected_track: Track | None = None
        self._worker: AnalysisWorker | None = None

        logger.info("Setting up UI...")
        self._setup_menu_bar()
        self._setup_toolbar()
        self._setup_central()
        self._setup_status_bar()
        self._load_preferences()
        logger.info("UI setup complete. Deferring track load to after show().")

        # Defer heavy DB load to after the window is visible
        QTimer.singleShot(200, self._load_existing_tracks)

    def _setup_menu_bar(self) -> None:
        menu = self.menuBar()

        # File menu
        file_menu = menu.addMenu("&File")
        open_action = QAction("&Open Folder...", self)
        open_action.setShortcut(QKeySequence("Ctrl+O"))
        open_action.triggered.connect(self._on_open_folder)
        file_menu.addAction(open_action)

        save_action = QAction("&Save Graph State", self)
        save_action.setShortcut(QKeySequence("Ctrl+S"))
        save_action.triggered.connect(self._on_save_state)
        file_menu.addAction(save_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut(QKeySequence("Ctrl+Q"))
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # View menu
        view_menu = menu.addMenu("&View")
        fit_action = QAction("&Fit All Nodes", self)
        fit_action.setShortcut(QKeySequence("F"))
        fit_action.triggered.connect(lambda: self._canvas.fit_all_nodes())
        view_menu.addAction(fit_action)

        # Export menu
        export_menu = menu.addMenu("&Export")
        for fmt, label in [("m3u", "M3U Playlist"), ("xml", "Rekordbox XML"),
                           ("csv", "CSV Data")]:
            action = QAction(label, self)
            action.triggered.connect(lambda checked, f=fmt: self._on_export(f))
            export_menu.addAction(action)

    def _setup_toolbar(self) -> None:
        toolbar = QToolBar()
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        # Search bar
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search tracks...")
        self._search.setFixedWidth(250)
        self._search.textChanged.connect(self._on_search)
        toolbar.addWidget(self._search)

        toolbar.addSeparator()

        # Layout mode buttons
        for mode, label in [("force", "Force"), ("scatter", "Scatter")]:
            action = QAction(label, self)
            action.triggered.connect(
                lambda checked, m=mode: self._on_layout_change(m)
            )
            toolbar.addAction(action)

    def _setup_central(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Canvas (center)
        self._canvas = GraphCanvas()
        self._canvas.node_selected.connect(self._on_node_selected)
        self._canvas.node_double_clicked.connect(self._on_node_double_clicked)
        self._canvas.node_context_menu.connect(self._on_context_menu)
        self._canvas.edge_created.connect(self._on_manual_edge_created)
        self._canvas.canvas_clicked.connect(self._on_canvas_clicked)

        # Right panel (tabbed)
        self._right_tabs = QTabWidget()
        self._right_tabs.setMinimumWidth(280)
        self._right_tabs.setMaximumWidth(360)

        self._inspector = InspectorPanel()
        self._suggestions_panel = SuggestionPanel()
        self._playlist_panel = PlaylistPanel()
        self._settings_panel = SettingsPanel()

        self._right_tabs.addTab(self._inspector, "Inspector")
        self._right_tabs.addTab(self._suggestions_panel, "Suggest")
        self._right_tabs.addTab(self._playlist_panel, "Set")
        self._right_tabs.addTab(self._settings_panel, "Settings")

        # Connect panel signals
        self._suggestions_panel.strategy_changed.connect(self._on_strategy_changed)
        self._suggestions_panel.suggestion_clicked.connect(self._on_suggestion_clicked)
        self._playlist_panel.track_removed.connect(self._on_track_removed_from_set)
        self._playlist_panel.optimize_requested.connect(self._on_optimize_order)
        self._playlist_panel.clear_requested.connect(self._on_clear_set)
        self._playlist_panel.export_requested.connect(self._on_export)
        self._settings_panel.weights_changed.connect(self._on_weights_changed)
        self._settings_panel.threshold_changed.connect(self._on_threshold_changed)
        self._settings_panel.folder_requested.connect(self._on_open_folder)

        splitter.addWidget(self._canvas)
        splitter.addWidget(self._right_tabs)
        splitter.setSizes([1000, 300])

        layout.addWidget(splitter)

        # Progress bar (hidden by default)
        self._progress_bar = QProgressBar()
        self._progress_bar.setFixedHeight(20)
        self._progress_bar.setVisible(False)
        self._progress_bar.setStyleSheet("""
            QProgressBar {
                background: #1A1A2E; border: none;
                text-align: center; color: #E0E0E0;
            }
            QProgressBar::chunk { background: #00D4FF; }
        """)

    def _setup_status_bar(self) -> None:
        status = QStatusBar()
        self.setStatusBar(status)
        self._status_label = QLabel("Ready")
        status.addWidget(self._status_label, 1)
        status.addPermanentWidget(self._progress_bar)

    def _load_preferences(self) -> None:
        """Restore saved preferences."""
        threshold = self._prefs.load_edge_threshold()
        self._settings_panel.set_threshold(threshold)

        last_folder = self._prefs.load_last_folder()
        if last_folder:
            self._settings_panel.set_folder(last_folder)

        config = self._prefs.load_suggestion_config()
        self._settings_panel.set_weights({
            "harmonic": config.harmonic_weight,
            "bpm": config.bpm_weight,
            "energy": config.energy_weight,
            "groove": config.groove_weight,
            "frequency": config.frequency_weight,
            "mix_quality": config.mix_quality_weight,
        })

    def _load_existing_tracks(self) -> None:
        """Load tracks from database and populate the graph."""
        logger.info("Loading existing tracks from DB...")
        try:
            tracks = self._db.get_all_tracks()
        except Exception as e:
            logger.exception("Failed to load tracks from DB")
            self._status_label.setText(f"DB load error: {e}")
            return

        if not tracks:
            logger.info("No cached tracks found.")
            return

        logger.info("Found %d cached tracks. Adding to graph...", len(tracks))
        self._status_label.setText(f"Loading {len(tracks)} cached tracks...")

        for track in tracks:
            self._all_tracks[track.id] = track
            self._graph.add_node(track)

        logger.info("Computing edges...")
        try:
            threshold = self._prefs.load_edge_threshold()
            self._graph.compute_edges(threshold=threshold)
        except Exception as e:
            logger.exception("Edge computation failed")

        logger.info("Computing layout...")
        try:
            self._apply_layout("force")
        except Exception as e:
            logger.exception("Layout computation failed")

        logger.info("Deferring render to next event loop cycle...")
        # Defer rendering to allow Qt to finish processing first
        QTimer.singleShot(500, self._deferred_initial_render)
        # DEBUG: skip render to test if crash is from scene items
        # Comment next line to disable render and test stability
        # return

    def _deferred_initial_render(self) -> None:
        """Render graph in small batches to avoid segfault from massive paint."""
        logger.info("Starting deferred render of %d tracks...", len(self._all_tracks))
        try:
            self._render_graph()
            self._status_label.setText(
                f"{len(self._all_tracks)} tracks loaded from cache."
            )
            logger.info("Deferred render complete.")
        except Exception as e:
            logger.exception("Deferred render failed")
            self._status_label.setText(f"Render error: {e}")

    def _render_graph(self) -> None:
        """Populate the canvas with nodes and edges from the graph.

        Optimized for large libraries (PERF-001): batched edge rendering,
        per-node edge caps, skips cluster hulls for large libraries.
        """
        scene = self._canvas.graph_scene
        scene.clear_all()

        n_tracks = len(self._all_tracks)
        logger.info("Rendering %d tracks...", n_tracks)

        # Block scene updates during batch construction
        self._canvas.setUpdatesEnabled(False)

        # Add nodes
        all_nodes = self._graph.get_all_nodes()
        for track in all_nodes:
            pos = getattr(track, "_ui_pos", (0, 0))
            scene.add_track_node(track, pos[0], pos[1])

        logger.info("Nodes added (%d). Adding edges...", len(all_nodes))

        # Collect edges above threshold, then add in batch with per-node cap
        threshold = self._prefs.load_edge_threshold()
        all_edges = self._graph.get_all_edges()
        eligible_edges = [e for e in all_edges if e.compatibility_score >= threshold]

        # Dynamically adjust max edges per node based on library size
        if n_tracks > 500:
            max_per_node = 2
        elif n_tracks > 200:
            max_per_node = 3
        elif n_tracks > 50:
            max_per_node = 5
        else:
            max_per_node = 8

        rendered_count = scene.add_edges_batch(eligible_edges, max_per_node=max_per_node)
        logger.info("Edges added: %d (of %d eligible)", rendered_count, len(eligible_edges))

        # Re-enable updates
        self._canvas.setUpdatesEnabled(True)

        # Only draw cluster hulls for smaller libraries (expensive for 200+)
        n_clusters = 0
        if n_tracks <= 150:
            clusters: dict[int, list[UUID]] = {}
            for track in self._all_tracks.values():
                cid = track.cluster_id
                if cid is not None:
                    clusters.setdefault(cid, []).append(track.id)
            if clusters:
                scene.draw_cluster_hulls(clusters)
            n_clusters = len([c for c in clusters if c >= 0])

        # Update status
        self._status_label.setText(
            f"{n_tracks} tracks | "
            f"{rendered_count} edges | "
            f"{n_clusters} clusters"
        )

        # Defer fit_all_nodes to let the scene fully initialize first
        QTimer.singleShot(100, self._canvas.fit_all_nodes)

    def _apply_layout(self, mode: str) -> None:
        """Compute node positions using specified layout algorithm."""
        nodes = self._graph.get_all_nodes()
        if not nodes:
            return

        if mode == "scatter":
            positions = scatter_layout(nodes)
        else:
            positions = force_directed_layout(self._graph.nx_graph)

        # Apply positions to tracks
        for node_pos in positions:
            track = self._all_tracks.get(node_pos.track_id)
            if track:
                track._ui_pos = (node_pos.x, node_pos.y)

    # ----- Event handlers -----

    def _on_open_folder(self) -> None:
        last = self._prefs.load_last_folder()
        folder = pick_music_folder(self, last)
        if not folder:
            return
        self._prefs.save_last_folder(folder)
        self._settings_panel.set_folder(folder)
        self._start_analysis(folder)

    def _start_analysis(self, folder: str) -> None:
        """Start background analysis of a music folder."""
        if self._worker and self._worker.isRunning():
            QMessageBox.warning(self, "Busy", "Analysis already in progress.")
            return

        self._progress_bar.setVisible(True)
        self._progress_bar.setValue(0)
        self._status_label.setText(f"Analyzing {folder}...")

        self._worker = AnalysisWorker(folder, self._db, self)
        self._worker.progress.connect(self._on_analysis_progress)
        self._worker.finished.connect(self._on_analysis_finished)
        self._worker.error.connect(self._on_analysis_error)
        self._worker.start()

    def _on_analysis_progress(self, current: int, total: int, filename: str) -> None:
        pct = int(current / total * 100) if total > 0 else 0
        self._progress_bar.setValue(pct)
        self._status_label.setText(f"Analyzing ({current}/{total}): {filename}")

    def _on_analysis_finished(self, tracks: list[Track]) -> None:
        self._progress_bar.setVisible(False)
        self._status_label.setText("Building graph...")
        QApplication.processEvents()

        # Update graph with new tracks
        new_tracks = []
        for track in tracks:
            if track.id not in self._all_tracks:
                self._all_tracks[track.id] = track
                self._graph.add_node(track)
                new_tracks.append(track)

        try:
            if new_tracks:
                self._status_label.setText(
                    f"Computing edges for {len(new_tracks)} new tracks..."
                )
                QApplication.processEvents()
                threshold = self._prefs.load_edge_threshold()
                self._graph.compute_edges_for_new_tracks(
                    new_tracks, threshold=threshold
                )

            self._status_label.setText("Computing layout...")
            QApplication.processEvents()
            self._apply_layout("force")
        except Exception as e:
            logger.exception("Edge/layout computation failed")
            self._status_label.setText(f"Graph build error: {e}")

        self._status_label.setText("Rendering graph...")
        QApplication.processEvents()

        # Defer the heavy render slightly to let the UI breathe
        QTimer.singleShot(100, self._finish_render)

    def _finish_render(self) -> None:
        """Deferred render after analysis completes."""
        try:
            self._render_graph()
            self._status_label.setText(
                f"Analysis complete. {len(self._all_tracks)} tracks loaded."
            )
        except Exception as e:
            logger.exception("Render failed")
            self._status_label.setText(
                f"{len(self._all_tracks)} tracks loaded (render error: {e})"
            )

    def _on_analysis_error(self, msg: str) -> None:
        self._progress_bar.setVisible(False)
        self._status_label.setText("Analysis failed")
        QMessageBox.critical(self, "Error", f"Analysis failed: {msg}")

    def _on_node_selected(self, track: Track | None) -> None:
        try:
            self._selected_track = track
            self._inspector.show_track(track)
            self._suggestions_panel.set_current_track(track)

            if track:
                self._right_tabs.setCurrentIndex(0)  # Inspector tab
                # Defer suggestions to avoid blocking UI on click
                QTimer.singleShot(50, lambda: self._safe_update_suggestions(track))
            else:
                self._canvas.graph_scene.clear_highlights()
        except Exception:
            logger.exception("Error in node selection")

    def _safe_update_suggestions(self, track: Track) -> None:
        """Update suggestions with error handling."""
        if self._selected_track is not track:
            return  # Selection changed before timer fired
        try:
            self._update_suggestions(track)
        except Exception:
            logger.exception("Error computing suggestions")

    def _on_node_double_clicked(self, track: Track) -> None:
        """Add track to the current set."""
        if track not in self._sequence:
            self._sequence.append(track)
            self._update_sequence_display()
            self._right_tabs.setCurrentIndex(2)  # Set tab

    def _on_context_menu(self, track: Track, pos) -> None:
        """Right-click context menu on a node (UI-012)."""
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background: #0F0F23; color: #E0E0E0; border: 1px solid #333; }
            QMenu::item:selected { background: #00D4FF; color: #000; }
        """)

        add_action = menu.addAction("Add to Sequence")
        add_action.triggered.connect(lambda: self._on_node_double_clicked(track))

        if track in self._sequence:
            remove_action = menu.addAction("Remove from Sequence")
            remove_action.triggered.connect(
                lambda: self._on_track_removed_from_set(track.id)
            )

        menu.addSeparator()

        find_similar = menu.addAction("Find Similar")
        find_similar.triggered.connect(lambda: self._find_similar(track))

        swap_action = menu.addAction("Swap Track")
        swap_action.setEnabled(track in self._sequence)
        swap_action.triggered.connect(lambda: self._swap_track(track))

        menu.addSeparator()

        show_folder = menu.addAction("Show in Folder")
        show_folder.triggered.connect(
            lambda: self._show_in_folder(track.file_path)
        )

        menu.exec(pos)

    def _find_similar(self, track: Track) -> None:
        """Highlight the top suggestions for a track."""
        self._on_node_selected(track)
        self._right_tabs.setCurrentIndex(1)  # Suggestions tab

    def _swap_track(self, track: Track) -> None:
        """Swap a track in the sequence with the best suggestion (UI-011)."""
        if track not in self._sequence:
            return

        config = self._prefs.load_suggestion_config()
        config.num_suggestions = 1

        results = self._suggestion_engine.suggest(
            current_track=track,
            all_tracks=list(self._all_tracks.values()),
            sequence=[t.id for t in self._sequence],
            config=config,
        )

        if results:
            replacement_id = results[0].track_id
            replacement = self._all_tracks.get(replacement_id)
            if replacement:
                idx = self._sequence.index(track)
                self._sequence[idx] = replacement
                self._update_sequence_display()
                self._on_node_selected(replacement)
                self._status_label.setText(
                    f"Swapped {track.filename} -> {replacement.filename}"
                )

    def _show_in_folder(self, file_path: str) -> None:
        """Open the folder containing a track file."""
        import subprocess
        import sys

        path = Path(file_path).parent
        if sys.platform == "win32":
            subprocess.Popen(["explorer", str(path)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])

    def _on_manual_edge_created(self, source: Track, target: Track) -> None:
        """Handle manual edge creation from port drag (UI-007)."""
        from rekordbox_creative.db.models import Edge
        from rekordbox_creative.graph.scoring import compute_compatibility

        score, scores = compute_compatibility(source, target)
        edge = Edge(
            source_id=source.id,
            target_id=target.id,
            compatibility_score=score,
            scores=scores,
            is_user_created=True,
        )
        self._graph.add_edge(edge)
        self._canvas.graph_scene.add_edge_line(edge)
        self._status_label.setText(
            f"Edge created: {source.filename} -> {target.filename} "
            f"(score: {score:.2f})"
        )

    def _on_canvas_clicked(self) -> None:
        self._inspector.show_track(None)
        self._suggestions_panel.set_current_track(None)

    def _update_suggestions(self, track: Track) -> None:
        """Compute and display suggestions for the selected track."""
        config = self._prefs.load_suggestion_config()

        # Apply panel filters
        filters = self._suggestions_panel.get_filters()
        if "bpm_min" in filters:
            config.bpm_min = filters["bpm_min"]
        if "bpm_max" in filters:
            config.bpm_max = filters["bpm_max"]
        if filters.get("key_lock"):
            config.key_lock = True
        if filters.get("groove_lock"):
            config.groove_lock = True

        strategy_str = self._suggestions_panel.get_strategy()
        config.strategy = SuggestionStrategy(strategy_str)

        try:
            results = self._suggestion_engine.suggest(
                current_track=track,
                all_tracks=list(self._all_tracks.values()),
                sequence=[t.id for t in self._sequence],
                config=config,
            )
        except Exception:
            logger.exception("Suggestion engine failed")
            return

        try:
            self._suggestions_panel.show_suggestions(results, self._all_tracks)
        except Exception:
            logger.exception("Failed to display suggestions")

        # Highlight suggested tracks on canvas
        try:
            suggestion_ids = [r.track_id for r in results]
            self._canvas.graph_scene.highlight_suggestion_nodes(suggestion_ids)
        except Exception:
            logger.exception("Failed to highlight suggestions")

    def _on_strategy_changed(self, strategy: str) -> None:
        if self._selected_track:
            self._update_suggestions(self._selected_track)

    def _on_suggestion_clicked(self, track_id: UUID) -> None:
        """Focus on a suggested track."""
        node = self._canvas.graph_scene.get_node(track_id)
        if node:
            self._canvas.centerOn(node)
            node.setSelected(True)

    def _on_track_removed_from_set(self, track_id: UUID) -> None:
        self._sequence = [t for t in self._sequence if t.id != track_id]
        self._update_sequence_display()

    def _on_optimize_order(self) -> None:
        if len(self._sequence) < 3:
            return
        ordered = optimal_order(self._sequence)
        self._sequence = ordered
        self._update_sequence_display()

    def _on_clear_set(self) -> None:
        self._sequence.clear()
        self._update_sequence_display()

    def _update_sequence_display(self) -> None:
        """Refresh playlist panel and node sequence badges."""
        from rekordbox_creative.graph.scoring import compute_compatibility

        compat_scores: list[float | None] = [None]
        for i in range(1, len(self._sequence)):
            score, _scores = compute_compatibility(
                self._sequence[i - 1], self._sequence[i]
            )
            compat_scores.append(score)

        self._playlist_panel.update_set(self._sequence, compat_scores)

        # Update node badges
        scene = self._canvas.graph_scene
        for node in scene.get_all_nodes():
            idx = next(
                (i for i, t in enumerate(self._sequence) if t.id == node.track_id),
                None,
            )
            node.set_in_sequence(idx is not None, idx)

    def _on_export(self, fmt: str) -> None:
        if not self._sequence:
            QMessageBox.information(self, "Export", "Add tracks to your set first.")
            return

        path = pick_export_path(self, fmt)
        if not path:
            return

        try:
            if fmt == "m3u":
                from rekordbox_creative.export.m3u import export_m3u

                export_m3u(self._sequence, path)
            elif fmt == "xml":
                from rekordbox_creative.export.rekordbox import export_rekordbox_xml

                export_rekordbox_xml(self._sequence, path)
            elif fmt == "csv":
                from rekordbox_creative.export.csv import export_csv

                export_csv(self._sequence, path)
            self._status_label.setText(f"Exported to {path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))

    def _on_save_state(self) -> None:
        from rekordbox_creative.db.models import GraphState, NodePosition, ViewportState

        nodes_pos = []
        for node in self._canvas.graph_scene.get_all_nodes():
            pos = node.scenePos()
            nodes_pos.append(NodePosition(
                track_id=node.track_id, x=pos.x(), y=pos.y()
            ))

        state = GraphState(
            node_positions=nodes_pos,
            viewport=ViewportState(),
            edge_threshold=self._prefs.load_edge_threshold(),
        )

        path, _ = QFileDialog.getSaveFileName(
            self, "Save Graph State", "graph_state.json", "JSON Files (*.json)"
        )
        if path:
            Path(path).write_text(state.model_dump_json(indent=2), encoding="utf-8")
            self._status_label.setText(f"Graph state saved to {path}")

    def _on_search(self, text: str) -> None:
        """Highlight nodes matching search text."""
        if not text:
            self._canvas.graph_scene.clear_highlights()
            return

        text_lower = text.lower()
        matching = []
        for track in self._all_tracks.values():
            name = (track.metadata.title or track.filename).lower()
            artist = (track.metadata.artist or "").lower()
            key = track.dj_metrics.key.lower()
            bpm_str = str(int(track.dj_metrics.bpm))
            if (text_lower in name or text_lower in artist
                    or text_lower == key or text_lower == bpm_str):
                matching.append(track.id)

        self._canvas.graph_scene.highlight_suggestion_nodes(matching)

    def _on_layout_change(self, mode: str) -> None:
        self._apply_layout(mode)
        scene = self._canvas.graph_scene

        # Block updates during batch position changes
        self._canvas.setUpdatesEnabled(False)

        for track_id, track in self._all_tracks.items():
            node = scene.get_node(track_id)
            pos = getattr(track, "_ui_pos", (0, 0))
            if node:
                node.setPos(pos[0], pos[1])
        # Update edges
        for edge_line in scene._edges.values():
            edge_line.update_position()

        self._canvas.setUpdatesEnabled(True)
        self._canvas.fit_all_nodes()

    def _on_weights_changed(self, weights: dict[str, float]) -> None:
        config = self._prefs.load_suggestion_config()
        config.harmonic_weight = weights.get("harmonic", 0.30)
        config.bpm_weight = weights.get("bpm", 0.25)
        config.energy_weight = weights.get("energy", 0.15)
        config.groove_weight = weights.get("groove", 0.10)
        config.frequency_weight = weights.get("frequency", 0.10)
        config.mix_quality_weight = weights.get("mix_quality", 0.10)
        self._prefs.save_suggestion_config(config)

        if self._selected_track:
            self._update_suggestions(self._selected_track)

    def _on_threshold_changed(self, threshold: float) -> None:
        self._prefs.save_edge_threshold(threshold)
        self._render_graph()

    def closeEvent(self, event) -> None:
        self._db.close()
        super().closeEvent(event)

    def keyPressEvent(self, event) -> None:
        """Global keyboard shortcuts."""
        key = event.key()
        mod = event.modifiers()

        if key == Qt.Key.Key_F and not mod:
            self._canvas.fit_all_nodes()
        elif key == Qt.Key.Key_1:
            self._right_tabs.setCurrentIndex(0)
        elif key == Qt.Key.Key_2:
            self._right_tabs.setCurrentIndex(1)
        elif key == Qt.Key.Key_3:
            self._right_tabs.setCurrentIndex(2)
        elif key == Qt.Key.Key_4:
            self._right_tabs.setCurrentIndex(3)
        elif key == Qt.Key.Key_Delete or key == Qt.Key.Key_Backspace:
            if self._selected_track and self._selected_track in self._sequence:
                self._on_track_removed_from_set(self._selected_track.id)
        elif key == Qt.Key.Key_F and mod & Qt.KeyboardModifier.ControlModifier:
            self._search.setFocus()
        else:
            super().keyPressEvent(event)
