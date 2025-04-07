import smbus
import time

# Initialize I2C bus
bus = smbus.SMBus(1)  # Use I2C bus 1

# CHT8305 I2C address
CHT8305_ADDR = 0x40

# Read temperature and humidity registers
def read_sensor():
    # Trigger a measurement by reading register 0x00
    data = bus.read_i2c_block_data(CHT8305_ADDR, 0x00, 4)
    
    # Convert raw data to temperature and humidity
    temp_raw = (data[0] << 8) | data[1]
    temp = ((temp_raw * 165.0) / 65535.0) - 40.0
    
    hum_raw = (data[2] << 8) | data[3]
    humidity = (hum_raw * 100.0) / 65535.0
    
    return temp, humidity

while True:
    temperature, humidity = read_sensor()
    print(f"Temperature: {temperature:.2f}°C, Humidity: {humidity:.2f}%")
    time.sleep(1)
