# cSLO image compilation
# Made by Brandon Anderson
# University of Pennsylvania


import tkinter as tk
from tkinter import filedialog
from PIL import Image, ImageDraw, ImageFont, ImageTk
import os
import subprocess
import math


def select_input_directory():
	root = tk.Tk()
	root.withdraw()  # Hide the main window
	input_directory = filedialog.askdirectory()
	return input_directory

def find_image_files(input_directory):
	image_files = []
	for root, dirs, files in os.walk(input_directory):
		for file in files:
			if file.endswith('.tif'):
				image_files.append(os.path.join(root, file))
	return image_files

def list_mice(input_directory):
	mouse_list = [folder for folder in os.listdir(input_directory) if os.path.isdir(os.path.join(input_directory, folder))]
	return mouse_list

def center_text_between_images(text, font, x1, x2):
	center_position = (x1 + x2) // 2
	text_bbox = font.getbbox(text)
	text_width = text_bbox[2] - text_bbox[0]
	text_x = center_position - text_width // 2
	return text_x


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

def user_defined_settings(number_of_mice):
	def on_ok_click(event=None):
		global document_title, subtitle, number_of_rows, number_of_columns
		window.withdraw()
		document_title = title_entry.get()
		subtitle = subtitle_entry.get()
		number_of_rows = int(row_entry.get())
		number_of_columns = int(column_entry.get())
		window.destroy()
		window.master.destroy()
		root.destroy()

	def on_close_window(event=None):
		exit()

	root = tk.Tk()
	root.withdraw()  # Hide the main window
	window = tk.Toplevel()
	window.title("Settings")
	window.protocol("WM_DELETE_WINDOW", on_close_window)

	# Function to create a label and an entry field in a grid
	def create_label_entry_grid(row, column, text, default_value):
		label = tk.Label(window, text=text)
		label.grid(row=row, column=column, columnspan=3, padx=5, pady=0, sticky="w")

		entry = tk.Entry(window)
		entry.insert(0, default_value)
		entry.grid(row=row, column=column + 1, columnspan=3, padx=5, pady=0, sticky="ew")

		return entry  # Return the entry widget for further use if needed

	# Function to specifically create the "Row x column" text field
	def create_grid_boxes():
		number_of_rows, number_of_columns = determine_row_and_column_number(number_of_mice)

		label = tk.Label(window, text="Row x column:")
		label.grid(row=2, column=0, padx=5, pady=5, sticky="w")

		row_entry = tk.Entry(window, width=5)
		row_entry.insert(0, number_of_rows)
		row_entry.grid(row=2, column=1, padx=5, pady=5)

		x_label = tk.Label(window, text="x")
		x_label.grid(row=2, column=2, padx=5, pady=5)

		column_entry = tk.Entry(window, width=5)
		column_entry.insert(0, number_of_columns)
		column_entry.grid(row=2, column=3, padx=5, pady=5)

		return row_entry, column_entry

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

	title_entry = create_label_entry_grid(0, 0, "Title:", "")
	subtitle_entry = create_label_entry_grid(1, 0, "Subtitle:", "")

	row_entry, column_entry = create_grid_boxes()
	row_entry.bind("<KeyRelease>", update_columns)
	column_entry.bind("<KeyRelease>", update_rows)

	ok_button = tk.Button(window, text="OK", command=on_ok_click)
	ok_button.grid(row=4, column=0, columnspan=4, padx=5, pady=10, sticky="ew")


	window.bind("<Escape>", on_close_window)
	window.bind("<Return>", on_ok_click)

	root.mainloop()


def user_select_from_multiple_images(image_paths):
	# Function to handle image click event
	def image_click(image_path):
		root.destroy()
		root.selected_image = image_path
				
	def on_close_window(event=None):
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


	root = tk.Tk()
	root.title("Image Selection")
	root.protocol("WM_DELETE_WINDOW", on_close_window)

	# Create a list to hold PhotoImage objects
	resized_images = []

	# Load images and display them in the tkinter window
	for path in image_paths:
		original_image = Image.open(path)
		resized_image = original_image.resize((int(original_image.width * 0.5), int(original_image.height * 0.5)))
		photo = ImageTk.PhotoImage(resized_image)
		resized_images.append(photo)
		label = tk.Label(root, image=photo)
		label.image = photo  # Keep a reference to the image to prevent garbage collection
		label.pack(side=tk.LEFT, padx=5, pady=5)  # Display images in a row with padding


		# Bind the click event to the image label
		label.bind("<Button-1>", lambda event, image_path=path: image_click(image_path))

	root.bind("<Escape>", on_close_window)

	# Center the window on the screen
	root.after(10, lambda: center_dialog_box(root))


	# Start the Tkinter main loop
	root.mainloop()



	return root.selected_image if hasattr(root, 'selected_image') else None

	


def compile_images(image_files, mouse_list, input_directory):
	# Determining the size of the compilation document
	example_image = Image.open(image_files[0])
	image_width = example_image.width
	image_height = example_image.height

	column_margin_size = 45
	row_margin_size = 400

	width_of_column_margins = int(len(mouse_list) * column_margin_size)
	x_offset = 400
	#compilation_width = width_of_images + width_of_column_margins + x_offset + 100
	compilation_width = number_of_columns * (image_width * 2 + column_margin_size) + x_offset 
	y_offset = 700

	if document_title == "":
		y_offset -= 250
		subtitle_y = 35
	else:
		subtitle_y = 230
	if subtitle == "":
		y_offset -= 70


	compilation_height = (image_height * 2 * number_of_rows) + ((number_of_rows - 1) * row_margin_size) + y_offset + 100
	compilation_height = int(compilation_height)
	background_color = (255, 255, 255)
	compiled_image = Image.new('RGB', (compilation_width, compilation_height), background_color)

	# Creating a title for the document
	draw = ImageDraw.Draw(compiled_image)
	text_color = (0, 0, 0)
	#title_font = ImageFont.truetype("arial.ttf", 120)
	title_font = ImageFont.load_default(size=160)
	draw.text((30, 20), document_title, fill=text_color, font=title_font)

	# Creating a subtitle for the document
	title_font = ImageFont.load_default(size=90)
	draw.text((30, subtitle_y), subtitle, fill=text_color, font=title_font)

	# Creating the image type text
	image_type_font = ImageFont.load_default(size=110)
	image_type_x = x_offset - 300
	image_type_y = center_text_between_images("BAF", image_type_font, y_offset, y_offset + image_height)
	draw.text((image_type_x, image_type_y), "BAF", fill=text_color, font=image_type_font)
	draw.text((image_type_x, image_type_y + image_height), "IRAF", fill=text_color, font=image_type_font)

	current_image_number = 0
	total_images = len(image_files)

	current_column = 0
	current_row = 0
	y_offset_addition = image_height * 2 + row_margin_size

	for i, mouse in enumerate(mouse_list):
		current_mouse_files = []
		for image in image_files:
			if mouse in os.path.basename(image):
				current_mouse_files.append(image)
		
		if len(current_mouse_files) != 4:
			new_current_mouse_files = []
			#print(f"Unexpected number of files in mouse {mouse}. Number of files: {len(current_mouse_files)}")
			images_needed = ["OD_BAF", "OD_IRAF", "OS_BAF", "OS_IRAF"]
			for image_type in images_needed:
				multiple_images_of_one_type = []
				for file in current_mouse_files:
					if image_type in os.path.basename(file):
						multiple_images_of_one_type.append(file)
				if len(multiple_images_of_one_type) == 1:
					new_current_mouse_files.append(multiple_images_of_one_type[0])
				elif len(multiple_images_of_one_type) > 1:
					selected_image = user_select_from_multiple_images(multiple_images_of_one_type)
					new_current_mouse_files.append(selected_image)
			current_mouse_files = new_current_mouse_files
		

		# Filter out 'None' values from the list
		current_mouse_files = [image for image in current_mouse_files if image is not None]

		image_x_offset = current_column * (image_width * 2 + column_margin_size) + x_offset
		# y_offset is defined above when making the compiled image

		# Typing the mouse number text
		mouse_font = ImageFont.load_default(size=110)
		#font = ImageFont.truetype("arial.ttf", 100)
		image_x1 = image_x_offset
		image_x2 = image_x_offset + (2 * image_width)
		mouse_text_x = center_text_between_images(mouse, mouse_font, image_x1, image_x2)
		draw.text((mouse_text_x, y_offset - 300), mouse, fill=text_color, font=mouse_font)

		# Typing the OD/OS text
		eye_font = ImageFont.load_default(size=100)
		OD_x1 = image_x_offset
		OD_x2 = image_x_offset + image_width
		OD_text_x = center_text_between_images("OD", eye_font, OD_x1, OD_x2)
		draw.text((OD_text_x, y_offset - 150), "OD", fill=text_color, font = eye_font)
		OS_x1 = image_x_offset + image_width
		OS_x2 = image_x_offset + image_width + image_width
		OS_text_x = center_text_between_images("OS", eye_font, OS_x1, OS_x2)
		draw.text((OS_text_x, y_offset - 150), "OS", fill=text_color, font = eye_font)


		# Placing the cSLO images in the document
		for image_path in current_mouse_files:
			image = Image.open(image_path)
			if "OD" in os.path.basename(image_path):
				if "BAF" in os.path.basename(image_path):
					compiled_image.paste(image, (image_x_offset, y_offset))
				if "IRAF" in os.path.basename(image_path):
					compiled_image.paste(image, (image_x_offset, y_offset + image_height))
			elif "OS" in os.path.basename(image_path):
				if "BAF" in os.path.basename(image_path):
					compiled_image.paste(image, (image_x_offset + image_width, y_offset))
				if "IRAF" in os.path.basename(image_path):
					compiled_image.paste(image, (image_x_offset + image_width, y_offset + image_height))
			else:
				continue
			current_image_number += 1
			percent_done = round(100 * current_image_number / total_images)
			print(f"Inserting images into compilation document. {percent_done}%", end='\r')
		
		if current_column + 1 < number_of_columns:
			current_column += 1
		else:
			current_column = 0
			y_offset = y_offset + y_offset_addition
			image_type_y = center_text_between_images("BAF", image_type_font, y_offset, y_offset + image_height)
			draw.text((image_type_x, image_type_y), "BAF", fill=text_color, font=image_type_font)
			draw.text((image_type_x, image_type_y + image_height), "IRAF", fill=text_color, font=image_type_font)

	print(f"Inserting images into compilation document. 100%")

	completed_file_path = os.path.join(input_directory, 'cSLO_compilation.jpg')
	compiled_image.save(completed_file_path)

	print("Compilation image saved as cSLO_compilation.jpg")

	return completed_file_path

# Define the input directory where your images are located
input_directory = select_input_directory()



mouse_list = list_mice(input_directory)

print(f"Number of mice found: {len(mouse_list)}")

image_files = find_image_files(input_directory)
print(f"Images found: {len(image_files)}")

# User now defines text and layout of document
user_defined_settings(len(mouse_list))



completed_file_path = compile_images(image_files, mouse_list, input_directory)

# Opening the final product
if os.name == 'nt':  # Check if the operating system is Windows
	os.startfile(completed_file_path)
	exit()
try:
	subprocess.Popen(['xdg-open', completed_file_path])  # Opens on Linux systems
except OSError:
	try:
		subprocess.Popen(['open', completed_file_path])  # Opens on macOS
	except OSError:
		exit()
