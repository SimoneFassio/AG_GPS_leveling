# main.py
import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QStackedWidget, QPushButton, QVBoxLayout, 
                             QHBoxLayout, QLabel, QLineEdit, QFileDialog, QMessageBox, QDialog, QDialogButtonBox, QDockWidget)
from PyQt5.QtCore import Qt, QTimer
from gps_receiver import GPSReceiver
from field_model import FieldModel
from plot_widget import FieldPlotWidget, LevelingPlotWidget, ElevationDiffColorBar
from leveling import compute_target_grid, compute_best_plane, compute_best_offset
import numpy as np

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
    
    def update_tractor(self, x, y, heading):
        self.plot_widget.update_tractor(x, y, heading)

class LevelingWidget(QWidget):
    def __init__(self, field_model, parent=None):
        super().__init__(parent)
        self.field_model = field_model
        main_layout = QVBoxLayout(self)
        
        # Input for slope and buttons
        input_layout = QHBoxLayout()
        self.slope_x_input = QLineEdit()
        self.slope_x_input.setPlaceholderText("Pendenza X (cm/100m)")
        self.slope_y_input = QLineEdit()
        self.slope_y_input.setPlaceholderText("Pendenza Y (cm/100m)")
        input_layout.addWidget(QLabel("Pendenza X:"))
        input_layout.addWidget(self.slope_x_input)
        input_layout.addWidget(QLabel("Pendenza Y:"))
        input_layout.addWidget(self.slope_y_input)
        self.compute_btn = QPushButton("Applica Livellamento")
        self.auto_compute_btn = QPushButton("Calcolo Automatico Piana")
        self.save_grid_btn = QPushButton("Salva Campo")
        input_layout.addWidget(self.compute_btn)
        input_layout.addWidget(self.auto_compute_btn)
        input_layout.addWidget(self.save_grid_btn)
        self.diff_label = QLabel("--")
        self.diff_label.setStyleSheet("font-size: 50px;")
        input_layout.addWidget(self.diff_label)
        main_layout.addLayout(input_layout)
        self.elev_info_label = QLabel("Current Elev: --, Target: --")
        main_layout.addWidget(self.elev_info_label)
        
        # Layout orizzontale per plot e color bar
        plot_layout = QHBoxLayout()
        self.leveling_plot = LevelingPlotWidget()  # Mostra la griglia interpolata
        plot_layout.addWidget(self.leveling_plot, stretch=4)
        self.color_bar = ElevationDiffColorBar()
        plot_layout.addWidget(self.color_bar, stretch=1)
        main_layout.addLayout(plot_layout)
        
        # Connessione bottoni
        self.compute_btn.clicked.connect(self.apply_levelling)
        self.auto_compute_btn.clicked.connect(self.auto_compute)
        self.save_grid_btn.clicked.connect(self.save_grid)
        
    
    def apply_levelling(self):
        self.field_model.update_points_from_grid()
        try:
            slope_x = float(self.slope_x_input.text())
            slope_y = float(self.slope_y_input.text())
        except ValueError:
            slope_x = 0.0
            slope_y = 0.0
        
        self.field_model.plane_b = slope_x / 10000.0
        self.field_model.plane_c = slope_y / 10000.0
        self.field_model.plane_a = compute_best_offset(self.field_model.points, self.field_model.plane_b, self.field_model.plane_c)
        self.update_interpolated_grid()
    
    def auto_compute(self):
        self.field_model.update_points_from_grid()
        if not self.field_model.points:
            QMessageBox.warning(self, "Errore", "Nessun dato di rilevamento disponibile.")
            return
        a, b, c = compute_best_plane(self.field_model.points)
        self.field_model.plane_a = a
        self.field_model.plane_b = b
        self.field_model.plane_c = c
        
        slope_x = b * 10000.0
        slope_y = c * 10000.0
        self.slope_x_input.setText(f"{slope_x:.2f}")
        self.slope_y_input.setText(f"{slope_y:.2f}")
        self.update_interpolated_grid()
    
    def save_grid(self):
        filename, _ = QFileDialog.getSaveFileName(self, "Salva Griglia come Punti", "", "File JSON (*.json)")
        if filename:
            self.field_model.save_grid_as_points(filename)
            QMessageBox.information(self, "Salvataggio Completato", "Griglia salvata come punti.")
    
    def update_interpolated_grid(self):
        if not self.field_model.leveling_mode:
            return
            
        if self.field_model.plane_b is not None:
            target_grid = compute_target_grid(
                self.field_model.grid_x, 
                self.field_model.grid_y, 
                self.field_model.plane_a, 
                self.field_model.plane_b, 
                self.field_model.plane_c
            )
            self.leveling_plot.update_grid(
                self.field_model.grid_x, 
                self.field_model.grid_y, 
                self.field_model.grid_z, 
                target_grid
            )
            diff = self.field_model.grid_z - target_grid
            min_diff = np.nanmin(diff)
            max_diff = np.nanmax(diff)
            self.color_bar.setRange(min_diff*100, max_diff*100)
    
    def update_tractor(self, x, y, current_alt, heading):
        self.leveling_plot.update_tractor(x, y, heading)
        if self.field_model.plane_b is not None:
            target_elev = compute_target_grid(x, y, self.field_model.plane_a, self.field_model.plane_b, self.field_model.plane_c)
        if current_alt is not None:
            diff = current_alt - target_elev
            self.elev_info_label.setText(f"Current Elev: {current_alt:.2f}, Target: {target_elev:.2f}")
            self.diff_label.setText(f"{diff*100:.0f} cm")
            self.color_bar.setLineValue(diff*100)

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
        self.status_widget = QWidget()
        status_layout = QHBoxLayout(self.status_widget)
        self.gps_status_label = QLabel("GPS: Non in ricezione")
        self.elevation_status_label = QLabel("Elevation: --")
        status_layout.addWidget(self.gps_status_label)
        status_layout.addWidget(self.elevation_status_label)
        self.status_widget.setLayout(status_layout)
        self.status_bar = self.statusBar()
        self.status_bar.addPermanentWidget(self.status_widget)
    
    def handle_gps_data(self, gps_data):
        x, y = self.field_model.latlon_to_xy(gps_data["latitude"], gps_data["longitude"])
        
        if self.stacked_widget.currentIndex() == 0:  # survey phase
            self.field_model.add_point(gps_data)
            self.survey_widget.update_plot()
            self.survey_widget.update_tractor(x, y, heading=gps_data["headingTrueDual"])
        elif self.stacked_widget.currentIndex() == 1:  # leveling phase
            current_alt = gps_data["altitude"] - self.field_model.ref_alt
            # Update grid points in front of the tractor
            self.field_model.update_grid_elevation(
                gps_data["latitude"], 
                gps_data["longitude"], 
                current_alt, 
                radius=4.5,
                direction_deg=gps_data["headingTrueDual"]
            )
            self.leveling_widget.update_tractor(x, y, current_alt, gps_data["headingTrueDual"])
            self.leveling_widget.update_interpolated_grid()
        
        self.gps_status_label.setText("GPS: In ricezione")
        self.elevation_status_label.setText(f"Elevation: {gps_data['altitude']:.2f}")  
          
    def end_survey(self):
        filename, _ = QFileDialog.getSaveFileName(self, "Salva Dati Campo", "", "File JSON (*.json)")
        if filename:
            self.field_model.save_to_file(filename)
        
        self.generate_grid()
        
        # Switch to leveling mode
        self.stacked_widget.setCurrentIndex(1)
        self.leveling_widget.update_interpolated_grid()
        
    def generate_grid(self):
        # Generate the leveling grid before switching to leveling mode
        if len(self.field_model.points) < 4:
            QMessageBox.warning(self, "Errore", "Sono necessari almeno 4 punti per generare la griglia di livellamento.")
            return
            
        # Generate grid with 1m resolution
        if not self.field_model.generate_leveling_grid(resolution=1.0):
            QMessageBox.warning(self, "Errore", "Impossibile generare la griglia di livellamento.")
            return
        
        print(f"Grid generated with shape: {self.field_model.grid_z.shape}")
        
        self.field_model.plane_a = compute_best_offset(self.field_model.points, self.field_model.plane_b, self.field_model.plane_c)
        self.leveling_widget.update_interpolated_grid()
        
    
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
                main_win.generate_grid()
        main_win.show()
        sys.exit(app.exec_())

if __name__ == "__main__":
    main()
