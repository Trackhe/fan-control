import time, threading, socket
import RPi.GPIO as GPIO

exitFlag = 0
exitFlag0 = 0

# options
temp_target = 40 # use ca 5 degrees more then idle tempeture
temp_max = 55
fan_cuttoff = 8 # percentage from 0 to 100 that shut the fan at low rpm off dont choice it to high

fan_gpio = 23
fan_pwm_freq = 100
fan_transistor = "npn" # use npn, pnp or pwm

master_case_fan_gpio = 24
master_case_fan_pwm_freq = 100
master_case_fan_transistor = "pwm" # use npn, pnp or pwm
master_port = 25565
master_client_adress = "10.10.150.161"

controller_mode = "master" # master, client, standalone : master runs standalone and master together


class fcThread (threading.Thread):
   def __init__(self, threadID, name):
      threading.Thread.__init__(self)
      self.threadID = threadID
      self.name = name
   def run(self):
      print ("Starting " + self.name)
      if self.name == "client":
          control_client()
      if self.name == "master":
          control_master()
      if self.name == "masterpwm":
          control_master_pwm()
      if self.name == "standalone":
          control_standalone()
      print ("Exiting " + self.name)

def control_standalone():
    # code
    if fan_transistor == "npn":
        fan_off = 100
        fan_on = 0
    else:
        fan_off = 0
        fan_on = 100

    GPIO.setup(fan_gpio, GPIO.OUT)
    fan_pwm = GPIO.PWM(fan_gpio, fan_pwm_freq)  # frequency=100Hz
    fan_pwm.start(0)
    fan_pwm.ChangeDutyCycle(fan_off)

    while not exitFlag:
        temp = get_temp()
        time.sleep(2)

        pwm_percent = int(round(((temp - temp_target) * 100) / (temp_max - temp_target), 0))

        if temp <= temp_target or pwm_percent < fan_cuttoff:
            print(str(temp) + "°C : " + "temp under " + str(temp_target) + " and the load percantage does\'t reach the cuttoff " + str(pwm_percent) + ":" + str(fan_cuttoff))
            fan_pwm.ChangeDutyCycle(fan_off)
        else:
            if pwm_percent >= 100:
                print(str(temp) + "°C : " + "100% at " + str(pwm_percent))
                fan_pwm.ChangeDutyCycle(fan_on)
            else:
                print(str(temp) + "°C : " + "PWM at " + str(pwm_percent))
                if fan_transistor == "npn":
                    fan_dutycycle = (pwm_percent - 100) * -1
                else:
                    fan_dutycycle = pwm_percent
                fan_pwm.ChangeDutyCycle(fan_dutycycle)

    fan_pwm.stop()

def control_client():
    # code
    server_address = (master_client_adress, master_port)

    while not exitFlag:
        time.sleep(2)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            print("connecting to " + str(server_address))
            sock.connect(server_address)
            # Send data
            message = str(int(round(get_temp(), 0)))
            sendmessage = message.encode('utf-8')
            print("send temp: " + message)
            sock.sendall(sendmessage)

            # Look for the response
            amount_received = 0
            amount_expected = 2

            while amount_received < amount_expected:
                time.sleep(0.2)
                data = sock.recv(2)
                amount_received = len(data)
                print("server replied: " + data.decode('utf-8'))

        finally:
            print("close connection")
            sock.close()

clientarray = {"localhost" : [0, time.time()]}
master_clear_time = 0

def control_master():
    # code
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_address = (master_client_adress, master_port)
    print("starting server at " + str(server_address))
    sock.bind(server_address)
    sock.listen(1)

    while not exitFlag:
        print("wait for client conntections")
        connection, client_address = sock.accept()
        try:
            ca = str(client_address[0])
            print("client connected: " + ca)
            while True and not exitFlag:
                data = connection.recv(2)
                if data:
                    mdata = data.decode('utf-8')
                    print("client: " + master_client_adress + ":" + str(master_port) + " message: " + mdata)
                    clientarray[ca] = [int(mdata), time.time()]
                    connection.sendall(b'io')
                else:
                    break
        finally:
            connection.close()

    master_case_fan_pwm.stop()

def control_master_pwm():
    # code
    if master_case_fan_transistor == "npn":
        fan_off = 100
        fan_on = 0
    else:
        fan_off = 0
        fan_on = 100

    GPIO.setup(master_case_fan_gpio, GPIO.OUT)
    master_case_fan_pwm = GPIO.PWM(master_case_fan_gpio, master_case_fan_pwm_freq)  # frequency=100Hz
    master_case_fan_pwm.start(0)
    master_case_fan_pwm.ChangeDutyCycle(fan_off)

    while not exitFlag:
        time.sleep(2)
        temp = 0
        time_now = time.time()
        clientarray["localhost"] = [get_temp(), time_now]

        for k in clientarray:
            (ti, te) = clientarray[k]
            if (time_now - te) <= 30:
                temp = max(ti, temp)



        pwm_percent = int(round(((temp - temp_target) * 100) / (temp_max - temp_target), 0))

        if temp <= temp_target or pwm_percent < fan_cuttoff:
            print(str(temp) + "°C : " + "master temp under " + str(temp_target) + " and the load percantage does\'t reach the cuttoff " + str(pwm_percent) + ":" + str(fan_cuttoff))
            master_case_fan_pwm.ChangeDutyCycle(fan_off)
        else:
            if pwm_percent >= 100:
                print(str(temp) + "°C : " + "master 100% at " + str(pwm_percent))
                master_case_fan_pwm.ChangeDutyCycle(fan_on)
            else:
                print(str(temp) + "°C : " + "master PWM at " + str(pwm_percent))
                if master_case_fan_transistor == "npn":
                    fan_dutycycle = (pwm_percent - 100) * -1
                else:
                    fan_dutycycle = pwm_percent
                master_case_fan_pwm.ChangeDutyCycle(fan_dutycycle)


    master_case_fan_pwm.stop()

def get_temp():
    """Get the core temperature.
    Read file from /sys to get CPU temp in temp in C *1000
    Returns:
        int: The core temperature in thousanths of degrees Celsius.
    """
    with open('/sys/class/thermal/thermal_zone0/temp') as f:
        temp_str = f.read()
    try:
        return int(temp_str) / 1000
    except (IndexError, ValueError,) as e:
        raise RuntimeError('Could not parse temperature output.') from e

if __name__ == '__main__':
    try:
        GPIO.setmode(GPIO.BCM)

        control_standalone_thread = fcThread(1, "standalone")
        control_standalone_thread.start()

        if controller_mode == "client":
            control_client_thread = fcThread(2, "client")
            control_client_thread.start()

        if controller_mode == "master":
            control_master_thread = fcThread(2, "master")
            control_master_thread.start()
            control_master_pwm_thread = fcThread(3, "masterpwm")
            control_master_pwm_thread.start()

        while True:
            time.sleep(500)

    except KeyboardInterrupt:
        pass
    finally:
        exitFlag = 1
        GPIO.cleanup()
