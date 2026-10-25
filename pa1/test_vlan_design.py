import ipaddress
import os
import tempfile
import unittest

import vlan_design


class TestParsing(unittest.TestCase):
    def test_parse_base_network_valid(self):
        net = vlan_design.parse_base_network("Base network: 10.10.0.0/16", 1)
        self.assertEqual(net, ipaddress.ip_network("10.10.0.0/16"))

    def test_parse_base_network_invalid_format(self):
        with self.assertRaises(vlan_design.NetworkInputError):
            vlan_design.parse_base_network("10.10.0.0/16", 1)

    def test_parse_base_network_invalid_cidr(self):
        with self.assertRaises(vlan_design.NetworkInputError):
            vlan_design.parse_base_network("Base network: not-an-ip", 1)

    def test_parse_department_line_valid(self):
        name, count = vlan_design.parse_department_line("Users,20", 2)
        self.assertEqual(name, "Users")
        self.assertEqual(count, 20)

    def test_parse_department_line_missing_comma(self):
        with self.assertRaises(vlan_design.NetworkInputError):
            vlan_design.parse_department_line("Users 20", 2)

    def test_parse_department_line_non_integer_count(self):
        with self.assertRaises(vlan_design.NetworkInputError):
            vlan_design.parse_department_line("Users,abc", 2)

    def test_parse_department_line_zero_count(self):
        with self.assertRaises(vlan_design.NetworkInputError):
            vlan_design.parse_department_line("Users,0", 2)

    def test_parse_department_line_negative_count(self):
        with self.assertRaises(vlan_design.NetworkInputError):
            vlan_design.parse_department_line("Users,-5", 2)

    def test_parse_department_line_empty_name(self):
        with self.assertRaises(vlan_design.NetworkInputError):
            vlan_design.parse_department_line(",20", 2)


class TestReadNetworkFile(unittest.TestCase):
    def _write_temp_file(self, content):
        fd, path = tempfile.mkstemp(suffix=".txt")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        self.addCleanup(os.remove, path)
        return path

    def test_read_valid_file(self):
        path = self._write_temp_file(
            "Base network: 10.10.0.0/16\nUsers,20\nEngineering,10\n"
        )
        base_network, departments = vlan_design.read_network_file(path)
        self.assertEqual(base_network, ipaddress.ip_network("10.10.0.0/16"))
        self.assertEqual(departments, [("Users", 20), ("Engineering", 10)])

    def test_read_missing_file(self):
        with self.assertRaises(vlan_design.NetworkInputError):
            vlan_design.read_network_file("does_not_exist.txt")

    def test_read_empty_file(self):
        path = self._write_temp_file("")
        with self.assertRaises(vlan_design.NetworkInputError):
            vlan_design.read_network_file(path)

    def test_read_file_with_no_departments(self):
        path = self._write_temp_file("Base network: 10.10.0.0/16\n")
        with self.assertRaises(vlan_design.NetworkInputError):
            vlan_design.read_network_file(path)

    def test_read_file_with_duplicate_department(self):
        path = self._write_temp_file(
            "Base network: 10.10.0.0/16\nUsers,20\nUsers,5\n"
        )
        with self.assertRaises(vlan_design.NetworkInputError):
            vlan_design.read_network_file(path)

    def test_read_file_ignores_blank_lines(self):
        path = self._write_temp_file(
            "Base network: 10.10.0.0/16\n\nUsers,20\n\n\nEngineering,10\n"
        )
        base_network, departments = vlan_design.read_network_file(path)
        self.assertEqual(departments, [("Users", 20), ("Engineering", 10)])


class TestRequiredPrefixLength(unittest.TestCase):
    def test_small_department(self):
        # 3 devices -> needs 4 usable addresses (3 devices + gateway) -> /29 (6 usable)
        self.assertEqual(vlan_design.required_prefix_length(3), 29)

    def test_exact_fit(self):
        # 5 devices -> needs 6 usable -> /29 (6 usable) fits exactly
        self.assertEqual(vlan_design.required_prefix_length(5), 29)

    def test_medium_department(self):
        # 10 devices -> needs 11 usable -> /28 (14 usable)
        self.assertEqual(vlan_design.required_prefix_length(10), 28)

    def test_larger_department(self):
        # 20 devices -> needs 21 usable -> /27 (30 usable)
        self.assertEqual(vlan_design.required_prefix_length(20), 27)

    def test_single_device(self):
        # 1 device -> needs 2 usable -> /30 (2 usable) fits exactly
        self.assertEqual(vlan_design.required_prefix_length(1), 30)


class TestAllocateSubnets(unittest.TestCase):
    def setUp(self):
        self.base_network = ipaddress.ip_network("10.10.0.0/16")
        self.departments = [
            ("Users", 20),
            ("Engineering", 10),
            ("Servers", 5),
            ("Management", 3),
        ]
        self.vlans = vlan_design.allocate_subnets(self.base_network, self.departments)

    def test_returns_one_entry_per_department_in_original_order(self):
        names = [v["name"] for v in self.vlans]
        self.assertEqual(names, ["Users", "Engineering", "Servers", "Management"])

    def test_vlan_ids_assigned_in_file_order(self):
        vlan_ids = [v["vlan_id"] for v in self.vlans]
        self.assertEqual(vlan_ids, [10, 20, 30, 40])

    def test_subnets_are_within_base_network(self):
        for v in self.vlans:
            self.assertTrue(v["subnet"].subnet_of(self.base_network))

    def test_subnets_do_not_overlap(self):
        subnets = [v["subnet"] for v in self.vlans]
        for i, a in enumerate(subnets):
            for j, b in enumerate(subnets):
                if i != j:
                    self.assertFalse(a.overlaps(b))

    def test_subnet_sizing_matches_device_count(self):
        by_name = {v["name"]: v for v in self.vlans}
        self.assertEqual(by_name["Users"]["prefixlen"], 27)
        self.assertEqual(by_name["Engineering"]["prefixlen"], 28)
        self.assertEqual(by_name["Servers"]["prefixlen"], 29)
        self.assertEqual(by_name["Management"]["prefixlen"], 29)

    def test_usable_count_covers_devices_plus_gateway(self):
        for v in self.vlans:
            self.assertGreaterEqual(v["usable_count"], v["device_count"] + 1)

    def test_insufficient_address_space_raises(self):
        tiny_network = ipaddress.ip_network("10.10.0.0/29")
        with self.assertRaises(vlan_design.NetworkInputError):
            vlan_design.allocate_subnets(tiny_network, self.departments)


class TestGatewayCalculation(unittest.TestCase):
    def test_gateway_is_first_usable_address(self):
        subnet = ipaddress.ip_network("10.10.0.0/27")
        vlans = vlan_design.allocate_subnets(
            ipaddress.ip_network("10.10.0.0/16"), [("Test", 20)]
        )
        v = vlans[0]
        self.assertEqual(v["gateway"], ipaddress.ip_address("10.10.0.1"))
        self.assertEqual(v["gateway"], v["first_usable"])


class TestUsableIpCalculation(unittest.TestCase):
    def test_usable_range_for_slash27(self):
        vlans = vlan_design.allocate_subnets(
            ipaddress.ip_network("10.10.0.0/16"), [("Test", 20)]
        )
        v = vlans[0]
        self.assertEqual(v["network_address"], ipaddress.ip_address("10.10.0.0"))
        self.assertEqual(v["first_usable"], ipaddress.ip_address("10.10.0.1"))
        self.assertEqual(v["last_usable"], ipaddress.ip_address("10.10.0.30"))
        self.assertEqual(v["broadcast_address"], ipaddress.ip_address("10.10.0.31"))
        self.assertEqual(v["usable_count"], 30)

    def test_usable_range_for_slash29(self):
        vlans = vlan_design.allocate_subnets(
            ipaddress.ip_network("10.10.0.0/16"), [("Test", 5)]
        )
        v = vlans[0]
        self.assertEqual(v["network_address"], ipaddress.ip_address("10.10.0.0"))
        self.assertEqual(v["first_usable"], ipaddress.ip_address("10.10.0.1"))
        self.assertEqual(v["last_usable"], ipaddress.ip_address("10.10.0.6"))
        self.assertEqual(v["broadcast_address"], ipaddress.ip_address("10.10.0.7"))
        self.assertEqual(v["usable_count"], 6)


class TestMarkdownGeneration(unittest.TestCase):
    def test_generate_markdown_contains_expected_sections(self):
        base_network = ipaddress.ip_network("10.10.0.0/16")
        vlans = vlan_design.allocate_subnets(
            base_network, [("Users", 20), ("Servers", 5)]
        )
        markdown = vlan_design.generate_markdown(base_network, vlans)
        self.assertIn("# VLAN Design", markdown)
        self.assertIn("## Network Summary", markdown)
        self.assertIn("## VLAN Summary", markdown)
        self.assertIn("Users", markdown)
        self.assertIn("Servers", markdown)
        self.assertIn(str(base_network), markdown)


if __name__ == "__main__":
    unittest.main()
