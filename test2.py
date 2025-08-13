import tkinter as tk
from datetime import datetime
import math

def user_defined_settings():
	def on_ok_click(event=None):
		global document_title, subtitle, number_of_rows, number_of_columns
		
		document_title = title_entry.get()
		subtitle = subtitle_entry.get()
		number_of_rows = int(row_entry.get())
		number_of_columns = int(column_entry.get())

		root.destroy()

	def on_close_window(event=None):
		root.destroy()
		exit()
	
	root = tk.Tk()
	root.title("Settings")
	root.protocol("WM_DELETE_WINDOW", on_close_window)
	root.columnconfigure(0, weight=1)
	root.rowconfigure(0, weight=1)


	# User defines working directories
	directory_frame = tk.Frame(root)
	directory_frame.pack()


	# Mouse information
	mouse_info_frame = tk.Frame(root)
	mouse_info_frame.pack(anchor='w')

	number_of_mice = 7 # DELETE LATER
	mouse_number_label = tk.Label(mouse_info_frame, text=f"Number of mice: {number_of_mice}")
	mouse_number_label.grid(row=0, column=0, padx=5, pady=0, sticky='w')

	
	
	# User defines titles for document
	title_frame = tk.Frame(root)
	title_frame.pack(fill='both', expand=True)
	title_frame.columnconfigure(1, weight=1)
	
	title_label = tk.Label(title_frame, text="Title:")
	title_label.grid(row=0, column=0, padx=5, pady=0, sticky="w")
	title_entry = tk.Entry(title_frame, width=40)
	title_entry.insert(0, "In vivo imaging")
	title_entry.grid(row=0, column=1, padx=5, pady=0, sticky="we")
	
	subtitle_label = tk.Label(title_frame, text="Subtitle:")
	subtitle_label.grid(row=1, column=0, padx=5, pady=0, sticky="w")
	subtitle_entry = tk.Entry(title_frame, width=40)
	today_str = datetime.today().strftime("%B %d, %Y").replace(" 0", " ") # Automatically filling in the subtitle with today's date
	subtitle_entry.insert(0, today_str)
	subtitle_entry.grid(row=1, column=1, padx=5, pady=0, sticky="we")



	# User defines how many rows and columns each group should have
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

	# When the "row" entry box is changed, this activates
	def update_columns(*args):
		try:
			row_number = row_entry.get()
			if row_number != "":
				row_number = int(row_number)
				column_number = math.ceil(number_of_mice / row_number)
				column_entry.delete(0, tk.END)
				column_entry.insert(0, str(column_number))
		except ValueError:
			column_entry.delete(0, tk.END)

	# When the "column" entry box is changed, this activates
	def update_rows(*args):
		try:
			column_number = column_entry.get()
			if column_number != "":
				column_number = int(column_number)
				row_number = math.ceil(number_of_mice / column_number)
				row_entry.delete(0, tk.END)
				row_entry.insert(0, str(row_number))
		except ValueError:
			row_entry.delete(0, tk.END)

	row_column_frame = tk.Frame(root)
	row_column_frame.pack(anchor='w')

	number_of_rows, number_of_columns = determine_row_and_column_number(number_of_mice)

	row_column_label = tk.Label(row_column_frame, text="Row x column:")
	row_column_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")

	row_entry = tk.Entry(row_column_frame, width=5)
	row_entry.insert(0, number_of_rows)
	row_entry.grid(row=0, column=1, padx=5, pady=5)

	x_label = tk.Label(row_column_frame, text="x")
	x_label.grid(row=0, column=2, padx=5, pady=5)

	column_entry = tk.Entry(row_column_frame, width=5)
	column_entry.insert(0, number_of_columns)
	column_entry.grid(row=0, column=3, padx=5, pady=5)
	
	row_entry.bind("<KeyRelease>", update_columns)
	column_entry.bind("<KeyRelease>", update_rows)


	# User defines additional options
	additional_options_frame = tk.Frame(root)
	additional_options_frame.pack(anchor='w')

	# User defines if cSLO or ear tag numbers should be used
	mouse_label_to_use_label = tk.Label(additional_options_frame, text="Use:")
	mouse_label_to_use_label.grid(row=0, column=0, padx=5, pady=0, sticky="w")

	cslo_number_var = tk.BooleanVar(value=True)
	cslo_cb = tk.Checkbutton(additional_options_frame, text="cSLO numbers", variable=cslo_number_var)
	cslo_cb.grid(row=0, column=1, padx=5, pady=0, sticky="w")

	eartag_number_var = tk.BooleanVar(value=False)
	eartag_cb = tk.Checkbutton(additional_options_frame, text="Ear tag numbers", variable=eartag_number_var)
	eartag_cb.grid(row=0, column=2, padx=5, pady=0, sticky="w")

	# User determines if text should be cropped off of cSLO images
	crop_cslo_text_var = tk.BooleanVar(value=True)
	crop_cslo_text_cb = tk.Checkbutton(additional_options_frame, text="Crop the text off of cSLO images", variable=crop_cslo_text_var)
	crop_cslo_text_cb.grid(row=1, column=0, columnspan=3, padx=5, pady=0, sticky="w")

	# User determines if OCT images should be further cropped
	def find_minimum_oct_height():
		print("Button currently not functional")
	
	def oct_crop_checkbox_unselected():
		print(oct_crop_var.get())
		if oct_crop_var.get():
			print("this should be true")
			oct_crop_entry.config(state="normal")
			oct_crop_entry.delete(0, tk.END)
			oct_crop_entry.insert(0, "480")
		else:
			print("this should be false")
			oct_crop_entry.config(state="disabled")

	oct_crop_frame = tk.Frame(root)
	oct_crop_frame.pack(anchor='w')

	oct_crop_var = tk.BooleanVar(value=False)
	oct_crop_cb = tk.Checkbutton(oct_crop_frame, text="Crop OCT images", variable=oct_crop_var, command=oct_crop_checkbox_unselected)
	oct_crop_cb.grid(row=0, column=0, padx=5, pady=0, sticky="w")

	oct_crop_entry = tk.Entry(oct_crop_frame, width=5, state="disabled")
	oct_crop_entry.insert(0, "480")
	oct_crop_entry.grid(row=0, column=1, padx=0, pady=0)
	pixel_label = tk.Label(oct_crop_frame, text="pixels")
	pixel_label.grid(row=0, column=2, padx=0, pady=0)

	oct_crop_button = tk.Button(oct_crop_frame, text="Find minimum OCT height", command=find_minimum_oct_height)
	oct_crop_button.grid(row=0, column=3, padx=5, pady=0)


	root.mainloop()

user_defined_settings()