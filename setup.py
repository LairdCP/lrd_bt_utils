#!/usr/bin/env python

from setuptools import setup

setup(name='lrd-bt-utils',
      version='1.0',
      description='BTPA Firmware Loading Utilities',
      scripts=['btpa_utility.py', 'btpa_firmware_loader/btpa_firmware_loader.py'],
      py_modules=['btpa_firmware_loader/uwf_processor', 'btpa_firmware_loader/ig60_bl654_uwf_processor'],
     )
