import os
import sys
import time

from argparse import ArgumentParser

from common_utils import *



#-------------------------------------------------------------------------------
# TODO: 
#   - By now the payload is stored in memory before being dumped to disk (it will not work with huge payloads)
#   - How do I recover if try catch gets stuck as well? This would cause a loss of statistics...
#   If possible, store statistics on the local machine
#-------------------------------------------------------------------------------


#-------------------------------------------------------------------------------
# Argument parser
#   Userful for automate experiments from the CLI
#-------------------------------------------------------------------------------
def process_opt():
    usage = """usage: test_write.py [options]"""
    parser = ArgumentParser(usage=usage)

    parser.add_argument("--output_folder", dest="out_dir", type=str, 
              help="Absolute path where to write logs and files")

    parser.add_argument("--file_no", dest="file_no", type=int, required=True, 
              help="Number of files to be generated")
    parser.add_argument("--file_size", dest="file_size", type=int, required=True, 
              help="Size of each file in Bytes")
    parser.add_argument("--file_type", dest="file_type", type=str, required=True, 
              help="Content type for files (e.g., text, binary)")

    parser.add_argument("--chunk_size", dest="chunk_size", type=int, required=True, 
              help="Number of bytes to be written for flush+os.fsync cycle")
    parser.add_argument("--chunk_time", dest="chunk_time", type=float, required=True, 
              help="Wait time in seconds between flush+os.fsync cycle")
    
    parser.add_argument("--interfile_time", dest="inter_time", type=float, default=0, 
              help="Wait time in seconds between write operations of two files")

    parser.add_argument("--sanity_check", dest="check_data", action='store_true', default=False, 
              help="Read data from disk and compare MD5 checksums")

    opt = parser.parse_args()
    return opt


#-------------------------------------------------------------------------------
# Append Write class
#   Class for testing plain write to disk mode: {open_append-write-flush-synch-close-wait}...
#-------------------------------------------------------------------------------
class Append():
    def __init__(self, fno, fsize, ftype, chunk_size=4096, chunk_time=0, itime=0, sanity_check=False, output_folder=CWD):
        self.test_type      = "append"
        self.ref_timestamp  = int(time.time())
        self.ref_test_name  = self.test_type+"_"+str(self.ref_timestamp)

        self.file_no        = fno
        self.file_size      = fsize
        self.file_type      = ftype
        self.chunk_size     = chunk_size
        self.chunk_time     = chunk_time
        self.inter_time     = itime
        self.check_data     = sanity_check

        self.output_folder  = output_folder
        self.logger_folder  = os.path.join(self.output_folder, LOG_FOLDER)
        self.result_folder  = os.path.join(self.output_folder, RESULTS, self.ref_test_name)
        self.checksums      = {}

        self.log            = Logger(os.path.join(self.logger_folder, self.ref_test_name+LOG_EXTENSION))
        self.log.write("info", "Experiment starting...")
        self.log.write("info", time.strftime("%c"))
        self.log_params()
        self.run_preliminary_checks()
        self.init_output_folder()

    def log_params(self):
        self.log.write("parameters", "Test type: "+self.test_type)
        self.log.write("parameters", "Test name: "+self.ref_test_name)
        self.log.write("parameters", "Test time: "+str(self.ref_timestamp))
        self.log.write("parameters", "File number: "+str(self.file_no))
        self.log.write("parameters", "File size: "+str(self.file_size))
        self.log.write("parameters", "File type: "+self.file_type)
        self.log.write("parameters", "Flush size: "+str(self.chunk_size))
        self.log.write("parameters", "Inter-flush time: "+str(self.chunk_time))
        self.log.write("parameters", "Inter-file time: "+str(self.inter_time)+"sec")
        self.log.write("parameters", "Sanity check required: "+str(self.check_data))
        self.log.write("parameters", "Typed ouput folder: "+self.output_folder)
        self.log.write("parameters", "Logger folder: "+self.logger_folder)
        self.log.write("parameters", "Results folder: "+self.result_folder)

    # Preliminary checks
    def run_preliminary_checks(self):
        if (not check_filetype(self.file_type)):
            self.log.write("error", "Unknown file type. Cannot continue.")
            sys.exit(1)
        self.log.write("info", "Preliminary checks passed")

    # Output folders initialization
    def init_output_folder(self):
        self.log.write("info", "Creating results folder...")
        if (not os.path.exists(self.result_folder)):
            os.makedirs(self.result_folder)
        self.log.write("info", "Results folder created")


    # Run the tests
    def run(self):

        # Generate the workload
        self.log.write("info", "Creating workload...")
        payload = make_payload(self.file_type, self.file_no, self.file_size)
        self.log.write("info", "Workload created")
        print "Workload created."

        # Write the payload to disk
        self.log.write("info", "Begin of write operations...")
        self.log.write("performance", "\t".join(["seq_no", "file_name", "file_size", "elapsed (s)", "through (MB/s)", "t_start", "t_end"]), write_timestamp=False)

        print "Writing to disk."
        for i, cp in enumerate(payload):
            fname = os.path.join(self.result_folder, self.ref_test_name+"_%07d" % i)
            file_start = time.time()
            append(cp, fname, self.chunk_size, self.chunk_time)
            file_end = time.time()
            
            elapsed = file_end-file_start
            throughput = (self.file_size/1000000.0)/elapsed  # These are MB/sec
            self.log.write("performance", "\t".join(str(cval) for cval in ["%07d" % i, fname, self.file_size, stringify(elapsed), stringify(throughput), file_start, file_end]), write_timestamp=False)

            # Crunch the current payload for eventual sanity check
            self.checksums[fname] = Checksum(i, fname)
            self.checksums[fname].set_source_md5(cp)

            # Sleep time, if specified
            time.sleep(self.inter_time)
            print i, fname
        self.log.write("info", "End of write operations")

        # If you enabled the sanity check
        if (self.check_data):
            self.run_sanity_check()

        # Goodbye
        self.log.write("info", "End of experiment")
        self.log.close()


    # Execute sanity checks on written bytes
    def run_sanity_check(self):
        self.log.write("info", "Begin of sanity check...")
        self.log.write("consistency", "\t".join(["seq_no", "file_name", "matching", "source_md5", "disk_md5"]), write_timestamp=False)
        print "Sanity check."

        for f in sorted(self.checksums.keys()):
            self.checksums[f].set_disk_md5()
            self.log.write("consistency", self.checksums[f].make_output_for_logging(), write_timestamp=False)
            if (not self.checksums[f].compare()):
                self.log.write("warning", f+" corrupted!")
        self.log.write("info", "End of sanity check")


#-------------------------------------------------------------------------------
# Append write function
#    Input:
#       - payload: data to be written to disk
#       - fout: filename
#       - chunk_size: number of bytes to be written for open-write-close cycle
#       - chunk_time: wait time in seconds between open-write-close cycles
#-------------------------------------------------------------------------------
def append(payload, fout, chunk_size, chunk_time):
    while payload:
        #print "I have data to write", str(len(payload))
        fwrite = open(fout, 'ab')
        fwrite.write(payload[0:chunk_size])
        fwrite.flush()            
        os.fsync(fwrite.fileno())
        fwrite.close()
        payload = payload[chunk_size:]
        time.sleep(chunk_time)
    return


#-------------------------------------------------------------------------------
# Orchestrate the test
#-------------------------------------------------------------------------------

# This is the argument parser from keyboard
#opt = process_opt()

#current_test = Append(opt.file_no, opt.file_size, opt.file_type, opt.chunk_size, opt.chunk_time, opt.inter_time, opt.check_data, opt.out_dir)
#current_test.run()

'''
#-------------------------------------------------------------------------------
# Workload specifications
FILE_NO = 5            # Number of files to be generated
FILE_SIZE = 1000000    # Size in Bytes of each file
FILE_TYPE = "text"     # Refer to SUPPORTED_FILETYPES for supported files types (e.g., text, binary, ...)

CHUNK_SIZE = 350000    # Number of bytes to be written for flush + os.fsync cycle
CHUNK_TIME = 0.5       # Wait time in seconds between flush + os.fsync cycle

INTER_TIME = 0.5       # Wait time in seconds between write operations of two files
CHECK_DATA = True      # Do you want to run the sanity check?


# Instantiate a class and run the test
current_test = Append(FILE_NO, FILE_SIZE, FILE_TYPE, CHUNK_SIZE, CHUNK_TIME, INTER_TIME, CHECK_DATA)
current_test.run()
'''
