# Pyinstaller helper to avoid repeating args
function New-pyinstaller
{
    {
        param
        (
        [String]$exemode
        )
        pyinstaller --$exemode --distpath="dist.exe" --onefile --add-data="LICENSE;." .\RemoveWindowsLockScreenAds\RemoveWindowsLockScreenAds.py
        Move-Item -Force "dist.exe\RemoveWindowsLockScreenAds.exe" "dist.exe\RemoveWindowsLockScreenAds.$exemode.exe"
    }.GetNewClosure()
}
$function:global:do_pyinstaller = New-pyinstaller

Remove-Item -Force -Recurse dist, dist.exe, build
# Create standalone executables
do_pyinstaller noconsole
do_pyinstaller console

# Create pypi dist
python setup.py sdist bdist_wheel

