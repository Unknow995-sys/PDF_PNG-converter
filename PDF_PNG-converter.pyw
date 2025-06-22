import sys
import subprocess
import threading
import os
from pathlib import Path

def check_and_install_dependencies():
    print("--- Comprobando dependencias ---")
    needs_restart = False
    try:
        from PySide6.QtCore import QObject
    except ImportError:
        print("Instalando PySide6..."); needs_restart = True
        subprocess.check_call([sys.executable, "-m", "pip", "install", "PySide6"])
    try:
        import fitz
    except ImportError:
        print("Instalando PyMuPDF..."); needs_restart = True
        subprocess.check_call([sys.executable, "-m", "pip", "install", "PyMuPDF"])
    if not needs_restart: print("Todas las dependencias están instaladas.")
    return needs_restart

def main():
    import fitz
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QPushButton, QLabel, QFileDialog, QSlider, QProgressBar,
        QTextEdit, QCheckBox, QFrame, QGraphicsDropShadowEffect, QMessageBox
    )
    from PySide6.QtCore import Qt, QThread, Signal, Slot, QTimer
    from PySide6.QtGui import QColor, QFont, QPainter, QPen, QBrush, QLinearGradient, QConicalGradient, QPainterPath

    class SymbolButton(QPushButton):
        def __init__(self, symbol='+', parent=None):
            super().__init__("", parent)
            self.symbol = symbol
            self.setFixedSize(35, 40)
            self._hovered = False

        def enterEvent(self, event): self._hovered = True; self.update()
        def leaveEvent(self, event): self._hovered = False; self.update()
        
        def paintEvent(self, event):
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            
            # Dibujar fondo
            bg_color = QColor("#555") if self._hovered else QColor("#404040")
            painter.setBrush(QBrush(bg_color))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(self.rect(), 4, 4)
            
            # Dibujar símbolo
            pen_color = QColor("#FFFFFF")
            painter.setPen(QPen(pen_color))
            font = QFont("Segoe UI Variable", 14, QFont.Bold)
            painter.setFont(font)
            painter.drawText(self.rect(), Qt.AlignCenter, self.symbol)

    class StyledSpinBox(QWidget):
        valueChanged = Signal(int)
        def __init__(self, parent=None):
            super().__init__(parent)
            self._value = 1
            self.setFixedSize(120, 40)
            layout = QHBoxLayout(self); layout.setContentsMargins(0, 0, 0, 0); layout.setSpacing(2)
            self.down_button = SymbolButton("-") # Usando el nuevo botón
            self.value_label = QLabel(str(self._value)); self.value_label.setObjectName("spinLabel"); self.value_label.setAlignment(Qt.AlignCenter)
            self.up_button = SymbolButton("+") # Usando el nuevo botón
            layout.addWidget(self.down_button); layout.addWidget(self.value_label); layout.addWidget(self.up_button)
            self.down_button.clicked.connect(self._decrement); self.up_button.clicked.connect(self._increment)
        def _increment(self): self.setValue(self._value + 1)
        def _decrement(self): self.setValue(self._value - 1)
        def value(self): return self._value
        def setValue(self, value):
            if value < 1: value = 1
            self._value = value; self.value_label.setText(str(self._value)); self.valueChanged.emit(self._value)

    class PageRangeWidget(QFrame):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setObjectName("pageRangeWidget")
            layout = QHBoxLayout(self); layout.setContentsMargins(15, 10, 15, 10); layout.setSpacing(10)
            layout.setAlignment(Qt.AlignCenter)
            self.all_pages_checkbox = QCheckBox("Todas las páginas"); self.all_pages_checkbox.setChecked(True)
            self.all_pages_checkbox.toggled.connect(self.toggle_controls)
            from_label = QLabel("Desde:"); self.from_page_control = StyledSpinBox()
            to_label = QLabel("Hasta:"); self.to_page_control = StyledSpinBox()
            layout.addWidget(self.all_pages_checkbox); layout.addStretch()
            layout.addWidget(from_label); layout.addWidget(self.from_page_control)
            layout.addSpacing(15)
            layout.addWidget(to_label); layout.addWidget(self.to_page_control)
            self.toggle_controls(True)
        def toggle_controls(self, checked):
            self.from_page_control.setDisabled(checked); self.to_page_control.setDisabled(checked)
        def get_page_range(self):
            if self.all_pages_checkbox.isChecked(): return None
            return (self.from_page_control.value(), self.to_page_control.value())

    class AnimatedDropArea(QLabel):
        fileDropped = Signal(str)
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setAcceptDrops(True); self.setAlignment(Qt.AlignCenter)
            self.setObjectName("dropArea"); self.setWordWrap(True); self.setMinimumHeight(180)
            self.setText("Arrastra y suelta un PDF aquí\no haz clic para seleccionar")
            self.hue_bg = 0.0; self.border_offset = 0.0
            self.bg_timer = QTimer(self); self.bg_timer.timeout.connect(self._update_bg)
            self.border_timer = QTimer(self); self.border_timer.timeout.connect(self._update_border)
            self.is_animating = False
        def _update_bg(self): self.hue_bg = (self.hue_bg + 0.001) % 1.0
        def _update_border(self): self.border_offset = (self.border_offset + 2) % 360; self.update()
        def start_animation(self):
            if not self.is_animating: self.bg_timer.start(50); self.border_timer.start(16); self.is_animating = True
        def stop_animation(self):
            if self.is_animating: self.bg_timer.stop(); self.border_timer.stop(); self.is_animating = False; self.update()
        def paintEvent(self, event):
            painter = QPainter(self); painter.setRenderHint(QPainter.Antialiasing)
            rect = self.rect().adjusted(1, 1, -1, -1)
            path = QPainterPath(); path.addRoundedRect(rect, 10, 10)
            if self.is_animating:
                bg_gradient = QLinearGradient(0, 0, self.width(), self.height())
                color1 = QColor.fromHsvF(self.hue_bg, 0.7, 0.15); color2 = QColor.fromHsvF((self.hue_bg + 0.1) % 1.0, 0.7, 0.2)
                bg_gradient.setColorAt(0, color1); bg_gradient.setColorAt(1, color2)
                painter.fillPath(path, QBrush(bg_gradient))
                border_gradient = QConicalGradient(self.rect().center(), self.border_offset)
                border_gradient.setColorAt(0.0, Qt.red); border_gradient.setColorAt(0.16, Qt.yellow); border_gradient.setColorAt(0.33, Qt.green)
                border_gradient.setColorAt(0.5, Qt.cyan); border_gradient.setColorAt(0.66, Qt.blue); border_gradient.setColorAt(0.83, Qt.magenta)
                border_gradient.setColorAt(1.0, Qt.red)
                pen = QPen(QBrush(border_gradient), 3); painter.setPen(pen); painter.drawPath(path)
            super().paintEvent(event)
        def dragEnterEvent(self, event):
            if event.mimeData().hasUrls() and event.mimeData().urls()[0].toLocalFile().lower().endswith('.pdf'):
                event.acceptProposedAction(); self.setProperty("dragging", True); self.style().unpolish(self); self.style().polish(self)
        def dragLeaveEvent(self, event): self.setProperty("dragging", False); self.style().unpolish(self); self.style().polish(self)
        def dropEvent(self, event):
            url = event.mimeData().urls()[0].toLocalFile(); self.fileDropped.emit(url)
            self.setProperty("dragging", False); self.style().unpolish(self); self.style().polish(self)
        def mousePressEvent(self, event):
            path, _ = QFileDialog.getOpenFileName(self, "Seleccionar PDF", "", "PDF Files (*.pdf)")
            if path: self.fileDropped.emit(path)

    STYLESHEET = """
    #mainWindow { background-color: #1c1c1c; }
    #centralWidget { background-color: #252526; border-radius: 10px; }
    QLabel, QCheckBox { color: #cccccc; font-size: 10pt; font-family: 'Segoe UI Variable', 'sans-serif'; }
    #titleLabel { color: white; font-size: 24pt; font-weight: 200; }
    #dropArea { border: none; border-radius: 10px; color: #aaaaaa; font-size: 12pt; }
    #dropArea[dragging="true"] { background-color: rgba(52, 152, 219, 0.2); }
    #dropArea[fileLoaded="true"] { color: #ffffff; font-size: 11pt; background-color: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:0, stop:0 rgba(52, 152, 219, 0.3), stop:1 rgba(142, 68, 173, 0.3)); }
    #pageRangeWidget { background-color: #333333; border-radius: 8px; }
    #spinLabel { background-color: #252526; border: 1px solid #444; border-radius: 4px; color: #f0f0f0; font-weight: bold; }
    QPushButton { background-color: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:0, stop:0 #3498db, stop:1 #8e44ad); color: white; border: none; padding: 12px 20px; border-radius: 8px; font-size: 12pt; font-weight: bold; }
    QPushButton:hover { background-color: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:0, stop:0 #5dade2, stop:1 #a569bd); }
    QPushButton:disabled { background-color: #555; color: #888; }
    QSlider::groove:horizontal { height: 6px; background: #3c3c3c; border-radius: 3px; }
    QSlider::handle:horizontal { background: #8e44ad; border: none; width: 18px; height: 18px; margin: -6px 0; border-radius: 9px; }
    QProgressBar { border: none; border-radius: 5px; background-color: #3c3c3c; text-align: center; color: white; }
    QProgressBar::chunk { border-radius: 5px; background-color: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:0, stop:0 #3498db, stop:1 #8e44ad); }
    QTextEdit { background-color: #1e1e1e; border: 1px solid #3c3c3c; border-radius: 5px; color: #cccccc; font-family: 'Consolas', monospace; }
    """

    class PDFConverterApp(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setObjectName("mainWindow"); self.setWindowTitle("Conversor de PDF a PNG")
            self.setGeometry(100, 100, 580, 700)
            self.central_widget = QWidget(self); self.central_widget.setObjectName("centralWidget")
            self.setCentralWidget(self.central_widget)
            shadow = QGraphicsDropShadowEffect(); shadow.setBlurRadius(35); shadow.setColor(QColor(0,0,0,90)); shadow.setOffset(0,4)
            self.central_widget.setGraphicsEffect(shadow)
            self.main_layout = QVBoxLayout(self.central_widget)
            self.main_layout.setContentsMargins(35, 35, 35, 35); self.main_layout.setSpacing(25)
            title = QLabel("Convierte tu PDF a PNG"); title.setObjectName("titleLabel"); title.setAlignment(Qt.AlignCenter)
            self.main_layout.addWidget(title)
            self.drop_area = AnimatedDropArea(); self.drop_area.fileDropped.connect(self.on_file_selected)
            self.main_layout.addWidget(self.drop_area)
            controls_frame = QFrame(); controls_layout = QVBoxLayout(controls_frame)
            controls_layout.setContentsMargins(0,0,0,0); controls_layout.setSpacing(15)
            dpi_layout = QHBoxLayout(); dpi_label = QLabel("Calidad de Imagen:"); self.dpi_slider = QSlider(Qt.Horizontal)
            self.dpi_slider.setRange(72, 600); self.dpi_slider.setValue(300)
            self.dpi_value_label = QLabel(f"{self.dpi_slider.value()} DPI"); self.dpi_value_label.setMinimumWidth(60)
            self.dpi_slider.valueChanged.connect(lambda v: self.dpi_value_label.setText(f"{v} DPI"))
            dpi_layout.addWidget(dpi_label); dpi_layout.addWidget(self.dpi_slider); dpi_layout.addWidget(self.dpi_value_label)
            controls_layout.addLayout(dpi_layout)
            self.page_range_widget = PageRangeWidget()
            controls_layout.addWidget(self.page_range_widget)
            self.main_layout.addWidget(controls_frame)
            self.convert_btn = QPushButton("Convertir a PNG"); self.convert_btn.setFixedHeight(50)
            self.convert_btn.clicked.connect(self.start_conversion); self.main_layout.addWidget(self.convert_btn)
            self.progress_bar = QProgressBar(); self.progress_bar.setTextVisible(False); self.progress_bar.setFixedHeight(8)
            self.main_layout.addWidget(self.progress_bar)
            self.log_console = QTextEdit(); self.log_console.setReadOnly(True); self.log_console.setFixedHeight(100)
            self.log_console.setPlaceholderText("El progreso de la conversión aparecerá aquí..."); self.main_layout.addWidget(self.log_console)
            self.pdf_path = None; self.worker = None; self.reset_ui()
            self.drop_area.start_animation()
        def on_file_selected(self, path):
            self.drop_area.stop_animation()
            self.pdf_path = path; filename = os.path.basename(path)
            self.drop_area.setText(f"Archivo Cargado:\n<b>{filename}</b>"); self.drop_area.setProperty("fileLoaded", True)
            self.drop_area.style().unpolish(self.drop_area); self.drop_area.style().polish(self.drop_area)
            self.convert_btn.setEnabled(True); self.log_to_console(f"PDF seleccionado: {path}", "info")
        def start_conversion(self):
            if not self.pdf_path: return
            output_folder = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta para guardar las imágenes")
            if not output_folder: self.log_to_console("Conversión cancelada.", "info"); return
            self.set_controls_enabled(False); self.log_to_console("Iniciando conversión...", "info")
            page_range = self.page_range_widget.get_page_range()
            self.worker = ConversionWorker(self.pdf_path, output_folder, self.dpi_slider.value(), page_range)
            self.worker.progress.connect(self.update_progress)
            self.worker.page_done.connect(lambda msg: self.log_to_console(msg, "info"))
            self.worker.finished.connect(self.on_conversion_finished); self.worker.error.connect(self.on_conversion_error)
            self.worker.start()
        def on_conversion_finished(self, message):
            self.log_to_console(message, "success"); QMessageBox.information(self, "Conversión Completa", "¡Todas las páginas se han convertido con éxito!")
            self.reset_ui()
        def on_conversion_error(self, message):
            self.log_to_console(message, "error"); QMessageBox.critical(self, "Error de Conversión", f"Ocurrió un error:\n{message}")
            self.reset_ui()
        def reset_ui(self):
            self.set_controls_enabled(True); self.pdf_path = None
            self.drop_area.setText("Arrastra y suelta un PDF aquí\no haz clic para seleccionar")
            self.drop_area.setProperty("fileLoaded", False)
            self.drop_area.style().unpolish(self.drop_area); self.drop_area.style().polish(self.drop_area)
            self.drop_area.start_animation()
            self.convert_btn.setEnabled(False); self.progress_bar.setValue(0)
        def set_controls_enabled(self, enabled):
            self.drop_area.setEnabled(enabled); self.dpi_slider.setEnabled(enabled)
            self.page_range_widget.setEnabled(enabled)
            self.convert_btn.setEnabled(enabled and self.pdf_path is not None)
            self.convert_btn.setText("Convertir a PNG" if enabled else "Convirtiendo...")
        def update_progress(self, value): self.progress_bar.setValue(value)
        def log_to_console(self, message, level="info"):
            color_map = {"info": "#aaaaaa", "success": "#2ecc71", "error": "#e74c3c"}
            self.log_console.append(f"<span style='color:{color_map.get(level)};'>{message}</span>")
        def closeEvent(self, event):
            if self.worker and self.worker.isRunning(): self.worker.stop(); self.worker.wait()
            event.accept()

    class ConversionWorker(QThread):
        progress = Signal(int); page_done = Signal(str); finished = Signal(str); error = Signal(str)
        def __init__(self, pdf_path, output_folder, dpi, page_range=None):
            super().__init__(); self.pdf_path, self.output_folder, self.dpi, self.page_range = pdf_path, output_folder, dpi, page_range; self.is_running = True
        def run(self):
            try:
                doc = fitz.open(self.pdf_path); total_pages = len(doc)
                first_page = self.page_range[0] - 1 if self.page_range else 0
                last_page = self.page_range[1] if self.page_range else total_pages
                if last_page > total_pages: last_page = total_pages
                pages_to_convert_indices = range(first_page, last_page); num_pages_to_convert = len(pages_to_convert_indices)
                if num_pages_to_convert <= 0: self.error.emit("El rango de páginas no es válido."); return
                base_filename = Path(self.pdf_path).stem
                for i, page_index in enumerate(pages_to_convert_indices):
                    if not self.is_running: doc.close(); self.error.emit("Conversión cancelada."); return
                    page = doc.load_page(page_index); pix = page.get_pixmap(dpi=self.dpi)
                    output_path = os.path.join(self.output_folder, f"{base_filename}_page_{page_index + 1}.png"); pix.save(output_path)
                    self.page_done.emit(f"Página {page_index + 1} guardada.")
                    self.progress.emit(int(((i + 1) / num_pages_to_convert) * 100))
                doc.close(); self.finished.emit(f"¡Éxito! Se convirtieron {num_pages_to_convert} páginas.")
            except Exception as e: self.error.emit(f"Ocurrió un error: {str(e)}")
        def stop(self): self.is_running = False

    app = QApplication(sys.argv); app.setStyle("Fusion"); app.setStyleSheet(STYLESHEET)
    window = PDFConverterApp(); window.show(); sys.exit(app.exec())

if __name__ == "__main__":
    if check_and_install_dependencies():
        print("\nDependencias instaladas. Reiniciando la aplicación...")
        os.execv(sys.executable, ['python'] + sys.argv)
    main()