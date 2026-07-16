# -*- coding: utf-8 -*-

# DEPENDENCIES --------------------------------------------------------------- #
from re import sub, search
from subprocess import run
from threading import Lock
from json import load, dump
from datetime import datetime
from os import path, getenv, makedirs
from socket import socket, gethostbyname, getservbyport, AF_INET, SOCK_STREAM, gaierror
from concurrent.futures import ThreadPoolExecutor, as_completed

# external
from requests import get
from bs4 import BeautifulSoup
from colorama import Fore, Style
from dotenv import load_dotenv
from tqdm import tqdm
from rich.console import Console
from rich.table import Table
from rich import box

# custom
from modules.custom_logger import exception
# ---------------------------------------------------------------------------- #

# LOGIC ---------------------------------------------------------------------- #
class PortScanner:
	def __init__(self):
		"""
			initialize scanner with default settings and environment
		"""
		super().__init__()
		load_dotenv()

		# initialize core components for port scanning
		self.descriptions = {} # store service descriptions from wiki
		self.lock = Lock()     # thread-safe lock for counter protection

		self.defaultPorts = [  # common ports to scan if user selects default option
			21, 22, 23, 25, 38, 43, 80, 109, 110, 115, 118, 119, 143,
			194, 220, 443, 540, 585, 591, 1112, 1433, 1443, 3128, 3197,
			3306, 4000, 4333, 5100, 5432, 6669, 8000, 8080, 9014, 9200
		]

		self.console = Console() # rich console for formatted output

		self.showBanner()
		self.handleCommands()

	def showBanner(self):
		"""
			display application banner with colored text and information
		"""
		banner = f"""{Fore.YELLOW}
 			::::    ::: :::::::::   ::::::::      :::     :::::::::   ::::::::  :::::::::  
			:+:+:   :+: :+:    :+: :+:    :+:    :+:      :+:    :+: :+:    :+: :+:    :+: 
			:+:+:+  +:+ +:+    +:+        +:+   +:+ +:+   +:+    +:+        +:+ +:+    +:+ 
			+#+ +:+ +#+ +#++:++#:      +#++:   +#+  +:+   +#++:++#+      +#++:  +#++:++#:  
			+#+  +#+#+# +#+    +#+        +#+ +#+#+#+#+#+ +#+               +#+ +#+    +#+ 
			#+#   #+#+# #+#    #+# #+#    #+#       #+#   #+#        #+#    #+# #+#    #+# 
			###    #### ###    ###  ########        ###   ###         ########  ###    ### 
			{Fore.RED}
			[!] → DISCLAIMER

			{Fore.YELLOW}{getenv("DISCLAIMER")}

			[?] → Enter {Fore.RED}help{Fore.YELLOW} for more information, or just {Fore.RED}start{Fore.YELLOW} to scan
		{Style.RESET_ALL}"""

		for line in banner.split("\n"):
			print(line.strip())

	def handleCommands(self):
		"""
			handle user input commands for navigation and control
		"""
		command = input(f"{Fore.YELLOW}Command: {Style.RESET_ALL}").strip().lower()

		if command == "start":
			self.startScan()
		elif command == "help":
			self.showHelp()
		elif command == "clear":
			run("cls", shell = True)

			self.showBanner()
			self.handleCommands()
		elif command == "":
			print(f"{Fore.RED}[!] Please enter a command{Style.RESET_ALL}")
			self.handleCommands()
		elif command == "exit":
			quit()
		else:
			print(f"{Fore.RED}[!] Invalid command{Style.RESET_ALL}")
			self.handleCommands()

	def fetchServiceInfo(self, dataFile = "./res/data/descriptions-of-services.json"):
		"""
			fetch and parse service descriptions from wiki or use cached data.
			uses exception handling to ensure robustness against network issues.
		"""
		def parseData():
			"""
				scrape service info from wiki page and save to cache
			"""
			try:
				# realistic request headers and cookies for wikipedia
				response = get(
					"https://en.wikipedia.org/wiki/List_of_TCP_and_UDP_port_numbers?lang=en",

					headers = {
						"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
					},

					timeout = 5
				)

				# check if response is successful
				if response.status_code != 200:
					print(f"\n{Fore.RED}[!] Wikipedia returned status code {response.status_code}{Style.RESET_ALL}")
					print(f"{Fore.YELLOW}[?] Please try again{Style.RESET_ALL}\n")

					self.handleCommands()
					return

				soup = BeautifulSoup(response.text, "html.parser")

				# find all relevant tables on the page
				tables = soup.find_all("table", class_ = "wikitable sortable collapsible")

				for table in tables:
					rows = table.find_all("tr") # get all rows in table

					for row in rows:
						cols = row.find_all("td") # get columns in row

						# determine column count based on row length
						colCount = 5 if len(cols) == 6 else 4

						# process only rows with enough columns
						if len(cols) > colCount:
							# extract port number using regex
							port = search(r"^\d{1,5}(?:-\d{1,5})?", cols[0].text.strip())

							# extract description and clean it
							desc = cols[colCount].text.strip()
							# remove all [number] references like [49][50]
							desc = sub(r"\[\d+\]", "", desc)
							# remove any remaining square brackets content
							desc = sub(r"\[[^\]]*\]", "", desc).strip()
							# remove trailing period if exists
							desc = desc[:-1] if (desc and desc[-1] == ".") else desc

							# store the extracted information
							if port:
								self.descriptions[port.group()] = desc

				# create directory if not exists
				try:
					makedirs(path.dirname(dataFile), exist_ok = True)
				except OSError as e:
					exception(e)

				# save the collected data to a file
				with open(dataFile, "w") as f:
					dump(self.descriptions, f)
			except Exception as e:
				exception(e)

				print(f"{Fore.RED}[!] Failed to fetch service info from Wikipedia{Style.RESET_ALL}")
				print(f"{Fore.YELLOW}[?] Please try again{Style.RESET_ALL}\n")

				self.handleCommands()
				return

		# load cached data if available, otherwise parse fresh
		if path.exists(dataFile) and path.getsize(dataFile) != 0:
			try:
				with open(dataFile, "r") as f:
					self.descriptions = load(f)
			except Exception as e:
				exception(e)

				print(f"{Fore.YELLOW}[!] Trying to fetch fresh data from Wikipedia...{Style.RESET_ALL}")
				parseData()
		else:
			parseData()

	def scanPort(self, host, port):
		"""
			scan a single port on a target host and return service information.

			args:
				host (str): the hostname or ip address to scan
				port (int): the port number to scan

			returns:
				tuple: (port, host, service, description) if port is open
				none: if port is closed or filtered
		"""
		try:
			# create tcp socket with 0.5s timeout
			sock = socket(AF_INET, SOCK_STREAM)
			sock.settimeout(0.5)

			# attempt connection
			if sock.connect_ex((str(host), int(port))) == 0:
				try:
					service = getservbyport(int(port)) # get service name
				except OSError:
					service = "unknown" # fallback if service lookup fails

				# get description from cache or use default
				description = self.descriptions.get(str(port), "no description available")
				sock.close()

				return (port, host, service, description)
			else:
				sock.close()
				return None
		except Exception as e:
			exception(e, f"Error scanning port {port} on {host}")
			return None

	def processPortRange(self, portRangeInput):
		"""
			process user input for port range selection.

			args:
				portrangeinput (str): user input for port range

			returns:
				range/list: ports to scan based on user input
		"""
		if not portRangeInput or portRangeInput.lower() == "default":
			# use default ports if no input or 'default' specified
			return self.defaultPorts

		elif portRangeInput == "1":
			# single port mode - ask user for specific port
			try:
				singlePort = int(input(f"\n{Fore.YELLOW}Port to scan: {Style.RESET_ALL}").strip())

				if 1 <= singlePort <= 65535:
					return [singlePort]
				else:
					print(f"{Fore.RED}[!] Invalid port number. Using default ports{Style.RESET_ALL}")
					return self.defaultPorts
			except ValueError:
				print(f"{Fore.RED}[!] Invalid port number. Using default ports{Style.RESET_ALL}")
				return self.defaultPorts

		elif portRangeInput == "2":
			# full port range - scan all ports from 1 to 65535
			return range(1, 65536)

		elif "-" in portRangeInput:
			# custom port range - parse start and end values
			try:
				start, end = map(int, portRangeInput.split("-"))

				if 1 <= start <= end <= 65535:
					return range(start, end + 1)
				else:
					print(f"{Fore.RED}[!] Invalid port range. Using default ports{Style.RESET_ALL}")
					return self.defaultPorts
			except ValueError:
				print(f"{Fore.RED}[!] Invalid port range format. Using default ports{Style.RESET_ALL}")
				return self.defaultPorts

		else:
			# handle unexpected input
			print(f"{Fore.RED}[!] Unrecognized port range option. Using default ports{Style.RESET_ALL}")
			return self.defaultPorts

	def startScan(self):
		"""
			start the scanning process based on user input
		"""
		self.descriptions = {} # reset descriptions
		self.fetchServiceInfo() # load service descriptions

		# get target host
		hostInput = input(f"\n{Fore.YELLOW}Hostname or IP: {Style.RESET_ALL}").strip()

		# resolve hostname to ip
		try:
			host = gethostbyname(hostInput)
		except gaierror:
			print(f"{Fore.RED}[!] Hostname or IP could not be resolved. Try again{Style.RESET_ALL}")

			self.handleCommands()
			return

		# configure port range
		portRangeInput = input(f"\n{Fore.YELLOW}Port range (default/1-65535/[start]-[end]): {Style.RESET_ALL}").strip()
		ports = self.processPortRange(portRangeInput)

		# start scan
		startTime = datetime.now()
		print(f"\n{Fore.GREEN}[!] START - {str(startTime.strftime('%H:%M:%S'))}{Style.RESET_ALL}\n")

		foundServices = [] # store found services

		# create progress bar for port scanning
		portProgress = tqdm(
			total = len(ports),
			desc = "Scanning ports",
			unit = "",
			dynamic_ncols = True,
			bar_format = "{l_bar}{bar}| {n_fmt}/{total_fmt} {unit}"
		)

		# scan ports
		with ThreadPoolExecutor(max_workers = 100) as executor:
			futures = {executor.submit(self.scanPort, host, port): port for port in ports}

			for future in as_completed(futures):
				result = future.result()
				portProgress.update(1)

				if result:
					foundServices.append(result)

		portProgress.close()
		print()

		# display results
		if foundServices:
			table = Table(
				show_header = True,
				header_style = "bold",
				box = box.SQUARE
			)

			table.add_column("№", style = "bold", width = 4)
			table.add_column("Port", width = 8)
			table.add_column("Service", width = 16)
			table.add_column("Description")

			for idx, (port, _, service, description) in enumerate(sorted(foundServices, key = lambda x: x[0]), 1):
				table.add_row(str(idx), str(port), service, description)

			self.console.print(table)
		else:
			print(f"{Fore.YELLOW}[!] No open ports found{Style.RESET_ALL}")

		# print scan summary
		endTime = datetime.now()
		duration = round((endTime - startTime).total_seconds(), 2)

		print(f"\n{Fore.GREEN}[!] END - {endTime.strftime('%H:%M:%S')} ({duration}s){Style.RESET_ALL}\n")

		input("Press Enter to continue...")

		run("cls", shell = True)
		self.showBanner()
		self.handleCommands()

	def showHelp(self):
		"""
			display help documentation explaining usage instructions
		"""
		output = f"""
			{Fore.YELLOW}[Description]{Style.RESET_ALL}
			• {getenv("DESCRIPTION")}

			• Version: {getenv("APP_VERSION")}
	 		• Author: {getenv("AUTHOR")}

			{Fore.YELLOW}[Available Commands]{Style.RESET_ALL}
			• help         → Show this help center
			• clear        → Clear the console
			• start        → Begin scanning
			• exit         → Close the program

			{Fore.YELLOW}[Host/IP Input]{Style.RESET_ALL}
			• domain name       → example.com
			• single IP         → 192.168.1.1

			{Fore.YELLOW}[Port Ranges]{Style.RESET_ALL}
			• default           → press Enter (uses built-in list of common ports)
			• single port       → type '1' and enter 80
			• full port range   → type '2' (scans ports 1–65535)
			• custom range      → type like '80-443'

			{Fore.YELLOW}[Examples]{Style.RESET_ALL}
			• Scan Google's web ports → google.com → default
			• Scan all ports on localhost → 127.0.0.1 → 2
			• Scan HTTP(S) range → 192.168.1.1 → 80-443
		{Style.RESET_ALL}"""

		for line in output.split("\n"):
			print(line.strip())

		self.handleCommands()
# ---------------------------------------------------------------------------- #

# FINISH --------------------------------------------------------------------- #
PortScanner()
# ---------------------------------------------------------------------------- #