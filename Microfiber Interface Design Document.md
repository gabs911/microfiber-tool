

**SOFTWARE DESIGN AND MAINTENANCE DOCUMENT**

1. **SYSTEM OVERVIEW**  
   The Microfiber Controller is a desktop application designed to translate high-level geometric parameters (fiber length, spacing, etc.) into low-level machine instructions (G-code).  
   The software interfaces with a modified Cartesian 3D printer. The key hardware modification is the replacement of the standard filament extruder/hotend with a custom syringe pump mechanism. The syringe's plunger is actuated by the printer's extruder stepper motor (E-axis) driving a lead screw.

**Architecture Pattern**

The software loosely follows the Model-View-Controller (MVC) design pattern, implemented via PySide6 (Qt for Python):

* Model (AppState & Params): Holds all user-defined parameters and machine state.  
* View (ui.py): The graphical interface. It observes the Model and updates itself when the Model changes.  
* Controller (MachineController): Handles the drawing logic, serial communication, and G-code generation based on the Model's parameters.

2. **HARDWARE-TO-SOFTWARE MAPPING**  
* X / Y Axes: Standard planar movement. Defines the length, width, and spacing of the microfiber array.  
* Z Axis: Controls the vertical clearance. Crucial for the Z-Offset (drawing height) and Z-Hop (travel height) to prevent dragging the syringe nozzle across the substrate.  
* E Axis (Extruder): Repurposed to drive the syringe plunger. An instruction like G1 E1.0 moves the plunger downward. The exact volume extruded depends on the physical lead screw pitch and the syringe's internal diameter, which is abstracted into "Droplet Amount (E units)" in the UI.  
    
3. **CODEBASE STRUCTURE**

**main.py**

The entry point. It instantiates the application, the AppState, the MachineController, and the MainWindow, wiring them together before starting the Qt event loop.

**backend.py**

The core engine of the application.

* Params (Dataclass): A pure data structure containing default values for all parameters.  
* AppState: Inherits from QObject. Emits Qt signals (changed, log) whenever a parameter is modified. Includes serialization logic (to\_project\_dict, apply\_project\_dict) for saving/loading.  
* MachineController:  
  * Serial Comms: Handles connection to the machine. Uses a strict "send and wait for ok" synchronous loop (\_send\_and\_wait\_ok) to prevent overflowing the printer's serial buffer.  
  * G-Code Generation: The \_run\_custom\_centered method acts as a mini-slicer. It calculates coordinates dynamically inside a while loop based on the AppState parameters.  
  * Threading: Drawing operations (start\_drawing) are offloaded to a QThread using a DrawingWorker. Crucial: Serial communication is blocking. If run on the main UI thread, the application will freeze. Always use the worker thread for prolonged machine operations.

**ui.py**

The graphical interface, utilizing PySide6 widgets.

* Page System: Uses a QStackedWidget paired with a QListWidget (sidebar) to navigate between different configuration screens (Welcome, Draw, Syringe, Summary, Connection).  
* RectanglePreview: A custom QWidget that overrides the paintEvent to draw a live 2D representation of the machine bed, the safe bounds, and the programmed print area.  
* State Synchronization: The UI widgets update the AppState via signals (e.g., valueChanged.connect). The UI also listens to the AppState.changed signal to update itself if the state changes programmatically (e.g., when a project is loaded).  
4. KEY DESIGN DECISIONS & CONSTRAINTS

**4.1. The "Safe Area" Hard Constraint**

Because the hardware has a physical syringe that can crash into bed clips or non-printable zones, a "Safe Area" is enforced at the software level (safe\_x\_min, safe\_x\_max, safe\_y\_min, safe\_y\_max in Params).

* The \_compute\_anchored\_rect method in MachineController actively verifies that the entire requested array fits within this bounding box.  
* If a user inputs dimensions that exceed these bounds, the RectanglePreview turns red, and the drawing loop will throw an error rather than attempting to print.

**4.2. Live Parameter Updates**

The \_run\_custom\_centered loop re-reads self.state.params at the start of every single fiber pass. This was an intentional design choice. It allows the user to tweak parameters (like speed or Z-offset) while the machine is printing, and the changes will take effect on the very next fiber.

**4.3 Relative vs. Absolute Extrusion**

* Motion (X, Y, Z): Uses Absolute Positioning (G90).  
* Extrusion (E): The script dynamically toggles to Relative Positioning (G91) just for the extrusion/afterdrop sequences, and then resets back to Absolute (G90). This prevents the need to track absolute E-axis coordinates over the entire print.  
    
5. **GUIDE: HOW TO ADD A NEW PARAMETER**  
   If a future maintainer needs to add a new parameter, follow these exact steps to ensure it propagates through the whole MVC architecture:  
   1. Update the Model: Add the variable and its default value to the Params dataclass in backend.py.  
   2. Update Serialization: Add the parameter to the dictionaries in both to\_project\_dict and apply\_project\_dict inside AppState to ensure it saves/loads correctly.  
   3. Update PDF Export (Optional): Add it to summary\_dict inside save\_pdf in MachineController.  
   4. Create the UI Element: In ui.py (likely in DrawPage), create the input widget (e.g., QSpinBox).  
   5. Wire UI to Model (Write): Connect the widget's signal to self.state.set\_param('new\_param\_name', value).  
   6. Wire Model to UI (Read): Inside \_sync\_from\_state in the UI class, read the value from self.state.params and update the widget. (Note: Always use .blockSignals(True) before updating the widget programmatically to prevent infinite feedback loops).  
   7. Implement the Logic: Finally, read self.state.params.new\_param\_name inside the G-code generation loop (\_run\_custom\_centered) and format it into the serial string sent to the printer.

**ANNEX: G-CODE REFERENCE GUIDE**

Since this script communicates directly with Marlin/RepRap firmware, it uses specific numerical commands (G-code) to move the motors and read sensors. Below is a glossary of the exact commands used in this codebase so maintainers without 3D printing experience can read the serial outputs.

G0 / G1 (Linear Move)

The most common command. G0 is technically for rapid non-extruding travel, and G1 is for coordinated extruding movement.

Example: G1 X10.0 Y20.0 Z0.4 F1500

Meaning: Move the toolhead to the X=10, Y=20, Z=0.4 coordinates at a speed (Feedrate) of 1500 mm/min.

G4 (Dwell / Pause)

Tells the machine to wait and do nothing for a specific amount of time.

Example: G4 P1000

Meaning: Pause all operations for 1000 milliseconds (1 second). Used in this script to let the droplet adhere before drawing the fiber.

G28 (Auto-Home)

Tells the printer to move its X, Y, and Z axes until they physically trigger their endstop switches, establishing the 0,0,0 origin point. This is executed immediately upon connection.

G90 (Absolute Positioning)

Tells the printer to interpret all X, Y, and Z coordinates as exact locations on the bed. For example, sending G1 X10 twice will result in the printer moving to the 10mm mark and then staying there.

G91 (Relative Positioning)

Tells the printer to interpret coordinates as distances from its current position. For example, sending G1 E1.0 twice will extrude 1 unit, and then extrude another 1 unit. This script temporarily switches to G91 for syringe drops, then switches back to G90 for bed movements.

G92 (Set Position)

Forces the printer to overwrite its current known location.

Example: G92 E0

Meaning: Tells the printer "Consider the current syringe position to be zero." This resets the internal counter so the next extrusion math starts fresh.

M119 (Get Endstop Status)

Queries the printer to report if the physical limit switches are currently pressed or unpressed. Used in the syringe homing sequence to detect if the syringe carriage has hit the top limit.

M220 / M221 (Set Speed/Flow Percentage)

M220 S100 sets the overall speed multiplier to 100%. M221 S100 sets the extrusion volume multiplier to 100%. Sent at the beginning of a print to clear any leftover modifiers from previous manual control.

M300 (Play Tone)

Example: M300 S440 P200

Meaning: Plays a beep from the LCD screen speaker at 440 Hz for 200 milliseconds. Used to signal the end of a drawing run.

M302 (Allow Cold Extrudes)

By default, 3D printers prevent the extruder motor from moving if the hotend isn't heated (to prevent stripping plastic). Because this is a syringe pump, there is no hotend.

Example: M302 S0

Meaning: Disables the minimum extrusion temperature safety lockout, allowing the syringe motor to turn at room temperature.

M400 (Wait for Moves to Finish)

Forces the firmware to finish every physical movement currently stored in its internal buffer before reading the next line of serial commands. Used in this script after each fiber is completed to keep the Python script tightly synchronized with the physical hardware.

