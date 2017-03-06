import hashlib
import nbformat
import nbconvert
import os
import random
import shutil
import time

from common_utils_ROOT import *


#--------------------------------------------------------------------------------
# Parameters
#--------------------------------------------------------------------------------
# Notebooks extension
NB_EXT = ".nbconvert.ipynb"

# ROOT version and metadata file extension
TEST_METADATA_EXT = ".metadata"

# Error handling on notebook execution
MD5_ERR		= "md5_mismatch"
IO_ERR		= "io_err"
TIMEOUT_ERR	= "timed_out"

# Memory info fname
MEMINFO_FNAME	= "/proc/meminfo"

# Namespace on Grafana
#   Should match the pattern "test.swan.<machine_id>.<test_type>.<metric>"
GRAFANA_NAMESPACE = "test.swan"        # By now, pushing to the testing environment



#--------------------------------------------------------------------------------
# DEPRECATED
# NOTE: This is an older version used when all the groundtruth was contained in a single file
#
# Load groundtruth from file
#   The groundtruch file is expected to match this format:
#       #test_type  test_name                                   md5_checksum
#       io          copyFiles.C.nbconvert.ipynb                 72586925675c275c0e20febf7ff91037
#       io          dirs.C.nbconvert.ipynb                      b49b0b9ec6d718113e0405b02c178024
#       ...
#   Specifically: 
#   - col0: test_type
#   - col1: test_name
#   - col2: md5_checksum
#   NOTE: (test_type, test_name) make a tuple used as key to identify templates.
#           If the key does not match, the sanity check will fail.
#--------------------------------------------------------------------------------
def load_groundtruth_threecols(fname):
	gt = {}
	with open(fname, 'r') as gtin:
		for line in gtin.read().splitlines():
			if (line[0] == "#"):
				continue
			fields = line.split()									# Fields: col0-test_type, col1-test_name, col2-md5_checksum
			gt[(fields[0].lower(), fields[1])] = fields[2]
	gtin.close()
	return gt


#--------------------------------------------------------------------------------
# Checksum functions
#--------------------------------------------------------------------------------
def get_md5(fname):
	hash_md5 = hashlib.md5()
	hash_md5.update(open(fname, "r").read())
	return hash_md5.hexdigest()

def get_sha256(fname):
	hash_sha = hashlib.sha256()
	hash_sha.update(open(fname, "r").read())
	return hash_sha.hexdigest()


#--------------------------------------------------------------------------------
# Notebook Class
#	It is required to handle Notebook metadata (e.g., input, output, result, errors, sanity checksum, etc.)
#--------------------------------------------------------------------------------
class Notebook():
	def __init__(self, name, test_type):
		self.name		= name
		self.test_type	= test_type
		self.run		= False
		self.output		= False
		self.out_file	= None
		self.error		= False
		self.error_type	= None
		self.error_msg	= None

		self.out_md5	= None		# From generated output
		self.ref_md5	= None		# From groundtruth file
		self.md5_match	= None

	def set_error(self, etype, emessage):
		self.error = True
		self.error_type = etype
		self.error_msg	= emessage

	def compare(self):
		self.md5_match = True if (self.out_md5 == self.ref_md5) else False
		return self.md5_match



#--------------------------------------------------------------------------------
# Experiment Class for CERN ROOT Data Analysis Framework (https://root.cern.ch/)
#   Class for running ROOT tutorials (https://root.cern.ch/doc/master/group__Tutorials.html)
#
#   - This class is intended to execute a batch of ROOT tutorials in a single run.
#		Specifically, it executes all the tutorials available in the input folder ("folder_in")
#	- ROOT tutorials are expected to be converted to IPython Notebooks
#		and to have a ".nbconvert.ipynb" extension (or whatever extension speficied in "NB_EXT")
#--------------------------------------------------------------------------------
class Experiment():
	def __init__(self, folder_in, folder_out=CWD, machine_id=None, ttype=None, exclude_list=None, sanity_check=True, gt_fname=None, to_grafana=True, memory_stats=True):

		# The basics
		self.test_type      = ttype if (ttype) else os.path.split(folder_in)[1]
		self.ref_timestamp  = int(time.time())
		print self.ref_timestamp	# Can be useful for debuggin purposes
		self.ref_test_name  = self.test_type+"_"+str(self.ref_timestamp)

		# Input/Output folders
		self.folder_master  = folder_in
		self.folder_copy    = os.path.join(folder_out, RESULTS, self.ref_test_name)
		self.folder_res     = os.path.join(folder_out, RESULTS, self.ref_test_name+"_results")
		self.folder_status	= None

		# ROOT version and CVMFS path (to be loaded from <test_type>.metadata file)
		self.test_metadata  = os.path.join(os.path.split(self.folder_master)[0], self.test_type+TEST_METADATA_EXT)
		self.ROOTv          = None
		self.CVMFS          = None

		# Notebooks execution, statistics, sanity checks
		self.available_nb   = set()
		self.exclude_nb     = set(exclude_list)
		self.nb_metadata    = {}        # There comes the Notebook class

		# Sanity check
		self.check_data         = sanity_check
		self.groundtruth_fn     = gt_fname
		self.groundtruth_ROOTv  = None
		self.groundtruth_CVMFS  = None
		self.groundtruth_match	= None
		self.groundtruth        = None

		# Reporting to monitoring dashboards
		self.machine_id     = machine_id if (machine_id) else os.path.abspath(os.getcwd()).split(os.path.sep)[-3]
		self.to_grafana     = to_grafana
		self.memory_stats	= memory_stats

		# Init the logger
		self.log            = Logger(os.path.join(folder_out, LOG_FOLDER, self.ref_test_name+LOG_EXTENSION)) 
		self.log.write("info", "Experiment starting...")
		self.log.write("info", time.strftime("%c"))
		if (not ttype):
			self.log.write("warning", "Test type not specified. Using source folder name: "+self.test_type)
		if (not machine_id):
			self.log.write("warning", "Machine ID not specified. Using directory tree name: "+self.machine_id)

		# Execute preliminary operations
		self.log_params()
		self.run_preliminary_checks()
		self.load_ROOTversion()
		self.init_output_folder()


	# Log experiment parameters
	def log_params(self):
		self.log.write("parameters", "Machine ID: "+self.machine_id)
		self.log.write("parameters", "Test type: "+self.test_type)
		self.log.write("parameters", "Test name: "+self.ref_test_name)
		self.log.write("parameters", "Test time: "+str(self.ref_timestamp))
		self.log.write("parameters", "Exclude list: "+",".join(self.exclude_nb))
		self.log.write("parameters", "Master folder: "+self.folder_master)
		self.log.write("parameters", "Copy folder: "+self.folder_copy)
		self.log.write("parameters", "Result folder: "+self.folder_res)
		self.log.write("parameters", "Sanity check required: "+str(self.check_data))
		self.log.write("parameters", "Groundtruth file: "+self.groundtruth_fn)
		self.log.write("parameters", "Push to Grafana: "+str(self.to_grafana))
		self.log.write("parameters", "Report memory usage statistics: "+str(self.memory_stats))

	# Preliminary checks
	def run_preliminary_checks(self):
		if (self.check_data):
			if (not self.groundtruth_fn):										# You wanted the sanity check but did not provide groundtruth
				self.log.write("warning", "Sanity check required but groundtruth file not provided")
				self.check_data = False
				self.log.write("info", "Sanity check disabled")
			elif (not os.path.isfile(self.groundtruth_fn)):                     # You wanted the sanity check but groundtruth file is missing
				self.log.write("warning", "Sanity check required but groundtruth file not found")
				self.check_data = False
				self.log.write("warning", "Sanity check disabled")
		self.log.write("info", "Preliminary checks passed")

	# Load ROOT version (or at least try to...)
	def load_ROOTversion(self):
		self.log.write("info", "Loading ROOT version info...")
		try:
			with open(self.test_metadata, 'r') as fin:
				for line in fin:
					if (line.startswith("#VERSION:")):
						version = line.split(":")[1].strip()
						self.ROOTv = version
						self.log.write("info", "ROOT version: "+version)
					if (line.startswith("#CVMFS_PATH:")):
						cvmfs_path = line.split(":")[1].strip()
						self.CVMFS = cvmfs_path
						self.log.write("info", "CVMFS path: "+cvmfs_path)
			fin.close()
		except IOError:     # Maybe the metadata file does not exists
			self.log.write("warning", "Unable to load ROOT version")
			self.ROOTv = "Unknown"
			self.CVMFS = "Unknown"
			

	# Output folders initialization
	def init_output_folder(self):
		self.log.write("info", "Creating output folders...")
		try:
			shutil.copytree(self.folder_master, self.folder_copy)					# Make a copy of the master notebooks
			os.makedirs(self.folder_res)											# Initialize result folder
			self.log.write("info", "Output folders created")
			self.folder_status = True
		except IOError as err:
			self.folder_status = False
			self.log.write("error", "Unable to initialize output folders")
			self.log.write("error", str(err))


	# Run the notebooks
	def run(self):

		if (not self.folder_status):
			self.log.write("error", "Unable to run experiments. Exiting...")
			return -1

		# Look for notebooks in the folder
		#os.chdir(self.folder_copy)
		for i in os.listdir(self.folder_copy):
			if (i[-len(NB_EXT):] == NB_EXT):
				self.available_nb.add(i)										# Make a list of available notebooks
		self.log.write("info", "Notebooks detected: "+str(len(self.available_nb)))
		self.log.write("info", "Notebooks in the exclude list: "+str(len(self.exclude_nb)))
		print "Notebooks detected: "+str(len(self.available_nb))

		# Scroll the list of notebooks and run the eligible ones
		self.log.write("info", "Begin of notebooks execution...")
		for cnb in sorted(self.available_nb):

			# Verify exclusion list
			if (cnb in self.exclude_nb):
				self.log.write("info", "Skipping "+cnb+" as it appears in exclude list")
				continue

			# If I do not drop the notebook, initialize the Notebook class for metadata
			self.nb_metadata[cnb] = Notebook(cnb, self.test_type)

			# Read and run the notebook
			self.log.write("info", "Running "+cnb+"...")
			print "\tRunning: "+cnb
			
			f = open(os.path.join(self.folder_copy, cnb))
			nb = nbformat.read(f, as_version=4)
			f.close()
			try: 
				exe_proc = nbconvert.preprocessors.ExecutePreprocessor(timeout=600) #kernel_name='ROOTC++')
				exe_proc.preprocess(nb, {'metadata': {'path': self.folder_copy}})
				self.nb_metadata[cnb].run = True
				self.log.write("info", "Successful run "+cnb)
			except RuntimeError as err:
				self.nb_metadata[cnb].set_error(TIMEOUT_ERR, err)
				self.log.write("warning", cnb+": timed-out")
				self.log.write("warning", cnb+": "+str(err))
				print "\t!error notebook timed out "+cnb
				continue

			# Store notebook results
			result_file = os.path.join(self.folder_res, cnb+".output.ipynb")
			self.nb_metadata[cnb].out_file = result_file
			try:
				f = open(result_file, 'w')
				nbformat.write(nb, f)
				f.close()
				self.nb_metadata[cnb].output = True
				self.log.write("info", "Successful output "+cnb)
			except IOError as err:
				self.nb_metadata[cnb].set_error(IO_ERR, err)
				self.log.write("warning", cnb+": IO error while writing output")
				self.log.write("warning", cnb+": "+str(err))
				print "\t!error writing output file: "+cnb
		self.log.write("info", "Notebooks executed: "+str(len(self.nb_metadata.keys())))
		self.log.write("info", "End of notebooks execution")
		print "Done with the notebooks."

		# If you enabled the sanity check
		if (self.check_data):
			self.run_sanity_check()

		# If you enabled to report statistics about memory usage
		if (self.memory_stats):
			self.log.write("info", "Reporting memory usage statistics...")
			# Load memory usage information
			mem_stats = {	'total': None,\
							'free': None, \
							'used': None, \
							'available': None,\
							'cached': None}
			with open(MEMINFO_FNAME) as fin:
				for line in fin.read().splitlines():
					if (line.startswith("MemTotal:")):
						mem_stats["total"] = line.split()[1]
					if (line.startswith("MemFree:")):
						mem_stats["free"] = line.split()[1]
					if (line.startswith("MemAvailable:")):
						mem_stats["available"] = line.split()[1]
					if (line.startswith("Cached:")):
						mem_stats["cached"] = line.split()[1]
			if (mem_stats["total"] and mem_stats["free"]):
				mem_stats["used"] = str(int(mem_stats["total"])-int(mem_stats["free"]))
			fin.close()
			# Dump the statistics to the log file
			for k,v in mem_stats.items():
				self.log.write("mem", k+"_memory (kB): "+v)
			self.log.write("info", "End memory usage statistics")

		# If you enabled the push-to-monitoring capability
		if (self.to_grafana):
			self.push_to_grafana()
			if (self.memory_stats):
				self.memory_to_grafana(mem_stats)
		#if (self.push_to_CDash):
		#	self.push_to_CDash()

		# Goodbye
		self.log.write("info", "End of experiment")
		self.log.close()


	def run_sanity_check(self):
		self.log.write("info", "Begin of sanity check...")
		print "Sanity check."

		#--------------------------------------------------------------------------------
		# Load groundtruth from file
		#   The groundtruch file is expected to match this format:
		#       #test_name                                  md5_checksum
		#       basic2.C.nbconvert.ipynb                    72de0569619c19730247eb68c895582e
		#       basic.C.nbconvert.ipynb                     3f6e188d974b90ae9bc72518e9306982
		#       bill.C.nbconvert.ipynb                      cb7f3bcb62e8d52217791b3a6aae992e
		#       ...
		#
		#   Specifically: 
		#   - col0: test_name
		#   - col1: md5_checksum
		#   NOTE: test_name is the key to identify templates.
		#       If the key does not match, the sanity check will fail.
		#--------------------------------------------------------------------------------
		self.log.write("info", "Loading groundtruth from file...")
		self.groundtruth = {}

		with open(self.groundtruth_fn, 'r') as gtin:
			for line in gtin.read().splitlines():

				# Try to spot ROOT version and CVMFS path
				if (line.startswith("#VERSION:")):
					version = line.split(":")[1].strip()
					self.groundtruth_ROOTv = version
					self.log.write("info", "Groundtruth built for ROOT version: "+version)
				if (line.startswith("#CVMFS_PATH:")):
					cvmfs_path = line.split(":")[1].strip()
					self.groundtruth_CVMFS = cvmfs_path
					self.log.write("info", "Groundtruth built for CVMFS path: "+cvmfs_path)

				# If the line is not a comment, load the groundtruth
				if (line[0] != "#"):
					fields = line.split()		# Fields: col0-test_name, col1-md5_checksum
					self.groundtruth[fields[0]] = fields[1]
		gtin.close()

		# If I was not able to spot ROOT version and CVMFS path, throw a warning
		if (not (self.groundtruth_ROOTv and self.groundtruth_CVMFS)):
			self.log.write("warning", "Unable to load ROOT version for groundtruth")

		# If I loaded the version but it does not match, throw a warning
		elif (not (self.ROOTv == self.groundtruth_ROOTv and self.CVMFS == self.groundtruth_CVMFS)):
			self.log.write("warning", "ROOT version for groundtruth not matching current ROOT version")

		# Otherwise, the versions are matching: Be happy!
		else:
			self.groundtruth_match = True
			self.log.write("info", "ROOT version matches")
		self.log.write("info", "Groundtruth loaded")

		# Scroll the list of executed notebooks, get reference md5 from groundtruth and compute md5 from output
		for nb_name, nb_class in self.nb_metadata.items():
			if (nb_class.error):
				self.log.write("consistency", "\t".join([nb_name, "Error", nb_class.error_type]))
				continue

			# TODO: you might need a try/expect here for Keys on the groundtruth
			self.nb_metadata[nb_name].ref_md5 = self.groundtruth[self.nb_metadata[nb_name].name]
			self.nb_metadata[nb_name].out_md5 = get_md5(self.nb_metadata[nb_name].out_file)
			self.log.write("consistency", "\t".join([nb_name, str(self.nb_metadata[nb_name].compare()), nb_class.ref_md5, nb_class.out_md5]))

			'''
			# This is the code for three-columns groundtruth, now deprecated
			# TODO: you might need a try/expect here for Keys on the groundtruth
			self.nb_metadata[nb_name].ref_md5 = self.groundtruth[(self.nb_metadata[nb_name].test_type, self.nb_metadata[nb_name].name)]
			self.nb_metadata[nb_name].out_md5 = get_md5(self.nb_metadata[nb_name].out_file)
			self.log.write("consistency", "\t".join([nb_name, str(self.nb_metadata[nb_name].compare()), nb_class.ref_md5, nb_class.out_md5]))
			'''
		self.log.write("info", "End of sanity check")

	# Publish results on Grafana monitoring dashboard
	def push_to_grafana(self, namespace=GRAFANA_NAMESPACE):
		self.log.write("info", "Publishing results on Grafana...")
		self.log.write("info", "Grafana namespace: "+namespace)

		# Build more detailed stats from the Notebook class dictionary
		successes	= 0
		sanity_err	= 0
		oth_err		= 0
		failure_stats	= {}
		failure_stats[MD5_ERR] = set()
		for nb in self.nb_metadata.values():
			# Check if the notebook raised an IO error or timed out
			if (nb.error):
				if (nb.error_type not in failure_stats.keys()):
					failure_stats[nb.error_type] = set()
				failure_stats[nb.error_type].add(nb.name)
				oth_err += 1
			# Check if md5 checksums match
			elif(not nb.md5_match):
				failure_stats[MD5_ERR].add(nb.name)
				sanity_err += 1
			# Otherwise, assume everything went fine
			else:
				successes += 1

		# Report overall info
		metrics = { "tot_exp": len(self.nb_metadata.keys()),	 		# Total notebooks executed for this run
					"success": successes,								# Notebooks matching groundtruth
					"error": sanity_err, 								# Notebooks NOT matching groundtruth
					"oth_error": oth_err,								# Notebooks experiencing other errors, e.g., Time-out or IOError
					"io_err": len(failure_stats[IO_ERR]) if IO_ERR in failure_stats.keys() else 0,					# Notebooks interrupted by IOErrors
					"timeout_err": len(failure_stats[TIMEOUT_ERR]) if TIMEOUT_ERR in failure_stats.keys() else 0,	# Notebooks interrupted by RuntimeError
					"total_runs": 1,									# Just raise one hand (set to *total* on Grafana side)
					"ROOT_version": self.ROOTv,							# Report ROOT version being used
					"Groundtruth_version": self.groundtruth_ROOTv,		# Report groundtruth ROOT version
					"Version_matching": self.groundtruth_match			# Report matching ROOT / groundtruth versions
				  }
		for k,v in metrics.items():
			metric = ".".join([namespace, self.machine_id, self.test_type, k])
			#print metric, str(v)
			hostname, port_no = publish_on_grafana(metric, str(v), self.ref_timestamp)

		# Report error conditions
		for k,v in failure_stats.items():
			metric = ".".join([namespace, self.machine_id, self.test_type, k+"_list"])
			#print metric, ",".join(list(v))
			hostname, port_no = publish_on_grafana(metric, ",".join(list(v)), self.ref_timestamp)

		self.log.write("info", "Grafana host: "+hostname)
		self.log.write("info", "Grafana port: "+str(port_no))
		self.log.write("info", "End of publishing on Grafana")

	# Publish memory statistics on Grafana monitoring dashboard
	def memory_to_grafana(self, mem_stats, namespace=GRAFANA_NAMESPACE):
		self.log.write("info", "Publishing statistics on memory usage on Grafana...")
		self.log.write("info", "Grafana namespace: "+namespace)
		for k,v in mem_stats.items():
			hostname, port_no = publish_on_grafana(k+"_memory", v, self.ref_timestamp)

		self.log.write("info", "Grafana host: "+hostname)
		self.log.write("info", "Grafana port: "+str(port_no))
		self.log.write("info", "End of memory statistics on Grafana")


	# TODO: we might want to extend the monitoring to CDash
	def push_to_CDash(self):
		#TODO: to be implemented
		pass

