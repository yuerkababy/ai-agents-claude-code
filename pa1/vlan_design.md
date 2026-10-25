# VLAN Design

## Network Summary

- Base network: `10.10.0.0/16`
- Departments: 4
- Total devices: 38
- Total usable addresses allocated: 56

## VLAN Summary

| VLAN ID | Department | Devices | Subnet | Netmask | Gateway | Usable Range | Broadcast |
|---|---|---|---|---|---|---|---|
| 10 | Users | 20 | 10.10.0.0/27 | 255.255.255.224 | 10.10.0.1 | 10.10.0.1 - 10.10.0.30 | 10.10.0.31 |
| 20 | Engineering | 10 | 10.10.0.32/28 | 255.255.255.240 | 10.10.0.33 | 10.10.0.33 - 10.10.0.46 | 10.10.0.47 |
| 30 | Servers | 5 | 10.10.0.48/29 | 255.255.255.248 | 10.10.0.49 | 10.10.0.49 - 10.10.0.54 | 10.10.0.55 |
| 40 | Management | 3 | 10.10.0.56/29 | 255.255.255.248 | 10.10.0.57 | 10.10.0.57 - 10.10.0.62 | 10.10.0.63 |
