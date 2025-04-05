# main.py
import sys
import math
import platform
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QStackedWidget, QPushButton, QVBoxLayout, 
                             QHBoxLayout, QLabel, QLineEdit, QFileDialog, QMessageBox, QDialog, QDialogButtonBox, QDockWidget, QSlider)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont
from gps_receiver import GPSReceiver
from field_model import FieldModel
from plot_widget import FieldPlotWidget, LevelingPlotWidget, ElevationDiffColorBar
from leveling import compute_target_grid, compute_best_plane, compute_best_offset
import numpy as np

# Application-wide style constants
LARGE_FONT = "15pt"
MEDIUM_FONT = "10pt"
SMALL_FONT = "7pt"
XLARGE_FONT = "20pt"

class StartupDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Avvio rilevamento")
        layout = QVBoxLayout(self)
        label = QLabel("Vuoi continuare un campo già esistente o iniziarne uno nuovo? Oppure importa da AgOpenGPS")
        layout.addWidget(label)
        buttons = QDialogButtonBox(self)
        self.new_field_btn = buttons.addButton("Nuovo Campo", QDialogButtonBox.AcceptRole)
        self.continue_field_btn = buttons.addButton("Continua Campo", QDialogButtonBox.ActionRole)
        self.import_field_btn = buttons.addButton("Importa Campo Elevation.txt", QDialogButtonBox.ActionRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.choice = None
        self.new_field_btn.clicked.connect(self.choose_new)
        self.continue_field_btn.clicked.connect(self.choose_continue)
        self.import_field_btn.clicked.connect(self.choose_import)
    
    def choose_new(self):
        self.choice = "new"
        self.accept()
    
    def choose_continue(self):
        self.choice = "continue"
        self.accept()
        
    def choose_import(self):
        self.choice = "import"
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
        
        # Reduce spacing and margins between layout sections
        main_layout.setSpacing(1)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Input for slope and buttons
        input_layout = QHBoxLayout()
        
        # Add vertical offset input
        self.vertical_offset_label = QLabel("Offset verticale (cm):")
        self.vertical_offset_label.setStyleSheet(f"font-size: {MEDIUM_FONT};")
        self.vertical_offset_input = QLineEdit("0")
        self.vertical_offset_input.setStyleSheet(f"font-size: {MEDIUM_FONT};")
        self.vertical_offset_input.setPlaceholderText("Offset (cm)")
        input_layout.addWidget(self.vertical_offset_label)
        input_layout.addWidget(self.vertical_offset_input)
        
        # Original slope inputs
        self.slope_x_input = QLineEdit()
        self.slope_x_input.setPlaceholderText("Pendenza oriz. (cm/100m)")
        self.slope_x_input.setStyleSheet(f"font-size: {MEDIUM_FONT};")
        self.slope_y_input = QLineEdit()
        self.slope_y_input.setPlaceholderText("Pendenza vert. (cm/100m)")
        self.slope_y_input.setStyleSheet(f"font-size: {MEDIUM_FONT};")
        
        slope_x_label = QLabel("Pendenza orizz.:")
        slope_x_label.setStyleSheet(f"font-size: {MEDIUM_FONT};")
        input_layout.addWidget(slope_x_label)
        input_layout.addWidget(self.slope_x_input)
        
        slope_y_label = QLabel("Pendenza vert.:")
        slope_y_label.setStyleSheet(f"font-size: {MEDIUM_FONT};")
        input_layout.addWidget(slope_y_label)
        input_layout.addWidget(self.slope_y_input)
        
        self.compute_btn = QPushButton("Applica pendenze")
        self.compute_btn.setStyleSheet(f"font-size: {MEDIUM_FONT};")
        self.auto_compute_btn = QPushButton("Calcolo pendenze")
        self.auto_compute_btn.setStyleSheet(f"font-size: {MEDIUM_FONT};")
        self.save_grid_btn = QPushButton("Salva Campo")
        self.save_grid_btn.setStyleSheet(f"font-size: {MEDIUM_FONT};")
        input_layout.addWidget(self.compute_btn)
        input_layout.addWidget(self.auto_compute_btn)
        input_layout.addWidget(self.save_grid_btn)
        self.diff_label = QLabel("--")
        self.diff_label.setStyleSheet(f"font-size: {XLARGE_FONT};")
        input_layout.addWidget(self.diff_label)
        input_layout.setSpacing(0)  # Optionally adjust spacing specifically for input_layout

        # Create a horizontal layout for elev_info_label and cut_fill_label
        elev_cut_fill_layout = QHBoxLayout()
        self.elev_info_label = QLabel("Altezza: --, Obiettivo: --")
        self.elev_info_label.setStyleSheet(f"font-size: {LARGE_FONT};")
        elev_cut_fill_layout.addWidget(self.elev_info_label)
        self.cut_fill_label = QLabel("Terra da togliere: -- m³, Terra da mettere: -- m³")
        self.cut_fill_label.setStyleSheet(f"font-size: {LARGE_FONT};")
        elev_cut_fill_layout.addWidget(self.cut_fill_label)
        elev_cut_fill_layout.setSpacing(0)  # Optionally adjust spacing specifically for this layout

        # Add the two layouts to the main layout with minimal spacing
        main_layout.addLayout(input_layout)
        main_layout.addLayout(elev_cut_fill_layout)

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
        try:
            slope_x = float(self.slope_x_input.text())
            slope_y = float(self.slope_y_input.text())
            self.field_model.vertical_offset = float(self.vertical_offset_input.text()) / 100.0  # Convert from cm to meters
        except ValueError:
            print("Errore: valori di pendenza non validi.")
            slope_x = 0.0
            slope_y = 0.0
            self.field_model.vertical_offset = 0.0
        
        if self.field_model.vertical_offset != self.field_model.vertical_offset_old:
            offset = self.field_model.vertical_offset - self.field_model.vertical_offset_old
            self.field_model.apply_vertical_offset_grid(offset)
            self.field_model.vertical_offset_old = self.field_model.vertical_offset
            
        
        self.field_model.update_points_from_grid()
        
        self.field_model.plane_b = slope_x / 10000.0
        self.field_model.plane_c = slope_y / 10000.0
        self.field_model.plane_a = compute_best_offset(self.field_model.points, self.field_model.plane_b, self.field_model.plane_c)
        self.update_interpolated_grid()
        self.update_cut_fill()
    
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
        self.update_cut_fill()
    
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
            self.elev_info_label.setText(f"Altezza: {current_alt:.2f}, Obiettivo: {target_elev:.2f}")
            self.diff_label.setText(f"{diff*100:.0f} cm")
            self.color_bar.setLineValue(diff*100)

    def update_cut_fill(self):
        """Compute and display the cut/fill volumes based on the current plane."""
        points = self.field_model.points
        if not points:
            self.cut_fill_label.setText("Terra da togliere: -- m³, Terra da mettere: -- m³")
            return

        a = self.field_model.plane_a
        b = self.field_model.plane_b
        c = self.field_model.plane_c

        # For each point, compute residual: z - (a + b*x + c*y)
        deviations = []
        for p in points:
            x, y, z = p["x"], p["y"], p["z"]
            plane_z = a + b * x + c * y
            deviations.append(z - plane_z)
        
        deviations = np.array(deviations)
        cut = np.sum(deviations[deviations > 0])
        fill = np.sum(-deviations[deviations < 0])
        
        # Renamed output
        self.cut_fill_label.setText(
            f"Terra da togliere: {cut:.2f} m³, Terra da mettere: {fill:.2f} m³"
        )

class RotationDialog(QDialog):
    """Dialog for rotating the field before leveling, with a preview plot similar to survey/leveling."""
    def __init__(self, field_model, parent=None):
        super().__init__(parent)
        self.parent = parent
        parent.rotation_in_progress = True
        self.field_model = field_model
        self.setWindowTitle("Rotazione Campo")
        
        layout = QVBoxLayout(self)
        self.info_label = QLabel("Ruota il campo con lo slider, poi clicca 'Salva Rotazione'.")
        self.info_label.setStyleSheet(f"font-size: {LARGE_FONT};")
        layout.addWidget(self.info_label)
        
        # Slider for angle: -180..180 degrees
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(-180, 180)
        self.slider.setValue(int(math.degrees(self.field_model.rotation_angle)))
        layout.addWidget(self.slider)
        
        # Show current angle
        self.angle_label = QLabel(f"Angolo: {self.slider.value()}°")
        self.angle_label.setStyleSheet(f"font-size: {MEDIUM_FONT};")
        layout.addWidget(self.angle_label)
        
        # Preview plot using FieldPlotWidget
        self.plot_widget = FieldPlotWidget()
        layout.addWidget(self.plot_widget)
        
        # Store the original points so we can rotate in preview
        # Ensure we keep "z" if present
        self.original_points = []
        if len(self.field_model.points) > 1000:
            sampled_points = np.random.choice(self.field_model.points, 1000, replace=False)
        else:
            sampled_points = self.field_model.points
        
        for p in sampled_points:
            self.original_points.append({
            "x": p["x"],
            "y": p["y"],
            "z": p.get("z", 0)  # or 0 if no z key
            })
        
        # Save/close button
        button_layout = QHBoxLayout()
        self.save_button = QPushButton("Salva Rotazione")
        self.save_button.setStyleSheet(f"font-size: {MEDIUM_FONT};")
        button_layout.addWidget(self.save_button)
        layout.addLayout(button_layout)
        
        # Signals
        self.slider.valueChanged.connect(self.on_slider_changed)
        self.save_button.clicked.connect(self.on_save_clicked)
        
        # Initial preview
        self.draw_preview(self.slider.value())

    def on_slider_changed(self):
        new_angle_deg = self.slider.value()
        self.angle_label.setText(f"Angolo: {new_angle_deg}°")
        self.draw_preview(new_angle_deg)

    def draw_preview(self, angle_deg):
        """Rotate the original points by angle_deg and update the preview plot."""
        angle_rad = math.radians(angle_deg)
        cos_a, sin_a = math.cos(angle_rad), math.sin(angle_rad)
        
        rotated_points = []
        for p in self.original_points:
            x_old, y_old, z_val = p["x"], p["y"], p["z"]
            x_new = x_old * cos_a - y_old * sin_a
            y_new = x_old * sin_a + y_old * cos_a
            # Keep the original z
            rotated_points.append({"x": x_new, "y": y_new, "z": z_val})

        self.plot_widget.update_points(rotated_points)

    def on_save_clicked(self):
        # Store the final rotation angle
        angle_deg = self.slider.value()
        self.field_model.rotation_angle = math.radians(angle_deg)
        self.parent.rotation_in_progress = False
        self.accept()

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
        
        # Add a static text box on the left
        self.static_text_label = QLabel("Dove è rosso la terra è da togliere, dove è blu da mettere     ")
        self.static_text_label.setStyleSheet(f"font-size: {MEDIUM_FONT};")
        status_layout.addWidget(self.static_text_label)
        
        self.gps_status_label = QLabel("GPS: Non in ricezione")
        self.gps_status_label.setStyleSheet(f"font-size: {MEDIUM_FONT};")
        self.elevation_status_label = QLabel("Altitudine: --")
        self.elevation_status_label.setStyleSheet(f"font-size: {MEDIUM_FONT};")
        status_layout.addWidget(self.gps_status_label)
        status_layout.addWidget(self.elevation_status_label)
        self.status_widget.setLayout(status_layout)
        self.status_bar = self.statusBar()
        self.status_bar.addPermanentWidget(self.status_widget)
        
        self.rotation_in_progress = False
        self.gps_survey_count = 0
    
    def handle_gps_data(self, gps_data):
        """Handle incoming GPS data and update the field model and plot."""
        if self.rotation_in_progress:
            return
        x, y = self.field_model.latlon_to_xy(gps_data["latitude"], gps_data["longitude"])
        
        # Rotate the tractor coordinates
        angle = self.field_model.rotation_angle
        x_rot = x*math.cos(angle) - y*math.sin(angle)
        y_rot = x*math.sin(angle) + y*math.cos(angle)
        
        if gps_data["headingTrue"]>0 and gps_data["headingTrue"]<360:
            heading = gps_data["headingTrue"] - math.degrees(angle)
        elif gps_data["headingTrueDual"]>0 and gps_data["headingTrueDual"]<360:
            heading = gps_data["headingTrueDual"] - math.degrees(angle)
        else:
            heading = gps_data["imuHeading"]/10 - math.degrees(angle) #TODO actually to do a manual VTG
        
        if self.stacked_widget.currentIndex() == 0:  # survey phase
            self.gps_survey_count += 1
            # Every 10 points, add to the field model
            if self.gps_survey_count % 10 == 0:
                self.field_model.add_point(gps_data)
                self.survey_widget.update_plot()
                self.survey_widget.update_tractor(x_rot, y_rot, heading=heading)
        elif self.stacked_widget.currentIndex() == 1:  # leveling phase
            current_alt = gps_data["altitude"] - self.field_model.ref_alt
            # Update grid points in front of the tractor
            self.field_model.update_grid_elevation(
                x_rot, 
                y_rot, 
                current_alt, 
                radius=4.5,
                direction_deg=heading
            )
            self.leveling_widget.update_tractor(x_rot, y_rot, current_alt, heading)
            self.leveling_widget.update_interpolated_grid()
        
        self.gps_status_label.setText("GPS: In ricezione")
        self.elevation_status_label.setText(f"Altitudine: {gps_data['altitude']:.2f}")  
          
    def end_survey(self):
        filename, _ = QFileDialog.getSaveFileName(self, "Salva Dati Campo", "", "File JSON (*.json)")
        if filename:
            self.field_model.save_to_file(filename)
        
        # Open the rotation dialog
        rotation_dlg = RotationDialog(self.field_model, self)
        if rotation_dlg.exec_() == QDialog.Accepted:
            # Apply the rotation to the field points if needed:
            self.apply_rotation_to_points()
        
        self.generate_grid()
        
        # Switch to leveling mode
        self.stacked_widget.setCurrentIndex(1)
        self.leveling_widget.update_interpolated_grid()
        
    def apply_rotation_to_points(self):
        """Rotate existing points in self.field_model by self.field_model.rotation_angle."""
        angle = self.field_model.rotation_angle
        for p in self.field_model.points:
            x_old, y_old = p["x"], p["y"]
            x_new = x_old*math.cos(angle) - y_old*math.sin(angle)
            y_new = x_old*math.sin(angle) + y_old*math.cos(angle)
            p["x"], p["y"] = x_new, y_new
    
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
    # Enable high DPI display support
    if hasattr(Qt, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    
    app = QApplication(sys.argv)
    
    # Set application-wide font scaling
    if platform.system() == 'Windows':
        font = app.font()
        font_size = font.pointSize()
        if font_size < 0:  # If pointSize is not available
            font_size = font.pixelSize()
        font.setPointSize(int(font_size * 1.2))  # Increase by 20%
        app.setFont(font)
    
    dlg = StartupDialog()
    if dlg.exec_() == QDialog.Accepted:
        main_win = MainWindow()
        
        if dlg.choice == "continue":
            filename, _ = QFileDialog.getOpenFileName(main_win, "Carica Dati Campo", "", "File JSON (*.json)")
            if filename:
                main_win.field_model.load_from_file(filename)
                
                # Apply rotation after loading but before generating the grid
                if abs(main_win.field_model.rotation_angle) > 1e-9:
                    main_win.apply_rotation_to_points()
                    
                main_win.stacked_widget.setCurrentIndex(1)
                main_win.generate_grid()
        
        elif dlg.choice == "import":
            # Ask user to select the Elevation.txt file
            filename, _ = QFileDialog.getOpenFileName(main_win, "Importa Elevation.txt", "", "File di testo (*.txt)")
            if filename:
                try:
                    # First, import directly to a grid structure for efficiency
                    if main_win.field_model.import_from_elevation_txt_to_grid(filename, resolution=1.0):
                        # Convert grid to points for rotation
                        main_win.field_model.update_points_from_grid()
                        
                        # Show rotation dialog
                        rotation_dlg = RotationDialog(main_win.field_model, main_win)
                        if rotation_dlg.exec_() == QDialog.Accepted:
                            # Apply rotation to points
                            main_win.apply_rotation_to_points()
                            
                            # Regenerate grid from rotated points
                            main_win.field_model.generate_leveling_grid(resolution=1.0)
                        
                        # Switch to leveling mode
                        main_win.stacked_widget.setCurrentIndex(1)
                        main_win.leveling_widget.update_interpolated_grid()
                    else:
                        QMessageBox.warning(main_win, "Errore", "Impossibile importare dati da Elevation.txt. File non valido o vuoto.")
                except Exception as e:
                    QMessageBox.warning(main_win, "Errore", f"Errore nell'importazione: {str(e)}")
        
        main_win.show()
        sys.exit(app.exec_())

if __name__ == "__main__":
    main()
