#include <EEPROM.h>

//Air pressure meter
//const int pressureInput = A15; //select the analog input pin for the pressure transducer
const int pressureZero = 102.4; //analog reading of pressure transducer at 0psi
const int pressureMax = 921.6; //analog reading of pressure transducer at 100psi
const int pressuretransducermaxPSI = 100; //psi value of transducer being used
//const int baudRate = 9600; //constant integer to set the baud rate for serial monitor
const int sensorreadDelay = 250; //constant integer to set the sensor read delay in milliseconds

float pressureValue = 0; //variable to store the value coming from the pressure transducer
//-----------------------------------------------------------------------------------------------------------------------------------------------

//IR Sensors
int cup1 = A0; int cup2 = A1; int cup16 = A15;

int grab1 = 0; int grab2 = 0; int grab16 = 0; //empty varaible
//---------------------------------------------------------------------------------------------------------------------------------

//Reading serial data from port
String serialstring;
char incomingByte; // for incoming serial data

//Flow Sensor
byte sensorInterrupt = 0;  // 0 = digital pin 2
byte sensorPin       = 2;

byte sensorInterrupt2 = 1;  // 1 = digital pin 3
byte sensorPin2       = 3;

byte sensorInterrupt3 = 5;  // 5 = digital pin 18
byte sensorPin3       = 18;

byte sensorInterrupt4 = 4;  // 4 = digital pin 19
byte sensorPin4       = 19;

byte sensorInterrupt5 = 3;  // 3 = digital pin 20
byte sensorPin5       = 20;

byte sensorInterrupt6 = 2;  // 2 = digital pin 21
byte sensorPin6       = 21;
//------------------------------------------------------------------------------------------------------------------------------------
//This part is needed to calculate volume
// The hall-effect flow sensor outputs approximately 4.5 pulses per second per litre/minute of flow.

float calibrationFactor = 4.5;
//-------------------------------------------------------------------------------------------------------------------------------------
//Each pulseCount, flowRate, flowMilliLitres, totalMilliLitres, oldTime, and total are for each flow meters
volatile byte pulseCount = 0;  
float flowRate = 0.0;
unsigned int flowMilliLitres = 0;
unsigned long totalMilliLitres = 0;
unsigned long oldTime = 0;
unsigned long total = 0;
// #8 is pump1 gas valve, 14 gas valve
volatile byte pulseCount2 = 0;  
float flowRate2 = 0.0;
unsigned int flowMilliLitres2 = 0;
unsigned long totalMilliLitres2 = 0;
unsigned long oldTime2 = 0;
unsigned long total2 = 0;

volatile byte pulseCount3 = 0;  
float flowRate3 = 0.0;
unsigned int flowMilliLitres3 = 0;
unsigned long totalMilliLitres3 = 0;
unsigned long oldTime3 = 0;
unsigned long total3 = 0;

volatile byte pulseCount4 = 0;  
float flowRate4 = 0.0;
unsigned int flowMilliLitres4 = 0;
unsigned long totalMilliLitres4 = 0;
unsigned long oldTime4 = 0;
unsigned long total4 = 0;

volatile byte pulseCount5 = 0;  
float flowRate5 = 0.0;
unsigned int flowMilliLitres5 = 0;
unsigned long totalMilliLitres5 = 0;
unsigned long oldTime5 = 0;
unsigned long total5 = 0;

volatile byte pulseCount6 = 0;  
float flowRate6 = 0.0;
unsigned int flowMilliLitres6 = 0;
unsigned long totalMilliLitres6 = 0;
unsigned long oldTime6 = 0;
unsigned long total6 = 0;
//-------------------------------------------------------------------------------------------------------

//output variables for motors, pumps, and valves
int valve1 = 22;
int valve2 = 23;
int valve3 = 24;
int valve4 = 25;
int valve5 = 26;
int valve6 = 27;
int valve7 = 28;
int valve8 = 29;
int valve9 = 30;
int valve10 = 31;
int valve11 = 32;
int valve12 = 33;
int valve13 = 34;
int valve14 = 35;
int valve15 = 36;
int valve16 = 37;
int valve17 = 38;
int valve18 = 39;

int check1 = 0;
int check2 = 0;
int check3 = 0;
int check4 = 0;
int check5 = 0;
int check6 = 0;
int check7 = 0;
int check8 = 0;
int check9 = 0;
int check10 = 0;
int check11 = 0;
int check12 = 0;
int check13 = 0;
int check14 = 0;
int check15 = 0;
int check16 = 0;
int check17 = 0;
int check18 = 0;
int check19 = 0;

byte flag1 = 1;
byte flag2 = 1;
byte flag3 = 1;
byte flag4 = 1;
byte flag5 = 1;
byte flag6 = 1;
byte flag7 = 1;
byte flag8 = 1;
byte flag9 = 1;
byte flag10 = 1;
byte flag11 = 1;
byte flag12 = 1;
byte flag13 = 1;
byte flag14 = 1;
byte flag15 = 1;
byte flag16 = 1;
byte flag17 = 1;
byte flag18 = 1;
byte flag19 = 1;


void setup() {
  //initialize digital pins for valve as output pin to enable or disable the pin. Set as HIGH so the relay doesn't turn on
  pinMode(valve1, OUTPUT);
  digitalWrite(valve1, LOW);
  pinMode(valve2, OUTPUT);
  digitalWrite(valve2, LOW);
  pinMode(valve3, OUTPUT);
  digitalWrite(valve3, LOW);
  pinMode(valve4, OUTPUT);
  digitalWrite(valve4, LOW);
  pinMode(valve5, OUTPUT);
  digitalWrite(valve5, LOW);
  pinMode(valve6, OUTPUT);
  digitalWrite(valve6, LOW);
  pinMode(valve7, OUTPUT);
  digitalWrite(valve7, LOW);
  pinMode(valve8, OUTPUT);
  digitalWrite(valve8, LOW);
  pinMode(valve9, OUTPUT);
  digitalWrite(valve9, LOW);
  pinMode(valve10, OUTPUT);
  digitalWrite(valve10, LOW);
  pinMode(valve11, OUTPUT);
  digitalWrite(valve11, LOW);
  pinMode(valve12, OUTPUT);
  digitalWrite(valve12, LOW);
  pinMode(valve13, OUTPUT);
  digitalWrite(valve13, LOW);
  pinMode(valve14, OUTPUT);
  digitalWrite(valve14, LOW);
  pinMode(valve15, OUTPUT);
  digitalWrite(valve15, LOW);
  pinMode(valve16, OUTPUT);
  digitalWrite(valve16, LOW);
  pinMode(valve17, OUTPUT);
  digitalWrite(valve17, LOW);
  pinMode(valve18, OUTPUT);
  digitalWrite(valve18, LOW);

  char device_status1 = EEPROM.read(0);
  char device_status2 = EEPROM.read(1);
  char device_status3 = EEPROM.read(2);
  char device_status4 = EEPROM.read(3);
  char device_status5 = EEPROM.read(4);
  char device_status6 = EEPROM.read(5);
  char device_status7 = EEPROM.read(6);
  char device_status8 = EEPROM.read(7);
  char device_status9 = EEPROM.read(8);
  char device_status10 = EEPROM.read(9);
  char device_status11 = EEPROM.read(10);
  char device_status12 = EEPROM.read(11);
  char device_status13 = EEPROM.read(12);
  char device_status14 = EEPROM.read(13);
  char device_status15 = EEPROM.read(14);
  char device_status16 = EEPROM.read(15);
  char device_status17 = EEPROM.read(16);
  char device_status18 = EEPROM.read(17);


  //Serial.println(device_status1);

  
  if (device_status1 == '0'){
    digitalWrite(valve1, LOW);
    flag1 = 1;
  }
  else {
    digitalWrite(valve1, HIGH);
    flag1 = 0;
  }

  if (device_status2 == '0'){
    digitalWrite(valve2, LOW);
    flag2 = 1;
  }
  else {
    digitalWrite(valve2, HIGH);
    flag2 = 0;
  }

  if (device_status3 == '0'){
    digitalWrite(valve3, LOW);
    flag3 = 1;
  }
  else {
    digitalWrite(valve3, HIGH);
    flag3 = 0;
  }

  if (device_status4 == '0'){
    digitalWrite(valve4, LOW);
    flag4 = 1;
  }
  else {
    digitalWrite(valve4, HIGH);
    flag4 = 0;
  }

  if (device_status5 == '0'){
    digitalWrite(valve5, LOW);
    flag5 = 1;
  }
  else {
    digitalWrite(valve5, HIGH);
    flag5 = 0;
  }

  if (device_status6 == '0'){
    digitalWrite(valve6, LOW);
    flag6 = 1;
  }
  else {
    digitalWrite(valve6, HIGH);
    flag6 = 0;
  }

  if (device_status7 == '0'){
    digitalWrite(valve7, LOW);
    flag7 = 1;
  }
  else {
    digitalWrite(valve7, HIGH);
    flag7 = 0;
  }

  if (device_status8 == '0'){
    digitalWrite(valve8, LOW);
    flag8 = 1;
  }
  else {
    digitalWrite(valve8, HIGH);
    flag8 = 0;
  }

  if (device_status9 == '0'){
    digitalWrite(valve9, LOW);
    flag9 = 1;
  }
  else {
    digitalWrite(valve9, HIGH);
    flag9 = 0;
  }

  if (device_status10 == '0'){
    digitalWrite(valve10, LOW);
    flag10 = 1;
  }
  else {
    digitalWrite(valve10, HIGH);
    flag10 = 0;
  }

  if (device_status11 == '0'){
    digitalWrite(valve11, LOW);
    flag11 = 1;
  }
  else {
    digitalWrite(valve11, HIGH);
    flag11 = 0;
  }

  if (device_status11 == '0'){
    digitalWrite(valve11, LOW);
    flag11 = 1;
  }
  else {
    digitalWrite(valve11, HIGH);
    flag11 = 0;
  }

  if (device_status12 == '0'){
    digitalWrite(valve12, LOW);
    flag12 = 1;
  }
  else {
    digitalWrite(valve12, HIGH);
    flag12 = 0;
  }

  if (device_status13 == '0'){
    digitalWrite(valve13, LOW);
    flag13 = 1;
  }
  else {
    digitalWrite(valve13, HIGH);
    flag13 = 0;
  }

  if (device_status14 == '0'){
    digitalWrite(valve14, LOW);
    flag14 = 1;
  }
  else {
    digitalWrite(valve14, HIGH);
    flag14 = 0;
  }

  if (device_status15 == '0'){
    digitalWrite(valve15, LOW);
    flag15 = 1;
  }
  else {
    digitalWrite(valve15, HIGH);
    flag15 = 0;
  }

  if (device_status16 == '0'){
    digitalWrite(valve16, LOW);
    flag16 = 1;
  }
  else {
    digitalWrite(valve16, HIGH);
    flag16 = 0;
  }

  if (device_status17 == '0'){
    digitalWrite(valve17, LOW);
    flag17 = 1;
  }
  else {
    digitalWrite(valve17, HIGH);
    flag17 = 0;
  }

  if (device_status18 == '0'){
    digitalWrite(valve18, LOW);
    flag18 = 1;
  }
  else {
    digitalWrite(valve18, HIGH);
    flag18 = 0;
  }
  
  // initialize digital pins for cup 1-16 as input pins to read from IR sensors.
  pinMode(cup1, INPUT); //makes IR read inputs
  pinMode(cup2, INPUT); //makes IR read inputs
  pinMode(cup16, INPUT); //makes IR read inputs
  //---------------------------------------------------------------------------------------------------------------------------
  
  //Buad rate, needed to read and write to serial.
  Serial.begin(9600);
  //----------------------------------------------------------------------------------------------------------------------------
  
  //initialize digital pins for sensorPin 1-6 as input pins to read interrupts from the flow meter. Set each pin to HIGH, so that the interrupt can read the Falling.
  pinMode(sensorPin, INPUT);
  digitalWrite(sensorPin, HIGH);
  pinMode(sensorPin2, INPUT);
  digitalWrite(sensorPin2, HIGH);
  pinMode(sensorPin3, INPUT);
  digitalWrite(sensorPin3, HIGH);
  pinMode(sensorPin4, INPUT);
  digitalWrite(sensorPin4, HIGH);
  pinMode(sensorPin5, INPUT);
  digitalWrite(sensorPin5, HIGH);
  pinMode(sensorPin6, INPUT);
  digitalWrite(sensorPin6, HIGH);
  //-----------------------------------------------------------------------------------------------------------------------



  check1 = 0;
  check2 = 0;
  check3 = 0;
  check4 = 0;
  check5 = 0;
  check6 = 0;
  check7 = 0;
  check8 = 0;
  check9 = 0;
  check10 = 0;
  check11 = 0;
  check12 = 0;
  check13 = 0;
  check14 = 0;
  check15 = 0;
  check16 = 0;
  check17 = 0;
  check18 = 0;
  check19 = 0;

  


  

  
  //Connect the interrupt pins to the pulseCounter function, so that everytime the interrupt falls, it goes to the pulseCounter function and increment pulseCount
  attachInterrupt(sensorInterrupt, pulseCounter, FALLING);
  attachInterrupt(sensorInterrupt2, pulseCounter2, FALLING);
  attachInterrupt(sensorInterrupt3, pulseCounter3, FALLING);
  attachInterrupt(sensorInterrupt4, pulseCounter4, FALLING);
  attachInterrupt(sensorInterrupt5, pulseCounter5, FALLING);
  attachInterrupt(sensorInterrupt6, pulseCounter6, FALLING);
}



// the loop function runs over and over again forever
void loop() {

  if (Serial.available() > 0) {
      serialstring = "";
      // read the incoming byte:
      while(Serial.available()) {
        incomingByte = Serial.read();
        if (incomingByte != '\n') {
          serialstring += String(incomingByte);
        }
        //Serial.print(serialstring);
        
        
        }

        if (serialstring == "a" || serialstring == "1") {
          check1 = 1;
          if (flag1 == 1) {
            digitalWrite(valve1, HIGH);
            EEPROM.write(0, '1');
          }
          else {
            digitalWrite(valve1, LOW);
            EEPROM.write(0, '0');
          }
          flag1 = 1 - flag1;
        }

        if (serialstring == "b" || serialstring == "2") { //middle pump 
          check2 = 2;
          if (flag2 == 1) {
            digitalWrite(valve2, HIGH);
            EEPROM.write(1, '1');
          }
          else {
            digitalWrite(valve2, LOW);
            EEPROM.write(1, '0');
          }
          flag2 = 1 - flag2;
        }

        if (serialstring == "c" || serialstring == "3") {
          check3 = 3;
          if (flag3 == 1) {
            digitalWrite(valve3, HIGH);
            EEPROM.write(2, '1');
          }
          else {
            digitalWrite(valve3, LOW);
            EEPROM.write(2, '0');
          }
          flag3 = 1 - flag3;
        }

        if (serialstring == "d" || serialstring == "4") {
          check4 = 4;
          if (flag4 == 1) {
            digitalWrite(valve4, HIGH);
            EEPROM.write(3, '1');
          }
          else {
            digitalWrite(valve4, LOW);
            EEPROM.write(3, '0');
          }
          flag4 = 1 - flag4;
        }

        if (serialstring == "e" || serialstring == "5") { //middle valve
          check5 = 5;
          if (flag5 == 1) {
            digitalWrite(valve5, HIGH);
            EEPROM.write(4, '1');
          }
          else {
            digitalWrite(valve5, LOW);
            EEPROM.write(4, '0');
          }
          flag5 = 1 - flag5;
        }

        if (serialstring == "f" || serialstring == "6") {
          check6 = 6;
          if (flag6 == 1) {
            digitalWrite(valve6, HIGH);
            EEPROM.write(5, '1');
          }
          else {
            digitalWrite(valve6, LOW);
            EEPROM.write(5, '0');
          }
          flag6 = 1 - flag6;
        }

        if (serialstring == "g" || serialstring == "7") { // left side valve, second from the top. fourth flow meter serial 1
          check7 = 7;
          if (flag7 == 1) {
            digitalWrite(valve7, HIGH);
            EEPROM.write(6, '1');
          }
          else {
            digitalWrite(valve7, LOW);
            EEPROM.write(6, '0');
          }
          flag7 = 1 - flag7;
        }

        if (serialstring == "h" || serialstring == "8") { //top left valve next to left pump. Third flow meter serial 1
          check8 = 8;
          if (flag8 == 1) {
            digitalWrite(valve8, HIGH);
            EEPROM.write(7, '1');
          }
          else {
            digitalWrite(valve8, LOW);
            EEPROM.write(7, '0');
          }
          flag8 = 1 - flag8;
        }

        if (serialstring == "i" || serialstring == "9") { //left side valve, third from the top. first flow meter serial 1
          check9 = 9;
          if (flag9 == 1) {
            digitalWrite(valve9, HIGH);
            EEPROM.write(8, '1');
          }
          else {
            digitalWrite(valve9, LOW);
            EEPROM.write(8, '0');
          }
          flag9 = 1 - flag9;
        }

        if (serialstring == "j" || serialstring == "10") { //right side gas valve
          check10 = 10;
          if (flag10 == 1) {
            digitalWrite(valve10, HIGH);
            EEPROM.write(9, '1');
          }
          else {
            digitalWrite(valve10, LOW);
            EEPROM.write(9, '0');
          }
          flag10 = 1 - flag10;
        }

        if (serialstring == "k" || serialstring == "11") { //left side valve, very bottom. second flow meter serial 1
          check11 = 11;
          if (flag11 == 1) {
            digitalWrite(valve11, HIGH);
            EEPROM.write(10, '1');
          }
          else {
            digitalWrite(valve11, LOW);
            EEPROM.write(10, '0');
          }
          flag11 = 1 - flag11;
        }

        if (serialstring == "l" || serialstring == "12") { // right side second from top valve. sixth flow meter serial 1
          check12 = 12;
          if (flag12 == 1) {
            digitalWrite(valve12, HIGH);
            EEPROM.write(11, '1');
          }
          else {
            digitalWrite(valve12, LOW);
            EEPROM.write(11, '0');
          }
          flag12 = 1 - flag12;
        }

        if (serialstring == "m" || serialstring == "13") { //right side valve very bottom. fifth flow meter serial 2
          
          check13 = 13;
          if (flag13 == 1) {
            digitalWrite(valve13, HIGH);
            EEPROM.write(12, '1');
          }
          else {
            digitalWrite(valve13, LOW);
            EEPROM.write(12, '0');
          }
          flag13 = 1 - flag13;
        }

        if (serialstring == "n" || serialstring == "14") { //right side valve very top. fifth flow meter serial 10
          check14 = 14;
          if (flag14 == 1) {
            digitalWrite(valve14, HIGH);
            EEPROM.write(13, '1');
          }
          else {
            digitalWrite(valve14, LOW);
            EEPROM.write(13, '0');
          }
          flag14 = 1 - flag14;
        }

        if (serialstring == "o" || serialstring == "15") { //right side valve third from the top sixth flow meter serial 2
          check15 = 15;
          if (flag15 == 1) {
            digitalWrite(valve15, HIGH);
            EEPROM.write(14, '1');
          }
          else {
            digitalWrite(valve15, LOW);
            EEPROM.write(14, '0');
          }
          flag15 = 1 - flag15;
        }

        if (serialstring == "p" || serialstring == "16") { // left side pump
          check16 = 16;
          if (flag16 == 1) {
            digitalWrite(valve16, HIGH);
            EEPROM.write(15, '1');
          }
          else {
            digitalWrite(valve16, LOW);
            EEPROM.write(15, '0');
          }
          flag16 = 1 - flag16;
        }

        if (serialstring == "q" || serialstring == "17") { //right side pump
          check17 = 17;
          if (flag17 == 1) {
            digitalWrite(valve17, HIGH);
            EEPROM.write(16, '1');
          }
          else {
            digitalWrite(valve17, LOW);
            EEPROM.write(16, '0');
          }
          flag17 = 1 - flag17;
        }

        if (serialstring == "r" || serialstring == "18") { //left side gas valve
          check18 = 18;
          if (flag18 == 1) {
            digitalWrite(valve18, HIGH);
            EEPROM.write(17, '1');
          }
          else {
            digitalWrite(valve18, LOW);
            EEPROM.write(17, '0');
          }
          flag18 = 1 - flag18;
        }

        if (serialstring == "0") {
          digitalWrite(valve1, LOW);
          EEPROM.write(0, '0');
          digitalWrite(valve2, LOW);
          EEPROM.write(1, '0');
          digitalWrite(valve3, LOW);
          EEPROM.write(2, '0');
          digitalWrite(valve4, LOW);
          EEPROM.write(3, '0');
          digitalWrite(valve5, LOW);
          EEPROM.write(4, '0');
          digitalWrite(valve6, LOW);
          EEPROM.write(5, '0');
          digitalWrite(valve7, LOW);
          EEPROM.write(6, '0');
          digitalWrite(valve8, LOW);
          EEPROM.write(7, '0');
          digitalWrite(valve9, LOW);
          EEPROM.write(8, '0');
          digitalWrite(valve10, LOW);
          EEPROM.write(9, '0');
          digitalWrite(valve11, LOW);
          EEPROM.write(10, '0');
          digitalWrite(valve12, LOW);
          EEPROM.write(11, '0');
          digitalWrite(valve13, LOW);
          EEPROM.write(12, '0');
          digitalWrite(valve14, LOW);
          EEPROM.write(13, '0');
          digitalWrite(valve15, LOW);
          EEPROM.write(14, '0');
          digitalWrite(valve16, LOW);
          EEPROM.write(15, '0');
          digitalWrite(valve17, LOW);
          EEPROM.write(16, '0');
          digitalWrite(valve18, LOW);
          EEPROM.write(17, '0');
          check19 = 19;
          flag1 = 1;
          flag2 = 1;
          flag3 = 1;
          flag4 = 1;
          flag5 = 1;
          flag6 = 1;
          flag7 = 1;
          flag8 = 1;
          flag9 = 1;
          flag10 = 1;
          flag11 = 1;
          flag12 = 1;
          flag13 = 1;
          flag14 = 1;
          flag15 = 1;
          flag16 = 1;
          flag17 = 1;
          flag18 = 1;

        }


  }

  delay(70);
  if (Serial.available() <= 0) {
    if((millis() - oldTime) > 1000)  { 
      detachInterrupt(sensorInterrupt);
      flowRate = ((1000.0 / (millis() - oldTime)) * pulseCount) / calibrationFactor;
      oldTime = millis();
      flowMilliLitres = (flowRate / 60) * 1000;
      total += flowMilliLitres;
      totalMilliLitres = total/4.5;
      if (flowRate == 0) {
        total = 0;
        totalMilliLitres = 0;
      }
      pulseCount = 0;
      attachInterrupt(sensorInterrupt, pulseCounter, FALLING);
    }

    if((millis() - oldTime2) > 1000)  { 
      detachInterrupt(sensorInterrupt2);
      flowRate2 = ((1000.0 / (millis() - oldTime2)) * pulseCount2) / calibrationFactor;
      oldTime2 = millis();
      flowMilliLitres2 = (flowRate2 / 60) * 1000;
      total2 += flowMilliLitres2;
      totalMilliLitres2 = total2/4.5;
      if (flowRate2 == 0) {
        total2 = 0;
        totalMilliLitres2 = 0;
      }
      pulseCount2 = 0;
      attachInterrupt(sensorInterrupt2, pulseCounter2, FALLING);
    }

    if((millis() - oldTime3) > 1000)  { 
      detachInterrupt(sensorInterrupt3);
      flowRate3 = ((1000.0 / (millis() - oldTime3)) * pulseCount3) / calibrationFactor;
      oldTime3 = millis();
      flowMilliLitres3 = (flowRate3 / 60) * 1000;
      total3 += flowMilliLitres3;
      totalMilliLitres3 = total3/4.5;
      if (flowRate3 == 0) {
        total3 = 0;
        totalMilliLitres3 = 0;
      }
      pulseCount3 = 0;
      attachInterrupt(sensorInterrupt3, pulseCounter3, FALLING);
    }

    if((millis() - oldTime4) > 1000)  { 
      detachInterrupt(sensorInterrupt4);
      flowRate4 = ((1000.0 / (millis() - oldTime4)) * pulseCount4) / calibrationFactor;
      oldTime4 = millis();
      flowMilliLitres4 = (flowRate4 / 90) * 1000;
      total4 += flowMilliLitres4;
      //if (total4/3 > 70) {
      //  totalMilliLitres4 = total4/3 - 70;
      //}
      //else {
      totalMilliLitres4 = total4/4.5;
      //}
      if (flowRate4 == 0) {
        total4 = 0;
        totalMilliLitres4 = 0;
      }
      pulseCount4 = 0;
      attachInterrupt(sensorInterrupt4, pulseCounter4, FALLING);
    }

    if((millis() - oldTime5) > 1000)  { 
      detachInterrupt(sensorInterrupt5);
      flowRate5 = ((1000.0 / (millis() - oldTime5)) * pulseCount5) / calibrationFactor;
      oldTime5 = millis();
      flowMilliLitres5 = (flowRate5 / 60) * 1000;
      total5 += flowMilliLitres5;
      totalMilliLitres5 = total5;
      if (flowRate5 == 0) {
        total5 = 0;
        totalMilliLitres5 = 0;
      }
      pulseCount5 = 0;
      attachInterrupt(sensorInterrupt5, pulseCounter5, FALLING);
    }

    if((millis() - oldTime6) > 1000)  { 
      detachInterrupt(sensorInterrupt6);
      flowRate6 = ((1000.0 / (millis() - oldTime6)) * pulseCount6) / calibrationFactor;
      oldTime6 = millis();
      flowMilliLitres6 = (flowRate6 / 60) * 1000;
      total6 += flowMilliLitres6;
      totalMilliLitres6 = total6;
      if (flowRate6 == 0) {
        total6 = 0;
        totalMilliLitres6 = 0;
      }
      pulseCount6 = 0;
      attachInterrupt(sensorInterrupt6, pulseCounter6, FALLING);
    }


    grab1 = analogRead(cup1); grab2 = analogRead(cup2);

    pressureValue = analogRead(cup16); //reads value from input pin and assigns to variable
    pressureValue = ((pressureValue-pressureZero)*pressuretransducermaxPSI)/(pressureMax-pressureZero); //conversion equation to convert analog reading to psi
    //Serial.print(pressureValue, 1); //prints value from previous line to serial
    
    
    Serial.print(totalMilliLitres);
    Serial.print(",");
    Serial.print(totalMilliLitres2);
    Serial.print(",");
    Serial.print(totalMilliLitres3);
    Serial.print(",");
    Serial.print(totalMilliLitres4);
    Serial.print(",");
    Serial.print(totalMilliLitres5);
    Serial.print(",");
    Serial.print(totalMilliLitres6);
    Serial.print(",");
    Serial.print(grab1);
    Serial.print(",");
    Serial.print(grab2);
    Serial.print(",");
    Serial.println(pressureValue);

    check1 = 0;
    check2 = 0;
    check3 = 0;
    check4 = 0;
    check5 = 0;
    check6 = 0;
    check7 = 0;
    check8 = 0;
    check9 = 0;
    check10 = 0;
    check11 = 0;
    check12 = 0;
    check13 = 0;
    check14 = 0;
    check15 = 0;
    check16 = 0;
    check17 = 0;
    check18 = 0;
    check19 = 0;
  }
  
} //Loops back to the beginning of the void loop.

void pulseCounter()
{
  // Increment the pulse counter
  pulseCount++;
}

void pulseCounter2()
{
  // Increment the pulse counter
  pulseCount2++;
}

void pulseCounter3()
{
  // Increment the pulse counter
  pulseCount3++;
}

void pulseCounter4()
{
  // Increment the pulse counter
  pulseCount4++;
}

void pulseCounter5()
{
  // Increment the pulse counter
  pulseCount5++;
}

void pulseCounter6()
{
  // Increment the pulse counter
  pulseCount6++;
}
