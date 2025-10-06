import os
print("Loading EasyOCR")
import easyocr
print("EasyOCR loaded")
import cv2
import matplotlib.pyplot as plt

def determine_ear_tag_number_in_cslo_images(base_directory):
	reader = easyocr.Reader(['en'], verbose=False)  # load English OCR
	show = False

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


		# Show cropped region for verification
		if show:
			plt.imshow(cv2.cvtColor(cropped, cv2.COLOR_BGR2RGB))
			plt.title(f"Cropped preview: {folder}")
			plt.axis("off")
			plt.show()
			show = False

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

		print(f"{folder}: {ear_tag_number}")


directory = "C:/Users/bran314/Desktop/cSLO image compilation images/cSLO images"
determine_ear_tag_number_in_cslo_images(directory)