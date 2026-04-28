import os
import sys
import json
import shutil
import subprocess
import tempfile
import threading
import tkinter as tk
import time
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp"}
APP_NAME         = "In vivo image compilation"
SCREEN_FILL      = 0.9   # maximum fraction of screen width/height the window may occupy
THUMB_GAP        = 6     # pixels between thumbnails in the pool panel

def _get_settings_path() -> str:
	"""Return the cross-platform path to image_sequence.json, creating the folder if needed."""
	if os.name == "nt":  # Windows
		base_dir = os.getenv("APPDATA")
	else:  # macOS / Linux
		base_dir = os.path.join(os.path.expanduser("~"), ".config")

	app_dir = os.path.join(base_dir, APP_NAME)
	os.makedirs(app_dir, exist_ok=True)

	return os.path.join(app_dir, "image_sequence.json")

# Modality filtering: which row types accept which image modalities
MODALITY_ALLOWED = {
	"IR":   {"IR"},
	"BAF":  {"BAF"},
	"IRAF": {"IRAF"},
}


# ===========================================================================
# Data Model
# ===========================================================================

class AppState:
	"""Holds all shared application data. No GUI logic here."""

	def __init__(self):
		self.sequence: list[tuple[str, str]] = []   # [(modality, custom_label), ...]
		self.original_folder: str | None = None
		self.image_groups: dict[str, list[str]] = {}
		self.assignments: dict[int, str | None] = {}
		self.mouse_number: str = ""
		self.eye: str = ""
		self.first_image_size: tuple[int, int] | None = None
		self.thumb_size: int = 140

	# ---- Persistence --------------------------------------------------------

	def save_sequence_json(self):
		with open(_get_settings_path(), "w") as f:
			json.dump({"sequence": self.sequence, "thumb_size": self.thumb_size}, f, indent=4)

	def load_sequence_json(self) -> bool:
		path = _get_settings_path()
		if os.path.exists(path):
			with open(path, "r") as f:
				data = json.load(f)
				self.sequence = data.get("sequence", [])
				self.thumb_size = data.get("thumb_size", 140)
				return True
		return False

	# ---- Queries ------------------------------------------------------------

	def image_modality_for(self, path: str) -> str:
		for modality, paths in self.image_groups.items():
			if path in paths:
				return modality
		return "Other"

	def image_compatible(self, path: str, row_index: int) -> bool:
		img_mod = self.image_modality_for(path)
		allowed_rows = MODALITY_ALLOWED.get(img_mod)
		if allowed_rows is None:
			return True
		row_modality, _ = self.sequence[row_index]
		return row_modality in allowed_rows


# ===========================================================================
# Image / File Logic
# ===========================================================================

_GLOBAL_THUMB_CACHE: dict[tuple, ImageTk.PhotoImage] = {}


class ImageProcessor:
	"""Handles all file I/O, thumbnail creation, and export."""

	def __init__(self, state: AppState):
		self.state = state

	# ---- Parsing ------------------------------------------------------------

	def parse_images(self):
		"""Scan the original_folder and populate state.image_groups."""
		s = self.state
		groups: dict[str, list[str]] = {"IR": [], "BAF": [], "IRAF": [], "OTHER": []}

		with os.scandir(s.original_folder) as entries:
			files = [
				e.name for e in entries
				if e.is_file()
				and os.path.splitext(e.name)[1].lower() in IMAGE_EXTENSIONS
			]

		for filename in files:
			modality = filename.split("_")[-1].split(".")[0]
			full_path = os.path.join(s.original_folder, filename)
			groups[modality if modality in groups else "OTHER"].append(full_path)

		s.image_groups = groups

		# Parse metadata from first filename
		if files:
			parts = files[0].split("_")
			if len(parts) >= 3:
				s.mouse_number = parts[1]
				s.eye          = parts[2]
			else:
				s.mouse_number = "unknown"
				s.eye          = "unknown"

			with Image.open(os.path.join(s.original_folder, files[0])) as img:
				s.first_image_size = img.size

	# ---- Thumbnails ---------------------------------------------------------

	def create_thumbnail(self, path: str, size: int, master=None) -> ImageTk.PhotoImage:
		cache_key = (path, size, id(master))
		if cache_key in _GLOBAL_THUMB_CACHE:
			return _GLOBAL_THUMB_CACHE[cache_key]

		ext = os.path.splitext(path)[1].lower()
		with Image.open(path) as img:
			if ext in (".jpg", ".jpeg", ".tif", ".tiff"):
				try:
					img.draft("RGB", (size, size))
				except (AttributeError, Exception):
					pass
			img = img.copy()

		img.thumbnail((size, size))
		photo = ImageTk.PhotoImage(img, master=master)
		_GLOBAL_THUMB_CACHE[cache_key] = photo
		return photo

	def clear_cache(self):
		# Only clear entries for paths in this folder so other folders stay warm
		folder = self.state.original_folder or ""
		keys_to_remove = [k for k in _GLOBAL_THUMB_CACHE if k[0].startswith(folder)]
		for k in keys_to_remove:
			del _GLOBAL_THUMB_CACHE[k]

	# ---- Export (now delegates to worker subprocess) -----------------------

	def get_extension(self) -> str:
		for group in self.state.image_groups.values():
			if group:
				return os.path.splitext(group[0])[1]
		return ".tif"

	def build_job(self) -> dict:
		"""Build the job dict that export_worker.py expects."""
		s = self.state
		parent     = os.path.dirname(s.original_folder)
		base       = os.path.basename(s.original_folder)
		new_folder = os.path.join(parent, f"{base}_standardized")

		return {
			"original_folder": s.original_folder,
			"new_folder":      new_folder,
			"mouse_number":    s.mouse_number,
			"eye":             s.eye,
			"first_image_size": list(s.first_image_size) if s.first_image_size else [512, 512],
			"sequence":        s.sequence,
			"assignments":     {str(k): v for k, v in s.assignments.items()},
			"extension":       self.get_extension(),
		}


# ===========================================================================
# Phase 1 GUI – Define Sequence
# ===========================================================================

class SequenceDialog:
	"""
	Modal window that lets the user build an ordered list of
	(modality, custom_label) pairs.  Populates state.sequence on OK.
	"""

	def __init__(self, state: AppState, standalone: bool = True):
		self.state = state
		self.standalone = standalone
		self.rows: list[dict] = []
		self._root: tk.Tk | None = None

	def run(self):
		root = tk.Tk()
		self._root = root
		root.title("Define Image Sequence")
		root.protocol("WM_DELETE_WINDOW", self._on_close)

		rows_frame = tk.Frame(root)
		rows_frame.pack(padx=3, pady=5)
		self._rows_frame = rows_frame

		buttons_frame = tk.Frame(root)
		buttons_frame.pack(pady=10)

		self._build_row()

		tk.Button(
			buttons_frame, text="Use Previous Settings",
			command=self._load_previous
		).grid(row=0, column=0, padx=10)

		tk.Button(
			buttons_frame, text="OK",
			command=self._on_okay
		).grid(row=0, column=1, padx=10)

		root.mainloop()

	# ---- Row building -------------------------------------------------------

	def _build_row(self):
		row_index     = len(self.rows)
		modality_vars = {m: tk.BooleanVar(value=False) for m in ("IR", "BAF", "IRAF")}
		custom_var    = tk.StringVar()
		frame         = self._rows_frame

		label = tk.Label(frame, text=f"{row_index}.")
		label.grid(row=row_index, column=0, padx=5)

		checkboxes = []
		for col, modality in enumerate(("IR", "BAF", "IRAF")):
			cb = tk.Checkbutton(
				frame, text=modality,
				variable=modality_vars[modality],
				command=lambda m=modality: self._on_checkbox_change(m, modality_vars)
			)
			cb.grid(row=row_index, column=col + 1, padx=1)
			checkboxes.append(cb)

		entry = tk.Entry(frame, textvariable=custom_var, width=20)
		entry.grid(row=row_index, column=4, padx=3)

		row_dict = {
			"modality_vars": modality_vars,
			"custom_var":    custom_var,
			"label":         label,
			"checkboxes":    checkboxes,
			"entry":         entry,
		}

		entry.bind("<Up>",   lambda e, r=row_dict: self._navigate_entry(-1, r))
		entry.bind("<Down>", lambda e, r=row_dict: self._navigate_entry(+1, r))

		self.rows.append(row_dict)

	def _on_checkbox_change(self, selected_modality: str, modality_vars: dict):
		for modality, var in modality_vars.items():
			if modality != selected_modality:
				var.set(False)

		self._cleanup_rows()

		if any(v.get() for v in modality_vars.values()):
			if self.rows[-1]["modality_vars"] is modality_vars:
				self._build_row()

	def _cleanup_rows(self):
		i = 0
		while i < len(self.rows) - 1:
			row = self.rows[i]
			if not any(v.get() for v in row["modality_vars"].values()):
				row["label"].destroy()
				row["entry"].destroy()
				for cb in row["checkboxes"]:
					cb.destroy()
				self.rows.pop(i)
				continue
			i += 1

		for idx, row in enumerate(self.rows):
			row["label"].grid(row=idx, column=0, padx=5)
			for col, cb in enumerate(row["checkboxes"]):
				cb.grid(row=idx, column=col + 1)
			row["entry"].grid(row=idx, column=4)
			row["label"].config(text=f"{idx}.")

	def _navigate_entry(self, direction: int, row_ref: dict):
		try:
			current_index = self.rows.index(row_ref)
		except ValueError:
			return
		next_index = current_index + direction
		if 0 <= next_index < len(self.rows):
			self.rows[next_index]["entry"].focus_set()

	# ---- Button handlers ----------------------------------------------------

	def _load_previous(self):
		if not self.state.load_sequence_json():
			return

		for row in self.rows:
			row["label"].destroy()
			row["entry"].destroy()
			for cb in row["checkboxes"]:
				cb.destroy()
		self.rows.clear()

		for modality, custom_label in self.state.sequence:
			self._build_row()
			row = self.rows[-1]
			if modality in row["modality_vars"]:
				row["modality_vars"][modality].set(True)
			row["custom_var"].set(custom_label)

		self._build_row()

	def _on_okay(self):
		sequence = []
		for row in self.rows:
			selected = [m for m, v in row["modality_vars"].items() if v.get()]
			if selected:
				sequence.append((selected[0], row["custom_var"].get()))
		self.state.sequence = sequence
		self.state.save_sequence_json()
		self._root.destroy()

	def _on_close(self):
		self._root.destroy()
		if self.standalone:
			sys.exit(0)


# ===========================================================================
# Directory Browser GUI
# ===========================================================================

class DirectoryEntry:
	"""Represents one sub-sub directory the user can work on."""

	def __init__(self, sub: str, subsub: str, path: str):
		self.sub      = sub
		self.subsub   = subsub
		self.path     = path
		self.exported = False
		self.std_folder: str | None = None


class DirectoryBrowserGUI:
	"""
	Shows all sub/sub-sub directories found under the chosen root.
	"""

	def __init__(self, root_folder: str | None, state: AppState, standalone: bool = True, paths: list[str] | None = None, parent: tk.Tk | None = None):
		self.root_folder = root_folder
		self.state       = state
		self.entries: list[DirectoryEntry] = []
		self._root: tk.Tk | None = None
		self._row_frames: dict[str, tk.Frame] = {}
		self.standalone = standalone
		self._parent = parent

		# CHANGE 4: track in-progress export jobs {path -> job_json_path}
		self._export_jobs: dict[str, str] = {}
		self._poll_job_id: str | None = None   # after() handle

	# ---- Entry point --------------------------------------------------------

	def run(self):
		self._scan_directories()

		root = tk.Tk() if self._parent is None else tk.Toplevel(self._parent)
		self._root = root
		root.title("Select Directory")
		root.protocol("WM_DELETE_WINDOW", self._on_close)

		self._build_ui(root)
		self._size_window(root)

		# CHANGE 1: kick off background count population
		self._wanted = self._sequence_modality_counts()
		threading.Thread(
			target=self._populate_counts_bg,
			daemon=True
		).start()

		root.mainloop()

	# ---- Scanning -----------------------------------------------------------

	def _scan_directories(self):
		self.entries.clear()
		for sub in sorted(os.listdir(self.root_folder)):
			sub_path = os.path.join(self.root_folder, sub)
			if not os.path.isdir(sub_path):
				continue
			for subsub in sorted(os.listdir(sub_path)):
				subsub_path = os.path.join(sub_path, subsub)
				if os.path.isdir(subsub_path) and not subsub.endswith("_standardized"):
					entry = DirectoryEntry(sub, subsub, subsub_path)
					std_path = subsub_path + "_standardized"
					if os.path.isdir(std_path):
						entry.std_folder = std_path
					self.entries.append(entry)

	def _count_modalities(self, path: str) -> dict[str, int]:
		counts: dict[str, int] = {}
		try:
			with os.scandir(path) as entries:
				for e in entries:
					if not e.is_file():
						continue
					if os.path.splitext(e.name)[1].lower() not in IMAGE_EXTENSIONS:
						continue
					modality = e.name.split("_")[-1].split(".")[0]
					counts[modality] = counts.get(modality, 0) + 1
		except PermissionError:
			pass
		return counts

	def _sequence_modality_counts(self) -> dict[str, int]:
		wanted: dict[str, int] = {}
		for modality, _ in self.state.sequence:
			wanted[modality] = wanted.get(modality, 0) + 1
		return wanted

	def _populate_counts_bg(self):
		wanted = self._wanted
		for entry in self.entries:
			counts     = self._count_modalities(entry.path)
			std_counts = self._count_modalities(entry.std_folder) if entry.std_folder else {}
			self._root.after(
				0,
				lambda e=entry, c=counts, sc=std_counts:
					self._update_row_counts(e, c, sc, wanted)
			)

	def _update_single_entry_counts(self, entry: DirectoryEntry):
		counts = self._count_modalities(entry.path)
		std_counts = self._count_modalities(entry.std_folder) if entry.std_folder else {}
		self._root.after(
			0,
			lambda: self._update_row_counts(entry, counts, std_counts, self._wanted)
		)

	def _update_row_counts(self,
						   entry: DirectoryEntry,
						   counts: dict[str, int],
						   std_counts: dict[str, int],
						   wanted: dict[str, int]):
		"""Called on the main thread to patch the placeholder badges."""
		row = self._row_frames.get(entry.path)
		if not row:
			return
		badge_frame = getattr(row, "_badge_frame", None)
		if badge_frame:
			for w in badge_frame.winfo_children():
				w.destroy()
			for modality, n_wanted in sorted(wanted.items()):
				n_have = counts.get(modality, 0)
				color  = "#00aa00" if n_have == n_wanted else "#cc0000"
				badge  = tk.Label(badge_frame,
								  text=f"{n_have}/{n_wanted} {modality}",
								  fg=color, font=("", 9))
				badge.pack(side="left", padx=4)
				badge.bind("<Button-1>",
						   lambda e, en=entry: self._open_assignment(en))

		# Update standardized badge if it exists or was just created
		std_btn = getattr(row, "_std_btn", None)
		if std_btn and std_counts:
			for w in std_btn.winfo_children():
				w.destroy()
			for i, (modality, n_wanted) in enumerate(sorted(wanted.items())):
				n_have = std_counts.get(modality, 0)
				color  = "#006600" if n_have >= n_wanted else "#cc0000"
				text   = f"Standardized: {n_have}/{n_wanted} {modality}" if i == 0 else f"{n_have}/{n_wanted} {modality}"
				badge  = tk.Label(std_btn, text=text, fg=color, font=("", 9), bg="#d9ecd0")
				badge.pack(side="left", padx=2)
				badge.bind("<Button-1>", lambda e, en=entry: self._open_standardized(en))

	# ---- UI -----------------------------------------------------------------

	def _build_ui(self, root: tk.Tk):
		hdr = tk.Frame(root, pady=6)
		hdr.pack(fill="x", padx=10)
		self._header_label = tk.Label(hdr, text="Select a directory to work on:",
									  font=("", 11, "bold"))
		self._header_label.pack(side="left")

		outer, inner, _ = _make_scrollable(root, "vertical")
		outer.pack(fill="both", expand=True, padx=10, pady=(0, 10))

		# CHANGE 1: build rows with "…" placeholder badges immediately
		for entry in self.entries:
			self._build_entry_row(inner, entry)

	def _build_entry_row(self, parent: tk.Frame, entry: DirectoryEntry):
		wanted = self._sequence_modality_counts()

		row = tk.Frame(parent, bd=1, relief="ridge", padx=6, pady=4, cursor="hand2")
		row.pack(fill="x", pady=2)
		self._row_frames[entry.path] = row

		row.bind("<Button-1>", lambda e, en=entry: self._open_assignment(en))

		dir_lbl = tk.Label(row, text=f"{entry.sub}:  {entry.subsub}",
						   font=("", 10), anchor="w")
		dir_lbl.pack(side="left")
		dir_lbl.bind("<Button-1>", lambda e, en=entry: self._open_assignment(en))

		badge_frame = tk.Frame(row)
		badge_frame.pack(side="left", padx=12)
		badge_frame.bind("<Button-1>", lambda e, en=entry: self._open_assignment(en))
		row._badge_frame = badge_frame  # type: ignore[attr-defined]

		for modality in sorted(wanted.keys()):
			badge = tk.Label(badge_frame,
							 text=f"…/{wanted[modality]} {modality}",
							 fg="#888888", font=("", 9))
			badge.pack(side="left", padx=4)
			badge.bind("<Button-1>", lambda e, en=entry: self._open_assignment(en))

		check = tk.Label(row, text="✔", fg="#00aa00", font=("", 14, "bold"))
		check.bind("<Button-1>", lambda e, en=entry: self._open_assignment(en))
		row._check_label = check  # type: ignore[attr-defined]

		if entry.exported:
			check.pack(side="right", padx=6)

		# Standardized column
		if entry.std_folder:
			std_btn = tk.Frame(row, bd=2, relief="raised", padx=6, pady=2,
							   bg="#d9ecd0", cursor="hand2")
			std_btn._is_std_btn = True  # type: ignore[attr-defined]
			std_btn.pack(side="right", padx=8)
			row._std_btn = std_btn  # type: ignore[attr-defined]

			# Placeholder text – replaced by background thread
			for i, modality in enumerate(sorted(wanted.keys())):
				text = f"Standardized: …/{wanted[modality]} {modality}" if i == 0 else f"…/{wanted[modality]} {modality}"
				tk.Label(std_btn, text=text,
						fg="#888888", font=("", 9), bg="#d9ecd0").pack(side="left", padx=2)

			std_btn.bind("<Button-1>",
						 lambda e, en=entry: self._open_standardized(en))

	def _refresh_entry_row(self, entry: DirectoryEntry):
		"""Rebuild the standardized badge for a row after a new export."""
		row = self._row_frames.get(entry.path)
		if not row:
			return

		std_path = entry.path + "_standardized"
		if os.path.isdir(std_path):
			entry.std_folder = std_path

		for widget in row.winfo_children():
			if getattr(widget, "_is_std_btn", False):
				widget.destroy()

		if not entry.std_folder:
			return

		wanted     = self._wanted
		std_counts = self._count_modalities(entry.std_folder)

		std_btn = tk.Frame(row, bd=2, relief="raised", padx=6, pady=2,
						   bg="#d9ecd0", cursor="hand2")
		std_btn._is_std_btn = True  # type: ignore[attr-defined]
		std_btn.pack(side="right", padx=8)
		row._std_btn = std_btn  # type: ignore[attr-defined]

		for i, (modality, n_wanted) in enumerate(sorted(wanted.items())):
			n_have = std_counts.get(modality, 0)
			color  = "#006600" if n_have >= n_wanted else "#cc0000"
			text   = f"Standardized: {n_have}/{n_wanted} {modality}" if i == 0 else f"{n_have}/{n_wanted} {modality}"
			badge  = tk.Label(std_btn, text=text, fg=color, font=("", 9), bg="#d9ecd0")
			badge.pack(side="left", padx=2)
			badge.bind("<Button-1>", lambda e, en=entry: self._open_standardized(en))

		std_btn.bind("<Button-1>",
					 lambda e, en=entry: self._open_standardized(en))

	def _mark_exported(self, entry: DirectoryEntry):
		entry.exported = True
		row = self._row_frames.get(entry.path)
		if row:
			check = getattr(row, "_check_label", None)
			if check:
				check.pack(side="right", padx=6)

	# ---- Opening AssignmentGUI ----------------------------------------------

	def _open_assignment(self, entry: DirectoryEntry):
		self._header_label.config(text=f"Loading {entry.sub}: {entry.subsub}…")
		self._root.update()

		state                 = AppState()
		state.load_sequence_json()
		state.sequence        = list(self.state.sequence)
		state.original_folder = entry.path

		processor = ImageProcessor(state)
		processor.parse_images()

		def on_export_done():
			self._mark_exported(entry)
			self._refresh_entry_row(entry)

		AssignmentGUI(state, processor, on_export_done=on_export_done,
					parent=self._root, browser=self, entry=entry).run()
		self._header_label.config(text="Select a directory to work on:")

	def _open_standardized(self, entry: DirectoryEntry):
		if not entry.std_folder:
			return
		self._header_label.config(
			text=f"Reviewing {entry.sub}: {entry.subsub}…")
		self._root.config(cursor="wait")
		self._root.update()
		StandardizedReviewGUI(entry.std_folder, self._root).run()
		self._root.config(cursor="")
		self._header_label.config(text="Select a directory to work on:")

	# ---- Subprocess export (CHANGE 4) ---------------------------------------

	def launch_export_job(self, entry: DirectoryEntry, job: dict):
		"""
		Write the job to a temp file and launch export_worker.py as a
		subprocess.  Shows "Processing..." in the standardized column immediately and
		starts polling for the .done sentinel.
		"""
		tmp_fd, job_path = tempfile.mkstemp(suffix=".json", prefix="export_job_")
		os.close(tmp_fd)
		with open(job_path, "w") as f:
			json.dump(job, f)

		self._export_jobs[entry.path] = job_path

		self._set_std_pending(entry)

		worker_script = os.path.join(os.path.dirname(__file__), "export_worker.py")
		subprocess.Popen(
			[sys.executable, worker_script, job_path],
			stdout=subprocess.DEVNULL,
			stderr=subprocess.DEVNULL,
		)

		self._start_poll()

	def _set_std_pending(self, entry: DirectoryEntry):
		self._set_badge_text(entry, "Processing…", "#856404")

	def _set_badge_text(self, entry: DirectoryEntry, text: str, color: str = "#856404"):
		row = self._row_frames.get(entry.path)
		if not row:
			return
		badge_frame = getattr(row, "_badge_frame", None)
		if not badge_frame:
			return
		widgets = badge_frame.winfo_children()
		for i, widget in enumerate(widgets):
			widget.config(text=text if i == 0 else "", fg=color)

	def _start_poll(self):
		if self._poll_job_id is not None:
			return   # already polling
		self._poll_jobs()

	def _poll_jobs(self):
		"""Check every 2 s whether any export worker has finished."""
		if not self._export_jobs:
			self._poll_job_id = None
			return

		finished = []
		for entry_path, job_path in list(self._export_jobs.items()):
			done_path = job_path + ".done"
			if os.path.exists(done_path):
				try:
					with open(done_path) as f:
						result = json.load(f)
				except Exception:
					result = {"status": "error", "message": "unreadable sentinel"}

				finished.append((entry_path, job_path, done_path, result))

		for entry_path, job_path in list(self._export_jobs.items()):
			done_path = job_path + ".done"
			if os.path.exists(done_path):
				result = None
				for _ in range(5):
					try:
						with open(done_path) as f:
							content = f.read()
						result = json.loads(content)
						break
					except Exception:
						time.sleep(0.1)
				if result is None:
					result = {"status": "error", "message": "unreadable sentinel"}
				finished.append((entry_path, job_path, done_path, result))

		for entry_path, job_path, done_path, result in finished:
			if entry_path in self._export_jobs:
				del self._export_jobs[entry_path]
			try:
				os.remove(job_path)
				os.remove(done_path)
			except OSError:
				pass

			# Find the matching DirectoryEntry and update the row
			entry = next((e for e in self.entries if e.path == entry_path), None)
			if entry:
				if result.get("status") == "ok":
					self._mark_exported(entry)
					self._refresh_entry_row(entry)
					threading.Thread(
						target=self._update_single_entry_counts,
						args=(entry,),
						daemon=True
					).start()
				else:
					messagebox.showerror(
						"Export failed",
						f"{entry.subsub}:\n{result.get('message', 'unknown error')}"
					)
					# Remove pending badge
					row = self._row_frames.get(entry_path)
					if row:
						for w in row.winfo_children():
							if getattr(w, "_is_std_btn", False):
								w.destroy()

		if self._export_jobs:
			self._poll_job_id = self._root.after(2000, self._poll_jobs)
		else:
			self._poll_job_id = None

	# ---- Window sizing ------------------------------------------------------

	def _size_window(self, root: tk.Tk):
		root.update_idletasks()
		sw = root.winfo_screenwidth()
		sh = root.winfo_screenheight()
		w  = min(root.winfo_reqwidth()  + 40, int(sw * SCREEN_FILL))
		h  = min(root.winfo_reqheight() + 60, int(sh * SCREEN_FILL))
		x  = (sw - w) // 2
		y  = (sh - h) // 2
		root.geometry(f"{w}x{h}+{x}+{y}")

	def _on_close(self):
		if self._export_jobs:
			if not messagebox.askokcancel(
				"Exports in progress",
				"There are exports still running in the background.\n"
				"They will finish even if you close this window.\n\n"
				"Close anyway?"
			):
				return
		self._root.destroy()
		if self.standalone:
			sys.exit(0)


# ===========================================================================
# Standardized Review GUI
# ===========================================================================

class StandardizedReviewGUI:
	"""
	Read-only window showing the contents of a _standardized folder
	as a scrollable grid of thumbnails with filename labels.
	"""

	def __init__(self, std_folder: str, parent: tk.Tk):
		self._std_folder = std_folder
		self._parent     = parent
		self._thumb_size = 280
		self._root: tk.Toplevel | None = None
		self._wrap_frame: tk.Frame | None = None
		# CHANGE 6: debounce handle for reflow
		self._reflow_job: str | None = None

	def run(self):
		root = tk.Toplevel(self._parent)
		self._root = root
		root.title(f"Standardized: {os.path.basename(self._std_folder)}")
		root.transient(self._parent)

		bar = tk.Frame(root)
		bar.pack(fill="x", padx=10, pady=(8, 0))
		tk.Button(bar, text="−", width=2,
				  command=lambda: self._resize_thumbs(-20)).pack(side="left")
		tk.Button(bar, text="+", width=2,
				  command=lambda: self._resize_thumbs(+20)).pack(side="left", padx=(2, 4))
		tk.Button(bar, text="Fit window",
				  command=self._fit_window).pack(side="left", padx=(0, 10))

		outer, inner, _ = _make_scrollable(root, "vertical")
		outer.pack(fill="both", expand=True, padx=10, pady=10)
		self._inner = inner

		self._wrap_frame = tk.Frame(inner)
		self._wrap_frame.pack(fill="x")
		# CHANGE 6: debounced reflow
		self._wrap_frame.bind("<Configure>",
							  lambda e: self._schedule_reflow())

		self._build_grid()

		root.after(200, self._fit_window)
		root.after(200, self._fit_window)
		self._parent.wait_window(root)

	def _load_images(self) -> list[str]:
		try:
			with os.scandir(self._std_folder) as entries:
				return sorted(
					e.path for e in entries
					if e.is_file()
					and os.path.splitext(e.name)[1].lower() in IMAGE_EXTENSIONS
				)
		except PermissionError:
			return []

	def _create_thumbnail(self, path: str, master=None) -> ImageTk.PhotoImage:
		cache_key = (path, self._thumb_size, id(master))
		if cache_key in _GLOBAL_THUMB_CACHE:
			return _GLOBAL_THUMB_CACHE[cache_key]

		ext = os.path.splitext(path)[1].lower()
		with Image.open(path) as img:
			if ext in (".jpg", ".jpeg", ".tif", ".tiff"):
				try:
					img.draft("RGB", (self._thumb_size, self._thumb_size))
				except Exception:
					pass
			img = img.copy()

		img.thumbnail((self._thumb_size, self._thumb_size))
		photo = ImageTk.PhotoImage(img, master=master)
		_GLOBAL_THUMB_CACHE[cache_key] = photo
		return photo

	def _build_grid(self):
		if not self._wrap_frame:
			return
		for w in self._wrap_frame.winfo_children():
			w.destroy()

		for path in self._load_images():
			container = tk.Frame(self._wrap_frame, bd=1, relief="groove",
								 padx=1, pady=1)
			container._img_path = path  # type: ignore[attr-defined]

			# CHANGE 2: label overlay instead of drawn annotation
			thumb = self._create_thumbnail(path, master=self._root)
			lbl = tk.Label(container, image=thumb, bd=0)
			lbl.image = thumb
			lbl.pack()

			index_str = os.path.basename(path).split("_")[0]
			overlay = tk.Label(container, text=index_str,
							   fg="red", bg="black",
							   font=("", 8, "bold"))
			overlay.place(x=4, y=4)

			container.bind("<Button-3>", lambda e, p=path: self._preview_full(p))
			lbl.bind("<Button-3>",       lambda e, p=path: self._preview_full(p))

		self._reflow()

	def _schedule_reflow(self):
		if self._reflow_job is not None:
			self._root.after_cancel(self._reflow_job)
		self._reflow_job = self._root.after(50, self._do_reflow)

	def _reflow(self):
		self._do_reflow()

	def _do_reflow(self):
		self._reflow_job = None
		if not self._wrap_frame:
			return
		containers = [
			w for w in self._wrap_frame.winfo_children()
			if getattr(w, "_img_path", None) is not None
		]
		if not containers:
			return

		cell_w = self._thumb_size + THUMB_GAP
		cell_h = self._thumb_size + THUMB_GAP

		available_w = self._wrap_frame.winfo_width()
		cols = max(1, available_w // cell_w) if available_w > 1 else len(containers)

		for i, container in enumerate(containers):
			row, col = divmod(i, cols)
			container.place(x=col * cell_w, y=row * cell_h)

		n_rows = (len(containers) + cols - 1) // cols
		self._wrap_frame.config(height=n_rows * cell_h)

	def _resize_thumbs(self, delta: int):
		new_size = max(40, min(300, self._thumb_size + delta))
		if new_size == self._thumb_size:
			return
		self._thumb_size = new_size
		self._build_grid()

	def _fit_window(self):
		root = self._root
		if not root.winfo_exists():
			return
		root.geometry("+99999+99999")
		root.update_idletasks()
		root.update()

		sw    = root.winfo_screenwidth()
		sh    = root.winfo_screenheight()
		max_w = int(sw * SCREEN_FILL)
		max_h = int(sh * SCREEN_FILL)

		n_images = len(self._load_images())
		cell_w   = self._thumb_size + THUMB_GAP
		ideal_w  = min(n_images * cell_w + 40, max_w)

		root.geometry(f"{ideal_w}x1+99999+99999")
		root.update_idletasks()
		root.update()

		try:
			canvas    = self._inner.master
			bbox      = canvas.bbox("all")
			content_h = (bbox[3] - bbox[1]) if bbox else 0
		except Exception:
			content_h = self._thumb_size + 40

		chrome_h = sum(
			w.winfo_height() for w in root.winfo_children()
			if isinstance(w, tk.Frame) and w is not self._inner.master.master
		)

		h = min(content_h + chrome_h + 40, max_h)
		x = (sw - ideal_w) // 2
		y = (sh - h) // 2
		root.geometry(f"{ideal_w}x{h}+{x}+{y}")

	def _preview_full(self, path: str):
		win = tk.Toplevel(self._root)
		win.title(os.path.basename(path))

		with Image.open(path) as img:
			img = img.copy()

		sw = int(self._root.winfo_screenwidth()  * 0.8)
		sh = int(self._root.winfo_screenheight() * 0.8)
		img.thumbnail((sw, sh), Image.LANCZOS)

		photo = ImageTk.PhotoImage(img, master=win)
		lbl = tk.Label(win, image=photo)
		lbl.image = photo
		lbl.pack()
		lbl.bind("<Button-1>", lambda e: win.destroy())
		lbl.bind("<Button-3>", lambda e: win.destroy())

		win.update_idletasks()
		w, h = win.winfo_width(), win.winfo_height()
		x = (win.winfo_screenwidth()  // 2) - (w // 2)
		y = (win.winfo_screenheight() // 2) - (h // 2)
		win.geometry(f"{w}x{h}+{x}+{y}")

		win.transient(self._root)
		win.focus_force()
		win.lift()
		win.bind("<Escape>", lambda e: win.destroy())


# ===========================================================================
# Phase 3 GUI – Assign Images
# ===========================================================================

class AssignmentGUI:
	"""
	Main assignment window.

	"""

	def __init__(self, state: AppState, processor: ImageProcessor,
				on_export_done=None, parent: tk.Tk | None = None,
				browser=None, entry=None):
		self.state           = state
		self.processor       = processor
		self._on_export_done = on_export_done
		self._parent         = parent
		self._browser		 = browser
		self._current_entry  = entry

		self._thumb_size = state.thumb_size
		self._root: tk.Tk | None = None

		self._row_widgets: list[tuple[tk.Frame, tk.Label]] = []
		self._pool_frames: dict[str, tk.Frame] = {}
		self._grp_header_vars: dict[str, tk.StringVar] = {}
		self._thumb_labels: dict[str, list[tk.Label]] = {}

		self._active_row_index  = 0
		self._assignment_counts: dict[str, int] = {}
		self._selected_pool_image: str | None = None

		self._warning_var: tk.StringVar | None = None
		self._progress_var: tk.StringVar | None = None

		# CHANGE 6: reflow debounce handles per wrap_frame (widget id -> after id)
		self._reflow_jobs: dict[int, str] = {}

	# ---- Entry point --------------------------------------------------------

	def run(self):
		self.state.assignments = {i: None for i in range(len(self.state.sequence))}
		self.processor.clear_cache()
		self._assignment_counts.clear()

		root = tk.Toplevel(self._parent) if self._parent else tk.Tk()
		self._root = root
		root.title("Assign Images to Sequence")
		root.protocol("WM_DELETE_WINDOW", self._on_close)

		if self._parent:
			root.transient(self._parent)

		self._warning_var  = tk.StringVar(master=root, value="")
		self._progress_var = tk.StringVar(master=root, value="")

		self._build_top_bar(root)
		self._build_main_area(root)
		self._build_bottom_bar(root)
		self._bind_keyboard(root)

		self._update_progress()

		root.after(500, self._fit_window)
		root.after(500, self._fit_window)
		if self._parent:
			self._parent.wait_window(root)
		else:
			root.mainloop()

	def _fit_window(self):
		root = self._root
		if not root.winfo_exists():
			return
		root.geometry("+99999+99999")
		root.update_idletasks()
		root.update()

		sw    = root.winfo_screenwidth()
		sh    = root.winfo_screenheight()
		max_w = int(sw * SCREEN_FILL)
		max_h = int(sh * SCREEN_FILL)

		cell_w = self._thumb_size + THUMB_GAP

		max_pool_images = max(
			(len(paths) for paths in self.state.image_groups.values() if paths),
			default=1
		)
		left_w   = self._thumb_size + 40
		right_w  = max_pool_images * cell_w
		chrome_w = 40
		ideal_w  = left_w + right_w + chrome_w

		def _canvas_content_height(canvas):
			bbox = canvas.bbox("all")
			return bbox[3] - bbox[1] if bbox else 0

		height_fudge    = 40
		left_content_h  = _canvas_content_height(self._left_canvas)
		right_content_h = _canvas_content_height(self._right_canvas)
		content_h       = max(left_content_h, right_content_h)

		chrome_h = sum(
			w.winfo_height() for w in root.winfo_children()
			if isinstance(w, tk.Frame)
			and w is not self._left_canvas.master.master
		)

		ideal_h = content_h + chrome_h + height_fudge

		if ideal_w <= max_w:
			w = ideal_w
		else:
			root.geometry(f"{max_w}x1+99999+99999")
			root.update_idletasks()
			right_content_h = _canvas_content_height(self._right_canvas)
			content_h       = max(_canvas_content_height(self._left_canvas),
								  right_content_h)
			ideal_h = content_h + chrome_h + height_fudge
			w = max_w

		h = min(ideal_h, max_h)
		x = (sw - w) // 2
		y = (sh - h) // 2 - 30
		root.geometry(f"{w}x{h}+{x}+{y}")

	# ---- Layout builders ----------------------------------------------------

	def _build_top_bar(self, root):
		bar = tk.Frame(root)
		bar.pack(fill="x", padx=10, pady=(8, 0))

		tk.Button(bar, text="−", width=2,
				  command=lambda: self._resize_thumbs(-20)).pack(side="left")
		tk.Button(bar, text="+", width=2,
				  command=lambda: self._resize_thumbs(+20)).pack(side="left", padx=(2, 4))
		tk.Button(bar, text="Fit window",
				  command=self._fit_window).pack(side="left", padx=(0, 10))

		tk.Label(bar, textvariable=self._progress_var,
				 font=("", 10)).pack(side="left")

	def _build_main_area(self, root):
		main = tk.Frame(root)
		main.pack(fill="both", expand=True, padx=10, pady=10)

		left_outer, left_inner, left_canvas = _make_scrollable(main, "vertical")
		left_outer.pack(side="left", fill="y")
		self._left_canvas = left_canvas
		self._left_inner  = left_inner
		self._update_left_panel_width()

		right_outer, right_inner, right_canvas = _make_scrollable(main, "vertical")
		right_outer.pack(side="right", fill="both", expand=True)
		self._right_inner  = right_inner
		self._right_canvas = right_canvas

		self._build_sequence_rows(left_inner)
		self._build_pool_panels(right_inner)

	def _build_bottom_bar(self, root):
		bar = tk.Frame(root)
		bar.pack(fill="x", padx=10, pady=6)

		tk.Button(bar, text="✕ Clear Row",
				  command=self._clear_active_row).pack(side="left", padx=8)
		tk.Button(bar, text="Export",
				  command=self._on_export).pack(side="right", padx=8)
		tk.Label(bar, textvariable=self._warning_var,
				 fg="red", font=("", 9)).pack(side="left", padx=8)

	def _bind_keyboard(self, root):
		root.bind("<Delete>",    lambda e: self._clear_active_row())
		root.bind("<BackSpace>", lambda e: self._clear_active_row())
		root.bind("<Return>",    lambda e: self._on_export())
		root.bind("<Up>",        lambda e: self._select_row(self._active_row_index - 1))
		root.bind("<Down>",      lambda e: self._select_row(self._active_row_index + 1))

	# ---- Sequence rows (left panel) -----------------------------------------

	def _build_sequence_rows(self, parent):
		self._row_widgets = []
		for idx, (modality, custom) in enumerate(self.state.sequence):
			row_frame = tk.Frame(parent, bd=1, relief="ridge", padx=4, pady=5)
			row_frame.pack(fill="x", pady=2)

			label_text = f"{idx:03d} – {modality}"
			if custom:
				label_text += f" ({custom})"

			label = tk.Label(row_frame, text=label_text, anchor="w")
			label.pack(anchor="w")

			thumb_label = tk.Label(row_frame)
			thumb_label.pack()

			for widget in (row_frame, label, thumb_label):
				widget.bind("<Button-1>", lambda e, i=idx: self._select_row(i))

			thumb_label.bind("<Button-3>",
							 lambda e, i=idx: self._preview_assigned(i))

			self._row_widgets.append((row_frame, thumb_label))

		self._highlight_active_row()

	# ---- Pool panels (right panel) ------------------------------------------

	def _build_pool_panels(self, parent):
		self._pool_frames.clear()
		self._grp_header_vars.clear()

		for modality, paths in self.state.image_groups.items():
			if not paths:
				continue

			grp_frame = tk.Frame(parent, bd=1, relief="groove", padx=4, pady=4)
			grp_frame.pack(fill="x", pady=4)

			hdr_var = tk.StringVar(master=self._root)
			self._grp_header_vars[modality] = hdr_var
			tk.Label(grp_frame, textvariable=hdr_var,
					 font=("", 10, "bold"), anchor="w").pack(anchor="w")

			wrap_frame = tk.Frame(grp_frame)
			wrap_frame.pack(fill="x")
			self._pool_frames[modality] = wrap_frame

		self._rebuild_pool_thumbnails()

	def _rebuild_pool_thumbnails(self):
		self._thumb_labels.clear()

		# Collect all (modality, path) pairs for the bg thread
		all_paths: list[tuple[str, str]] = []

		for modality, wrap_frame in self._pool_frames.items():
			for w in wrap_frame.winfo_children():
				w.destroy()

			paths = sorted(self.state.image_groups.get(modality, []))

			if modality in self._grp_header_vars:
				self._grp_header_vars[modality].set(f"{modality}  ({len(paths)} images)")

			for path in paths:
				container = tk.Frame(wrap_frame, bd=1, relief="groove",
									 padx=1, pady=1,
									 width=self._thumb_size,
									 height=self._thumb_size)
				container._pool_path = path  # type: ignore[attr-defined]
				container.pack_propagate(False)

				# Placeholder label shown while thumbnail loads
				placeholder = tk.Label(container, text="…",
									   width=self._thumb_size,
									   height=self._thumb_size,
									   bg="#dddddd")
				placeholder.pack(fill="both", expand=True)
				container._placeholder = placeholder  # type: ignore[attr-defined]

				# CHANGE 2: index overlay label (no ImageDraw needed)
				index_str = os.path.basename(path).split("_")[0]
				overlay = tk.Label(container, text=index_str,
								   fg="red", bg="black",
								   font=("", 8, "bold"))
				overlay.place(x=4, y=4)
				overlay.lift()
				container._overlay = overlay  # type: ignore[attr-defined]

				# Image label – starts hidden, shown once thumb is ready
				img_lbl = tk.Label(container, bd=0)
				img_lbl._pool_path = path  # type: ignore[attr-defined]
				container._img_lbl = img_lbl  # type: ignore[attr-defined]

				for w in (container, placeholder, img_lbl):
					w.bind("<Button-1>", lambda e, p=path: self._on_pool_click(p))
					w.bind("<Button-3>", lambda e, p=path: self._preview_full(p))

				self._thumb_labels.setdefault(path, []).append(img_lbl)
				all_paths.append((modality, path))

			# CHANGE 6: debounced reflow
			wrap_frame.bind("<Configure>",
							lambda e, wf=wrap_frame: self._schedule_reflow(wf))
			self._reflow(wrap_frame)

		self._update_pool_availability()
		self._refresh_checkmarks()

		# Launch background thumbnail loader
		root_ref = self._root
		threading.Thread(
			target=self._load_thumbnails_bg,
			args=(all_paths, root_ref),
			daemon=True,
		).start()

	def _load_thumbnails_bg(self, paths: list[tuple[str, str]], master):
		"""Background thread: generate thumbnails and post to main thread."""
		for modality, path in paths:
			size = self._thumb_size
			try:
				photo = self.processor.create_thumbnail(path, size, master=master)
			except Exception:
				continue

			def _install(p=path, ph=photo):
				self._install_thumbnail(p, ph)

			if self._root and self._root.winfo_exists():
				self._root.after(0, _install)

	def _install_thumbnail(self, path: str, photo: ImageTk.PhotoImage):
		"""Main thread: swap placeholder for real thumbnail."""
		for modality, wrap_frame in self._pool_frames.items():
			for container in wrap_frame.winfo_children():
				if getattr(container, "_pool_path", None) != path:
					continue
				img_lbl = getattr(container, "_img_lbl", None)
				placeholder = getattr(container, "_placeholder", None)
				overlay = getattr(container, "_overlay", None)

				if img_lbl is None:
					return

				img_lbl.config(image=photo)
				img_lbl.image = photo
				img_lbl.pack(fill="both", expand=True)

				if placeholder:
					placeholder.destroy()
					container._placeholder = None  # type: ignore[attr-defined]

				if overlay:
					overlay.lift()
				return

	# CHANGE 6: debounced reflow
	def _schedule_reflow(self, wrap_frame: tk.Frame):
		job_id = id(wrap_frame)
		existing = self._reflow_jobs.get(job_id)
		if existing is not None:
			try:
				self._root.after_cancel(existing)
			except Exception:
				pass
		self._reflow_jobs[job_id] = self._root.after(
			50, lambda wf=wrap_frame: self._do_reflow(wf)
		)

	def _reflow(self, wrap_frame: tk.Frame):
		self._do_reflow(wrap_frame)

	def _do_reflow(self, wrap_frame: tk.Frame):
		self._reflow_jobs.pop(id(wrap_frame), None)
		containers = [
			w for w in wrap_frame.winfo_children()
			if getattr(w, "_pool_path", None) is not None
		]
		if not containers:
			return

		cell_w = self._thumb_size + THUMB_GAP
		cell_h = self._thumb_size + THUMB_GAP

		available_w = wrap_frame.winfo_width()
		cols = max(1, available_w // cell_w) if available_w > 1 else len(containers)

		for i, container in enumerate(containers):
			row, col = divmod(i, cols)
			container.place(x=col * cell_w, y=row * cell_h)

		n_rows = (len(containers) + cols - 1) // cols
		wrap_frame.config(height=n_rows * cell_h)

	# ---- Row selection & highlighting ---------------------------------------

	def _select_row(self, index: int):
		index = max(0, min(index, len(self._row_widgets) - 1))
		self._active_row_index = index
		self._highlight_active_row()
		self._scroll_row_into_view(index)

	def _highlight_active_row(self):
		for idx, (frame, _) in enumerate(self._row_widgets):
			frame.config(bg="#4a90d9" if idx == self._active_row_index else "#e8e8e8")
		self._update_pool_availability()

	def _scroll_row_into_view(self, index: int):
		try:
			frame, _ = self._row_widgets[index]
			self._left_inner.update_idletasks()
			total_h = self._left_inner.winfo_height()
			if total_h <= 0:
				return
			fraction = frame.winfo_y() / max(total_h, 1)
			self._left_canvas.yview_moveto(fraction)
		except Exception:
			pass

	def _update_pool_availability(self):
		for modality, wrap_frame in self._pool_frames.items():
			for widget in wrap_frame.winfo_children():
				path = getattr(widget, "_pool_path", None)
				if path is None:
					continue
				compatible = self.state.image_compatible(path, self._active_row_index)
				widget.config(
					relief="groove" if compatible else "flat",
					bd=1 if compatible else 0,
					cursor="hand2" if compatible else "X_cursor",
					bg="#ffffff" if compatible else "#cccccc",
				)

	# ---- Assignment logic ---------------------------------------------------

	def _on_pool_click(self, path: str):
		self._selected_pool_image = path
		self._assign_image(path)

	def _assign_image(self, path: str):
		if not self.state.image_compatible(path, self._active_row_index):
			return

		old_path = self.state.assignments[self._active_row_index]
		if old_path is not None:
			self._assignment_counts[old_path] = max(
				0, self._assignment_counts.get(old_path, 0) - 1)

		self.state.assignments[self._active_row_index] = path
		self._assignment_counts[path] = self._assignment_counts.get(path, 0) + 1

		thumb = self.processor.create_thumbnail(path, self._thumb_size, master=self._root)

		self._row_widgets[self._active_row_index][1].config(image=thumb)
		self._row_widgets[self._active_row_index][1].image = thumb

		self._refresh_checkmarks()
		self._check_duplicate_warning()
		self._update_progress()

		if self._active_row_index + 1 < len(self.state.sequence):
			self._active_row_index += 1
			self._highlight_active_row()
			self._scroll_row_into_view(self._active_row_index)

	def _clear_active_row(self):
		idx      = self._active_row_index
		old_path = self.state.assignments[idx]
		if old_path is None:
			return

		self._assignment_counts[old_path] = max(
			0, self._assignment_counts.get(old_path, 0) - 1)

		self.state.assignments[idx] = None
		self._row_widgets[idx][1].config(image="")
		self._row_widgets[idx][1].image = None

		self._check_duplicate_warning()
		self._update_progress()
		self._refresh_checkmarks()

	# ---- Thumbnail resize ---------------------------------------------------

	def _update_left_panel_width(self):
		padding = 40
		self._left_canvas.config(width=self._thumb_size + padding)

	def _resize_thumbs(self, delta: int):
		new_size = max(40, min(300, self._thumb_size + delta))
		if new_size == self._thumb_size:
			return
		self._thumb_size = new_size
		self.state.thumb_size = new_size

		if hasattr(self, "_save_job"):
			self._root.after_cancel(self._save_job)
		self._save_job = self._root.after(500, self.state.save_sequence_json)

		self._update_left_panel_width()
		self._rebuild_pool_thumbnails()

		for idx, path in self.state.assignments.items():
			if path is not None:
				thumb = self.processor.create_thumbnail(path, self._thumb_size, master=self._root)
				self._row_widgets[idx][1].config(image=thumb)
				self._row_widgets[idx][1].image = thumb

		for wrap_frame in self._pool_frames.values():
			self._reflow(wrap_frame)

	# ---- Checkmarks & warnings ----------------------------------------------

	def _refresh_checkmarks(self):
		assigned_paths = {p for p in self.state.assignments.values() if p is not None}

		for modality, wrap_frame in self._pool_frames.items():
			for container in wrap_frame.winfo_children():
				path = getattr(container, "_pool_path", None)
				if path is None:
					continue
				check_lbl = getattr(container, "_check_lbl", None)
				if check_lbl is None:
					check_lbl = tk.Label(
						container, text="✔", fg="#00bb00",
						font=("", 14, "bold"), bg=container.cget("bg")
					)
					container._check_lbl = check_lbl  # type: ignore[attr-defined]

				if path in assigned_paths:
					check_lbl.place(relx=1.0, rely=0.0, anchor="ne")
				else:
					check_lbl.place_forget()

	def _check_duplicate_warning(self):
		dupes = [p for p, c in self._assignment_counts.items() if c > 1]
		self._warning_var.set(
			"⚠ An image has been selected multiple times" if dupes else ""
		)

	def _update_progress(self):
		total    = len(self.state.sequence)
		assigned = sum(1 for v in self.state.assignments.values() if v is not None)
		self._progress_var.set(f"{assigned} / {total} assigned")

	# ---- Full-size preview --------------------------------------------------

	def _preview_assigned(self, row_index: int):
		path = self.state.assignments.get(row_index)
		if path:
			self._preview_full(path)

	def _preview_full(self, path: str):
		win = tk.Toplevel(self._root)
		win.title(os.path.basename(path))

		with Image.open(path) as img:
			img = img.copy()

		sw = int(self._root.winfo_screenwidth()  * 0.8)
		sh = int(self._root.winfo_screenheight() * 0.8)
		img.thumbnail((sw, sh), Image.LANCZOS)

		photo = ImageTk.PhotoImage(img, master=win)
		lbl = tk.Label(win, image=photo)
		lbl.image = photo
		lbl.pack()
		lbl.bind("<Button-1>", lambda e: win.destroy())
		lbl.bind("<Button-3>", lambda e: win.destroy())

		win.update_idletasks()
		w, h = win.winfo_width(), win.winfo_height()
		x = (win.winfo_screenwidth()  // 2) - (w // 2)
		y = (win.winfo_screenheight() // 2) - (h // 2)
		win.geometry(f"{w}x{h}+{x}+{y}")

		win.transient(self._root)
		win.focus_force()
		win.lift()
		win.bind("<Escape>", lambda e: win.destroy())

	# ---- Export -------------------------------------------------------------

	def _on_export(self):
		s = self.state
		if not s.mouse_number or not s.eye:
			messagebox.showerror("Error", "Metadata not parsed. Please re-select the folder.")
			return

		job = self.processor.build_job()

		# If we have a parent DirectoryBrowserGUI, use the subprocess path
		if self._browser is not None:
			self._browser.launch_export_job(self._current_entry, job)
			if self._on_export_done:
				self._on_export_done()
			self._root.destroy()
			return

		# Fallback: in-process export (used when opened standalone)
		root = self._root

		def do_export():
			import tempfile, subprocess as sp
			tmp_fd, job_path = tempfile.mkstemp(suffix=".json", prefix="export_job_")
			os.close(tmp_fd)
			with open(job_path, "w") as f:
				json.dump(job, f)
			done_path = job_path + ".done"
			worker = os.path.join(os.path.dirname(__file__), "export_worker.py")
			sp.run([sys.executable, worker, job_path])
			try:
				with open(done_path) as f:
					result = json.load(f)
			except Exception:
				result = {"status": "error", "message": "no sentinel"}
			os.remove(job_path)
			try:
				os.remove(done_path)
			except OSError:
				pass
			if self._on_export_done:
				root.after(0, self._on_export_done)

		threading.Thread(target=do_export, daemon=True).start()
		root.destroy()

	# ---- Window close -------------------------------------------------------

	def _on_close(self):
		self._root.destroy()


# ===========================================================================
# Scrollable Frame Helper
# ===========================================================================

def _make_scrollable(
	parent: tk.Widget, orient: str = "vertical"
) -> tuple[tk.Frame, tk.Frame, tk.Canvas]:
	outer  = tk.Frame(parent)
	canvas = tk.Canvas(outer, highlightthickness=0)

	if orient == "vertical":
		sb = tk.Scrollbar(outer, orient="vertical", command=canvas.yview)
		canvas.configure(yscrollcommand=sb.set)
		sb.pack(side="right", fill="y")
		canvas.pack(side="left", fill="both", expand=True)
	else:
		sb = tk.Scrollbar(outer, orient="horizontal", command=canvas.xview)
		canvas.configure(xscrollcommand=sb.set)
		sb.pack(side="bottom", fill="x")
		canvas.pack(side="top", fill="both", expand=True)

	inner     = tk.Frame(canvas)
	window_id = canvas.create_window((0, 0), window=inner, anchor="nw")

	def _on_canvas_configure(event):
		canvas.configure(scrollregion=canvas.bbox("all"))
		if orient == "vertical":
			canvas.itemconfig(
				window_id,
				width=event.width if event.width > 1 else canvas.winfo_width()
			)

	inner.bind("<Configure>",  lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
	canvas.bind("<Configure>", _on_canvas_configure)

	def _on_mousewheel(event):
		if orient == "vertical":
			canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
		else:
			canvas.xview_scroll(int(-1 * (event.delta / 120)), "units")

	canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _on_mousewheel))
	canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))

	return outer, inner, canvas


# ===========================================================================
# Orchestrator
# ===========================================================================

class ImageSequenceStandardizer:
	def run(self, sequence=None, root_folder=None, parent=None):
		state = AppState()
		standalone = sequence is None and root_folder is None

		if sequence is not None:
			state.sequence = sequence
			state.save_sequence_json()
		else:
			SequenceDialog(state, standalone=standalone).run()
			if not state.sequence:
				return
			for item in state.sequence:
				print(item)

		if root_folder is None:
			root_folder = _choose_directory()
			if not root_folder:
				return

		DirectoryBrowserGUI(root_folder, state, standalone=standalone, parent=parent).run()


def _choose_directory() -> str | None:
	root = tk.Tk()
	root.withdraw()
	folder = filedialog.askdirectory(title="Select Image Folder")
	root.destroy()
	return folder if folder else None


# ===========================================================================
# Entry point
# ===========================================================================

if __name__ == "__main__":
	ImageSequenceStandardizer().run()