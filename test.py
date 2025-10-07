import tkinter as tk
from tkinter import filedialog
from tkinter import ttk
from datetime import datetime
import math
import os
import pandas as pd
import numpy as np
import cv2
from PIL import Image
import warnings
warnings.filterwarnings("ignore", message=".*pin_memory.*")
def get_reader():
	"""Return a persistent EasyOCR reader, loading it only once."""
	if not hasattr(get_reader, "reader"):
		print("Loading EasyOCR")
		import easyocr
		get_reader.reader = easyocr.Reader(['en'], verbose=False, gpu=False)
		print("EasyOCR is loaded")
	return get_reader.reader



def user_defined_settings():
	# Allowed image extensions
	image_extensions = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp"}


	def on_close_window():
		root.destroy()
		exit()

	class DirectoryFrame(tk.Frame):
		def __init__(self, parent):
			super().__init__(parent)
			self.rows = []

			# Add the first row initially
			self.add_row()

		def add_row(self, text=""):
			row_index = len(self.rows)

			# Label
			if row_index == 0:
				label = tk.Label(self, text="Image directory:")
				label.grid(row=row_index, column=0, padx=5, pady=0)

			# Entry widget
			entry = tk.Entry(self, width=30)
			entry.grid(row=row_index, column=1, padx=5, pady=0)
			entry.bind("<KeyRelease>", self.on_entry_change)

			# Choose directory button
			button = tk.Button(self, text="Choose", 
							command=lambda e=entry: self.choose_directory(entry_widget=e))
			button.grid(row=row_index, column=2, padx=5, pady=0)

			# cSLO checkbox
			cslo_var = tk.BooleanVar(value=False)
			cslo_cb = tk.Checkbutton(self, text="cSLO", variable=cslo_var,
									command=lambda e=entry: self.checkbox_toggle(e, 'cslo'))
			cslo_cb.grid(row=row_index, column=3, padx=5, pady=0)

			# OCT checkbox
			oct_var = tk.BooleanVar(value=False)
			oct_cb = tk.Checkbutton(self, text="OCT", variable=oct_var,
									command=lambda e=entry: self.checkbox_toggle(e, 'oct'))
			oct_cb.grid(row=row_index, column=4, padx=5, pady=0)

			# Store the row info
			self.rows.append({
				'entry': entry,
				'cslo_var': cslo_var,
				'oct_var': oct_var,
				'cslo_cb': cslo_cb,
				'oct_cb': oct_cb,
				'button': button
			})

		def cleanup_empty_rows(self):
			# Keep the last row, delete other empty rows
			new_rows = []
			for i, row in enumerate(self.rows):
				if i == len(self.rows) - 1 or row['entry'].get().strip() != "":
					new_rows.append(row)
				else:
					# Remove widgets from grid
					for widget in ['entry', 'cslo_cb', 'oct_cb', 'button']:
						row[widget].grid_forget()
			self.rows = new_rows

			# Re-grid all remaining rows so their row numbers match their list indices
			for i, row in enumerate(self.rows):
				row['entry'].grid(row=i, column=1, padx=5, pady=0)
				row['button'].grid(row=i, column=2, padx=5, pady=0)
				row['cslo_cb'].grid(row=i, column=3, padx=5, pady=0)
				row['oct_cb'].grid(row=i, column=4, padx=5, pady=0)

			# Update the number of mice
			number_of_mice_frame.mice_set.clear()
			number_of_mice_frame.figure_out_how_many_mice()




		def checkbox_toggle(self, entry_widget, which):
			row = next(r for r in self.rows if r['entry'] == entry_widget)
			if which == 'cslo' and row['cslo_var'].get():
				row['oct_var'].set(False)
			elif which == 'oct' and row['oct_var'].get():
				row['cslo_var'].set(False)


		def on_entry_change(self, event):
			entry_widget = event.widget
			row_index = next(i for i, r in enumerate(self.rows) if r['entry'] == entry_widget)

			# If last row is non-empty, add a new blank row
			if row_index == len(self.rows) - 1 and entry_widget.get().strip() != "":
				self.add_row()
			
			# Remove extra empty rows
			self.cleanup_empty_rows()

			def check_directory(directory):
				cslo_or_oct_directory = ""

				# List contents of the directory
				contents = os.listdir(directory)

				# Filter out directories and files
				subdirs = [os.path.join(directory, d) for d in contents if os.path.isdir(os.path.join(directory, d))]
				files = [f for f in contents if os.path.isfile(os.path.join(directory, f))]

				# cSLO images: Check if each subdir contains "OS" and "OD"
				if subdirs:
					valid = True
					for subdir in subdirs:
						if not (os.path.isdir(os.path.join(subdir, "OS")) or os.path.isdir(os.path.join(subdir, "OD"))):
							valid = False
							break
					if valid:
						cslo_or_oct_directory = "cslo"
						return cslo_or_oct_directory

				# OCT images: Check if the directory contains image files
				# Get all files in directory (ignores subdirectories themselves)
				files = [f for f in os.listdir(inputted_directory) 
						if os.path.isfile(os.path.join(inputted_directory, f))]

				# Look for image files with "_OD_" or "_OS_" in the filename
				for f in files:
					ext = os.path.splitext(f)[1].lower()
					if ext in image_extensions and ("_OD_" in f or "_OS_" in f):
						cslo_or_oct_directory = "oct"
						return cslo_or_oct_directory

				return cslo_or_oct_directory

			inputted_directory = entry_widget.get()
			if os.path.exists(inputted_directory):
				# Change the text color to black
				entry_widget.config(fg="black")

				# Determine if the images are cSLO or OCT and update the checkbox accordingly
				cslo_or_oct_directory = check_directory(inputted_directory)
				
				if cslo_or_oct_directory == "cslo":
					row = next(r for r in self.rows if r['entry'] == entry_widget)
					row['cslo_var'].set(True)
					row['oct_var'].set(False)
				elif cslo_or_oct_directory == "oct":
					row = next(r for r in self.rows if r['entry'] == entry_widget)
					row['oct_var'].set(True)
					row['cslo_var'].set(False)

				# Update the number of mice
				number_of_mice_frame.figure_out_how_many_mice()
			
			# If this isn't a directory that exists, change the color to red
			else:
				entry_widget.config(fg="red")

		def choose_directory(self, row_index=None, entry_widget=None):
			directory = filedialog.askdirectory()
			if directory:
				if entry_widget is not None:
					# Find the row by entry widget
					row = next(r for r in self.rows if r['entry'] == entry_widget)
				else:
					row = self.rows[row_index]
				
				row['entry'].delete(0, tk.END)
				row['entry'].insert(0, directory)
				self.on_entry_change(event=type('Event', (), {'widget': row['entry']})())

		def get_data(self):
			directories = []
			for row in self.rows:
				path = row['entry'].get().strip()
				if os.path.exists(path):
					if path:  # skip blanks
						if row['cslo_var'].get():
							image_type = "cslo"
						elif row['oct_var'].get():
							image_type = "oct"
						else:
							image_type = None

						directories.append((path, image_type))
			
			return {"directories": directories}

	class NumberOfMiceFrame(tk.Frame):
		def __init__(self, parent):
			super().__init__(parent)
			self.mice_set = set()

			text_label = tk.Label(self, text="Number of mice found:")
			text_label.grid(row=0, column=0, padx=5)

			number_of_mice = 0
			mouse_number_label = tk.Label(self, text=number_of_mice)
			mouse_number_label.grid(row=0, column=1, padx=5)

			#determine_button = tk.Button(self, text="Determine", command=self.figure_out_how_many_mice)
			#determine_button.grid(row=0, column=2, padx=5)

		def figure_out_how_many_mice(self):
			directory_info_from_user = directory_frame.get_data().get("directories")
			
			for entry in directory_info_from_user:
				directory_path, image_type = entry

				if image_type == "oct":
					
					for file in os.listdir(directory_path):
						ext = os.path.splitext(file)[1].lower()
						if ext in image_extensions:
							mouse_number = file.split("_")[0]
							self.mice_set.add(mouse_number)
					
				elif image_type == "cslo":
					for item in os.listdir(directory_path):
						subfolder_path = os.path.join(directory_path, item)
						
						# Check if it is a directory
						if os.path.isdir(subfolder_path):
							# Get a list of items inside this subfolder
							sub_items = os.listdir(subfolder_path)
							
							# Check if both "OD" and "OS" exist as folders
							if "OD" in sub_items and "OS" in sub_items:
								od_path = os.path.join(subfolder_path, "OD")
								os_path = os.path.join(subfolder_path, "OS")
								
								# Make sure both are directories, not files
								if os.path.isdir(od_path) and os.path.isdir(os_path):
									self.mice_set.add(item)
		
			number_of_mice = len(self.mice_set)
			self.update_mouse_number(number_of_mice)

		def update_mouse_number(self, number_of_mice):
			mouse_number_label = tk.Label(self, text=number_of_mice)
			mouse_number_label.grid(row=0, column=1, padx=5)
			
			# Update the row x column numbers
			row_col_frame.update_numbers(number_of_mice)

			# Update the mouse dataframe
			mouse_info_frame.on_entry_change()
		
		def get_data(self):
			return {
				"mice_numbers_set": self.mice_set
			}


	class MouseInfoFrame(tk.Frame):
		def __init__(self, parent):
			super().__init__(parent)

			self.create_blank_df()

			label = tk.Label(self, text="Mouse info:")
			label.grid(row=0, column=0, padx=5, pady=0)

			# StringVar linked to Entry
			self.excel_var = tk.StringVar()			
			self.excel_var.trace_add("write", self.on_entry_change)

			self.excel_entry = tk.Entry(self, textvariable=self.excel_var, width=42)
			self.excel_entry.insert(0, "[Mouse info file location]")
			self.excel_entry.grid(row=0, column=1, padx=5, pady=0)

			choose_button = tk.Button(self, text="Choose", command=self.choose_file)
			choose_button.grid(row=0, column=2, padx=5, pady=0)

			edit_button = tk.Button(self, text="Edit info", command=self.edit_mouse_info)
			edit_button.grid(row=0, column=3, padx=5, pady=0)

			cslo_eartag_button = tk.Button(self, text="Determine ear tag number based off of cSLO images",
								  command=self.determine_cslo_eartag_number)
			cslo_eartag_button.grid(row=1, column=0, columnspan=4, padx=5, pady=3)

		def choose_file(self):
			info_file_path = filedialog.askopenfilename(
				filetypes=[("Excel files", "*.xlsx *.xls"), ("CSV files", "*.csv")]
			)
			if info_file_path:
				self.excel_var.set(info_file_path)
			
		def on_entry_change(self, *args):
			self.create_blank_df()
			self.add_mice_from_csv_doc()
			self.add_mice_from_image_files()

		def create_blank_df(self):
			self.df = pd.DataFrame(columns=[
				"cSLO number",
				"ET number",
				"Cage number",
				"Treatment group",
				"Exclude images"
			])

		def add_mice_from_csv_doc(self):
			file_path = self.excel_var.get()
			if os.path.isfile(file_path):
				ext = os.path.splitext(file_path)[1]  # get file extension

				new_df = None
				if ext in [".xlsx", ".xls"]:
					new_df = pd.read_excel(file_path)
				elif ext == ".csv":
					new_df = pd.read_csv(file_path)

				if new_df is not None and not new_df.empty:
					new_df["Exclude images"] = new_df["Exclude images"].map(lambda x: True if x == "X" else False)
					self.df = pd.concat([self.df, new_df], ignore_index=True)
				

		def add_mice_from_image_files(self):
			# Including mouse numbers found in the files not in the excel spreadsheet
			for mouse in number_of_mice_frame.mice_set:
				if mouse not in self.df["cSLO number"].values:
					# Create a new row with cSLO number set and other columns empty/NaN
					new_row = {
						"cSLO number": mouse,
						"ET number": "",
						"Cage number": "",
						"Treatment group": "",
						"Exclude images": False
					}
					self.df = pd.concat([self.df, pd.DataFrame([new_row])], ignore_index=True)


		def edit_mouse_info(self):
			top = tk.Toplevel(root)
			top.title("Edit DataFrame")

			entries = {}  # store references to Entry widgets or BooleanVars for checkboxes

			# Column headers
			for j, col in enumerate(self.df.columns):
				label = tk.Label(top, text=col, font=("Arial", 10, "bold"))
				label.grid(row=0, column=j, padx=2, pady=5)

			# Data rows
			for i, row in self.df.iterrows():
				for j, col in enumerate(self.df.columns):
					if col == "Exclude images":
						# Use a checkbox for boolean values
						var = tk.BooleanVar(value=row[col])
						cb = tk.Checkbutton(top, variable=var)
						cb.grid(row=i+1, column=j, padx=0, pady=0)
						entries[(i, col)] = var  # store the BooleanVar
					else:
						# Text entry, centered
						e = tk.Entry(top, justify="center")
						e.grid(row=i+1, column=j, padx=2, pady=0)
						e.insert(0, row[col])
						entries[(i, col)] = e

			def save_changes():
				for (i, col), widget in entries.items():
					if col == "Exclude images":
						# Get the value of the checkbox
						self.df.at[i, col] = widget.get()
					else:
						self.df.at[i, col] = widget.get()
				top.destroy()

			save_button = tk.Button(top, text="Save", command=save_changes)
			save_button.grid(row=len(self.df)+1, column=0, columnspan=len(self.df.columns), pady=10)
			
		def determine_cslo_eartag_number(self):
			# Get a list of directories that have cSLO images
			data_dic = directory_frame.get_data()
			available_directories = data_dic["directories"]	# Will be a list of tuples: (directory, "cslo"/"oct")
			cslo_directories = []
			for directory, image_type in available_directories:
				if image_type == "cslo":
					cslo_directories.append(directory)
			
			if len(cslo_directories) == 0:
				print("No cSLO directories found")
				return
			
			# Going through the cSLO image directories and grabbing the information from the images and putting it in the df
			for directory in cslo_directories:
				self.cslo_ear_tag_dic = determine_ear_tag_number_in_cslo_images(directory)
				for cslo_num, et_value in self.cslo_ear_tag_dic.items():
					# check if the cSLO number exists in the df
					if cslo_num in self.df["cSLO number"].values:
						# update the ET number
						self.df.loc[self.df["cSLO number"] == cslo_num, "ET number"] = et_value
					else:
						# add a new row
						new_row = {"cSLO number": cslo_num, "ET number": et_value}
						self.df = pd.concat([self.df, pd.DataFrame([new_row])], ignore_index=True)
			self.edit_mouse_info()


		def get_data(self):
			self.df_to_export = self.df
			
			# Remove any mice that there aren't any image files of
			self.df_to_export = self.df_to_export[self.df_to_export["cSLO number"].isin(number_of_mice_frame.mice_set)]

			# Remove any mice that were marked to be excluded
			self.df_to_export = self.df_to_export[self.df_to_export["Exclude images"] != True]

			# Create dictionary with cSLO numbers (key) and [Ear tag number, cage, group]
			mouse_info_dic = {
				row["cSLO number"]: (row["ET number"], row["Cage number"], row["Treatment group"])
				for _, row in self.df_to_export.iterrows()
			}

			return {
				"mouse_info_dic": mouse_info_dic
			}



	class TitleFrame(tk.Frame):
		def __init__(self, parent):
			super().__init__(parent)
			self.columnconfigure(1, weight=1)

			# Title label + entry
			title_label = tk.Label(self, text="Title:")
			title_label.grid(row=0, column=0, padx=5, pady=0, sticky="w")

			self.title_entry = tk.Entry(self, width=40)
			self.title_entry.insert(0, "In vivo imaging")
			self.title_entry.grid(row=0, column=1, padx=5, pady=0, sticky="we")

			# Subtitle label + entry
			subtitle_label = tk.Label(self, text="Subtitle:")
			subtitle_label.grid(row=1, column=0, padx=5, pady=0, sticky="w")

			today_str = datetime.today().strftime("%B %d, %Y").replace(" 0", " ")
			self.subtitle_entry = tk.Entry(self, width=40)
			self.subtitle_entry.insert(0, today_str)
			self.subtitle_entry.grid(row=1, column=1, padx=5, pady=0, sticky="we")

		def get_data(self):
			return {
				"document_title": self.title_entry.get(),
				"subtitle": self.subtitle_entry.get()
			}
				


	class RowColumnFrame(tk.Frame):
		def __init__(self, parent):
			super().__init__(parent)

			self.number_of_mice = 0

			# Calculate initial row/col numbers
			number_of_rows, number_of_columns = self.determine_row_and_column_number(self.number_of_mice)

			# Label
			label = tk.Label(self, text="Row x column:")
			label.grid(row=0, column=0, padx=5, pady=5, sticky="w")

			# Row entry
			self.row_entry = tk.Entry(self, width=5)
			self.row_entry.insert(0, number_of_rows)
			self.row_entry.grid(row=0, column=1, padx=5, pady=5)

			# x label
			x_label = tk.Label(self, text="x")
			x_label.grid(row=0, column=2, padx=5, pady=5)

			# Column entry
			self.column_entry = tk.Entry(self, width=5)
			self.column_entry.insert(0, number_of_columns)
			self.column_entry.grid(row=0, column=3, padx=5, pady=5)

			# Bind updates
			self.row_entry.bind("<KeyRelease>", self.update_columns)
			self.column_entry.bind("<KeyRelease>", self.update_rows)

		# Triggered when other things happen in the dialog box
		def update_numbers(self, new_total_number):
			self.number_of_mice = new_total_number
			number_of_rows, number_of_columns = self.determine_row_and_column_number(self.number_of_mice)
			self.row_entry.delete(0, tk.END)
			self.row_entry.insert(0, str(number_of_rows))
			self.column_entry.delete(0, tk.END)
			self.column_entry.insert(0, str(number_of_columns))

		@staticmethod
		def determine_row_and_column_number(total_number):
			square_root = math.sqrt(total_number)
			number_of_rows = math.floor(square_root)
			number_of_columns = math.ceil(square_root)
			if number_of_rows == number_of_columns:
				number_of_rows -= 1
				number_of_columns += 1
			while number_of_rows * number_of_columns < total_number:
				number_of_rows += 1
			if number_of_rows == number_of_columns:
				number_of_rows -= 1
				number_of_columns += 1
			return number_of_rows, number_of_columns

		# Triggered when row number is changed
		def update_columns(self, *_):
			try:
				row_number = self.row_entry.get()
				if row_number != "":
					row_number = int(row_number)
					column_number = math.ceil(self.number_of_mice / row_number)
					self.column_entry.delete(0, tk.END)
					self.column_entry.insert(0, str(column_number))
			except ValueError:
				self.column_entry.delete(0, tk.END)

		# Triggered when column number is changed
		def update_rows(self, *_):
			try:
				column_number = self.column_entry.get()
				if column_number != "":
					column_number = int(column_number)
					row_number = math.ceil(self.number_of_mice / column_number)
					self.row_entry.delete(0, tk.END)
					self.row_entry.insert(0, str(row_number))
			except ValueError:
				self.row_entry.delete(0, tk.END)

		
		def get_data(self):
			return {
				"number_of_rows": int(self.row_entry.get()),
				"number_of_columns": int(self.column_entry.get())
			}


	class NumberAndCsloCropFrame(tk.Frame):
		def __init__(self, parent):
			super().__init__(parent)

			# Use label
			mouse_label_to_use_label = tk.Label(self, text="Use:")
			mouse_label_to_use_label.grid(row=0, column=0, padx=5, pady=0, sticky="w")

			# cSLO checkbox
			self.cslo_number_var = tk.BooleanVar(value=True)
			cslo_cb = tk.Checkbutton(self, text="cSLO numbers", variable=self.cslo_number_var)
			cslo_cb.grid(row=0, column=1, padx=5, pady=0, sticky="w")

			# Ear tag checkbox
			self.eartag_number_var = tk.BooleanVar(value=False)
			eartag_cb = tk.Checkbutton(self, text="Ear tag numbers", variable=self.eartag_number_var)
			eartag_cb.grid(row=0, column=2, padx=5, pady=0, sticky="w")

			# Crop cSLO text checkbox
			self.crop_cslo_text_var = tk.BooleanVar(value=True)
			crop_cslo_text_cb = tk.Checkbutton(self, text="Crop the text off of cSLO images",
											variable=self.crop_cslo_text_var)
			crop_cslo_text_cb.grid(row=1, column=0, columnspan=3, padx=5, pady=0, sticky="w")

		def get_data(self):
			self.cslo_number_bool = self.cslo_number_var.get()
			self.eartag_number_bool = self.eartag_number_var.get()
			self.crop_cslo_text_bool = self.crop_cslo_text_var.get()

			return {
				"cslo_number_bool": self.cslo_number_bool,
				"eartag_number_bool": self.eartag_number_bool,
				"crop_cslo_text_bool": self.crop_cslo_text_bool
			}

	
	class OctCropFrame(tk.Frame):
		def __init__(self, parent):
			super().__init__(parent)

			# Crop OCT section
			self.oct_crop_var = tk.BooleanVar(value=False)
			oct_crop_cb = tk.Checkbutton(self, text="Crop OCT images",
										variable=self.oct_crop_var,
										command=self.oct_crop_checkbox)
			oct_crop_cb.grid(row=2, column=0, padx=5, pady=0, sticky="w")

			self.oct_crop_entry = tk.Entry(self, width=5, state="disabled")
			self.oct_crop_entry.grid(row=2, column=1, padx=0, pady=0)

			pixel_label = tk.Label(self, text="pixels")
			pixel_label.grid(row=2, column=2, padx=0, pady=0)

			oct_crop_button = tk.Button(self, text="Find minimum OCT height", command=self.find_minimum_oct_height)
			oct_crop_button.grid(row=2, column=3, padx=5, pady=0)

		def find_minimum_oct_height(self):
			print("Button currently not functional")

		def oct_crop_checkbox(self):
			if self.oct_crop_var.get():
				self.oct_crop_entry.config(state="normal")
				self.oct_crop_entry.delete(0, tk.END)
				
				# -- Figure out the height of OCT images, if any --
				# Find OCT directories
				directories_info = directory_frame.get_data()
				directories = directories_info["directories"]
				oct_directory_present = False
				for directory in directories:
					if directory[1] == "oct":
						oct_directory_present = True
						oct_directory = directory[0]
						continue
				if oct_directory_present:
					# list all files
					files = sorted(os.listdir(oct_directory))
					image_height = 0
					# find the first file that looks like an image
					for f in files:
						if f.lower().endswith(('.png', '.jpg', '.jpeg', '.tif', '.tiff', '.bmp')):
							image_path = os.path.join(oct_directory, f)
							with Image.open(image_path) as img:
								_, image_height = img.size
					if image_height > 0:
						self.oct_crop_entry.insert(0, image_height)
					else:
						self.oct_crop_entry.insert(0, "480")
				else:
					self.oct_crop_entry.insert(0, "480")
			else:
				self.oct_crop_entry.config(state="disabled")
	
	class ImagesToUseFrame(tk.Frame):
		def __init__(self, parent):
			super().__init__(parent)

			label = tk.Label(self, text="Images to use")
			label.grid(row=0, column=0, padx=5)

	class PresetFrame(tk.Frame):
		def __init__(self, parent):
			super().__init__(parent)

			label = tk.Label(self, text="Presets")
			label.grid(row=0, column=0, padx=5)


	class ConfirmationFrame(tk.Frame):
		def __init__(self, parent):
			super().__init__(parent)
			
			# Preview layout
			preview_layout_button = tk.Button(self, text="Preview layout", 
									 command=self.preview_layout)
			preview_layout_button.grid(row=0, column=0, padx=5)

			# Preview layout + images
			preview_layout_images_button = tk.Button(self, text="Preview layout & images",
											command=self.preview_layout_and_images)
			preview_layout_images_button.grid(row=0, column=1, padx=5)

			# Okay button
			okay_button = tk.Button(self, text="Okay", command=self.on_ok_click)
			okay_button.grid(row=0, column=2, padx=5)

		def preview_layout(self):
			print("Hello")

		
		def preview_layout_and_images(self):
			self.test_settings = row_col_frame.get_data()
			

		
		def on_ok_click(self):
			self.settings = {}

			self.settings.update(directory_frame.get_data())
			self.settings.update(title_frame.get_data())
			self.settings.update(row_col_frame.get_data())
			self.settings.update(mouse_info_frame.get_data())
			self.settings.update(number_and_cslo_crop_frame.get_data())



			root.destroy()



	root = tk.Tk()
	root.title("Settings")
	root.protocol("WM_DELETE_WINDOW", on_close_window)
	root.columnconfigure(0, weight=1)
	root.rowconfigure(0, weight=1)

	directory_frame = DirectoryFrame(root)
	directory_frame.pack(anchor='w')
	number_of_mice_frame = NumberOfMiceFrame(root)
	number_of_mice_frame.pack(anchor='w')
	mouse_info_frame = MouseInfoFrame(root)
	mouse_info_frame.pack(anchor='w', pady=3)
	title_frame = TitleFrame(root)
	title_frame.pack(anchor='w', fill='x')
	row_col_frame = RowColumnFrame(root)
	row_col_frame.pack(anchor='w')
	number_and_cslo_crop_frame = NumberAndCsloCropFrame(root)
	number_and_cslo_crop_frame.pack(anchor='w')
	oct_crop_frame = OctCropFrame(root)
	oct_crop_frame.pack(anchor='w')
	images_to_use_frame = ImagesToUseFrame(root)
	images_to_use_frame.pack(anchor='w')
	preset_frame = PresetFrame(root)
	preset_frame.pack(anchor='w')
	confirmation_frame = ConfirmationFrame(root)
	confirmation_frame.pack(anchor='s', pady=10)

	root.mainloop()
	return confirmation_frame.settings




def determine_ear_tag_number_in_cslo_images(base_directory):
	reader = get_reader()
	cslo_ear_tag_dic = {}

	# loop through all subfolders
	for folder in os.listdir(base_directory):
		folder_path = os.path.join(base_directory, folder)
		if not os.path.isdir(folder_path):
			continue  # skip non-folders

		# prefer "OD", fallback to "OS"
		target_dir = os.path.join(folder_path, "OD")
		if not os.path.exists(target_dir):
			target_dir = os.path.join(folder_path, "OS")
		if not os.path.exists(target_dir):
			continue # skip if it doesn't have the OD or OS subfolders

		# find first image file in target_dir
		files = [f for f in os.listdir(target_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.tif'))]
		if not files:
			continue	# skip if no images

		first_image_path = os.path.join(target_dir, files[0])
		img = cv2.imread(first_image_path)

		if img is None:
			continue	# skip if can't read image

		height, width, _ = img.shape

		# crop bottom-left region
		top_square_height = width
		bottom_rect_height = height - top_square_height
		crop_height = (bottom_rect_height // 3) + 10
		crop_width = int(width * 0.70)  # left 70% of image

		# slice: rows (y), columns (x)
		cropped = img[top_square_height : top_square_height + crop_height, 0:crop_width]

		# OCR
		results = reader.readtext(cropped)
		mouse_id = [res[1] for res in results]  # res[1] contains detected text
		mouse_id_string = " ".join(mouse_id)
		if folder in mouse_id_string:
			ear_tag_number = mouse_id_string.split(folder, 1)[1]
		else:
			ear_tag_number = mouse_id_string
			print(f"Folder ({folder}) not found in {mouse_id_string}")	
		#ear_tag_number = mouse_id_string.split(folder, 1)[1] if folder in mouse_id_string else mouse_id_string
		ear_tag_number = ear_tag_number.replace("_", " ").replace(",", " "). replace(".", " ")
		ear_tag_number = " ".join(ear_tag_number.split()).strip()

		cslo_ear_tag_dic[folder] = ear_tag_number
	
	return(cslo_ear_tag_dic)



settings = user_defined_settings()
for key, value in settings.items():
	print(f"{key}: {value}")


