#-------------------------------------------------------------------------------
# Various utilities for IO testing
#   Provides logging, checksum, and file generation capabilities
#-------------------------------------------------------------------------------

import hashlib
import numpy
import os
import sys
import time

import payload_gen


#--------------------------------------------------------------------------------
# Global variables
#   Define global variables, supported file types, and log specifications
#--------------------------------------------------------------------------------
SUPPORTED_FILETYPES = ["text", "binary"]

#CWD    = "/eos/user/e/ebocchi/Tests_on_SWAN/IO_testing"
#CWD    = "/eos/user/c/cboxtu/Enrico_swanIOtesting"
CWD     = os.getcwd()
RESULTS = "processing"

LOG_FOLDER      = "logs"
LOG_EXTENSION   = ".log"
LOG_DELIMITER   = "| "

# Grafana Monitoring Framework
MONITORING_HOST = "filer-carbon.cern.ch"
MONITORING_PORT = 2003
GRAFANA_NAMESPACE = "test.swan_io"      # Should match the pattern "test.io_storage.<machine_id>.<test_type>.<metric>"
                                        # By now pushing to the test environment



#--------------------------------------------------------------------------------
# Logger class
#   Create a log file to output collected operations
#--------------------------------------------------------------------------------
class Logger():
    def __init__(self, fname):

        # Supported types of messages for logging
        self.msg_type_switcher = {
            "parameters": "[PARAMS] ", 
            "info": "[INFO] ",
            "performance": "[PERF] ", 
            "consistency": "[CONS] ", 
            "warning": "[WARNING] ", 
            "error": "[ERROR] ", 
            }

        # Make sure the output folder for logs is there
        log_folder = os.path.split(fname)[0]
        if (not os.path.exists(log_folder)):
            os.makedirs(log_folder)            
        self.fname = fname
        self.fout = open(fname, 'a')

    def write(self, msg_type, msg, write_timestamp=True):
        try:
            t = self.msg_type_switcher[msg_type]
        except KeyError:
            t = "[UNKNOWN] "

        message = t + LOG_DELIMITER + msg + "\n" 
        if (write_timestamp):
            message = t + "%.6f" % time.time() + LOG_DELIMITER + msg + "\n"
        self.fout.write(message)
        self.fout.flush()
        
    def close(self):
        self.fout.close()


#-------------------------------------------------------------------------------
# WriteOp class
#   Provides support for each write operation
#-------------------------------------------------------------------------------
class WriteOp:
    def __init__(self, sno, fname, fsize, ftype):
        self.seq_no     = sno
        self.fname      = fname
        self.fsize      = fsize
        self.ftype      = ftype

        self.success    = None
        self.error      = None
        self.emessage   = None      

        self.t_start    = None
        self.t_end      = None
        self.time_taken = None
        self.throughput = None

        self.source_md5 = None
        self.disk_md5   = None
        self.md5_match  = None

    # Record success/failure of the write operation
    def set_success(self):
        self.success = True
        self.error = False

    def set_error(self, emsg=None):
        self.success = False
        self.error = True
        self.emessage = emsg

    # Performance utilities
    def set_performance(self, start, end):
        self.t_start = start
        self.t_end = end
        self.time_taken = end-start
        self.throughput = (self.fsize/1000000.0)/self.time_taken   # These are MB/sec

    def performance_output_for_logging(self):
        return "\t".join(str(cval) for cval in ["%07d" % self.seq_no, self.fname, self.fsize, stringify(self.time_taken), stringify(self.throughput), self.t_start, self.t_end])

    # MD5 checksum utilities
    def set_source_md5(self, data):
        hash_md5 = hashlib.md5()
        hash_md5.update(data)
        self.source_md5 = hash_md5.hexdigest()
    
    def set_disk_md5(self):
        hash_md5 = hashlib.md5()
        hash_md5.update(open(self.fname, "r").read())
        self.disk_md5 = hash_md5.hexdigest()

    def compare_md5(self):
        self.md5_match = True if (self.source_md5 == self.disk_md5) else False
        return self.md5_match

    def checksum_output_for_logging(self):
        return "\t".join(["%07d" % self.seq_no, self.fname, str(self.md5_match), self.source_md5, self.disk_md5])



#-------------------------------------------------------------------------------
# DEPRECATED
# Checksum class
#   Provides support for checksum verification on written data
#-------------------------------------------------------------------------------
class Checksum:
    def __init__(self, sno, fname):
        self.seq_no     = sno
        self.fname      = fname
        self.source_md5 = None
        self.disk_md5   = None
        self.md5_match  = None

    def set_source_md5(self, data):
        hash_md5 = hashlib.md5()
        hash_md5.update(data)
        self.source_md5 = hash_md5.hexdigest()

    def set_disk_md5(self):
        hash_md5 = hashlib.md5()
        hash_md5.update(open(self.fname, "r").read())
        self.disk_md5 = hash_md5.hexdigest()

    def compare(self):
        self.md5_match = True if (self.source_md5 == self.disk_md5) else False
        return self.md5_match

    def make_output_for_logging(self):
        return "\t".join(["%07d" % self.seq_no, self.fname, str(self.compare()), self.source_md5, self.disk_md5])


#--------------------------------------------------------------------------------
# Float to string
#   Convert float to string with a predefined number of decimal digits
#--------------------------------------------------------------------------------
def stringify(float_in):
    return "%.6f" % float_in


#--------------------------------------------------------------------------------
# Check file type
#   Checks whether the requested file type is supported
#--------------------------------------------------------------------------------
def check_filetype(file_type):
    if (file_type not in SUPPORTED_FILETYPES):
        print "\nERROR: Unknown file type."
        return False
    return True


#--------------------------------------------------------------------------------
# Get the payload done by payload_gen.py file
#   Returns the payload as a list with lenght equal to the number of files
#--------------------------------------------------------------------------------
def make_payload(file_type, file_no, file_size):
    payload = []

    # Plain readable text files
    if (file_type == "text"):
        payload_gen.load_word_list()    # Load the wordlist from file
        for i in range(file_no):
            payload.append(payload_gen.get_text(file_size))
        return payload

    # Binary files with random bytes content
    if (file_type == "binary"):
        for i in range(file_no):
            payload.append(payload_gen.get_binary(file_size))
        return payload


#--------------------------------------------------------------------------------
# Compute statistics on write operations and publish data to Grafana
#   This function is used by test_write, test_flush, and test_append to centralize
#   the computations of statistics and ease their publication on Grafana
#--------------------------------------------------------------------------------
def make_stats_and_publish(test_class, namespace=GRAFANA_NAMESPACE):

    # Scroll the list of WriteOp to collect statistics
    success         = 0
    error           = 0
    md5_ok          = 0
    md5_mismatch    = 0
    throughput_list = []
    timing_list     = []
    for t in test_class.writeops_stats.values():
        if (t.success):
            success += 1
            throughput_list.append(t.throughput)
            timing_list.append(t.time_taken)
            if (t.md5_match):
                md5_ok += 1
            else:
                md5_mismatch += 1
        else:
            error += 1

    metrics = { "success":  success,                                # Write operations ended successfully
                "error":    error,                                  # Write operations ended with an error
                \
                "md5_ok":       md5_ok,                             # Sanity check OK
                "md5_mismatch": md5_mismatch,                       # Sanity check failed
                \
                "throughput_min":       min(throughput_list),
                "throughput_mean":      numpy.mean(throughput_list),
                "throughput_median":    numpy.median(throughput_list),
                "throughput_max":       max(throughput_list),
                "throughput_sdev":      numpy.std(throughput_list),
                \
                "time_min":             min(timing_list),
                "time_mean":            numpy.mean(timing_list),
                "time_median":          numpy.median(timing_list),
                "time_max":             max(timing_list),
                "time_sdev":            numpy.std(timing_list)
              }

    #
    # NOTE: for the time being, I am dropping all the paramters related to wait times and chunk size
    #       to avoid over-loading the grafana interface with too much information.
    #       These are all exeperiment parameters that would require filtering and templating, and, more importantly,
    #       a lot of time would be needed to collect a statically representative population of tests for each configuration.
    '''
    # Adding metrics belonging to specific tests
    metrics["inter_file_time"] == test_class.inter_time             # Write time between write of consecutive files

    if (test_class.test_type == "flush"):
        metrics["flush_size"] = test_class.flush_size               # Amount of bytes to be written to disk for each (flush + os.sync) cycle
        metrics["flush_time"] = test_class.flush_time               # Time waited between consecutive (flush + os.sync) cycles

    if (test_class.test_type == "append"):
        metrics["chunk_size"] = test_class.chunk_size               # Amount of bytes to be written to disk for each (open_append + flush + os.sync + close) cycle
        metrics["chunk_time"] = test_class.chunk_time               # Time waited between consecutive (open_append + flush + os.sync + close) cycles
    '''
    
    for k,v in metrics.items():
        metric = ".".join([namespace, test_class.machine_id, test_class.test_type, \
                            str(test_class.file_no), str(test_class.file_size), test_class.file_type, \
                            k])
        #print metric, str(v)
        hostname, port_no = publish_on_grafana(metric, str(v), test_class.ref_timestamp)
    return (hostname, port_no)


#--------------------------------------------------------------------------------
# Push to Grafana
#   Report results and statistics to the Grafana monitoring dashboard
#--------------------------------------------------------------------------------
def publish_on_grafana(metric, value, timestamp=time.time(), host=MONITORING_HOST, port=MONITORING_PORT):
    os.system("echo '%s %s %s' | nc %s %s"%(metric,value,timestamp,host,port))  # Do netcat and push data
    #print metric, value, timestamp
    return (host, port)


