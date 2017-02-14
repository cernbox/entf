#!/bin/bash


#-------------------------------------------------------------------------------
#
### SETUP
#
# This script is responsible for setting up the local environment to run IO tests.
# It creates the required folder tree and clones the git repository containing the scripts.
#
# Given IO tests are expected to be executed in an unattended way and from 
# multiple test boxes, it is recommended to follow a strict nomenclature and 
# scheme on the directory tree used for experiments
#-------------------------------------------------------------------------------
# .
# |__ ENTF                    # Enrico's Notebook Testing Framework
# |   |__ $hostname           # Identifier for the box where experiments are executed
# |       |__ workdir         # Folder where to put output files and logs
# |       |__ entf            # Clone of the git repository
# |           |  README.md
# |           |  LICENSE
# |           |__ IO_testing  # This script sits here (together will all other scripts needed to run the experiments)
#                             # The default output directory for test_orchestrator.ipynb is '../../workdir'


# Check whether the user provided a valid machine name
if [ -z $1 ]; then
    echo -e "Usage: bash $0 HOSTNAME"
    exit
fi

# Sanitize input
hostname=${1//_/}					# Strip underscores
hostname=${hostname// /_}				# Replace whitespaces with underscore
hostname=${hostname//[^a-zA-Z0-9_]/}			# Remove non-alphanumeric
hostname=`echo $hostname | tr '[:upper:]' '[:lower:]'`	# Shift to lowercase


# Check if destination folder is already there
if [ -d ./ENTF/$hostname ]; then
    echo -e "ERROR: output folder already exists. Cannot continue."
    exit
fi


# Clone git repository
echo -e "Cloning GitHub repository..."
git clone https://github.com/cernbox/entf ./ENTF/$hostname/entf


# Set up directory tree
echo -e "\nSetting up folders..."
echo -e "Sanitized machine name: "$hostname
mkdir -p ./ENTF/$hostname/workdir


echo -e "Done!"



