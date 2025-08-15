import tkinter as tk
from tkinter import filedialog
from datetime import datetime
import math

def user_defined_settings():
	def on_close_window(event=None):
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


	class MouseInfoFrame(tk.Frame):
		def __init__(self, parent):
			super().__init__(parent)

			label = tk.Label(self, text="Mouse info:")
			label.grid(row=0, column=0, padx=5, pady=0)

			self.excel_entry = tk.Entry(self, width=42)
			self.excel_entry.insert(0, "[Excel file location]")
			self.excel_entry.grid(row=0, column=1, padx=5, pady=0)

			choose_button = tk.Button(self, text="Choose", command=self.choose_file)
			choose_button.grid(row=0, column=2, padx=5, pady=0)

			edit_button = tk.Button(self, text="Edit info", command=self.edit_mouse_info)
			edit_button.grid(row=0, column=3, padx=5, pady=0)

			cslo_eartag_button = tk.Button(self, text="Determine cSLO/ear tag number based off of cSLO images",
								  command=self.determine_cslo_eartag_number)
			cslo_eartag_button.grid(row=1, column=0, columnspan=4, padx=5, pady=3)

		def choose_file(self):
			excel_file_path = filedialog.askopenfilename(filetypes=[("Excel files", "*.xlsx *.xls")])
			if excel_file_path:
				self.excel_entry.delete(0, tk.END)
				self.excel_entry.insert(0, excel_file_path)
		
		def edit_mouse_info(self):
			print("Button has no function yet")
		
		def determine_cslo_eartag_number(self):
			print("This button doesn't do anything right now")


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


	class RowColumnFrame(tk.Frame):
		def __init__(self, parent, number_of_mice):
			super().__init__(parent)

			# Calculate initial row/col numbers
			number_of_rows, number_of_columns = self.determine_row_and_column_number(number_of_mice)

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
			self.number_of_mice = number_of_mice
			self.row_entry.bind("<KeyRelease>", self.update_columns)
			self.column_entry.bind("<KeyRelease>", self.update_rows)

		@staticmethod
		def determine_row_and_column_number(number_of_mice):
			square_root = math.sqrt(number_of_mice)
			number_of_rows = math.floor(square_root)
			number_of_columns = math.ceil(square_root)
			if number_of_rows == number_of_columns:
				number_of_rows -= 1
				number_of_columns += 1
			while number_of_rows * number_of_columns < number_of_mice:
				number_of_rows += 1
			if number_of_rows == number_of_columns:
				number_of_rows -= 1
				number_of_columns += 1
			return number_of_rows, number_of_columns

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

	
	class OctCropFrame(tk.Frame):
		def __init__(self, parent):
			super().__init__(parent)

			# Crop OCT section
			self.oct_crop_var = tk.BooleanVar(value=False)
			oct_crop_cb = tk.Checkbutton(self, text="Crop OCT images",
										variable=self.oct_crop_var,
										command=self.oct_crop_checkbox_unselected)
			oct_crop_cb.grid(row=2, column=0, padx=5, pady=0, sticky="w")

			self.oct_crop_entry = tk.Entry(self, width=5, state="disabled")
			self.oct_crop_entry.insert(0, "480")
			self.oct_crop_entry.grid(row=2, column=1, padx=0, pady=0)

			pixel_label = tk.Label(self, text="pixels")
			pixel_label.grid(row=2, column=2, padx=0, pady=0)

			oct_crop_button = tk.Button(self, text="Find minimum OCT height", command=self.find_minimum_oct_height)
			oct_crop_button.grid(row=2, column=3, padx=5, pady=0)

		def find_minimum_oct_height(self):
			print("Button currently not functional")

		def oct_crop_checkbox_unselected(self):
			if self.oct_crop_var.get():
				self.oct_crop_entry.config(state="normal")
				self.oct_crop_entry.delete(0, tk.END)
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
			print("Nope")
		
		def preview_layout_and_images(self):
			print("None")

		def on_ok_click(self, event=None):
			global document_title, subtitle, number_of_rows, number_of_columns
			
			document_title = title_frame.title_entry.get()
			subtitle = title_frame.subtitle_entry.get()
			number_of_rows = int(row_col_frame.row_entry.get())
			number_of_columns = int(row_col_frame.column_entry.get())

			print("This button is currently being worked on")
			root.destroy()



	root = tk.Tk()
	root.title("Settings")
	root.protocol("WM_DELETE_WINDOW", on_close_window)
	root.columnconfigure(0, weight=1)
	root.rowconfigure(0, weight=1)

	directory_frame = DirectoryFrame(root)
	directory_frame.pack(anchor='w')

	mouse_info_frame = MouseInfoFrame(root)
	mouse_info_frame.pack(anchor='w', pady=3)

	title_frame = TitleFrame(root)
	title_frame.pack(anchor='w', fill='x')

	row_col_frame = RowColumnFrame(root, number_of_mice=10)
	row_col_frame.pack(anchor='w')

	numbers_and_cslo_crop_frame = NumberAndCsloCropFrame(root)
	numbers_and_cslo_crop_frame.pack(anchor='w')

	oct_crop_frame = OctCropFrame(root)
	oct_crop_frame.pack(anchor='w')

	images_to_use_frame = ImagesToUseFrame(root)
	images_to_use_frame.pack(anchor='w')

	preset_frame = PresetFrame(root)
	preset_frame.pack(anchor='w')

	confirmation_frame = ConfirmationFrame(root)
	confirmation_frame.pack(anchor='s', pady=10)

	root.mainloop()

user_defined_settings()