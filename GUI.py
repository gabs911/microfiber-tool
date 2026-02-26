from customtkinter import *
import tkinter as tk
from tkinter import filedialog as fd
from tkinter import messagebox
import json
from reportlab.pdfgen import canvas
import serial
from serial.tools import list_ports
import time
from datetime import datetime
import threading

ser = None


class MyTabView(CTkTabview):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs, anchor='w')

        # create tabs
        self.add("Draw")
        self.add("Syringe")
        self.add('Summary')
        self.add('Connection')
        self.add('Log')  # New tab

        # add widgets on tabs
        self.drawTab = DrawingFrame(master=self.tab("Draw"))
        self.syringeTab = SyringeFrame(master=self.tab("Syringe"))
        self.summaryTab = SummaryFrame(master=self.tab('Summary'))
        self.connectTab = ConnectFrame(master=self.tab("Connection"))
        self.logTab = LogFrame(master=self.tab('Log'))


class GUI(CTk):
    def __init__(self):
        super().__init__()
        self.title("Nanofiber Machine")
        self.geometry("800x600")
        set_appearance_mode("light")
        self.resizable(False, False)
        # declaring global variables
        global logTextVar
        logTextVar = tk.StringVar(value='This is the Log')
        global layers_var
        layers_var = tk.IntVar(value=1)
        global orientation_var
        orientation_var = tk.StringVar(value='Horizontal')
        global speed_var
        speed_var = tk.IntVar(value=1500)
        global step_var
        step_var = tk.DoubleVar(value=0.1)
        global zhopValue
        zhopValue = tk.StringVar(value='10')
        global cups_var
        cups_var = tk.IntVar(value=9)
        global pauseValue
        pauseValue = tk.StringVar(value='0')
        global zoffset
        zoffset = tk.DoubleVar(value=0.4)
        global amountValue
        amountValue = tk.StringVar(value='1')
        global abort
        abort = False
        global current_amount
        current_amount = tk.IntVar(value=0)

        # welcome message, with load and new button
        self.welcomeLabel = CTkLabel(self, text="NanoFiber Fabrication Interface\n for Ender printer",
                                     font=("Arial", 40))
        self.newButton = CTkButton(self, text="New", font=("Arial", 25), command=self.new)
        self.loadButton = CTkButton(self, text="Load", font=("Arial", 25), command=self.load, fg_color='grey',
                                    hover_color='dark grey')
        self.infoButton = CTkButton(self, text="Info", font=("Arial", 20), command=infoMessage)

        # placing widgets
        self.welcomeLabel.place(relx=0.5, rely=0.3, anchor='center')
        self.newButton.place(relx=0.3, rely=0.5, anchor='center', relwidth=0.25, relheight=0.15)
        self.loadButton.place(relx=0.7, rely=0.5, anchor='center', relwidth=0.25, relheight=0.15)
        self.infoButton.place(relx=0.5, rely=0.9, anchor='center', relwidth=0.2, relheight=0.08)

        self.mainloop()

    def new(self):
        self.welcomeLabel.place_forget()
        self.newButton.place_forget()
        self.loadButton.place_forget()
        self.tabview = MyTabView(self)
        self.title("Nanofiber Machine - New Project")
        self.tabview.pack(fill='both', expand=True)

    def load(self):
        self.loadProject()
        self.welcomeLabel.place_forget()
        self.newButton.place_forget()
        self.loadButton.place_forget()
        self.tabview = MyTabView(self)
        self.tabview.pack(fill='both', expand=True)

    def loadProject(self):
        file_path = fd.askopenfilename(defaultextension=".json", filetypes=[("JSON files", "*.json")])

        # If a file path was selected
        if file_path:
            # Load the data from the .json file into a dictionary
            with open(file_path, 'r') as f:
                data = json.load(f)

            # Assign the values from the dictionary to the variables of the program
            layers_var.set(data["Layers"])
            orientation_var.set(data["Orientation"])
            cups_var.set(data["Cups"])
            speed_var.set(data["Speed"])
            step_var.set(data["Step"])
            amountValue.set(data["Droplet Amount"])
            zhopValue.set(data["Z-Hop"])
            pauseValue.set(data["Pause"])
            zoffset.set(data["Z-Offset"])

            # Change the title of the window to include the name of the file
            project_name = os.path.basename(file_path).split('.')[0]
            self.title(f"Nanofiber Machine - {project_name}")

        print("Loaded project")
        logTextVar.set(logTextVar.get() + '\n' + 'Loaded project')


class SyringeFrame(CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color='transparent')
        self.pack(fill='both', expand=True)

        global current_amount

        self.rowconfigure((0, 1, 2, 3, 4, 5), weight=1, uniform='a')
        self.columnconfigure((0, 1, 2), weight=1, uniform='a')

        # creating widgets
        self.syringe_label = CTkLabel(self, text="Syringe", font=("Arial", 30))
        self.homeButton = CTkButton(self, text="Home", font=("Arial", 25), command=homeSyringe)
        self.amountOne = CTkButton(self, text="1", font=("Arial", 30), command=syringe_1ml)
        self.amountTwo = CTkButton(self, text="2", font=("Arial", 30), command=syringe_2ml)
        self.amountThree = CTkButton(self, text="3", font=("Arial", 30), command=syringe_3ml)
        self.amountFour = CTkButton(self, text="4", font=("Arial", 30), command=syringe_4ml)
        self.amountFive = CTkButton(self, text="5", font=("Arial", 30), command=syringe_5ml)
        self.dropletLabel = CTkLabel(self, text="Droplet size to intake", font=("Arial", 15))
        global droplet_var
        droplet_var = tk.IntVar(value=5)
        self.dropletEntry = CTkEntry(self, font=("Arial", 15), textvariable=droplet_var, width=3)
        self.columnconfigure((0, 1, 2, 3), weight=1, uniform='a')
        self.nextButton = CTkButton(self, text="Next", font=("Arial", 20), command=self.nextTab)
        self.backButton = CTkButton(self, text="Back", font=("Arial", 20), command=self.backTab, fg_color='grey',
                                    hover_color='dark grey')
        self.intakeButton = CTkButton(self, text="Droplet amount to intake", font=("Arial", 20), command=intakeAmount)
        self.amountLabel = CTkLabel(self, text="Current amount: ", font=("Arial", 20))
        self.currentAmountLabel = CTkLabel(self, textvariable=current_amount, font=("Arial", 20))

        # placing widgets
        self.syringe_label.grid(row=0, column=0, sticky="nswe", padx=10, pady=10)
        self.homeButton.grid(row=1, column=0, sticky="nsew", padx=30, pady=10)
        self.amountLabel.grid(row=3, column=0, sticky="nse", padx=10, pady=10)
        self.currentAmountLabel.grid(row=3, column=1, sticky="nsw", padx=30, pady=10)
        self.amountOne.grid(row=1, column=1, sticky="nsew", padx=30, pady=10)
        self.amountTwo.grid(row=2, column=1, sticky="nsew", padx=30, pady=10)
        self.dropletLabel.grid(row=4, column=0, sticky="e", padx=10, pady=10)
        self.dropletEntry.grid(row=4, column=1, sticky="we", pady=10, padx=(0, 100))
        self.intakeButton.grid(row=4, column=2, columnspan=2, sticky="nsw", padx=30, pady=10)
        self.amountThree.grid(row=1, column=2, sticky="nsew", padx=30, pady=10)
        self.amountFour.grid(row=2, column=2, sticky="nsew", padx=30, pady=10)
        self.amountFive.grid(row=1, column=3, sticky="nsew", padx=30, pady=10)
        self.nextButton.place(relx=0.95, rely=0.95, anchor='se', relwidth=0.15, relheight=0.08)
        self.backButton.place(relx=0.8, rely=0.95, anchor='se', relwidth=0.15, relheight=0.08)


    def nextTab(self):
        # Get the parent of this frame, which should be the MyTabView instance
        # Select the "Connection" tab
        self.master.master.set('Summary')

    def backTab(self):
        # Get the parent of this frame, which should be the MyTabView instance
        # Select the "Draw" tab
        self.master.master.set('Draw')


class DrawingFrame(CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color='transparent')
        self.pack(fill='both', expand=True)

        self.rowconfigure((0, 1, 2, 3, 4, 5, 6, 7, 8), weight=1, uniform='a')
        self.columnconfigure((0, 1, 2, 3, 4, 5), weight=1, uniform='a')

        # creating widgets
        self.drawingLabel = CTkLabel(self, text="Drawing", font=("Arial", 30))
        self.layersLabel = CTkLabel(self, text="Layers", font=("Arial", 20))
        self.layersBox = CTkComboBox(self, values=["1", "2", '3', '4', '5', '6', '7', '8', '9', '10'],
                                     command=layersBoxSelection, variable=layers_var, font=("Arial", 15))
        # orientation_var = 1 means vertical, 2 means horizontal, 3 means both
        self.orientationBox = CTkComboBox(self, values=["Vertical", "Horizontal", "Both"], font=("Arial", 15),
                                          variable=orientation_var, command=lambda x: print(orientation_var.get()))
        self.speedLabel = CTkLabel(self, text="Speed", font=("Arial", 20))
        self.speedSlider = CTkSlider(self, from_=100, to=5000, progress_color='transparent', variable=speed_var,
                                     orientation='horizontal', height=10)
        self.speed_varLabel = CTkLabel(self, textvariable=speed_var, font=("Arial", 20))
        self.mmperminLabel = CTkLabel(self, text="mm/min", font=("Arial", 15))
        self.stepLabel = CTkLabel(self, text="Step", font=("Arial", 20))
        self.stepEntry = IncrementDecrementEntry(self, step_var)
        self.mmLabel1 = CTkLabel(self, text="mm", font=("Arial", 15))
        self.mmLabel2 = CTkLabel(self, text="mm", font=("Arial", 15))
        self.mmLabel3 = CTkLabel(self, text="mm", font=("Arial", 15))
        # make droplet amount, length, z-hop, repetitions, x-step entries
        self.amountLabel = CTkLabel(self, text="Droplet Amount", font=("Arial", 17))
        global amountEntry
        amountEntry = CTkEntry(self, font=("Arial", 17), width=3, textvariable=amountValue)
        self.unitsLabel = CTkLabel(self, text="units", font=("Arial", 15))
        self.zhopLabel = CTkLabel(self, text="Z-Hop", font=("Arial", 20))
        global zhopEntry
        zhopEntry = CTkEntry(self, font=("Arial", 17), width=3, textvariable=zhopValue)
        self.pauseLabel = CTkLabel(self, text="Pause", font=("Arial", 20))
        global pauseEntry
        pauseEntry = CTkEntry(self, font=("Arial", 17), width=3, textvariable=pauseValue)
        self.timeLabel = CTkLabel(self, text="s", font=("Arial", 15))

        self.drawing3 = Drawing3(self)
        self.drawing6 = Drawing6(self)
        self.drawing9 = Drawing9(self)
        self.nextButton = CTkButton(self, text="Next", font=("Arial", 20), command=self.nextTab)
        self.zoffsetLabel = CTkLabel(self, text="Z-Offset", font=("Arial", 20))
        self.zoffsetEntry = IncrementDecrementEntry(self, zoffset)
        self.mmLabel5 = CTkLabel(self, text="mm", font=("Arial", 15))
        self.testButton = CTkButton(self, text="Test Z-offset", font=("Arial", 20), command=testZoffset)

        global check_clean_var
        # check_clean_var = "on"
        self.check_clean_var = StringVar(value="on")
        self.checkboxClean = CTkCheckBox(self, text="Clean", command=self.checkbox_clean_event,
                                    variable=self.check_clean_var, onvalue="on", offvalue="off")
        check_clean_var = self.check_clean_var.get()

        global check_afterdrop_var
        self.check_afterdrop_var = StringVar(value="on")
        self.checkboxAfterdrop = CTkCheckBox(self, text="Afterdrop", command=self.checkbox_afterdrop_event,
                                         variable=self.check_afterdrop_var, onvalue="on", offvalue="off")
        check_afterdrop_var = self.check_afterdrop_var.get()

        # placing widgets
        self.drawingLabel.grid(row=0, column=0, columnspan=2, sticky="nswe", padx=10, pady=10)
        self.layersLabel.grid(row=1, column=0, sticky="nswe", padx=10, pady=10)
        self.layersBox.grid(row=1, column=1, padx=10, pady=10)
        self.orientationBox.grid(row=1, column=2, padx=10, pady=10)
        self.speedLabel.grid(row=5, column=0, sticky="nswe", padx=10, pady=10)
        self.speedSlider.grid(row=5, column=1, columnspan=3, sticky="nswe", padx=10, pady=15)
        self.speed_varLabel.grid(row=5, column=4, sticky="nswe", padx=10, pady=10)
        self.mmperminLabel.grid(row=5, column=5, sticky="w", padx=10, pady=10)
        self.stepLabel.grid(row=4, column=0, sticky="nswe", padx=10, pady=10)
        self.stepEntry.grid(row=4, column=1, sticky="nswe", padx=10, pady=10)
        self.mmLabel1.grid(row=4, column=2, sticky="w", padx=10, pady=10)
        self.amountLabel.grid(row=2, column=0, sticky="nswe", pady=10)
        amountEntry.grid(row=2, column=1, sticky="nswe", padx=10, pady=10)
        self.unitsLabel.grid(row=2, column=2, sticky="w", padx=10, pady=10)
        self.zhopLabel.grid(row=6, column=0, sticky="nswe", padx=10, pady=10)
        zhopEntry.grid(row=6, column=1, sticky="nswe", padx=10, pady=10)
        self.mmLabel3.grid(row=6, column=2, sticky="w", padx=10, pady=10)
        self.pauseLabel.grid(row=7, column=0, sticky="nswe", padx=10, pady=10)
        pauseEntry.grid(row=7, column=1, sticky="nswe", padx=10, pady=10)
        self.timeLabel.grid(row=7, column=2, sticky="w", padx=10, pady=10)
        self.drawing9.grid(row=1, column=5, rowspan=3)
        self.drawing6.grid(row=1, column=4, rowspan=3)
        self.drawing3.grid(row=1, column=3, rowspan=3)
        self.nextButton.place(relx=0.95, rely=0.95, anchor='se', relwidth=0.15, relheight=0.08)
        self.zoffsetLabel.grid(row=3, column=0, sticky="nswe", padx=10, pady=10)
        self.zoffsetEntry.grid(row=3, column=1, sticky="nswe", padx=10, pady=10)
        self.mmLabel5.grid(row=3, column=2, sticky="w", padx=10, pady=10)
        self.testButton.grid(row=3, column=3, sticky="nsw", padx=10, pady=10, columnspan=2)

        self.checkboxClean.grid(row=8, column=0, sticky="nsw")
        self.checkboxAfterdrop.grid(row=8, column=1, sticky="nsw")

    def checkbox_clean_event(self):
        global check_clean_var
        check_clean_var = self.check_clean_var.get()
        print(self.check_clean_var.get())

    def checkbox_afterdrop_event(self):
        global check_afterdrop_var
        check_afterdrop_var = self.check_afterdrop_var.get()
        print(self.check_afterdrop_var.get())

    def nextTab(self):
        # Get the parent of this frame, which should be the MyTabView instance
        # Select the "Syringe" tab
        self.master.master.set('Syringe')


class MoveWindow(CTkToplevel):
    def __init__(self):
        super().__init__()
        self.title("Setup Window")
        self.geometry("700x300")
        self.attributes('-topmost', 1)
        # create buttons to move in x and y axis
        upButton = CTkButton(self, text="↑", font=("Arial", 30))
        downButton = CTkButton(self, text="↓", font=("Arial", 30))
        leftButton = CTkButton(self, text="←", font=("Arial", 30))
        rightButton = CTkButton(self, text="→", font=("Arial", 30))

        # create labels for each axis
        xyLabel = CTkLabel(self, text="XY", font=("Arial", 30))
        zLabel = CTkLabel(self, text="Z", font=("Arial", 30))

        # create button to go up and down on z axis
        upZButton = CTkButton(self, text="↑", font=("Arial", 30))
        downZButton = CTkButton(self, text="↓", font=("Arial", 30))

        self.columnconfigure((0, 1, 2, 3, 4), weight=1, uniform='a')
        self.rowconfigure((0, 1, 2), weight=1, uniform='a')

        # place buttons to the left of the window
        upButton.grid(row=0, column=1, sticky="nsew", padx=20, pady=10)
        downButton.grid(row=2, column=1, sticky="nsew", padx=20, pady=10)
        leftButton.grid(row=1, column=0, sticky="nsew", padx=20, pady=10)
        rightButton.grid(row=1, column=2, sticky="nsew", padx=20, pady=10)
        xyLabel.grid(row=1, column=1, sticky="nsew", padx=20, pady=10)

        # place z axis buttons to the right of the rest
        upZButton.grid(row=0, column=3, sticky="nsew", padx=20, pady=10)
        downZButton.grid(row=2, column=3, sticky="nsew", padx=20, pady=10)
        zLabel.grid(row=1, column=3, sticky="nsew", padx=20, pady=10)


class IncrementDecrementEntry(CTkFrame):
    def __init__(self, master, variable):
        super().__init__(master, fg_color='transparent')

        self.var = variable
        # Create the decrement button
        self.decrement_button = CTkButton(self, text="-", command=self.decrement_value, corner_radius=0,
                                          fg_color='#939ba2', text_color='black')

        # Create the entry
        self.entry = CTkEntry(self, textvariable=self.var, width=5, font=('Arial', 17))

        # Create the increment button
        self.increment_button = CTkButton(self, text="+", command=self.increment_value, corner_radius=0,
                                          fg_color='#939ba2', text_color='black')

        # Place the widgets
        self.rowconfigure((0, 1), weight=1, uniform='a')
        self.columnconfigure((0, 1, 2, 3), weight=1, uniform='a')
        self.entry.grid(row=0, column=0, rowspan=2, sticky="nswe", columnspan=2)
        self.decrement_button.grid(row=1, column=2)
        self.increment_button.grid(row=0, column=2)

    def update_value_var(self):
        self.var.set(round(self.var.get(), 1))

    def increment_value(self):
        self.var.set(self.var.get() + 0.1)
        self.update_value_var()

    def decrement_value(self):
        self.var.set(self.var.get() - 0.1)
        if self.var.get() < 0.1:
            self.var.set(0.1)
        self.update_value_var()


class Buttons(CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color='transparent')
        # placed in the bottom to the right
        self.place(relx=0.45, rely=0.8, relwidth=0.6, relheight=0.2)
        # test movement button, Start button and save g-code button
        self.moveButton = CTkButton(self, text="Movement test", font=("Arial", 20), command=movementTest,
                                    fg_color='grey', hover_color='dark grey', )
        self.startButton = CTkButton(self, text="Do Science!", font=("Arial", 20), fg_color='green',
                                     hover_color='dark green', command=start)
        self.saveGCodeButton = CTkButton(self, text="Save G-Code", font=("Arial", 20),
                                         command=save_gcode_commands_to_file)

        # placing buttons side to side using pack
        self.moveButton.pack(side="left", fill='both', expand=True, padx=5)
        self.saveGCodeButton.pack(side="left", fill='both', expand=True, padx=5)
        self.startButton.pack(side="left", fill='both', expand=True, padx=5)


class ConnectFrame(CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color='transparent')
        self.pack(fill='both', expand=True)
        self.rowconfigure((0, 1, 2, 3, 4), weight=1, uniform='a')
        self.columnconfigure((0, 1, 2, 3), weight=1, uniform='a')

        # creating widgets
        self.connectLabel = CTkLabel(self, text="Connection", font=("Arial", 30))
        self.connectButton = CTkButton(self, text="Connect", font=("Arial", 20), fg_color='green',
                                       hover_color='dark green', command=self.connect)
        self.disconnectButton = CTkButton(self, text="Disconnect", font=("Arial", 20), fg_color='red',
                                          hover_color='dark red', command=self.disconnect, state='disabled')
        self.connectionState = CTkLabel(self, text="Disconnected", font=("Arial", 30), text_color='red')
        self.buttons = Buttons(self)
        self.backButton = CTkButton(self, text="Back", font=("Arial", 20), command=self.backTab, fg_color='grey',
                                    hover_color='dark grey')
        self.infoButton = CTkButton(self, text="Info", font=("Arial", 20), command=infoMessage, fg_color='grey',
                                    hover_color='dark grey')

        # placing widgets
        self.connectLabel.grid(row=0, column=0, columnspan=2, sticky="nswe", padx=10, pady=10)
        self.connectButton.grid(row=1, column=0, sticky="nswe", padx=10, pady=10)
        self.disconnectButton.grid(row=1, column=1, sticky="nswe", padx=10, pady=10)
        self.buttons.grid(row=4, column=0, columnspan=3, sticky="nswe", padx=10, pady=10)
        self.connectionState.grid(row=1, column=2, sticky="nswe", padx=10, pady=10, columnspan=2)
        self.backButton.place(relx=0.95, rely=0.95, anchor='se', relwidth=0.15, relheight=0.08)
        self.infoButton.place(relx=0.95, rely=0.05, anchor='ne', relwidth=0.15, relheight=0.08)

    def backTab(self):
        # Get the parent of this frame, which should be the MyTabView instance
        # Select the "Syringe" tab
        self.master.master.set('Syringe')

    def connect(self):
        if connect():
            self.connectionState.configure(text="Connected", text_color='green')
            self.connectButton.configure(state='disabled')
            self.disconnectButton.configure(state='normal')
            print('Connected to the printer')
            logTextVar.set(logTextVar.get() + '\n' + 'Connected to the printer')
            #time.sleep(0.5)
            # send_gcode('G28')
            command("G28")
            print('Homed the printer')

            command("M203 Z15")  # Speed Up the Z
            # send_gcode('M300 S440 P200')
        else:
            messagebox.showerror("Error", "Could not connect to the printer")

    def disconnect(self):
        if disconnect():
            self.connectionState.configure(text="Disconnected", text_color='red')
            self.connectButton.configure(state='normal')
            self.disconnectButton.configure(state='disabled')
            print('Disconnected from the printer')
            logTextVar.set(logTextVar.get() + '\n' + 'Disconnected from the printer')
        else:
            messagebox.showerror("Error", "Could not disconnect from the printer")


class Drawing3(CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color='transparent')
        # create nine grey circles, with a black border, three of them in each row
        # it will be in a button, so it can't be too big
        # before making the circles, make a rectangle with blue border to highlight the first three buttons
        canvas = CTkCanvas(self, width=95, height=95)
        canvas.create_rectangle(5, 65, 95, 95, outline="blue", width=2)
        canvas.create_rectangle(5, 5, 35, 95, outline="red", width=2)
        # create the circles
        for i in range(3):
            canvas.create_oval(10 + 30 * i, 10, 30 + 30 * i, 30, fill="grey", outline="black")
            canvas.create_oval(10 + 30 * i, 40, 30 + 30 * i, 60, fill="grey", outline="black")
            canvas.create_oval(10 + 30 * i, 70, 30 + 30 * i, 90, fill="grey", outline="black")

        buttonFrame = CTkFrame(self, fg_color='transparent')
        radio = CTkRadioButton(buttonFrame, value=3, text='', variable=cups_var)
        radio.place(relx=0.42, rely=0, anchor='nw')
        canvas.pack(side='top')
        buttonFrame.pack(side='top')


class Drawing6(CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color='transparent')
        # create nine grey circles, with a black border, three of them in each row
        # it will be in a button, so it can't be too big
        # before making the circles, make a rectangle with blue border to highlight the first three buttons
        canvas = CTkCanvas(self, width=95, height=95)
        canvas.create_rectangle(5, 35, 95, 95, outline="blue", width=2)
        canvas.create_rectangle(5, 5, 65, 95, outline="red", width=2)
        # create the circles
        for i in range(3):
            canvas.create_oval(10 + 30 * i, 10, 30 + 30 * i, 30, fill="grey", outline="black")
            canvas.create_oval(10 + 30 * i, 40, 30 + 30 * i, 60, fill="grey", outline="black")
            canvas.create_oval(10 + 30 * i, 70, 30 + 30 * i, 90, fill="grey", outline="black")

        buttonFrame = CTkFrame(self, fg_color='transparent')
        radio = CTkRadioButton(buttonFrame, value=6, text='', variable=cups_var)
        radio.place(relx=0.42, rely=0, anchor='nw')
        canvas.pack(side='top')
        buttonFrame.pack(side='top')


class Drawing9(CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color='transparent')
        # create nine grey circles, with a black border, three of them in each row
        # it will be in a button, so it can't be too big
        # before making the circles, make a rectangle with blue border to highlight the first three buttons
        canvas = CTkCanvas(self, width=95, height=95)
        canvas.create_rectangle(5, 5, 95, 95, outline="blue", width=2)
        # create the circles
        for i in range(3):
            canvas.create_oval(10 + 30 * i, 10, 30 + 30 * i, 30, fill="grey", outline="black")
            canvas.create_oval(10 + 30 * i, 40, 30 + 30 * i, 60, fill="grey", outline="black")
            canvas.create_oval(10 + 30 * i, 70, 30 + 30 * i, 90, fill="grey", outline="black")

        buttonFrame = CTkFrame(self, fg_color='transparent')
        radio = CTkRadioButton(buttonFrame, value=9, text='', variable=cups_var)
        radio.place(relx=0.42, rely=0, anchor='nw')
        canvas.pack(side='top')
        buttonFrame.pack(side='top')


class LogFrame(CTkScrollableFrame):
    def __init__(self, master):
        super().__init__(master, fg_color='white')
        self.pack(fill='both', expand=True)
        self.logText = CTkLabel(self, textvariable=logTextVar, font=("Arial", 15), anchor='w', justify='left')
        self.logText.pack(fill='both', expand=True)


class ProgressWindow(CTkToplevel):
    def __init__(self):
        super().__init__()
        self.title("Progress")
        self.geometry("500x150")
        self.attributes('-topmost', 1)
        self.rowconfigure((0, 1), weight=1, uniform='a')
        self.columnconfigure((0, 1), weight=1, uniform='a')
        global total_lines
        global percentage
        global current_line
        global percentage_str
        if cups_var.get() == 9:
            total_lines = layers_var.get() * round(81 / step_var.get())
        if cups_var.get() == 6:
            total_lines = layers_var.get() * round(55 / step_var.get())
        if cups_var.get() == 3:
            total_lines = layers_var.get() * round(27 / step_var.get())
        if orientation_var.get() == 'Both':
            total_lines *= 2
        current_line = tk.IntVar(value=0)
        percentage = tk.DoubleVar(value=current_line.get() / total_lines)
        # percentage label
        percentage_str = tk.StringVar(value='0%')
        self.percentageLabel = CTkLabel(self, textvariable=percentage_str)
        self.progress = CTkProgressBar(self, width=200, height=30, variable=percentage)
        self.abortButton = CTkButton(self, text="Abort", font=("Arial", 20), fg_color='red', hover_color='dark red',
                                     command=self.abort)

        # placing
        self.progress.grid(row=0, column=0, columnspan=2, sticky='nswe', padx=10, pady=25)
        self.abortButton.grid(row=1, column=1, sticky='se', padx=10, pady=10)
        self.percentageLabel.grid(row=1, column=0, sticky='sw', padx=10, pady=10)

    def abort(self):
        global abort
        abort = True
        self.progress.stop()
        self.destroy()
        logTextVar.set(logTextVar.get() + '\n' + 'Aborted')


class SummaryFrame(CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color='transparent')
        self.pack(fill='both', expand=True)

        self.nextButton = CTkButton(self, text="Next", font=("Arial", 20), command=self.nextTab)
        self.backButton = CTkButton(self, text="Back", font=("Arial", 20), command=self.backTab, fg_color='grey',
                                    hover_color='dark grey')
        # button to update the values of the summary
        self.updateButton = CTkButton(self, text="Update", font=("Arial", 20), command=self.updateSummary)
        # create labels to show the summary of the project, with the parameters set by the user
        self.summaryLabel = CTkLabel(self, text="Summary", font=("Arial", 30))
        self.layersLabel = CTkLabel(self, text="Layers: " + str(layers_var.get()), font=("Arial", 20), justify='left')
        self.orientationLabel = CTkLabel(self, text="Orientation: " + orientation_var.get(), font=("Arial", 20),
                                         justify='left')
        self.cupsLabel = CTkLabel(self, text="Cups: " + str(cups_var.get()), font=("Arial", 20))
        self.speedLabel = CTkLabel(self, text="Speed: " + str(speed_var.get()) + ' mm/min', font=("Arial", 20))
        self.stepLabel = CTkLabel(self, text="Step: " + str(step_var.get()) + ' mm', font=("Arial", 20))
        self.amountLabel = CTkLabel(self, text="Droplet Amount: " + amountEntry.get(), font=("Arial", 20))
        self.zhopLabel = CTkLabel(self, text="Z-Hop: " + zhopEntry.get() + ' mm', font=("Arial", 20))
        self.pauseLabel = CTkLabel(self, text="Pause: " + pauseEntry.get() + ' s', font=("Arial", 20))
        self.savePDF = CTkButton(self, text="Save PDF", font=("Arial", 20), command=self.savePDF)
        self.saveButton = CTkButton(self, text='Save Project', font=("Arial", 20), command=self.saveProject)
        self.loadButton = CTkButton(self, text="Load", font=("Arial", 20), command=master.master.master.loadProject,
                                    fg_color='grey', hover_color='dark grey')
        self.zOffsetLabel = CTkLabel(self, text="Z-Offset: " + str(zoffset.get()) + ' mm', font=("Arial", 20))
        # calculate the total lines
        global total_lines
        if cups_var.get() == 9:
            total_lines = layers_var.get() * round(81 / step_var.get())
        if cups_var.get() == 6:
            total_lines = layers_var.get() * round(55 / step_var.get())
        if cups_var.get() == 3:
            total_lines = layers_var.get() * round(27 / step_var.get())
        if orientation_var.get() == 'Both':
            total_lines *= 2
        self.fibersLabel = CTkLabel(self, text="Total fibers: " + str(total_lines), font=("Arial", 20))
        amount_necessary = int(total_lines) * float(amountValue.get())
        self.amountNecessary = CTkLabel(self, text=f"Amount necessary: {amount_necessary}", font=("Arial", 20))

        self.columnconfigure((0, 1, 2), weight=1, uniform='a')

        # place the widgets
        self.nextButton.place(relx=0.95, rely=0.95, anchor='se', relwidth=0.15, relheight=0.08)
        self.backButton.place(relx=0.8, rely=0.95, anchor='se', relwidth=0.15, relheight=0.08)
        self.summaryLabel.grid(row=0, column=0, sticky="nswe", padx=10, pady=10)
        self.layersLabel.grid(row=1, column=0, sticky="nswe", padx=10, pady=10)
        self.updateButton.place(relx=0.95, rely=0.05, anchor='ne', relwidth=0.15, relheight=0.08)
        self.orientationLabel.grid(row=2, column=0, sticky="nswe", padx=10, pady=10)
        self.cupsLabel.grid(row=3, column=0, sticky="nswe", padx=10, pady=10)
        self.speedLabel.grid(row=7, column=0, sticky="nswe", padx=10, pady=10)
        self.stepLabel.grid(row=5, column=0, sticky="nswe", padx=10, pady=10)
        self.amountLabel.grid(row=4, column=0, sticky="nswe", padx=10, pady=10)
        self.zhopLabel.grid(row=6, column=0, sticky="nswe", padx=10, pady=10)
        self.pauseLabel.grid(row=8, column=0, sticky="nswe", padx=10, pady=10)
        self.zOffsetLabel.grid(row=9, column=0, sticky="nswe", padx=10, pady=10)
        self.fibersLabel.grid(row=10, column=0, sticky="nswe", padx=10, pady=10)
        self.amountNecessary.grid(row=1, column=1, sticky="nswe", padx=10, pady=10)

        # place buttons to the right
        self.saveButton.grid(row=2, column=2, sticky='nswe', padx=38, pady=10, rowspan=2)
        self.savePDF.grid(row=4, column=2, sticky='nswe', padx=38, pady=10, rowspan=2)
        self.loadButton.grid(row=6, column=2, sticky='nswe', padx=38, pady=10, rowspan=2)

    def nextTab(self):
        # Get the parent of this frame, which should be the MyTabView instance
        # Select the "Connection" tab
        self.master.master.set('Connection')

    def backTab(self):
        # Get the parent of this frame, which should be the MyTabView instance
        # Select the "Draw" tab
        self.master.master.set('Syringe')

    def updateSummary(self):
        self.layersLabel.configure(text="Layers: " + str(layers_var.get()))
        self.orientationLabel.configure(text="Orientation: " + orientation_var.get())
        self.cupsLabel.configure(text="Cups: " + str(cups_var.get()))
        self.speedLabel.configure(text="Speed: " + str(speed_var.get()) + ' mm/min')
        self.stepLabel.configure(text="Step: " + str(step_var.get()) + ' mm')
        self.amountLabel.configure(text="Droplet Amount: " + amountEntry.get())
        self.zhopLabel.configure(text="Z-Hop: " + zhopEntry.get() + ' mm')
        self.pauseLabel.configure(text="Pause: " + pauseEntry.get() + ' s')
        self.zOffsetLabel.configure(text="Z-Offset: " + str(zoffset.get()) + ' mm')
        if cups_var.get() == 9:
            total_lines = layers_var.get() * round(81 / step_var.get())
        if cups_var.get() == 6:
            total_lines = layers_var.get() * round(55 / step_var.get())
        if cups_var.get() == 3:
            total_lines = layers_var.get() * round(27 / step_var.get())
        if orientation_var.get() == 'Both':
            total_lines *= 2
        self.fibersLabel.configure(text="Total fibers: " + str(total_lines))
        amount_necessary = int(total_lines) * float(amountValue.get())
        self.amountNecessary.configure(text=f"Amount necessary: {amount_necessary}")
        self.update_idletasks()

    def saveProject(self):
        summary_dict = {
            "Layers": layers_var.get(),
            "Orientation": orientation_var.get(),
            "Cups": cups_var.get(),
            "Speed": speed_var.get(),
            "Step": step_var.get(),
            "Droplet Amount": amountEntry.get(),
            "Z-Hop": zhopEntry.get(),
            "Pause": pauseEntry.get(),
            "Z-Offset": zoffset.get()
        }

        # Open a save file dialog
        file_path = fd.asksaveasfilename(defaultextension=".json", filetypes=[("JSON files", "*.json")])

        # If a file path was selected
        if file_path:
            # Write the dictionary to the selected .json file
            with open(file_path, 'w') as f:
                json.dump(summary_dict, f)
        print('project saved')
        # write into the log that the project was saved
        logTextVar.set(logTextVar.get() + '\n' + 'Project saved')
        project_name = os.path.basename(file_path).split('.')[0]

        # Change the window title to the project name
        self.master.master.master.title('Nanofiber Machine - ' + project_name)

    def savePDF(self):
        summary_dict = {
            "Layers": str(layers_var.get()),
            "Orientation": orientation_var.get(),
            "Cups": str(cups_var.get()),
            "Droplet Amount": amountEntry.get() + " units",
            "Step": str(step_var.get()) + " mm",
            "Z-Hop": zhopEntry.get() + " mm",
            "Speed": str(speed_var.get()) + " mm/min",
            "Pause": pauseEntry.get() + " s",
            "Z-Offset": str(zoffset.get()) + " mm",
            'Fibers': str(total_lines) + ' fibers'
        }
        now = datetime.now()

        # Format the date and time as a string
        project_name = self.master.master.master.title().split('-')[1].strip()
        print(project_name)
        date_time = now.strftime("%Y-%m-%d %H:%M:%S")
        # Open a save file dialog
        file_path = fd.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF files", "*.pdf")])

        # If a file path was selected
        if file_path:
            # Create a new PDF with Reportlab
            c = canvas.Canvas(file_path)

            # Add the title
            c.setFont("Helvetica-Bold", 24)
            c.drawString(20, 800, "Project Summary")
            c.drawString(20, 760, project_name)
            c.setFont("Helvetica", 14)
            c.drawString(20, 740, f"Date: {date_time}")

            # Add the summary data
            c.setFont("Helvetica", 14)
            for i, (key, value) in enumerate(summary_dict.items()):
                text = f"{key}: {value}"
                c.drawString(20, 700 - (i * 30), text)

            # Save the PDF
            c.save()

            print('PDF saved')
            logTextVar.set(logTextVar.get() + '\n' + 'PDF saved')

def command(command):

    if ser is not None:
        command = command + ' \r\n'
        ser.write(str.encode(command))

        while True:
            line = ser.readline()
            print(line.decode('utf-8').strip())
            if line == b'ok\n':
                break

def homeSyringe():
    global ser, current_amount

    def check_syringe(ser, command):
        if ser is None:
            messagebox.showerror("Connection error", "Connect to printer first!")
        else:
            command = command + '\r\n'
            ser.write(str.encode(command))
            time.sleep(0.1)

            while True:
                line = ser.readline()
                print(line)

                if line == b'filament: open\n':
                    print('trigger reached!')
                    return 'empty'
                if line == b'filament: TRIGGERED\n':
                    return 'full'

    command("M302 P1")  # cold extrusion
    command("M302")  # cold extrusion status
    # command("G28")

    # status = check_syringe(ser, "M119")
    # if status == 'empty':
    #     command("G1 E+20 F300 ")  # E+ - goes down
    #     time.sleep(0.1)

    #
    # Delam tady zmeny a vubec neni vliv ! Kontrola nutna
    #
    status = check_syringe(ser, "M119")
    command("G91 E0")
    while status == 'full':
        command( "G1 E-0.5 F300")  # E+ - goes down
        # send_gcode('G4 P10')
        status = check_syringe(ser, "M119")
        if status == 'empty':
            # print('syringe homed')
            command( "G92 E0")
            current_amount.set(0)
    # set this point as the zero point
    command( "G92 E0 ")
    command( "G90")


def infoMessage():
    messagebox.showinfo("Application info",
                        "Autor:\n      Ing. Andrii Shynkarenko\n      Department of Manufacturing Systems and Automation\n      Technical University of Liberec\n\n"
                        "In case of breakdown, contact:\n      andrii.shynkarenko@tul.cz\n      +420 48535 3355")


def movementTest():
    print("Movement Test")
    logTextVar.set(logTextVar.get() + '\n' + 'Movement test')


def layersBoxSelection(event):
    print(layers_var.get())


def savePDF():
    summary_dict = {
        "Layers": str(layers_var.get()),
        "Orientation": orientation_var.get(),
        "Cups": str(cups_var.get()),
        "Droplet Amount": amountEntry.get() + " units",
        "Step": str(step_var.get()) + " mm",
        "Z-Hop": zhopEntry.get() + " mm",
        "Speed": str(speed_var.get()) + " mm/min",
        "Pause": pauseEntry.get() + " s",
        "Z-Offset": str(zoffset.get()) + " mm"
    }
    now = datetime.now()

    # Format the date and time as a string
    date_time = now.strftime("%Y-%m-%d %H:%M:%S")
    # Open a save file dialog
    file_path = fd.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF files", "*.pdf")])

    # If a file path was selected
    if file_path:
        # Create a new PDF with Reportlab
        c = canvas.Canvas(file_path)

        # Add the title
        c.setFont("Helvetica-Bold", 24)
        c.drawString(20, 800, "Project Summary")
        c.setFont("Helvetica", 14)
        c.drawString(20, 740, f"Date: {date_time}")

        # Add the summary data
        c.setFont("Helvetica", 14)
        for i, (key, value) in enumerate(summary_dict.items()):
            text = f"{key}: {value}"
            c.drawString(20, 700 - (i * 30), text)

        # Save the PDF
        c.save()

        print('PDF saved')
        logTextVar.set(logTextVar.get() + '\n' + 'PDF saved')


def testZoffset():
    # homes the printer and then moves the z axis to the z offset
    # if the printer is not connected, it will connect to it
    if ser is None:
        messagebox.showerror("Connection error", "Connect to printer first!")
    if ser is not None:
        command("G28")
        send_gcode('G90')  # go absolut
        # send_gcode(f'G1 Z20 F{str(speed_var.get())}')
        # send_gcode(f'G1 X10 Y10 Z20 F{str(speed_var.get())}')
        send_gcode(f'G1 X5 Y10 Z3 F{str(speed_var.get())}')
        for repetiton in range(3):
            send_gcode(f'G1 X5 Y10 Z0 F500')
            send_gcode(f'G1 X10 Y10 Z0 F500')
            send_gcode(f'G1 X10 Y15 Z0 F500')
            send_gcode(f'G1 X5 Y15 Z0 F500')
            send_gcode(f'G1 X5 Y10 Z0 F500')
            time.sleep(1)
            send_gcode(f'G1 X5 Y10 Z{str(zoffset.get())} F500')
            send_gcode(f'G1 X10 Y10 Z{str(zoffset.get())} F500')
            send_gcode(f'G1 X10 Y15 Z{str(zoffset.get())} F500')
            send_gcode(f'G1 X5 Y15 Z{str(zoffset.get())} F500')
            send_gcode(f'G1 X5 Y10 Z{str(zoffset.get())} F500')
            time.sleep(1)
        # for repetiton in range(3):
        #     send_gcode(f'G1 X10 Y10 Z{str(zoffset.get())} F{str(speed_var.get())}')
        #     time.sleep(1)
        #     send_gcode(f'G1 X10 Y10 Z0 F{str(speed_var.get())}')
        print("Test Z-Offset")
        logTextVar.set(logTextVar.get() + '\n' + 'Test Z-Offset')
    print("Test Z-Offset")
    logTextVar.set(logTextVar.get() + '\n' + 'Test Z-Offset')


def find_3d_printer_port(baudrate=115200):
    ports = list_ports.comports()
    for port in ports:
        try:
            ser = serial.Serial(port.device, baudrate)
            # You might want to write some printer-specific command and check the response
            # to make sure you're communicating with the 3D printer and not some other device.
            ser.close()
            return port.device
        except serial.SerialException:
            pass
    return None


def connect():
    global ser
    port = find_3d_printer_port()
    try:
        ser = serial.Serial(port, 115200)
        time.sleep(2)  # Give the connection a second to settle
        print('Connected')
        return True
    except Exception as e:
        print('Failed to connect to the printer')
        print('Error:', str(e))  # Print the error message
        return False


def disconnect():
    global ser
    # Close the connection
    try:
        if ser is not None:
            command("M18")
            time.sleep(1)
            ser.close()
            ser = None
            return True
    except Exception as e:
        print('Failed to disconnect from the printer')
        print('Error:', str(e))  # Print the error message
        return False


def start():
    # Create the progress window
    progress_window = ProgressWindow()

    # Start the G-code execution in a separate thread
    thread = threading.Thread(target=send_gcode_commands)
    thread.start()


def send_gcode(command):
    ser.write((command + '\n').encode())
    while True:
        response = ser.readline().decode().strip()
        print(response)
        if response == 'ok':
            break
        elif 'error' in response.lower():
            print(f"Error: {response}")
            break
        else:
            print(f"Received: {response}")

# def send_gcode(command):
#     max_retries = 3
#     for retry in range(max_retries):
#         ser.write((command + '\n').encode('utf-8'))
#         response = ""
#         timeout = time.time() + 5  # Set a timeout of 5 seconds
#         time.sleep(0.1)
#         while time.time() < timeout:
#             temp = ser.readline().decode().strip()
#             if temp != "":
#                 response += temp
#                 if response.endswith("ok"):
#                     return response
#                 elif response.startswith("Error"):
#                     raise Exception(f"Printer error: {response}")
#         print(f"Retrying command ({retry + 1}/{max_retries}): {command}")
#     raise Exception(f"Failed to execute command after {max_retries} retries: {command}")


def send_gcode_commands():
    # create another window with progress bar and abort button

    adjust_different_layers = 3  # distance between the start of each layer

    global ser, abort, current_line, total_lines, percentage, current_amount
    abort = False

    # def command(command):
    #     start_time = datetime.now()
    #     ser.write(str.encode(command))
    #
    #     while True:
    #         line = ser.readline()
    #
    #         if line == b'ok\n':
    #             break

    def check_syringe(ser, command):
        if ser is None:
            messagebox.showerror("Connection error", "Connect to printer first!")
        else:
            command = command + '\r\n'
            ser.write(str.encode(command))
            time.sleep(0.1)

            while True:
                line = ser.readline()
                print(line)

                if line == b'filament: open\n':
                    print('trigger reached!')
                    return 'empty'
                if line == b'filament: TRIGGERED\n':
                    return 'full'

    if ser is not None:

        # Send the G-code commands
        # Define the G-code commands
        send_gcode('M220 S100')  # reset feedrate
        send_gcode('M302 S0')  # enable cold extrusion
        send_gcode('M221 S100')  # reset flowrate
        send_gcode('G90')  # use absolute coordinates
        send_gcode('M82')  # absolute extrusion mode
        # send_gcode('G28') # home all axes
        send_gcode('G1 Z2 F1500')  # raise z
        send_gcode('G92 E0')  # reset syringe
        # Add more G-code commands as needed

        if cups_var.get() == 9:
            limit_y = 172  # limit for the y position if there are 9 cups
            limit_x = 117  # limit for the x position if there are 9 cups
        elif cups_var.get() == 6:
            limit_y = 145  # limit for the y position if there are 6 cups
            limit_x = 91  # limit for the x position if there are 6 cups
        elif cups_var.get() == 3:
            limit_y = 117  # limit for the y position if there are 3 cups
            limit_x = 63  # limit for the x position if there are 3 cups

        delay_after_extrusion = 5

        if orientation_var.get() == 'Horizontal':
            x1 = 25.5  # first x position
            x2 = 128  # second x position
            x22 = 25.5
            x3 = 128  # third x position
            for _ in range(layers_var.get()):
                y = 90  # y start position
                lines = round(82.5 / (step_var.get() / 2))
                print(f'Number of fibers: {lines}')
                send_gcode('G90')
                send_gcode(f'G1 Z7 F{str(speed_var.get())}')  # taxi height ?
                for _ in range(lines):
                    if y < limit_y:
                        send_gcode('G90')
                        send_gcode(f'G1 X{str(x1)} Y{str(y)} F{str(speed_var.get())}')   # First position BUT High
                        send_gcode(f'G1 Z{str(zoffset.get())} F{str(speed_var.get())}')  # Go to first position with Z-Offset

                        # status = check_syringe(ser, "M119")
                        # if status == 'empty':
                        #     print('syringe empty')
                        #     break

                        ###### EXTRUSION

                        send_gcode('G91')
                        send_gcode(f'G1 E-{amountEntry.get()} F200')  # extrusion with speed 200
                        current_amount.set(current_amount.get() - float(amountEntry.get()))
                        send_gcode('G4 P1000')  # sleep after extrusion
                        send_gcode('G90')
                        send_gcode(f'G1 Z{zhopEntry.get()} F{str(speed_var.get())}')  # go up with extruder Z-Hop parametr
                        if pauseEntry.get() != '0':
                            send_gcode(f'G4 P{pauseEntry.get()}')  # wait if needed PAUSE
                        send_gcode(f'G1 X{str(x2)}')
                        send_gcode(f'G1 X{str(x3)} Z{str(zoffset.get())} F{str(speed_var.get())}')  # last point but on offset height
                        # afterdrop if needed
                        if check_afterdrop_var == 'on':
                            send_gcode('G91')
                            send_gcode(f'G1 E-{amountEntry.get()} F200')  # extrusion with speed 200
                            current_amount.set(current_amount.get() - float(amountEntry.get()))
                            send_gcode('G4 P500')
                            send_gcode('G90')
                            send_gcode(f'G1 F{str(speed_var.get())}')
                        # cleaning process
                        if check_clean_var == 'on':
                            send_gcode(f'G1 X{str(x3 + 5)} Z0 F{str(speed_var.get())}')
                            send_gcode(f'G1 X{str(x3 + 10)} F{str(speed_var.get())}')
                            send_gcode(f'G1 Z3 F{str(speed_var.get())}')  # go up to travel movement
                        else:
                            send_gcode(f'G1 Z{str(zoffset.get())}')  # go up to Z{str(zoffset.get())}

                        # update the progress bar
                        current_line.set(current_line.get() + 1)
                        percentage.set(current_line.get() / total_lines)
                        percentage_str.set(f"{percentage.get() * 100:.1f}%")
                        if abort:
                            break
                        y = round(y + step_var.get(), 2)
                        send_gcode(f'G1 X{str(x3)} Y{str(y)} Z{str(zoffset.get())}')
                        # status = check_syringe(ser, "M119")
                        # if status == 'empty':
                        #     print('syringe empty')
                        #     break
                        send_gcode('G91')
                        send_gcode(f'G1 E-{amountEntry.get()} F200')
                        current_amount.set(current_amount.get() - float(amountEntry.get()) )
                        send_gcode('G4 P1000')
                        send_gcode('G90')
                        send_gcode(f'G1 Z{zhopEntry.get()} F{str(speed_var.get())}')
                        if pauseEntry.get() != '0':
                            send_gcode(f'G4 P{pauseEntry.get()}')

                        send_gcode(f'G1 X{str(x22)} F{str(speed_var.get())}')
                        send_gcode(f'G1 Z{str(zoffset.get())} X{str(x1)} F{str(speed_var.get())}')
                        if check_afterdrop_var == 'on':
                            send_gcode('G91')
                            send_gcode(f'G1 E-{amountEntry.get()} F200')  # extrusion with speed 200
                            current_amount.set(current_amount.get() - float(amountEntry.get()))
                            send_gcode('G4 P500')
                            send_gcode('G90')
                            send_gcode(f'G1 F{str(speed_var.get())}')
                        if check_clean_var == 'on':
                            send_gcode(f'G1 X{str(x1 - 5)} Z0 F{str(speed_var.get())}')
                            send_gcode(f'G1 X{str(x1 - 10)} F{str(speed_var.get())}')
                            send_gcode(f'G1 Z3 F{str(speed_var.get())}')  # go up to travel movement
                        else:
                            send_gcode(f'G1 Z{str(zoffset.get())}')  # go up to Z{str(zoffset.get())}

                        y = round(y + step_var.get(), 2)
                        # print('going to sleep for 4 seconds')
                        # time.sleep(4)
                        send_gcode('M400')
                        # update the progress bar
                        current_line.set(current_line.get() + 1)
                        percentage.set(current_line.get() / total_lines)
                        percentage_str.set(f"{percentage.get() * 100:.1f}%")
                        if abort:
                            break
                x1 -= adjust_different_layers  # adjust the x position for the next layer
                x3 += adjust_different_layers  # adjust the x position for the next layer

        if orientation_var.get() == 'Vertical':
            y1 = 79  # first y position
            y2 = 181.5  # second y position
            y22 = 79
            y3 = 181.5  # third y position
            lines = round(82.5 / (step_var.get() / 2))
            for _ in range(layers_var.get()):
                x = 36  # x start position
                send_gcode('G90')
                send_gcode(f'G1 Z7 F{str(speed_var.get())}')
                for _ in range(lines):
                    if x < limit_x:
                        send_gcode('G90')
                        send_gcode(f'G1 X{str(x)} Y{str(y1)} F{str(speed_var.get())}')
                        send_gcode(f'G1 Z{str(zoffset.get())} F{str(speed_var.get())}')
                        # status = check_syringe(ser, "M119")
                        # if status == 'empty':
                        #     print('syringe empty')
                        #     break
                        send_gcode('G91')
                        send_gcode(f'G1 E-{amountEntry.get()} F200')
                        current_amount.set(current_amount.get() - float(amountEntry.get()))
                        send_gcode('G4 P1000')
                        send_gcode('G90')
                        send_gcode(f'G1 Z{zhopEntry.get()} F{str(speed_var.get())}')
                        if pauseEntry.get() != '0':
                            send_gcode(f'G4 P{pauseEntry.get()}')
                        send_gcode(f'G1 Y{str(y2)}')
                        send_gcode(f'G1 Z{str(zoffset.get())} Y{str(y3)} F{str(speed_var.get())}')
                        # afterdrop if needed
                        if check_afterdrop_var == 'on':
                            send_gcode('G91')
                            send_gcode(f'G1 E-{amountEntry.get()} F200')  # extrusion with speed 200
                            current_amount.set(current_amount.get() - float(amountEntry.get()))
                            send_gcode('G4 P500')
                            send_gcode('G90')
                            send_gcode(f'G1 F{str(speed_var.get())}')
                        # cleaning process
                        if check_clean_var == 'on':
                            send_gcode(f'G1 Y{str(y3 + 5)} Z0 F{str(speed_var.get())}')
                            send_gcode(f'G1 Y{str(y3 + 10)} F{str(speed_var.get())}')
                            send_gcode(f'G1 Z3 F{str(speed_var.get())}')  # go up to travel movement
                        else:
                            send_gcode(f'G1 Z{str(zoffset.get())}')  # go up to Z{str(zoffset.get())}

                        x = round(x + step_var.get(), 2)
                        # update the progress bar
                        current_line.set(current_line.get() + 1)
                        percentage.set(current_line.get() / total_lines)
                        percentage_str.set(f"{percentage.get() * 100:.1f}%")
                        if abort:
                            break
                        send_gcode(f'G1 X{str(x)} Y{str(y3)} Z{str(zoffset.get())}')
                        # status = check_syringe(ser, "M119")
                        # if status == 'empty':
                        #     print('syringe empty')
                        #     break
                        send_gcode('G91')
                        send_gcode(f'G1 E-{amountEntry.get()} F200')
                        current_amount.set(current_amount.get() - float(amountEntry.get()))
                        send_gcode('G4 P1000')
                        send_gcode('G90')
                        send_gcode(f'G1 Z{zhopEntry.get()} F{str(speed_var.get())}')
                        if pauseEntry.get() != '0':
                            send_gcode(f'G4 P{pauseEntry.get()}')

                        send_gcode(f'G1 Y{str(y22)} F{str(speed_var.get())}')
                        send_gcode(f'G1 Z{str(zoffset.get())} Y{str(y1)} F{str(speed_var.get())}')
                        if check_afterdrop_var == 'on':
                            send_gcode('G91')
                            send_gcode(f'G1 E-{amountEntry.get()} F200')  # extrusion with speed 200
                            current_amount.set(current_amount.get() - float(amountEntry.get()))
                            send_gcode('G4 P500')
                            send_gcode('G90')
                            send_gcode(f'G1 F{str(speed_var.get())}')
                        if check_clean_var == 'on':
                            send_gcode(f'G1 Y{str(y1 - 5)} Z0 F{str(speed_var.get())}')
                            send_gcode(f'G1 Y{str(y1 - 10)} F{str(speed_var.get())}')
                            send_gcode(f'G1 Z3 F{str(speed_var.get())}')  # go up to travel movement
                        else:
                            send_gcode(f'G1 Z{str(zoffset.get())}')  # go up to Z{str(zoffset.get())}

                        # time.sleep(4)
                        x = round(x + step_var.get(), 2)
                        send_gcode('M400')
                        # update the progress bar
                        current_line.set(current_line.get() + 1)
                        percentage.set(current_line.get() / total_lines)
                        percentage_str.set(f"{percentage.get() * 100:.1f}%")
                        if abort:
                            break

                y1 -= adjust_different_layers  # adjust the y position for the next layer
                y3 += adjust_different_layers  # adjust the y position for the next layer

        if orientation_var.get() == 'Both':
            x1 = 25.5  # first x position
            x2 = 128  # second x position
            x22 = 25.5
            x3 = 128  # third x position
            y1 = 79  # first y position
            y2 = 181.5  # second y position
            y22 = 79
            y3 = 181.5  # third y position
            for _ in range(layers_var.get()):
                y = 89
                lines = round(82.5 / (step_var.get() / 2))
                send_gcode('G90')
                send_gcode(f'G1 Z7 F{str(speed_var.get())}')
                for _ in range(lines):
                    if y < limit_y:
                        send_gcode('G90')
                        send_gcode(f'G1 X{str(x1)} Y{str(y)} F{str(speed_var.get())}')  # First position BUT High
                        send_gcode(
                            f'G1 Z{str(zoffset.get())} F{str(speed_var.get())}')  # Go to first position with Z-Offset

                        # status = check_syringe(ser, "M119")
                        # if status == 'empty':
                        #     print('syringe empty')
                        #     break

                        ###### EXTRUSION

                        send_gcode('G91')
                        send_gcode(f'G1 E-{amountEntry.get()} F200')  # extrusion with speed 200
                        current_amount.set(current_amount.get() - float(amountEntry.get()))
                        send_gcode('G4 P1000')  # sleep after extrusion
                        send_gcode('G90')
                        send_gcode(
                            f'G1 Z{zhopEntry.get()} F{str(speed_var.get())}')  # go up with extruder Z-Hop parametr
                        if pauseEntry.get() != '0':
                            send_gcode(f'G4 P{pauseEntry.get()}')  # wait if needed PAUSE
                        send_gcode(f'G1 X{str(x2)}')
                        send_gcode(
                            f'G1 X{str(x3)} Z{str(zoffset.get())} F{str(speed_var.get())}')  # last point but on offset height
                        # afterdrop if needed
                        if check_afterdrop_var == 'on':
                            send_gcode('G91')
                            send_gcode(f'G1 E-{amountEntry.get()} F200')  # extrusion with speed 200
                            current_amount.set(current_amount.get() - float(amountEntry.get()))
                            send_gcode('G4 P500')
                            send_gcode('G90')
                            send_gcode(f'G1 F{str(speed_var.get())}')
                        # cleaning process
                        if check_clean_var == 'on':
                            send_gcode(f'G1 X{str(x3 + 5)} Z0 F{str(speed_var.get())}')
                            send_gcode(f'G1 X{str(x3 + 10)} F{str(speed_var.get())}')
                            send_gcode(f'G1 Z3 F{str(speed_var.get())}')  # go up to travel movement
                        else:
                            send_gcode(f'G1 Z{str(zoffset.get())}')  # go up to Z{str(zoffset.get())}

                        # update the progress bar
                        current_line.set(current_line.get() + 1)
                        percentage.set(current_line.get() / total_lines)
                        percentage_str.set(f"{percentage.get() * 100:.1f}%")
                        if abort:
                            break
                        y = round(y + step_var.get(), 2)
                        send_gcode(f'G1 X{str(x3)} Y{str(y)} Z{str(zoffset.get())}')
                        # status = check_syringe(ser, "M119")
                        # if status == 'empty':
                        #     print('syringe empty')
                        #     break
                        send_gcode('G91')
                        send_gcode(f'G1 E-{amountEntry.get()} F200')
                        current_amount.set(current_amount.get() - float(amountEntry.get()))
                        send_gcode('G4 P1000')
                        send_gcode('G90')
                        send_gcode(f'G1 Z{zhopEntry.get()} F{str(speed_var.get())}')
                        if pauseEntry.get() != '0':
                            send_gcode(f'G4 P{pauseEntry.get()}')

                        send_gcode(f'G1 X{str(x22)} F{str(speed_var.get())}')
                        send_gcode(f'G1 Z{str(zoffset.get())} X{str(x1)} F{str(speed_var.get())}')
                        if check_afterdrop_var == 'on':
                            send_gcode('G91')
                            send_gcode(f'G1 E-{amountEntry.get()} F200')  # extrusion with speed 200
                            current_amount.set(current_amount.get() - float(amountEntry.get()))
                            send_gcode('G4 P500')
                            send_gcode('G90')
                            send_gcode(f'G1 F{str(speed_var.get())}')
                        if check_clean_var == 'on':
                            send_gcode(f'G1 X{str(x1 - 5)} Z0 F{str(speed_var.get())}')
                            send_gcode(f'G1 X{str(x1 - 10)} F{str(speed_var.get())}')
                            send_gcode(f'G1 Z3 F{str(speed_var.get())}')  # go up to travel movement
                        else:
                            send_gcode(f'G1 Z{str(zoffset.get())}')  # go up to Z{str(zoffset.get())}

                        y = round(y + step_var.get(), 2)
                        # print('going to sleep for 4 seconds')
                        # time.sleep(4)
                        send_gcode('M400')
                        # update the progress bar
                        current_line.set(current_line.get() + 1)
                        percentage.set(current_line.get() / total_lines)
                        percentage_str.set(f"{percentage.get() * 100:.1f}%")
                        if abort:
                            break
                lines = round(82.5 / (step_var.get() / 2))
                x = 35.5
                send_gcode('G90')
                send_gcode(f'G1 Z7 F{str(speed_var.get())}')
                for _ in range(lines):
                    if x < limit_x:
                        send_gcode('G90')
                        send_gcode(f'G1 X{str(x)} Y{str(y1)} F{str(speed_var.get())}')
                        send_gcode(f'G1 Z{str(zoffset.get())} F{str(speed_var.get())}')
                        # status = check_syringe(ser, "M119")
                        # if status == 'empty':
                        #     print('syringe empty')
                        #     break
                        send_gcode('G91')
                        send_gcode(f'G1 E-{amountEntry.get()} F200')
                        current_amount.set(current_amount.get() - float(amountEntry.get()))
                        send_gcode('G4 P1000')
                        send_gcode('G90')
                        send_gcode(f'G1 Z{zhopEntry.get()} F{str(speed_var.get())}')
                        if pauseEntry.get() != '0':
                            send_gcode(f'G4 P{pauseEntry.get()}')
                        send_gcode(f'G1 Y{str(y2)}')
                        send_gcode(f'G1 Z{str(zoffset.get())} Y{str(y3)} F{str(speed_var.get())}')
                        # afterdrop if needed
                        if check_afterdrop_var == 'on':
                            send_gcode('G91')
                            send_gcode(f'G1 E-{amountEntry.get()} F200')  # extrusion with speed 200
                            current_amount.set(current_amount.get() - float(amountEntry.get()))
                            send_gcode('G4 P500')
                            send_gcode('G90')
                            send_gcode(f'G1 F{str(speed_var.get())}')
                        # cleaning process
                        if check_clean_var == 'on':
                            send_gcode(f'G1 Y{str(y3 + 5)} Z0 F{str(speed_var.get())}')
                            send_gcode(f'G1 Y{str(y3 + 10)} F{str(speed_var.get())}')
                            send_gcode(f'G1 Z3 F{str(speed_var.get())}')  # go up to travel movement
                        else:
                            send_gcode(f'G1 Z{str(zoffset.get())}')  # go up to Z{str(zoffset.get())}

                        x = round(x + step_var.get(), 2)
                        # update the progress bar
                        current_line.set(current_line.get() + 1)
                        percentage.set(current_line.get() / total_lines)
                        percentage_str.set(f"{percentage.get() * 100:.1f}%")
                        if abort:
                            break
                        send_gcode(f'G1 X{str(x)} Y{str(y3)} Z{str(zoffset.get())}')
                        # status = check_syringe(ser, "M119")
                        # if status == 'empty':
                        #     print('syringe empty')
                        #     break
                        send_gcode('G91')
                        send_gcode(f'G1 E-{amountEntry.get()} F200')
                        current_amount.set(current_amount.get() - float(amountEntry.get()))
                        send_gcode('G4 P1000')
                        send_gcode('G90')
                        send_gcode(f'G1 Z{zhopEntry.get()} F{str(speed_var.get())}')
                        if pauseEntry.get() != '0':
                            send_gcode(f'G4 P{pauseEntry.get()}')

                        send_gcode(f'G1 Y{str(y22)} F{str(speed_var.get())}')
                        send_gcode(f'G1 Z{str(zoffset.get())} Y{str(y1)} F{str(speed_var.get())}')
                        if check_afterdrop_var == 'on':
                            send_gcode('G91')
                            send_gcode(f'G1 E-{amountEntry.get()} F200')  # extrusion with speed 200
                            current_amount.set(current_amount.get() - float(amountEntry.get()))
                            send_gcode('G4 P500')
                            send_gcode('G90')
                            send_gcode(f'G1 F{str(speed_var.get())}')
                        if check_clean_var == 'on':
                            send_gcode(f'G1 Y{str(y1 - 5)} Z0 F{str(speed_var.get())}')
                            send_gcode(f'G1 Y{str(y1 - 10)} F{str(speed_var.get())}')
                            send_gcode(f'G1 Z3 F{str(speed_var.get())}')  # go up to travel movement
                        else:
                            send_gcode(f'G1 Z{str(zoffset.get())}')  # go up to Z{str(zoffset.get())}

                        # time.sleep(4)
                        x = round(x + step_var.get(), 2)
                        send_gcode('M400')
                        # update the progress bar
                        current_line.set(current_line.get() + 1)
                        percentage.set(current_line.get() / total_lines)
                        percentage_str.set(f"{percentage.get() * 100:.1f}%")
                        if abort:
                            break
                x1 -= adjust_different_layers  # adjust the x position for the next layer
                x3 += adjust_different_layers  # adjust the x position for the next layer

                y1 -= adjust_different_layers  # adjust the y position for the next layer
                y3 += adjust_different_layers  # adjust the y position for the next layer

        # send gcode that makes a beep when finished
        percentage_str.set("100%")
        send_gcode('M300 S440 P200')
        send_gcode('G0 X10 Y190 Z30 F3000')
    else:
        print('no connected')
        messagebox.showerror("Connection error", "Connect to printer first!")


def save_gcode_commands_to_file():
    # Define the G-code commands

    adjust_different_layers = 3  # distance between the start of each layer

    gcode_commands = [
        'M220 S100 ;reset feedrate',
        'M302 S0;enable cold extrusion',
        'M221 S100 ;reset flowrate',
        'G90 ;use absolute coordinates',
        'M82 ;absolute extrusion mode',
        'G28 ;home all axes',
        'G1 Z2 F1500 ;raise z',
        'G92 E0 ;reset syringe',
        # Add more G-code commands as needed
    ]
    if cups_var.get() == 9:
        limit_y = 171.5  # limit for the y position if there are 9 cups
        limit_x = 118  # limit for the x position if there are 9 cups
    elif cups_var.get() == 6:
        limit_y = 145  # limit for the y position if there are 6 cups
        limit_x = 91  # limit for the x position if there are 6 cups
    elif cups_var.get() == 3:
        limit_y = 117  # limit for the y position if there are 3 cups
        limit_x = 64  # limit for the x position if there are 3 cups

    if orientation_var.get() == 'Horizontal':
        x1 = 25.5  # first x position
        x2 = 77  # second x position
        x3 = 128  # third x position
        for i in range(layers_var.get()):
            y = 90  # y start position
            lines = round(82.5 / (step_var.get() / 2))
            for i in range(lines):
                if y < limit_y:
                    gcode_commands.append('G90')
                    gcode_commands.append(f'G1 X{str(x1)} Y{str(y)} F{str(speed_var.get())}')
                    gcode_commands.append(f'G1 Z{str(zoffset.get())} F{str(speed_var.get())}')
                    gcode_commands.append('G91')
                    gcode_commands.append(f'G1 E-{amountEntry.get()} F200')
                    gcode_commands.append('G90')
                    gcode_commands.append(f'G1 Z{zhopEntry.get()} F3000')
                    if pauseEntry.get() != '0':
                        gcode_commands.append(f'G4 S{pauseEntry.get()}')
                    gcode_commands.append(f'G1 X{str(x2)}')
                    gcode_commands.append(f'G1 Z{str(zoffset.get())} X{str(x3)} F{str(speed_var.get())}')
                    gcode_commands.append(f'G1 X{str(x3 + 5)} Z0')
                    gcode_commands.append(f'G1 X{str(x3 + 10)}')
                    y = round(y + step_var.get(), 2)
                    gcode_commands.append(f'G1 X{str(x3)} Y{str(y)} Z{str(zoffset.get())}')
                    gcode_commands.append('G91')
                    gcode_commands.append(f'G1 E-{amountEntry.get()} F200')
                    gcode_commands.append('G90')
                    gcode_commands.append(f'G1 Z{zhopEntry.get()} F3000')
                    gcode_commands.append(f'G4 S{pauseEntry.get()}')
                    gcode_commands.append(f'G1 X{str(x2)} F{str(speed_var.get())}')
                    gcode_commands.append(f'G1 Z{str(zoffset.get())} X{str(x1)} F{str(speed_var.get())}')
                    gcode_commands.append(f'G1 X{str(x1 - 5)} Z0')
                    gcode_commands.append(f'G1 X{str(x1 - 10)}')
                    y = round(y + step_var.get(), 2)
            x1 = x1 - adjust_different_layers  # adjust the x position for the next layer
            x3 = x3 + adjust_different_layers  # adjust the x position for the next layer
    if orientation_var.get() == 'Vertical':
        y1 = 79  # first y position
        y2 = 130.5  # second y position
        y3 = 181.5  # third y position
        lines = round(82.5 / (step_var.get() / 2))
        for i in range(layers_var.get()):
            for i in range(lines):
                x = 35.5  # x start position
                if x < limit_x:
                    gcode_commands.append('G90')
                    gcode_commands.append(f'G1 X{str(x)} Y{str(y1)} F{str(speed_var.get())}')
                    gcode_commands.append(f'G1 Z{str(zoffset.get())} F{str(speed_var.get())}')
                    gcode_commands.append('G91')
                    gcode_commands.append(f'G1 E-{amountEntry.get()} F200')
                    gcode_commands.append('G90')
                    gcode_commands.append(f'G1 Z{zhopEntry.get()} F3000')
                    if pauseEntry.get() != '0':
                        gcode_commands.append(f'G4 S{pauseEntry.get()}')
                    gcode_commands.append(f'G1 Y{str(y2)}')
                    gcode_commands.append(f'G1 Z{str(zoffset.get())} Y{str(y3)} F{str(speed_var.get())}')
                    gcode_commands.append(f'G1 Y{str(y3 + 5)} Z0')
                    gcode_commands.append(f'G1 Y{str(y3 + 10)}')
                    x = round(x + step_var.get(), 2)
                    gcode_commands.append(f'G1 X{str(x)} Y{str(y3)} Z{str(zoffset.get())}')
                    gcode_commands.append('G91')
                    gcode_commands.append(f'G1 E-{amountEntry.get()} F200')
                    gcode_commands.append('G90')
                    gcode_commands.append(f'G1 Z{zhopEntry.get()} F3000')
                    if pauseEntry.get() != '0':
                        gcode_commands.append(f'G4 S{pauseEntry.get()}')
                    gcode_commands.append(f'G1 Y{str(y2)} F{str(speed_var.get())}')
                    gcode_commands.append(f'G1 Z{str(zoffset.get())} Y{str(y1)} F{str(speed_var.get())}')
                    gcode_commands.append(f'G1 Y{str(y1 - 5)} Z0')
                    gcode_commands.append(f'G1 Y{str(y1 - 10)}')
                    x = round(x + step_var.get(), 2)
            y1 = y1 - adjust_different_layers  # adjust the y position for the next layer
            y3 = y3 + adjust_different_layers  # adjust the y position for the next layer

    if orientation_var.get() == 'Both':
        x1 = 25.5
        x2 = 77
        x3 = 128
        y1 = 79
        y2 = 130.5
        y3 = 181.5
        for i in range(layers_var.get()):
            y = 89
            lines = round(82.5 / (step_var.get() / 2))
            for i in range(lines):
                if y < limit_y:
                    gcode_commands.append('G90')
                    gcode_commands.append(f'G1 X{str(x1)} Y{str(y)} F{str(speed_var.get())}')
                    gcode_commands.append(f'G1 Z{str(zoffset.get())} F{str(speed_var.get())}')
                    gcode_commands.append('G91')
                    gcode_commands.append(f'G1 E-{amountEntry.get()} F200')
                    gcode_commands.append('G90')
                    gcode_commands.append(f'G1 Z{zhopEntry.get()} F3000')
                    if pauseEntry.get() != '0':
                        gcode_commands.append(f'G4 S{pauseEntry.get()}')
                    gcode_commands.append(f'G1 X{str(x2)}')
                    gcode_commands.append(f'G1 Z{str(zoffset.get())} X{str(x3)} F{str(speed_var.get())}')
                    gcode_commands.append(f'G1 X{str(x3 + 5)} Z0')
                    gcode_commands.append(f'G1 X{str(x3 + 10)}')
                    y = round(y + step_var.get(), 2)
                    gcode_commands.append(f'G1 X{str(x3)} Y{str(y)} Z{str(zoffset.get())}')
                    gcode_commands.append('G91')
                    gcode_commands.append(f'G1 E-{amountEntry.get()} F200')
                    gcode_commands.append('G90')
                    gcode_commands.append(f'G1 Z{zhopEntry.get()} F3000')
                    gcode_commands.append(f'G4 S{pauseEntry.get()}')
                    gcode_commands.append(f'G1 X{str(x2)} F{str(speed_var.get())}')
                    gcode_commands.append(f'G1 Z{str(zoffset.get())} X{str(x1)} F{str(speed_var.get())}')
                    gcode_commands.append(f'G1 X{str(x1 - 5)} Z0')
                    gcode_commands.append(f'G1 X{str(x1 - 10)}')
                    y = round(y + step_var.get(), 2)
            lines = round(82.5 / (step_var.get() / 2))
            x = 35.5
            for i in range(lines):
                if x < limit_x:
                    gcode_commands.append('G90')
                    gcode_commands.append(f'G1 X{str(x)} Y{str(y1)} F{str(speed_var.get())}')
                    gcode_commands.append(f'G1 Z{str(zoffset.get())} F{str(speed_var.get())}')
                    gcode_commands.append('G91')
                    gcode_commands.append(f'G1 E-{amountEntry.get()} F200')
                    gcode_commands.append('G90')
                    gcode_commands.append(f'G1 Z{zhopEntry.get()} F3000')
                    if pauseEntry.get() != '0':
                        gcode_commands.append(f'G4 S{pauseEntry.get()}')
                    gcode_commands.append(f'G1 Y{str(y2)}')
                    gcode_commands.append(f'G1 Z{str(zoffset.get())} Y{str(y3)} F{str(speed_var.get())}')
                    gcode_commands.append(f'G1 Y{str(y3 + 5)} Z0')
                    gcode_commands.append(f'G1 Y{str(y3 + 10)}')
                    x = round(x + step_var.get(), 2)
                    gcode_commands.append(f'G1 X{str(x)} Y{str(y3)} Z{str(zoffset.get())}')
                    gcode_commands.append('G91')
                    gcode_commands.append(f'G1 E-{amountEntry.get()} F200')
                    gcode_commands.append('G90')
                    gcode_commands.append(f'G1 Z{zhopEntry.get()} F3000')
                    if pauseEntry.get() != '0':
                        gcode_commands.append(f'G4 S{pauseEntry.get()}')
                    gcode_commands.append(f'G1 Y{str(y2)} F{str(speed_var.get())}')
                    gcode_commands.append(f'G1 Z{str(zoffset.get())} Y{str(y1)} F{str(speed_var.get())}')
                    gcode_commands.append(f'G1 Y{str(y1 - 5)} Z0')
                    gcode_commands.append(f'G1 Y{str(y1 - 10)}')
                    x = round(x + step_var.get(), 2)
            x1 = x1 - adjust_different_layers  # adjust the x position for the next layer
            x3 = x3 + adjust_different_layers  # adjust the x position for the next layer

            y1 = y1 - adjust_different_layers  # adjust the y position for the next layer
            y3 = y3 + adjust_different_layers  # adjust the y position for the next layer
    # write gcode that makes a beep when finished
    gcode_commands.append('M300 S440 P200')
    # Open a save file dialog
    file_path = fd.asksaveasfilename(defaultextension=".gcode", filetypes=[("G-code files", "*.gcode")])

    # If a file path was selected
    if file_path:
        # Open the file in write mode
        with open(file_path, 'w') as f:
            # Write each command to the file
            for command in gcode_commands:
                f.write(command + '\n')

        print('G-code saved to file:', file_path)


def syringe_1ml():
    global ser, current_amount
    if ser is not None:
        # Set to relative positioning
        # ser.write(('G90' + '\n').encode('utf-8'))
        ser.write(('M302 S0\nG1 E20 F200' + '\n').encode('utf-8'))
        print("Go to 1 ml")
        current_amount.set(20)
        logTextVar.set(logTextVar.get() + '\n' + 'Go to 1 ml')
        # ser.write(('G90' + '\n').encode('utf-8'))
    else:
        print('Error: No connection to the printer')

def syringe_2ml():
    global ser, current_amount
    if ser is not None:
        # Set to relative positioning
        # ser.write(('G90' + '\n').encode('utf-8'))
        ser.write(('M302 S0\nG1 E53 F200' + '\n').encode('utf-8'))
        print("Go to 1 ml")
        current_amount.set(53)
        logTextVar.set(logTextVar.get() + '\n' + 'Go to 1 ml')
        # ser.write(('G90' + '\n').encode('utf-8'))
    else:
        print('Error: No connection to the printer')

def syringe_3ml():
    global ser, current_amount
    if ser is not None:
        # Set to relative positioning
        # ser.write(('G90' + '\n').encode('utf-8'))
        ser.write(('M302 S0\nG1 E86 F200' + '\n').encode('utf-8'))
        print("Go to 1 ml")
        current_amount.set(86)
        logTextVar.set(logTextVar.get() + '\n' + 'Go to 1 ml')
        # ser.write(('G90' + '\n').encode('utf-8'))
    else:
        print('Error: No connection to the printer')

def syringe_4ml():
    global ser, current_amount
    if ser is not None:
        # Set to relative positioning
        # ser.write(('G90' + '\n').encode('utf-8'))
        ser.write(('M302 S0\nG1 E119 F200' + '\n').encode('utf-8'))
        print("Go to 1 ml")
        current_amount.set(119)
        logTextVar.set(logTextVar.get() + '\n' + 'Go to 1 ml')
        # ser.write(('G90' + '\n').encode('utf-8'))
    else:
        print('Error: No connection to the printer')

def syringe_5ml():
    global ser, current_amount
    if ser is not None:
        # Set to relative positioning
        # ser.write(('G90' + '\n').encode('utf-8'))
        ser.write(('M302 S0\nG1 E152 F200' + '\n').encode('utf-8'))
        print("Go to 1 ml")
        current_amount.set(152)
        logTextVar.set(logTextVar.get() + '\n' + 'Go to 1 ml')
        # ser.write(('G90' + '\n').encode('utf-8'))
    else:
        print('Error: No connection to the printer')

# def extrude10():
#     global ser, current_amount
#     if ser is not None:
#         # Set to relative positioning
#         ser.write(('G91' + '\n').encode('utf-8'))
#         ser.write(('M302 S0\nG1 E-10 F200 ;intake 10 units' + '\n').encode('utf-8'))
#         print("Extrude 10 units")
#         current_amount.set(current_amount.get() - 10)
#         logTextVar.set(logTextVar.get() + '\n' + 'Extrude 10 units')
#         ser.write(('G90' + '\n').encode('utf-8'))
#     else:
#         print('Error: No connection to the printer')
#
#
# def intake50():
#     global ser, current_amount
#     if ser is not None:
#         # Set to relative positioning
#         ser.write(('G91' + '\n').encode('utf-8'))
#         ser.write(('M302 S0\nG1 E50 F200 ;intake 10 units' + '\n').encode('utf-8'))
#         print("Intake 50 units")
#         current_amount.set(current_amount.get() + 50)
#         logTextVar.set(logTextVar.get() + '\n' + 'Intake 50 units')
#         ser.write(('G90' + '\n').encode('utf-8'))
#     else:
#         print('Error: No connection to the printer')
#
#
# def extrude50():
#     global ser, current_amount
#     if ser is not None:
#         # Set to relative positioning
#         ser.write(('G91' + '\n').encode('utf-8'))
#         ser.write(('M302 S0\nG1 E-50 F200 ;intake 10 units' + '\n').encode('utf-8'))
#         print("Extrude 50 units")
#         current_amount.set(current_amount.get() - 50)
#         logTextVar.set(logTextVar.get() + '\n' + 'Extrude 50 units')
#         ser.write(('G90' + '\n').encode('utf-8'))
#     else:
#         print('Error: No connection to the printer')


def intakeAmount():
    global ser, current_amount
    if ser is not None:
        # Set to relative positioning
        ser.write(('G91' + '\n').encode('utf-8'))
        ser.write((f'M302 S0\nG1 E{droplet_var.get()} F200 ;intake {droplet_var.get()} units\n').encode('utf-8'))
        print(f"Intake {droplet_var.get()} units")
        current_amount.set(current_amount.get() + droplet_var.get())
        logTextVar.set(f'{logTextVar.get()}\n Intake {droplet_var.get()} units')
        ser.write(('G90' + '\n').encode('utf-8'))
    else:
        print('Error: No connection to the printer')


# Create the main window
window = GUI()
