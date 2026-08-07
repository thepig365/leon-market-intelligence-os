on run
	launchTraderWorkstation()
end run

on open location theURL
	launchTraderWorkstation()
end open location

on launchTraderWorkstation()
	set traderWorkstationPath to (POSIX path of (path to home folder)) & "Applications/Trader Workstation/Trader Workstation.app"
	try
		do shell script "/usr/bin/test -d " & quoted form of traderWorkstationPath
	on error
		display alert "Trader Workstation is not installed" message "Expected TWS at ~/Applications/Trader Workstation/Trader Workstation.app."
		return
	end try
	do shell script "/usr/bin/open " & quoted form of traderWorkstationPath
end launchTraderWorkstation
