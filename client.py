import socket
import threading
import json
import time
from PyQt6.QtCore import QObject, pyqtSignal

HOST = '127.0.0.1'
PORT = 12345

class Client(QObject):
    tasks_updated = pyqtSignal(list)
    game_start = pyqtSignal()
    generate_mines = pyqtSignal(list)
    game_update = pyqtSignal(dict)
    game_stop = pyqtSignal()

    def __init__(self, host=HOST, port=PORT):
        super().__init__() 
        self.host = host
        self.port = port
        self.tasks = []
        self.socket = None
        self.my_id = None
    
    def connect(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((self.host, self.port))
        threading.Thread(target=self.listen_server, daemon=True).start()
    
    def listen_server(self):
        buffer = ""

        while True:
            try:
                data = self.socket.recv(1024).decode('utf-8')

                if not data:
                    break

                buffer += data
                lines = buffer.split('\n')
                buffer = lines.pop()

                for line in lines:
                    if not line.strip():
                        continue
                    msg = json.loads(line)

                    if "mines" in msg:
                        self.generate_mines.emit(msg["mines"])
                        continue
                    elif "set_id" in msg:
                        self.my_id = msg["set_id"]
                        continue
                    elif "game_start" in msg:
                        self.game_start.emit()
                    elif "disconnect" in msg:
                        print("Сервер завершил игру")
                        self.game_stop.emit()
                        time.sleep(2)
                        self.socket.close()
                        return
                    else:
                        self.game_update.emit(msg)

            except Exception as e:
                print("[ОШИБКА ПОДКЛЮЧЕНИЯ]", e)
                break

    def send_command(self, command: dict):
        try:
            msg = json.dumps(command, ensure_ascii=False) + "\n"
            self.socket.sendall(msg.encode("utf-8"))
        except Exception as e:
            print("[ОШИБКА ОТПРАВКИ]", e)