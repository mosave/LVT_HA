@echo off
set FN=LVT_HA
set DIR="K:\Archives\SmartHome"

7z a -r "%DIR%\%FN%.New.7z" \\wsl$\docker-desktop-data\version-pack-data\community\docker\volumes\core-9f57a2833957335ae13e29b74397db11\_data\core\homeassistant\components\lvt\*.* -xr!.git -xr!.vs -xr!.venv*  -xr!__pycache__
if errorlevel 1 goto error


ren "%DIR%\%FN%.7z" "%FN%.Old.7z"
ren "%DIR%\%FN%.New.7z" "%FN%.7z"
del "%DIR%\%FN%.Old.7z"

goto :exit

:error
del "%DIR%\%FN%.New.7z"

:exit
