import serial

class SerialModel:
    def __init__(self, port="COM10", baudrate=115200, timeout=1):
        self.ser = serial.Serial(port, baudrate, timeout=timeout)
        self.data = None
        self.feed = None

    def send_command(self, command):
        try:
            # Ensure the command starts with '$'
            if not command.startswith('$'):
                print("Invalid command! Command must start with '$'.")
                return

            # Append '\n' automatically
            command += '\n'

            # Send command over serial
            self.ser.write(command.encode())  
            print(f"Sent: {command.strip()}")

            # Read response
            response = self.ser.readline().decode().strip()
            print(f"Received: {response}")

            # Store the response
            self.data = response
            self.feed = command.strip()

        except Exception as e:
            print(f"Error: {e}")

    def close(self):
        self.ser.close()

    def get_status(self):
        return {"data": self.data, "feed": self.feed}