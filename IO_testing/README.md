# IO_testing


**DISCLAIMER** --- 
This is currently work-in-progress.
Updates, fixes, and improvements are on the way. Please also consider to read the documentation details and the comments available in scripts as a complement to this read-me file.

----
## what is IO_testing?
IO_testing is a set of IPython Notebooks and python scripts to execute tests on the storage infrastructure from Jupyter Notebooks. 

The scripts contained in this repository are intended to be executed unattended and from multiple test boxes to contrast different configurations and potentially run regression tests.


----
## configuration
The scripts here provided are working out-of-the-box. They are all self-contained and there are no dependencies to be satisfied. 

Given their IO testing nature, they need to be granted permission for reading/writing to disk.

It is also **highly recommended** to follow a precise directory tree in order to easily distinguish between results produced by different machines. The bash script *setup.sh* provides more insights on this and can be executed to automatically configure the local environment for running tests -- i.e., clone the git repository and setup the folder tree. 


----
## usage
The main notebook responsible of the orchestration of all tests is *test_orchestrator.ipynb*. It relies on external python scripts to actually run the tests (e.g., *test_write.py*, *test_flush.py*, *test_append.py*).
Please, refer to *test_orchestrator.ipynb* for more details on the tests and on the parameters.

To run the tests, it is enough to execute the *test_orchestrator.ipynb* notebook, eventually customizing the experiment parameters and the output folder. Please refer to the guide provided 
in *test_orchestrator.ipynb* for more details.



    .
    |__ ENTF                    # Enrico's Notebook Testing Framework
    |   |__ $hostname           # Identifier for the box where experiments are executed
    |       |__ workdir         # Folder where to put output files and logs
    |       |__ entf            # Clone of the git repository
    |           |  README.md
    |           |  LICENSE
    |           |__ IO_testing  # This script sits here (together will all other scripts needed to run the experiments)
                                # The default output directory for test_orchestrator.ipynb is '../../workdir'

