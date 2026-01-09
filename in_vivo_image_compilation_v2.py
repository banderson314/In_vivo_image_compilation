"""
Created by Brandon Anderson

---------------------------
--- Script organization ---
---------------------------
1. Imports
2. Settings dialog box
	Uses tkinter dialog box to have the user imput how they want the compilation document to be organized
	Each dialog box line (or group of lines) is divided into separate classes:
		...
3. find_oct_retina_bounds function
	Function that is used by both the user_defined_settings and ImageCompilation class
4. ImageCompilation class
	Takes the user's settings and processes them into a compilation document, divided into functions:
		...
5. Main code orchestration
	The code the calls the user_defined_settings function and ImageCompilation class
	
"""



"""
---------------------------
--------- Imports ---------
---------------------------
"""

_last_len = 0
def status(msg):
    global _last_len
    pad = max(_last_len - len(msg), 0)
    print("\rStatus: " + msg + " " * pad, end="", flush=True)
    _last_len = len(msg)

status("Importing packages")
import tkinter as tk
from tkinter import filedialog
from tkinter import ttk
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional, Tuple, Literal, ClassVar
import re
import math
import os
import pandas as pd
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont, ImageTk, UnidentifiedImageError
import warnings
warnings.filterwarnings("ignore", message=".*pin_memory.*")
import subprocess
status("Package import complete")
def get_reader():
	"""Return a persistent EasyOCR reader, loading it only once."""
	if not hasattr(get_reader, "reader"):
		status("Loading EasyOCR")
		import easyocr
		get_reader.reader = easyocr.Reader(['en'], verbose=False, gpu=False)
		status("EasyOCR is loaded")
	return get_reader.reader

# Allowed image extensions
image_extensions = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp"}



"""
Things left to do:
Allow for multiple dates
Final save location (and name)
An extra optional dialog box with additional settings such as:
	Margin size
	Background and text color
	Text size

	
Updates you should consider including:
Make margins proportional to images
Text should also be made proportional to images (for now I'm just making OCT images bigger). When fixed, remove the line that says #self.image_width = 640


Bugs:
Removing mice manually doesn't update the row x column numbers
Adding another folder of images resets the df of mice

"""






"""
---------------------------
--- Settings dialog box ---
---------------------------
"""

def user_defined_settings():
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

				# Update the availabe images the user can select (e.g. "BAF", "OCT vertical", etc.)
				images_to_use_frame.determine_what_images_are_available()
			

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
			self.group_order = []

			edit_button = tk.Button(self, text="Edit mouse info", command=self.edit_mouse_info)
			edit_button.grid(row=0, column=0, padx=5)

			cslo_labID_button = tk.Button(self, text="Determine lab ID from cSLO images",
								  command=self.determine_cslo_labID_number)
			cslo_labID_button.grid(row=0, column=1, padx=5)

			group_order_button = tk.Button(self, text="Group order", command=self.edit_group_order)
			group_order_button.grid(row=0, column=2, padx=5)

		
		def on_entry_change(self, *args):
			self.create_blank_df()
			self.add_mice_from_image_files()

		def create_blank_df(self):
			self.df = pd.DataFrame(columns=[
				"cSLO number",
				"Lab ID",
				"Group",
				"Exclude images"
			])


		def add_mice_from_image_files(self):
			# Including mouse numbers found in the files not in the excel spreadsheet
			for mouse in number_of_mice_frame.mice_set:
				if mouse not in self.df["cSLO number"].values:
					# Create a new row with cSLO number set and other columns empty/NaN
					new_row = {
						"cSLO number": mouse,
						"Lab ID": "",
						"Group": "",
						"Exclude images": False
					}
					self.df = pd.concat([self.df, pd.DataFrame([new_row])], ignore_index=True)

		def edit_mouse_info(self):
			top = tk.Toplevel(root)
			top.title("Edit DataFrame")

			entries = {}          # (i, col) -> Entry or BooleanVar
			entry_widgets = {}    # (grid_row, grid_col) -> Entry widget

			# Sorting the dataframe by cSLO number
			self.df = self.df.sort_values(
				by="cSLO number",
				key=pd.to_numeric
			).reset_index(drop=True)

			# Arrow-key navigation 
			def move_focus(event, row, col):
				key = event.keysym

				if key not in ("Up", "Down"):
					return

				# All rows that have Entry widgets
				rows = sorted({r for r, _ in entry_widgets})

				if row not in rows:
					return "break"

				idx = rows.index(row)

				if key == "Down":
					next_row = rows[(idx + 1) % len(rows)]
				else:  # Up
					next_row = rows[(idx - 1) % len(rows)]

				# Only move if the same column exists in the target row
				if (next_row, col) in entry_widgets:
					entry_widgets[(next_row, col)].focus_set()
					entry_widgets[(next_row, col)].icursor("end")

				return "break"


			# Column headers
			for j, col in enumerate(self.df.columns):
				label = tk.Label(top, text=col, font=("Arial", 10, "bold"))
				label.grid(row=0, column=j, padx=2, pady=5)

			# Data rows
			for i, row in self.df.iterrows():
				for j, col in enumerate(self.df.columns):
					if col == "Exclude images":
						var = tk.BooleanVar(value=row[col])
						cb = tk.Checkbutton(top, variable=var)
						cb.grid(row=i + 1, column=j, padx=0, pady=0)
						entries[(i, col)] = var
					else:
						e = tk.Entry(top, justify="center")
						e.grid(row=i + 1, column=j, padx=2, pady=0)
						e.insert(0, row[col])

						entries[(i, col)] = e
						entry_widgets[(i + 1, j)] = e

						# Bind arrow keys
						e.bind("<Up>",    lambda ev, r=i + 1, c=j: move_focus(ev, r, c))
						e.bind("<Down>",  lambda ev, r=i + 1, c=j: move_focus(ev, r, c))


			def save_changes():
				for (i, col), widget in entries.items():
					self.df.at[i, col] = widget.get()
				self.group_order = self.df["Group"].unique().tolist()
				if self.group_order == ['']:
					self.group_order = []

				# Updating the row x column options based off of groups, if it exists
				if self.group_order:
					largest_group_size = self.df['Group'].value_counts().max()
					row_col_frame.update_numbers(largest_group_size)

				top.destroy()

			footer = tk.Frame(top)
			footer.grid(
				row=len(self.df) + 1,
				column=0,
				columnspan=len(self.df.columns),
				pady=10
			)

			save_button = tk.Button(footer, text="Save", command=save_changes)
			save_button.pack(side="left")

			label = tk.Label(
				footer,
				text="Clicking Save will reset user-defined group order"
			)
			label.pack(side="left", padx=10)


		def determine_labID_in_cslo_images(self, base_directory):
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
				ear_tag_number = ear_tag_number.replace("_", " ").replace(",", " "). replace(".", " ")
				ear_tag_number = " ".join(ear_tag_number.split()).strip()

				cslo_ear_tag_dic[folder] = ear_tag_number
			
			return(cslo_ear_tag_dic)



		def determine_cslo_labID_number(self):
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
				self.cslo_ear_tag_dic = self.determine_labID_in_cslo_images(directory)
				for cslo_num, et_value in self.cslo_ear_tag_dic.items():
					# check if the cSLO number exists in the df
					if cslo_num in self.df["cSLO number"].values:
						# update the Lab ID
						self.df.loc[self.df["cSLO number"] == cslo_num, "Lab ID"] = et_value
					else:
						# add a new row
						new_row = {"cSLO number": cslo_num, "Lab ID": et_value}
						self.df = pd.concat([self.df, pd.DataFrame([new_row])], ignore_index=True)
			self.edit_mouse_info()


		def edit_group_order(self):
			class GroupOrderDialog:
				def __init__(self, root, groups):
					self.root = root
					self.groups = groups[:]
					self.rows = []
					self.drag_data = None

					self.win = tk.Toplevel(root)
					self.win.title("Order groups")
					self.win.minsize(150, 0)
					self.win.transient(root)
					self.win.grab_set()

					self.container = tk.Frame(self.win)
					self.container.pack(fill="both", expand=True, padx=10, pady=10)

					self.build_rows()

					btn = tk.Button(self.win, text="OK", command=self.on_ok)
					btn.pack(pady=6)

				# ---------- UI ----------
				def build_rows(self):
					for group in self.groups:
						self.add_row(group)

				def add_row(self, text):
					row = tk.Frame(self.container)
					row.pack(fill="x", pady=2)

					handle = tk.Label(row, text="☰", cursor="fleur")
					handle.pack(side="left", padx=(0, 6))

					label = tk.Label(row, text=text, anchor="w")
					label.pack(side="left", fill="x", expand=True)

					# Drag bindings ONLY on handle
					handle.bind("<Button-1>", self.start_drag)
					handle.bind("<B1-Motion>", self.do_drag)
					handle.bind("<ButtonRelease-1>", self.stop_drag)

					self.rows.append(row)

				def repack_rows(self):
					for row in self.rows:
						row.pack_forget()
						row.pack(fill="x", pady=2)

				def get_row_index(self, row):
					return self.rows.index(row)

				# ---------- Drag logic ----------
				def start_drag(self, event):
					widget = event.widget.master

					self.drag_data = {
						"widget": widget,
						"start_y": event.y_root,
						"orig_index": self.get_row_index(widget),
						"original_colors": {
							widget: widget.cget("bg"),
							**{child: child.cget("bg") for child in widget.winfo_children()}
						}
					}

					widget.lift()
					widget.config(bg="#d0d0d0")
					for child in widget.winfo_children():
						child.config(bg="#d0d0d0")

				def do_drag(self, event):
					if not self.drag_data:
						return

					widget = self.drag_data["widget"]
					y = event.y_root

					hover_index = None
					for i, row in enumerate(self.rows):
						if row == widget:
							continue
						ry = row.winfo_rooty()
						rh = row.winfo_height()
						if ry < y < ry + rh:
							hover_index = i
							break

					current_index = self.get_row_index(widget)
					if hover_index is not None and hover_index != current_index:
						self.rows.insert(hover_index, self.rows.pop(current_index))
						self.groups.insert(hover_index, self.groups.pop(current_index))
						self.repack_rows()

				def stop_drag(self, event):
					widget = self.drag_data["widget"]
					original_colors = self.drag_data["original_colors"]

					widget.config(bg=original_colors[widget])
					for child in widget.winfo_children():
						child.config(bg=original_colors[child])

					self.drag_data = None

				# ---------- Result ----------
				def on_ok(self):
					self.win.destroy()

				def get_result(self):
					return self.groups

			if self.group_order == []:
				self.group_order = self.df["Group"].unique().tolist()

			dialog = GroupOrderDialog(root, self.group_order)
			root.wait_window(dialog.win)

			self.group_order = dialog.get_result()

		def get_data(self):
			self.df_to_export = self.df
			
			# Remove any mice that there aren't any image files of
			self.df_to_export = self.df_to_export[self.df_to_export["cSLO number"].isin(number_of_mice_frame.mice_set)]

			# Remove any mice that were marked to be excluded
			self.df_to_export = self.df_to_export[self.df_to_export["Exclude images"] != True]

			# Create dictionary with cSLO numbers (key) and [Lab ID, cage, group]
			mouse_info_dic = {
				row["cSLO number"]: (row["Lab ID"], row["Group"])
				for _, row in self.df_to_export.iterrows()
			}

			# Sort the dictionary
			mouse_info_dic = dict(sorted(mouse_info_dic.items()))

			return {
				"mouse_info_dic": mouse_info_dic,
				"group_order": self.group_order
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
			self.label = tk.Label(self, text="Row x column:")
			self.label.grid(row=0, column=0, padx=5, pady=5, sticky="w")

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

			if mouse_info_frame.group_order:
				self.label.config(text="Row x column per group:")
			

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

			# Lab ID checkbox
			self.labID_var = tk.BooleanVar(value=False)
			labID_cb = tk.Checkbutton(self, text="Lab IDs", variable=self.labID_var)
			labID_cb.grid(row=0, column=2, padx=5, pady=0, sticky="w")

			# Crop cSLO text checkbox
			self.crop_cslo_text_var = tk.BooleanVar(value=True)
			crop_cslo_text_cb = tk.Checkbutton(self, text="Crop the text off of cSLO images",
											variable=self.crop_cslo_text_var)
			crop_cslo_text_cb.grid(row=1, column=0, columnspan=3, padx=5, pady=0, sticky="w")

		def get_data(self):
			self.cslo_number_bool = self.cslo_number_var.get()
			self.labID_bool = self.labID_var.get()
			self.crop_cslo_text_bool = self.crop_cslo_text_var.get()

			return {
				"cslo_number_bool": self.cslo_number_bool,
				"labID_bool": self.labID_bool,
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

		def oct_crop_checkbox(self):
			if self.oct_crop_var.get():
				self.oct_crop_entry.config(state="normal")
				
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
						self.oct_crop_entry.delete(0, tk.END)
						self.oct_crop_entry.insert(0, image_height)
					else:
						self.oct_crop_entry.insert(0, "480")

			else:
				self.oct_crop_entry.delete(0, tk.END)
				self.oct_crop_entry.config(state="disabled")
		

		def find_minimum_oct_height(self):
			oct_heights = []

			self.available_directories = directory_frame.get_data()["directories"]

			for directory in self.available_directories:
				if directory[1] == "oct":
					directory_path = directory[0]
				else:
					continue
			
				image_files = [
					f for f in os.listdir(directory_path)
					if f.lower().endswith(tuple(image_extensions)) and os.path.isfile(os.path.join(directory_path, f))
				]

				for image_file in image_files:
					# Only including images if the user hasn't removed them
					cslo_number = image_file.split("_")[0]
					if cslo_number in mouse_info_frame.get_data()["mouse_info_dic"]:
						image_path = os.path.join(directory_path, image_file)
						image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
						top, bottom = find_oct_retina_bounds(image)
						height = abs(bottom-top)
						oct_heights.append(height)
			
			if len(oct_heights) > 0:
				self.smallest_possible_height = max(oct_heights)
				self.oct_crop_entry.delete(0, tk.END)
				self.oct_crop_entry.insert(0, self.smallest_possible_height)
			else:
				self.oct_crop_entry.delete(0, tk.END)



		def get_data(self):
			oct_height = self.oct_crop_entry.get()
			oct_crop_bool = self.oct_crop_var.get()

			return {
				"oct_crop_bool": oct_crop_bool,
				"oct_height": oct_height
			}


	class ImagesToUseFrame(tk.Frame):
		def __init__(self, parent):
			super().__init__(parent)

			title = tk.Label(self, text="Images to use and the order they are arranged in:")
			title.grid(row=0, column=0, columnspan=2, sticky="w", padx=5, pady=(2,5))

			# --- Main area: Available | Selected side by side ---
			main_frame = tk.Frame(self)
			main_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=(17,5))
			main_frame.columnconfigure(0, weight=1)
			main_frame.columnconfigure(1, weight=1)

			# Available list
			available_frame = tk.Frame(main_frame)
			available_frame.grid(row=0, column=0, sticky="new", padx=(0, 15))

			tk.Label(available_frame, text="Available image types").grid(row=0, column=0, sticky="w")
			self.available_listbox = tk.Listbox(available_frame, selectmode="browse", height=1, width=25)
			self.available_listbox.grid(row=1, column=0, sticky="nsew", pady=3)
			self.available_listbox.bind("<Double-Button-1>", self.add_selected_from_listbox)
			self.available_listbox.config(selectbackground="SystemHighlight", activestyle="none")

			# Scrollbar (initially hidden)
			self.available_scrollbar = tk.Scrollbar(available_frame, orient="vertical")
			self.available_listbox.config(yscrollcommand=self.available_scrollbar.set)
			self.available_scrollbar.config(command=self.available_listbox.yview)

			# Selected list (container with draggable rows)
			selected_frame = tk.Frame(main_frame)
			selected_frame.grid(row=0, column=1, sticky="nsew")
			#selected_frame.rowconfigure(1, weight=1)

			tk.Label(selected_frame, text="Selected images (rename or reorder)").grid(row=0, column=0, sticky="w")
			self.selected_frame = tk.Frame(selected_frame)
			self.selected_frame.grid(row=1, column=0, sticky="nsew")

			self.available_image_types = []
			self.selected_image_types = []
			self.rows = []
			self.drag_data = None

			
		# --- Populate available options ---
		def determine_what_images_are_available(self):
			directories = directory_frame.get_data()["directories"]
			self.available_image_types_set = set()

			for directory, image_type in directories:
				if image_type == "oct":
					image_files = [
						f for f in os.listdir(directory)
						if os.path.isfile(os.path.join(directory, f))
						and os.path.splitext(f)[1].lower() in image_extensions
					]
					for image_file in image_files:
						oct_type = "OCT " + image_file.split("_")[2]
						self.available_image_types_set.add(oct_type)
				
				elif image_type =="cslo":
					image_files = []
					
					# Grabbing all cSLO file names
					for subdir, dirs, files in os.walk(directory):
						if os.path.basename(subdir) in {"OD", "OS"}:
							for f in files:
								if os.path.splitext(f)[1].lower() in image_extensions:
									image_files.append(f)
					
					cslo_images_dic = {}
					for image in image_files:
						image_base = os.path.splitext(image)[0]
						image_number, mouse_number, eye, image_type = image_base.split("_")
						mouse_eye = mouse_number + "_" + eye

						if mouse_eye not in cslo_images_dic:
							cslo_images_dic[mouse_eye] = {}

						if image_type not in cslo_images_dic[mouse_eye]:
							cslo_images_dic[mouse_eye][image_type] = 0

						cslo_images_dic[mouse_eye][image_type] += 1
					
					max_counts = {}
					for mouse_eye, counts in cslo_images_dic.items():
						for image_type, count in counts.items():
							if image_type not in max_counts or count > max_counts[image_type]:
								max_counts[image_type] = count

					def ordinal(n):
						if 10 <= n % 100 <= 20:
							suffix = "th"
						else:
							suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
						return f"{n}{suffix}"

					for image_type, count in max_counts.items():
						image_type = "cSLO " + image_type
						if int(count) == 1:
							self.available_image_types_set.add(image_type)
						else:
							self.available_image_types_set.discard(image_type)
							i = 0
							for i in range(int(count)):
								image_type_ammended = f"{image_type} ({ordinal(i+1)})"
								self.available_image_types_set.add(image_type_ammended)
								self.available_image_types_set.add(f"{image_type} [select]")
						


			self.available_image_types = sorted(list(self.available_image_types_set))
			self.refresh_available_list()


		def refresh_available_list(self):
			"""Update available listbox items and manage scrollbar visibility."""
			# Clear listbox
			self.available_listbox.delete(0, tk.END)
			
			# Create a set of the original names already selected
			selected_originals = {orig for orig, _ in self.selected_image_types}

			# Insert items that are not yet selected
			for item in self.available_image_types:
				if item not in selected_originals:
					self.available_listbox.insert(tk.END, item)

			# Adjust height
			num_items = self.available_listbox.size()
			self.available_listbox.config(height=min(num_items, 10))  # max height = 10

			# Show or hide scrollbar
			if num_items > 10:
				self.available_scrollbar.grid(row=1, column=1, sticky="ns")
			else:
				self.available_scrollbar.grid_forget()


		# --- Add/Remove logic ---
		def add_selected_from_listbox(self, event=None):
			selection = self.available_listbox.curselection()
			if not selection:
				return
			
			value = self.available_listbox.get(selection[0])
			self.available_listbox.delete(selection[0])
			self.selected_image_types.append((value, value))  # (original, current/custom)
			self.add_label_row(value)

			# Refresh available list to update height and scrollbar
			self.refresh_available_list()



		def add_label_row(self, selection):
			frame = tk.Frame(self.selected_frame)
			frame.grid(sticky="ew", pady=0)
			frame.columnconfigure(1, weight=1)

			handle = tk.Label(frame, text="≡", font=("Arial", 10), cursor="fleur")
			handle.grid(row=0, column=0, padx=(0,2), pady=0)
			handle.bind("<Button-1>", self.start_drag)
			handle.bind("<B1-Motion>", self.do_drag)
			handle.bind("<ButtonRelease-1>", self.stop_drag)

			label = tk.Label(frame, text=selection, anchor="w")
			label.grid(row=0, column=1, sticky="ew", pady=0)

			remove_btn = tk.Button(frame, text="✕", relief="flat", bd=0,
								command=lambda f=frame, s=selection: self.remove_row(f, s))
			remove_btn.grid(row=0, column=3, padx=(2,0), pady=0)


			# Determining initial custom name
			custom_name = selection
			if custom_name[:5] == "cSLO ":
				custom_name = custom_name[5:]
			elif custom_name[:4] == "OCT ":
				custom_name = custom_name[4:]
			if custom_name[-9:] == " [select]":
				custom_name = custom_name[:-9]
			ordinal_format = r" \(\d+(st|nd|rd|th)\)$"
			custom_name = re.sub(ordinal_format, "", custom_name)
			custom_name = custom_name[0].upper() + custom_name[1:]

			image_type_name_var = tk.StringVar(value=custom_name)
			entry_box = tk.Entry(frame, textvariable=image_type_name_var, width=15)
			entry_box.grid(row=0, column=2, padx=(5,0))

			# Update self.selected_image_types when entry changes
			def on_entry_change(*args):
				for i, (orig, custom) in enumerate(self.selected_image_types):
					if orig == selection:
						self.selected_image_types[i] = (orig, image_type_name_var.get())
						break

			image_type_name_var.trace_add("write", on_entry_change)
			on_entry_change()	# Force initial update


			self.rows.append((frame, selection))
			self.repack_rows()



		def remove_row(self, frame, selection):
			for i, (f, sel) in enumerate(self.rows):
				if f == frame:
					f.destroy()
					del self.rows[i]
					break

			# remove from selected_image_types (match by first element)
			self.selected_image_types = [
				pair for pair in self.selected_image_types if pair[0] != selection
			]

			self.refresh_available_list()
			self.repack_rows()




		def repack_rows(self):
			for i, (f, _) in enumerate(self.rows):
				f.grid(row=i, column=0, sticky="ew", pady=0)


		# --- Drag & reorder logic ---
		def start_drag(self, event):
			widget = event.widget.master
			self.drag_data = {
				"widget": widget,
				"start_y": event.y_root,
				"orig_index": self.get_row_index(widget),
				"original_colors": {
					widget: widget.cget("bg"),
					**{child: child.cget("bg") for child in widget.winfo_children()}
					}
			}
			widget.lift()
			widget.config(bg="#929292")
			for child in widget.winfo_children():
				child.config(bg="#929292")

		def do_drag(self, event):
			if not self.drag_data:
				return
			widget = self.drag_data["widget"]
			y = event.y_root
			widget.lift()

			hover_index = None
			for i, (f, _) in enumerate(self.rows):
				if f == widget:
					continue
				fy = f.winfo_rooty()
				fh = f.winfo_height()
				if fy < y < fy + fh:
					hover_index = i
					break

			current_index = self.get_row_index(widget)
			if hover_index is not None and hover_index != current_index:
				self.rows.insert(hover_index, self.rows.pop(current_index))
				self.selected_image_types.insert(hover_index, self.selected_image_types.pop(current_index))
				self.repack_rows()


		def stop_drag(self, event):
			widget = event.widget.master
			original_colors = self.drag_data["original_colors"]

			# Restore frame color
			if widget in original_colors:
				widget.config(bg=original_colors[widget])

			# Restore each child’s color
			for child in widget.winfo_children():
				if child in original_colors:
					child.config(bg=original_colors[child])
			self.drag_data = None


		def get_row_index(self, frame):
			for i, (f, _) in enumerate(self.rows):
				if f == frame:
					return i
			return None


		def get_data(self):
			return {"images_to_use": self.selected_image_types}


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

			# Settings button
			settings_button = tk.Button(self, text="Print Settings", command=self.grab_settings)
			settings_button.grid(row=0, column=3, padx=5)


		def collect_settings(self):
			self.settings = {}
			self.settings.update(directory_frame.get_data())
			self.settings.update(title_frame.get_data())
			self.settings.update(row_col_frame.get_data())
			self.settings.update(mouse_info_frame.get_data())
			self.settings.update(number_and_cslo_crop_frame.get_data())
			self.settings.update(oct_crop_frame.get_data())
			self.settings.update(images_to_use_frame.get_data())

			
		def preview_layout(self):
			self.collect_settings()
			compiler = ImageCompilation(self.settings, mode="preview_layout")
			compiler.run()

		def preview_layout_and_images(self):
			self.collect_settings()
			compiler = ImageCompilation(self.settings, mode="preview_layout_and_images")
			compiler.run()
			
		
	
		def on_ok_click(self):
			self.collect_settings()
			root.destroy()

		def grab_settings(self):
			self.collect_settings()
			
			for key, value in self.settings.items():
				print(f"{key}: {value}")




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
	mouse_info_frame.pack(anchor='n', pady=3)
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
	confirmation_frame = ConfirmationFrame(root)
	confirmation_frame.pack(anchor='s', pady=10)

	root.mainloop()
	return confirmation_frame.settings



"""
----------------------------------
--- Find OCT retina boundaries ---
----------------------------------
"""

def find_oct_retina_bounds(img):
	"""Return the topmost and bottommost pixel positions of the retina."""
	# Convert to grayscale if needed
	if img.ndim == 3:
		img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

	# Flatten along width (take max across columns) to get brightness by row
	#row_max = img.max(axis=1).astype(float)
	row_brightness = np.percentile(img, 95, axis=1).astype(float)

	# Compute adaptive threshold based on overall brightness
	mean = np.mean(img)
	std = np.std(img)
	cutoff = max(mean + std, 50)

	# Find where the retina (bright region) exists
	#bright_rows = np.where(row_max > cutoff)[0]
	bright_rows = np.where(row_brightness > cutoff)[0]

	if bright_rows.size == 0:
		return img.shape[0], 0  # nothing bright enough found

	# Return absolute top and bottom of the bright region
	top = int(bright_rows.min())
	bottom = int(bright_rows.max())
	return top, bottom



"""
---------------------------------
--- Compiling images together ---
---------------------------------
"""

class ImageCompilation:
	def __init__(self, settings=None, mode="full"):
		self.settings = settings or {}
		self.mode = mode
		self.mouse_image_list = {}

		# Creating dictionary of mouse numbers
		# This will be filled in with file paths in the build_mouse_image_list() function
		for mouse_number in self.settings['mouse_info_dic']:
			self.mouse_image_list[mouse_number] = {
					"OD": {"cslo": [], "oct": []},
					"OS": {"cslo": [], "oct": []}
				}
		self.mouse_info_dic = self.settings['mouse_info_dic']

		# Modify user input of image modalities to use into something more usable
		# Ex. ('cSLO BAF (1st)', 'BAF') --> class(imager, image_type_name, select_required, multiple_index, custom_name)
		original_images_to_use = self.settings.get('images_to_use', [])
		self.image_type_objects = [self.ImageType.from_tuple(t) for t in original_images_to_use]

		# -- Determining cslo and oct image sizes and assigning images as examples --
		# First cslo images
		self.cslo_width = 0
		self.cslo_height = 0
		for directory, imager in self.settings['directories']:
			if imager == "cslo" and not hasattr(self, "example_cslo_image"):
				# Get the first subdirectory in the root
				first_subdir = next(
					os.path.join(directory, d)
					for d in os.listdir(directory)
					if os.path.isdir(os.path.join(directory, d))
				)
				# Get the first subdirectory inside that, which should be "OD" or "OS"
				second_subdir = next(
					os.path.join(first_subdir, d)
					for d in os.listdir(first_subdir)
					if os.path.isdir(os.path.join(first_subdir, d)) and d in {"OD", "OS"}
				)
				directory = second_subdir

				files = [
					f for f in os.listdir(directory)
					if os.path.splitext(f)[1].lower() in image_extensions
				]

				example_path = os.path.join(directory, files[0])
				try:
					self.example_cslo_image = Image.open(example_path)
					self.cslo_width, self.cslo_height = self.example_cslo_image.size
					if self.settings['crop_cslo_text_bool']:	# If the user specified that the text should be cropped off (will result in a square)
						self.cslo_height = self.cslo_width
						self.example_cslo_image = self.example_cslo_image.crop((0, 0, self.cslo_width, self.cslo_height))
				except (FileNotFoundError, UnidentifiedImageError):
					self.example_cslo_image = None
					self.cslo_width, self.cslo_height = 768, 868
					if self.settings['crop_cslo_text_bool']:
						self.cslo_height = 768
				
				if hasattr(self, "example_cslo_image"):
					self.image_width = self.cslo_width
					break
		
		# Then oct images
		self.oct_width = 0
		self.oct_height = 0
		for directory, imager in self.settings['directories']:
			if imager == "oct" and not hasattr(self, "example_oct_image"):
				files = [
					f for f in os.listdir(directory)
					if os.path.splitext(f)[1].lower() in image_extensions
				]

				example_path = os.path.join(directory, files[0])
				try:
					self.example_oct_image = Image.open(example_path)
					self.oct_width, self.oct_height = self.example_oct_image.size
				except (FileNotFoundError, UnidentifiedImageError):
					self.example_oct_image = None
					self.oct_width, self.oct_height = 640, 480
				if self.settings['oct_crop_bool']:	# If the user has specified a specific height should be used
					self.oct_height = int(self.settings['oct_height'])

				# Resizing if needed
				if self.cslo_width != 0:		# Only bothering if cslo width has been established
					if self.oct_width != self.cslo_width:
						new_width = self.cslo_width
						w, h = self.example_oct_image.size
						if self.settings['oct_crop_bool']:
							h = int(self.settings['oct_height'])
						aspect_ratio = h / w
						new_height = int(new_width * aspect_ratio)
						self.example_oct_image = self.example_oct_image.resize((new_width, new_height), Image.LANCZOS)
						self.oct_width, self.oct_height = new_width, new_height
				else:
					self.image_width = self.oct_width
					
					# Delete the following once you have made the text size dynamically change based off of image size
					self.image_width = 768
					new_width = self.image_width
					w, h = self.example_oct_image.size
					if self.settings['oct_crop_bool']:
						h = int(self.settings['oct_height'])
					aspect_ratio = h / w
					new_height = int(new_width * aspect_ratio)
					self.example_oct_image = self.example_oct_image.resize((new_width, new_height), Image.LANCZOS)
					self.oct_width, self.oct_height = new_width, new_height


				# Stop looping once oct found
				if hasattr(self, "example_oct_image"):
					break
			
					
	
	@dataclass
	class ImageType:
		imager: str
		image_type_name: str
		select_required: bool = False
		multiple_index: int | None = None
		custom_name: str | None = None

		@classmethod
		def from_tuple(cls, pair: tuple[str, str]):
			"""Parse (image_type_string, custom_name) into an ImageType instance."""
			image_type_str, custom_name = pair
			imager, remainder = image_type_str.split(" ", 1)  # e.g. 'cSLO', 'BAF [select]'
			select_required = False
			multiple_index = None

			# Check for ordinal format like " (1st)"
			ordinal_pattern = r" \((\d+)(st|nd|rd|th)\)$"
			match = re.search(ordinal_pattern, remainder)
			if match:
				multiple_index = int(match.group(1)) - 1
				remainder = re.sub(ordinal_pattern, "", remainder)

			# Check for "[select]" tag
			if remainder.endswith(" [select]"):
				select_required = True
				remainder = remainder[:-9]

			return cls(
				imager=imager.lower(),
				image_type_name=remainder.strip(),
				select_required=select_required,
				multiple_index=multiple_index,
				custom_name=custom_name,
			)

		
	@staticmethod
	def convert_path_to_base_name_and_parts(path, cslo_or_oct):
		base_name = os.path.splitext(os.path.basename(path))[0]
		parts_of_name = base_name.split("_")

		if cslo_or_oct == "cslo":
			image_number = parts_of_name[0]
			mouse_number = parts_of_name[1]
			eye = parts_of_name[2]
			modality = parts_of_name[3]
		elif cslo_or_oct == "oct":
			image_number = 000
			mouse_number = parts_of_name[0]
			eye = parts_of_name[1]
			modality = parts_of_name[2]
		else:
			image_number = ""
			mouse_number = ""
			eye = ""
			modality = ""

		return base_name, image_number, mouse_number, eye, modality


	@staticmethod
	def measure_text(font, text):
		x0, y0, x1, y1 = font.getbbox(text)
		return (x1 - x0), (y1 - y0), -y0   # width, height, baseline offset

	# ====================================================
	# SETTINGS
	# ====================================================
	def add_non_user_defined_settings(self):
		"""Add additional settings to self.settings"""
		additional_settings = {
			'background_color': (15, 15, 15),	# black
			'text_color': (255, 255, 255),				# white
			'final_product_file_path': "C:/Users/bran314/Desktop/image_compilation.jpg",
			'column_margin_size': 45,
			'row_margin_size': 150,
			'title_font': ImageFont.load_default(size=225),
			'subtitle_font': ImageFont.load_default(size=150),
			'group_font': ImageFont.load_default(size=185),
			'heading_font': ImageFont.load_default(size=150),
			'subheading_font': ImageFont.load_default(size=120),
			'outer_margin_size': 50
		}

		self.settings.update(additional_settings)

	# ====================================================
	# BUILD IMAGE LIST
	# ====================================================
	def build_mouse_image_list(self):
		"""Define and  refine the mouse image list."""
		def create_list_of_all_image_paths():
			# Dividing directories into cSLO and OCT
			cslo_directories = []
			oct_directories = []
			for directory, image_type in self.settings['directories']:
				if image_type == "cslo":
					cslo_directories.append(directory)
				elif image_type == "oct":
					oct_directories.append(directory)
			
			# Creating a list of file paths for cSLO images
			cslo_image_file_paths = []
			for directory in cslo_directories:
				mice = [f for f in os.listdir(directory) if os.path.isdir(os.path.join(directory, f))]
				mice_directories = []
				
				# Excluding any mice that the user may have manually removed
				for mouse in mice:
					if mouse in self.settings["mouse_info_dic"]:
						mice_directories.append(os.path.join(directory, mouse))
				
				for mouse_directory in mice_directories:
					for root, dirs, files in os.walk(mouse_directory):	# recursively walk all subfolders
						folder_name = os.path.basename(root)
						if folder_name in ("OD", "OS"):
							for f in files:
								if f.lower().endswith(tuple(image_extensions)):
									cslo_image_file_paths.append(os.path.join(root, f))
			
			# Creating a list of file paths for OCT images
			oct_image_file_paths = []
			for directory in oct_directories:
				potential_oct_image_files = [f for f in os.listdir(directory)
							if f.lower().endswith(tuple(image_extensions))]
				
				for file in potential_oct_image_files:
					if file.split("_")[0] in self.settings["mouse_info_dic"]:
						oct_image_file_paths.append(os.path.join(directory, file))
			

			return cslo_image_file_paths, oct_image_file_paths


		def remove_unneeded_images(list_of_file_paths, cslo_or_oct):
			new_list_of_file_paths = []

			# Looping through all file paths and only including the needed ones
			image_modalities_to_use = {obj.image_type_name for obj in self.image_type_objects}
			for path in list_of_file_paths:
				_, _, mouse_number, _, modality = self.convert_path_to_base_name_and_parts(path, cslo_or_oct)
				
				# Remove mice that had previously been excluded
				if mouse_number not in self.settings["mouse_info_dic"]:
					continue		

				# Remove image modalities that are not needed
				if modality not in image_modalities_to_use:
					continue
				# Note that if there are multiple of one modality, all of them will be included. This will be filtered properly when the images are being inserted.

				new_list_of_file_paths.append(path)

			return new_list_of_file_paths


		def create_image_path_dic(list_of_file_paths, cslo_or_oct):
			for path in list_of_file_paths:
				_, _, mouse_number, eye, _ = self.convert_path_to_base_name_and_parts(path, cslo_or_oct)
				self.mouse_image_list[mouse_number][eye][cslo_or_oct].append(path)

		cslo_image_file_paths, oct_image_file_paths = create_list_of_all_image_paths()

		cslo_image_file_paths = remove_unneeded_images(cslo_image_file_paths, "cslo")
		oct_image_file_paths = remove_unneeded_images(oct_image_file_paths, "oct")
		
		create_image_path_dic(cslo_image_file_paths, "cslo")
		create_image_path_dic(oct_image_file_paths, "oct")



	# ====================================================
	# IMAGE ASSEMBLY
	# ====================================================
	def assemble_mouse_image_grid(self, mouse_id, mouse_grid_mode="Normal"):
		"""Creates image compilation and metadata for one mouse"""
		def crop_cslo_image(image):
			# Crops the text off of the bottom of the image
			width, height = image.size
			cropped_image = image.crop((0, 0, width, width))

			return cropped_image
		
		def crop_oct_image(image):
			desired_oct_height = int(self.settings['oct_height'])

			# Case 1: Already correct height
			if image.height == desired_oct_height:
				return image
			
			# Determine where the center of the retina is
			# Convert PIL → NumPy
			img = np.array(image)
			if img.ndim == 3:
				# Normalize color channel order to BGR for OpenCV
				if img.shape[2] == 4:
					img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
				else:
					img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
			
			top_of_retina, bottom_of_retina = find_oct_retina_bounds(img)
			center_of_retina = (top_of_retina + bottom_of_retina) // 2

			# Case 2: Crop if taller
			if image.height > desired_oct_height:
				half_height = desired_oct_height // 2
				top_crop = max(center_of_retina - half_height, 0)
				bottom_crop = top_crop + desired_oct_height

				# Adjust if bottom exceeds bounds
				if bottom_crop > image.height:
					bottom_crop = image.height
					top_crop = bottom_crop - desired_oct_height

				return image.crop((0, top_crop, image.width, bottom_crop))

			# Case 3: Pad if shorter
			new_img = Image.new("RGB", (image.width, desired_oct_height), color="black")
			y_offset = (desired_oct_height - image.height) // 2
			new_img.paste(image, (0, y_offset))
			return new_img
			
			

		def user_choose_which_images_to_use(image_path_list, title):
			def image_click(image_path):
				root.destroy()
				root.selected_image = image_path

			def select_none(event=None):
				root.destroy()
				root.selected_image = None

			def on_close_window(event=None):
				root.destroy()
				exit()

			def center_dialog_box(window):
				window.update_idletasks()
				width = window.winfo_width()
				height = window.winfo_height()
				screen_width = window.winfo_screenwidth()
				screen_height = window.winfo_screenheight()
				x_coordinate = (screen_width - width) // 2
				y_coordinate = (screen_height - height) // 2
				window.geometry(f"{width}x{height}+{x_coordinate}+{y_coordinate}")


			# Root window
			if tk._default_root is None:
				root = tk.Tk()
			else:
				root = tk.Toplevel()
			root.title(title)
			root.protocol("WM_DELETE_WINDOW", on_close_window)
			root.config(bg="black")

			# Keep references to images
			resized_images = []

			# Determine a uniform size based on first image
			sample_image = Image.open(image_path_list[0])
			uniform_width = int(sample_image.width * 0.5)
			uniform_height = int(sample_image.height * 0.5)
			
			# Determining the size and grid layout of the images
			usable_screen_width = int(root.winfo_screenwidth()*0.95)
			usable_screen_height = int(root.winfo_screenheight()*0.95)
			max_col_count = usable_screen_width // uniform_width
			max_row_count = usable_screen_height // uniform_height
			squares_needed = len(image_path_list)+1
			while squares_needed > (max_col_count * max_row_count):
				uniform_width = int(uniform_width * 0.95)
				uniform_height = int(uniform_height * 0.95)
				max_col_count = int(usable_screen_width // uniform_width)
				max_row_count = usable_screen_height // uniform_height
			

			# Load and display images
			row, col = 0, 0
			for path in image_path_list:
				original_image = Image.open(path)
				resized_image = original_image.resize((uniform_width, uniform_height))
				photo = ImageTk.PhotoImage(resized_image)
				resized_images.append(photo)
				label = tk.Label(root, image=photo)
				label.image = photo
				label.grid(row=row, column=col, padx=0, pady=0)
				label.bind("<Button-1>", lambda event, image_path=path: image_click(image_path))
				col += 1
				if col == max_col_count:
					row += 1
					col = 0

			# Add the "Select none" box
			none_canvas = tk.Canvas(root, width=uniform_width, height=uniform_height, bg="black")
			none_canvas.create_text(
				uniform_width // 2,
				uniform_height // 2,
				text="Select none",
				fill="white",
				font=("Arial", 14)
			)
			none_canvas.grid(row=row, column=col, padx=0, pady=0)
			none_canvas.bind("<Button-1>", select_none)


			# Bind Escape key
			root.bind("<Escape>", on_close_window)

			# Center the window
			root.after(10, lambda: center_dialog_box(root))

			# Start main loop
			root.mainloop()

			return root.selected_image if hasattr(root, 'selected_image') else None


		def create_single_mouse_canvas():
			cslo_count, oct_count = 0, 0
			for image_modality in self.image_type_objects:
				if image_modality.imager == "cslo":
					cslo_count += 1
				elif image_modality.imager == "oct":
					oct_count += 1
			
			canvas_width = self.image_width * 2	# 2x because OD and OS
			canvas_height = (self.cslo_height * cslo_count) + (self.oct_height * oct_count)
			canvas = Image.new("RGB", (canvas_width, canvas_height), color="black")

			return canvas

		


		# -- Main body of this function --
		# Will take one mouse number (mouse_id) and loop through all images to generate a canvas with the chosen images compiled together
		
		# Early return
		if mouse_id == "return_canvas_only":
			blank_mouse_canvas_no_text = create_single_mouse_canvas()
			return blank_mouse_canvas_no_text

		# Initial canvas with only images (no headings)
		individual_mouse_canvas_images_only = create_single_mouse_canvas()


		# -- Creating the text heading area --
		# Fonts
		heading_font = self.settings['heading_font']
		subheading_font = self.settings['subheading_font']

		# Compute a consistent height for heading text (fixed)
		_, heading_h, heading_offset = self.measure_text(heading_font, "Hpqy")  # includes ascenders & descenders

		# Gaps
		gap_before_ID_heading = 10
		gap_after_ID_heading = 15
		gap_after_od_os = 25


		# Create mouse number text (but not draw yet)
		use_cslo_number_heading = self.settings['cslo_number_bool']
		use_labID_heading = self.settings['labID_bool']
		if use_cslo_number_heading:							# If user selected to use the cSLO number
			ID_heading_text = mouse_id
		elif use_labID_heading:								# If user instead selected to use the lab ID
			labID = self.mouse_info_dic[mouse_id][0]
			ID_heading_text = labID
		else:												# If user selected to not use either number (will still put a blank space)
			ID_heading_text = ""
		ID_heading_w, ID_heading_h, baseline_offset = self.measure_text(heading_font, ID_heading_text)
		ID_heading_x = (individual_mouse_canvas_images_only.width - ID_heading_w) // 2
		ID_heading_y = gap_before_ID_heading + baseline_offset
		ID_heading_bottom = gap_before_ID_heading + heading_h

		additional_heading_text = None
		if use_cslo_number_heading and use_labID_heading:	# If both cSLO number and lab ID are to be used
			labID = self.mouse_info_dic[mouse_id][0]
			additional_heading_text = f"({labID})"
			additional_ID_heading_w, _, additional_baseline_offset = self.measure_text(subheading_font, additional_heading_text)
			_, additional_ID_heading_h, _ = self.measure_text(heading_font, "Hpqy")
			additional_ID_heading_x = (individual_mouse_canvas_images_only.width - additional_ID_heading_w) // 2
			additional_ID_heading_y = ID_heading_bottom + gap_after_ID_heading + additional_baseline_offset
			ID_heading_bottom = additional_ID_heading_y + additional_ID_heading_h


		# Create OD and OS text (but not draw yet)
		od_w, od_h, od_offset = self.measure_text(subheading_font, "OD")
		od_x = (self.image_width - od_w) // 2
		os_x = od_x + self.image_width
		od_y = ID_heading_bottom + gap_after_ID_heading
		os_y = od_y
		
		# Create new canvas with heading area
		self.total_heading_height = od_y + od_h + gap_after_od_os
		new_height = individual_mouse_canvas_images_only.height + self.total_heading_height
		new_width = individual_mouse_canvas_images_only.width
		new_canvas = Image.new("RGB", (new_width, new_height), color=self.settings['background_color'])
		new_canvas.paste(individual_mouse_canvas_images_only, (0, self.total_heading_height))
		individual_mouse_canvas = new_canvas


		# Draw heading texts
		draw = ImageDraw.Draw(individual_mouse_canvas)
		draw.text((ID_heading_x, ID_heading_y), 
			ID_heading_text, font=heading_font, fill=self.settings['text_color'])
		if additional_heading_text:
			draw.text((additional_ID_heading_x, additional_ID_heading_y), 
			additional_heading_text, font=subheading_font, fill=self.settings['text_color'])
		draw.text((od_x, od_y + od_offset), 
			"OD", font=subheading_font, fill=self.settings['text_color'])
		draw.text((os_x, os_y + od_offset), 
			"OS", font=subheading_font, fill=self.settings['text_color'])


		x_offset_od = 0
		x_offset_os = self.image_width
		y_offset_od = self.total_heading_height
		y_offset_os = self.total_heading_height


		# Ending this part if all that was needed was defining self.total_heading_height
		if mouse_grid_mode == "initiate heading":
			return ""

		if self.mode == "preview_layout":
			return individual_mouse_canvas


		# Add the images to the mouse canvas
		for eye, cslo_and_oct_image_list in self.mouse_image_list[mouse_id].items():
			for image_modality in self.image_type_objects:	# Loops through the images the user selected they wanted (i.e. BAF, IRAF, horizontal, etc.)
				image_path_to_use = None
				
				available_image_paths = cslo_and_oct_image_list[image_modality.imager]	# All paths for that imager and eye
				

				# -- Defining the image path --
				only_one_image_exists = not image_modality.select_required and image_modality.multiple_index is None
				# If there aren't any images from that imager (cslo/oct)
				if not available_image_paths:
					image_path_to_use = None

				# If the modality shouldn't have multiple images and thus just needs to grab the image that has the correct modality
				elif only_one_image_exists:
					for image_path in available_image_paths:
						_, _, _, _, modality = self.convert_path_to_base_name_and_parts(image_path, image_modality.imager)
						if modality == image_modality.image_type_name:
							image_path_to_use = image_path
							break

				else:
					# Create a list of all paths with the modality of interest
					image_paths_with_same_modality = []
					for image_path in available_image_paths:
						_, image_number, _, _, modality = self.convert_path_to_base_name_and_parts(image_path, image_modality.imager)
						if modality == image_modality.image_type_name:
							image_paths_with_same_modality.append((int(image_number), image_path))
					image_paths_with_same_modality.sort(key=lambda x: x[0])	# Sorting the list by image_number
					image_paths_with_same_modality = [x[1] for x in image_paths_with_same_modality]	# Making the list just image_path


					# If we just need to grab the nth image with that modality
					if image_modality.multiple_index is not None:
						index_to_use = image_modality.multiple_index
					
						# Grab the image with the correct index, unless it can't, then don't use any image
						try:
							image_path_to_use = image_paths_with_same_modality[index_to_use]
						except IndexError:
							image_path_to_use = None

					# If the user needs to select the image
					elif image_modality.select_required:
						if image_paths_with_same_modality and self.mode == "full":
							dialog_title = (f"{mouse_id} {eye} - {image_modality.image_type_name}")
							image_path_to_use = user_choose_which_images_to_use(image_paths_with_same_modality, dialog_title)
						else:
							image_path_to_use = None
				

				# -- Putting the image into the individual mouse canvas --
				if image_path_to_use:
					img = Image.open(image_path_to_use)
					if image_modality.imager == "cslo" and self.settings['crop_cslo_text_bool']:
						img = crop_cslo_image(img)
					elif image_modality.imager == "oct" and self.settings['oct_crop_bool']:
						img = crop_oct_image(img)
				else:
					if image_modality.imager == "cslo":
						w, h = self.cslo_width, self.cslo_height
					elif image_modality.imager == "oct":
						w, h = self.oct_width, self.oct_height
					img = Image.new("RGB", (w, h), color="black")

					if self.mode == "preview_layout_and_images" and image_modality.select_required:
						draw = ImageDraw.Draw(img)
						text = "No preview available"
						font = ImageFont.load_default(size=60)
						text_w, text_h, baseline_offset = self.measure_text(font, text)
						x = (w - text_w) / 2
						y = (h - text_h) / 2
						draw.text((x, y+baseline_offset), text, font=font, fill="white")

					
				# Setting x, y offsets
				if eye == "OD":
					x_offset = x_offset_od
					y_offset = y_offset_od
				elif eye == "OS":
					x_offset = x_offset_os
					y_offset = y_offset_os

				# Resizing if needed
				if img.width != self.image_width:
					new_width = self.image_width
					w, h = img.size
					aspect_ratio = h / w
					new_height = int(new_width * aspect_ratio)
					img = img.resize((new_width, new_height), Image.LANCZOS)

				# Pasting img into canvas
				individual_mouse_canvas.paste(img, (x_offset, y_offset))
				
				# Adjusting offsets
				if eye == "OD":
					y_offset_od += img.height
				elif eye == "OS":
					y_offset_os += img.height



		return individual_mouse_canvas

	# ====================================================
	# CANVAS AND LAYOUT
	# ====================================================
	def create_master_canvas(self):
		"""Create the master canvas based on one example mouse."""

		# Unpacking self.settings to make easier to read
		
		column_margin_size = int(self.settings['column_margin_size'])	# int
		row_margin_size = int(self.settings['row_margin_size'])			# int
		outer_margin_size = int(self.settings['outer_margin_size'])		# int
		number_of_rows = int(self.settings['number_of_rows'])			# int
		number_of_columns = int(self.settings['number_of_columns'])		# int
		
		# Unpacking some self.settings to make easier to read
		outer_margin_size = int(self.settings['outer_margin_size'])
		background_color = self.settings['background_color'] 			# (x, x, x)
		text_color = self.settings['text_color']						# (x, x, x)



		
		@dataclass
		class LayoutElement:
			kind: Literal["text", "image"]
			position: Tuple[int, int]
			width: int
			height: int
			text: Optional[str] = None
			font: Optional[ImageFont.FreeTypeFont] = None
			image: Optional[Image.Image] = None

			@property
			def right(self): return self.position[0] + self.width
			@property
			def bottom(self): return self.position[1] + self.height
			@property
			def left(self): return self.position[0]
			@property
			def top(self): return self.position[1]
			@property
			def center_x(self): return self.left + self.width // 2
			@property
			def center_y(self): return self.top + self.height // 2

			@classmethod
			def from_text(cls, text: str, font: ImageFont.FreeTypeFont, position: Tuple[int, int]):
				draw = ImageDraw.Draw(Image.new("RGB", (10, 10)))
				bbox = draw.textbbox((0, 0), text, font=font)
				width = bbox[2] - bbox[0]
				height = bbox[3] - bbox[1]
				y_offset = -bbox[1]
				
				return cls(
					kind="text",
					text=text,
					font=font,
					position=position,
					width=width,
					height=height
				)

			@classmethod
			def from_image(cls, image: Image.Image, position: Tuple[int, int]):
				return cls(
					kind="image",
			   		image=image,
					position=position,
					width=image.width,
					height=image.height
				)

			# Draw itself on a canvas
			def draw_on_canvas(self, canvas: Image.Image):
				draw_obj = ImageDraw.Draw(canvas)
				if self.kind == "text":
					bbox = self.font.getbbox(self.text) 
					draw_obj.text(
						(self.position[0], self.position[1] - bbox[1]),
						self.text,
						font=self.font,
						fill=text_color
					)

				elif self.kind == "image":
					canvas.paste(self.image, self.position)

		

		# Creating text elements
		title_element = LayoutElement.from_text(
			self.settings['document_title'], 
			self.settings['title_font'], 
			(outer_margin_size, outer_margin_size)
			)
		subtitle_element = LayoutElement.from_text(
			self.settings['subtitle'],
			self.settings['subtitle_font'],
			(outer_margin_size, title_element.bottom + (title_element.height//5))
		)
		
		self.master_canvas_elements = [
			title_element, 
			subtitle_element
		]



		def determine_size_of_column_one_x_offset():
			modality_text_max_width = 0
			for modality in self.image_type_objects:
				text = modality.custom_name
				font = self.settings['heading_font']
				modality_text_element = LayoutElement.from_text(text, font, (0, 0))
				if modality_text_element.width > modality_text_max_width:
					modality_text_max_width = modality_text_element.width
			
			column_one_x_offset = outer_margin_size + modality_text_max_width + min(outer_margin_size, 40)
			return column_one_x_offset



		def insert_image_modality_text(y_offset):
			def position_halfway_vertically(text, text_font, imager):
				# Get image height
				if imager == "cslo":
					img_h = self.cslo_height
				elif imager == "oct":
					img_h = self.oct_height
				else:
					raise ValueError("Invalid image_modality")

				# Measure text height
				x0, y0, x1, y1 = text_font.getbbox(text)
				h = y1 - y0
				baseline = -y0
				text_height = h - baseline  # how tall the drawn text is
				y_position = (img_h - text_height) // 2

				return y_position
			
			x_offset = outer_margin_size
			modality_text_max_width = 0
			top_of_image = y_offset + self.total_heading_height
			for modality in self.image_type_objects:
				text = modality.custom_name
				font = self.settings['heading_font']
				text_x = x_offset
				text_y = top_of_image + position_halfway_vertically(text, font, modality.imager)
				modality_text_element = LayoutElement.from_text(text, font, (text_x, text_y))
				self.master_canvas_elements.append(modality_text_element)

				if modality_text_element.width > modality_text_max_width:
					modality_text_max_width = modality_text_element.width

				# Adjust for next text
				if modality.imager == "cslo":
					top_of_image += self.cslo_height
				elif modality.imager == "oct":
					top_of_image += self.oct_height


		def assemble_mouse_canvases_into_layout(mouse_list, y_offset):
			nonlocal i
			column_count = 0
			column_one_x_offset = determine_size_of_column_one_x_offset()
			x_offset = column_one_x_offset

			for mouse in mouse_list:
				# Inserting image type titles on the far left
				if column_count == 0:
					insert_image_modality_text(y_offset)
				
				# Creating individual mouse compilation
				mouse_canvas = self.assemble_mouse_image_grid(mouse)
				mouse_element = LayoutElement.from_image(
					mouse_canvas,
					(x_offset, y_offset)
				)
				self.master_canvas_elements.append(mouse_element)
				
				# Determining the next column/row to use
				column_count += 1
				if column_count == number_of_columns:
					x_offset = column_one_x_offset
					y_offset = mouse_element.bottom + row_margin_size
					column_count = 0
				else:
					x_offset = mouse_element.right + column_margin_size

				status(f"Processing mouse canvases: {i}/{number_of_mice}")
			
			bottom_pixel = mouse_element.bottom
			return(bottom_pixel)

		# Determining location and pasting mouse images onto master canvas
		group_order = self.settings['group_order']
		y_offset = subtitle_element.bottom + row_margin_size

		number_of_mice = len(self.settings['mouse_info_dic'])
		i = 1

		if group_order:		# Only doing the group loop if there are actually groups defined
			for group in group_order:
				# Create group name element
				group_element = LayoutElement.from_text(
					group,
					self.settings['group_font'],
					(outer_margin_size, y_offset)
				)
				self.master_canvas_elements.append(group_element)
				_, group_text_h, _ = self.measure_text(self.settings['group_font'], group)
				y_offset += group_text_h + int(row_margin_size / 2)

				# Assembling the mouse canvases into the layout for the group
				group_mice_list = []
				for mouse, mouse_info in self.settings['mouse_info_dic'].items():
					if mouse_info[1] == group:
						group_mice_list.append(mouse)
				bottom_pixel = assemble_mouse_canvases_into_layout(group_mice_list, y_offset)
				
				# Adjusting the y_offset
				y_offset  = bottom_pixel + (row_margin_size * 2)
				
		else:
			mouse_list = list(self.settings['mouse_info_dic'].keys())
			_ = assemble_mouse_canvases_into_layout(mouse_list, y_offset)



		# Finding the bottom right most pixel
		bottom_most_pixel = outer_margin_size
		right_most_pixel = outer_margin_size
		for element in self.master_canvas_elements:

			if element.right > right_most_pixel:
				right_most_pixel = element.right
			if element.bottom > bottom_most_pixel:
				bottom_most_pixel = element.bottom
			

		# Creating the master canvas
		master_width = right_most_pixel + outer_margin_size
		master_height = bottom_most_pixel + outer_margin_size
		self.master_canvas = Image.new('RGB', (master_width, master_height), background_color)
		

		# Pasting the elements onto the canvas
		i = 1
		number_of_elements = len(self.master_canvas_elements)
		for element in self.master_canvas_elements:
			element.draw_on_canvas(self.master_canvas)
			status(f"Inserting canvas elements: {i}/{number_of_elements}")
			i += 1

		status("Canvas creation complete")


	# ====================================================
	# SAVE & DISPLAY
	# ====================================================
	def save_and_display_compilation_document(self):
		"""Save the final image and optionally show it."""
		
		final_product_file_path = self.settings['final_product_file_path']
		self.master_canvas.save(final_product_file_path)

		# Opening the final product
		if os.name == 'nt':  # Check if the operating system is Windows
			os.startfile(final_product_file_path)
			exit()
		try:
			subprocess.Popen(['xdg-open', final_product_file_path])  # Opens on Linux systems
		except OSError:
			try:
				subprocess.Popen(['open', final_product_file_path])  # Opens on macOS
			except OSError:
				exit()


	# ====================================================
	# MAIN ORCHESTRATION
	# ====================================================
	def run(self):
		# 1. Add non user defined settings
		self.add_non_user_defined_settings()
		

		# 2. Build image list
		self.build_mouse_image_list()

		# 3. Determine size of individual mouse canvas
		# Initializing individual mouse canvas creation to determine heading size (self.total_heading_height)
		example_mouse_number = list(self.mouse_image_list.keys())[0]
		_ = self.assemble_mouse_image_grid(example_mouse_number, "initiate heading")

		
		# 4. Create master canvas and layout
		self.create_master_canvas()

		# Ends before actually saving the document
		if self.mode == "preview_layout" or self.mode == "preview_layout_and_images":
			self.master_canvas.show()
			return

		# 5. Save document
		self.save_and_display_compilation_document()

		return



"""
-------------------------------
--- Main code orchestration ---
-------------------------------
"""

settings = user_defined_settings()
compiler = ImageCompilation(settings)
compiler.run()
