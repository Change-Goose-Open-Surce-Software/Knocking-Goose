@echo off
:: Install dependencies
echo Installing dependencies...
python -m pip install --upgrade pip
pip install playsound pywinusb

:: Copy files to the appropriate locations
echo Copying files...
copy knock.py C:\Knock\knock.py
copy knock.desktop C:\Knock\knock.desktop

:: Add to autostart
echo Adding to autostart...
copy knock.desktop "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\"

echo Installation completed successfully.