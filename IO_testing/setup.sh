#!/bin/bash

# Check whether the user provided a valid machine name
if [ $1 == "" ]; then
	echo -e "Usage: bash $0 MACHINE_NAME"
	exit
fi

# Sanitize input
hostname=${1//_/}										# Strip underscores
hostname=${hostname// /_}								# Replace whitespaces with underscore
hostname=${hostname//[^a-zA-Z0-9_]/}					# Remove non-alphanumeric
hostname=`echo $hostname | tr '[:upper:]' '[:lower:]'`	# Shift to lowercase

# Set up directory tree
echo -e "Setting up folders..."
echo -e "Sanitized machine name: "$hostname
mkdir -p ./ENTF/$hostname/workdir

# Clone git repository
echo -e "Setting up folders..."
git clone git@github.com:cernbox/entf.git ./ENTF/$hostname

echo -e "Done!"
