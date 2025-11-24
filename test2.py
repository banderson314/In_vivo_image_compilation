import tkinter as tk

class DraggableDropdownApp(tk.Tk):
	def __init__(self):
		super().__init__()
		self.title("Dynamic Dropdown Selector")
		self.available_types = [
			"cSLO BAF",
			"cSLO IRAF",
			"OCT Superior",
			"OCT Vertical",
			"OCT Horizontal"
		]

		self.menu_frame = tk.Frame(self)
		self.menu_frame.pack(fill="both", expand=True, pady=10)

		self.dropdown_rows = []
		self.drag_data = None

		self.add_dropdown()  # Start with one OptionMenu

		tk.Button(self, text="Print Selection Order", command=self.print_order).pack(pady=10)

	def add_dropdown(self, default=None):
		frame = tk.Frame(self.menu_frame, pady=0)
		frame.grid(sticky="ew", padx=2, pady=0)
		frame.columnconfigure(1, weight=1)  # column 1 (menu) expands

		var = tk.StringVar(value=default or "Select image type")

		# Drag handle (hidden initially)
		handle = tk.Label(frame, text="≡", font=("Arial", 14), cursor="fleur")
		handle.bind("<Button-1>", self.start_drag)
		handle.bind("<B1-Motion>", self.do_drag)
		handle.bind("<ButtonRelease-1>", self.stop_drag)
		# Do not grid yet

		# Dropdown menu
		menu = tk.OptionMenu(frame, var, *self.available_types,
							 command=lambda val, v=var, f=frame, h=handle: self.option_selected(v, f, h))
		menu.grid(row=0, column=1, sticky="ew", padx=2, pady=0)

		# Remove button (hidden initially)
		remove_btn = tk.Button(frame, text="✕", relief="flat", bd=0,
						 command=lambda f=frame: self.remove_dropdown(f))
		# Do not grid yet

		self.dropdown_rows.append((frame, var, handle, remove_btn))

	def option_selected(self, var, frame, handle):
		if var.get() != "Select image type":
			# Show handle on the left
			handle.grid(row=0, column=0, padx=(0,2))
			# Show remove button on the right
			for f, v, h, remove_btn in self.dropdown_rows:
				if f == frame:
					remove_btn.grid(row=0, column=2, padx=(2,0))
					break
			# Add a new dropdown if this is the last
			if var == self.dropdown_rows[-1][1]:
				self.add_dropdown()
			self.repack_dropdowns()

	def remove_dropdown(self, frame):
		for i, (f, v, h, r) in enumerate(self.dropdown_rows):
			if f == frame:
				f.destroy()
				del self.dropdown_rows[i]
				break
		self.repack_dropdowns()

	# --- Drag & reorder logic ---
	def start_drag(self, event):
		widget = event.widget.master
		self.drag_data = {"widget": widget, "start_y": event.y_root, "orig_index": self.get_row_index(widget)}
		widget.lift()

		# Find the OptionMenu in this frame
		for child in widget.winfo_children():
			if isinstance(child, tk.OptionMenu):
				child.config(bg="#929292")  # highlight only the menu
				break


	def do_drag(self, event):
		if not self.drag_data:
			return

		widget = self.drag_data["widget"]
		y = event.y_root
		widget.lift()

		# Find which frame we’re hovering over
		hover_index = None
		for i, (f, *_rest) in enumerate(self.dropdown_rows):
			if f == widget or i == len(self.dropdown_rows) - 1:  # skip last row
				continue
			fy = f.winfo_rooty()
			fh = f.winfo_height()
			if fy < y < fy + fh:
				hover_index = i
				break

		current_index = self.get_row_index(widget)
		if hover_index is not None and hover_index != current_index:
			# Reorder
			self.dropdown_rows.insert(hover_index, self.dropdown_rows.pop(current_index))
			self.repack_dropdowns()

		self.drag_data["start_y"] = y

	def stop_drag(self, event):
		if not self.drag_data:
			return

		widget = self.drag_data["widget"]

		# Find the OptionMenu child of this frame
		for child in widget.winfo_children():
			if isinstance(child, tk.OptionMenu):
				child.config(bg="#f0f0f0")
				break

		self.drag_data = None


	def get_row_index(self, frame):
		for i, (f, *_rest) in enumerate(self.dropdown_rows):
			if f == frame:
				return i
		return None

	def repack_dropdowns(self):
		"""Repack frames using grid with proper row order."""
		for i, (f, *_rest) in enumerate(self.dropdown_rows):
			f.grid(row=i, column=0, columnspan=3, sticky="ew", pady=3)

	def print_order(self):
		order = [var.get() for _, var, *_ in self.dropdown_rows if var.get() != "Select image type"]
		print("Selected order:", order)


if __name__ == "__main__":
	app = DraggableDropdownApp()
	app.mainloop()
