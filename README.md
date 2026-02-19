# In vivo image compilation

This script imports images, allows the user to enter metadata, and generates a compilation document that provides a summary view of all images. The script is fully controlled through a Tkinter GUI.

Requirements
  - Input images must be in JPG, PNG, TIF, or BMP format.
  - The script reads only OCT and cSLO images that follow specific naming and folder conventions.

cSLO Images
  - Images must be organized into patient folders, with subfolders for each eye.
  - Files are expected to follow this naming format: imageNumber_patientID_eye_imageWavelength

OCT Images
  - All images should be stored in a single folder.
  - Files must follow this naming format: patientID_eye_location_depth

These folder and file naming conventions are consistent with the companion scripts Convert_OCT_files_to_TIF and cSLO_image_download.

Notes
This tool was developed primarily for, but is not limited to, mouse research. As a result, several variable names include “mouse” or “mice.”
