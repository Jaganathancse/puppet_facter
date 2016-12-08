#!/usr/bin/ruby -w
require 'facter'

numa_list=Facter::Util::Resolution.exec("lscpu | grep 'NUMA .* CPU'")
numa_lines=numa_list.split("\n")
numa_nodes_core_info=Array.new
numa_nodes_pci_address=Array.new

numa_lines.each_with_index do |line,index|
  numa_nodes_core_info[index] = Hash.new
  cpu_range = line.split(':').last.strip()
  if cpu_range.include? "-"
    cpu_range_list=cpu_range.split('-')
    if cpu_range_list.length==2
      numa_nodes_core_info[index] = (cpu_range_list[0]..cpu_range_list[1]).to_a
    end
  else
    numa_nodes[index][0]=cpu_range
  end
end

Dir["/sys/bus/pci/devices/*"].each do |pci_address_dir|
  file_name = File.join(pci_address_dir,"numa_node")
  if File.file?(file_name)
    pci_numa_node = Facter::Util::Resolution.exec("cat #{file_name}").to_i
    # TEST
    #pci_numa_node = pci_numa_node==-1?0:pci_numa_node
    if numa_nodes_pci_address[pci_numa_node].nil?
      numa_nodes_pci_address[pci_numa_node]=Array.new
    end
    numa_nodes_pci_address[pci_numa_node]<< File.basename(pci_address_dir)
  end
end

Facter.add(:numa_core_info) do
  confine :kernel => :linux
  setcode do
    numa_nodes_core_info
  end
end

Facter.add(:numa_pci_address) do
  confine :kernel => :linux
  setcode do
    numa_nodes_pci_address
  end
end

