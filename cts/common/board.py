# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from abc import ABCMeta
from abc import abstractmethod
import fcntl
import os
import select
import shutil
import subprocess as sp


OCD_SCRIPT_DIR = '/usr/local/share/openocd/scripts'
OPENOCD_CONFIGS = {
    'stm32l476g-eval': 'board/stm32l4discovery.cfg',
    'nucleo-f072rb': 'board/st_nucleo_f0.cfg',
    'nucleo-f411re': 'board/st_nucleo_f4.cfg',
}
FLASH_OFFSETS = {
    'stm32l476g-eval': '0x08000000',
    'nucleo-f072rb': '0x08000000',
    'nucleo-f411re': '0x08000000',
}
REBOOT_MARKER = 'UART initialized after reboot'


class Board(object):
  """Class representing a single board connected to a host machine.

  Attributes:
    board: String containing actual type of board, i.e. nucleo-f072rb
    config: Directory of board config file relative to openocd's
        scripts directory
    hla_serial: String containing board's hla_serial number (if board
    is an stm32 board)
    tty_port: String that is the path to the tty port which board's
        UART outputs to
    tty: String of file descriptor for tty_port
  """

  __metaclass__ = ABCMeta  # This is an Abstract Base Class (ABC)

  def __init__(self, board, module, hla_serial=None):
    """Initializes a board object with given attributes.

    Args:
      board: String containing board name
      module: String of the test module you are building,
        i.e. gpio, timer, etc.
      hla_serial: Serial number if board's adaptor is an HLA

    Raises:
      RuntimeError: Board is not supported
    """
    if board not in OPENOCD_CONFIGS:
      msg = 'OpenOcd configuration not found for ' + board
      raise RuntimeError(msg)
    if board not in FLASH_OFFSETS:
      msg = 'Flash offset not found for ' + board
      raise RuntimeError(msg)
    self.board = board
    self.flash_offset = FLASH_OFFSETS[self.board]
    self.openocd_config = OPENOCD_CONFIGS[self.board]
    self.module = module
    self.hla_serial = hla_serial
    self.tty_port = None
    self.tty = None

  def reset_log_dir(self):
    """Reset log directory."""
    if os.path.isdir(self.log_dir):
      shutil.rmtree(self.log_dir)
    os.makedirs(self.log_dir)

  @staticmethod
  def get_stlink_serials():
    """Gets serial numbers of all st-link v2.1 board attached to host.

    Returns:
      List of serials
    """
    usb_args = ['lsusb', '-v', '-d', '0x0483:0x374b']
    usb_process = sp.Popen(usb_args, stdout=sp.PIPE, shell=False)
    st_link_info = usb_process.communicate()[0]
    st_serials = []
    for line in st_link_info.split('\n'):
      if 'iSerial' not in line:
        continue
      words = line.split()
      if len(words) <= 2:
        continue
      st_serials.append(words[2].strip())
    return st_serials

  @abstractmethod
  def get_serial(self):
    """Subclass should implement this."""
    pass

  def send_open_ocd_commands(self, commands):
    """Send a command to the board via openocd.

    Args:
      commands: A list of commands to send

    Returns:
      True if execution is successful or False otherwise.
    """
    args = ['openocd', '-s', OCD_SCRIPT_DIR,
            '-f', self.openocd_config, '-c', 'hla_serial ' + self.hla_serial]

    for cmd in commands:
      args += ['-c', cmd]
    args += ['-c', 'shutdown']

    rv = 1
    with open(self.openocd_log, 'a') as output:
      rv = sp.call(args, stdout=output, stderr=sp.STDOUT)

    if rv != 0:
      self.dump_openocd_log()

    return rv == 0

  def dump_openocd_log(self):
    with open(self.openocd_log) as log:
      print log.read()

  def build(self, ec_dir):
    """Builds test suite module for board.

    Args:
      ec_dir: String of the ec directory path

    Returns:
      True if build is successful or False otherwise.
    """
    cmds = ['make',
            '--directory=' + ec_dir,
            'BOARD=' + self.board,
            'CTS_MODULE=' + self.module,
            '-j']

    rv = 1
    with open(self.build_log, 'a') as output:
      rv = sp.call(cmds, stdout=output, stderr=sp.STDOUT)

    if rv != 0:
      self.dump_build_log()

    return rv == 0

  def dump_build_log(self):
    with open(self.build_log) as log:
      print log.read()

  def flash(self, image_path):
    """Flashes board with most recent build ec.bin."""
    cmd = ['reset_config connect_assert_srst',
           'init',
           'reset init',
           'flash write_image erase %s %s' % (image_path, self.flash_offset)]
    return self.send_open_ocd_commands(cmd)

  def to_string(self):
    s = ('Type: Board\n'
         'board: ' + self.board + '\n'
         'hla_serial: ' + self.hla_serial + '\n'
         'openocd_config: ' + self.openocd_config + '\n'
         'tty_port: ' + self.tty_port + '\n'
         'tty: ' + str(self.tty) + '\n')
    return s

  def reset(self):
    """Reset then halt board."""
    return self.send_open_ocd_commands(['init', 'reset halt'])

  def setup_tty(self):
    """Call this before calling read_tty for the first time.

    This is not in the initialization because caller only should call
    this function after serial numbers are setup
    """
    self.get_serial()
    self.reset()
    self.identify_tty_port()

    tty = None
    try:
      tty = self.open_tty()
    except (IOError, OSError):
      raise ValueError('Unable to read ' + self.board + '. If you are running '
                       'cat on a ttyACMx file, please kill that process and '
                       'try again')
    self.tty = tty

  def read_tty(self, max_boot_count=1):
    """Read info from a serial port described by a file descriptor.

    Args:
      max_boot_count: Stop reading if boot count exceeds this number

    Returns:
      result: characters read from tty
      boot: boot counts
    """
    buf = []
    line = []
    boot = 0
    while True:
      if select.select([self.tty], [], [], 1)[0]:
        c = os.read(self.tty, 1)
      else:
        break
      line.append(c)
      if c == '\n':
        l = ''.join(line)
        buf.append(l)
        if REBOOT_MARKER in l:
          boot += 1
        line = []
        if boot > max_boot_count:
          break

    l = ''.join(line)
    buf.append(l)
    result = ''.join(buf)

    return result, boot

  def identify_tty_port(self):
    """Saves this board's serial port."""
    dev_dir = '/dev'
    id_prefix = 'ID_SERIAL_SHORT='
    com_devices = [f for f in os.listdir(dev_dir) if f.startswith('ttyACM')]

    for device in com_devices:
      self.tty_port = os.path.join(dev_dir, device)
      properties = sp.check_output(
          ['udevadm', 'info', '-a', '-n', self.tty_port, '--query=property'])
      for line in [l.strip() for l in properties.split('\n')]:
        if line.startswith(id_prefix):
          if self.hla_serial == line[len(id_prefix):]:
            return

    # If we get here without returning, something is wrong
    raise RuntimeError('The device dev path could not be found')

  def open_tty(self):
    """Read available bytes from device dev path."""
    fd = os.open(self.tty_port, os.O_RDONLY)
    flag = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, flag | os.O_NONBLOCK)
    return fd


class TestHarness(Board):
  """Subclass of Board representing a Test Harness.

  Attributes:
    serial_path: Path to file containing serial number
  """

  def __init__(self, board, module, log_dir, serial_path):
    """Initializes a board object with given attributes.

    Args:
      board: board name
      module: module name
      log_dir: Directory where log file is stored
      serial_path: Path to file containing serial number
    """
    Board.__init__(self, board, module)
    self.log_dir = log_dir
    self.openocd_log = os.path.join(log_dir, 'openocd_th.log')
    self.build_log = os.path.join(log_dir, 'build_th.log')
    self.serial_path = serial_path
    self.reset_log_dir()

  def get_serial(self):
    """Loads serial number from saved location."""
    if self.hla_serial:
      return  # serial was already loaded
    try:
      with open(self.serial_path, mode='r') as ser_f:
        self.hla_serial = ser_f.read()
        return
    except IOError:
      msg = ('Your TH board has not been identified.\n'
             'Connect only TH and run the script --setup, then try again.')
      raise RuntimeError(msg)

  def save_serial(self):
    """Saves the TH serial number to a file."""
    serials = Board.get_stlink_serials()
    if len(serials) > 1:
      msg = ('There are more than one test board connected to the host.'
             '\nConnect only the test harness and remove other boards.')
      raise RuntimeError(msg)
    if len(serials) < 1:
      msg = ('No test boards were found.'
             '\nTry to run the script outside chroot.')
      raise RuntimeError(msg)

    serial = serials[0]
    serial_dir = os.path.dirname(self.serial_path)
    if not os.path.exists(serial_dir):
      os.makedirs(serial_dir)
    with open(self.serial_path, mode='w') as ser_f:
      ser_f.write(serial)
      self.hla_serial = serial

    print 'Your TH serial', serial, 'has been saved as', self.serial_path
    return


class DeviceUnderTest(Board):
  """Subclass of Board representing a DUT board.

  Attributes:
    th: Reference to test harness board to which this DUT is attached
  """

  def __init__(self, board, th, module, log_dir, hla_ser=None):
    """Initializes a DUT object.

    Args:
      board: String containing board name
      th: Reference to test harness board to which this DUT is attached
      module: module name
      log_dir: Directory where log file is stored
      hla_ser: Serial number if board uses an HLA adaptor
    """
    Board.__init__(self, board, module, hla_serial=hla_ser)
    self.th = th
    self.log_dir = log_dir
    self.openocd_log = os.path.join(log_dir, 'openocd_dut.log')
    self.build_log = os.path.join(log_dir, 'build_dut.log')
    self.reset_log_dir()

  def get_serial(self):
    """Get serial number.

    Precondition: The DUT and TH must both be connected, and th.hla_serial
    must hold the correct value (the th's serial #)

    Raises:
      RuntimeError: DUT isn't found or multiple DUTs are found.
    """
    if self.hla_serial is not None:
      # serial was already set ('' is a valid serial)
      return

    serials = Board.get_stlink_serials()
    dut = [s for s in serials if self.th.hla_serial != s]

    # If len(dut) is 0 then your dut doesn't use an st-link device, so we
    # don't have to worry about its serial number
    if  len(dut) != 1:
      msg = ('Your TH serial number is incorrect, or your have'
             ' too many st-link devices attached.')
      raise RuntimeError(msg)

    # Found your other st-link device serial!
    self.hla_serial = dut[0]
    return
