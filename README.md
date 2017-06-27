# RoadTest-GridEye
Code for  1-Wire® Grid-EYE® Sensor w/Arduino-Compatible PCB RoadTest

This repository contains the code used for the element14 RoadTest "1-Wire® Grid-EYE® Sensor w/Arduino-Compatible PCB".
The RoadTest aimed at testin and reviewing the Maxim Reference Design boards MAXREFDES131# (1-Wire GridEYE sensor) and MAXREFDES130# (Building Automation Shield).
The "Arduino" directory contains the Arduino firmware source code. To compile, use the Arduino IDE, taking care of adding the following libraries:
- OneWire (https://github.com/MaximIntegratedRefDesTeam/OneWire)
- OWGridEye (https://github.com/MaximIntegratedRefDesTeam/OWGridEye)
- MAX11300 (https://github.com/MaximIntegratedRefDesTeam/MAX11300)
- MAX4822 (https://github.com/MaximIntegratedRefDesTeam/MAX4822)
- ArduinoJson

The RPi directory contains python source code for the server part.
The server code is written in Python 2.7, and used Numpy and Scipy packages for the calculations.
For the web server, you will need to install the Tornado package.