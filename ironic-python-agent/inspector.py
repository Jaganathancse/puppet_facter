# Copyright 2015 Red Hat, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import re
import time

from oslo_concurrency import processutils
from oslo_config import cfg
from oslo_log import log as logging
from oslo_serialization import jsonutils
from oslo_utils import excutils
import requests
import stevedore

from ironic_python_agent import encoding
from ironic_python_agent import errors
from ironic_python_agent import hardware
from ironic_python_agent import utils


LOG = logging.getLogger(__name__)
CONF = cfg.CONF
DEFAULT_COLLECTOR = 'default'
DEFAULT_DHCP_WAIT_TIMEOUT = 60

_DHCP_RETRY_INTERVAL = 2
_COLLECTOR_NS = 'ironic_python_agent.inspector.collectors'
_NO_LOGGING_FIELDS = ('logs',)


def _extension_manager_err_callback(names):
    raise errors.InspectionError('Failed to load collector %s' % names)


def extension_manager(names):
    return stevedore.NamedExtensionManager(
        _COLLECTOR_NS, names=names, name_order=True,
        on_missing_entrypoints_callback=_extension_manager_err_callback)


def inspect():
    """Optionally run inspection on the current node.

    If ``inspection_callback_url`` is set in the configuration, get
    the hardware inventory from the node and post it back to the inspector.

    :return: node UUID if inspection was successful, None if associated node
             was not found in inspector cache. None is also returned if
             inspector support is not enabled.
    """
    if not CONF.inspection_callback_url:
        LOG.info('Inspection is disabled, skipping')
        return
    collector_names = [x.strip() for x in CONF.inspection_collectors.split(',')
                       if x.strip()]
    LOG.info('inspection is enabled with collectors %s', collector_names)

    # NOTE(dtantsur): inspection process tries to delay raising any exceptions
    # until after we posted some data back to inspector. This is because
    # inspection is run automatically on (mostly) unknown nodes, so if it
    # fails, we don't have much information for debugging.
    failures = utils.AccumulatedFailures(exc_class=errors.InspectionError)
    data = {}

    try:
        ext_mgr = extension_manager(collector_names)
        collectors = [(ext.name, ext.plugin) for ext in ext_mgr]
    except Exception as exc:
        with excutils.save_and_reraise_exception():
            failures.add(exc)
            call_inspector(data, failures)

    for name, collector in collectors:
        try:
            collector(data, failures)
        except Exception as exc:
            # No reraise here, try to keep going
            failures.add('collector %s failed: %s', name, exc)

    resp = call_inspector(data, failures)

    # Now raise everything we were delaying
    failures.raise_if_needed()

    if resp is None:
        LOG.info('stopping inspection, as inspector returned an error')
        return

    # Optionally update IPMI credentials
    setup_ipmi_credentials(resp)

    LOG.info('inspection finished successfully')
    return resp.get('uuid')


def call_inspector(data, failures):
    """Post data to inspector."""
    data['error'] = failures.get_error()

    LOG.info('posting collected data to %s', CONF.inspection_callback_url)
    LOG.debug('collected data: %s',
              {k: v for k, v in data.items() if k not in _NO_LOGGING_FIELDS})

    encoder = encoding.RESTJSONEncoder()
    data = encoder.encode(data)

    resp = requests.post(CONF.inspection_callback_url, data=data)
    if resp.status_code >= 400:
        LOG.error('inspector error %d: %s, proceeding with lookup',
                  resp.status_code, resp.content.decode('utf-8'))
        return

    return resp.json()


def setup_ipmi_credentials(resp):
    """Setup IPMI credentials, if requested.

    :param resp: JSON response from inspector.
    """
    if not resp.get('ipmi_setup_credentials'):
        LOG.info('setting IPMI credentials was not requested')
        return

    user, password = resp['ipmi_username'], resp['ipmi_password']
    LOG.debug('setting IPMI credentials: user %s', user)

    commands = [
        ('user', 'set', 'name', '2', user),
        ('user', 'set', 'password', '2', password),
        ('user', 'enable', '2'),
        ('channel', 'setaccess', '1', '2',
         'link=on', 'ipmi=on', 'callin=on', 'privilege=4'),
    ]

    for cmd in commands:
        try:
            utils.execute('ipmitool', *cmd)
        except processutils.ProcessExecutionError:
            LOG.exception('failed to update IPMI credentials')
            raise errors.InspectionError('failed to update IPMI credentials')

    LOG.info('successfully set IPMI credentials: user %s', user)


def _normalize_mac(mac):
    """Convert MAC to a well-known format aa:bb:cc:dd:ee:ff."""
    if '-' in mac:
        # pxelinux format is 01-aa-bb-cc-dd-ee-ff
        mac = mac.split('-', 1)[1]
        mac = mac.replace('-', ':')
    return mac.lower()


def wait_for_dhcp():
    """Wait until NIC's get their IP addresses via DHCP or timeout happens.

    Depending on the value of inspection_dhcp_all_interfaces configuration
    option will wait for either all or only PXE booting NIC.

    Note: only supports IPv4 addresses for now.

    :return: True if all NIC's got IP addresses, False if timeout happened.
             Also returns True if waiting is disabled via configuration.
    """
    if not CONF.inspection_dhcp_wait_timeout:
        return True

    pxe_mac = utils.get_agent_params().get('BOOTIF')
    if pxe_mac:
        pxe_mac = _normalize_mac(pxe_mac)
    elif not CONF.inspection_dhcp_all_interfaces:
        LOG.warning('No PXE boot interface known - not waiting for it '
                    'to get the IP address')
        return False

    threshold = time.time() + CONF.inspection_dhcp_wait_timeout
    while time.time() <= threshold:
        interfaces = hardware.dispatch_to_managers('list_network_interfaces')
        interfaces = [iface for iface in interfaces
                      if CONF.inspection_dhcp_all_interfaces
                      or iface.mac_address.lower() == pxe_mac]
        missing = [iface.name for iface in interfaces
                   if not iface.ipv4_address]
        if not missing:
            return True

        LOG.debug('Still waiting for interfaces %s to get IP addresses',
                  missing)
        time.sleep(_DHCP_RETRY_INTERVAL)

    LOG.warning('Not all network interfaces received IP addresses in '
                '%(timeout)d seconds: %(missing)s',
                {'timeout': CONF.inspection_dhcp_wait_timeout,
                 'missing': missing})
    return False


def collect_default(data, failures):
    """The default inspection collector.

    This is the only collector that is called by default. It collects
    the whole inventory as returned by the hardware manager(s).

    It also tries to get BMC address, PXE boot device and the expected
    root device.

    :param data: mutable data that we'll send to inspector
    :param failures: AccumulatedFailures object
    """
    wait_for_dhcp()
    inventory = hardware.dispatch_to_managers('list_hardware_info')

    data['inventory'] = inventory
    # Replicate the same logic as in deploy. We need to make sure that when
    # root device hints are not set, inspector will use the same root disk as
    # will be used for deploy.
    try:
        root_disk = utils.guess_root_disk(inventory['disks'][:])
    except errors.DeviceNotFound:
        root_disk = None
        LOG.warning('no suitable root device detected')
    else:
        data['root_disk'] = root_disk
        LOG.debug('default root device is %s', root_disk.name)
    # Both boot interface and IPMI address might not be present,
    # we don't count it as failure
    data['boot_interface'] = inventory['boot'].pxe_interface
    LOG.debug('boot devices was %s', data['boot_interface'])
    data['ipmi_address'] = inventory.get('bmc_address')
    LOG.debug('BMC IP address: %s', data['ipmi_address'])


def collect_logs(data, failures):
    """Collect system logs from the ramdisk.

    As inspection runs before any nodes details are known, it's handy to have
    logs returned with data. This collector sends logs to inspector in format
    expected by the 'ramdisk_error' plugin: base64 encoded tar.gz.

    This collector should be installed last in the collector chain, otherwise
    it won't collect enough logs.

    This collector does not report failures.

    :param data: mutable data that we'll send to inspector
    :param failures: AccumulatedFailures object
    """
    try:
        data['logs'] = utils.collect_system_logs(journald_max_lines=10000)
    except errors.CommandExecutionError:
        LOG.warning('failed to get system journal')
        return


def collect_extra_hardware(data, failures):
    """Collect detailed inventory using 'hardware-detect' utility.

    Recognizes ipa-inspection-benchmarks with list of benchmarks (possible
    values are cpu, disk, mem) to run. No benchmarks are run by default, as
    they're pretty time-consuming.

    Puts collected data as JSON under 'data' key.
    Requires 'hardware' python package to be installed on the ramdisk in
    addition to the packages in requirements.txt.

    :param data: mutable data that we'll send to inspector
    :param failures: AccumulatedFailures object
    """
    benchmarks = utils.get_agent_params().get('ipa-inspection-benchmarks', [])
    if benchmarks:
        benchmarks = ['--benchmark'] + benchmarks.split(',')

    try:
        out, err = utils.execute('hardware-detect', *benchmarks)
    except (processutils.ProcessExecutionError, OSError) as exc:
        failures.add('failed to run hardware-detect utility: %s', exc)
        return

    try:
        data['data'] = jsonutils.loads(out)
    except ValueError as exc:
        msg = 'JSON returned from hardware-detect cannot be decoded: %s'
        failures.add(msg, exc)


def collect_pci_devices_info(data, failures):
    """Collect a list of PCI devices.

    Each PCI device entry in list is a dictionary containing vendor_id and
    product_id keys, which will be then used by the ironic inspector to
    distinguish various PCI devices.

    The data is gathered from /sys/bus/pci/devices directory.

    :param data: mutable data that we'll send to inspector
    :param failures: AccumulatedFailures object
    """
    pci_devices_path = '/sys/bus/pci/devices'
    pci_devices_info = []
    try:
        subdirs = os.listdir(pci_devices_path)
    except OSError as exc:
        msg = 'Failed to get list of PCI devices: %s'
        failures.add(msg, exc)
        return
    for subdir in subdirs:
        if not os.path.isdir(os.path.join(pci_devices_path, subdir)):
            continue
        try:
            # note(sborkows): ids located in files inside PCI devices
            # directory are stored in hex format (0x1234 for example) and
            # we only need that part after 'x' delimiter
            with open(os.path.join(pci_devices_path, subdir,
                                   'vendor')) as vendor_file:
                vendor = vendor_file.read().strip().split('x')[1]
            with open(os.path.join(pci_devices_path, subdir,
                                   'device')) as vendor_device:
                device = vendor_device.read().strip().split('x')[1]
        except IOError as exc:
            LOG.warning('Failed to gather vendor id or product id '
                        'from PCI device %s: %s', subdir, exc)
            continue
        except IndexError as exc:
            LOG.warning('Wrong format of vendor id or product id in PCI '
                        'device %s: %s', subdir, exc)
            continue
        LOG.debug(
            'Found a PCI device with vendor id %s and product id %s',
            vendor, device)
        pci_devices_info.append({'vendor_id': vendor,
                                 'product_id': device})
    data['pci_devices'] = pci_devices_info


def get_numa_nodes_memory_info(numa_node_path, numa_node_dirs):
    ram = []
    for numa_node_dir in numa_node_dirs:
        if (not os.path.isdir(os.path.join(numa_node_path, numa_node_dir))
            or not numa_node_dir.startswith("node")):
            continue
        numa_node_memory ={}
        memory_available_kb = 0
        try:
            with open(os.path.join(numa_node_path, numa_node_dir,
                  'meminfo')) as meminfo_file:
                meminfo_lines = meminfo_file.read().split('\n')
                for line in meminfo_lines:
                    if "MemTotal:" in line:
                        memory_available_kb = int(line.split(":")[1].strip().split(" ")[0].strip())
                        break
                numa_node_memory['numa_node'] = int(numa_node_dir[4:])
                numa_node_memory['size_kb'] = memory_available_kb
            ram.append(numa_node_memory)
        except IOError as exc:
            LOG.warning('Failed to get meminfo for numa_node %s: %s', 
                            numa_node_dir, exc)
    return ram


def get_numa_nodes_cores_info(numa_node_path, numa_node_dirs):
    cpus = []
    for numa_node_dir in numa_node_dirs:
        if (not os.path.isdir(os.path.join(numa_node_path, numa_node_dir))
            or not numa_node_dir.startswith("node")):
            continue
        try:
            thread_dirs = os.listdir(os.path.join(numa_node_path, numa_node_dir))
        except OSError as exc:
            LOG.warning('Failed to get list of threads for numa_node %s: %s',    
                            numa_node_dir, exc)

        for thread_dir in thread_dirs:
            if (not os.path.isdir(os.path.join(numa_node_path,
                numa_node_dir, thread_dir)) or not thread_dir.startswith("cpu")):
                continue
            try:
                is_cpu_id_exists = False
                thread_id = int(thread_dir[3:])
                numa_node_id = int(numa_node_dir[4:])
                with open(os.path.join(numa_node_path, numa_node_dir,
                          thread_dir, 'topology',
                          'core_id')) as core_id_file:
                     cpu_id = int(core_id_file.read().strip())
                     if cpus:
                         for c in cpus:
                             if (cpu_id == c['cpu'] and not thread_id in c['thread_siblings']):
                                 c['thread_siblings'].append(thread_id)
                                 is_cpu_id_exists = True
                                 break
                     if not is_cpu_id_exists:
                         cpu_item = {}
                         cpu_item['thread_siblings'] = [thread_id]
                         cpu_item['cpu'] = cpu_id
                         cpu_item['numa_node'] = numa_node_id
                         cpus.append(cpu_item)
                
            except IOError as exc:
                LOG.warning('Failed to gather cpu_id for thread'
                            '%s numa_node %s: %s', thread_dir,
                            numa_node_dir, exc)
    return cpus


def get_numa_nodes_nics_info(nic_device_path, nic_dirs):
    nics = []
    for nic_dir in nic_dirs:
        if (not os.path.exists(os.path.join(nic_device_path, nic_dir, 'device'))
            or not os.path.isdir(os.path.join(nic_device_path, nic_dir, 'device'))
            or not os.path.exists(os.path.join(nic_device_path,
            nic_dir, 'device', 'numa_node'))):
            continue
        try:
            with open(os.path.join(nic_device_path, nic_dir, 'device',
                                   'numa_node')) as numa_node_file:
                numa_node_nics = {}
                numa_node_nics['name'] = nic_dir
                numa_node_nics['numa_node'] = int(numa_node_file.read().strip())
                LOG.debug('Found a NIC %s in NUMA node %s', nic_dir,
                          numa_node_nics['numa_node'])
                nics.append(numa_node_nics)
        except IOError as exc:
            LOG.warning('Failed to gather NUMA node for NICs %s: %s', nic_dir, exc)
    return nics


def collect_numa_topology_info(data, failures):
    """Collect the NUMA topology information.

    {
      "numa_topology": {
        "ram": [{"numa_node": <numa_node_id>, "size_kb": <memory_in_kb>}, ...],
        "cpus": [
          {
            "cpu": <cpu_id>, "numa_node": <numa_node_id>,
            "thread_siblings": [<list of sibling threads>]
          },
          ...,
        ],
        "nics": [
          {"name": "<network interface name>", "numa_node": <numa_node_id>},
          ...,
        ]
      }
    }

    The data is gathered from /sys/devices/system/node/node<X> and
    /sys/class/net/ directories.

    :param data: mutable data that we'll send to inspector
    :param failures: AccumulatedFailures object
    """
    numa_node_path = '/sys/devices/system/node/'
    numa_topology = {}
    try:
        numa_node_dirs = os.listdir(numa_node_path)
        numa_topology['ram'] = get_numa_nodes_memory_info(numa_node_path, numa_node_dirs)
        numa_topology['cpus'] = get_numa_nodes_cores_info(numa_node_path, numa_node_dirs)
    except OSError as exc:
        msg = 'Failed to get list of NUMA nodes: %s'
        failures.add(msg, exc)
        return

    nic_device_path = '/sys/class/net/'
    try:
        nic_dirs = os.listdir(nic_device_path)
        numa_topology['nics'] = get_numa_nodes_nics_info(nic_device_path, nic_dirs)
    except OSError as exc:
        msg = 'Failed to get list of NICs: %s'
        failures.add(msg, exc)
        return

    data['numa_topology'] = numa_topology
