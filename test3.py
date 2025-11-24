from PIL import Image, ImageDraw, ImageFont, ImageTk, UnidentifiedImageError
import os
from dataclasses import dataclass, field
from typing import Optional, Tuple, Literal, ClassVar
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
	settings = {
		'directories': [
			('C:/Users/bran314/Desktop/cSLO image compilation images/Less images/cSLO', 'cslo'),
			('C:/Users/bran314/Desktop/cSLO image compilation images/Less images/OCT', 'oct')],
			#('C:/Users/nodna/Desktop/cSLO image compilation images/Less images/cSLO', 'cslo'),
			#('C:/Users/nodna/Desktop/cSLO image compilation images/Less images/OCT', 'oct')],
		 'document_title': 'In vivo imaging',
		 'subtitle': 'October 23, 2025',
		 'number_of_rows': 2,
		 'number_of_columns': 3,
		 'mouse_info_dic': {
			 '1995': ('C809 BEH', '', ''),
			 '1994': ('C809 BEN', '', ''),
			 '1976': ('C806 REN', '', ''),
			 '1977': ('C806 LEN', '', '')},
		 'cslo_number_bool': True,
		 'labID_bool': True,
		 'crop_cslo_text_bool': True,
		 'oct_crop_bool': True,
		 'oct_height': '480',
		 'images_to_use': [
			 ('cSLO BAF (1st)', 'BAF'),
			 ('cSLO IRAF (2nd)', 'IRAF'),
			 ('OCT horizontal', 'Horizontal'),
			 ('OCT vertical', 'Vertical')]
		}
	
	mode = "full"
	
	return settings, mode


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



class ImageCompilation:
	def __init__(self, settings=None, mode="full"):
		self.settings = settings or {}
		self.mode = mode
		self.mouse_image_list = {}


		# Modify user input of image modalities to use into something more usable
		# Ex. ('cSLO BAF (1st)', 'BAF') --> class(imager, image_type_name, select_required, multiple_index, custom_name)
		original_images_to_use = self.settings.get('images_to_use', [])
		self.image_type_objects = [self.ImageType.from_tuple(t) for t in original_images_to_use]

		# -- Determining cslo and oct image sizes and assigning images as examples --
		for directory, imager in self.settings['directories']:
			if imager == "cslo":
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
			if imager == "cslo" and not hasattr(self, "example_cslo_image"):
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
			elif imager == "oct" and not hasattr(self, "example_oct_image"):
				try:
					self.example_oct_image = Image.open(example_path)
					self.oct_width, self.oct_height = self.example_oct_image.size
				except (FileNotFoundError, UnidentifiedImageError):
					self.example_oct_image = None
					self.oct_width, self.oct_height = 640, 480
				if self.settings['oct_crop_bool']:	# If the user has specified a specific height should be used
					self.oct_height = int(self.settings['oct_height'])


				
				# Resizing if needed
				if self.oct_width != self.cslo_width:
					new_width = self.cslo_width
					w, h = self.example_oct_image.size
					if self.settings['oct_crop_bool']:
						h = int(self.settings['oct_height'])
					aspect_ratio = h / w
					new_height = int(new_width * aspect_ratio)
					self.example_oct_image = self.example_oct_image.resize((new_width, new_height), Image.LANCZOS)
					self.oct_width, self.oct_height = new_width, new_height


			# Stop looping once both found
			if hasattr(self, "example_cslo_image") and hasattr(self, "example_oct_image"):
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
			'subtitle_font': ImageFont.load_default(size=90),
			'outer_margin_size': 30
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


		def create_single_mouse_canvas():
			cslo_count, oct_count = 0, 0
			for image_modality in self.image_type_objects:
				if image_modality.imager == "cslo":
					cslo_count += 1
				elif image_modality.imager == "oct":
					oct_count += 1
			
			canvas_width = self.cslo_width * 2	# 2x because OD and OS; oct images will be adjusted to match cslo images
			canvas_height = (self.cslo_height * cslo_count) + (self.oct_height * oct_count)
			canvas = Image.new("RGB", (canvas_width, canvas_height), color="black")

			return canvas


		# -- Main body of this function --
		# Will take one mouse number (mouse_id) and loop through all images generate a canvas with all images compiled together
		if mouse_id == "return_canvas_only":
			return create_single_mouse_canvas()

		individual_mouse_canvas = create_single_mouse_canvas()
		x_offset_od = 0
		x_offset_os = self.cslo_width
		y_offset_od = 0
		y_offset_os = 0

		for eye, cslo_or_oct in self.mouse_image_list[mouse_id].items():
			for image_modality in self.image_type_objects:	# Loops through the images the user selected they wanted (i.e. BAF, IRAF, horizontal, etc.)
				image_path_to_use = None
				
				if image_modality.imager not in cslo_or_oct:		# "imager" being either "cslo" or "oct"
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
						print(image_path_to_use)
				

				# -- Putting the image into the canvas --
				if image_path_to_use:	# Ignoring any image paths that are None
					# Cropping
					img = Image.open(image_path_to_use)
					if image_modality.imager == "cslo" and self.settings['crop_cslo_text_bool']:
						img = crop_cslo_image(img)
					elif image_modality.imager == "oct" and self.settings['oct_crop_bool']:
						img = crop_oct_image(img)
					
					# Setting x, y offsets
					if eye == "OD":
						x_offset = x_offset_od
						y_offset = y_offset_od
					elif eye == "OS":
						x_offset = x_offset_os
						y_offset = y_offset_os

					# Resizing if needed
					if img.width != self.cslo_width:
						new_width = self.cslo_width
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
	def create_master_canvas(self, example_mouse_canvas):
		"""Create the master canvas based on one example mouse."""

		# Unpacking self.settings to make easier to read
		
		column_margin_size = int(self.settings['column_margin_size'])	# int
		row_margin_size = int(self.settings['row_margin_size'])			# int
		title_font = self.settings['title_font']						# ImageFont.load_default(size=x)
		subtitle_font = self.settings['subtitle_font']					# ImageFont.load_default(size=x)
		outer_margin_size = int(self.settings['outer_margin_size'])		# int
		number_of_rows = int(self.settings['number_of_rows'])			# int
		number_of_columns = int(self.settings['number_of_columns'])		# int
		document_title = self.settings['document_title']				# string
		subtitle = self.settings['subtitle']							# string
		
		# Unpacking some self.settings to make easier to read
		outer_margin_size = int(self.settings['outer_margin_size'])
		background_color = self.settings['background_color'] 			# (x, x, x)
		text_color = self.settings['text_color']						# (x, x, x)


		# -- Defining additional variables --
		padding = 20
		
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
					#position=(position[0], position[1] + y_offset),
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


		# Creating elements
		title_element = LayoutElement.from_text(
			self.settings['document_title'], 
			self.settings['title_font'], 
			(outer_margin_size, outer_margin_size)
			)
		subtitle_element = LayoutElement.from_text(
			self.settings['subtitle'],
			self.settings['subtitle_font'],
			(outer_margin_size, title_element.bottom + padding)
		)

		
		self.master_canvas_elements = [
			title_element, 
			subtitle_element
		]

		# Determining location and pasting mouse images onto master canvas
		row_count = 0
		column_count = 0
		x_offset = outer_margin_size
		y_offset = subtitle_element.bottom + padding
		for mouse, mouse_info in self.settings['mouse_info_dic'].items():
			# Inserting image type titles
			if column_count == 0:
				for image_type in self.image_type_objects:
					text = image_type.custom_name	
			
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
				x_offset = outer_margin_size
				y_offset = mouse_element.bottom + padding
				row_count += 1
				column_count = 0
			else:
				x_offset = mouse_element.right + padding






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
		for element in self.master_canvas_elements:
			element.draw_on_canvas(self.master_canvas)




	# ====================================================
	# PASTING & LABELS
	# ====================================================
	def paste_images_into_compilation_document(self, mouse_id, mouse_images):
		"""Paste a mouse's images onto the master canvas."""
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
		self.create_master_canvas(example_comp)
		self.compute_layout_map()

		# 5. Compile images
		for mouse_id, mouse_images in self.mouse_image_list.items():
			mouse_comp, _ = self.assemble_mouse_image_grid(mouse_id)
			self.paste_images_into_compilation_document(mouse_id, mouse_images)

		# 6. Labels and final output
		self.insert_labels()
		self.save_and_display_compilation_document()

	def test_functionality(self):
		# 1. Add derived settings
		self.add_non_user_defined_settings()

		# 2. Build image list
		self.build_mouse_image_list()

		# 3. Determine size of individual mouse canvas
		#self.example_mouse_number = list(self.mouse_image_list.keys())[0]
		#example_mouse_canvas = self.assemble_mouse_image_grid(self.example_mouse_number)
		example_mouse_canvas = self.assemble_mouse_image_grid("return_canvas_only")
		
		
		#. Create master canvas and layout
		self.create_master_canvas(example_mouse_canvas)
		self.master_canvas.show()

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


