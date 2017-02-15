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
# Home folder and notebooks extension
NB_EXT = ".nbconvert.ipynb"

# Grafana Monitoring Framework
MONITORING_HOST="filer-carbon.cern.ch"
MONITORING_PORT=2003


#--------------------------------------------------------------------------------
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
def load_groundtruth(fname):
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

        self.out_md5	= None		# From generated output
        self.ref_md5	= None		# From groundtruth file
        self.md5_match	= None

    def set_error(self, etype):
        self.error = True
        self.error_type = etype

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
    def __init__(self, folder_in, folder_out=CWD, ttype=None, exclude_list=None, sanity_check=False, gt_fname=None, to_grafana=False):
        self.test_type      = ttype.lower() if (ttype) else os.path.split(folder_in)[1].lower()
        self.ref_timestamp  = int(time.time())
        self.ref_test_name  = self.test_type+"_"+str(self.ref_timestamp)

        self.folder_master  = folder_in
        self.folder_copy    = os.path.join(folder_out, RESULTS, self.ref_test_name)
        self.folder_res     = os.path.join(folder_out, RESULTS, self.ref_test_name+"_results")

        self.available_nb   = set()
        self.exclude_nb     = set(exclude_list)
        self.nb_metadata    = {}												# There comes the Notebook class

        self.check_data     = sanity_check
        self.groundtruth_fn = gt_fname
        self.groundtruth    = None
        self.to_grafana     = to_grafana

        self.log            = Logger(os.path.join(LOG_FOLDER, self.ref_test_name+LOG_EXTENSION)) 
        self.log.write("info", "Experiment starting...")
        self.log.write("info", time.strftime("%c"))
        if (not ttype):
            self.log.write("warning", "Test type not specified. Using source folder name")
        self.log_params()
        self.run_preliminary_checks()
        self.init_output_folder()
        
    # Log experiment parameters
    def log_params(self):
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

    # Preliminary checks
    def run_preliminary_checks(self):
        if (self.check_data):
            if (not self.groundtruth_fn):										# You wanted the sanity check but did not provide groundtruth
                self.log.write("warning", "Sanity check required but groundtruth file not provided")
                self.check_data = False
                self.log.write("info", "Sanity check disabled")
            elif (not os.path.isfile(self.groundtruth_fn)):							# You wanted the sanity check but groundtruth file is missing
                self.log.write("warning", "Sanity check required but groundtruth file not found")
                self.check_data = False
                self.log.write("warning", "Sanity check disabled")
        self.log.write("info", "Preliminary checks passed")

    # Output folders initialization
    def init_output_folder(self):
        self.log.write("info", "Creating output folders...")
        shutil.copytree(self.folder_master, self.folder_copy)					# Make a copy of the master notebooks
        os.makedirs(self.folder_res)											# Initialize result folder
        self.log.write("info", "Output folders created")


    # Run the notebooks
    def run(self):

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
            except RuntimeError:
                self.nb_metadata[cnb].set_error("timed_out")
                self.log.write("warning", "Timed-out: "+cnb)
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
            except IOError:
                self.nb_metadata[cnb].set_error("io_err")
                self.log.write("warning", "IO error while writing output: "+cnb)
                print "\t!error writing output file: "+cnb
        self.log.write("info", "Notebooks executed: "+str(len(self.nb_metadata.keys())))
        self.log.write("info", "End of notebooks execution")
        print "Done with the notebooks."

        # If you enabled the sanity check
        if (self.check_data):
            self.run_sanity_check()

        # If you enabled the push-to-monitoring capability
        if (self.to_grafana):
            self.push_to_grafana()

        # Goodbye
        self.log.write("info", "End of experiment")
        self.log.close()


    def run_sanity_check(self):
        self.log.write("info", "Begin of sanity check...")
        print "Sanity check."

        # Load the groundtruth from file first
        self.log.write("info", "Loading groundtruth from file...")
        self.groundtruth = load_groundtruth(self.groundtruth_fn)
        self.log.write("info", "Groundtruth loaded")

        # Scroll the list of executed notebooks, get reference md5 from groundtruth and compute md5 from output
        for nb_name, nb_class in self.nb_metadata.items():
            if (nb_class.error):
                self.log.write("consistency", "\t".join([nb_name, "Error", nb_class.error_type]))
                continue

            # TODO: you might need a try/expect here for Keys on the groundtruth
            self.nb_metadata[nb_name].ref_md5 = self.groundtruth[(self.nb_metadata[nb_name].test_type, self.nb_metadata[nb_name].name)]
            self.nb_metadata[nb_name].out_md5 = get_md5(self.nb_metadata[nb_name].out_file)
            self.log.write("consistency", "\t".join([nb_name, str(self.nb_metadata[nb_name].compare()), nb_class.ref_md5, nb_class.out_md5]))
        self.log.write("info", "End of sanity check")



    def push_to_grafana(self, host=MONITORING_HOST, port=MONITORING_PORT):
        self.log.write("info", "Pushing data to grafana...")
        self.log.write("info", "Grafana host: "+host)
        self.log.write("info", "Grafana port: "+port)

        # TODO: this should be implemented...

        self.log.write("info", "End of push to grafana")

    # TODO: we might want to extend the monitoring to CDash
    def push_to_CDash(self):
        pass

