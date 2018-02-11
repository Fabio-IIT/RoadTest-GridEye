# RoadTest-GridEye
Code for 1-Wire® Grid-EYE® Sensor w/Arduino-Compatible PCB RoadTest (https://www.element14.com/community/roadTestReviews/2414/l/1-wire-grid-eye-sensor-warduino-compatible-pcb-review)

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

Installation.

You need to have Arduino IDE installed, and Python 2.7, and all the respective libraries listed above.
To install the application you need to clone/download the repository locally, for example to clone the repository issue the command:

    git clone https://github.com/Fabio-IIT/RoadTest-GridEye

You need to build and upload the firmware for Arduino UNO first. Open the Arduino IDE and load the firmware sketch located under:

    ./RoadTest-GridEye/Arduino/grideye/grideye.ino

Build and upload onto your Arduino board.

Move under the directory:

    ./RoadTest-GridEye/RPi/

in the directory config there is the grideye.cfg configuration file for the application.
Edit the settings in the file according to your needs, then start the application by issuing the command:

    python ./server.py

Open your browser and point to http://RPi-IP-address:8080 to access the dashboard.

