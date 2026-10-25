# VLAN Design Generator

A generated VLAN network design file from an existing network requirements file.

Stack: Python + Markdown + local filesystem

## Commands
- Install: No external dependencies needed but verify with `python --version`
- Test: `python -m unittest discover`
- Lint: `python -m py_compile vlan_design.py`
- Build/Run: `python vlan_design.py`

## Structure
- `network.txt` - existing input file containing a base network, departments, and number of devices.
- `vlan_design.py` - Python program that reads the input, calculates the VLAN and subnet information, and generates the design.
- `test_vlan_design.py` - tests VLAN calculations, subnet sizing, gateway and usable IP calculations.
- `vlan_design.md` - generated markdown report containing the VLAN design as well as a network and VLAN summary table.

## Conventions
- Use Python 3
- Use the Python standard library
- Use clear functions for reading input, calculating network information, and generating the markdown.
- Calculate VLAN and subnet information from `network.txt` rather than hard-coding department names or device counts.
- Handle invalid or missing input with clear error messages.
- The program should run end-to-end with one command: `python vlan_design.py`.

## Do Not
- Do not create, modify, or overwrite `network.txt`
- Do not use unnecessary external libraries.
- Do not hard-code department names or device counts
