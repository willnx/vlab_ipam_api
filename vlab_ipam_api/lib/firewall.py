# -*- coding: UTF-8
"""
This module enables modifications to the Linux Netfilter firewall
"""
from threading import RLock

from vlab_ipam_api.lib.shell import run_cmd, CliResult
from vlab_ipam_api.lib.exceptions import CliError


class FireWall(object):
    """A thread-safe way to manipulate iptables

    If you need to perform several modifications to iptables, use a ``with``
    statement to prevent other threads from making conflicting changes in between
    the modifications you need to make.

    Example::

        firewall = FireWall()
        with firewall:
            firewall.delete_rule(rule_id, table='nat')
            firewall.delete_rule(other_id, table='filter')
    """

    def __init__(self):
        # This lock can be acquired multiple times by the same thread that owns
        # it without blocking. This comes with the responsibility of that thread
        # to also release the lock for every call to acquire it. Thankfully
        # Python makes this easy via Context Managers (i.e. ``with`` statement)
        # (http://book.pythontips.com/en/latest/context_managers.html)
        self._rlock = RLock()

    def __enter__(self):
        """Enable use of the ``with`` statement to serialize changes to iptables"""
        self._rlock.acquire()

    def __exit__(self, exc_type, exc_value, the_traceback):
        self._rlock.release()

    def map_port(self, conn_port, target_port, target_addr):
        """Create a port mapping rule to forward packets past the NAT firewall

        :Returns: Tuple

        :param conn_port: The TCP port on the local system user's will connect to
        :type conn_port: Integer

        :parm target_port: The TCP port on the remote machines to map to.
        :type target_port: Integer

        :param target_addr: The IP address of the remote machien to map to.
        :type target_addr: String
        """
        with self:
            forward_id = self.forward(target_port=target_port, target_addr=target_addr)
            try:
                prerouting_id = self.prerouting(conn_port=conn_port, target_port=target_port, target_addr=target_addr)
            except (CliError, RuntimeError) as doh:
                self.delete_rule(forward_id, table='filter')
                raise doh
            else:
                self.save_rules()
                return forward_id, prerouting_id

    def forward(self, target_port, target_addr):
        """Create the FORWARD rule in the "filter" table

        :Returns: Integer - Rule ID

        :parm target_port: The TCP port on the remote machines to map.
        :type target_port: Integer

        :param target_addr: The IP address of the remote machien to map to.
        :type target_addr: String
        """
        run_cmd('sudo iptables -A FORWARD -p tcp -d {} --dport {} -j ACCEPT'.format(target_addr, target_port))
        try:
            forward_id = self.find_rule(target_port, target_addr, table='filter')
        except RuntimeError:
            raise RuntimeError('Unable to find newly created FORWARD rule for {}:{}'.format(target_addr, target_port))
        else:
            return forward_id

    def prerouting(self, conn_port, target_port, target_addr):
        """Create the PREROUTING rule in the "nat" table

        :Returns: Integer - Rule ID

        :parm conn_port: The TCP port on the local machine to map.
        :type target_port: Integer

        :parm target_port: The TCP port on the remote machines to map.
        :type target_port: Integer

        :param target_addr: The IP address of the remote machien to map to.
        :type target_addr: String
        """
        run_cmd('sudo iptables -A PREROUTING -t nat -i ens160 -p tcp --dport {} -j DNAT --to {}:{}'.format(conn_port, target_addr, target_port))
        try:
            prerouting_id = self.find_rule(target_port, target_addr, table='nat', conn_port=conn_port)
        except RuntimeError:
            raise RuntimeError('Unable to find newly created PERROUTING rule for port {} to {}:{}'.format(conn_port, target_addr, target_port))
        else:
            return prerouting_id

    def find_rule(self, target_port, target_addr, table, conn_port=None):
        """Iterate defines rules, and find the rule ID. Returns zero if no rule found.

        :Returns: Integer

        :param target_port: The TCP port on the remote machines to map to.
        :type target_port: Integer

        :param target_addr: The IP address of the remote machien to map to.
        :type target_addr: String

        :param table: The specific table within iptables to delete a rule from.
                      Must be either 'filter' or 'nat'.
        :type table: String

        :conn_port: The local port that maps to a remote port. Used for NAT table lookups.
        :conn_port: Integer
        """
        if table.lower() == 'nat' and conn_port is None:
            error = "Must supply conn_port when looking up NAT rules"
            raise ValueError(error)
        rules = self.show(table=table)
        current_id = 0
        for rule_id, info in rules.items():
            if info['target_addr'] == target_addr and info['target_port'] == target_port:
                if conn_port == info.get('conn_port', None):
                    current_id = rule_id
                    break
        if not current_id:
            raise RuntimeError('Unable to find iptable rule')
        else:
            return current_id

    def delete_rule(self, rule_id, table):
        """Destroy a port mapping rule

        :Returns: None

        :param rule_id: The rule by number to delete in the supplied table
        :type rule_id: String

        :param table: The specific table within iptables to delete a rule from.
                      Must be either 'filter' or 'nat'.
        :type table: String
        """
        with self:
            if table.lower() == 'nat':
                chain = 'PREROUTING'
            elif table.lower() == 'filter':
                chain = 'FORWARD'
            else:
                raise ValueError('Param "table" must be either "nat" or "filter", supplied: {}'.format(table))
            run_cmd('iptables -t {} -D {} {}'.format(table, chain, rule_id))

    def save_rules(self):
        """Make the current firewall config persist reboots"""
        with self:
            result = run_cmd('sudo iptables-save')
            with open('/etc/iptables/rules.v4', 'w') as the_file:
                the_file.write(result.stdout)

    def show(self, table='filter', format='parsed'):
        """Display configured firewall rules for a given table

        :Returns: String or Dictionary

        :Raises: ValueError

        :param table: The specific iptable table to view, must be either 'filter' or 'nat'
        :type table: String, default "filter"

        :param format: Set to 'raw' for unprocess output, or 'parsed' for just the important stuff
        :type format: String, default 'parsed'
        """
        with self:
            if table.lower() == 'nat':
                result = run_cmd('sudo iptables --numeric -L PREROUTING -t nat --line-numbers')
                if format.lower() == 'parsed':
                    return self._prettify_nat_output(result.stdout)
                else:
                    return result.stdout
            elif table.lower() == 'filter':
                result = run_cmd('sudo iptables --numeric -L FORWARD -t filter --line-numbers')
                if format.lower() == 'parsed':
                    return self._prettify_filter_output(result.stdout)
                else:
                    return result.stdout
            else:
                raise ValueError('Param "table" must be either "nat" or "filter", supplied: {}'.format(table))

    def _prettify_nat_output(self, output):
        """Takes the ``iptables`` output, and turns it into a user-friendly object

        :Returns: Dictionary

        :param output: The raw output from the ``iptables`` command
        :type output: String
        """
        # Example of output:
        # Chain PREROUTING (policy ACCEPT)
        # num  target     prot opt source               destination
        # 1    DNAT       tcp  --  0.0.0.0/0            0.0.0.0/0            tcp dpt:6000 to:192.168.1.2:22
        rows = output.split('\n')[2:]
        rules = {}
        for row in rows:
            if not row:
                # trailing newline chars...
                continue
            columns = row.split()
            rid = columns[0]
            conn_port = columns[-2].split(':')[-1]
            target = columns[-1]
            _, target_ip, target_port = target.split(':')
            rules[rid] = {'conn_port': int(conn_port),
                         'target_addr': target_ip,
                         'target_port': int(target_port),
                        }
        return rules

    def _prettify_filter_output(self, output):
        """Takes the ``iptables`` output, and turns it into a user-friendly object

        :Returns: Dictionary

        :param output: Th raw output from the ``iptables`` command
        :type output: String
        """
        # Example of output:
        # Chain FORWARD (policy ACCEPT)
        # num  target     prot opt source               destination
        # 1    LOG        all  --  0.0.0.0/0            0.0.0.0/0            LOG flags 0 level 4
        # 2    ACCEPT     all  --  0.0.0.0/0            0.0.0.0/0
        # 3    ACCEPT     tcp  --  0.0.0.0/0            192.168.1.2          tcp dpt:22
        rows = output.split('\n')[2:]
        rules = {}
        for row in rows:
            if not row:
                continue
            columns = row.split()
            rid = columns[0]
            if rid in ('1', '2'):
                # default rules; skip
                continue
            target_ip = columns[5]
            target_port = columns[7].split(':')[-1]
            rules[rid] = {'target_addr': target_ip, 'target_port': int(target_port)}
        return rules
