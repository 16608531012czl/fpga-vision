param(
 [ValidateSet('verify','sim','full','test','preview','gui','system','synth','bit','package')][string]$Step='verify',
 [string]$VivadoRoot='C:\Users\CHENZHELONG\Desktop\diansai\Vivado\2018.3',
 [string]$PythonExe='C:\fpga\vision\host_py313\Scripts\python.exe'
)
$ErrorActionPreference='Stop'
$root=$PSScriptRoot
$vivado=Join-Path $VivadoRoot 'bin\vivado.bat'
function Check-Exit([string]$label) {if($LASTEXITCODE -ne 0){throw "$label failed (exit $LASTEXITCODE)"}}
function Python-Run([string[]]$Arguments) {& $PythonExe @Arguments;Check-Exit 'Python'}
function Vivado-Run([string]$Name,[string[]]$Extra=@(),[string]$ScriptFolder='vivado') {
 $script=(Join-Path $root "$ScriptFolder\$Name.tcl").Replace('\','/')
 $log=(Join-Path $root "reports\$Name.log").Replace('\','/')
 $journal=(Join-Path $root "reports\$Name.jou").Replace('\','/')
 $dir=Join-Path $root "build\tool_runs\$Name"
 New-Item -ItemType Directory -Force -Path $dir | Out-Null
 Push-Location -LiteralPath $dir
 try {& $vivado -mode batch -source $script -notrace -log $log -journal $journal @Extra;Check-Exit $Name} finally {Pop-Location}
 if(Select-String -LiteralPath $log -Pattern '^(ERROR:|Fatal:)' -Quiet){throw "Vivado error in $log"}
 if(-not(Select-String -LiteralPath $log -SimpleMatch 'PASS:' -Quiet)){throw "Missing completion marker in $log"}
}
Push-Location -LiteralPath $root
try {
 if(-not(Test-Path -LiteralPath $PythonExe)){throw "Python missing: $PythonExe"}
 if($Step -in @('verify','sim')){Python-Run -Arguments @('tools/verify.py','--vivado',$VivadoRoot)}
 if($Step -in @('verify','full')){Python-Run -Arguments @('tools/verify.py','--full','--vivado',$VivadoRoot)}
 if($Step -in @('verify','test')){Python-Run -Arguments @('tools/test_software.py')}
 if($Step -in @('verify','preview')){Python-Run -Arguments @('software/preview.py','--out','reports/preview')}
 if($Step -in @('verify','gui')){Vivado-Run -Name 'create_sim' -Extra @('-tclargs','run')}
 if($Step -in @('verify','system')) {
  if(Test-Path -LiteralPath 'build\system\visual_aid_v3.xpr'){Vivado-Run 'validate_system'}
  else{Vivado-Run 'create_system'}
 }
 if($Step -in @('verify','synth')){Vivado-Run 'synth_core'}
 if($Step -eq 'bit'){
  $full=Get-Content -LiteralPath 'reports\xsim_full.json' -Raw | ConvertFrom-Json
  foreach($file in Get-ChildItem -LiteralPath 'rtl' -Filter '*.sv'){
   $key='rtl/'+$file.Name
   if((Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLower() -ne $full.sha256.$key){throw "RTL changed after full simulation: $key"}
  }
  Python-Run -Arguments @('tools/package_board.py','--snapshot')
  Vivado-Run 'implement_system'
  Vivado-Run -Name 'review_routed' -ScriptFolder 'tools'
  Python-Run -Arguments @('tools/check_original.py')
  Python-Run -Arguments @('tools/package_board.py')
 }
 if($Step -eq 'package'){
  $inspection=Join-Path $root 'reports\check_timing.rpt'
  $checkpoint=Join-Path $root 'build\verified_routed.dcp'
  if(!(Test-Path -LiteralPath $inspection) -or (Get-Item -LiteralPath $inspection).LastWriteTime -lt (Get-Item -LiteralPath $checkpoint).LastWriteTime){
   Vivado-Run -Name 'review_routed' -ScriptFolder 'tools'
  }
  Python-Run -Arguments @('tools/check_original.py')
  Python-Run -Arguments @('tools/package_board.py')
 }
 if($Step -eq 'verify'){
  Python-Run -Arguments @('tools/check_original.py')
  Python-Run -Arguments @('tools/summarize.py')
 }
} finally {Pop-Location}
