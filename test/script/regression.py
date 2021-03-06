#!/usr/bin/python
# -*- coding: utf_8 -*- 
import codecs
import datetime
import logging
import os
import re
import shutil
import socket
import sqlite3
import subprocess
import sys
from sys import platform as _platform
import time
import traceback
import xml
from time import localtime, strftime
from xml.dom.minidom import parse, parseString
import smtplib
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import re
import zipfile
import zlib
import Emailer
import srcupdater

#
# Please read me...
#
# This is the regression testing Python script.
# It uses an ant command to run build.xml for RegressionTest.java
#
# The code is cleanly sectioned and commented.
# Please follow the current formatting.
# It is a long and potentially confusing script.
#
# Variable, function, and class names are written in Python conventions:
# this_is_a_variable	this_is_a_function()	ThisIsAClass
#
# All variables that are needed throughout the script have been initialized
# in a global class.
# - Command line arguments are in Args (named args)
# - Information pertaining to each test is in TestAutopsy (named case)
# - Queried information from the databases is in Database (named database)
# Feel free to add additional global classes or add to the existing ones,
# but do not overwrite any existing variables as they are used frequently.
#

Day = 0

#-------------------------------------------------------------#
# Parses argv and stores booleans to match command line input #
#-------------------------------------------------------------#
class Args:
	def __init__(self):
		self.single = False
		self.single_file = ""
		self.rebuild = False
		self.list = False
		self.config_file = ""
		self.unallocated = False
		self.ignore = False
		self.keep = False
		self.verbose = False
		self.exception = False
		self.exception_string = ""
		self.contin = False
		self.gold_creation = False
		self.daily = False
		self.fr = False
	
	def parse(self):
		global nxtproc 
		nxtproc = []
		nxtproc.append("python3")
		nxtproc.append(sys.argv.pop(0))
		while sys.argv:
			arg = sys.argv.pop(0)
			nxtproc.append(arg)
			if(arg == "-f"):
				try:
					arg = sys.argv.pop(0)
					printout("Running on a single file:")
					printout(path_fix(arg) + "\n")
					self.single = True
					self.single_file = path_fix(arg)
				except:
					printerror("Error: No single file given.\n")
					return False
			elif(arg == "-r" or arg == "--rebuild"):
				printout("Running in rebuild mode.\n")
				self.rebuild = True
			elif(arg == "-l" or arg == "--list"):
				try:
					arg = sys.argv.pop(0)
					nxtproc.append(arg)
					printout("Running from configuration file:")
					printout(arg + "\n")
					self.list = True
					self.config_file = arg
				except:
					printerror("Error: No configuration file given.\n")
					return False
			elif(arg == "-u" or arg == "--unallocated"):
			   printout("Ignoring unallocated space.\n")
			   self.unallocated = True
			elif(arg == "-i" or arg == "--ignore"):
				printout("Ignoring the ../input directory.\n")
				self.ignore = True
			elif(arg == "-k" or arg == "--keep"):
				printout("Keeping the Solr index.\n")
				self.keep = True
			elif(arg == "-v" or arg == "--verbose"):
				printout("Running in verbose mode:")
				printout("Printing all thrown exceptions.\n")
				self.verbose = True
			elif(arg == "-e" or arg == "--exception"):
				try:
					arg = sys.argv.pop(0)
					nxtproc.append(arg)
					printout("Running in exception mode: ")
					printout("Printing all exceptions with the string '" + arg + "'\n")
					self.exception = True
					self.exception_string = arg
				except:
					printerror("Error: No exception string given.")
			elif arg == "-h" or arg == "--help":
				printout(usage())
				return False
			elif arg == "-c" or arg == "--continuous":
				printout("Running until interrupted")
				self.contin = True
			elif arg == "-g" or arg == "--gold":
				printout("Creating gold standards")
				self.gold_creation = True
			elif arg == "-d" or arg == "--daily":
				printout("Running daily")
				self.daily = True
			elif arg == "-fr" or arg == "--forcerun":
				printout("Not downloading new images")
				self.fr = True
			else:
				printout(usage())
				return False
		# Return the args were sucessfully parsed
		return True



#-----------------------------------------------------#
# Holds all global variables for each individual test #
#-----------------------------------------------------#
class TestAutopsy:
	def __init__(self):
		# Paths:
		self.input_dir = Emailer.make_local_path("..","input")
		self.output_dir = ""
		self.gold = Emailer.make_path("..", "output", "gold")
		# Logs:
		self.antlog_dir = ""
		self.common_log = ""
		self.sorted_log = ""
		self.common_log_path = ""
		self.warning_log = ""
		self.csv = ""
		self.global_csv = ""
		self.html_log = ""
		# Error tracking
		self.printerror = []
		self.printout = []
		self.report_passed = False
		# Image info:
		self.image_file = ""
		self.image_name = ""
		# Ant info:
		self.known_bad_path = ""
		self.keyword_path = ""
		self.nsrl_path = ""
		self.build_path = ""
		# Case info
		self.start_date = ""
		self.end_date = ""
		self.total_test_time = ""
		self.total_ingest_time = ""
		self.autopsy_version = ""
		self.heap_space = ""
		self.service_times = ""
		self.ingest_messages = 0
		self.indexed_files = 0
		self.indexed_chunks = 0
		self.autopsy_data_file = ""
		self.sorted_data_file = ""
		self.gold_dbdump = ""
		self.autopsy_dbdump = ""
		self.artifact_count = 0
		self.artifact_fail = 0
		# Infinite Testing info
		timer = 0
		
		# Set the timeout to something huge
		# The entire tester should not timeout before this number in ms
		# However it only seems to take about half this time
		# And it's very buggy, so we're being careful
		self.timeout = 24 * 60 * 60 * 1000 * 1000
		self.ant = []
	  
	def get_image_name(self, image_file):
		path_end = image_file.rfind("/")
		path_end2 = image_file.rfind("\\")
		ext_start = image_file.rfind(".")
		if(ext_start == -1):
			name = image_file
		if(path_end2 != -1):
			name = image_file[path_end2+1:ext_start]
		elif(ext_start == -1):
			name = image_file[path_end+1:]
		elif(path_end == -1):
			name = image_file[:ext_start]
		elif(path_end!=-1 and ext_start!=-1):
			name = image_file[path_end+1:ext_start]
		else:
			name = image_file[path_end2+1:ext_start]
		return name
		
	def ant_to_string(self):
		string = ""
		for arg in self.ant:
			string += (arg + " ")
		return string	

	 
		
	def reset(self):
		# Logs:
		self.antlog_dir = ""
		# Error tracking
		self.printerror = []
		self.printout = []
		self.report_passed = False
		# Image info:
		self.image_file = ""
		self.image_name = ""
		# Ant info:
		self.known_bad_path = ""
		self.keyword_path = ""
		self.nsrl_path = ""
		# Case info
		self.start_date = ""
		self.end_date = ""
		self.total_test_time = ""
		self.total_ingest_time = ""
		self.heap_space = ""
		self.service_times = ""
		
		# Set the timeout to something huge
		# The entire tester should not timeout before this number in ms
		# However it only seems to take about half this time
		# And it's very buggy, so we're being careful
		self.timeout = 24 * 60 * 60 * 1000 * 1000
		self.ant = []
	   



#---------------------------------------------------------#
# Holds all database information from querying autopsy.db #
#  and standard.db. Initialized when the autopsy.db file  #
#		  is compared to the gold standard.			  #
#---------------------------------------------------------#
class Database:
	def __init__(self):
		self.gold_artifacts = []
		self.autopsy_artifacts = []
		self.gold_attributes = 0
		self.autopsy_attributes = 0
		self.gold_objects = 0
		self.autopsy_objects = 0
		self.artifact_comparison = []
		self.attribute_comparison = []
		
	def clear(self):
		self.gold_artifacts = []
		self.autopsy_artifacts = []
		self.gold_attributes = 0
		self.autopsy_attributes = 0
		self.gold_objects = 0
		self.autopsy_objects = 0
		self.artifact_comparison = []
		self.attribute_comparison = []
		
	def get_artifacts_count(self):
		total = 0
		for nums in self.autopsy_artifacts:
			total += nums
		return total
		
	def get_artifact_comparison(self):
		if not self.artifact_comparison:
			return "All counts matched"
		else:
			global failedbool
			global errorem
			failedbool = True
			global imgfail
			imgfail = True
			return "; ".join(self.artifact_comparison)
		
	def get_attribute_comparison(self):
		if not self.attribute_comparison:
			return "All counts matched"
		global failedbool
		global errorem
		failedbool = True
		global imgfail
		imgfail = True
		list = []
		for error in self.attribute_comparison:
			list.append(error)
		return ";".join(list)
		
	def generate_autopsy_artifacts(self):
		if not self.autopsy_artifacts:
			autopsy_db_file = Emailer.make_path(case.output_dir, case.image_name,
										  "AutopsyTestCase", "autopsy.db")
			autopsy_con = sqlite3.connect(autopsy_db_file)
			autopsy_cur = autopsy_con.cursor()
			autopsy_cur.execute("SELECT COUNT(*) FROM blackboard_artifact_types")
			length = autopsy_cur.fetchone()[0] + 1
			for type_id in range(1, length):
				autopsy_cur.execute("SELECT COUNT(*) FROM blackboard_artifacts WHERE artifact_type_id=%d" % type_id)
				self.autopsy_artifacts.append(autopsy_cur.fetchone()[0])		
	
	def generate_autopsy_attributes(self):
		if self.autopsy_attributes == 0:
			autopsy_db_file = Emailer.make_path(case.output_dir, case.image_name,
										  "AutopsyTestCase", "autopsy.db")
			autopsy_con = sqlite3.connect(autopsy_db_file)
			autopsy_cur = autopsy_con.cursor()
			autopsy_cur.execute("SELECT COUNT(*) FROM blackboard_attributes")
			autopsy_attributes = autopsy_cur.fetchone()[0]
			self.autopsy_attributes = autopsy_attributes

	def generate_autopsy_objects(self):
		if self.autopsy_objects == 0:
			autopsy_db_file = Emailer.make_path(case.output_dir, case.image_name,
										  "AutopsyTestCase", "autopsy.db")
			autopsy_con = sqlite3.connect(autopsy_db_file)
			autopsy_cur = autopsy_con.cursor()
			autopsy_cur.execute("SELECT COUNT(*) FROM tsk_objects")
			autopsy_objects = autopsy_cur.fetchone()[0]
			self.autopsy_objects = autopsy_objects
		
	def generate_gold_artifacts(self):
		if not self.gold_artifacts:
			gold_db_file = Emailer.make_path(case.gold, 'tmp', case.image_name, "autopsy.db")
			if(not file_exists(gold_db_file)):
				gold_db_file = Emailer.make_path(case.gold_parse, 'tmp', case.image_name, "autopsy.db")
			gold_con = sqlite3.connect(gold_db_file)
			gold_cur = gold_con.cursor()
			gold_cur.execute("SELECT COUNT(*) FROM blackboard_artifact_types")
			length = gold_cur.fetchone()[0] + 1
			for type_id in range(1, length):
				gold_cur.execute("SELECT COUNT(*) FROM blackboard_artifacts WHERE artifact_type_id=%d" % type_id)
				self.gold_artifacts.append(gold_cur.fetchone()[0])
			gold_cur.execute("SELECT * FROM blackboard_artifacts")
			self.gold_artifacts_list = []
			for row in gold_cur.fetchall():
				for item in row:
					self.gold_artifacts_list.append(item)
				
	def generate_gold_attributes(self):
		if self.gold_attributes == 0:
			gold_db_file = Emailer.make_path(case.gold, 'tmp', case.image_name, "autopsy.db")
			if(not file_exists(gold_db_file)):
				gold_db_file = Emailer.make_path(case.gold_parse, 'tmp', case.image_name, "autopsy.db")
			gold_con = sqlite3.connect(gold_db_file)
			gold_cur = gold_con.cursor()
			gold_cur.execute("SELECT COUNT(*) FROM blackboard_attributes")
			self.gold_attributes = gold_cur.fetchone()[0]

	def generate_gold_objects(self):
		if self.gold_objects == 0:
			gold_db_file = Emailer.make_path(case.gold, 'tmp', case.image_name, "autopsy.db")
			if(not file_exists(gold_db_file)):
				gold_db_file = Emailer.make_path(case.gold_parse, 'tmp', case.image_name, "autopsy.db")
			gold_con = sqlite3.connect(gold_db_file)
			gold_cur = gold_con.cursor()
			gold_cur.execute("SELECT COUNT(*) FROM tsk_objects")
			self.gold_objects = gold_cur.fetchone()[0]



#----------------------------------#
#	  Main testing functions	  #
#----------------------------------#

def retrieve_data(data_file, autopsy_con,autopsy_db_file):
	autopsy_cur2 = autopsy_con.cursor()
	global errorem
	global attachl
	autopsy_cur2.execute("SELECT tsk_files.parent_path, tsk_files.name, blackboard_artifact_types.display_name, blackboard_artifacts.artifact_id FROM blackboard_artifact_types INNER JOIN blackboard_artifacts ON blackboard_artifact_types.artifact_type_id = blackboard_artifacts.artifact_type_id INNER JOIN tsk_files ON tsk_files.obj_id = blackboard_artifacts.obj_id")
	database_log = codecs.open(data_file, "wb", "utf_8")
	rw = autopsy_cur2.fetchone()
	case.artifact_count = 0
	case.artifact_fail = 0
	appnd = False
	counter = 0
	try:
		while (rw != None):
			if(rw[0] != None):
				database_log.write(rw[0] + rw[1] + ' <artifact type = "' + rw[2] + '" > ')
			else:
				database_log.write(rw[1] + ' <artifact type = "' + rw[2] + '" > ')
			autopsy_cur1 = autopsy_con.cursor()
			looptry = True
			case.artifact_count += 1
			try:
				key = ""
				key = str(rw[3])
				key = key,
				autopsy_cur1.execute("SELECT blackboard_attributes.source, blackboard_attribute_types.display_name, blackboard_attributes.value_type, blackboard_attributes.value_text, blackboard_attributes.value_int32, blackboard_attributes.value_int64, blackboard_attributes.value_double FROM blackboard_attributes INNER JOIN blackboard_attribute_types ON blackboard_attributes.attribute_type_id = blackboard_attribute_types.attribute_type_id WHERE artifact_id =? ORDER BY blackboard_attributes.source, blackboard_attribute_types.display_name, blackboard_attributes.value_type, blackboard_attributes.value_text, blackboard_attributes.value_int32, blackboard_attributes.value_int64, blackboard_attributes.value_double", key)
				attributes = autopsy_cur1.fetchall()
			except Exception as e:
				print(str(e))
				print(str(rw[3]))
				errorem += "Artifact with id#" + str(rw[3]) + " encountered an error.\n"
				looptry = False
				case.artifact_fail += 1
				pass
			if(looptry == True):
				src = attributes[0][0]
				for attr in attributes:
					val = 3 + attr[2]
					numvals = 0
					for x in range(3, 6):
						if(attr[x] != None):
							numvals += 1
					if(numvals > 1):
						global failedbool
						global errorem
						global attachl
						errorem += case.image_name + ":There were too many values for attribute type: " + attr[1] + " for artifact with id #" + str(rw[3]) + ".\n"
						printerror("There were too many values for attribute type: " + attr[1] + " for artifact with id #" + str(rw[3]) + " for image " + case.image_name + ".")
						failedbool = True
						if(not appnd):
							attachl.append(autopsy_db_file)
							appnd = True
					if(not attr[0] == src):
						global failedbool
						global errorem
						global attachl
						errorem += case.image_name + ":There were inconsistents sources for artifact with id #" + str(rw[3]) + ".\n"
						printerror("There were inconsistents sources for artifact with id #" + str(rw[3]) + " for image " + case.image_name + ".")
						failedbool = True
						if(not appnd):
							attachl.append(autopsy_db_file)
							appnd = True
					try:
						database_log.write('<attribute source = "' + attr[0] + '" type = "' + attr[1] + '" value = "')
						inpval = attr[val]
						if((type(inpval) != 'unicode') or (type(inpval) != 'str')):
							inpval = str(inpval)
						try:
							database_log.write(inpval)
						except Exception as e:
							print("Inner exception" + outp)
					except Exception as e:
							print(str(e))
					database_log.write('" />')
			database_log.write(' <artifact/>\n')
			rw = autopsy_cur2.fetchone()
	except Exception as e:
		print('outer exception: ' + str(e))
	errorem += case.image_name + ":There were " + str(case.artifact_count) + " artifacts and " + str(case.artifact_fail) + " of them were unusable.\n"
		
def dbDump():
	autopsy_db_file = Emailer.make_path(case.output_dir, case.image_name,
									  "AutopsyTestCase", "autopsy.db")
	backup_db_file = Emailer.make_path(case.output_dir, case.image_name,
									  "AutopsyTestCase", "autopsy_backup.db")
	copy_file(autopsy_db_file,backup_db_file)
	autopsy_con = sqlite3.connect(backup_db_file)
	autopsy_con.execute("DROP TABLE blackboard_artifacts")
	autopsy_con.execute("DROP TABLE blackboard_attributes")
	dump_file = Emailer.make_path(case.output_dir, case.image_name, case.image_name + "Dump.txt")
	database_log = codecs.open(dump_file, "wb", "utf_8")
	dump_list = autopsy_con.iterdump()
	try:
		for line in dump_list:
			try:
				database_log.write(line + "\n")
			except:
				print("Inner dump Exception:" + str(e))
	except Exception as e:
		print("Outer dump Exception:" + str(e))


# Iterates through an XML configuration file to find all given elements		
def run_config_test(config_file):
	try:
		global parsed
		global errorem
		global attachl
		count = 0
		parsed = parse(config_file)
		case
		counts = {}
		if parsed.getElementsByTagName("indir"):
			case.input_dir = parsed.getElementsByTagName("indir")[0].getAttribute("value").encode().decode("utf_8")
		if parsed.getElementsByTagName("global_csv"):
			case.global_csv = parsed.getElementsByTagName("global_csv")[0].getAttribute("value").encode().decode("utf_8")
			case.global_csv = Emailer.make_local_path(case.global_csv)
		if parsed.getElementsByTagName("golddir"):
			case.gold_parse = parsed.getElementsByTagName("golddir")[0].getAttribute("value").encode().decode("utf_8")
		else:
			case.gold_parse = case.gold
		# Generate the top navbar of the HTML for easy access to all images
		values = []
		for element in parsed.getElementsByTagName("image"):
			value = element.getAttribute("value").encode().decode("utf_8")
			if file_exists(value):
				values.append(value)
			else:
				print("File: ", value, " doesn't exist")
		count = len(values)
		archives = Emailer.make_path(case.gold, "..")
		arcount = 0
		for file in os.listdir(archives):
			if not(file == 'tmp'):
				arcount+=1
		if (count > arcount):
			print("******Alert: There are more input images than gold standards, some images will not be properly tested.\n")
		elif not (arcount == count):
			print("******Alert: There are more gold standards than input images, this will not check all gold Standards.\n")
		html_add_images(values)
		images = []
		# Run the test for each file in the configuration
		global args
		
		if(args.contin):
			#set all times an image has been processed to 0
			for element in parsed.getElementsByTagName("image"):
				value = element.getAttribute("value").encode().decode("utf_8")
				images.append(str(value))
			#Begin infiniloop
			if(newDay()):
				global daycount
				setDay()
				srcupdater.compile(errorem, attachl, parsed)
				if(daycount > 0):
					print("starting process")
					outputer = open("ScriptLog.txt", "a")
					pid = subprocess.Popen(nxtproc,
					stdout = outputer,
					stderr = outputer)
					sys.exit()
				daycount += 1
			for img in images:
				run_test(img, 0 )
		else:
			for img in values:  
				if file_exists(img):
					run_test(str(img), 0)
				else:
					printerror("Warning: Image file listed in configuration does not exist:")
					printrttot(value + "\n")
		   
	except Exception as e:
		printerror("Error: There was an error running with the configuration file.")
		printerror(str(e) + "\n")
		logging.critical(traceback.format_exc())

# Runs the test on the single given file.
# The path must be guarenteed to be a correct path.
def run_test(image_file, count):
	global parsed
	global imgfail
	imgfail = False
	if image_type(image_file) == IMGTYPE.UNKNOWN:
		printerror("Error: Image type is unrecognized:")
		printerror(image_file + "\n")
		return
		
	# Set the case to work for this test
	case.image_file = image_file
	case.image_name = case.get_image_name(image_file) + "(" + str(count) + ")"
	case.autopsy_data_file = Emailer.make_path(case.output_dir, case.image_name, case.image_name + "Autopsy_data.txt")
	case.sorted_data_file = Emailer.make_path(case.output_dir, case.image_name, "Sorted_Autopsy_data.txt")
	case.image = case.get_image_name(image_file)
	case.common_log_path = Emailer.make_local_path(case.output_dir, case.image_name, case.image_name+case.common_log)
	case.warning_log = Emailer.make_local_path(case.output_dir, case.image_name, "AutopsyLogs.txt")
	case.antlog_dir = Emailer.make_local_path(case.output_dir, case.image_name, "antlog.txt")
	if(args.list):
		element = parsed.getElementsByTagName("build")
		if(len(element)<=0):
			toval = Emailer.make_path("..", "build.xml")
		else:
			element = element[0]
			toval = element.getAttribute("value").encode().decode("utf_8")
			if(toval==None):
				toval = Emailer.make_path("..", "build.xml")
	else:
		toval = Emailer.make_path("..", "build.xml")
	case.build_path = toval	
	case.known_bad_path = Emailer.make_path(case.input_dir, "notablehashes.txt-md5.idx")
	case.keyword_path = Emailer.make_path(case.input_dir, "notablekeywords.xml")
	case.nsrl_path = Emailer.make_path(case.input_dir, "nsrl.txt-md5.idx")
	
	logging.debug("--------------------")
	logging.debug(case.image_name)
	logging.debug("--------------------")
	run_ant()
	time.sleep(2) # Give everything a second to process
	
	# After the java has ran:
	copy_logs()
	generate_common_log()
	try:
		fill_case_data()
	except Exception as e:
		printerror("Error: Unknown fatal error when filling case data.")
		printerror(str(e) + "\n")
		logging.critical(traceback.format_exc())
	# If NOT keeping Solr index (-k)
	if not args.keep:
		solr_index = Emailer.make_local_path(case.output_dir, case.image_name, "AutopsyTestCase", "KeywordSearch")
		if clear_dir(solr_index):
			print_report([], "DELETE SOLR INDEX", "Solr index deleted.")
	elif args.keep:
		print_report([], "KEEP SOLR INDEX", "Solr index has been kept.")
	# If running in verbose mode (-v)
	if args.verbose:
		errors = report_all_errors()
		okay = "No warnings or errors in any log files."
		print_report(errors, "VERBOSE", okay)
	# If running in exception mode (-e)
	if args.exception:
		exceptions = search_logs(args.exception_string)
		okay = "No warnings or exceptions found containing text '" + args.exception_string + "'."
		print_report(exceptions, "EXCEPTION", okay)
	case.autopsy_dbdump = Emailer.make_path(case.output_dir, case.image_name,
										  case.image_name + "Dump.txt")
	autopsy_db_file = Emailer.make_path(case.output_dir, case.image_name,
										  "AutopsyTestCase", "autopsy.db")
	autopsy_con = sqlite3.connect(autopsy_db_file)
	retrieve_data(case.autopsy_data_file, autopsy_con,autopsy_db_file)
	srtcmdlst = ["sort", case.autopsy_data_file, "-o", case.sorted_data_file]
	subprocess.call(srtcmdlst)
	dbDump()
	# Now test in comparison to the gold standards
	if not args.gold_creation:
		try:
			gold_path = case.gold
			img_gold = Emailer.make_path(case.gold, "tmp", case.image_name)
			img_archive = Emailer.make_path("..", "output", "gold", case.image_name+"-archive.zip")
			if(not file_exists(img_archive)):
				img_archive = Emailer.make_path(case.gold_parse, case.image_name+"-archive.zip")
				gold_path = case.gold_parse
				img_gold = Emailer.make_path(gold_path, "tmp", case.image_name)
			extrctr = zipfile.ZipFile(img_archive, 'r', compression=zipfile.ZIP_DEFLATED)
			extrctr.extractall(gold_path)
			extrctr.close
			time.sleep(2)
			compare_to_gold_db()
			compare_to_gold_html()
			compare_errors()
			gold_nm = "SortedData"
			compare_data(case.sorted_data_file, gold_nm)
			gold_nm = "DBDump"
			compare_data(case.autopsy_dbdump, gold_nm)
			del_dir(img_gold)
		except Exception as e:
			print("Tests failed due to an error, try rebuilding or creating gold standards.\n")
			print(str(e) + "\n")
	# Make the CSV log and the html log viewer
	generate_csv(case.csv)
	if case.global_csv:
		generate_csv(case.global_csv)
	generate_html()
	# If running in rebuild mode (-r)
	if args.rebuild or args.gold_creation:
		rebuild()
	# Reset the case and return the tests sucessfully finished
	clear_dir(Emailer.make_path(case.output_dir, case.image_name, "AutopsyTestCase", "ModuleOutput", "keywordsearch"))
	case.reset()
	return True

# Tests Autopsy with RegressionTest.java by by running
# the build.xml file through ant
def run_ant():
	# Set up the directories
	test_case_path = os.path.join(case.output_dir, case.image_name)
	if dir_exists(test_case_path):
		shutil.rmtree(test_case_path)
	os.makedirs(test_case_path)
	case.ant = ["ant"]
	case.ant.append("-v")
	case.ant.append("-f")
#	case.ant.append(case.build_path)
	case.ant.append(os.path.join("..","..","Testing","build.xml"))
	case.ant.append("regression-test")
	case.ant.append("-l")
	case.ant.append(case.antlog_dir)
	case.ant.append("-Dimg_path=" + case.image_file)
	case.ant.append("-Dknown_bad_path=" + case.known_bad_path)
	case.ant.append("-Dkeyword_path=" + case.keyword_path)
	case.ant.append("-Dnsrl_path=" + case.nsrl_path)
	case.ant.append("-Dgold_path=" + Emailer.make_path(case.gold))
	case.ant.append("-Dout_path=" + Emailer.make_local_path(case.output_dir, case.image_name))
	case.ant.append("-Dignore_unalloc=" + "%s" % args.unallocated)
	case.ant.append("-Dcontin_mode=" + str(args.contin))
	case.ant.append("-Dtest.timeout=" + str(case.timeout))
	
	printout("Ingesting Image:\n" + case.image_file + "\n")
	printout("CMD: " + " ".join(case.ant))
	printout("Starting test...\n")
	antoutpth = Emailer.make_local_path(case.output_dir, "antRunOutput.txt")
	antout = open(antoutpth, "a")
	if SYS is OS.CYGWIN:
		subprocess.call(case.ant, stdout=antout)
	elif SYS is OS.WIN:
		theproc = subprocess.Popen(case.ant, shell = True, stdout=subprocess.PIPE)
		theproc.communicate()
	antout.close()
	
# Returns the type of image file, based off extension
class IMGTYPE:
	RAW, ENCASE, SPLIT, UNKNOWN = range(4)
def image_type(image_file):
	ext_start = image_file.rfind(".")
	if (ext_start == -1):
		return IMGTYPE.UNKNOWN
	ext = image_file[ext_start:].lower()
	if (ext == ".img" or ext == ".dd"):
		return IMGTYPE.RAW
	elif (ext == ".e01"):
		return IMGTYPE.ENCASE
	elif (ext == ".aa" or ext == ".001"):
		return IMGTYPE.SPLIT
	else:
		return IMGTYPE.UNKNOWN



#-----------------------------------------------------------#
#	  Functions relating to rebuilding and comparison	  #
#				   of gold standards					   #
#-----------------------------------------------------------#

# Rebuilds the gold standards by copying the test-generated database
# and html report files into the gold directory
def rebuild():
	# Errors to print
	errors = []
	if(case.gold_parse == None):
		case.gold_parse = case.gold
	# Delete the current gold standards
	gold_dir = Emailer.make_path(case.gold_parse,'tmp')
	clear_dir(gold_dir)
	tmpdir = Emailer.make_path(gold_dir, case.image_name)
	dbinpth = Emailer.make_path(case.output_dir, case.image_name, "AutopsyTestCase", "autopsy.db")
	dboutpth = Emailer.make_path(tmpdir, "autopsy.db")
	dataoutpth = Emailer.make_path(tmpdir, case.image_name + "SortedData.txt")
	dbdumpinpth = case.autopsy_dbdump
	dbdumpoutpth = Emailer.make_path(tmpdir, case.image_name + "DBDump.txt")
	if not os.path.exists(case.gold_parse):
		os.makedirs(case.gold_parse)
	if not os.path.exists(gold_dir):
		os.makedirs(gold_dir)
	if not os.path.exists(tmpdir):
		os.makedirs(tmpdir)
	try:
		copy_file(dbinpth, dboutpth)
		copy_file(case.sorted_data_file, dataoutpth)
		copy_file(dbdumpinpth, dbdumpoutpth)
		error_pth = Emailer.make_path(tmpdir, case.image_name+"SortedErrors.txt")
	except Exception as e:
		print(str(e))
	copy_file(case.sorted_log, error_pth)
	# Rebuild the HTML report
	htmlfolder = ""
	for fs in os.listdir(os.path.join(os.getcwd(),case.output_dir, case.image_name, "AutopsyTestCase", "Reports")):
		if os.path.isdir(os.path.join(os.getcwd(), case.output_dir, case.image_name, "AutopsyTestCase", "Reports", fs)):
			htmlfolder = fs
	autopsy_html_path = Emailer.make_local_path(case.output_dir, case.image_name, "AutopsyTestCase", "Reports", htmlfolder)
	
	html_path = Emailer.make_path(case.output_dir, case.image_name,
								 "AutopsyTestCase", "Reports")
	try:
		if not os.path.exists(Emailer.make_path(tmpdir, htmlfolder)):
			os.makedirs(Emailer.make_path(tmpdir, htmlfolder))
		for file in os.listdir(autopsy_html_path):
			html_to = Emailer.make_path(tmpdir, file.replace("HTML Report", "Report"))
			copy_dir(get_file_in_dir(autopsy_html_path, file), html_to)
	except FileNotFoundException as e:
		errors.append(e.error)
	except Exception as e:
		errors.append("Error: Unknown fatal error when rebuilding the gold html report.")
		errors.append(str(e) + "\n")
		traceback.print_exc
	oldcwd = os.getcwd()
	zpdir = gold_dir
	os.chdir(zpdir)
	os.chdir("..")
	img_gold = "tmp"
	img_archive = Emailer.make_path(case.image_name+"-archive.zip")
	comprssr = zipfile.ZipFile(img_archive, 'w',compression=zipfile.ZIP_DEFLATED)
	zipdir(img_gold, comprssr)
	comprssr.close()
	os.chdir(oldcwd)
	del_dir(gold_dir)
	okay = "Sucessfully rebuilt all gold standards."
	print_report(errors, "REBUILDING", okay)

def zipdir(path, zip):
    for root, dirs, files in os.walk(path):
        for file in files:
            zip.write(os.path.join(root, file))

# Using the global case's variables, compare the database file made by the
# regression test to the gold standard database file
# Initializes the global database, which stores the information retrieved
# from queries while comparing
def compare_to_gold_db():
	# SQLITE needs unix style pathing
	gold_db_file = Emailer.make_path(case.gold, 'tmp', case.image_name, "autopsy.db")
	if(not file_exists(gold_db_file)):
		gold_db_file = Emailer.make_path(case.gold_parse, 'tmp', case.image_name, "autopsy.db")
	autopsy_db_file = Emailer.make_path(case.output_dir, case.image_name,
									  "AutopsyTestCase", "autopsy.db")
	# Try to query the databases. Ignore any exceptions, the function will
	# return an error later on if these do fail
	database.clear()
	try:
		database.generate_gold_objects()
		database.generate_gold_artifacts()
		database.generate_gold_attributes()
	except Exception as e:
		print("Way out:" + str(e))
	try:
		database.generate_autopsy_objects()
		database.generate_autopsy_artifacts()
		database.generate_autopsy_attributes()
	except Exception as e:
		print("Way outA:" + str(e))
	# This is where we return if a file doesn't exist, because we don't want to
	# compare faulty databases, but we do however want to try to run all queries
	# regardless of the other database
	if not file_exists(autopsy_db_file):
		printerror("Error: Database file does not exist at:")
		printerror(autopsy_db_file + "\n")
		return
	if not file_exists(gold_db_file):
		printerror("Error: Gold database file does not exist at:")
		printerror(gold_db_file + "\n")
		return
		
	# compare size of bb artifacts, attributes, and tsk objects
	gold_con = sqlite3.connect(gold_db_file)
	gold_cur = gold_con.cursor()
	autopsy_con = sqlite3.connect(autopsy_db_file)
	autopsy_cur = autopsy_con.cursor()
	
	exceptions = []
	# Testing tsk_objects
	exceptions.append(compare_tsk_objects())
	# Testing blackboard_artifacts
	exceptions.append(count_bb_artifacts())
	# Testing blackboard_attributes
	exceptions.append(compare_bb_attributes())
	
	database.artifact_comparison = exceptions[1]
	database.attribute_comparison = exceptions[2]
	
	okay = "All counts match."
	print_report(exceptions[0], "COMPARE TSK OBJECTS", okay)
	print_report(exceptions[1], "COMPARE ARTIFACTS", okay)
	print_report(exceptions[2], "COMPARE ATTRIBUTES", okay)
	
# Using the global case's variables, compare the html report file made by
# the regression test against the gold standard html report
def compare_to_gold_html():
	gold_html_file = Emailer.make_path(case.gold, 'tmp', case.image_name, "Report", "index.html")
	if(not file_exists(gold_html_file)):
		gold_html_file = Emailer.make_path(case.gold_parse, 'tmp', case.image_name, "Report", "index.html")
	htmlfolder = ""
	for fs in os.listdir(Emailer.make_path(case.output_dir, case.image_name, "AutopsyTestCase", "Reports")):
		if os.path.isdir(Emailer.make_path(case.output_dir, case.image_name, "AutopsyTestCase", "Reports", fs)):
			htmlfolder = fs
	autopsy_html_path = Emailer.make_path(case.output_dir, case.image_name, "AutopsyTestCase", "Reports", htmlfolder, "HTML Report") #, "AutopsyTestCase", "Reports", htmlfolder)
	
	
	try:
		autopsy_html_file = get_file_in_dir(autopsy_html_path, "index.html")
		if not file_exists(gold_html_file):
			printerror("Error: No gold html report exists at:")
			printerror(gold_html_file + "\n")
			return
		if not file_exists(autopsy_html_file):
			printerror("Error: No case html report exists at:")
			printerror(autopsy_html_file + "\n")
			return
		#Find all gold .html files belonging to this case
		ListGoldHTML = []
		for fs in os.listdir(Emailer.make_path(case.output_dir, case.image_name, "AutopsyTestCase", "Reports", htmlfolder)):
			if(fs.endswith(".html")):
				ListGoldHTML.append(Emailer.make_path(case.output_dir, case.image_name, "AutopsyTestCase", "Reports", htmlfolder, fs))
		#Find all new .html files belonging to this case
		ListNewHTML = []
		if(os.path.exists(Emailer.make_path(case.gold, 'tmp', case.image_name))):
			for fs in os.listdir(Emailer.make_path(case.gold, 'tmp', case.image_name)):
				if (fs.endswith(".html")):
					ListNewHTML.append(Emailer.make_path(case.gold, 'tmp', case.image_name, fs))
		if(not case.gold_parse == None or case.gold == case.gold_parse):
			if(file_exists(Emailer.make_path(case.gold_parse, 'tmp', case.image_name))):
				for fs in os.listdir(Emailer.make_path(case.gold_parse, 'tmp',case.image_name)):
					if (fs.endswith(".html")):
						ListNewHTML.append(Emailer.make_path(case.gold_parse, 'tmp', case.image_name, fs))
		#ensure both reports have the same number of files and are in the same order
		if(len(ListGoldHTML) != len(ListNewHTML)):
			printerror("The reports did not have the same number of files. One of the reports may have been corrupted")
		else:
			ListGoldHTML.sort()
			ListNewHTML.sort()
		  
		total = {"Gold": 0, "New": 0}
		for x in range(0, len(ListGoldHTML)):
			count = compare_report_files(ListGoldHTML[x], ListNewHTML[x])
			total["Gold"]+=count[0]
			total["New"]+=count[1]
		okay = "The test report matches the gold report."
		errors=["Gold report had " + str(total["Gold"]) +" errors", "New report had " + str(total["New"]) + " errors."]
		print_report(errors, "REPORT COMPARISON", okay)
		if total["Gold"] == total["New"]:
			case.report_passed = True
		else:
			printerror("The reports did not match each other.\n " + errors[0] +" and the " + errors[1])
	except FileNotFoundException as e:
		e.print_error()
	except DirNotFoundException as e:
		e.print_error()
	except Exception as e:
		printerror("Error: Unknown fatal error comparing reports.")
		printerror(str(e) + "\n")
		logging.critical(traceback.format_exc())

def compare_bb_artifacts():
	count_bb_artifacts()
	
# Compares the blackboard artifact counts of two databases
# given the two database cursors
def count_bb_artifacts():
	exceptions = []
	try:
		global failedbool
		global errorem
		if database.gold_artifacts != database.autopsy_artifacts:
			failedbool = True
			global imgfail
			imgfail = True
			errorem += case.image + ":There was a difference in the number of artifacts.\n"
		rner = len(database.gold_artifacts)
		for type_id in range(1, rner):
			if database.gold_artifacts[type_id] != database.autopsy_artifacts[type_id]:
				error = str("Artifact counts do not match for type id %d. " % type_id)
				error += str("Gold: %d, Test: %d" %
							(database.gold_artifacts[type_id],
							 database.autopsy_artifacts[type_id]))
				exceptions.append(error)
		return exceptions
	except Exception as e:
		print(str(e))
		exceptions.append("Error: Unable to compare blackboard_artifacts.\n")
		return exceptions

# Compares the blackboard atribute counts of two databases
# given the two database cursors
def compare_bb_attributes():
	exceptions = []
	try:
		if database.gold_attributes != database.autopsy_attributes:
			error = "Attribute counts do not match. "
			error += str("Gold: %d, Test: %d" % (database.gold_attributes, database.autopsy_attributes))
			exceptions.append(error)
			global failedbool
			global errorem
			failedbool = True
			global imgfail
			imgfail = True
			errorem += case.image + ":There was a difference in the number of attributes.\n"
			return exceptions
	except Exception as e:
		exceptions.append("Error: Unable to compare blackboard_attributes.\n")
		return exceptions

# Compares the tsk object counts of two databases
# given the two database cursors
def compare_tsk_objects():
	exceptions = []
	try:
		if database.gold_objects != database.autopsy_objects:
			error = "TSK Object counts do not match. "
			error += str("Gold: %d, Test: %d" % (database.gold_objects, database.autopsy_objects))
			exceptions.append(error)
			global failedbool
			global errorem
			failedbool = True
			global imgfail
			imgfail = True
			errorem += case.image + ":There was a difference between the tsk object counts.\n"
			return exceptions
	except Exception as e:
		exceptions.append("Error: Unable to compare tsk_objects.\n")
		return exceptions



#-------------------------------------------------#
#	  Functions relating to error reporting	  #
#-------------------------------------------------#	  

# Generate the "common log": a log of all exceptions and warnings
# from each log file generated by Autopsy
def generate_common_log():
	try:
		logs_path = Emailer.make_local_path(case.output_dir, case.image_name, "logs")
		common_log = codecs.open(case.common_log_path, "w", "utf_8")
		warning_log = codecs.open(case.warning_log, "w", "utf_8")
		common_log.write("--------------------------------------------------\n")
		common_log.write(case.image_name + "\n")
		common_log.write("--------------------------------------------------\n")
		rep_path = Emailer.make_local_path(case.output_dir)
		rep_path = rep_path.replace("\\\\", "\\")
		for file in os.listdir(logs_path):
			log = codecs.open(Emailer.make_path(logs_path, file), "r", "utf_8")
			for line in log:
				line = line.replace(rep_path, "CASE")
				if line.startswith("Exception"):
					common_log.write(file +": " +  line)
				elif line.startswith("Error"):
					common_log.write(file +": " +  line)
				elif line.startswith("SEVERE"):
					common_log.write(file +":" +  line)
				else:
					warning_log.write(file +": " +  line)
			log.close()
		common_log.write("\n")
		common_log.close()
		case.sorted_log = Emailer.make_local_path(case.output_dir, case.image_name, case.image_name + "SortedErrors.txt")
		srtcmdlst = ["sort", case.common_log_path, "-o", case.sorted_log]
		subprocess.call(srtcmdlst)
	except Exception as e:
		printerror("Error: Unable to generate the common log.")
		printerror(str(e) + "\n")
		logging.critical(traceback.format_exc())
		
def compare_data(aut, gld):
	gold_dir = Emailer.make_path(case.gold, "tmp", case.image_name, case.image_name + gld + ".txt")
	if(not file_exists(gold_dir)):
			gold_dir = Emailer.make_path(case.gold_parse, "tmp",  case.image_name, case.image_name + gld + ".txt")
	if(not file_exists(aut)):
		return
	srtd_data = codecs.open(aut, "r", "utf_8")
	gold_data = codecs.open(gold_dir, "r", "utf_8")
	gold_dat = gold_data.read()
	srtd_dat = srtd_data.read()
	if (not(gold_dat == srtd_dat)):
		diff_dir = Emailer.make_local_path(case.output_dir, case.image_name, case.image_name+gld+"-Diff.txt")
		diff_file = codecs.open(diff_dir, "wb", "utf_8") 
		dffcmdlst = ["diff", case.sorted_data_file, gold_dir]
		subprocess.call(dffcmdlst, stdout = diff_file)
		global attachl
		global errorem
		global failedbool
		attachl.append(diff_dir)
		errorem += case.image_name + ":There was a difference in the Database data for the file " + gld + ".\n"
		print("There was a difference in the Database data for " + case.image_name + " for the file " + gld + ".\n")
		failedbool = True
		global imgfail
		imgfail = True

def compare_errors():
	gold_dir = Emailer.make_path(case.gold, "tmp",  case.image_name, case.image_name + "SortedErrors.txt")
	if(not file_exists(gold_dir)):
			gold_dir = Emailer.make_path(case.gold_parse, 'tmp', case.image_name, case.image_name + "SortedErrors.txt")
	common_log = codecs.open(case.sorted_log, "r", "utf_8")
	gold_log = codecs.open(gold_dir, "r", "utf_8")
	gold_dat = gold_log.read()
	common_dat = common_log.read()
	patrn = re.compile("\d")
	if (not((re.sub(patrn, 'd', gold_dat)) == (re.sub(patrn, 'd', common_dat)))):
		diff_dir = Emailer.make_local_path(case.output_dir, case.image_name, case.image_name+"AutopsyErrors-Diff.txt")
		diff_file = open(diff_dir, "w") 
		dffcmdlst = ["diff", case.sorted_log, gold_dir]
		subprocess.call(dffcmdlst, stdout = diff_file)
		global attachl
		global errorem
		global failedbool
		attachl.append(case.sorted_log)
		attachl.append(diff_dir)
		errorem += case.image_name + ":There was a difference in the exceptions Log.\n"
		print("Exceptions didn't match.\n")
		failedbool = True
		global imgfail
		imgfail = True

# Fill in the global case's variables that require the log files
def fill_case_data():
	try:
		# Open autopsy.log.0
		log_path = Emailer.make_local_path(case.output_dir, case.image_name, "logs", "autopsy.log.0")
		log = open(log_path)
		
		# Set the case starting time based off the first line of autopsy.log.0
		# *** If logging time format ever changes this will break ***
		case.start_date = log.readline().split(" org.")[0]
	
		# Set the case ending time based off the "create" time (when the file was copied)
		case.end_date = time.ctime(os.path.getmtime(log_path))
	except Exception as e:
		printerror("Error: Unable to open autopsy.log.0.")
		printerror(str(e) + "\n")
		logging.warning(traceback.format_exc())
	# Set the case total test time
	# Start date must look like: "Jul 16, 2012 12:57:53 PM"
	# End date must look like: "Mon Jul 16 13:02:42 2012"
	# *** If logging time format ever changes this will break ***
	start = datetime.datetime.strptime(case.start_date, "%b %d, %Y %I:%M:%S %p")
	end = datetime.datetime.strptime(case.end_date, "%a %b %d %H:%M:%S %Y")
	case.total_test_time = str(end - start)

	try:
		# Set Autopsy version, heap space, ingest time, and service times
		
		version_line = search_logs("INFO: Application name: Autopsy, version:")[0]
		case.autopsy_version = get_word_at(version_line, 5).rstrip(",")
		
		case.heap_space = search_logs("Heap memory usage:")[0].rstrip().split(": ")[1]
		
		ingest_line = search_logs("Ingest (including enqueue)")[0]
		case.total_ingest_time = get_word_at(ingest_line, 6).rstrip()
		
		message_line = search_log_set("autopsy", "Ingest messages count:")[0]
		case.ingest_messages = int(message_line.rstrip().split(": ")[2])
		
		files_line = search_log_set("autopsy", "Indexed files count:")[0]
		case.indexed_files = int(files_line.rstrip().split(": ")[2])
		
		chunks_line = search_log_set("autopsy", "Indexed file chunks count:")[0]
		case.indexed_chunks = int(chunks_line.rstrip().split(": ")[2])
	except Exception as e:
		printerror("Error: Unable to find the required information to fill case data.")
		printerror(str(e) + "\n")
		logging.critical(traceback.format_exc())
	try:
		service_lines = search_log("autopsy.log.0", "to process()")
		service_list = []
		for line in service_lines:
			words = line.split(" ")
			# Kind of forcing our way into getting this data
			# If this format changes, the tester will break
			i = words.index("secs.")
			times = words[i-4] + " "
			times += words[i-3] + " "
			times += words[i-2] + " "
			times += words[i-1] + " "
			times += words[i]
			service_list.append(times)
		case.service_times = "; ".join(service_list)
	except FileNotFoundException as e:
		e.print_error()
	except Exception as e:
		printerror("Error: Unknown fatal error when finding service times.")
		printerror(str(e) + "\n")
		logging.critical(traceback.format_exc())
	
# Generate the CSV log file
def generate_csv(csv_path):
	try:
		# If the CSV file hasn't already been generated, this is the
		# first run, and we need to add the column names
		if not file_exists(csv_path):
			csv_header(csv_path)
			
		# Now add on the fields to a new row
		csv = open(csv_path, "a")
		
		# Variables that need to be written
		vars = []
		vars.append( case.image_file )
		vars.append( case.image_name )
		vars.append( case.output_dir )
		vars.append( socket.gethostname() )
		vars.append( case.autopsy_version )
		vars.append( case.heap_space )
		vars.append( case.start_date )
		vars.append( case.end_date )
		vars.append( case.total_test_time )
		vars.append( case.total_ingest_time )
		vars.append( case.service_times )
		vars.append( str(len(get_exceptions())) )
		vars.append( str(get_num_memory_errors("autopsy")) )
		vars.append( str(get_num_memory_errors("tika")) )
		vars.append( str(get_num_memory_errors("solr")) )
		vars.append( str(len(search_log_set("autopsy", "TskCoreException"))) )
		vars.append( str(len(search_log_set("autopsy", "TskDataException"))) )
		vars.append( str(case.ingest_messages) )
		vars.append( str(case.indexed_files) )
		vars.append( str(case.indexed_chunks) )
		vars.append( str(len(search_log_set("autopsy", "Stopping ingest due to low disk space on disk"))) )
		vars.append( str(database.autopsy_objects) )
		vars.append( str(database.get_artifacts_count()) )
		vars.append( str(database.autopsy_attributes) )
		vars.append( Emailer.make_local_path("gold", case.image_name, "autopsy.db") )
		vars.append( database.get_artifact_comparison() )
		vars.append( database.get_attribute_comparison() )
		vars.append( Emailer.make_local_path("gold", case.image_name, "standard.html") )
		vars.append( str(case.report_passed) )
		vars.append( case.ant_to_string() )
		
		# Join it together with a ", "
		output = "|".join(vars)
		output += "\n"
		# Write to the log!
		csv.write(output)
		csv.close()
	except Exception as e:
		printerror("Error: Unknown fatal error when creating CSV file at:")
		printerror(csv_path)
		printerror(str(e) + "\n")
		logging.critical(traceback.format_exc())

# Generates the CSV header (column names)
def csv_header(csv_path):
	csv = open(csv_path, "w")
	titles = []
	titles.append("Image Path")
	titles.append("Image Name")
	titles.append("Output Case Directory")
	titles.append("Host Name")
	titles.append("Autopsy Version")
	titles.append("Heap Space Setting")
	titles.append("Test Start Date")
	titles.append("Test End Date")
	titles.append("Total Test Time")
	titles.append("Total Ingest Time")
	titles.append("Service Times")
	titles.append("Autopsy Exceptions")
	titles.append("Autopsy OutOfMemoryErrors/Exceptions")
	titles.append("Tika OutOfMemoryErrors/Exceptions")
	titles.append("Solr OutOfMemoryErrors/Exceptions")
	titles.append("TskCoreExceptions")
	titles.append("TskDataExceptions")
	titles.append("Ingest Messages Count")
	titles.append("Indexed Files Count")
	titles.append("Indexed File Chunks Count")
	titles.append("Out Of Disk Space")
	titles.append("Tsk Objects Count")
	titles.append("Artifacts Count")
	titles.append("Attributes Count")
	titles.append("Gold Database Name")
	titles.append("Artifacts Comparison")
	titles.append("Attributes Comparison")
	titles.append("Gold Report Name")
	titles.append("Report Comparison")
	titles.append("Ant Command Line")
	output = "|".join(titles)
	output += "\n"
	csv.write(output)
	csv.close()
		
# Returns a list of all the exceptions listed in all the autopsy logs
def get_exceptions():
	exceptions = []
	logs_path = Emailer.make_local_path(case.output_dir, case.image_name, "logs")
	results = []
	for file in os.listdir(logs_path):
		if "autopsy.log" in file:
			log = codecs.open(Emailer.make_path(logs_path, file), "r", "utf_8")
			ex = re.compile("\SException")
			er = re.compile("\SError")
			for line in log:
				if ex.search(line) or er.search(line):
					exceptions.append(line)
			log.close()
	return exceptions
	
# Returns a list of all the warnings listed in the common log
def get_warnings():
	warnings = []
	common_log = codecs.open(case.warning_log, "r", "utf_8")
	for line in common_log:
		if "warning" in line.lower():
			warnings.append(line)
	common_log.close()
	return warnings

# Returns all the errors found in the common log in a list
def report_all_errors():
	try:
		return get_warnings() + get_exceptions()
	except Exception as e:
		printerror("Error: Unknown fatal error when reporting all errors.")
		printerror(str(e) + "\n")
		logging.warning(traceback.format_exc())

# Searched all the known logs for the given regex
# The function expects regex = re.compile(...)
def regex_search_logs(regex):
	logs_path = Emailer.make_local_path(case.output_dir, case.image_name, "logs")
	results = []
	for file in os.listdir(logs_path):
		log = codecs.open(Emailer.make_path(logs_path, file), "r", "utf_8")
		for line in log:
			if regex.search(line):
				results.append(line)
		log.close()
	if results:
		return results

# Search through all the known log files for a specific string.
# Returns a list of all lines with that string
def search_logs(string):
	logs_path = Emailer.make_local_path(case.output_dir, case.image_name, "logs")
	results = []
	for file in os.listdir(logs_path):
		log = codecs.open(Emailer.make_path(logs_path, file), "r", "utf_8")
		for line in log:
			if string in line:
				results.append(line)
		log.close()
	return results
	
# Searches the common log for any instances of a specific string.
def search_common_log(string):
	results = []
	log = codecs.open(case.common_log_path, "r", "utf_8")
	for line in log:
		if string in line:
			results.append(line)
	log.close()
	return results

# Searches the given log for the given string
# Returns a list of all lines with that string
def search_log(log, string):
	logs_path = Emailer.make_local_path(case.output_dir, case.image_name, "logs", log)
	try:
		results = []
		log = codecs.open(logs_path, "r", "utf_8")
		for line in log:
			if string in line:
				results.append(line)
		log.close()
		if results:
			return results
	except:
		raise FileNotFoundException(logs_path)

# Search through all the the logs of the given type
# Types include autopsy, tika, and solr
def search_log_set(type, string):
	logs_path = Emailer.make_local_path(case.output_dir, case.image_name, "logs")
	results = []
	for file in os.listdir(logs_path):
		if type in file:
			log = codecs.open(Emailer.make_path(logs_path, file), "r", "utf_8")
			for line in log:
				if string in line:
					results.append(line)
			log.close()
	return results
		
# Returns the number of OutOfMemoryErrors and OutOfMemoryExceptions
# for a certain type of log
def get_num_memory_errors(type):
	return (len(search_log_set(type, "OutOfMemoryError")) + 
			len(search_log_set(type, "OutOfMemoryException")))

# Print a report for the given errors with the report name as name
# and if no errors are found, print the okay message
def print_report(errors, name, okay):
	if errors:
		printerror("--------< " + name + " >----------")
		for error in errors:
			printerror(str(error))
		printerror("--------< / " + name + " >--------\n")
	else:
		printout("-----------------------------------------------------------------")
		printout("< " + name + " - " + okay + " />")
		printout("-----------------------------------------------------------------\n")

# Used instead of the print command when printing out an error
def printerror(string):
	print(string)
	case.printerror.append(string)

# Used instead of the print command when printing out anything besides errors
def printout(string):
	print(string)
	case.printout.append(string)

# Generates the HTML log file
def generate_html():
	# If the file doesn't exist yet, this is the first case to run for
	# this test, so we need to make the start of the html log
	global imgfail
	if not file_exists(case.html_log):
		write_html_head()
	try:
		global html
		html = open(case.html_log, "a")
		# The image title
		title = "<h1><a name='" + case.image_name + "'>" + case.image_name + " \
					<span>tested on <strong>" + socket.gethostname() + "</strong></span></a></h1>\
				 <h2 align='center'>\
				 <a href='#" + case.image_name + "-errors'>Errors and Warnings</a> |\
				 <a href='#" + case.image_name + "-info'>Information</a> |\
				 <a href='#" + case.image_name + "-general'>General Output</a> |\
				 <a href='#" + case.image_name + "-logs'>Logs</a>\
				 </h2>"
		# The script errors found
		if imgfail:
			ids = 'errors1'
		else:
			ids = 'errors'
		errors = "<div id='" + ids + "'>\
				  <h2><a name='" + case.image_name + "-errors'>Errors and Warnings</a></h2>\
				  <hr color='#FF0000'>"
		# For each error we have logged in the case
		for error in case.printerror:
			# Replace < and > to avoid any html display errors
			errors += "<p>" + error.replace("<", "&lt").replace(">", "&gt") + "</p>"
			# If there is a \n, we probably want a <br /> in the html
			if "\n" in error:
				errors += "<br />"
		errors += "</div>"
		
		# Links to the logs
		logs = "<div id='logs'>\
				<h2><a name='" + case.image_name + "-logs'>Logs</a></h2>\
				<hr color='#282828'>"
		logs_path = Emailer.make_local_path(case.output_dir, case.image_name, "logs")
		for file in os.listdir(logs_path):
			logs += "<p><a href='file:\\" + Emailer.make_path(logs_path, file) + "' target='_blank'>" + file + "</a></p>"
		logs += "</div>"
		
		# All the testing information
		info = "<div id='info'>\
				<h2><a name='" + case.image_name + "-info'>Information</a></h2>\
				<hr color='#282828'>\
				<table cellspacing='5px'>"
		# The individual elements
		info += "<tr><td>Image Path:</td>"
		info += "<td>" + case.image_file + "</td></tr>"
		info += "<tr><td>Image Name:</td>"
		info += "<td>" + case.image_name + "</td></tr>"
		info += "<tr><td>Case Output Directory:</td>"
		info += "<td>" + case.output_dir + "</td></tr>"
		info += "<tr><td>Autopsy Version:</td>"
		info += "<td>" + case.autopsy_version + "</td></tr>"
		info += "<tr><td>Heap Space:</td>"
		info += "<td>" + case.heap_space + "</td></tr>"
		info += "<tr><td>Test Start Date:</td>"
		info += "<td>" + case.start_date + "</td></tr>"
		info += "<tr><td>Test End Date:</td>"
		info += "<td>" + case.end_date + "</td></tr>"
		info += "<tr><td>Total Test Time:</td>"
		info += "<td>" + case.total_test_time + "</td></tr>"
		info += "<tr><td>Total Ingest Time:</td>"
		info += "<td>" + case.total_ingest_time + "</td></tr>"
		info += "<tr><td>Exceptions Count:</td>"
		info += "<td>" + str(len(get_exceptions())) + "</td></tr>"
		info += "<tr><td>Autopsy OutOfMemoryExceptions:</td>"
		info += "<td>" + str(len(search_logs("OutOfMemoryException"))) + "</td></tr>"
		info += "<tr><td>Autopsy OutOfMemoryErrors:</td>"
		info += "<td>" + str(len(search_logs("OutOfMemoryError"))) + "</td></tr>"
		info += "<tr><td>Tika OutOfMemoryErrors/Exceptions:</td>"
		info += "<td>" + str(get_num_memory_errors("tika")) + "</td></tr>"
		info += "<tr><td>Solr OutOfMemoryErrors/Exceptions:</td>"
		info += "<td>" + str(get_num_memory_errors("solr")) + "</td></tr>"
		info += "<tr><td>TskCoreExceptions:</td>"
		info += "<td>" + str(len(search_log_set("autopsy", "TskCoreException"))) + "</td></tr>"
		info += "<tr><td>TskDataExceptions:</td>"
		info += "<td>" + str(len(search_log_set("autopsy", "TskDataException"))) + "</td></tr>"
		info += "<tr><td>Ingest Messages Count:</td>"
		info += "<td>" + str(case.ingest_messages) + "</td></tr>"
		info += "<tr><td>Indexed Files Count:</td>"
		info += "<td>" + str(case.indexed_files) + "</td></tr>"
		info += "<tr><td>Indexed File Chunks Count:</td>"
		info += "<td>" + str(case.indexed_chunks) + "</td></tr>"
		info += "<tr><td>Out Of Disk Space:\
						 <p style='font-size: 11px;'>(will skew other test results)</p></td>"
		info += "<td>" + str(len(search_log_set("autopsy", "Stopping ingest due to low disk space on disk"))) + "</td></tr>"
		info += "<tr><td>TSK Objects Count:</td>"
		info += "<td>" + str(database.autopsy_objects) + "</td></tr>"
		info += "<tr><td>Artifacts Count:</td>"
		info += "<td>" + str(database.get_artifacts_count()) + "</td></tr>"
		info += "<tr><td>Attributes Count:</td>"
		info += "<td>" + str(database.autopsy_attributes) + "</td></tr>"
		info += "</table>\
				 </div>"
		# For all the general print statements in the case
		output = "<div id='general'>\
				  <h2><a name='" + case.image_name + "-general'>General Output</a></h2>\
				  <hr color='#282828'>"
		# For each printout in the case's list
		for out in case.printout:
			output += "<p>" + out + "</p>"
			# If there was a \n it probably means we want a <br /> in the html
			if "\n" in out:
				output += "<br />"
		output += "</div>"
		
		html.write(title)
		html.write(errors)
		html.write(info)
		html.write(logs)
		html.write(output)
		html.close()
	except Exception as e:
		printerror("Error: Unknown fatal error when creating HTML log at:")
		printerror(case.html_log)
		printerror(str(e) + "\n")
		logging.critical(traceback.format_exc())

# Writed the top of the HTML log file
def write_html_head():
	print(case.html_log)
	html = open(str(case.html_log), "a")
	head = "<html>\
			<head>\
			<title>AutopsyTestCase Output</title>\
			</head>\
			<style type='text/css'>\
			body { font-family: 'Courier New'; font-size: 12px; }\
			h1 { background: #444; margin: 0px auto; padding: 0px; color: #FFF; border: 1px solid #000; font-family: Tahoma; text-align: center; }\
			h1 span { font-size: 12px; font-weight: 100; }\
			h2 { font-family: Tahoma; padding: 0px; margin: 0px; }\
			hr { width: 100%; height: 1px; border: none; margin-top: 10px; margin-bottom: 10px; }\
			#errors { background: #CCCCCC; border: 1px solid #282828; color: #282828; padding: 10px; margin: 20px; }\
			#errors1 { background: #CC0000; border: 1px solid #282828; color: #282828; padding: 10px; margin: 20px; }\
			#info { background: #CCCCCC; border: 1px solid #282828; color: #282828; padding: 10px; margin: 20px; }\
			#general { background: #CCCCCC; border: 1px solid #282828; color: #282828; padding: 10px; margin: 20px; }\
			#logs { background: #CCCCCC; border: 1px solid #282828; color: #282828; padding: 10px; margin: 20px; }\
			#errors p, #info p, #general p, #logs p { pading: 0px; margin: 0px; margin-left: 5px; }\
			#info table td { color: ##282828; font-size: 12px; min-width: 225px; }\
			#logs a { color: ##282828; }\
			</style>\
			<body>"
	html.write(head)
	html.close()

# Writed the bottom of the HTML log file
def write_html_foot():
	html = open(case.html_log, "a")
	head = "</body></html>"
	html.write(head)
	html.close()

# Adds all the image names to the HTML log for easy access
def html_add_images(full_image_names):
	# If the file doesn't exist yet, this is the first case to run for
	# this test, so we need to make the start of the html log
	if not file_exists(case.html_log):
		write_html_head()
	html = open(case.html_log, "a")
	links = []
	for full_name in full_image_names:
		name = case.get_image_name(full_name)
		links.append("<a href='#" + name + "(0)'>" + name + "</a>")
	html.write("<p align='center'>" + (" | ".join(links)) + "</p>")



#----------------------------------#
#		 Helper functions		 #
#----------------------------------#

def setDay():
	global Day
	Day = int(strftime("%d", localtime()))
		
def getLastDay():
	return Day
		
def getDay():
	return int(strftime("%d", localtime()))
		
def newDay():
	return getLastDay() != getDay()

		
	
#Watches clock and waits for current ingest to be done

# Verifies a file's existance
def file_exists(file):
	try:
		if os.path.exists(file):
			return os.path.isfile(file)
	except:
		return False
		
# Verifies a directory's existance
def dir_exists(dir):
	try:
		return os.path.exists(dir)
	except:
		return False

# Copy the log files from Autopsy's default directory
def copy_logs():
	try:
		log_dir = os.path.join("..", "..", "Testing","build","test","qa-functional","work","userdir0","var","log")
		shutil.copytree(log_dir, Emailer.make_local_path(case.output_dir, case.image_name, "logs"))
	except Exception as e:
		printerror("Error: Failed to copy the logs.")
		printerror(str(e) + "\n")
		logging.warning(traceback.format_exc())
# Clears all the files from a directory and remakes it
def clear_dir(dir):
	try:
		if dir_exists(dir):
			shutil.rmtree(dir)
		os.makedirs(dir)
		return True;
	except:
		printerror("Error: Cannot clear the given directory:")
		printerror(dir + "\n")
		return False;

def del_dir(dir):
	try:
		if dir_exists(dir):
			shutil.rmtree(dir)
		return True;
	except:
		printerror("Error: Cannot delete the given directory:")
		printerror(dir + "\n")
		return False;
# Copies a given file from "ffrom" to "to"
def copy_file(ffrom, to):
	try :
		if not file_exists(ffrom):
			raise FileNotFoundException(ffrom)
		shutil.copy(ffrom, to)
	except:
		raise FileNotFoundException(to)

# Copies a directory file from "ffrom" to "to"
def copy_dir(ffrom, to):
	#try :
	if not os.path.isdir(ffrom):
		raise FileNotFoundException(ffrom)
	shutil.copytree(ffrom, to)
	#except:
		#raise FileNotFoundException(to)
# Returns the first file in the given directory with the given extension
def get_file_in_dir(dir, ext):
	try:
		for file in os.listdir(dir):
			if file.endswith(ext):
				return Emailer.make_path(dir, file)
		# If nothing has been found, raise an exception
		raise FileNotFoundException(dir)
	except:
		raise DirNotFoundException(dir)
		
def find_file_in_dir(dir, name, ext):
	try: 
		for file in os.listdir(dir):
			if file.startswith(name):
				if file.endswith(ext):
					return Emailer.make_path(dir, file)
		raise FileNotFoundException(dir)
	except:
		raise DirNotFoundException(dir)

# Compares file a to file b and any differences are returned
# Only works with report html files, as it searches for the first <ul>
def compare_report_files(a_path, b_path):
	a_file = open(a_path)
	b_file = open(b_path)
	a = a_file.read()
	b = b_file.read()
	a = a[a.find("<ul>"):]
	b = b[b.find("<ul>"):]
	
	a_list = split(a, 50)
	b_list = split(b, 50)
	if not len(a_list) == len(b_list):
		ex = (len(a_list), len(b_list))
		return ex
	else: 
		return (0, 0)
  
# Split a string into an array of string of the given size
def split(input, size):
	return [input[start:start+size] for start in range(0, len(input), size)]

# Returns the nth word in the given string or "" if n is out of bounds
# n starts at 0 for the first word
def get_word_at(string, n):
	words = string.split(" ")
	if len(words) >= n:
		return words[n]
	else:
		return ""

# Returns true if the given file is one of the required input files
# for ingest testing
def required_input_file(name):
	if ((name == "notablehashes.txt-md5.idx") or
	   (name == "notablekeywords.xml") or
	   (name == "nsrl.txt-md5.idx")): 
	   return True
	else:
		return False

		

# Returns the args of the test script
def usage():
	return """
Usage:  ./regression.py [-f FILE] [OPTIONS]

		Run RegressionTest.java, and compare the result with a gold standard.
		By default, the script tests every image in ../input
		When the -f flag is set, this script only tests a single given image.
		When the -l flag is set, the script looks for a configuration file,
		which may outsource to a new input directory and to individual images.
		
		Expected files:
		  An NSRL database at:			../input/nsrl.txt-md5.idx
		  A notable hash database at:	 ../input/notablehashes.txt-md5.idx
		  A notable keyword file at:	  ../input/notablekeywords.xml
		
Options:
  -r			Rebuild the gold standards for the image(s) tested.
  -i			Ignores the ../input directory and all files within it.
  -u			Tells Autopsy not to ingest unallocated space.
  -k			Keeps each image's Solr index instead of deleting it.
  -v			Verbose mode; prints all errors to the screen.
  -e ex		 Prints out all errors containing ex.
  -l cfg		Runs from configuration file cfg.
  -c			Runs in a loop over the configuration file until canceled. Must be used in conjunction with -l
  -fr			Will not try download gold standard images
	"""




#------------------------------------------------------------#
# Exception classes to manage "acceptable" thrown exceptions #
#		  versus unexpected and fatal exceptions			#
#------------------------------------------------------------#

# If a file cannot be found by one of the helper functions
# they will throw a FileNotFoundException unless the purpose
# is to return False
class FileNotFoundException(Exception):
	def __init__(self, file):
		self.file = file
		self.strerror = "FileNotFoundException: " + file
		
	def print_error(self):
		printerror("Error: File could not be found at:")
		printerror(self.file + "\n")
	def error(self):
		error = "Error: File could not be found at:\n" + self.file + "\n"
		return error

# If a directory cannot be found by a helper function,
# it will throw this exception
class DirNotFoundException(Exception):
	def __init__(self, dir):
		self.dir = dir
		self.strerror = "DirNotFoundException: " + dir
		
	def print_error(self):
		printerror("Error: Directory could not be found at:")
		printerror(self.dir + "\n")
	def error(self):
		error = "Error: Directory could not be found at:\n" + self.dir + "\n"
		return error




#Executes the tests, makes continuous testing easier 
def execute_test():
	global parsed
	global errorem
	global failedbool
	global html
	global attachl
	if(not dir_exists(Emailer.make_path("..", "output", "results"))):
		os.makedirs(Emailer.make_path("..", "output", "results",))
	case.output_dir = Emailer.make_path("..", "output", "results", time.strftime("%Y.%m.%d-%H.%M.%S"))
	os.makedirs(case.output_dir)
	case.common_log = "AutopsyErrors.txt"
	case.csv = Emailer.make_local_path(case.output_dir, "CSV.txt")
	case.html_log = Emailer.make_path(case.output_dir, "AutopsyTestCase.html")
	log_name = case.output_dir + "\\regression.log"
	logging.basicConfig(filename=log_name, level=logging.DEBUG)
	# If user wants to do a single file and a list (contradictory?)
	if args.single and args.list:
		printerror("Error: Cannot run both from config file and on a single file.")
		return
	# If working from a configuration file
	if args.list:
	   if not file_exists(args.config_file):
		   printerror("Error: Configuration file does not exist at:")
		   printerror(args.config_file)
		   return
	   run_config_test(args.config_file)
	# Else if working on a single file
	elif args.single:
	   if not file_exists(args.single_file):
		   printerror("Error: Image file does not exist at:")
		   printerror(args.single_file)
		   return
	   run_test(args.single_file, 0)
	# If user has not selected a single file, and does not want to ignore
	#  the input directory, continue on to parsing ../input
	if (not args.single) and (not args.ignore) and (not args.list):
	   args.config_file = "config.xml"
	   if not file_exists(args.config_file):
		   printerror("Error: Configuration file does not exist at:")
		   printerror(args.config_file)
		   return
	   run_config_test(args.config_file)
	write_html_foot()
	html.close()
	logres = search_common_log("TskCoreException")
	if (len(logres)>0):
		failedbool = True
		imgfail = True
		passFail = False
		for lm in logres:
			errorem += lm
	html.close()
	if failedbool:
		passFail = False
		errorem += "The test output didn't match the gold standard.\n"
		errorem += "Autopsy test failed.\n"
		attachl.append(case.common_log_path)
		attachl.insert(0, html.name)
	else:
		errorem += "Autopsy test passed.\n"
		passFail = True
		attachl = []
	if not args.gold_creation:
		Emailer.send_email(parsed, errorem, attachl, passFail)
		
def secs_till_tommorow():
	seconds = (23*3600)-(int(strftime("%H", localtime()))*3600)
	seconds += (59*60)-(int(strftime("%M", localtime()))*60)
	seconds += 60-(int(strftime("%S", localtime())))
	return seconds+5
#----------------------#
#		 Main		 #
#----------------------#
def main():
	# Global variables
	global args
	global case
	global database
	global failedbool
	global inform
	global fl
	global errorem
	global attachl
	global daycount
	global redo
	global passed
	daycount = 0
	failedbool = False
	redo = False
	errorem = ""
	case = TestAutopsy()
	database = Database()
	printout("")
	args = Args()
	attachl = []
	passed = False
	# The arguments were given wrong:
	if not args.parse():
		case.reset()
		return
	if(not args.fr):
		antin = ["ant"]
		antin.append("-f")
		antin.append(os.path.join("..","..","build.xml"))
		antin.append("test-download-imgs")
		if SYS is OS.CYGWIN:
			subprocess.call(antin)
		elif SYS is OS.WIN:
			theproc = subprocess.Popen(antin, shell = True, stdout=subprocess.PIPE)
			theproc.communicate()
	# Otherwise test away!
	execute_test()
	if(args.daily and args.contin):
		time.sleep(secs_till_tommorow())
	while args.contin:
		redo = False
		attachl = []
		errorem = "The test standard didn't match the gold standard.\n"
		failedbool = False
		passed = False
		execute_test()
		case = TestAutopsy()

class OS:
  LINUX, MAC, WIN, CYGWIN = range(4)	  
if __name__ == "__main__":
	global SYS
	if _platform == "linux" or _platform == "linux2":
		SYS = OS.LINUX
	elif _platform == "darwin":
		SYS = OS.MAC
	elif _platform == "win32":
		SYS = OS.WIN
	elif _platform == "cygwin":
		SYS = OS.CYGWIN
		
	if SYS is OS.WIN or SYS is OS.CYGWIN:
		main()
	else:
		print("We only support Windows and Cygwin at this time.")
