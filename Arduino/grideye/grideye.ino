/*
 * 1-Wire RT - Fabio
 */
#include <OneWire.h>     
#include <OWGridEye.h>
#include <grideye_api_common.h>
#include <MAX4822.h>
#include <MAX11300Hex.h>
#include <MAX11300.h>
#include <ArduinoJson.h>

#define D_SCLK          13
#define D_MISO          12
#define D_MOSI          11
#define RLY_DRVR_CS     10
#define PIXI_CNVT       9
#define PIXI_CS         8
#define RLY_DRVR_SET    7
#define RLY_DRVR_RESET  6
#define PIXI_TIMER_INT  4
#define PIXI_INT        5

#define GRIDEYE             "GE"
#define LATCHING_RELAYS     "LR"
#define NON_LATCHING_RELAYS "NLR"
#define THERMISTOR_TEMP     "TEMP"
#define START_MARKER        '{'
#define END_MARKER          '}'

#define RECV_BUF_MAXSIZE 50
#define SEND_BUF_MAXSIZE 600

#define DEVICE_ID                 "ID"
#define DEVICE_TYPE               "TYPE"
#define DEVICE_TYPE_MRD130        1
#define DEVICE_TYPE_MRD130_MRD131 2

#define MY_DEVICE_ID              1

volatile boolean endMarkerFound = false;
volatile boolean startMarkerFound = false;

typedef struct {
  volatile uint8_t bytesRead;
  volatile char inputBuffer[RECV_BUF_MAXSIZE];
} SerialData;

using namespace OneWire;
using namespace RomCommands;

MAX4822 rly_drvr;
MAX11300 pixi;
DS2484 owm;
MultidropRomIterator selector(owm);
OWGridEye owGridEye(selector);

volatile boolean sendGEData;
volatile SerialData dataBuf;
volatile boolean ge_connected;

void setup_MAXREFDES130(void){
  rly_drvr.begin(D_MOSI, D_SCLK, RLY_DRVR_CS);
  pinMode(RLY_DRVR_SET, OUTPUT);
  digitalWrite(RLY_DRVR_SET, HIGH);
  pinMode(RLY_DRVR_RESET, OUTPUT);
  digitalWrite(RLY_DRVR_RESET, HIGH);
  pixi.begin(D_MOSI, D_MISO, D_SCLK, PIXI_CS, PIXI_CNVT);  
}

boolean setup_MAXREFDES131(void) {
  if ( owm.begin() == OneWireMaster::Success) {
    // init GridEye
    OneWireMaster::CmdResult owResult;
    SearchState searchState;
    DS2413 owSwitch(selector);

    if (owm.OWReset() == OneWireMaster::Success) {
      //Find DS2413
      searchState.findFamily(OWGridEye::DS2413_FAMILY_CODE);
      if ((OWNext(owm, searchState) == OneWireMaster::Success) &&
          (searchState.romId.familyCode() == OWGridEye::DS2413_FAMILY_CODE)) {
        //ensure DS28E17 and GridEye are connected to bus
        owSwitch.setRomId(searchState.romId);
        owSwitch.pioAccessWriteChAB(2);

        //let GridEye object know what the DS2413 ROM ID is
        owGridEye.setOWSwitchRomId(searchState.romId);

        //Find DS28E17
        searchState.findFamily(OWGridEye::DS28E17_FAMILY_CODE);
        if (( OWNext(owm, searchState) == OneWireMaster::Success) &&
            (searchState.romId.familyCode() == OWGridEye::DS28E17_FAMILY_CODE)) {
            //let GridEye object know what the DS28E17 ROM ID is
            owGridEye.setI2CBridgeRomId(searchState.romId);
            return (owGridEye.connectGridEye() == OWGridEye::Success);
        }
      } 
    } 
  }
  return false;
}

void setup()
{
  Serial.begin(115200);
  while (!Serial);
  
  Serial.println(F("IIT firmware boot."));

  setup_MAXREFDES130();
  ge_connected = setup_MAXREFDES131();

  delay(15000);

  // initialize Timer1
  cli();          // disable global interrupts
  TCCR1A = 0;     // set entire TCCR1A register to 0
  TCCR1B = 0;     // same for TCCR1B

  // set compare match register to desired timer count:
  OCR1A = 1562; // 100ms

  // turn on CTC mode:
  TCCR1B |= (1 << WGM12);

  // Set CS10 and CS12 bits for 1024 prescaler:
  TCCR1B |= (1 << CS10) | (1 << CS12);

  // enable timer compare interrupt:
  TIMSK1 |= (1 << OCIE1A);
  sei();          // enable global interrupts
  Serial.println(F("Boot completed."));
  delay(1);
}

ISR(TIMER1_COMPA_vect)
{
  sendGEData = true;
}

void loop() {
  if (sendGEData) {
    StaticJsonBuffer<SEND_BUF_MAXSIZE> jsonBuffer;
    JsonObject& root = jsonBuffer.createObject();

    root[DEVICE_ID] = MY_DEVICE_ID;
    root[DEVICE_TYPE] = DEVICE_TYPE_MRD130_MRD131;

    JsonArray& data = root.createNestedArray(GRIDEYE);
     
    if (ge_connected) {
        int16_t recvBuff[64];
        int sec_buf[64];
        if(owGridEye.gridEyeGetFrameTemperature(recvBuff) == OWGridEye::Success){ 
          memcpy(sec_buf,recvBuff,128);
          data.copyFrom(sec_buf);   
        }
    }
    root.printTo(Serial);
    delay(1);
    Serial.println();
    cli();
    sendGEData = false;
    sei();
  }
}

void parseData() {
  StaticJsonBuffer<RECV_BUF_MAXSIZE> jsonBuffer;
  JsonObject& data = jsonBuffer.parse((char *)&dataBuf.inputBuffer);
  if (data.containsKey(NON_LATCHING_RELAYS)) {
    uint8_t non_latching_relays_status = (uint8_t) data[NON_LATCHING_RELAYS];
    if(non_latching_relays_status==255){
      rly_drvr.set_all_relays(RLY_DRVR_SET);
    } else if(non_latching_relays_status==0){
      rly_drvr.reset_all_relays(RLY_DRVR_RESET);
    } else {
    for(uint8_t i=0;i<8;i++){
        if((non_latching_relays_status>>i)&1){
          rly_drvr.set_relay(static_cast<MAX4822::RelayChannel>(i+1));
        } else {
          rly_drvr.reset_relay(static_cast<MAX4822::RelayChannel>(i+1));
        }
      }
    }
  }
  if (data.containsKey(LATCHING_RELAYS)) {
    uint8_t latching_relays_status = (uint8_t)data[LATCHING_RELAYS];
    for(uint8_t i=0;i<3;i++){
      uint8_t bit_value=(latching_relays_status>>i)&1;
      pixi.gpio_write(static_cast<MAX11300::MAX11300_Ports>(i + 9), bit_value);
    }  
  }
  if (data.containsKey(GRIDEYE)) {
    if(data[GRIDEYE]==0){
      ge_connected=false;
    } else {
      ge_connected=true;
    }
  }
}

void serialEvent() {
  cli();
  while ((Serial.available() > 0) && (!endMarkerFound)) {
    char x = Serial.read();

    if (x == START_MARKER) {
      startMarkerFound = true;
      dataBuf.bytesRead = 0;
    } else if (x == END_MARKER) {
      if (startMarkerFound) {
        endMarkerFound = true;
        startMarkerFound = false;
        (dataBuf.inputBuffer)[dataBuf.bytesRead] = END_MARKER;
        parseData();
      }
    }

    if ((startMarkerFound) && (!endMarkerFound)) {
      (dataBuf.inputBuffer)[dataBuf.bytesRead] = x;
      dataBuf.bytesRead++;
      if (dataBuf.bytesRead == RECV_BUF_MAXSIZE) {
        // exceeding buffer size! ERROR! Discard input
        endMarkerFound = true;
        startMarkerFound = false;
        dataBuf.bytesRead = 0;
      }
    }
  }
  if (endMarkerFound) {
    memset(&dataBuf.inputBuffer, 0, RECV_BUF_MAXSIZE);
    endMarkerFound=false;
  }
  sei();
}

