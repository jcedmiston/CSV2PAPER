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
from tkinter import filedialog, messagebox, ttk

from docx2pdf import convert
from dragdroplistbox import DragDropListbox
from files import FilePaths, __location__
from mailmerge_tracking import MailMergeTracking
from UpdateChecker import Updater
from WindowsStyleButton import WindowsButton


class App:
	def __init__(self, base):
		self.files = FilePaths()

		self.base = base
		self.base.title("CSV 2 Paper")
		self.base.columnconfigure(1,weight=1)    #confiugures to stretch with a scaler of 1.
		self.base.rowconfigure(5,weight=1)
		self.base.columnconfigure(2,weight=1)
		self.base.protocol("WM_DELETE_WINDOW", self.on_closing)

		self.menu_bar = Menu(base)
		
		self.help_menu = Menu(self.menu_bar, tearoff=0)
		self.help_menu.add_command(label="About...", command=self.about_popup)
		self.menu_bar.add_cascade(label="Help", menu=self.help_menu)
		
		self.base.config(menu=self.menu_bar)


		self.template = StringVar(value="Word Template")
		self.template_entry = Entry(textvariable=self.template)
		self.template_entry.configure(validate="focusout", validatecommand = lambda:self.template_file_text())
		self.template_file_selector = Button(base, text ='+', command = lambda:self.template_file_opener())
		self.template_entry.grid(row=1,column=1,columnspan=2,sticky='we',padx=(5, 30),pady=(0,0))
		self.template_file_selector.grid(row=1,column=1,columnspan=2,sticky=E,padx=(0, 5),pady=5)


		self.csv = StringVar(value="CSV")
		self.csv_entry = Entry(state='disabled', textvariable=self.csv)
		self.csv_entry.configure(validate="focusout", validatecommand = lambda:self.csv_file_text())
		self.csv_file_selector = Button(base, text ='+', state='disabled', command = lambda:self.csv_file_opener())
		self.csv_entry.grid(row=2,column=1,columnspan=2,sticky='we',padx=(5, 30),pady=5)
		self.csv_file_selector.grid(row=2,column=1,columnspan=2,sticky=E,padx=(0, 5),pady=5)


		self.folder = StringVar(value="Output Folder")
		self.folder_entry = Entry(state='disabled', textvariable=self.folder)
		self.folder_entry.configure(validate="focusout", validatecommand = lambda:self.directory_selctor_text())
		self.folder_selector = Button(base, text ='+', state='disabled', command = lambda:self.directory_selector())
		self.folder_entry.grid(row=3,column=1,columnspan=2,sticky='we',padx=(5, 30),pady=5)
		self.folder_selector.grid(row=3,column=1,columnspan=2,sticky=E,padx=(0, 5),pady=5)


		self.file_output_info_group = Frame(base)
		self.file_output_info_group.grid(row=4,column=1, columnspan=2,padx=5,pady=5, sticky='nsew')
		self.file_output_info_group.columnconfigure(0,weight=1)
		self.file_output_info_group.rowconfigure(0,weight=1)

		self.filename = StringVar(value="Output File")
		self.filename_entry = Entry(self.file_output_info_group, state='disabled', textvariable=self.filename)

		self.output_as_word = BooleanVar(value=True)
		self.docx_checkbox = Checkbutton(self.file_output_info_group, state='disabled', text='Word', variable=self.output_as_word, onvalue=True, offvalue=False, command=self.check_runnable)
		
		self.output_as_pdf = BooleanVar(value=True)
		self.pdf_checkbox = Checkbutton(self.file_output_info_group, state='disabled', text='PDF', variable=self.output_as_pdf, onvalue=True, offvalue=False, command=self.check_runnable)

		self.filename_entry.grid(row=0,column=0,sticky='we',padx=(0, 30))
		self.docx_checkbox.grid(row=0,column=1,sticky='we',padx=(5, 30))
		self.pdf_checkbox.grid(row=0,column=3,sticky='we',padx=(5, 30))


		self.left_merge_fields_group = Frame(base)
		self.left_merge_fields_group.grid(row=5,column=1, padx=5,pady=5, sticky='nsew')
		self.left_merge_fields_group.columnconfigure(0,weight=1)
		self.left_merge_fields_group.rowconfigure(1,weight=1)

		self.merge_field_label = Label(self.left_merge_fields_group, text="Template Fields", justify=CENTER, padx=10, pady=5)
		self.merge_field_label.grid(row=0,column=0, sticky='nsew')

		self.scroll_merge_fields_y = Scrollbar(self.left_merge_fields_group, orient=VERTICAL)
		self.scroll_merge_fields_x = Scrollbar(self.left_merge_fields_group, orient=HORIZONTAL)

		self.merge_fields_listbox = Listbox(self.left_merge_fields_group, height=20, width=30, yscrollcommand=self.scroll_merge_fields_y.set, xscrollcommand=self.scroll_merge_fields_x.set, exportselection=0)
		self.merge_fields_listbox.bind("<<ListboxSelect>>", self.on_select)
		self.merge_fields_listbox.grid(row=1,column=0, sticky='nsew')

		self.scroll_merge_fields_y.config(command = self.merge_fields_listbox.yview)
		self.scroll_merge_fields_y.grid(row=1,column=1, sticky='nsew')

		self.scroll_merge_fields_x.config(command = self.merge_fields_listbox.xview)
		self.scroll_merge_fields_x.grid(row=2,column=0, sticky='nsew')


		self.right_headers_group = Frame(base)
		self.right_headers_group.grid(row=5,column=2, padx=5,pady=5, sticky='nsew')
		self.right_headers_group.columnconfigure(0,weight=1)
		self.right_headers_group.rowconfigure(1,weight=1)

		self.headers_label = Label(self.right_headers_group, text="Data Headers", justify=CENTER, padx=10, pady=5)
		self.headers_label.grid(row=0,column=0, sticky='nsew')

		self.scroll_headers_y = Scrollbar(self.right_headers_group, orient=VERTICAL)
		self.scroll_headers_x = Scrollbar(self.right_headers_group, orient=HORIZONTAL)

		self.headers_listbox = Listbox(self.right_headers_group, height=20, width=30, yscrollcommand=self.scroll_headers_y.set, xscrollcommand=self.scroll_headers_x.set, exportselection=0, )
		self.headers_listbox.bind("<<ListboxSelect>>", self.on_select)
		self.headers_listbox.grid(row=1,column=0, sticky='nsew')

		self.scroll_headers_y.config(command = self.headers_listbox.yview)
		self.scroll_headers_y.grid(row=1,column=1, sticky='nsew')

		self.scroll_headers_x.config(command = self.headers_listbox.xview)
		self.scroll_headers_x.grid(row=2,column=0, sticky='nsew')

		self.edit_header_buttons = Frame(self.right_headers_group)
		self.edit_header_buttons.grid(row=1,column=2, rowspan=2, padx=5,pady=5, sticky='nsew')

		self.up_arrow_icon = PhotoImage(file = join(__location__, 'BundledResources','up-arrow.png')).subsample(30, 30)
		self.move_header_up_button = Button(self.edit_header_buttons, image=self.up_arrow_icon, command=lambda: self.move_up())
		self.move_header_up_button.grid(row=0,column=0, sticky='ew')

		self.down_arrow_icon = PhotoImage(file = join(__location__, 'BundledResources', 'down-arrow.png')).subsample(30, 30)
		self.move_header_down_button = Button(self.edit_header_buttons, image=self.down_arrow_icon, command=lambda: self.move_down())
		self.move_header_down_button.grid(row=1,column=0, sticky='ew')

		self.run = WindowsButton(base, text ='Run', state='disabled', command = self.run_op)
		self.run.grid(row=6,column=1, columnspan=2,padx=5,pady=5)
		
		self.base.withdraw()
		Updater(self.base)

	def template_file_opener(self):
		template_file = filedialog.askopenfilename(filetypes=[("Word Document", ".docx")])
		self.files.template = template_file
		self.template_entry.delete(0,END)
		self.template_entry.insert(0,template_file)
		with MailMergeTracking(self.files.template) as document:
			fields = document.get_merge_fields()
			fields = sorted(fields)
			self.merge_fields_listbox.delete(0,END)
			for field in fields:
				self.merge_fields_listbox.insert(END, field)

		self.csv_entry.configure(state='normal')
		self.csv_file_selector.configure(state='normal')

	def template_file_text(self):
		self.files.template = abspath(self.template_entry.get())
		with MailMergeTracking(self.files.template) as document:
			fields = document.get_merge_fields()
			fields = sorted(fields)
			self.merge_fields_listbox.delete(0,END)
			for field in fields:
				self.merge_fields_listbox.insert(END, field)

	def csv_file_opener(self):
		csv_file = filedialog.askopenfilename(filetypes=[("CSV", ".csv")])
		self.files.csv_file = csv_file
		self.csv_entry.delete(0, END)
		self.csv_entry.insert(0, csv_file)
		with open(self.files.csv_file, encoding='utf8', newline='') as csv_file:
			csv_list = csv.reader(csv_file)
			headers = next(csv_list)
			'''
			data = next(csv_list) # new feature - show data preview
			output = []
			for i in range(len(headers)):
				output.append(headers[i]+" "+data[i])
			headers = sorted(output) # end new feature
			'''
			headers = sorted(headers)
			self.headers_listbox.delete(0,END)
			for header in headers:
				self.headers_listbox.insert(END, header)

		self.folder_entry.configure(state='normal')
		self.folder_selector.configure(state='normal')
	
	def csv_file_text(self):
		self.files.csv_file = self.csv_entry.get()
		with open(self.files.csv_file, encoding='utf8', newline='') as csv_file:
			csv_list = csv.reader(csv_file)
			headers = next(csv_list)
			'''
			data = next(csv_list) # new feature - show data preview
			output = []
			for i in range(len(headers)):
				output.append(headers[i]+" "+data[i])
			headers = sorted(output) # end new feature
			'''
			headers = sorted(headers)
			self.headers_listbox.delete(0,END)
			for header in headers:
				self.headers_listbox.insert(END, header)

	def directory_selector(self):
		folder_selected = filedialog.askdirectory()
		self.files.folder = folder_selected
		self.folder_entry.delete(0,END)
		self.folder_entry.insert(0,folder_selected)

		self.filename_entry.configure(state='normal')
		self.run.configure(state='normal')
		self.pdf_checkbox.configure(state='normal')
		self.docx_checkbox.configure(state='normal')

	def directory_selctor_text(self):
		self.files.folder = self.folder_entry.get()

	def on_select(self, sender):
		listbox = sender.widget
		try:
			idxs = listbox.curselection()
			if not idxs:
				return
			for pos in idxs:
				self.merge_fields_listbox.selection_clear(0,END)
				self.merge_fields_listbox.selection_set(pos)
				self.merge_fields_listbox.see(pos)
				self.merge_fields_listbox.activate(pos)

				self.headers_listbox.selection_clear(0,END)
				self.headers_listbox.selection_set(pos)
				self.headers_listbox.activate(pos)
		except:
			pass

	def move_up(self):
		try:
			idxs = self.headers_listbox.curselection()
			if not idxs:
				return
			for pos in idxs:
				if pos==0:
					self.merge_fields_listbox.selection_clear(0,END)
					self.merge_fields_listbox.selection_set(pos)
					self.merge_fields_listbox.see(pos)
					continue
				text=self.headers_listbox.get(pos)
				self.headers_listbox.delete(pos)
				self.headers_listbox.insert(pos-1, text)
				self.headers_listbox.selection_set(pos-1)
				self.headers_listbox.activate(pos-1)
				self.merge_fields_listbox.selection_clear(0,END)
				self.merge_fields_listbox.selection_set(pos-1)
		except:
			pass

	def move_down(self):
		try:
			idxs = self.headers_listbox.curselection()
			if not idxs:
				return
			for pos in idxs:
				# Are we at the bottom of the list?
				if pos == self.headers_listbox.size()-1:
					self.merge_fields_listbox.selection_clear(0,END)
					self.merge_fields_listbox.selection_set(pos)
					self.merge_fields_listbox.see(pos)
					continue
				text=self.headers_listbox.get(pos)
				self.headers_listbox.delete(pos)
				self.headers_listbox.insert(pos+1, text)
				self.headers_listbox.selection_set(pos+1)
				self.headers_listbox.activate(pos+1)
				self.merge_fields_listbox.selection_clear(0,END)
				self.merge_fields_listbox.selection_set(pos+1)
		except:
			pass
	
	def check_runnable(self):
		if not self.output_as_word.get() and not self.output_as_pdf.get():
			self.run.configure(state='disabled')
		if self.output_as_word.get() or self.output_as_pdf.get():
			self.run.configure(state='normal')

	def about_popup(self):
		about_win = Toplevel(takefocus=True)
		about_win.focus_force()
		about_win.grab_set()
		about_win.wm_title("About CSV 2 Paper")
		about_win.resizable(0, 0)
		about_win.columnconfigure(0,weight=1)
		about_text = """Material Design Icon Pack made by\nGoogle (flaticon.com/authors/google")\nRetrieved from Flaticon (flaticon.com)\nLicense under Creative Commons 3.0 BY\n(creativecommons.org/licenses/by/3.0/)"""
		about_label = Label(about_win, text=about_text, justify=CENTER, padx=10, pady=5)
		about_label.grid(row=0, column=0, sticky="nsew")
		close_button = Button(about_win, text="Close", command=about_win.destroy, justify=CENTER)
		close_button.grid(row=1, column=0, pady=5, padx=5)
		about_win.update_idletasks() 
		x = self.base.winfo_rootx()
		y = self.base.winfo_rooty()
		x_offset = self.base.winfo_width() / 2 - about_win.winfo_width() / 2
		y_offset = self.base.winfo_height() / 4 - about_win.winfo_height() / 2
		geom = "+%d+%d" % (x+x_offset,y+y_offset)
		about_win.wm_geometry(geom)

	def map_fields(self):
		headers = self.headers_listbox.get(0,END)
		fields = self.merge_fields_listbox.get(0,END)
		map = {}
		for index in range(len(fields)):
			map[fields[index]] = headers[index]
		return map

	def run_op(self):
		map = self.map_fields()
		self.files.template = self.template_entry.get()
		self.files.csv_file = self.csv_entry.get()
		self.files.folder = self.folder_entry.get()
		Run(self.base, map, self.files, self.output_as_word.get(), self.output_as_word.get())

	def on_closing(self):
		self.base.destroy()

class Run:
	def __init__(self, base, map, files, output_as_word, output_as_pdf):
		self.map = map
		self.files = files
		self.output_as_word = output_as_word
		self.output_as_pdf = output_as_pdf

		self.run_popup = Toplevel(takefocus=True)
		self.run_popup.focus_force()
		self.run_popup.grab_set()
		self.run_popup.protocol("WM_DELETE_WINDOW", self.on_closing)

		self.run_popup.wm_title("Converting...")
		self.run_popup.resizable(0, 0)
		self.run_popup.columnconfigure(0,weight=1)

		self.running_description = StringVar(value="Mapping data to fields...")
		self.running_description_label = Label(self.run_popup, textvariable=self.running_description, justify=LEFT)
		self.running_description_label.grid(row=1, column=0, pady=(10,0), padx=5, sticky=W)

		self.progress = ttk.Progressbar(self.run_popup, orient="horizontal",length=250, mode="determinate")
		self.progress_indeterminate = ttk.Progressbar(self.run_popup, orient="horizontal",length=250, mode="indeterminate")
		with open(self.files.csv_file, encoding='utf8', newline='') as csv_file:
			self.num_records = sum(1 for row in csv_file) - 1
		self.progress["maximum"] = self.num_records
		self.progress_indeterminate["maximum"] = 100
		
		self.running_count = StringVar(value="0 of "+str(self.num_records))
		self.running_count_label = Label(self.run_popup, textvariable=self.running_count, justify=LEFT)
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
		self.thread = threading.Thread(target=self.write_out)
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

	def write_out(self):
		with open(self.files.csv_file, encoding='utf8', newline='') as csv_file:
			csv_dict = csv.DictReader(csv_file)
		
			document = MailMergeTracking(self.files.template)
			merge_data = []
			progress = 0
			for row in csv_dict:
				merge_data.append({field:row[self.map[field]] for field in document.get_merge_fields()})
				progress += 1
				self.queue.put((progress, "Mapping data to fields...", "determinate"))
		self.queue.put((self.num_records, "Mapping data to fields...", "determinate"))

		self.queue.put((0, "Merging into template...", "determinate"))
		document.merge_templates(merge_data, separator="page_break", queue=self.queue)
		self.queue.put((self.num_records, "Merging into template...", "determinate"))

		docx_filename = str(self.files.filename)+".docx"
		pdf_filename = str(self.files.filename)+".pdf"

		self.queue.put((None, "Saving...", "indeterminate"))
		if not isdir(self.files.folder):
			mkdir(self.files.folder)

		docx_filepath = normpath(abspath(join(self.files.folder, docx_filename)))
		pdf_filepath = normpath(abspath(join(self.files.folder, pdf_filename)))

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
	
	def on_closing(self):
		if messagebox.askyesno("Cancel", "Are you sure you want to cancel?"):
			self.run_popup.destroy()

if __name__ == '__main__':
	base = Tk()
	app = App(base)
	base.mainloop()
