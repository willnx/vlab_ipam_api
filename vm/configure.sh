#!/bin/bash
#
# This script will take a basic Ubuntu 18.04 server with 2 NICs and configure
# the system to be a vLab Firewall.
#
# You must run this script as root, or with sudo.

# Exit the moment any single command fails
set -e

setup_sysctls () {
  # This function configures all the sysctls needed to turn Ubuntu into a firewall
  echo "Configuring systcls"
  echo "net.ipv4.ip_forward = 1" >> /etc/sysctl.conf
  echo "net.core.somaxconn=1024" >> /etc/sysctl.conf
}

setup_logrotate () {
  # Aggressivetly rotate the logs to avoid filling the root partition
  echo "\
# see "man logrotate" for details
# rotate log files every day
daily

# use the syslog group by default, since this is the owning group
# of /var/log/syslog.
su root syslog

# keep only yesterday's log
rotate 1

# create new (empty) log files after rotating old ones
create

# uncomment this if you want your log files compressed
compress

# packages drop log rotation information into this directory
include /etc/logrotate.d

# no packages own wtmp, or btmp -- we'll rotate them here
/var/log/wtmp {
    missingok
    monthly
    create 0664 root utmp
    rotate 1
}

/var/log/btmp {
    missingok
    monthly
    create 0660 root utmp
    rotate 1
}

# system-specific logs may be configured here
" > /etc/logrotate.conf
}

install_deb_deps () {
  # Install all the libs needed in Ubuntu, like OpenSSL and what-not
  echo "Installing dependancies"
  apt-get update
  apt-get upgrade -y
  apt-get install -y openssl libssl-dev python3 python3-dev gcc python3-pip \
                     isc-dhcp-server open-vm-tools openssh-server iptables-persistent \
                     postgresql postgresql-contrib libpcre3 libpcre3-dev chrony bind9 \
                     libpq-dev
}

setup_nics () {
  # This function will define the Netplan yaml file for the NICs
  echo "Configuring NIC settings"
echo "\
network:
  version: 2
  ethernets:
    ens160:
      dhcp4: yes
      dhcp6: yes
    ens192:
      addresses: [192.168.1.1/24]
" > /etc/netplan/01-netcfg.yaml
}

setup_dhcp () {
  # This function configures the DHCP server out the LAN interface
  echo "Configuring DHCP server settings"
echo '
# dhcpd.conf configuration file

option domain-name "vlab.local";
option domain-name-servers 192.168.1.1;

default-lease-time 600;
max-lease-time 7200;

# No Dynamic DNS for your vlab
ddns-update-style none;

# This is the authoritative DHCP server for your vLab
authoritative;

subnet 192.168.1.0 netmask 255.255.255.0 {
  range 192.168.1.150 192.168.1.219;
  option routers 192.168.1.1;
}
' > /etc/dhcp/dhcpd.conf

echo "\
# Defaults for isc-dhcp-server (sourced by /etc/init.d/isc-dhcp-server)

# Path to dhcpd's config file (default: /etc/dhcp/dhcpd.conf).
#DHCPDv4_CONF=/etc/dhcp/dhcpd.conf
#DHCPDv6_CONF=/etc/dhcp/dhcpd6.conf

# Path to dhcpd's PID file (default: /var/run/dhcpd.pid).
#DHCPDv4_PID=/var/run/dhcpd.pid
#DHCPDv6_PID=/var/run/dhcpd6.pid

# Additional options to start dhcpd with.
#       Don't use options -cf or -pf here; use DHCPD_CONF/ DHCPD_PID instead
#OPTIONS=""

# On what interfaces should the DHCP server (dhcpd) serve DHCP requests?
#       Separate multiple interfaces with spaces, e.g. \"eth0 eth1\".
INTERFACESv4=\"ens192\"
INTERFACESv6=\"ens192\"
" > /etc/default/isc-dhcp-server

  echo "Enabling DHCP server to start on boot"
  systemctl enable isc-dhcp-server
}

setup_nat () {
  # This function will configure IPTables to turn this box into a NATing firewall
  echo "Setting up NAT"
  # delete any existing rules/chains
  iptables --flush
  iptables --table nat --flush
  iptables --delete-chain
  iptables --table nat --delete-chain

  # Setup IP FORWARDing and Masquerading
  iptables --table nat --append POSTROUTING --out-interface ens160 -j MASQUERADE
  iptables --append FORWARD --in-interface ens192 -j ACCEPT
  iptables -I FORWARD 1 -j LOG

  # Default to drop attempts to connect to this Firewall
  iptables --policy INPUT DROP
  # But accept standard Linux TCP port range for client-initiated connections
  # sysctl net.ipv4.ip_local_port_range
  iptables -A INPUT -p tcp --match multiport --dports 32768:60999 -j ACCEPT
  # No IPv6 support
  ip6tables --policy INPUT DROP
  ip6tables --policy FORWARD DROP

  # Ensure processes can talk over loopback
  iptables --append INPUT -i lo -j ACCEPT
  iptables --append OUTPUT -o lo -j ACCEPT

  # Enable local DNS queries
  iptables -A OUTPUT -p udp --dport 53 -j ACCEPT
  iptables -A INPUT -p udp --sport 53 -j ACCEPT
  iptables -A OUTPUT -p tcp --dport 53 -j ACCEPT
  iptables -A INPUT -p tcp --sport 53 -j ACCEPT

  # Enable DNS queries from remote VMs
  iptables -A INPUT -p udp -m udp --dport 53 -j ACCEPT
  iptables -A OUTPUT -p udp -m udp --sport 53 -j ACCEPT

  # Enable incoming SSH access
  iptables -A INPUT -p tcp --dport 22 -m conntrack --ctstate NEW,ESTABLISHED -j ACCEPT
  iptables -A OUTPUT -p tcp --sport 22 -m conntrack --ctstate ESTABLISHED -j ACCEPT

  # Enable incoming access to the vLab RESTful API
  iptables -A INPUT -p tcp --dport 443 -m conntrack --ctstate NEW,ESTABLISHED -j ACCEPT
  iptables -A OUTPUT -p tcp --sport 443 -m conntrack --ctstate NEW,ESTABLISHED -j ACCEPT

  # Enable outbound HTTP/S for updates
  iptables -A OUTPUT -p tcp --dport 443 -m state --state NEW,ESTABLISHED -j ACCEPT
  iptables -A INPUT -p tcp --sport 443 -m state --state ESTABLISHED -j ACCEPT
  iptables -A OUTPUT -p tcp --dport 80 -m state --state NEW,ESTABLISHED -j ACCEPT
  iptables -A INPUT -p tcp --sport 80 -m state --state ESTABLISHED -j ACCEPT

  # Enable NTP
  iptables -A OUTPUT -p udp --dport 123 -j ACCEPT
  iptables -A INPUT -p udp --sport 123 -j ACCEPT

  # Enable ICMP (aka ping)
  iptables -A INPUT -p icmp --icmp-type echo-request -j ACCEPT
  iptables -A INPUT -p icmp --icmp-type echo-reply -j ACCEPT
  iptables -A OUTPUT -p icmp --icmp-type echo-reply -j ACCEPT

  # Apply config
  iptables-save > /etc/iptables/rules.v4
  ip6tables-save > /etc/iptables/rules.v6
}

setup_cert () {
  # This function will create a self-signed TLS cert
  echo "Creating self-signed cert"
  openssl req -x509 -nodes -days 900 -newkey rsa:2048 -keyout /etc/vlab/server.key -out /etc/vlab/server.crt
}

setup_webapp () {
  echo "Installing IPAM software"
  # This function installs the RESTful API for managaing the vLab Firewall
  pip3 --trusted-host pypi.org --trusted-host files.python.org install vlab-ipam-api
  ln -s /usr/local/lib/python3.6/dist-packages/vlab_ipam_api/vlab-ipam.service /etc/systemd/system/vlab-ipam.service
  systemctl enable vlab-ipam
  ln -s /usr/local/lib/python3.6/dist-packages/vlab_ipam_api/vlab-worker.service /etc/systemd/system/vlab-worker.service
  systemctl enable vlab-worker
  ln -s /usr/local/lib/python3.6/dist-packages/vlab_ipam_api/vlab-log-sender.service /etc/systemd/system/vlab-log-sender.service
  systemctl enable vlab-log-sender
  ln -s /usr/local/lib/python3.6/dist-packages/vlab_ipam_api/vlab-ddns-updater.service /etc/systemd/system/vlab-ddns-updater.service
  systemctl enable vlab-ddns-updater
}

setup_sudo () {
  echo "Configuring sudo"
  # This function allows the vLab RESTful API to issue iptable commands as a
  # non-root user, which in turns enables the app to not run as root.
echo "
# Enable the vLAB APP to run as a non-root user
nobody ALL=NOPASSWD: /sbin/iptables
nobody ALL=NOPASSWD: /sbin/ip6tables
nobody ALL=NOPASSWD: /sbin/iptables-save

# Enable the vLAB server to automate the config
administrator ALL=(ALL) NOPASSWD:ALL
" > /etc/sudoers.d/vLabAPI
}

setup_db () {
  # This function configures the PostgreSQL database
echo "
adminpostgres postgres postgres
adminpostgres nobody   postgres
adminpostgres root     postgres
" >> /etc/postgresql/10/main/pg_ident.conf

sed -i -e 's/local   all             postgres                                peer/local   all             postgres                                peer map=adminpostgres/g' /etc/postgresql/10/main/pg_hba.conf

  systemctl restart postgresql
  createdb -U postgres vlab_ipam
  psql -U postgres -d vlab_ipam -c \
  "CREATE TABLE ipam(
    conn_port INT PRIMARY KEY NOT NULL,
    target_addr TEXT,
    target_port INT,
    target_name TEXT,
    target_component TEXT,
    routable  Boolean
  );
  CREATE USER readonly;
  ALTER USER readonly with encrypted password 'a';
  GRANT CONNECT ON DATABASE vlab_ipam TO readonly;
  ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT ON TABLES TO readonly;
  "
}

setup_rsyslog () {
  echo "Modifing rsyslog config"
  # This function changes the timestamp format used by rsyslog
sed -i -e 's/$ActionFileDefaultTemplate RSYSLOG_TraditionalFileFormat/#$ActionFileDefaultTemplate RSYSLOG_TraditionalFileFormat/g' /etc/rsyslog.conf
}

setup_ntp () {
  echo "Configuring NTP (chrony) settings"
  chown -R _chrony /etc/chrony
  echo '
# Welcome to the chrony config file. See chrony.conf(5) for more
# information about usable directives

# The "upstream" NTP server to sync from
server 1.us.pool.ntp.org

# Defeins NTP authentication file
keyfile /etc/chrony/chorny.keys

# Persist information about the system clock drift, so chrony can start making
# adjustments even before establishing a connection to an NTP server
driftfile /var/lib/chrony/chrony.drift

# Log file location
logdir /var/log/chrony

# Prevent bad estimates from upsetting the system clock
maxupdateskew 100.0

# Enable kernel synchronisation every 11 minutes of the real-time clock
rtcsync

# Allow chrony to step the clock massively within the first 5 updates. This
# enables chrony to fix the clock upon boot when the system clock is really
# off when compaired to the real time.
makestep 300 5

# Chrony defaults to using a random port for client updates. Setting it to the
# standard NTP port makes dealing with firewall easier because you only have to
# open the one single (well known) port for NTP
acquisitionport 123

# Let chrony also act as an NTP server for any client that can reach it over
# the network.
allow
' > /etc/chrony/chrony.conf
}

setup_dns () {
  echo "Setting up DNS (bind9)"
  echo '
// BIND9 DNS config -- overridden version of the default Debian config

options {
  forwarders {
    8.8.8.8;
  };

  // Only listen for DNS querys on the LAN and local networks
  // Implictly sets the allow-query to the same interfaces
  listen-on {
    127.0.0.1;
    192.168.1.1;
  };
  listen-on-v6 { ::1; };

  dnssec-validation no;
};
' > /etc/bind/named.conf
  systemctl disable systemd-resolved.service
}

setup_cms () {
  echo "Setting up configuration management"
  # Handle installing config management software
  # Add the repo's GPG key so updates work
  wget -O - https://repo.saltstack.com/apt/ubuntu/18.04/amd64/latest/SALTSTACK-GPG-KEY.pub | apt-key add -
  # Add the repo
  touch /etc/apt/sources.list.d/saltstack.list
  echo 'deb http://repo.saltstack.com/apt/ubuntu/18.04/amd64/latest bionic main' > /etc/apt/sources.list.d/saltstack.list
  # Install the software
  apt-get update && apt-get install -y salt-minion

  # Disable and remove old identity. The Gateway service will set the hostname
  # then re-enable it. This will make it so the minion ref and the owner of the
  # gateway coincide.
  systemctl disable salt-minion.service
  truncate -s0 /etc/salt/minion_id
}

clean_up () {
  # fix issue with different VMs getting same DHCP addr
  # https://github.com/chef/bento/issues/1062
  echo "" > /etc/machine-id
  # Remove any lingering junk and get the VM ready for cloning
  echo "Cleaning up junk"
  rm configure.sh
  echo "" > /var/log/lastlog
  history -c
}

add_envvars () {
  echo "Adding enviroment variables"
  # Set the nesseary enviroment variables now so replacing them later is easier
  echo "VLAB_LOG_TARGET=localhost:9092" >> /etc/environment
  echo "VLAB_URL=https://localhost" >> /etc/environment
  echo "PRODUCTION=false" >> /etc/environment
  echo "VLAB_DDNS_KEY=aabbcc" >> /etc/environment
  echo "VLAB_DDNS_ALGORITHM=HMAC-SHA512" >> /etc/environment
}

add_logsender_key () {
  echo "Creating logsender key file"
  # Enable automation to set encryption key
  echo "changeME" > /etc/vlab/log_sender.key
}

setup_etc () {
  # Make the /etc/vlab directory
  mkdir /etc/vlab
  chmod 700 /etc/vlab
}

main () {
  # Ties all the smaller functions together
  echo "Converting Ubuntu 18.04 server into vLab Firewall"
  setup_etc
  setup_sysctls
  setup_logrotate
  install_deb_deps
  setup_nics
  setup_nat
  setup_dhcp
  setup_cert
  setup_webapp
  setup_sudo
  add_envvars
  add_logsender_key
  setup_db
  setup_ntp
  setup_cms
  setup_dns
  clean_up
  echo "All done, shutting down machine (so you can convert it into a VM template)"
  shutdown -P now
}
main
