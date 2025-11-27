import sys
from PyQt6.QtWidgets import (
    QApplication, QWidget, QPushButton, QLabel, QGridLayout, QVBoxLayout,
    QHBoxLayout, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont

from client import Client

class Cell(QPushButton):
    left_clicked = pyqtSignal(int, int)
    right_clicked = pyqtSignal(int, int)

    def __init__(self, x: int, y: int):
        super().__init__()
        self.x = x
        self.y = y
        self.is_mine = False
        self.revealed = False
        self.flagged = False
        self.adjacent = 0
        self.setFixedSize(32, 32)
        self.setFont(QFont('Consolas', 10, QFont.Weight.Bold))
        self.update_style()

    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self.left_clicked.emit(self.x, self.y)
        elif ev.button() == Qt.MouseButton.RightButton:
            self.right_clicked.emit(self.x, self.y)

    def reveal(self):
        if self.revealed:
            return
        self.revealed = True
        self.setDisabled(True)
        if self.is_mine:
            self.setText('💣')
            self.setStyleSheet('background: #ff9999;')
        else:
            if self.adjacent > 0:
                self.setText(str(self.adjacent))
                colors = {
                    1: '#0000ff', 2: '#008200', 3: '#ff0000', 4: '#000084',
                    5: '#840000', 6: '#008284', 7: '#000000', 8: '#808080'
                }
                self.setStyleSheet(f'color: {colors.get(self.adjacent, "#000")}; background: #e0e0e0;')
            else:
                self.setStyleSheet('background: #e0e0e0;')
        self.update()

    def toggle_flag(self):
        if self.revealed:
            return
        self.flagged = not self.flagged
        self.update_style()

    def update_style(self):
        if self.revealed:
            self.setDisabled(True)
        else:
            self.setEnabled(True)

        if self.flagged and not self.revealed:
            self.setText('🚩')
        elif not self.revealed:
            self.setText('')
        if not self.revealed:
            self.setStyleSheet('background: #c0c0c0;')


class Minesweeper(QWidget):
    def __init__(self, rows=9, cols=9, mines=10):
        super().__init__()
        self.setWindowTitle('Сапер — PyQt6')
        self.rows = rows
        self.cols = cols
        self.total_mines = mines
        self.first_click = True
        self.timer = QTimer(self)
        self.elapsed = 0
        self.my_score = 0
        self.enemy_score = 0
        self.timer.timeout.connect(self._tick)

        self._create_ui()

        self.client = Client()
        self.client.game_start.connect(self.new_game)
        self.client.generate_mines.connect(self.plant_mines)
        self.client.game_update.connect(self.update_board)
        self.client.game_stop.connect(self.handle_disconnect)
        self.client.connect()

        self.my_turn = None

    def _create_ui(self):
        main_layout = QVBoxLayout()

        top_row = QHBoxLayout()
        self.mine_label = QLabel(f'Мины: {self.total_mines}')
        self.mine_label.setFont(QFont('Arial', 12, QFont.Weight.Bold))
        top_row.addWidget(self.mine_label)

        self.turn_label = QLabel("Ход: —")
        self.turn_label.setFont(QFont('Arial', 12, QFont.Weight.Bold))
        self.turn_label.setStyleSheet("color: #0055ff;")
        top_row.addWidget(self.turn_label)

        top_row.addStretch()

        self.time_label = QLabel('Время: 0')
        self.time_label.setFont(QFont('Arial', 12, QFont.Weight.Bold))
        top_row.addWidget(self.time_label)

        main_layout.addLayout(top_row)

        score_row = QHBoxLayout()
        self.score_label = QLabel("Очки: вы — 0 | соперник — 0")
        self.score_label.setFont(QFont('Arial', 12, QFont.Weight.Bold))
        score_row.addWidget(self.score_label)
        score_row.addStretch()  

        main_layout.addLayout(score_row)

        self.board_widget = QWidget()
        self.grid = QGridLayout()
        self.grid.setSpacing(2)
        self.board_widget.setLayout(self.grid)
        main_layout.addWidget(self.board_widget)

        self.wait_label = QLabel("Ждём подключения соперника...")
        self.wait_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.wait_label.setFont(QFont('Arial', 14, QFont.Weight.Bold))
        self.wait_label.setStyleSheet("color: #ff0000;")
        self.grid.addWidget(self.wait_label, 0, 0, 9, 9)

        self.setLayout(main_layout)

    def new_game(self):
        if hasattr(self, 'wait_label'):
            self.wait_label.hide()

        self.timer.stop()
        self.elapsed = 0
        self.time_label.setText('Время: 0')
        self.first_click = True

        self.remaining_flags = self.total_mines
        self.mine_label.setText(f'Мины: {self.remaining_flags}')

        while self.grid.count():
            item = self.grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        self.cells = [[Cell(x, y) for y in range(self.cols)] for x in range(self.rows)]
        for x in range(self.rows):
            for y in range(self.cols):
                cell = self.cells[x][y]
                cell.left_clicked.connect(self.on_left_click)
                cell.right_clicked.connect(self.on_right_click)
                self.grid.addWidget(cell, x, y)

        self.mines_planted = False
        self.game_over = False
        self.revealed_count = 0

        if self.client.my_id == 0:
            self.my_turn = True
        else:
            self.my_turn = False

        self.update_turn_label()


    def plant_mines(self, mines):
        for (x, y) in mines:
            self.cells[x][y].is_mine = True

        for x in range(self.rows):
            for y in range(self.cols):
                if self.cells[x][y].is_mine:
                    continue
                cnt = 0
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        if dx == 0 and dy == 0:
                            continue
                        nx, ny = x + dx, y + dy
                        if 0 <= nx < self.rows and 0 <= ny < self.cols:
                            if self.cells[nx][ny].is_mine:
                                cnt += 1
                self.cells[x][y].adjacent = cnt
        self.mines_planted = True


    def update_board(self, msg):
        cmd = msg.get("cmd")

        if cmd == "left_click":
            x, y = msg['x'], msg['y']
            if self.game_over:
                return
            cell = self.cells[x][y]
            if cell.flagged or cell.revealed:
                return
            if msg['first_click']:
                self.timer.start(1000)

            if cell.is_mine:
                cell.reveal()
                self._reveal_all_mines()
                self._game_lost()
                return

            self._reveal_cell(x, y)
            if self.my_turn:
                self.my_score += cell.adjacent
            else:
                self.enemy_score += cell.adjacent
            self.update_score_label()
            if self._check_win():
                self._game_won()

            self.update_turn_label()

    def update_turn_label(self):
        if self.my_turn:
            self.my_turn = False
        elif not self.my_turn:
            self.my_turn = True

        if self.my_turn is None:
            self.turn_label.setText("Ход: —")
        elif self.my_turn:
            self.turn_label.setText("Ход: ваш")
            self.turn_label.setStyleSheet("color: #008000; font-weight: bold;")
        else:
            self.turn_label.setText("Ход: соперника")
            self.turn_label.setStyleSheet("color: #cc0000; font-weight: bold;")

    def update_score_label(self):
        self.score_label.setText(
            f"Очки: вы — {self.my_score} | соперник — {self.enemy_score}"
        )
        
    def on_left_click(self, x, y):
        if self.my_turn:
            self.client.send_command({
                "cmd" : "left_click",
                "x" : x,
                "y" : y
            })


    def on_right_click(self, x, y):
        if self.game_over:
            return
        cell = self.cells[x][y]
        if cell.revealed:
            return
        cell.toggle_flag()
        if cell.flagged:
            self.remaining_flags -= 1
        else:
            self.remaining_flags += 1
        self.mine_label.setText(f'Мины: {self.remaining_flags}')


    def handle_disconnect(self):
        self.game_over = True
        self.timer.stop()

        QMessageBox.warning(self, "Игра остановлена", "Соперник отключился. Игра завершена.")
        QTimer.singleShot(300, self.close)

        for x in range(self.rows):
            for y in range(self.cols):
                self.cells[x][y].setDisabled(True)



    def _reveal_cell(self, x, y):
        cell = self.cells[x][y]
        if cell.revealed or cell.flagged:
            return
        cell.reveal()
        self.revealed_count += 1

        if cell.adjacent == 0 and not cell.is_mine:
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < self.rows and 0 <= ny < self.cols:
                        if not (dx == 0 and dy == 0):
                            self._reveal_cell(nx, ny)

    def _reveal_all_mines(self):
        for x in range(self.rows):
            for y in range(self.cols):
                c = self.cells[x][y]
                if c.is_mine and not c.revealed:
                    c.reveal()

    def _game_lost(self):
        self.game_over = True
        self.timer.stop()
        if self.my_turn:
            QMessageBox.information(self, 'Поражение', 'Вы наступили на мину! Победил соперник.')
        else:
            QMessageBox.information(self, 'Победа', 'Соперник наступили на мину! Вы победили.')
        QTimer.singleShot(300, self.close)


    def _game_won(self):
        self.game_over = True
        self.timer.stop()
        if self.my_score > self.enemy_score:
            msg = f"Вы победили!\nВаши очки: {self.my_score}\nОчки соперника: {self.enemy_score}"
        elif self.my_score < self.enemy_score:
            msg = f"Победил соперник!\nВаши очки: {self.my_score}\nОчки соперника: {self.enemy_score}"
        else:
            msg = f"Ничья!\nОчки: {self.my_score} : {self.enemy_score}"

        QMessageBox.information(self, "Итог игры", msg)
        QTimer.singleShot(500, self.close)

    def _check_win(self):
        total_cells = self.rows * self.cols
        return self.revealed_count == total_cells - self.total_mines

    def _tick(self):
        self.elapsed += 1
        self.time_label.setText(f'Время: {self.elapsed}')


def main():
    app = QApplication(sys.argv)
    w = Minesweeper(rows=9, cols=9, mines=10)
    w.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
