#/usr/bin/bash

SRC_DIR="/cvmfs/sft.cern.ch/lcg/releases/ROOT/6.08.02-99084/x86_64-slc6-gcc49-opt/tutorials/math"
DST_DIR=${SRC_DIR##*/}

SUPPORTED=(C c cpp py)

echo "Starting..."
source /cvmfs/sft.cern.ch/lcg/views/LCG_87/x86_64-slc6-gcc49-opt/setup.sh
mkdir $DST_DIR 2>/dev/null


for cf in `ls $SRC_DIR`
do
	if [[ -f $SRC_DIR/$cf ]]; then
		ext=${cf##*.}
		if [[ "$ext" =~ ^(c|C|cpp|py)$ ]]; then
			echo "Processing: $SRC_DIR/$cf"
			cp $SRC_DIR/$cf ./$DST_DIR
			python converttonotebook.py $SRC_DIR/$cf ./$DST_DIR
		else
			echo "Not supported: $cf"
		fi
	fi
done

