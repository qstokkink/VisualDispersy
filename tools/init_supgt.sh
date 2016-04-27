# READ THIS:
# THIS FILE COVERS THE INSTALLATION OF THE python-graph-tool PACKAGE
# IT IS CALLED THROUGH quick_graph_tool.sh AND SHOULD NOT BE CALLED DIRECTLY

# CHECK IF THE OS VERSION IS SUPPORTED BY graph-tool
# AND TEMPORARILY ADD RESPECTIVE REPOSITORIES
OSDISTRO=`lsb_release --codename | cut -f2`
if [ "$OSDISTRO" = "stretch" ] || [ "$OSDISTRO" = "sid" ]
then 
echo "ADDING DEBIAN REPOSITORIES"
echo "deb http://downloads.skewed.de/apt/$OSDISTRO $OSDISTRO main" >> /etc/apt/sources.list.d/graph-tool.sources.list
echo "deb-src http://downloads.skewed.de/apt/$OSDISTRO $OSDISTRO main" >> /etc/apt/sources.list.d/graph-tool.sources.list
elif [ "$OSDISTRO" = "trusty" ] || [ "$OSDISTRO" = "vivid" ] || [ "$OSDISTRO" = "wily" ]
then
echo "ADDING UBUNTU REPOSITORIES"
echo "deb http://downloads.skewed.de/apt/$OSDISTRO $OSDISTRO universe" >> /etc/apt/sources.list.d/graph-tool.sources.list
echo "deb-src http://downloads.skewed.de/apt/$OSDISTRO $OSDISTRO universe" >> /etc/apt/sources.list.d/graph-tool.sources.list
else echo "ERROR: Unsupported OS or OS distribution (see https://graph-tool.skewed.de/download#packages)"; exit 1
fi

# VERIFY INTEGRITY OF DOWNLOAD BY PUBKEY
gpg --keyring /etc/apt/trusted.gpg -k "98507F25" 2>&1 >/dev/null
KEY_KNOWN=$?
if [ $KEY_KNOWN -ne 0 ]; then apt-key adv --fetch-keys http://pgp.skewed.de:11371/pks/lookup?op=get\&search=0x612DEFB798507F25; fi

# FETCH FROM REPO
apt-get -qq update
apt-get -qq install python-graph-tool
rm /etc/apt/sources.list.d/graph-tool.sources.list
apt-get -qq update
