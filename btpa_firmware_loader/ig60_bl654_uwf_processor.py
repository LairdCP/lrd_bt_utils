import dbus
import struct
from uwf_processor import UwfProcessor
from uwf_processor import ERROR_REGISTER_DEVICE
from uwf_processor import UWF_OFFSET_ERASE_START_ADDR
from uwf_processor import UWF_OFFSET_ERASE_SIZE
from uwf_processor import COMMAND_ERASE_SECTOR
from uwf_processor import RESPONSE_ACKNOWLEDGE
from uwf_processor import RESPONSE_ACKNOWLEDGE_SIZE
from uwf_processor import ERROR_ERASE_BLOCKS

BT_BOOTLOADER_MODE = 0
BT_SMART_BASIC_MODE = 1

FUP_OPTION_CURRENT_ERASE_LEN_BYTES = 0x0000

class Ig60Bl654UwfProcessor(UwfProcessor):
	"""
	Class that encapsulates how to process UWF commands for an IG60
	BL654 module upgrade
	"""

	def __init__(self, port, baudrate):
		UwfProcessor.__init__(self, port, baudrate)

		# Setup the DBus connection to the device service
		self.bus = dbus.SystemBus()
		self.device_svc = dbus.Interface(self.bus.get_object('com.lairdtech.device.DeviceService',
			'/com/lairdtech/device/DeviceService'), 'com.lairdtech.device.public.DeviceInterface')

		# Expected registration values for an IG60 BL654
		self.expected_handle = 0
		self.expected_num_banks = 1
		self.expected_bank_algo = 1

	def enter_bootloader(self):
		success = False

		# Enter the bootloader via the Device Service
		if self.device_svc.SetBtBootMode(BT_BOOTLOADER_MODE) != 0:
			raise Exception('Failed to enter bootloader via smartBASIC and DBus')
		else:
			success = True

			# Clear the serial line before starting
			self.ser.readline()

		return success

	def process_command_register_device(self, file, data_length):
		error = None

		UwfProcessor.process_command_register_device(self, file, data_length)

		# Validate the registration data
		if self.handle == self.expected_handle and self.num_banks == self.expected_num_banks and self.bank_size > 0 and self.bank_algo == self.expected_bank_algo:
			self.registered = True
		else:
			error = ERROR_REGISTER_DEVICE.format('Unexpected registration data')
			self.registered = False

		return error

	def process_command_erase_blocks(self, file, data_length):
		"""
		In enhanced bootloader mode, if total erase size is factor of 64k, erase block size is 64k
		Else, erase block according to the sector size value from the the UWF file
		"""
		error = None
		erase_mode_64k = False
		erase_block_64k = 0x10000

		if self.synchronized and self.registered and self.sectors > 0 and self.sector_size > 0:
			# Get the UWF erase data
			erase_data = file.read(data_length)
			start = self.base_address + struct.unpack('<I', erase_data[:UWF_OFFSET_ERASE_START_ADDR])[0]
			size = struct.unpack('<I', erase_data[UWF_OFFSET_ERASE_START_ADDR:UWF_OFFSET_ERASE_SIZE])[0]

			# Check if 64k erase block size can be used
			if self.enhanced_mode and (size % erase_block_64k == 0):
				UwfProcessor.process_setting_set(self, FUP_OPTION_CURRENT_ERASE_LEN_BYTES, 0x2)
				erase_mode_64k = True

			if size < self.bank_size:
				erase_command = bytearray(COMMAND_ERASE_SECTOR, 'utf-8')
				while size > 0:
					erase_sector = struct.pack('<I', start)
					if erase_mode_64k:
						erase_block_size = struct.pack('<I',0x2)
						port_cmd_bytes = erase_command + erase_sector + erase_block_size
					else:
						port_cmd_bytes = erase_command + erase_sector
					response = self.write_to_comm(port_cmd_bytes, RESPONSE_ACKNOWLEDGE_SIZE)
					if response.decode('utf-8') != RESPONSE_ACKNOWLEDGE:
						error = ERROR_ERASE_BLOCKS.format('Non-ack to erase command')
						break
					if erase_mode_64k:
						start += erase_block_64k
						size -= erase_block_64k
					else:
						start += self.sector_size
						size -= self.sector_size
				else:
					self.erased = True
			else:
				error = ERROR_ERASE_BLOCKS.format('Erase block size > bank size')
		else:
			error = ERROR_ERASE_BLOCKS.format('Target platform, register device, or sector map commands not yet processed')

		return error

	def process_reboot(self):
		# Use the device service to return the bt_boot_mode to smartBASIC
		self.device_svc.SetBtBootMode(BT_SMART_BASIC_MODE)

		# Cleanup
		self.ser.close()
