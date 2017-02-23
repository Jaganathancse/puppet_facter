#!/usr/bin/python

import subprocess
import json
import math

#To execute a command and returns the command line output
def execute_command(command):
    return subprocess.check_output(command, shell=True)

def get_node_introspect_hardware_data(uuid):
    command = "source ~/stackrc;"\
              "openstack baremetal introspection data save {uuid}"\
              " | jq .".format(uuid=uuid)
    data_json = execute_command(command)
    return json.loads(data_json)

def join_fields(fields_json, exclude_fields = []):
    fields = []
    for key, value in fields_json.items():
       if key in exclude_fields:
           continue
       fields.append("{key}: {value}".format(key=key, value=value))
    return ",".join(fields)

def get_node_cpu_info(numa_json):
    cpus = numa_json["cpus"]
    cpu_info = "CPU's:\n"
    for cpu in cpus:
        cpu_info += join_fields(cpu)
        cpu_info += "\n"
    cpu_info +="\n"
    return cpu_info

def get_node_memory_info(numa_json):
    rams = numa_json["ram"]
    ram_info ="RAM: \n"
    for ram in rams:
        ram_info += join_fields(ram)
        ram_info +="\n"
    return ram_info

def get_node_nics_info(numa_json):
    nics = numa_json["nics"]
    nics_info = "NICs: count-{count}".format(count=len(nics))
    nics_info +="\n"
    nic_count = 1
    for nic in nics:
        nics_info += "NIC-{nic_count}: ".format(nic_count=nic_count)
        nics_info += join_fields(nic) + "\n"
        nic_count +=1
    return nics_info

def print_node_numa_topology_info(uuid):
    data_json = get_node_introspect_hardware_data(uuid)
    numa_json = data_json["numa_topology"]
    print "#Node : {uuid}".format(uuid=uuid) + "\n"
    print get_node_cpu_info(numa_json)
    print get_node_memory_info(numa_json)
    print get_node_nics_info(numa_json)
    print "-------------\n"

if __name__ == "__main__":
   lines = execute_command("ironic node-list | grep -v UUID | awk '{print $2}'")
   uuids = list(line for line in lines.split("\n") if line)
   for uuid in uuids:
       print_node_numa_topology_info(uuid)
