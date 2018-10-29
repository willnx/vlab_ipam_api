# -*- coding: UTF-8 -*-
"""A suite of unit tests for the vlab_ipam_api.lib.firewall module"""
import textwrap
import unittest
from unittest.mock import patch, MagicMock, mock_open

from vlab_ipam_api.lib import firewall


class TestFirewallInternals(unittest.TestCase):
    """A suite of test cases for the FireWall internal methods"""

    def test_init(self):
        """A simple test to verify we can initialize the FireWall object"""
        fw = firewall.FireWall()

        self.assertTrue(hasattr(fw, '_rlock'))

    def test_with(self):
        """FireWall support use of the with statement"""
        fake_rlock = MagicMock()
        fw = firewall.FireWall()
        fw._rlock = fake_rlock

        with fw:
            pass

        self.assertEqual(fake_rlock.acquire.call_count, 1)
        self.assertEqual(fake_rlock.release.call_count, 1)

    def test_prettify_nat_output(self):
        """``_prettify_nat_output`` parses the raw text into a usable data structure"""
        example = """\
        Chain PREROUTING (policy ACCEPT)
        num  target     prot opt source               destination
        1    DNAT       tcp  --  0.0.0.0/0            0.0.0.0/0            tcp dpt:6000 to:192.168.1.2:22
        """

        fw = firewall.FireWall()
        output = fw._prettify_nat_output(textwrap.dedent(example))
        expected = {'1': {'conn_port': 6000,
                          'target_addr': '192.168.1.2',
                          'target_port': 22}}

        self.assertEqual(output, expected)

    def test_prettify_filter_output(self):
        """``_prettify_filter_output`` parses the raw text into a usable data structure"""
        example = """\
        Chain FORWARD (policy ACCEPT)
        num  target     prot opt source               destination
        1    LOG        all  --  0.0.0.0/0            0.0.0.0/0            LOG flags 0 level 4
        2    ACCEPT     all  --  0.0.0.0/0            0.0.0.0/0
        3    ACCEPT     tcp  --  0.0.0.0/0            192.168.1.2          tcp dpt:22
        """

        fw = firewall.FireWall()
        output = fw._prettify_filter_output(textwrap.dedent(example))
        expected = {'3': {'target_addr': '192.168.1.2', 'target_port': 22}}


        self.assertEqual(output, expected)


# Mock away run_cmd in every test case
@patch('vlab_ipam_api.lib.firewall.run_cmd')
class TestFireWall(unittest.TestCase):
    """A suite of test cases for the FireWall object"""

    @classmethod
    def setUp(cls):
        """Runs before every test case"""
        cls.fw = firewall.FireWall()

    @classmethod
    def tearDown(cls):
        """Runs after every test case"""
        del cls.fw

    def test_delete_rule_value_error(self, fake_run_cmd):
        """``delete_rule`` raises ValueError is supplied table is not supported"""
        with self.assertRaises(ValueError):
            self.fw.delete_rule(rule_id=23432, table='NoTable')

    def test_delete_rule_nat(self, fake_run_cmd):
        """``delete_rule`` runs the correct syntax to remove a rule by ID from iptables from the nat table"""
        self.fw.delete_rule(rule_id=9001, table='nat')

        args, _ = fake_run_cmd.call_args

        syntax_sent = args[0]
        expected = 'iptables -t nat -D PREROUTING 9001'

        self.assertEqual(syntax_sent, expected)

    def test_delete_rule_filter(self, fake_run_cmd):
        """``delete_rule`` runs the correct syntax to remove a rule by ID from iptables from the filter table"""
        self.fw.delete_rule(rule_id=9001, table='filter')

        args, _ = fake_run_cmd.call_args

        syntax_sent = args[0]
        expected = 'iptables -t filter -D FORWARD 9001'

        self.assertEqual(syntax_sent, expected)

    def test_save_rules_file(self, fake_run_cmd):
        """``save_rules`` persists the firewall rules to disk"""
        fake_result = MagicMock()
        fake_result.stdout = 'HelloWorld'
        with patch('builtins.open', mock_open()) as mocked_file:
            self.fw.save_rules()

        args, _ = mocked_file.call_args
        the_file, mode = args
        expected_file = '/etc/iptables/rules.v4'
        expected_mode = 'w'

        self.assertEqual(the_file, expected_file)
        self.assertEqual(mode, expected_mode)

    def test_save_rules_cmd(self, fake_run_cmd):
        """``save_rules`` obtains an accurate list of firewall rules"""
        fake_result = MagicMock()
        fake_result.stdout = 'HelloWorld'
        with patch('builtins.open', mock_open()) as mocked_file:
            self.fw.save_rules()

        args, _ = fake_run_cmd.call_args
        save_syntax = args[0]
        expected_syntax = 'sudo iptables-save'

        self.assertEqual(save_syntax, expected_syntax)

    def test_show_nat(self, fake_run_cmd):
        """``show`` returns parsed output for the nat table by default"""
        fake_prettify_nat_output = MagicMock()
        fake_prettify_nat_output.return_value = {'woot' : True}
        self.fw._prettify_nat_output = fake_prettify_nat_output

        output = self.fw.show(table='nat')
        expected = {'woot': True}

        self.assertEqual(output, expected)

    def test_show_nat_raw(self, fake_run_cmd):
        """``show`` returns the raw output when defining the format param for the nat table"""
        self.fw._prettify_nat_output = MagicMock()
        fake_result = MagicMock()
        fake_result.stdout = 'woot'
        fake_run_cmd.return_value = fake_result

        output = self.fw.show(table='nat',format='raw')
        expected = 'woot'

        self.assertEqual(output, expected)

    def test_show_filter(self, fake_run_cmd):
        """``show`` returns parsed output for the filter table by default"""
        fake_prettify_filter_output = MagicMock()
        fake_prettify_filter_output.return_value = {'woot' : True}
        self.fw._prettify_filter_output = fake_prettify_filter_output

        output = self.fw.show(table='filter')
        expected = {'woot': True}

        self.assertEqual(output, expected)

    def test_show_filter_raw(self, fake_run_cmd):
        """``show`` returns the raw output when defining the format param for the filter table"""
        self.fw._prettify_filter_output = MagicMock()
        fake_result = MagicMock()
        fake_result.stdout = 'woot'
        fake_run_cmd.return_value = fake_result

        output = self.fw.show(table='filter',format='raw')
        expected = 'woot'

        self.assertEqual(output, expected)

    def test_show_value_error(self, fake_run_cmd):
        """``show`` raises ValueError if supplied with a bad table value"""
        with self.assertRaises(ValueError):
            self.fw.show(table='NoTable')

    def test_find_rule_filter(self, fake_run_cmd):
        """``find_rule``returns the rule id when found in filter table"""
        self.fw.show = MagicMock()
        self.fw.show.return_value = {'3' : {'target_addr': '1.1.1.1', 'target_port': '9001'}}

        output = self.fw.find_rule(target_port='9001',
                                   target_addr='1.1.1.1',
                                   table='filter')
        expected = '3'

        self.assertEqual(output, expected)

    def test_find_rule_nat(self, fake_run_cmd):
        """``find_rule``returns the rule id when found in the nat table"""
        self.fw.show = MagicMock()
        self.fw.show.return_value = {'3' : {'target_addr': '1.1.1.1', 'target_port': '9001', 'conn_port': '5632'}}

        output = self.fw.find_rule(target_port='9001',
                                   target_addr='1.1.1.1',
                                   table='nat',
                                   conn_port='5632')
        expected = '3'

        self.assertEqual(output, expected)

    def test_find_rule_nat_value_error(self, fake_run_cmd):
        """``find_rule`` raises ValueError is not supplied with param conn_port for the nat table"""
        self.fw.show = MagicMock()
        self.fw.show.return_value = {'3' : {'target_addr': '1.1.1.1', 'target_port': '9001', 'conn_port': '5632'}}

        with self.assertRaises(ValueError):
            self.fw.find_rule(target_port='9001',
                              target_addr='1.1.1.1',
                              table='nat')

    def test_find_rule_runtime_error(self, fake_run_cmd):
        """``find_rule`` raises RuntimeError if no matching rule is found"""
        self.fw.show = MagicMock()
        self.fw.show.return_value = {'3' : {'target_addr': '1.1.1.1', 'target_port': '9001', 'conn_port': '5632'}}

        with self.assertRaises(RuntimeError):
            self.fw.find_rule(target_port='99',
                              target_addr='1.2.3.4',
                              table='filter')

    def test_prerouting_id(self, fake_run_cmd):
        """``prerouting`` creates returns the ID upon success"""
        self.fw.find_rule = MagicMock()
        self.fw.find_rule.return_value = '8'

        output = self.fw.prerouting(conn_port='8965', target_addr='5.2.3.2', target_port='22')
        expected = '8'

        self.assertEqual(output, expected)

    def test_prerouting_cmd(self, fake_run_cmd):
        """``prerouting`` creates the correct rule in iptables"""
        self.fw.find_rule = MagicMock()
        self.fw.find_rule.return_value = '8'

        self.fw.prerouting(conn_port='8965', target_addr='5.2.3.2', target_port='22')
        args, _ = fake_run_cmd.call_args
        syntax_sent = args[0]
        expected_syntax = 'sudo iptables -A PREROUTING -t nat -i ens160 -p tcp --dport 8965 -j DNAT --to 5.2.3.2:22'

        self.assertEqual(syntax_sent, expected_syntax)

    def test_prerouting_runtime_error(self, fake_run_cmd):
        """``prerouting`` raises RuntimeError if it's unable to find the rule id for a newly created rule"""
        self.fw.find_rule = MagicMock()
        self.fw.find_rule.side_effect = [RuntimeError('doh')]

        with self.assertRaises(RuntimeError):
            self.fw.prerouting(conn_port='8965', target_addr='5.2.3.2', target_port='22')

    def test_forward_id(self, fake_run_cmd):
        """``forward`` returns the rule id of the newly created iptables rule"""
        self.fw.find_rule = MagicMock()
        self.fw.find_rule.return_value = '7'

        output = self.fw.forward(target_port='8965', target_addr='1.12.1.2')
        expected = '7'

        self.assertEqual(output, expected)

    def test_forward_cmd(self, fake_run_cmd):
        """``forward`` creates the correct rule in iptables"""
        self.fw.find_rule = MagicMock()
        self.fw.find_rule.return_value = '7'

        self.fw.forward(target_port='8965', target_addr='1.12.1.2')

        args, _ = fake_run_cmd.call_args
        syntax_sent = args[0]
        expected_syntax = 'sudo iptables -A FORWARD -p tcp -d 1.12.1.2 --dport 8965 -j ACCEPT'

        self.assertEqual(syntax_sent, expected_syntax)

    def test_forward_runtime_error(self, fake_run_cmd):
        """``forward`` raises RuntimeError if it cannot find the rule id of the newly created rule"""
        self.fw.find_rule = MagicMock()
        self.fw.find_rule.side_effect = [RuntimeError('doh')]

        with self.assertRaises(RuntimeError):
            self.fw.forward(target_port='8965', target_addr='1.12.1.2')

    def test_map_port_ok(self, fake_run_cmd):
        """``map_port`` returns a Tuple upon success"""
        self.fw.forward = MagicMock()
        self.fw.forward.return_value = '9'
        self.fw.prerouting = MagicMock()
        self.fw.prerouting.return_value = '23'
        self.fw.save_rules = MagicMock()

        forward_id, prerouting_id = self.fw.map_port(conn_port=5698,
                                                     target_port=22,
                                                     target_addr='8.6.5.3')
        expected = ('9', '23')

        self.assertEqual((forward_id, prerouting_id), expected)

    def test_map_port_saves(self, fake_run_cmd):
        """``map_port`` auto-saves the rules upon success"""
        self.fw.forward = MagicMock()
        self.fw.forward.return_value = '9'
        self.fw.prerouting = MagicMock()
        self.fw.prerouting.return_value = '23'
        self.fw.save_rules = MagicMock()

        self.fw.map_port(conn_port=5698,
                         target_port=22,
                         target_addr='8.6.5.3')

        self.assertEqual(self.fw.save_rules.call_count, 1)

    def test_map_port_locks(self, fake_run_cmd):
        """``map_port`` locks the object while executing"""
        self.fw.forward = MagicMock()
        self.fw.forward.return_value = '9'
        self.fw.prerouting = MagicMock()
        self.fw.prerouting.return_value = '23'
        self.fw.save_rules = MagicMock()
        self.fw._rlock = MagicMock()

        self.fw.map_port(conn_port=5698,
                         target_port=22,
                         target_addr='8.6.5.3')

        self.assertEqual(self.fw._rlock.acquire.call_count, 1)

    def test_map_port_undo(self, fake_run_cmd):
        """``map_port`` deletes the FORWARD rule if it fails to also create the PREROUTING rule"""
        self.fw.forward = MagicMock()
        self.fw.forward.return_value = '9'
        self.fw.prerouting = MagicMock()
        self.fw.prerouting.side_effect = [RuntimeError('testing')]
        self.fw.save_rules = MagicMock()
        self.fw.delete_rule = MagicMock()

        try:
            self.fw.map_port(conn_port=5698,
                             target_port=22,
                             target_addr='8.6.5.3')
        except Exception:
            pass

        self.assertEqual(self.fw.delete_rule.call_count, 1)



if __name__ == '__main__':
    unittest.main()
