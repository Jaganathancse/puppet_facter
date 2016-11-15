#!/usr/bin/ruby -w
require 'facter'

numa_list=Facter::Util::Resolution.exec("lscpu | grep 'NUMA .* CPU'")
numa_lines=numa_list.split("\n")
numa_nodes=Array.new

# TEST
numa_lines << "NUMA node1 CPU(s):     4-10"

numa_lines.each_with_index do |line,index|
  numa_nodes[index] = Hash.new
  cpu_range = line.split(':').last.strip()
  numa_nodes[index]["cpu_list"]=Array.new
  if cpu_range.include? "-"
    cpu_range_list=cpu_range.split('-')
    if cpu_range_list.length==2
      numa_nodes[index]["cpu_list"] = (cpu_range_list[0]..cpu_range_list[1]).to_a
    end
  else
    numa_nodes[index]["cpu_list"][0]=cpu_range
  end

end

#puts numa_nodes[1]["cpu_list"][3]

Dir["/sys/bus/pci/devices/*"].each do |pci_address_dir|
  file_name = File.join(pci_address_dir,"numa_node")
  if File.file?(file_name)
    pci_numa_node = Facter::Util::Resolution.exec("cat #{file_name}").to_i
    # TEST
    pci_numa_node = pci_numa_node==-1?0:pci_numa_node
    if numa_nodes[pci_numa_node]["pci_address"].nil?
      numa_nodes[pci_numa_node]["pci_address"]=Array.new
    end
    numa_nodes[pci_numa_node]["pci_address"] << File.basename(pci_address_dir)
    #puts File.basename(pci_address_dir) + "  " + pci_numa_node.to_s
  end
end

#puts numa_nodes

Facter.add(:numa_count) do
  confine :kernel => :linux
  setcode do
   numa_nodes.length 
  end
end

Facter.add(:numa_info) do
  confine :kernel => :linux
  setcode do
    numa_nodes
  end
end
