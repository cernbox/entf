import hashlib
import os
import sys
import time

import payload_gen


#--------------------------------------------------------------------------------
# Define global variables and supported test/file types and 
#--------------------------------------------------------------------------------
#CWD    = "/eos/user/e/ebocchi/Tests_on_SWAN/IO_testing"
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
# Checksum class
#   Provides support for checksum check on written data
#-------------------------------------------------------------------------------
class Checksum:
    def __init__(self, sno, fname):
        self.seq_no     = sno
        self.fname      = fname
        self.source_md5 = None
        self.disk_md5   = None

    def set_source_md5(self, data):
        hash_md5 = hashlib.md5()
        hash_md5.update(data)
        self.source_md5 = hash_md5.hexdigest()

    def set_disk_md5(self):
        hash_md5 = hashlib.md5()
        hash_md5.update(open(self.fname, "r").read())
        self.disk_md5 = hash_md5.hexdigest()

    def compare(self):
        return self.source_md5 == self.disk_md5

    def make_output_for_logging(self):
        return "\t".join(["%07d" % self.seq_no, self.fname, str(self.compare()), self.source_md5, self.disk_md5])


#--------------------------------------------------------------------------------
# Check file type
#   Checks whether the requested file type is supported
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
# Get the payload done by payload_gen.py
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

