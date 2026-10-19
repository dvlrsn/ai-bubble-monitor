# Double-click entry for `python monitor.py review`: Claude checks today's headlines and
# suggests tripwires; you answer y/n before anything fires.
Set-Location (Split-Path -Parent $PSScriptRoot)
python monitor.py review
Read-Host "`nPress Enter to close"
