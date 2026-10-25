"""VLAN Design Generator.

Reads a base network and department/device-count list from network.txt,
calculates VLAN and subnet assignments (VLSM), and writes the result to
vlan_design.md.
"""

import ipaddress
import sys

INPUT_FILE = "network.txt"
OUTPUT_FILE = "vlan_design.md"

VLAN_ID_START = 10
VLAN_ID_STEP = 10


class NetworkInputError(Exception):
    """Raised when network.txt is missing or malformed."""


def parse_base_network(line, line_num):
    if ":" not in line:
        raise NetworkInputError(
            f"Line {line_num}: expected 'Base network: <CIDR>' but got: {line!r}"
        )
    _, _, value = line.partition(":")
    value = value.strip()
    try:
        return ipaddress.ip_network(value, strict=False)
    except ValueError as exc:
        raise NetworkInputError(
            f"Line {line_num}: invalid base network '{value}': {exc}"
        ) from exc


def parse_department_line(line, line_num):
    parts = line.split(",")
    if len(parts) != 2:
        raise NetworkInputError(
            f"Line {line_num}: expected 'DepartmentName,DeviceCount' but got: {line!r}"
        )
    name, count_str = (p.strip() for p in parts)
    if not name:
        raise NetworkInputError(f"Line {line_num}: department name is empty")
    try:
        count = int(count_str)
    except ValueError as exc:
        raise NetworkInputError(
            f"Line {line_num}: device count '{count_str}' is not an integer"
        ) from exc
    if count <= 0:
        raise NetworkInputError(
            f"Line {line_num}: device count for '{name}' must be a positive integer, got {count}"
        )
    return name, count


def read_network_file(path):
    """Read and parse the network requirements file.

    Returns (base_network, departments) where departments is a list of
    (name, device_count) tuples in file order.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw_lines = f.readlines()
    except FileNotFoundError as exc:
        raise NetworkInputError(f"Input file '{path}' was not found") from exc
    except OSError as exc:
        raise NetworkInputError(f"Could not read input file '{path}': {exc}") from exc

    lines = [(i, line.strip()) for i, line in enumerate(raw_lines, start=1)]
    lines = [(i, line) for i, line in lines if line]

    if not lines:
        raise NetworkInputError(f"Input file '{path}' is empty")

    first_num, first_line = lines[0]
    base_network = parse_base_network(first_line, first_num)

    departments = []
    seen_names = set()
    for line_num, line in lines[1:]:
        name, count = parse_department_line(line, line_num)
        if name in seen_names:
            raise NetworkInputError(f"Line {line_num}: duplicate department '{name}'")
        seen_names.add(name)
        departments.append((name, count))

    if not departments:
        raise NetworkInputError(
            f"Input file '{path}' does not list any departments"
        )

    return base_network, departments


def required_prefix_length(device_count, address_family_bits=32):
    """Smallest prefix length whose subnet has room for device_count hosts
    plus one address reserved for the gateway, plus network/broadcast."""
    usable_needed = device_count + 1  # devices + gateway
    host_bits = 0
    while (2 ** host_bits) - 2 < usable_needed:
        host_bits += 1
    return address_family_bits - host_bits


def allocate_subnets(base_network, departments):
    """Allocate a VLSM subnet to each department.

    Returns a list of dicts (one per department, in original file order)
    with VLAN id, subnet, gateway, and usable IP range details.
    """
    indexed = list(enumerate(departments))
    # Allocate largest requirements first to pack the address space cleanly.
    by_size_desc = sorted(
        indexed, key=lambda item: item[1][1], reverse=True
    )

    base_start = int(base_network.network_address)
    base_end = int(base_network.broadcast_address)
    next_addr = base_start

    results_by_index = {}
    for original_index, (name, device_count) in by_size_desc:
        prefixlen = required_prefix_length(device_count)
        block_size = 2 ** (32 - prefixlen)

        aligned_start = ((next_addr + block_size - 1) // block_size) * block_size
        aligned_end = aligned_start + block_size - 1

        if aligned_end > base_end:
            raise NetworkInputError(
                f"Base network {base_network} does not have enough address "
                f"space for department '{name}' ({device_count} devices, "
                f"needs a /{prefixlen} block)"
            )

        subnet = ipaddress.ip_network((aligned_start, prefixlen))
        hosts = list(subnet.hosts())
        gateway = hosts[0]
        first_usable = hosts[0]
        last_usable = hosts[-1]

        results_by_index[original_index] = {
            "name": name,
            "device_count": device_count,
            "subnet": subnet,
            "prefixlen": prefixlen,
            "netmask": subnet.netmask,
            "network_address": subnet.network_address,
            "broadcast_address": subnet.broadcast_address,
            "gateway": gateway,
            "first_usable": first_usable,
            "last_usable": last_usable,
            "usable_count": len(hosts),
        }

        next_addr = aligned_start + block_size

    vlans = []
    for original_index, (name, _device_count) in indexed:
        entry = results_by_index[original_index]
        entry["vlan_id"] = VLAN_ID_START + original_index * VLAN_ID_STEP
        vlans.append(entry)

    return vlans


def generate_markdown(base_network, vlans):
    total_devices = sum(v["device_count"] for v in vlans)
    total_usable = sum(v["usable_count"] for v in vlans)

    lines = []
    lines.append("# VLAN Design")
    lines.append("")
    lines.append("## Network Summary")
    lines.append("")
    lines.append(f"- Base network: `{base_network}`")
    lines.append(f"- Departments: {len(vlans)}")
    lines.append(f"- Total devices: {total_devices}")
    lines.append(f"- Total usable addresses allocated: {total_usable}")
    lines.append("")
    lines.append("## VLAN Summary")
    lines.append("")
    header = (
        "| VLAN ID | Department | Devices | Subnet | Netmask | Gateway | "
        "Usable Range | Broadcast |"
    )
    separator = "|---|---|---|---|---|---|---|---|"
    lines.append(header)
    lines.append(separator)
    for v in sorted(vlans, key=lambda x: x["vlan_id"]):
        usable_range = f"{v['first_usable']} - {v['last_usable']}"
        lines.append(
            f"| {v['vlan_id']} | {v['name']} | {v['device_count']} | "
            f"{v['subnet']} | {v['netmask']} | {v['gateway']} | "
            f"{usable_range} | {v['broadcast_address']} |"
        )
    lines.append("")
    return "\n".join(lines)


def write_markdown(content, path):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def main():
    try:
        base_network, departments = read_network_file(INPUT_FILE)
        vlans = allocate_subnets(base_network, departments)
    except NetworkInputError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    markdown = generate_markdown(base_network, vlans)
    write_markdown(markdown, OUTPUT_FILE)
    print(f"VLAN design written to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
