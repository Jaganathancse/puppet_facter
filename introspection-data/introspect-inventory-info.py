#!/usr/bin/python

import subprocess
import json
import math

#To execute a command and returns the command line output
def execute_command(command):
    return subprocess.check_output(command, shell=True)

#To get introspection data as json format for a node
def get_node_introspect_hardware_data(uuid):
    command = "source ~/stackrc;"\
              "openstack baremetal introspection data save {uuid}"\
              " | jq .".format(uuid=uuid)
    data_json = execute_command(command)
    return json.loads(data_json)

#To join all the fields as key and value pair
def join_fields(fields_json, exclude_fields = []):
    fields = []
    for key, value in fields_json.items():
       if key in exclude_fields:
           continue
       fields.append("{key}: {value}".format(key=key, value=value))
    return ",".join(fields)

#To get the node cpu's information in custom format
def get_node_cpu_info(inventory_json):
    cpus = inventory_json["cpu"]
    cpu_info = "CPU: "
    cpu_info += join_fields(cpus, ["flags"])
    cpu_info +="\n"
    return cpu_info

#To convert the size from bytes to required size name
def convert_size(size):
    size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    index = int(math.floor(math.log(size,1024)))
    converted_size = round(size/math.pow(1024, index), 2)
    if (converted_size > 0):
        return '%s %s' % (converted_size, size_name[index])
    return '0B'

#To get the node memory information in custom format
def get_node_memory_info(inventory_json):
    ram = inventory_json["memory"]
    ram_info ="RAM: "
    ram_fields = []
    for key, value in ram.items():
        if key in ["total"]:
            ram_fields.append("{key}: {val}".format(key=key,
                              val=convert_size(int(value))))
        else:
            ram_fields.append("{key}: {value}".format(key=key,
                                                      value=value))
    ram_info += ",".join(ram_fields) + "\n"
    return ram_info

#To get the node system information in custom format
def get_node_system_info(inventory_json):
    system = inventory_json["system_vendor"]
    system_info = "System: "
    system_info +=  join_fields(system)
    system_info += "\n"
    return system_info

#To get boot information
def get_node_boot_info(inventory_json):
    boot = inventory_json["boot"]
    boot_info = "Boot Info: "
    boot_info += join_fields(boot)
    return boot_info

#To get the node disks information in custom format
def get_node_disk_info(inventory_json):
    disks = inventory_json["disks"]
    disk_info = "Disks: Count-{count}".format(count=len(disks))
    disk_info +="\n"
    disk_count = 1
    for disk in disks:
        disk_size = int(disk["size"] if disk["size"] else 0)
        disk["size"] = convert_size(disk_size)
        disk_info += "Disk-{disk_count}: ".format(disk_count=disk_count)
        disk_info += join_fields(disk) + "\n"
        disk_count +=1
    return disk_info

#To get the node nics information in custom format
def get_node_nics_info(inventory_json):
    nics = inventory_json["interfaces"]
    nics_info = "NICs: Count-{count}".format(count=len(nics))
    nics_info +="\n"
    nic_count = 1
    for nic in nics:
        nics_info += "NIC-{nic_count}: ".format(nic_count=nic_count)
        nics_info += join_fields(nic) + "\n"
        nic_count +=1
    return nics_info

#To print the node inventory hardware information
def print_node_inventory_hardware_info(uuid):
    data_json = get_node_introspect_hardware_data(uuid)
    inventory_json = data_json["inventory"]
    print "#Node : {uuid}".format(uuid=uuid) + "\n"
    print get_node_cpu_info(inventory_json)
    print get_node_memory_info(inventory_json)
    print get_node_system_info(inventory_json)
    print get_node_boot_info(inventory_json)
    print get_node_disk_info(inventory_json)
    print get_node_nics_info(inventory_json)
    print "-------------\n"

#To print all the node inventory hardware information
if __name__ == "__main__":
   lines = execute_command("ironic node-list | grep -v UUID | awk '{print $2}'")
   uuids = list(line for line in lines.split("\n") if line)
   for uuid in uuids:
       print_node_inventory_hardware_info(uuid)
