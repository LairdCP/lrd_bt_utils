#!/usr/bin/python3
import sys
import serial
import binascii
import errno
import time

SERIAL_TIMEOUT = 1
MAX_UPLOAD_SIZE = 32

EXIT_CODE_SUCCESS = 0

RETURN_CODE_SIZE = 2
RETURN_CODE_SUCCESS = '00'
RETURN_CODE_SCRIPT_FOUND = '06'

UPLOAD_OPEN_FILE_CMD = 'AT+FOW "{}"\r\n'
UPLOAD_WRITE_DATA_CMD = 'AT+FWRH "{}"\r\n'
UPLOAD_CLOSE_FILE_CMD = 'AT+FCL\r\n'
LIST_FILES_CMD = 'AT+DIR\r\n'
DELETE_FILE_CMD = 'AT+DEL "{}"\r\n'
DELETE_FILE_FORCE_CMD = 'AT+DEL "{}" +\r\n'
RENAME_FILE_CMD = 'AT+REN "{}" "{}"\r\n'

PYTHON3 = sys.version_info >= (3, 0)

def write_to_comm(serial, bytes):
	ecode = EXIT_CODE_SUCCESS

	# Write the provided bytes to the serial port
	serial.write(bytes)

	# Clear the first newline
	serial.readline()

	# Get the return code
	return_code = serial.read(RETURN_CODE_SIZE).strip().decode('utf-8')
	if return_code != RETURN_CODE_SUCCESS:
		# Get the error code
		error_code = serial.readline().strip().decode('utf-8')
		sys.stderr.write('{} {}'.format(return_code, error_code))
		ecode = errno.EPERM

	return ecode

exit_code = EXIT_CODE_SUCCESS	# Success (for now)
if len(sys.argv) >= 4:
	port = sys.argv[1]
	baudrate = int(sys.argv[2])
	cmd = sys.argv[3]

	# Open the COM port to the Bluetooth adapter
	ser = serial.Serial(port, baudrate, timeout=SERIAL_TIMEOUT)

	# Send break, flush the input, delay for BL654 reset
	ser.send_break()
	ser.reset_input_buffer()
	time.sleep(3)

	# Execute the given command
	if cmd == 'upload':
		if len(sys.argv) == 6:
			file_name = sys.argv[4]
			file_path = sys.argv[5]

			try:
				f = open(file_path,'rb')
			except IOError as i:
				# Failed to open the file
				sys.stderr.write('{}'.format(i))
				exit_code = errno.ENOENT
			else:
				if f.mode == 'rb':
					# Open the file at the device
					port_cmd = UPLOAD_OPEN_FILE_CMD.format(file_name)
					port_cmd_bytes = bytearray(port_cmd, 'utf-8')
					exit_code = write_to_comm(ser, port_cmd_bytes)
					if exit_code == EXIT_CODE_SUCCESS:
						# Read the file (in bytes)
						bytes = f.read(MAX_UPLOAD_SIZE)
						while bytes:
							# Convert bytes to hex
							if PYTHON3:
								bytes_hex = bytes.hex()
							else:
								bytes_hex = binascii.hexlify(bytes)

							# Write this chunk of bytes to the BT module
							port_cmd = UPLOAD_WRITE_DATA_CMD.format(bytes_hex)
							port_cmd_bytes = bytearray(port_cmd, 'utf-8')
							exit_code = write_to_comm(ser, port_cmd_bytes)
							if exit_code == EXIT_CODE_SUCCESS:
								# Get the next chunk of bytes
								bytes = f.read(MAX_UPLOAD_SIZE)
							else:
								bytes = None

						if exit_code == EXIT_CODE_SUCCESS:
							# Close the file at the device
							port_cmd_bytes = bytearray(UPLOAD_CLOSE_FILE_CMD, 'utf-8')
							exit_code = write_to_comm(ser, port_cmd_bytes)

				# Close the local file
				f.close()
		else:
			print('usage: btpa_utility <port> <baudrate> upload <new name> <path to file>')
	elif cmd == 'list':
		port_cmd_bytes = bytearray(LIST_FILES_CMD, 'utf-8')
		ser.write(port_cmd_bytes)

		# Clear the first newline
		ser.readline()

		# Get the return code
		return_code = ser.read(RETURN_CODE_SIZE).strip().decode('utf-8')
		while return_code != '':
			if return_code == RETURN_CODE_SUCCESS:
				# Clear the serial line to look for more scripts
				ser.readline()
			elif return_code == RETURN_CODE_SCRIPT_FOUND:
				# Print the script name that was found
				script = ser.readline().strip().decode('utf-8')
				print(script)
			else:
				# Failed to get the script list
				sys.stderr.write(return_code)
				exit_code = errno.EPERM
				break

			return_code = ser.read(RETURN_CODE_SIZE).strip().decode('utf-8')
	elif cmd == 'delete':
		if len(sys.argv) >= 5:
			file = sys.argv[4]

			# Collect any delete options that are on the command line
			option = ''
			if len(sys.argv) == 6:
				option = sys.argv[5]

			if option == '--force':
				port_cmd = DELETE_FILE_FORCE_CMD.format(file)
			else:
				port_cmd = DELETE_FILE_CMD.format(file)
			port_cmd_bytes = bytearray(port_cmd, 'utf-8')
			exit_code = write_to_comm(ser, port_cmd_bytes)
		else:
			print('usage: btpa_utility <port> <baudrate> delete <filename> [--force]')
	elif cmd == 'rename':
		if len(sys.argv) == 6:
			old = sys.argv[4]
			new = sys.argv[5]
			port_cmd = RENAME_FILE_CMD.format(old, new)
			port_cmd_bytes = bytearray(port_cmd, 'utf-8')
			exit_code = write_to_comm(ser, port_cmd_bytes)
		else:
			print('usage: btpa_utility <port> <baudrate> rename <current filename> <new filename>')
	else:
		print('Invalid command: {}'.format(cmd))
else:
	print('usage: btpa_utility <port> <baudrate> <command>')

sys.exit(exit_code)
