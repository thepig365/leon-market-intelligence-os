on run
	launchTraderWorkstation()
end run

on open location theURL
	launchTraderWorkstation()
end open location

on launchTraderWorkstation()
	try
		do shell script "/usr/bin/open -a " & quoted form of "Trader Workstation"
	on error errorMessage
		display alert "Trader Workstation could not be opened" message "macOS could not locate the registered Trader Workstation application. " & errorMessage
	end try
end launchTraderWorkstation
