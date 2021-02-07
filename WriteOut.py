import subprocess, os, platform
import csv
from os import mkdir, remove, unlink
from os.path import isdir, isfile, join, abspath, normcase, normpath
from tempfile import TemporaryFile, NamedTemporaryFile
from time import sleep
from mailmerge import MailMerge
from docx2pdf import convert

def write_out(map, responsesFilePath, template, folder, filename, output_as_word, output_as_pdf):
	with open(responsesFilePath, encoding='utf8', newline='') as auditionsFile:
		auditions = csv.DictReader(auditionsFile)
		next(auditions)
		
		document = MailMerge(template)
		merge_data = []
		for audition in auditions:
			merge_data.append({field:audition[map[field]] for field in document.get_merge_fields()})
		document.merge_templates(merge_data, separator="nextPage_section")

		docx_filename = str(filename)+".docx"
		pdf_filename = str(filename)+".pdf"

		docx_filepath = normpath(abspath(join(folder, docx_filename)))
		pdf_filepath = normpath(abspath(join(folder, pdf_filename)))

		if not output_as_word:
			temp_docx = NamedTemporaryFile(delete=False, suffix=".docx")
			temp_docx.close()
			document.write(temp_docx.name)
			document.close()
			convert(temp_docx.name, pdf_filepath)
			unlink(temp_docx.name)
		if not output_as_pdf:
			document.write(docx_filepath)
			document.close()
		if output_as_word and output_as_pdf:
			document.write(docx_filepath)
			document.close()
			convert(docx_filepath, pdf_filepath)
		
		if platform.system() == 'Darwin':       # macOS
			if output_as_word:
				subprocess.call(('open', docx_filename))
			if output_as_pdf:
				subprocess.call(('open', pdf_filename))
		elif platform.system() == 'Windows':    # Windows
			if output_as_word:
				os.startfile(docx_filename)
			if output_as_pdf:
				os.startfile(pdf_filename)
		else:                                   # linux variants
			if output_as_word:
				subprocess.call(('xdg-open', docx_filename))