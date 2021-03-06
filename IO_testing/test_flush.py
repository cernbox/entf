#-------------------------------------------------------------------------------
# Flush Write class
#   Class for testing write-flush to disk: open-{flush-sync-wait}...-close
#-------------------------------------------------------------------------------

import os
import sys
import time

from argparse import ArgumentParser

from common_utils_IO import *


#-------------------------------------------------------------------------------
# TODO: 
#   - By now the payload is stored in memory before being dumped to disk (it will not work with huge payloads)
#   - Is it possible, store logs on the local machine? If I get stuck on the mount I will lose logs as well
#-------------------------------------------------------------------------------


#-------------------------------------------------------------------------------
# Argument parser
#   Userful for automate experiments from the CLI
#-------------------------------------------------------------------------------
def process_opt():
    usage = """usage: test_write.py [options]"""
    parser = ArgumentParser(usage=usage)

    parser.add_argument("--file_no", dest="file_no", type=int, required=True, 
              help="Number of files to be generated")
    parser.add_argument("--file_size", dest="file_size", type=int, required=True, 
              help="Size of each file in Bytes")
    parser.add_argument("--file_type", dest="file_type", type=str, required=True, 
              help="Content type for files (e.g., text, binary)")

    parser.add_argument("--flush_size", dest="flush_size", type=int, required=True, 
              help="Number of bytes to be written for flush+os.fsync cycle")
    parser.add_argument("--flush_time", dest="flush_time", type=float, required=True, 
              help="Wait time in seconds between flush+os.fsync cycle")
    
    parser.add_argument("--interfile_time", dest="inter_time", type=float, default=0, 
              help="Wait time in seconds between write operations of two files")

    parser.add_argument("--sanity_check", dest="check_data", action='store_true', default=False, 
              help="Read data from disk and compare MD5 checksums")

    parser.add_argument("--output_folder", dest="out_dir", type=str, 
              help="Absolute path where to write logs and files")
    parser.add_argument("--machine_id", dest="machine_id", type=str, 
              help="Unique identifier of the machine used for tests")

    parser.add_argument("--to_grafana", dest="to_grafana", action='store_true', default=False, 
              help="Publish results on Grafana monitoring dashboard")

    opt = parser.parse_args()
    return opt


#-------------------------------------------------------------------------------
# Flush Write class
#   Class for testing write-flush to disk: open-{flush-sync-wait}...-close
#   Input:  -fno:   number of files to be written to disk
#           -fsize: size of each file in bytes
#           -ftype: content type of each file (e.g., binary, text)
#           -flush_size:    number of bytes to be written to disk for each flush operation
#           -flush_time:    wait time in seconds between flush operations
#           -itime:         wait time in seconds between close of one file and open of the following file
#           -sanity_check:  read the data back from disk and contrast it to the source
#           -output_folder: specify the output folder where to write output
#           -machine_id: unique identifier of the machine used for tests
#           -to_grafana: publish results on Grafana monitoring dashboard
#-------------------------------------------------------------------------------
class Flush():
    def __init__(self, fno, fsize, ftype, flush_size=4096, flush_time=0, itime=0, sanity_check=False, output_folder=CWD, machine_id=None, to_grafana=True):
        self.test_type      = "flush"       # DO take care of modifying this when you write a new test
        self.ref_timestamp  = int(time.time())
        self.ref_test_name  = self.test_type+"_"+str(self.ref_timestamp)

        self.file_no        = fno
        self.file_size      = fsize
        self.file_type      = ftype
        self.flush_size     = flush_size
        self.flush_time     = flush_time
        self.inter_time     = itime
        self.check_data     = sanity_check

        self.output_folder  = output_folder
        self.logger_folder  = os.path.join(self.output_folder, LOG_FOLDER)
        self.result_folder  = os.path.join(self.output_folder, RESULTS, self.ref_test_name)

        # Dictionary for keeping track of metadata related to each wrrite operation
        self.writeops_stats = {}    # Metadata class for storing statistics on each write operation

        # Reporting to monitoring dashboards
        self.machine_id     = machine_id if (machine_id) else os.path.abspath(os.getcwd()).split(os.path.sep)[-3]
        self.to_grafana     = to_grafana

        self.log            = Logger(os.path.join(self.logger_folder, self.ref_test_name+LOG_EXTENSION))
        self.log.write("info", "Experiment starting...")
        self.log.write("info", time.strftime("%c"))
        if (not machine_id):
            self.log.write("warning", "Machine ID not specified. Using directory tree name: "+self.machine_id)

        # Execute preliminary operations
        self.log_params()
        self.run_preliminary_checks()
        self.init_output_folder()


    # Log experiment parameters
    def log_params(self):
        self.log.write("parameters", "Machine ID: "+self.machine_id)
        self.log.write("parameters", "Test type: "+self.test_type)
        self.log.write("parameters", "Test name: "+self.ref_test_name)
        self.log.write("parameters", "Test time: "+str(self.ref_timestamp))
        self.log.write("parameters", "File number: "+str(self.file_no))
        self.log.write("parameters", "File size: "+str(self.file_size))
        self.log.write("parameters", "File type: "+self.file_type)
        self.log.write("parameters", "Flush size: "+str(self.flush_size))
        self.log.write("parameters", "Inter-flush time: "+str(self.flush_time))
        self.log.write("parameters", "Inter-file time: "+str(self.inter_time)+"sec")
        self.log.write("parameters", "Sanity check required: "+str(self.check_data))
        self.log.write("parameters", "Typed ouput folder: "+self.output_folder)
        self.log.write("parameters", "Logger folder: "+self.logger_folder)
        self.log.write("parameters", "Results folder: "+self.result_folder)
        self.log.write("parameters", "Publish results on Grafana: "+str(self.to_grafana))

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
        self.log.write("performance", "\t".join(["seq_no", "file_name", "file_size", "elapsed(s)", "through(MB/s)", "t_start", "t_end"]), write_timestamp=False)

        print "Writing to disk."
        for i, cp in enumerate(payload):
            # Write to disk
            fname = os.path.join(self.result_folder, self.ref_test_name+"_%07d" % i)

            # Instantiate the metadata class and store statistics
            self.writeops_stats[fname] = WriteOp(i, fname, self.file_size, self.file_type)

            try:
                write_start = time.time()
                flush(cp, fname, self.flush_size, self.flush_time)             # This is the actual write function
                write_end = time.time()
            except Exception as err:
                self.writeops_stats[fname].set_error(err)
                self.log.write("error", "Error while writing "+fname)
                self.log.write("error", fname+": "+str(err))
                print "\t!error while writing "+fname
                continue
            else:
                self.writeops_stats[fname].set_success()
                self.writeops_stats[fname].set_performance(write_start, write_end)      # Store metadata on performance
                self.writeops_stats[fname].set_source_md5(cp)                           # Store metadata for sanity check
                # Write on the log about performance
                self.log.write("performance", self.writeops_stats[fname].performance_output_for_logging(), write_timestamp=False)            

            # Sleep time, if specified
            time.sleep(self.inter_time)
            print i, fname
        self.log.write("info", "End of write operations")

        # If you enabled the sanity check
        if (self.check_data):
            self.run_sanity_check()
        
        # If you enabled the push-to-monitoring capability
        if (self.to_grafana):
            self.push_to_grafana()

        # Goodbye
        self.log.write("info", "End of experiment")
        self.log.close()


    # Execute sanity checks on written bytes
    def run_sanity_check(self):
        self.log.write("info", "Begin of sanity check...")
        self.log.write("consistency", "\t".join(["seq_no", "file_name", "matching", "source_md5", "disk_md5"]), write_timestamp=False)
        print "Sanity check."

        for f in sorted(self.writeops_stats.keys()):
            if (self.writeops_stats[f].error):
                self.log.write("error", "Unable to perform sanity check on "+f+" due to an error occurred while writing this file")
                continue
            self.writeops_stats[f].set_disk_md5()
            self.writeops_stats[f].compare_md5()
            self.log.write("consistency", self.writeops_stats[f].checksum_output_for_logging(), write_timestamp=False)
            if (not self.writeops_stats[f].md5_match):
                self.log.write("warning", f+" corrupted!")
        self.log.write("info", "End of sanity check")

    # Publish results on Grafana monitoring dashboard
    def push_to_grafana(self, namespace=GRAFANA_NAMESPACE):
        self.log.write("info", "Publishing results on Grafana...")
        self.log.write("info", "Grafana namespace: "+namespace)
        (hostname, port_no) = make_stats_and_publish(self)
        self.log.write("info", "Grafana host: "+hostname)
        self.log.write("info", "Grafana port: "+str(port_no))
        self.log.write("info", "End of publishing on Grafana")


#-------------------------------------------------------------------------------
# Flush write function
#    Input:
#       - payload: data to be written to disk
#       - fout: filename
#       - flush_size: number of bytes to be written for (flush+os.fsync) cycle
#       - flush_time: wait time in seconds between (flush+os.fsync) cycles
#-------------------------------------------------------------------------------
def flush(payload, fout, flush_size, flush_time):
    fwrite = open(fout, 'wb')
    while payload:
        #print "I have data to write", str(len(payload))
        fwrite.write(payload[0:flush_size])
        fwrite.flush()            
        os.fsync(fwrite.fileno())
        payload = payload[flush_size:]
        time.sleep(flush_time)
    fwrite.close()
    return


#-------------------------------------------------------------------------------
# Test specifications from the command line
#   Get test parameters from argument parser
#-------------------------------------------------------------------------------
# This is the argument parser from keyboard
#opt = process_opt()
#
#current_test = Flush(opt.file_no, opt.file_size, opt.file_type, opt.flush_size, opt.flush_time, opt.inter_time, opt.check_data, opt.out_dir, opt.machine_id, opt.to_grafana)
#current_test.run()


#-------------------------------------------------------------------------------
# Hard coded test specifications
#   Manually specify test parameters and run the test
#-------------------------------------------------------------------------------
#FILE_NO = 3            # Number of files to be generated
#FILE_SIZE = 1000000    # Size in Bytes of each file
#FILE_TYPE = "text"     # Refer to SUPPORTED_FILETYPES for supported files types (e.g., text, binary, ...)
#
#FLUSH_SIZE = 350000    # Number of bytes to be written for flush + os.fsync cycle
#FLUSH_TIME = 0.2       # Wait time in seconds between flush + os.fsync cycle
#
#INTER_TIME = 0.5       # Wait time in seconds between write operations of two files
#
#CHECK_DATA = True      # Do you want to run the sanity check?
#OUTPUT_DIR = '.'       # Specify the output directory
#MACHINE_ID = "local-test"    # Specify the machine ID
#TO_GRAFANA = True      # Do you want to publish results to Grafana?
#
#current_test = Flush(FILE_NO, FILE_SIZE, FILE_TYPE, FLUSH_SIZE, FLUSH_TIME, INTER_TIME, CHECK_DATA, OUTPUT_DIR, MACHINE_ID, TO_GRAFANA)
#current_test.run()


