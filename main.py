# main.py
import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QStackedWidget, QPushButton, QVBoxLayout, 
                             QHBoxLayout, QLabel, QLineEdit, QFileDialog, QMessageBox, QDialog, QDialogButtonBox, QDockWidget)
from PyQt5.QtCore import Qt, QTimer
from gps_receiver import GPSReceiver
from field_model import FieldModel
from plot_widget import FieldPlotWidget, LevelingPlotWidget, ElevationDiffColorBar
from leveling import compute_target_grid, compute_best_plane

class StartupDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Avvio rilevamento")
        layout = QVBoxLayout(self)
        label = QLabel("Vuoi continuare un campo già esistente o iniziarne uno nuovo?")
        layout.addWidget(label)
        buttons = QDialogButtonBox(self)
        self.new_field_btn = buttons.addButton("Nuovo Campo", QDialogButtonBox.AcceptRole)
        self.continue_field_btn = buttons.addButton("Continua Campo", QDialogButtonBox.ActionRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.choice = None
        self.new_field_btn.clicked.connect(self.choose_new)
        self.continue_field_btn.clicked.connect(self.choose_continue)
    
    def choose_new(self):
        self.choice = "new"
        self.accept()
    
    def choose_continue(self):
        self.choice = "continue"
        self.accept()

class SurveyWidget(QWidget):
    def __init__(self, field_model, parent=None):
        super().__init__(parent)
        self.field_model = field_model
        layout = QVBoxLayout(self)
        self.plot_widget = FieldPlotWidget()  # Mostra i punti come scatter
        layout.addWidget(self.plot_widget)
        self.end_survey_btn = QPushButton("Termina Rilevamento")
        layout.addWidget(self.end_survey_btn)
    
    def update_plot(self):
        self.plot_widget.update_points(self.field_model.points)
    
    def update_tractor(self, x, y):
        self.plot_widget.update_tractor(x, y)

class LevelingWidget(QWidget):
    def __init__(self, field_model, parent=None):
        super().__init__(parent)
        self.field_model = field_model
        main_layout = QVBoxLayout(self)
        
        # Input per slope e bottoni
        input_layout = QHBoxLayout()
        self.slope_x_input = QLineEdit()
        self.slope_x_input.setPlaceholderText("Slope X (cm/100m)")
        self.slope_y_input = QLineEdit()
        self.slope_y_input.setPlaceholderText("Slope Y (cm/100m)")
        input_layout.addWidget(QLabel("Slope X desiderato:"))
        input_layout.addWidget(self.slope_x_input)
        input_layout.addWidget(QLabel("Slope Y desiderato:"))
        input_layout.addWidget(self.slope_y_input)
        self.compute_btn = QPushButton("Applica Livellamento")
        self.auto_compute_btn = QPushButton("Calcolo Automatico Piana")
        input_layout.addWidget(self.compute_btn)
        input_layout.addWidget(self.auto_compute_btn)
        main_layout.addLayout(input_layout)
        
        # Layout orizzontale per plot e color bar
        plot_layout = QHBoxLayout()
        self.leveling_plot = LevelingPlotWidget()  # Mostra la griglia interpolata
        plot_layout.addWidget(self.leveling_plot, stretch=4)
        self.color_bar = ElevationDiffColorBar()
        plot_layout.addWidget(self.color_bar, stretch=1)
        main_layout.addLayout(plot_layout)
        
        # Info label per mostrare l'elevazione corrente, target e differenza
        self.elev_info_label = QLabel("Current Elev: --, Target: --, Diff: --")
        main_layout.addWidget(self.elev_info_label)
        
        self.auto_result_label = QLabel("")
        main_layout.addWidget(self.auto_result_label)
        
        # Connessione bottoni
        self.compute_btn.clicked.connect(self.apply_levelling)
        self.auto_compute_btn.clicked.connect(self.auto_compute)
        
        # Timer per aggiornare la griglia (ogni 2 secondi)
        self.grid_timer = QTimer(self)
        self.grid_timer.timeout.connect(self.update_interpolated_grid)
        self.grid_timer.start(2000)
        self.interpolation_worker = None  # Worker per interpolazione
    
    def apply_levelling(self):
        self.update_interpolated_grid()
    
    def auto_compute(self):
        if not self.field_model.points:
            QMessageBox.warning(self, "Errore", "Nessun dato di rilevamento disponibile.")
            return
        a, b, c = compute_best_plane(self.field_model.points)
        slope_x = b * 10000.0
        slope_y = c * 10000.0
        self.slope_x_input.setText(f"{slope_x:.2f}")
        self.slope_y_input.setText(f"{slope_y:.2f}")
        self.auto_result_label.setText(f"Piana calcolata: base={a:.2f}, slope_x={slope_x:.2f} cm/100m, slope_y={slope_y:.2f} cm/100m")
        self.update_interpolated_grid()
    
    def update_interpolated_grid(self):
        # Se ci sono meno di 4 punti, non facciamo l'interpolazione (evitiamo l'errore e visualizziamo solo il punto corrente)
        if len(self.field_model.points) < 4:
            self.leveling_plot.img_item.clear()
            return
        # Evitiamo di avviare più worker contemporaneamente
        if self.interpolation_worker is not None and self.interpolation_worker.isRunning():
            return
        from interpolation_worker import InterpolationWorker
        self.interpolation_worker = InterpolationWorker(self.field_model.points, resolution=1.0)
        self.interpolation_worker.result_ready.connect(self.on_interpolation_result)
        self.interpolation_worker.start()
    
    def on_interpolation_result(self, grid_x, grid_y, survey_grid):
        if grid_x is None or survey_grid is None:
            return
        base_elev = self.field_model.points[0]["alt"] if self.field_model.points else 0
        try:
            slope_x = float(self.slope_x_input.text())
            slope_y = float(self.slope_y_input.text())
        except ValueError:
            slope_x = 0.0
            slope_y = 0.0
        from leveling import compute_target_grid
        target_grid = compute_target_grid(grid_x, grid_y, slope_x, slope_y, base_elev)
        self.leveling_plot.update_grid(grid_x, grid_y, survey_grid, target_grid)
        import numpy as np
        diff = target_grid - survey_grid
        min_diff = np.nanmin(diff)
        max_diff = np.nanmax(diff)
        self.color_bar.setRange(min_diff, max_diff)
    
    def update_tractor(self, x, y, current_alt=None):
        self.leveling_plot.update_tractor(x, y)
        # Calcola l'elevazione target al punto attuale usando il modello
        try:
            slope_x = float(self.slope_x_input.text())
            slope_y = float(self.slope_y_input.text())
        except ValueError:
            slope_x = 0.0
            slope_y = 0.0
        base_elev = self.field_model.points[0]["alt"] if self.field_model.points else 0
        target_elev = base_elev + x * (slope_x / 10000.0) + y * (slope_y / 10000.0)
        if current_alt is not None:
            diff = target_elev - current_alt
            self.elev_info_label.setText(f"Current Elev: {current_alt:.2f}, Target: {target_elev:.2f}, Diff: {diff:.2f}")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Software di Livellamento Terreno")
        self.resize(1000,600)
        self.field_model = FieldModel()
        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)
        
        self.survey_widget = SurveyWidget(self.field_model)
        self.leveling_widget = LevelingWidget(self.field_model)
        self.stacked_widget.addWidget(self.survey_widget)   # indice 0: survey
        self.stacked_widget.addWidget(self.leveling_widget)   # indice 1: leveling
        
        self.stacked_widget.setCurrentIndex(0)
        self.survey_widget.end_survey_btn.clicked.connect(self.end_survey)
        
        # Avvio del GPSReceiver (rimane attivo in entrambe le fasi)
        self.gps_receiver = GPSReceiver()
        self.gps_receiver.new_data.connect(self.handle_gps_data)
        self.gps_receiver.start()
        
        # Dock per lo status
        self.status_dock = QDockWidget("Status", self)
        self.status_widget = QWidget()
        status_layout = QVBoxLayout(self.status_widget)
        self.gps_status_label = QLabel("GPS: Non in ricezione")
        status_layout.addWidget(self.gps_status_label)
        self.elevation_status_label = QLabel("Elevation: --")
        status_layout.addWidget(self.elevation_status_label)
        self.status_dock.setWidget(self.status_widget)
        self.addDockWidget(Qt.RightDockWidgetArea, self.status_dock)
    
    def handle_gps_data(self, gps_data):
        self.field_model.add_point(gps_data)
        x, y = self.field_model.latlon_to_xy(gps_data["latitude"], gps_data["longitude"])
        if self.stacked_widget.currentIndex() == 0:
            self.survey_widget.update_plot()
            self.survey_widget.update_tractor(x, y)
        elif self.stacked_widget.currentIndex() == 1:
            self.leveling_widget.update_tractor(x, y, current_alt=gps_data["altitude"])
            self.leveling_widget.update_interpolated_grid()
        self.gps_status_label.setText("GPS: In ricezione")
        self.elevation_status_label.setText(f"Elevation: {gps_data['altitude']:.2f}")
    
    def end_survey(self):
        filename, _ = QFileDialog.getSaveFileName(self, "Salva Dati Campo", "", "File JSON (*.json)")
        if filename:
            self.field_model.save_to_file(filename)
        self.stacked_widget.setCurrentIndex(1)
    
    def closeEvent(self, event):
        self.gps_receiver.stop()
        event.accept()

def main():
    app = QApplication(sys.argv)
    dlg = StartupDialog()
    if dlg.exec_() == QDialog.Accepted:
        main_win = MainWindow()
        if dlg.choice == "continue":
            filename, _ = QFileDialog.getOpenFileName(main_win, "Carica Dati Campo", "", "File JSON (*.json)")
            if filename:
                main_win.field_model.load_from_file(filename)
                main_win.stacked_widget.setCurrentIndex(1)
        main_win.show()
        sys.exit(app.exec_())

if __name__ == "__main__":
    main()
