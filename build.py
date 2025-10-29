# -*- coding: utf-8 -*-

# DEPENDENCIES --------------------------------------------------------------- #
import os
from subprocess import run

# external
from dotenv import load_dotenv
# ---------------------------------------------------------------------------- #

# LOGIC ---------------------------------------------------------------------- #
load_dotenv()

author = os.getenv("AUTHOR")
appName = os.getenv("APP_NAME")
appVersion = os.getenv("APP_VERSION")
description = os.getenv("DESCRIPTION")
command = [
  ".venv\\Scripts\\nuitka.cmd",

  # compilation mode options
  "--standalone", # create self-contained distribution
  "--onefile", # create single executable

  # compiler options
  "--mingw64", # use mingw64 compiler

  # output configuration
  f"--output-dir=dist", # build directory
  f"--output-filename={appName}", # final executable name

  # windows metadata
  f"--product-name={appName}", # product name
  f"--file-version={appVersion}", # file version
  f"--product-version={appVersion}", # product version
  f"--copyright={author}", # copyright info
  f"--file-description={description}", # file description

  # dependency control
	f"--include-data-file={os.path.abspath('.env')}=.env", # include encrypted file
	"--include-package=urllib3", # follow all urllib3 imports recursively

  # optimization
  "--enable-plugin=upx", # enable upx compression
  f"--upx-binary={os.path.abspath('tools/upx')}", # custom upx path

  # debugging and reporting
  "--show-progress", # show compilation progress
  "--show-modules", # display included modules
  "--report=logs/compilation-report.xml", # generate build report

  "main.py"
]

run(command, shell = True)
# ---------------------------------------------------------------------------- #