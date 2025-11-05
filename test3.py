from PIL import Image, ImageDraw, ImageFont, ImageTk
import os
from dataclasses import dataclass
import tkinter as tk
import pandas as pd
import numpy as np
import re
import cv2
import subprocess

# Allowed image extensions
image_extensions = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp"}


def user_defined_settings():
	"""Dialog box where user defines settings and returns them as a dictionary"""
	# C:/Users/nodna/Desktop/cSLO image compilation images/Less images
	settings = {
		'directories': [
			('C:/Users/bran314/Desktop/cSLO image compilation images/Less images/cSLO', 'cslo'),
			('C:/Users/bran314/Desktop/cSLO image compilation images/Less images/OCT', 'oct')],
		 'document_title': 'In vivo imaging',
		 'subtitle': 'October 23, 2025',
		 'number_of_rows': 1,
		 'number_of_columns': 4,
		 'mouse_info_dic': {
			 '1995': ('C809 BEH', '', ''),
			 '1994': ('C809 BEN', '', ''),
			 '1976': ('C806 REN', '', ''),
			 '1977': ('C806 LEN', '', '')},
		 'cslo_number_bool': True,
		 'labID_bool': True,
		 'crop_cslo_text_bool': True,
		 'oct_height': '350',
		 'images_to_use': [
			 ('cSLO BAF (1st)', 'BAF'),
			 ('cSLO IRAF [select]', 'IRAF'),
			 ('OCT horizontal', 'Horizontal'),
			 ('OCT vertical', 'Vertical')]
		}
	
	mode = "full"
	
	return settings, mode


class ImageCompilation:
	def __init__(self, settings=None, mode="full"):
		self.settings = settings or {}
		self.mode = mode
		self.mouse_image_list = {}
		self.canvas = None
		self.layout_map = None
		self.metadata = {}
		self.example_mouse_number = None  # to be set later


		original_images_to_use = self.settings.get('images_to_use', [])
		self.image_type_objects = [self.ImageType.from_tuple(t) for t in original_images_to_use]



	
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


	# ====================================================
	# SETTINGS
	# ====================================================
	def add_non_user_defined_settings(self):
		"""Add additional settings to self.settings"""
		additional_settings = {
			'background_color': (255, 255, 255),	# white
			'text_color': (0, 0, 0),				# black
			'final_product_file_path': "C:/Users/bran314/Desktop/cSLO image compilation images/image_compilation.jpg",
			'column_margin_size': 45,
			'row_margin_size': 400,
			'title_font': ImageFont.load_default(size=160),
			'subtitle_font': ImageFont.load_default(size=90)
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

				if mouse_number not in self.mouse_image_list:
					self.mouse_image_list[mouse_number] = {
							"OD": {"cslo": [], "oct": []},
							"OS": {"cslo": [], "oct": []},
						}
				
				self.mouse_image_list[mouse_number][eye][cslo_or_oct].append(path)

		cslo_image_file_paths, oct_image_file_paths = create_list_of_all_image_paths()

		cslo_image_file_paths = remove_unneeded_images(cslo_image_file_paths, "cslo")
		oct_image_file_paths = remove_unneeded_images(oct_image_file_paths, "oct")
		
		create_image_path_dic(cslo_image_file_paths, "cslo")
		create_image_path_dic(oct_image_file_paths, "oct")



	# ====================================================
	# IMAGE ASSEMBLY
	# ====================================================
	def assemble_mouse_image_grid(self, mouse_id):
		"""Creates image compilation and metadata for one mouse"""
		
		def crop_cslo_image(image_path):
			# Crops the text off of the bottom of the image
			image = Image.open(image_path)
			width, height = image.size
			cropped_image = image.crop((0, 0, width, width))

			return cropped_image

		def user_choose_which_images_to_use(image_path_list, title):
			def image_click(image_path):
				root.destroy()
				root.selected_image = image_path

			def select_none(event=None):
				root.destroy()
				root.selected_image = None

			def on_close_window(event=None):
				root.destroy()
				root.selected_image = None

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



		for eye, cslo_or_oct in self.mouse_image_list[mouse_id].items():
			for image_modality in self.image_type_objects:	# Loops through the images the user selected they wanted (i.e. BAF, IRAF, horizontal, etc.)
				image_path_to_use = None
				
				if image_modality.imager not in cslo_or_oct:		# Imager being either "cslo" or "oct"
					continue  # Skip imagers not present for this eye

				available_image_paths = cslo_or_oct[image_modality.imager]	# All paths for that imager and eye
				
				if not available_image_paths:
					continue

				# If the modality shouldn't have multiple images and thus just needs to grab the image that has the correct modality
				only_one_image_exists = not image_modality.select_required and image_modality.multiple_index is None
				if only_one_image_exists:
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
						if image_paths_with_same_modality:
							dialog_title = (f"{mouse_id} {eye} - {image_modality.image_type_name}")
							image_path_to_use = user_choose_which_images_to_use(image_paths_with_same_modality, dialog_title)
						else:
							image_path_to_use = None
					

		
		
		exit()

		
		mouse_compilation = None  # Replace with Pillow Image.new(...) etc.
		metadata = {}
		return mouse_compilation, metadata

	# ====================================================
	# CANVAS AND LAYOUT
	# ====================================================
	def create_compilation_canvas(self, example_mouse_compilation):
		"""Create the master canvas based on one example mouse."""
		self.canvas = None  # Replace with Image.new('RGB', size, color)
		return self.canvas

	def compute_layout_map(self):
		"""Compute coordinates for image placement."""
		self.layout_map = {}  # e.g., {mouse_id: (x, y), ...}
		return self.layout_map

	# ====================================================
	# PASTING & LABELS
	# ====================================================
	def paste_images_into_compilation_document(self, mouse_id, mouse_images):
		"""Paste a mouse’s images onto the master canvas."""
		pass

	def insert_labels(self):
		"""Add titles, labels, and text."""
		def center_text_between_images(text, font, x1, x2):
			center_position = (x1 + x2) // 2
			text_bbox = font.getbbox(text)
			text_width = text_bbox[2] - text_bbox[0]
			text_x = center_position - text_width // 2
			return text_x

		def create_title_and_subtitle():
			pass

		def create_image_labels():
			pass

		def create_additional_text():
			pass

		pass

	# ====================================================
	# SAVE & DISPLAY
	# ====================================================
	def save_and_display_compilation_document(self):
		"""Save the final image and optionally show it."""
		pass

	# ====================================================
	# MAIN ORCHESTRATION
	# ====================================================
	def run(self):
		"""Main workflow controller."""
		# 1. Add derived settings
		self.add_non_user_defined_settings()

		# 2. Build image list
		self.build_mouse_image_list()

		# 3. Example mouse setup
		self.example_mouse_number = list(self.mouse_image_list.keys())[0] if self.mouse_image_list else None
		example_comp, example_meta = self.assemble_mouse_image_grid(self.example_mouse_number)

		# 4. Canvas and layout
		self.create_compilation_canvas(example_comp)
		self.compute_layout_map()

		# 5. Compile images
		for mouse_id, mouse_images in self.mouse_image_list.items():
			mouse_comp, _ = self.assemble_mouse_image_grid(mouse_id)
			self.paste_images_into_compilation_document(mouse_id, mouse_images)

		# 6. Labels and final output
		self.insert_labels()
		self.save_and_display_compilation_document()

	def test_functionality(self):
		self.add_non_user_defined_settings()
		self.build_mouse_image_list()



		example_mouse_number = list(self.mouse_image_list.keys())[0] if self.mouse_image_list else None
		example_compilation, example_meta = self.assemble_mouse_image_grid(example_mouse_number)


		return

		# Print all entries in the mouse_image_list dictionary
		for mouse_id, eyes in self.mouse_image_list.items():
			print(f"Mouse {mouse_id}:")
			for eye, modalities in eyes.items():
				print(f"  {eye}:")
				for modality, paths in modalities.items():
					print(f"    {modality}:")
					for path in paths:
						print(f"      {path}")
			print()  # blank line between mice
		


settings, mode = user_defined_settings()
compiler = ImageCompilation(settings, mode)
compiler.test_functionality()
#compiler.run()


