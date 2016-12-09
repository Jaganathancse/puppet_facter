require 'spec_helper'

describe Puppet::Type.type(:dpdk_options) do
  before { Facter.clear }
  after { Facter.clear }
  context "Numa Architecture" do
    before do
     Facter.fact(:numa_core_info).stubs(:value).returns([["0","1","2","3"]])
     Facter.fact(:numa_pci_address).stubs(:value).returns([["0000:00:00.0", "0000:00:01.0", "0000:00:01.1", "0000:00:01.3", "0000:00:02.0", "0000:00:03.0", "0000:00:04.0", "0000:00:05.0"]])
    end
    it "should support valid value all params" do
      expect do
        described_class.new(:path =>'/etc/sysconfig/openvswitch' ,:core_list => '0,2', :pci_list =>'0000:00:01.1,0000:00:01.3', :socket_memory => '1024',:memory_channels =>'2', :ensure => :present)
      end.to_not raise_error
    end

    it "should support absent as a value for ensure" do
      expect do
        described_class.new(:path =>'/etc/sysconfig/openvswitch' ,:core_list => '0,2', :pci_list =>'0000:00:01.1,0000:00:01.3', :socket_memory => '1024',:memory_channels =>'2', :ensure => :absent)
      end.to_not raise_error
    end

    it "should accept only core list with comma seperator" do
      expect do
        described_class.new({:path =>'/etc/sysconfig/openvswitch' ,:core_list => 'a,b', :pci_list =>'0000:00:01.1,0000:00:01.3', :socket_memory => '1024',:memory_channels =>'2', :ensure => :present})
      end.to raise_error(Puppet::Error)
    end
    it "should accept only valid core list based on pci list" do
      expect do
        described_class.new({:path =>'/etc/sysconfig/openvswitch' ,:core_list => '11,13', :pci_list =>'0000:00:01.1,0000:00:01.3', :socket_memory => '1024',:memory_channels =>'2', :ensure => :present})
      end.to raise_error(Puppet::Error)
    end
  
    it "should not accept socket memory as blank" do
      expect do
        described_class.new({:path =>'/etc/sysconfig/openvswitch' ,:core_list => '1,2', :pci_list =>'0000:00:01.1,0000:00:01.3', :socket_memory => ' ',:memory_channels =>'2', :ensure => :present})
      end.to raise_error(Puppet::Error)
    end
  
    it "should not accept socket memory as 0" do
      expect do
        described_class.new({:path =>'/etc/sysconfig/openvswitch' ,:core_list => '1,2', :pci_list =>'0000:00:01.1,0000:00:01.3', :socket_memory => '0',:memory_channels =>'2', :ensure => :present})
      end.to raise_error(Puppet::Error)
    end

    it "should not accept memory channels as blank" do
      expect do
        described_class.new({:path =>'/etc/sysconfig/openvswitch' ,:core_list => '1,2', :pci_list =>'0000:00:01.1,0000:00:01.3', :socket_memory => '1024',:memory_channels =>' ', :ensure => :present})
      end.to raise_error(Puppet::Error)
    end
 
    it "should not accept memory channels as 0" do
      expect do
        described_class.new({:path =>'/etc/sysconfig/openvswitch' ,:core_list => '1,2', :pci_list =>'0000:00:01.1,0000:00:01.3', :socket_memory => '1024',:memory_channels =>'0', :ensure => :present})
      end.to raise_error(Puppet::Error)
    end
  end
  context "No Numa Architecture" do
    before do
     Facter.fact(:numa_core_info).stubs(:value).returns([["0","1","2","3"]])
     Facter.fact(:numa_pci_address).stubs(:value).returns([])
    end
    it "should support valid value all params" do
      expect do
        described_class.new(:path =>'/etc/sysconfig/openvswitch' ,:core_list => '0,2', :pci_list =>'0000:00:01.1,0000:00:01.3', :socket_memory => '1024',:memory_channels =>'2', :ensure => :present)
      end.to_not raise_error
    end

    it "should support absent as a value for ensure" do
      expect do
        described_class.new(:path =>'/etc/sysconfig/openvswitch' ,:core_list => '0,2', :pci_list =>'0000:00:01.1,0000:00:01.3', :socket_memory => '1024',:memory_channels =>'2', :ensure => :absent)
      end.to_not raise_error
    end

    it "should accept only core list with comma seperator" do
      expect do
        described_class.new({:path =>'/etc/sysconfig/openvswitch' ,:core_list => 'a,b', :pci_list =>'0000:00:01.1,0000:00:01.3', :socket_memory => '1024',:memory_channels =>'2', :ensure => :present})
      end.to raise_error(Puppet::Error)
    end
    it "should accept invalid core list" do
      expect do
        described_class.new({:path =>'/etc/sysconfig/openvswitch' ,:core_list => '11,13', :pci_list =>'0000:00:01.1,0000:00:01.3', :socket_memory => '1024',:memory_channels =>'2', :ensure => :present})
      end.to_not raise_error
    end
  
    it "should accept socket memory as blank" do
      expect do
        described_class.new({:path =>'/etc/sysconfig/openvswitch' ,:core_list => '1,2', :pci_list =>'0000:00:01.1,0000:00:01.3', :socket_memory => ' ',:memory_channels =>'2', :ensure => :present})
      end.to_not raise_error
    end
  
    it "should accept socket memory as 0" do
      expect do
        described_class.new({:path =>'/etc/sysconfig/openvswitch' ,:core_list => '1,2', :pci_list =>'0000:00:01.1,0000:00:01.3', :socket_memory => '0',:memory_channels =>'2', :ensure => :present})
      end.to_not raise_error
    end

    it "should not accept memory channels as blank" do
      expect do
        described_class.new({:path =>'/etc/sysconfig/openvswitch' ,:core_list => '1,2', :pci_list =>'0000:00:01.1,0000:00:01.3', :socket_memory => '1024',:memory_channels =>' ', :ensure => :present})
      end.to raise_error(Puppet::Error)
    end
 
    it "should not accept memory channels as 0" do
      expect do
        described_class.new({:path =>'/etc/sysconfig/openvswitch' ,:core_list => '1,2', :pci_list =>'0000:00:01.1,0000:00:01.3', :socket_memory => '1024',:memory_channels =>'0', :ensure => :present})
      end.to raise_error(Puppet::Error)
    end
  end

end
