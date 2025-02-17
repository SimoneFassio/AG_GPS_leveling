# Terrain Leveling Software Documentation

## Overview

This application is designed for real-time terrain leveling using PyQt5. It collects GPS data, stores and processes field survey points, and then uses these data to compute and display target elevations for leveling. The application is divided into two main phases:

1. **Survey Phase:**  
   - Collects GPS points from a UDP stream.
   - Displays these points on a scatter plot along with the current tractor position.
   - Saves the field data into a JSON file once the survey is finished.

2. **Leveling Phase:**  
   - Uses the collected survey data to interpolate the terrain on a regular grid.
   - Computes target elevations based on user-defined slopes or by automatically calculating the best-fit plane.
   - Displays a continuous grid view (with color mapping) of the difference between the survey and target elevations.
   - Shows additional status information (current GPS elevation, target elevation, and the difference).

The design emphasizes modularity, responsiveness (via multithreading), and a clear separation between data, computations, and user interface.

---

## Architecture & Design

### Modular Design

The project is split into several Python files, each handling a specific responsibility:

- **`gps_receiver.py`**  
  Handles real-time reception of GPS data over UDP.  
  **Key elements:**
  - **GPSReceiver (QThread subclass):** Continuously listens for UDP packets on a specified port.
  - **parse_gps_data function:** Decodes the binary data format, validates the header and checksum, and extracts GPS values (latitude, longitude, altitude, headings, etc.).
  - **Signal Emission:** Once a valid GPS reading is parsed, a signal is emitted so the main application can update the UI and field model.

- **`field_model.py`**  
  Manages the field survey data.  
  **Key elements:**
  - **FieldModel class:**  
    - **Data Storage:** Holds a list of survey points. Each point is a dictionary containing latitude, longitude, altitude, and computed local X/Y coordinates.
    - **Coordinate Conversion:** Converts geographic coordinates (lat/lon) into a local Cartesian system using a simple equirectangular approximation (based on a reference point).
    - **Persistence:** Provides methods to save the collected field data to a JSON file and load from it.
  - **Design Choice:**  
    The separation of the data model from the UI logic makes it easier to manage, extend, or replace the data-handling logic later.

- **`leveling.py`**  
  Contains the computation logic for target elevations and leveling analysis.  
  **Key elements:**
  - **compute_best_plane:** Uses a least-squares approach to fit a plane to the survey points, automatically determining the best slopes that minimize the volume of moved soil.
  - **compute_target_grid:** Generates a grid of target elevations using the same slope-based formula as for individual points.
  - **Design Choice:**  
    Encapsulating these mathematical operations in their own module keeps the computational logic separate from UI and data handling, making it easier to modify or improve the leveling algorithms.

- **`plot_widget.py`**  
  Implements the graphical components for displaying the survey and leveling data using pyqtgraph.  
  **Key elements:**
  - **FieldPlotWidget:**  
    - Used during the survey phase.
    - Displays survey points as a scatter plot.
    - Updates the plot in real time as new points are added.
  - **LevelingPlotWidget:**  
    - Used during the leveling phase.
    - Displays a continuous grid (using an ImageItem) that shows the difference between the survey and target elevations.
    - Includes a marker for the current tractor position.
  - **ElevationDiffColorBar:**  
    - A custom widget that displays a vertical color gradient (from red through white to blue) corresponding to the range of elevation differences.
  - **Design Choice:**  
    Using pyqtgraph ensures fast and efficient rendering for real-time data updates. Separating the display widgets for different phases allows for tailored visualization in each phase.

- **`interpolation_worker.py`**  
  Offloads heavy interpolation computations to a separate thread.  
  **Key elements:**
  - **InterpolationWorker (QThread subclass):**  
    - Performs grid interpolation using `scipy.interpolate.griddata` on the collected survey points.
    - Checks the number of points and, if there are too few (less than 4), uses an alternative (e.g., nearest-neighbor) method to avoid errors.
    - Emits a signal with the resulting grid data once the computation is complete.
  - **Design Choice:**  
    Running interpolation in a separate thread prevents the main UI from freezing when handling large datasets or computationally expensive tasks.

- **`main.py`**  
  The entry point and central controller of the application.  
  **Key elements:**
  - **StartupDialog:**  
    - Prompts the user at startup to either load an existing field or start a new survey.
  - **SurveyWidget:**  
    - Manages the UI for the survey phase.
    - Uses `FieldPlotWidget` to display collected GPS points.
    - Includes a button to end the survey.
  - **LevelingWidget:**  
    - Manages the UI for the leveling phase.
    - Provides input fields for desired slopes, buttons for applying leveling or auto-computing the best-fit plane.
    - Displays the interpolated grid along with the color bar and additional elevation information (current, target, and difference).
    - Uses a timer to trigger grid updates and an interpolation worker to compute the grid without blocking the UI.
  - **MainWindow:**  
    - Uses a QStackedWidget to switch between the survey and leveling phases.
    - Contains a dock widget that shows status indicators (GPS reception and current elevation).
    - Listens for new GPS data and updates the field model and appropriate UI widgets accordingly.
  - **Design Choice:**  
    The main window acts as the coordinator, ensuring that data flows from the GPS receiver to the data model, and then to the appropriate visualization components. The use of a stacked widget provides a clear separation between phases.

---

## Key Design Concepts

### 1. Separation of Concerns & Modularity
- **Data, Logic, and UI Separation:**  
  Each module is responsible for a distinct part of the system (data reception, storage, processing, or display). This makes it easier to update or replace parts of the system independently.
- **Ease of Extension:**  
  The modular structure allows you to add new features (e.g., additional data analyses or visualization options) without needing to refactor the entire application.

### 2. Responsiveness & Multithreading
- **Using QThread:**  
  The GPSReceiver and InterpolationWorker run in their own threads. This prevents blocking the main UI thread, ensuring that the application remains responsive even when handling intensive tasks.
- **Signal/Slot Communication:**  
  Modules communicate via signals and slots (a core concept in PyQt5). For example, when the InterpolationWorker completes its computation, it emits a signal that triggers an update in the leveling display.

### 3. Real-Time Data Visualization
- **pyqtgraph Integration:**  
  The application uses pyqtgraph for efficient real-time plotting. This choice supports the fast and smooth visualization of changing data, which is crucial in applications that handle live GPS data.
- **Dynamic Updates:**  
  The UI is continuously updated as new GPS data arrives. In the leveling phase, additional information like the current elevation, target elevation, and their difference are updated in real time, providing immediate feedback to the user.

### 4. Data Persistence & Continuity
- **JSON Storage:**  
  Field data is saved and loaded in JSON format. This makes it easy to persist survey data between sessions, allowing users to continue working on the same field over multiple sessions.
- **Reference Point for Coordinate Conversion:**  
  The first GPS reading sets the reference point for converting lat/lon to local coordinates, ensuring consistency across all data points.

---

## Summary

- **GPS Receiver Module:**  
  Listens for UDP GPS data, decodes the binary packets, and emits signals for each valid reading.

- **Field Model:**  
  Stores survey points, handles coordinate conversion, and manages file-based persistence.

- **Leveling Module:**  
  Contains the mathematical logic to compute target elevations and fit a leveling plane to the survey data.

- **Plot Widgets:**  
  Provides real-time visualization of survey data (as a scatter plot) and leveling data (as an interpolated grid with a color bar).

- **Interpolation Worker:**  
  Offloads heavy interpolation computations to a separate thread to keep the UI responsive.

- **Main Application:**  
  Orchestrates the overall workflow using a multi-phase UI (survey and leveling), integrates real-time GPS updates, and provides user controls for saving data and computing leveling results.

The overall design prioritizes modularity, ease of maintenance, and a responsive user interface. With this documentation, you should have a clear understanding of the structure and logic behind the program, enabling you to continue extending or modifying the project with confidence.

Happy coding!