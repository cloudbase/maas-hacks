This is a Ubuntu MaaS power template for VMWare Workstation / Fusion

On your host (Windows / Linux / OS X), run:

python vmrunapi.py

On the VM running MaaS:

Edit vmrunapi.template and replace the IP in vmrunapi_url with the URL of
your host's VMWare NAT interface.  

Edit install.sh and replace ~/maas with the path where MaaS is installed.

Run:

./install.sh

Start / restart MaaSm e.g.:

make run

