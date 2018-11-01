#############
vLab IPAM API
#############

This service replaces the existing static gateway used in vLab.

The goal of this service is to make it easier for users to access their lab
by removing the need for the jumpbox. This is achieved by exposing a RESTful API
on the gateway that can dynamically port-forward through the NAT firewall that
runs on the gateway. Additionally, vLab clients can leverage this API to programmically
*connect* users to a given resource. For example the vLab CLI client can potentially:

1. Expose an interface like ``vlab connect windows --name <name of instance> --protocol=RDP``
#. Call the main vLab server to *get the IP of the gateway*
#. Call the API on the gateway to *get the port* that maps to the specific component and protocol
#. Evoke an application *on the user's machine* that understands the specific protocol, and pre-populate the connection information.

Clients can also programmically create the port forwarding rules upon component
creation. This would remove the need for users to manually port forwarding
rules, but clients should not prevent users from inputting their own port forwarding
rules.

Background Services
###################

The IPAM service has two background processes:

vlab-worker
***********

Periodically pings IPs stored in the IPAM database. This allows the service to
identify "bad records" and relay that information to the user.

vlab-log-sender
***************

Forwards firewall logs to a remote server. The default iptables config will
log every time a package is FORWARDed. By forwarding the logs for remote processing,
admins of vLab can answer business questions like, *"Do they use that resource?"*
