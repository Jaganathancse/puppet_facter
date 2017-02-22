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

def get_node_cpu_info(extra_json):
    cpus = extra_json["cpu"]
    cpu_info = "CPU: physical: {physical}, logical: {logical}"\
               .format(physical=cpus['physical']['number'],
                       logical=cpus['logical']['number'])
    cpu_count = int(cpus['physical']['number'])
    cpu_info +="\n"
    for item in xrange(0, cpu_count):
        cpu_info +="physical "+str(item)+": "
        cpu_info += join_fields(cpus['physical_'+str(item)], ["flags"])
        cpu_info +="\n"
    return cpu_info

def convert_size(size):
    size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    index = int(math.floor(math.log(size,1024)))
    converted_size = round(size/math.pow(1024, index), 2)
    if (converted_size > 0):
        return '%s %s' % (converted_size, size_name[index])
    return '0B'

def get_node_memory_info(extra_json):
    ram = extra_json["memory"]
    total = 0
    for key, value in ram.items():
        if key in ["bank","total"]:
            total += int(value["size"])
    return "RAM: " + str(convert_size(total)) + "\n"

def get_node_system_info(extra_json):
    system = extra_json["system"]
    system_info = "System: "
    system_info +=  join_fields(system["product"])
    system_info += "\n"
    system_info += "Kernel: "
    system_info += join_fields(system["kernel"])
    system_info += "\n"
    return system_info

def get_node_firmware_info(extra_json):
    firmware = extra_json["firmware"]
    firmware_info = "Firmware: "
    firmware_info += join_fields(firmware["bios"])
    return firmware_info

def get_node_disk_info(extra_json):
    disk = extra_json["disk"]
    disk_info = "Disk: logical: {logical}".format(logical=disk["logical"]["count"])
    disk_info +="\n"
    disk_count = 1
    for key, value in disk.items():
        if key in ["logical","physical"]:
            continue;
        disk_info += "Disk-{disk_count} Name-{key}: ".format(disk_count=disk_count,
                                                       key=key) + join_fields(value) + "\n"
        disk_count +=1
    return disk_info

def get_node_nics_info(extra_json):
    nics = extra_json["network"]
    nics_info = "NICS: "
    nics_info +="\n"
    nics_count = 1
    for key, value in nics.items():
        nics_info += "NIC-{nics_count} Name-{key}: ".format(nics_count=nics_count,
                                                            key=key) + join_fields(value) + "\n"
    return nics_info

def print_node_extra_hardware_info(uuid):
    data_json = get_node_introspect_hardware_data(uuid)
    extra_json = data_json["extra"]
    print "#Node : {uuid}".format(uuid=uuid) + "\n"
    print get_node_cpu_info(extra_json)
    print get_node_memory_info(extra_json)
    print get_node_system_info(extra_json)
    print get_node_firmware_info(extra_json)
    print get_node_disk_info(extra_json)
    print get_node_nics_info(extra_json)
    print "-------------\n"

if __name__ == "__main__":
   lines = execute_command("ironic node-list | grep -v UUID | awk '{print $2}'")
   uuids = list(line for line in lines.split("\n") if line)
   for uuid in uuids:
       print_node_extra_hardware_info(uuid)

