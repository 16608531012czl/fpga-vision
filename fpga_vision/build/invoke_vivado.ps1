param(
    [Parameter(Mandatory=$true)][string]$Executable,
    [Parameter(Mandatory=$true)][string]$ScriptFile,
    [Parameter(Mandatory=$true)][string]$LogFile,
    [Parameter(Mandatory=$true)][string]$JournalFile,
    [Parameter(Mandatory=$true)][string]$OutputFile,
    [Parameter(Mandatory=$true)][string]$WorkingDirectory
)
$ErrorActionPreference = 'Stop'
Push-Location -LiteralPath $WorkingDirectory
try {
    # Let PowerShell launch the vendor batch file with native argument handling.
    # Do not replace Vivado's Tcl library or locale with Python's configuration.
    & $Executable -mode batch -source $ScriptFile -log $LogFile -journal $JournalFile 2>&1 |
        Out-File -LiteralPath $OutputFile -Encoding utf8
    $toolExitCode = $LASTEXITCODE
} finally {
    Pop-Location
}
exit $toolExitCode
