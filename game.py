import os
import sys
import time
import random
from typing import Optional

import pygame
import pygame.mixer as mixer
import chess
import chess.engine
from tqdm import tqdm

# --- Configuration ---
BOARD_SIZE = 512
HUD_HEIGHT = 48
WIDTH = BOARD_SIZE
HEIGHT = BOARD_SIZE + HUD_HEIGHT
SQ_SIZE = BOARD_SIZE // 8

STOCKFISH_PATH = r"C:\Users\Admin\Downloads\stockfish-windows-x86-64-universal\stockfish\stockfish-windows-x86-64-universal.exe"

class AssetManager:
    """Handles loading and storing of all game assets (images, sounds)."""
    def __init__(self):
        self.sounds = {
            "move": mixer.Sound("assets/move-self.ogg"),
            "check": mixer.Sound("assets/move-check.ogg"),
            "end": mixer.Sound("assets/game-end.ogg"),
            "promote": mixer.Sound("assets/promote.ogg"),
            "capture": mixer.Sound("assets/capture.ogg"),
            "castle": mixer.Sound("assets/castle.ogg")
        }
        
        self.piece_images = {}
        self.icon_images = {}
        self._load_pieces()
        self._load_icons()

    def _load_pieces(self):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        piece_names = ["pawn", "knight", "bishop", "rook", "queen", "king"]
        types = [chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN, chess.KING]
        
        for color_name, color_bool in [("white", chess.WHITE), ("black", chess.BLACK)]:
            for name, p_type in zip(piece_names, types):
                path = os.path.join(script_dir, f"{color_name}/{name}.png")
                try:
                    img = pygame.image.load(path).convert_alpha()
                    self.piece_images[(p_type, color_bool)] = pygame.transform.smoothscale(img, (SQ_SIZE, SQ_SIZE))
                except FileNotFoundError:
                    # Fallback text surface if image is missing
                    surf = pygame.Surface((SQ_SIZE, SQ_SIZE), pygame.SRCALPHA)
                    font = pygame.font.SysFont("Arial", 36, bold=True)
                    text_color = (255, 255, 255) if color_bool else (0, 0, 0)
                    text = font.render(name[0].upper(), True, text_color)
                    surf.blit(text, text.get_rect(center=(SQ_SIZE//2, SQ_SIZE//2)))
                    self.piece_images[(p_type, color_bool)] = surf

    def _load_icons(self):
        labels = ["Brilliant", "Great", "Book", "Best", "Excellent", "Good", 
                  "Inaccuracy", "Mistake", "Blunder", "Miss", "Forced"]
        for label in labels:
            path = f"assets/icons/{label.lower()}.png"
            try:
                img = pygame.image.load(path).convert_alpha()
                self.icon_images[label] = pygame.transform.smoothscale(img, (28, 28))
            except FileNotFoundError:
                self.icon_images[label] = None

class Evaluator:
    """Stockfish integration for evaluating position and move quality."""
    def __init__(self, stockfish_path: str, assets: AssetManager):
        self.engine = None
        self.assets = assets
        try:
            self.engine = chess.engine.SimpleEngine.popen_uci(stockfish_path)
        except Exception:
            print(f"[Warning] Stockfish not found at '{stockfish_path}'.")

    def analyze_move(self, board: chess.Board, move: chess.Move) -> tuple[str, Optional[pygame.Surface], str]:
        if not self.engine:
            return "N/A", None, "Eval: N/A"

        # 1. Forced Move Check
        if board.legal_moves.count() == 1:
            temp_board = board.copy()
            temp_board.push(move)
            info = self.engine.analyse(temp_board, chess.engine.Limit(time=0.05))
            rel_score = info["score"].pov(chess.WHITE)
            eval_str = f"Mate in {abs(rel_score.mate())}" if rel_score.is_mate() else f"Eval: {rel_score.score() / 100:+.2f}"
            return "Forced", self.assets.icon_images.get("Forced"), eval_str

        # 2. Pre-move evaluation
        info_before = self.engine.analyse(board, chess.engine.Limit(time=0.05), multipv=2)
        pv_list = info_before if isinstance(info_before, list) else [info_before]
        best_move = pv_list[0].get("pv", [None])[0]
        second_best = pv_list[1].get("pv", [None])[0] if len(pv_list) > 1 else None
        score_before = pv_list[0]["score"].pov(board.turn).score(mate_score=10000)

        # 3. Sacrifice Check
        piece_values = {chess.PAWN: 100, chess.KNIGHT: 300, chess.BISHOP: 320, chess.ROOK: 500, chess.QUEEN: 900, chess.KING: 20000}
        moving = board.piece_at(move.from_square)
        captured = board.piece_at(move.to_square)
        m_val = piece_values.get(moving.piece_type, 0) if moving else 0
        c_val = piece_values.get(captured.piece_type, 0) if captured else 0
        is_sacrifice = (m_val - c_val) >= 200

        # 4. Post-move evaluation
        temp_board = board.copy()
        temp_board.push(move)
        info_after = self.engine.analyse(temp_board, chess.engine.Limit(time=0.05))
        score_after = info_after["score"].pov(board.turn).score(mate_score=10000)
        rel_score = info_after["score"].pov(chess.WHITE)
        eval_str = f"Mate in {abs(rel_score.mate())}" if rel_score.is_mate() else f"Eval: {rel_score.score() / 100:+.2f}"

        # 5. Label Logic
        loss = score_before - score_after
        if move == best_move:
            label = "Brilliant" if (is_sacrifice and score_after >= 0) else "Best"
        elif loss <= 0 and move == second_best:
            label = "Great"
        elif loss <= 15:
            label = "Excellent"
        elif loss <= 35:
            label = "Good"
        elif loss <= 80:
            label = "Inaccuracy"
        elif loss <= 200:
            label = "Mistake"
        elif score_before >= 300 and score_after <= 50:
            label = "Miss"
        else:
            label = "Blunder"

        return label, self.assets.icon_images.get(label), eval_str

    def close(self):
        if self.engine:
            self.engine.quit()

class ChessGame:
    def __init__(self):
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Chess Analyzer")
        self.clock = pygame.time.Clock()
        
        self.assets = AssetManager()
        self.board = chess.Board()
        self.evaluator = Evaluator(STOCKFISH_PATH, self.assets)
        
        self.player_team = chess.WHITE if random.choice([True, False]) else chess.BLACK
        self.selected_square = None
        self.last_move = None
        
        self.last_label = "N/A"
        self.last_icon = None
        self.last_score = "Eval: +0.00"
        
        self.game_over = False
        self.opponent_move_time = pygame.time.get_ticks() + 3000 if self.player_team == chess.BLACK else None

    def execute_move(self, move: chess.Move):
        self.last_label, self.last_icon, self.last_score = self.evaluator.analyze_move(self.board, move)
        self.last_move = move
        
        is_promo = bool(move.promotion)
        is_castle = self.board.is_castling(move)
        is_capture = self.board.is_capture(move)
        
        self.board.push(move)
        
        if self.board.is_checkmate():
            self.assets.sounds["check"].play()
            pygame.time.delay(60)
            self.assets.sounds["end"].play()
            self.game_over = True
        elif self.board.is_check():
            self.assets.sounds["check"].play()
        elif is_promo:
            self.assets.sounds["promote"].play()
        elif is_castle:
            self.assets.sounds["castle"].play()
        elif is_capture:
            self.assets.sounds["capture"].play()
        else:
            self.assets.sounds["move"].play()
            
        if self.board.is_stalemate():
            self.assets.sounds["end"].play()
            self.game_over = True

    def draw(self):
        colors = [pygame.Color(235, 236, 208), pygame.Color(115, 149, 82)]
        highlight = pygame.Color(246, 246, 105, 150)

        # Draw Board & Pieces
        for row in range(8):
            for col in range(8):
                rect = pygame.Rect(col * SQ_SIZE, row * SQ_SIZE, SQ_SIZE, SQ_SIZE)
                pygame.draw.rect(self.screen, colors[(row + col) % 2], rect)

                file = col if self.player_team == chess.WHITE else 7 - col
                rank = 7 - row if self.player_team == chess.WHITE else row
                sq = chess.square(file, rank)

                if sq == self.selected_square:
                    s = pygame.Surface((SQ_SIZE, SQ_SIZE), pygame.SRCALPHA)
                    s.fill(highlight)
                    self.screen.blit(s, rect)

                piece = self.board.piece_at(sq)
                if piece:
                    img = self.assets.piece_images.get((piece.piece_type, piece.color))
                    if img:
                        self.screen.blit(img, rect)
                        
                # Draw evaluation icon on the destination square of the last move
                if self.last_move and sq == self.last_move.to_square and self.last_icon:
                    icon_rect = self.last_icon.get_rect(topright=(rect.right - 2, rect.top + 2))
                    self.screen.blit(self.last_icon, icon_rect)

        # Draw HUD
        hud_rect = pygame.Rect(0, BOARD_SIZE, WIDTH, HUD_HEIGHT)
        pygame.draw.rect(self.screen, (30, 30, 30), hud_rect)
        font = pygame.font.SysFont("Arial", 20, bold=True)
        
        score_surf = font.render(self.last_score, True, (255, 255, 255))
        self.screen.blit(score_surf, (15, BOARD_SIZE + 12))
        
        label_surf = font.render(f"Move: {self.last_label}", True, (255, 255, 255))
        label_x = WIDTH - label_surf.get_width() - 15
        self.screen.blit(label_surf, (label_x, BOARD_SIZE + 12))
        
        if self.last_icon:
            self.screen.blit(self.last_icon, (label_x - 35, BOARD_SIZE + 10))

        pygame.display.flip()

    def run(self):
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_x):
                    running = False

                elif event.type == pygame.MOUSEBUTTONDOWN and not self.game_over and self.board.turn == self.player_team:
                    x, y = pygame.mouse.get_pos()
                    if y < BOARD_SIZE:
                        col, row = x // SQ_SIZE, y // SQ_SIZE
                        sq = chess.square(col, 7 - row) if self.player_team == chess.WHITE else chess.square(7 - col, row)

                        if self.selected_square is None:
                            piece = self.board.piece_at(sq)
                            if piece and piece.color == self.player_team:
                                self.selected_square = sq
                        else:
                            move = chess.Move(self.selected_square, sq)
                            piece = self.board.piece_at(self.selected_square)
                            
                            # Handle Auto-Queen Promotion
                            if piece and piece.piece_type == chess.PAWN:
                                if chess.square_rank(sq) in [0, 7]:
                                    move = chess.Move(self.selected_square, sq, promotion=chess.QUEEN)

                            if move in self.board.legal_moves:
                                self.execute_move(move)
                                self.selected_square = None
                                self.opponent_move_time = pygame.time.get_ticks() + 800
                            else:
                                clicked_piece = self.board.piece_at(sq)
                                self.selected_square = sq if clicked_piece and clicked_piece.color == self.player_team else None

            # Opponent turn
            if not self.game_over and self.board.turn != self.player_team:
                if self.opponent_move_time and pygame.time.get_ticks() >= self.opponent_move_time:
                    legal_moves = list(self.board.legal_moves)
                    if legal_moves:
                        self.execute_move(random.choice(legal_moves))
                    self.opponent_move_time = None

            self.draw()
            self.clock.tick(60)

        self.evaluator.close()
        pygame.quit()
        sys.exit()

def initial_loading():
    """Simulates a loading bar for aesthetic purposes."""
    with tqdm(total=100, desc="Loading Engine", unit="%", bar_format="{desc}: {percentage:3.0f}%|{bar}|") as pbar:
        for _ in range(20):
            time.sleep(0.05)
            pbar.update(5)

if __name__ == "__main__":
    pygame.init()
    mixer.init()
    initial_loading()
    game = ChessGame()
    game.run()
