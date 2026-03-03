# Microfiber Drawing Controller

This repository contains a PySide6-based graphical user interface (GUI) designed to control a custom microfiber drawing tool. The hardware is built on top of a modified 3D printer chassis equipped with a custom syringe extruder. 

## Features
* **Custom Extrusion Control:** Direct control over a syringe-based extruder for precise microfiber deposition.
* **Parametric Toolpath Generation:** Automatically generates G-code for horizontal or vertical fiber arrays based on geometric parameters.
* **Safe Area Boundaries:** Enforces physical hardware limits to prevent the toolhead from crashing.
* **Live Hardware Communication:** Real-time serial connection to Marlin/RepRap firmware with homing, pausing, and live parameter updates.
* **Project Management:** Save and load drawing configurations as JSON files, and export run summaries as PDFs.

---

## Installation

### Prerequisites
* Python 3.8 or higher

### Setup
1. Clone the repository to your local machine:
   ```bash
   git clone https://github.com/gabs911/microfiber-tool.git
   cd microfiber-controller
   ```

2. Install the required Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Launch the application:
   ```bash
   python main.py
   ```

---

## Usage

1. **Connect:** Navigate to the **Connection** tab. The software will automatically scan for available serial ports (at 115200 baud). Click **Connect**. The machine will automatically home its axes (G28) upon a successful connection.
2. **Setup Syringe:** Go to the **Syringe** tab to home the syringe plunger or prime it using the intake/ml controls.
3. **Configure Layout:** On the **Draw** tab, define the dimensions, spacing, and starting coordinates of your microfiber array. The UI will provide a live preview of the drawing rectangle relative to the safe bed area. Green indicates a valid placement; red indicates the toolpath exceeds the safe bounds.
4. **Set Deposition Parameters:** Adjust speed, Z-offset, and extrusion amounts in the "Drawing parameters" section.
5. **Run:** Once configured, navigate back to the **Connection** tab and click **Do Science!** to begin the drawing process. You can pause or stop the operation at any time.

---

## Parameter Glossary

### Layout Parameters
These parameters define the geometry of the fiber array you are printing.
* **Orientation:** The direction the fibers will be drawn (`Horizontal` or `Vertical`).
* **Length (mm):** The length of the individual fibers.
* **Width (mm):** The total width of the array (perpendicular to the fiber length).
* **Spacing (mm):** The distance between each parallel fiber.
* **Starting X / Y (mm):** The bottom-left anchor coordinate of the rectangular array.

### Drawing Parameters
These control the physical motion and extrusion behavior of the machine.
* **Speed (mm/min):** The travel speed of the print head during deposition.
* **Droplet Amount (E units):** The volume of material extruded at the start of a fiber to anchor it.
* **Z-Offset (mm):** The absolute Z-height used while actively drawing a fiber. Use the `Test Z-Offset` button to verify this height safely.
* **Z-Hop (mm):** The clearance height the print head raises to when traveling between fiber lines.
* **Pause (ms):** A programmed delay (G4 command) after anchoring the droplet, allowing material to adhere before pulling the fiber.
* **Afterdrop:** If enabled, the extruder will perform a secondary, smaller extrusion at the end of the fiber to detach/anchor the tail.
* **Clean:** If enabled, the print head will execute a wiping motion outside the array boundary after completing a fiber to break off trailing material.

### Syringe Parameters
* **Syringe Current Amount:** Tracks the theoretical position/volume of the syringe based on commanded moves.
* **Syringe Droplet Units:** The specific amount of material to draw into the syringe when using the intake function.


This tool was developed by Gabriel Alvares de Sousa Guimaraes under the supervision of Andrii Shykarenko at the Technical University of Liberec.