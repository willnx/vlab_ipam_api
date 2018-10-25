########################
Making the vLab Firewall
########################

This directory contains automation for converting an Ubuntu 18.04 server with
two NICs into a vLab firewall.


configure.sh
============

The ``configure.sh`` file needs to be copied onto a fresh deployment of Ubuntu
18.04 that has two NICs. Once the file is copied onto the new machine make it
executable with ``chmod +x configure.sh`` then run the script as root (or via
``sudo``).

As the script runs, it will prompt you a few times for information. Accepting
the defaults is normally the best options. When the script completes successfully,
it will shut down the machine (so you can make an OVA or some other sort of VM
template from it).
