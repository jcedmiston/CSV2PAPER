import csv
import os
import platform
import queue
import subprocess
import threading
from os import mkdir, unlink
from os.path import abspath, isdir, join, normpath
from tempfile import NamedTemporaryFile
from tkinter import *
from tkinter import messagebox, ttk

from docx2pdf import convert
from drag_drop_listbox import DragDropListbox

from files import __location__
from mailmerge_tracking import MailMergeTracking

class Convert:
	def __init__(self, base, field_map, files, output_as_word, output_as_pdf, user_settings, limit=None):
		self.field_map = field_map
		self.files = files
		self.output_as_word = output_as_word
		self.output_as_pdf = output_as_pdf
		self.user_settings = user_settings

		self.window_bg = None
		self.widget_bg = None
		self.fg = None
		self.insert_bg = None
		self.disabled_bg = 'gray80'
		self.select_bg = None
		self.folder_icon_file = None
		self.up_arrow_icon_file = None
		self.down_arrow_icon_file = None
		self.set_colors()

		self.run_popup = Toplevel(takefocus=True)
		self.run_popup.focus_force()
		#self.run_popup.grab_set()
		self.run_popup.protocol("WM_DELETE_WINDOW", self.on_closing)

		self.run_popup.wm_title("Converting...")
		self.run_popup.resizable(0, 0)
		self.run_popup.columnconfigure(0,weight=1)
		self.run_popup.configure(bg=self.window_bg)

		self.running_description = StringVar(value="Mapping data to fields...")
		self.running_description_label = Label(self.run_popup, bg=self.window_bg, fg=self.fg, textvariable=self.running_description, justify=LEFT)
		self.running_description_label.grid(row=1, column=0, pady=(10,0), padx=5, sticky=W)

		s = ttk.Style()
		s.theme_use('alt')
		s.configure('blue.Horizontal.TProgressbar', troughcolor  = 'gray35', troughrelief = 'flat', background = '#2f92ff')
		self.progress = ttk.Progressbar(self.run_popup, style = 'blue.Horizontal.TProgressbar', orient="horizontal",length=250, mode="determinate")
		self.progress_indeterminate = ttk.Progressbar(self.run_popup, style = 'blue.Horizontal.TProgressbar', orient="horizontal",length=250, mode="indeterminate")
		if limit is None:
			with open(self.files.csv_file, encoding='utf8', newline='') as csv_file:
				self.num_records = sum(1 for row in csv.reader(csv_file)) - 1
		else:
			self.num_records = limit
		self.progress["maximum"] = self.num_records
		self.progress_indeterminate["maximum"] = 100
		
		self.running_count = StringVar(value="0 of "+str(self.num_records))
		self.running_count_label = Label(self.run_popup, bg=self.window_bg, fg=self.fg, textvariable=self.running_count, justify=LEFT)
		self.running_count_label.grid(row=1, column=1, pady=(10,0), padx=5, sticky=E)
		self.progress.grid(row=2, column=0, columnspan=2, pady=(0,20), padx=5, sticky='ew')
		
		self.run_popup.update_idletasks()
		x = base.winfo_rootx()
		y = base.winfo_rooty()
		x_offset = base.winfo_width() / 2 - self.run_popup.winfo_width() / 2
		y_offset = base.winfo_height() / 4 - self.run_popup.winfo_height() / 2
		geom = "+%d+%d" % (x+x_offset,y+y_offset)
		self.run_popup.wm_geometry(geom)

		self.queue = queue.Queue()
		self.cancel_convert = threading.Event()
		self.thread = threading.Thread(target=self.write_out, args=(self.cancel_convert,limit))
		self.thread.start()
		self.run_popup.after(1, self.refresh_data)
		
	def refresh_data(self):
		"""
		"""
		# do nothing if the aysyncio thread is dead
		# and no more data in the queue
		if not self.thread.is_alive() and self.queue.empty():
			self.run_popup.destroy()
			return

        # refresh the GUI with new data from the queue
		while not self.queue.empty():
			progress, description, mode = self.queue.get()
			if mode == "determinate":
				self.progress['value'] = progress
				self.running_description.set(description)
				self.running_count.set(str(progress)+" of "+str(self.num_records))
			elif mode == "indeterminate":
				self.progress.destroy()
				self.running_count_label.destroy()
				self.progress_indeterminate.grid(row=2, column=0, columnspan=2, pady=(0,20), padx=5, sticky='ew')
				self.progress_indeterminate.start(20)
				self.running_description.set(description)
			elif mode == "holding":
				pass
			elif mode == "finished":
				self.progress_indeterminate.stop()

			self.run_popup.update()

		#  timer to refresh the gui with data from the asyncio thread
		self.run_popup.after(1, self.refresh_data)

	def write_out(self, stopped, limit):
		with open(self.files.csv_file, encoding='utf8', newline='') as csv_file:
			csv_dict = csv.DictReader(csv_file)
				
			document = MailMergeTracking(self.files.template)
			merge_data = []
			progress = 0
			for row in csv_dict:
				if limit is not None:
					if progress == limit:
						break
				if not stopped.is_set(): 
					merge_data.append({field:row[self.field_map[field]] for field in document.get_merge_fields()})
					progress += 1
					self.queue.put((progress, "Mapping data to fields...", "determinate"))
				else: return

		if not stopped.is_set():
			self.queue.put((self.num_records, "Mapping data to fields...", "determinate"))
		else: return

		self.queue.put((0, "Merging into template...", "determinate"))
		document.merge_templates(merge_data, separator="page_break", queue=self.queue, stopped=stopped)
		self.queue.put((self.num_records, "Merging into template...", "determinate"))

		docx_filename = str(self.files.filename)+".docx"
		pdf_filename = str(self.files.filename)+".pdf"

		if not stopped.is_set():
			self.queue.put((None, "Saving...", "indeterminate"))
			if not isdir(self.files.folder):
				mkdir(self.files.folder)
		else: return

		docx_filepath = normpath(abspath(join(self.files.folder, docx_filename)))
		pdf_filepath = normpath(abspath(join(self.files.folder, pdf_filename)))

		if not stopped.is_set():
			if not self.output_as_word:
				temp_docx = NamedTemporaryFile(delete=False, suffix=".docx")
				temp_docx.close()
				document.write(temp_docx.name)
				document.close()
				try:
					convert(temp_docx.name, pdf_filepath)
				except NotImplementedError:
					pass
				unlink(temp_docx.name)
			if not self.output_as_pdf:
				document.write(docx_filepath)
				document.close()
			if self.output_as_word and self.output_as_pdf:
				document.write(docx_filepath)
				document.close()
				try:
					convert(docx_filepath, pdf_filepath) 
				except NotImplementedError:
					pass
		else: return
		
		if not stopped.is_set():
			self.queue.put((None, "Opening...", "holding"))
			if platform.system() == 'Darwin':       # macOS
				if self.output_as_word:
					subprocess.call(('open', docx_filepath))
				if self.output_as_pdf:
					subprocess.call(('open', pdf_filepath))
			elif platform.system() == 'Windows':    # Windows
				if self.output_as_word:
					os.startfile(docx_filepath)
				if self.output_as_pdf:
					os.startfile(pdf_filepath)
			else:                                   # linux variants
				if self.output_as_word:
					subprocess.call(('xdg-open', docx_filepath))
			
			self.queue.put((None, "Opening...", "finished"))
		else: return
	
	def on_closing(self):
		if messagebox.askyesno("CSV 2 Paper", "Are you sure you want to cancel?"):
			self.cancel_convert.set()
			if self.thread.is_alive():
				self.thread.join()
			self.run_popup.destroy()

	def set_colors(self):
		if self.user_settings.dark_mode_enabled:
			self.window_bg = 'gray15'
			self.widget_bg = 'gray35'
			self.fg = 'white'
			self.insert_bg = 'white'
			self.disabled_bg = 'gray20'
			self.select_bg = 'gray30'
			self.folder_icon_file = join(__location__, 'resources', 'folder_open', '2x', 'sharp_folder_open_white_48dp.png')
			self.up_arrow_icon_file = join(__location__, 'resources', 'cheveron_up', '2x', 'sharp_chevron_up_white_48dp.png')
			self.down_arrow_icon_file = join(__location__, 'resources', 'cheveron_down', '2x', 'sharp_chevron_down_white_48dp.png')
		else:
			self.window_bg = 'SystemButtonFace'
			self.widget_bg = 'SystemWindow'
			self.fg = 'SystemWindowText'
			self.insert_bg = 'SystemWindowText'
			self.disabled_bg = 'gray80'
			self.select_bg = 'SystemWindow'
			self.folder_icon_file = join(__location__, 'resources', 'folder_open', '2x', 'sharp_folder_open_black_48dp.png')
			self.up_arrow_icon_file = join(__location__, 'resources', 'cheveron_up', '2x', 'sharp_chevron_up_black_48dp.png')
			self.down_arrow_icon_file = join(__location__, 'resources', 'cheveron_down', '2x', 'sharp_chevron_down_black_48dp.png')
