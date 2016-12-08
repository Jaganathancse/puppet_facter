require 'puppet'
require 'facter'

Puppet::Type.newtype(:dpdk_options) do
  desc 'DPDK Options'

  ensurable
  newparam(:path, :namevar => true) do
    newvalues(/\S+\/\S+/)
  end
  newparam(:pci_list) do
    desc 'PCI address for driver type'
  end
  newparam(:core_list) do
    desc 'CPU core list for dpdk options'
    newvalues(/^[0-9]+([,]{1}[0-9]+)*$/)
  end
  newparam(:socket_memory) do
    desc 'Socket memory mapping'
  end
  newparam(:memory_channels) do
    desc 'Memory channels'
    validate do |value|
      if !/^\d+$/.match(value) || value=="0" || value==" "
        fail("Invalid memory channels #{value}")        
      end 
    end
  end
  validate do      
    cpu_core_list = self[:core_list].split(",")
    pci_address_list=self[:pci_list].split(",")
    numa_nodes_pci_address = Facter.value(:numa_pci_address)
    numa_nodes_core_info = Facter.value(:numa_core_info)
    numa_nodes_list=[]
    pci_address_list.each do |pci|
      for node in 0..numa_nodes_pci_address.length-1
        if (numa_nodes_pci_address[node].include? pci)
          unless (numa_nodes_list.include? node)
            numa_nodes_list.push(node)
          end
          break
        end
      end
    end
    pci_numa_nodes_core_info = []
    numa_nodes_list.each do |pci_node|
      pci_numa_nodes_core_info = pci_numa_nodes_core_info | numa_nodes_core_info[pci_node]
    end
    is_core_valid=false
    cpu_core_list.each do |core|
      if(pci_numa_nodes_core_info.include? core)
        is_core_valid=true
        break
      end
    end
    if !is_core_valid
      fail("Invalid core list #{self[:core_list]}")
    end
    socket_memory=self[:socket_memory].split(",")
    numa_nodes_list.each do |node|
      if(socket_memory[node]=="0" || socket_memory[node]==" " || socket_memory[node].length==0)
        #puts socket_memory[node]
        fail("Invalid socket memory #{self[:socket_memory]}")
      end
    end
  end
 
end
