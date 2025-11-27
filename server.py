import socket
import threading
import json
import random
import time

HOST = '127.0.0.1'
PORT = 12345

clients_lock = threading.Lock()
clients = [] 
games = []

class Game:
    def __init__(self):
        self.clients = []
        self.cols = 9
        self.rows = 9
        self.total_mines = 10
        self.game_id = -1
        
        self.first_click = True

    def set_clients_id(self):
        with clients_lock:
            for i, conn in enumerate(self.clients):
                payload = json.dumps({"set_id" : i}) + "\n"
                try:
                    conn.sendall(payload.encode('utf-8'))
                except Exception as e:
                    print(f"[ОШИБКА] Не удалось отправить сообщение клиенту {conn}", e)
    
    def init_mines(self, safe_x, safe_y):
        positions = [(x, y) for x in range(self.rows) for y in range(self.cols)]
        exclude = set()
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                nx, ny = safe_x + dx, safe_y + dy
                if 0 <= nx < self.rows and 0 <= ny < self.cols:
                    exclude.add((nx, ny))
        candidates = [pos for pos in positions if pos not in exclude]
        mines = random.sample(candidates, self.total_mines)

        self.send_message({"mines" : mines})
    
    def send_message(self, msg):
        payload = json.dumps(msg) + "\n"
        with clients_lock:
            for conn in self.clients:
                try:
                    conn.sendall(payload.encode('utf-8'))
                except Exception as e:
                    print(f"[ОШИБКА] Не удалось отправить сообщение клиенту {conn}", e)

    def disconnect_all(self):
        for conn in self.clients:
            try:
                msg = json.dumps({"disconnect": True}) + "\n"
                conn.sendall(msg.encode('utf-8'))
            except:
                pass

    

def handle_client(conn, addr):
    print(f"[НОВОЕ ПОДКЛЮЧЕНИЕ] {addr}")

    with clients_lock:
        clients.append(conn)
    
    if games and len(games[-1].clients) == 1:
        game = games[-1]
        game.clients.append(conn)
        game.set_clients_id()
        game.send_message({"game_start" : True})
    else:
        game = Game()
        game.clients.append(conn)
        games.append(game)
        game.game_id = len(games) - 1

    
    buffer = ""

    try:
        while True:
            data = conn.recv(1024).decode('utf-8')
            if not data:
                break

            buffer += data

            lines = buffer.split("\n")
            buffer = lines.pop()   

            for line in lines:
                if not line.strip():
                    continue

                info = json.loads(line)

                if info.get("cmd") == "left_click":
                    x = info["x"]
                    y = info["y"]
                    if game.first_click:
                        game.init_mines(x, y)
                        game.first_click = False
                        info["first_click"] = True
                    else:
                        info["first_click"] = False

                    game.send_message(info)
                    continue
                elif info.get("cmd") == "right_click":
                    game.send_message(info)

    except Exception as e:
        print(f"[ОТКЛЮЧЕНИЕ] Клиент {addr} отключился")

    finally:
        with clients_lock:
            game_to_close = None

            for g in games:
                if conn in g.clients:
                    print("[ОТКЛЮЧЕНИЕ] Один игрок отключился — завершаем игру")
                    g.disconnect_all()
                    game_to_close = g
                    break
            time.sleep(2)

        if conn in clients:
            clients.remove(conn)

        if game_to_close:
            games.remove(game_to_close)



        
def start_server():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    with server_socket:
        server_socket.bind((HOST, PORT))
        server_socket.listen()
        print(f"[СЕРВЕР ЗАПУЩЕН] {HOST}:{PORT}")
        while True:
            conn, addr = server_socket.accept()
            threading.Thread(target=handle_client, args=(conn, addr)).start()

if __name__ == "__main__":
    start_server()
