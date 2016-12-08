require 'puppet'

Puppet::Type.type(:vs_options).provide(:dpdk) do
  desc 'Write dpdk options in /etc/sysconfig/openvswitch file'

  def exists?
    exists  = get_dpdk_line == get_updated_dpdk_line
  end

  def create
    dpdk_line=get_dpdk_line
    file_content = File.read(resource[:path])
    updated_content = file_content.gsub(dpdk_line, get_updated_dpdk_line)
    File.open(resource[:path], "w") do |file|
      file.write(updated_content)
    end
  end

  def destroy
    dpdk_line=get_dpdk_line
    file_content = File.read(resource[:path])
    updated_content = file_content.gsub(dpdk_line,'DPDK_OPTIONS =""')
    File.open(resource[:path], "w") do |file|
      file.write(updated_content)
    end
  end
  
  def get_dpdk_line
    dpdk_line=""
    if File.exist?(resource[:path])
      File.open(resource[:path], 'r').each_line do |line|
        if (line.include? "DPDK_OPTIONS =")
          return line
        end
      end
    else
      fail("#{resource[:path]} doesn't exist.")
    end
    dpdk_line
  end
  def get_updated_dpdk_line
    return "DPDK_OPTIONS = \"-l #{resource[:core_list]} -n #{resource[:memory_channels]} -socket-mem #{resource[:socket_memory]} -w #{resource[:pci_list].gsub(",", " -w ")}\""
  end

end
