
require 'puppet'
require 'spec_helper'
require 'puppet/provider/dpdk_options/dpdk'

provider_class = Puppet::Type.type(:dpdk_options).
  provider(:dpdk)

describe provider_class do

  let :dpdk_conf do
    {
      :path =>'/etc/sysconfig/openvswitch',
      :core_list => '1,2',
      :pci_list =>'0000:00:01.1,0000:00:01.3',
      :socket_memory => '1024',
      :memory_channels =>'2',
      :ensure => :present,
    }
  end

  describe 'when setting the attributes' do
    let :resource do
      Puppet::Type::Dpdk_options.new(dpdk_conf)
    end

    let :provider do
      provider_class.new(resource)
    end

    it 'should return the current dpdk options line' do
      expect(provider.get_dpdk_line).to include('DPDK_OPTIONS =')
    end

    it 'should return the updated dpdk options line' do
      expect(provider.get_updated_dpdk_line).to eql('DPDK_OPTIONS = "-l 1,2 -n 2 -socket-mem 1024 -w 0000:00:01.1 -w 0000:00:01.3"')
    end

  end
end
