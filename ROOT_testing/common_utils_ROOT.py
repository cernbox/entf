#--------------------------------------------------------------------------------
# Common utilities for ROOT testing
#   TODO: on the long run, there should be a single common_utils.py across all the testing packages
#--------------------------------------------------------------------------------


import hashlib
import os
import sys
import time


#--------------------------------------------------------------------------------
# Define global variables and supported test/file types and 
#--------------------------------------------------------------------------------
#CWD    = "/eos/user/c/cboxtu/Enrico_swanIOtesting"
CWD     = os.getcwd()

RESULTS = "processing"
SUPPORTED_FILETYPES = ["text", "binary"]

LOG_FOLDER      = "logs"
LOG_EXTENSION   = ".log"
LOG_DELIMITER   = "| "


#--------------------------------------------------------------------------------
# Logger class
#   Create a log file to output collected statistics
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


#--------------------------------------------------------------------------------
# Check file type
#   Checks whether the requested file type is supported
#--------------------------------------------------------------------------------
def stringify(float_in):
    return "%.6f" % float_in
