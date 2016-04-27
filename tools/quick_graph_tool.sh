#!/bin/bash

# CHECK IF PYTHON IS AVAILABLE
python --version 2>&1 >/dev/null
PYTHON_IS_AVAILABLE=$?
if [ $PYTHON_IS_AVAILABLE -ne 0 ]; then echo "ERROR: Python could not be found"; exit 1; fi

# INIT graph-tool PACKAGE
python -c "import pkgutil,sys;sys.exit(0 if pkgutil.find_loader('graph_tool') else 1)" 2>&1 >/dev/null
GRAPH_TOOL_INSTALLED=$?
if [ $GRAPH_TOOL_INSTALLED -ne 0 ]; then 
echo "DOWNLOADING graph-tool"
# CHECK COMPATABILITY
echo "[Root permissions required]"
sudo bash init_supgt.sh
fi
