import pygame
import chess
import chess.engine
import random
import os
import sys
import time
from tqdm import tqdm
from typing import TypeAlias
pygame.init()
import pygame.mixer as mixer
mixer.init()
progress:int= 100
import time
from tqdm import tqdm
PYGAME_DETECT_AVX2=1
with tqdm(
    total=progress,
    desc="Loading...",
    unit="%",
    unit_scale=True,
    ascii="// ",       # Uses '/' as the bar fill character
    colour="#708030",   # Muted green/olive color matching the image
    bar_format="{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]"
) as pbar:
    for _ in range(100):
        time.sleep(0.2)
        pbar.update(1)  # Advance by 10 MB per iteration
if sys.platform == "win32":
    os.chdir(r"G:\chess") # replace the disk label
elif sys.platform == "darwin": os.chdir("/media/administrator/data/chess") #replace the username
else: os.chdir("/media/administrator/data/chess") # Replace the administrator username with ur username!
# Setup Screen Constraints
BOARD_SIZE = 512
HUD_HEIGHT = 48
WIDTH = BOARD_SIZE
HEIGHT = BOARD_SIZE + HUD_HEIGHT
SQ_SIZE = BOARD_SIZE // 8
run:TypeAlias = bool
# Sound (checkmate, check, etc...)
SOUND = {
    "move": mixer.Sound("assets/move-self.ogg"),
    "check": mixer.Sound("assets/move-check.ogg"),
    "end": mixer.Sound("assets/game-end.ogg"),
    "promote": mixer.Sound("assets/promote.ogg"),
    "capture": mixer.Sound("assets/capture.ogg"),
    "castle": mixer.Sound("assets/castle.ogg")
}
"Sounds."

STOCKFISH_PATH = "/home/administrator/Downloads/stockfish/stockfish-ubuntu-x86-64-avx2"
"Stockfish AI evaluates each move is brilliant or blunder."
class Board:
    "just a board"
    @staticmethod
    def init():
        return chess.Board()

class Pieces:
    """Load pieces into target :class:`pygame.Surface()` instance."""
    def __init__(self):
        self.WHITE: str = "white"
        self.BLACK: str = "black"
        self.WHITE_PIECES = {
            "rook": "white/rook.png", "knight": "white/knight.png",
            "bishop": "white/bishop.png", "king": "white/king.png",
            "queen": "white/queen.png", "pawn": "white/pawn.png"
        }
        self.BLACK_PIECES = {
            "rook": "black/rook.png", "knight": "black/knight.png",
            "bishop": "black/bishop.png", "king": "black/king.png",
            "queen": "black/queen.png", "pawn": "black/pawn.png"
        }
        self.PIECES = {
            "white": self.WHITE_PIECES,
            "black": self.BLACK_PIECES
        }
        
        self.images = {}
        self.load_images()

    def load_images(self):
        type_map = {
            "pawn": chess.PAWN, "knight": chess.KNIGHT, "bishop": chess.BISHOP,
            "rook": chess.ROOK, "queen": chess.QUEEN, "king": chess.KING
        }

        script_dir = os.path.dirname(os.path.abspath(__file__))

        for color_name, piece_dict in self.PIECES.items():
            color_bool = chess.WHITE if color_name == "white" else chess.BLACK
            
            for name, path in piece_dict.items():
                p_type = type_map[name]
                full_image_path = os.path.join(script_dir, path)
                
                try:
                    if os.path.exists(full_image_path):
                        img = pygame.image.load(full_image_path).convert_alpha()
                        img = pygame.transform.smoothscale(img, (SQ_SIZE, SQ_SIZE))
                        self.images[(p_type, color_bool)] = img
                    else:
                        raise FileNotFoundError
                except Exception:
                    surf = pygame.Surface((SQ_SIZE, SQ_SIZE), pygame.SRCALPHA)
                    font = pygame.font.SysFont("Arial", 36, bold=True)
                    text_color = (255, 255, 255) if color_bool else (0, 0, 0)
                    text = font.render(name[0].upper(), True, text_color)
                    text_rect = text.get_rect(center=(SQ_SIZE//2, SQ_SIZE//2))
                    surf.blit(text, text_rect)
                    self.images[(p_type, color_bool)] = surf

    def random_team(self):
        return chess.WHITE if random.choice(["white", "black"]) == "white" else chess.BLACK


class Evaluator:
    """Stockfish integration for evaluating position and move quality."""
    def __init__(self, stockfish_path: str):
        self.engine = None
        try:
            self.engine = chess.engine.SimpleEngine.popen_uci(stockfish_path)
        except Exception:
            print(f"[Warning] Stockfish not found at '{stockfish_path}'. Running without AI evaluation.")

    def analyze_move(self, board: chess.Board, move: chess.Move) -> tuple[str, str]:
        if not self.engine:
            return "N/A", "Eval: N/A"

        piece_values = {
            chess.PAWN: 100, chess.KNIGHT: 300, chess.BISHOP: 320,
            chess.ROOK: 500, chess.QUEEN: 900, chess.KING: 20000
        }

        # 1. Pre-move evaluation
        info_before = self.engine.analyse(board, chess.engine.Limit(time=0.05))
        best_move = info_before.get("pv", [None])[0]
        score_before = info_before["score"].pov(board.turn).score(mate_score=10000)

        # 2. Check for sacrifice
        moving_piece = board.piece_at(move.from_square)
        captured_piece = board.piece_at(move.to_square)
        moving_val = piece_values.get(moving_piece.piece_type, 0) if moving_piece else 0
        captured_val = piece_values.get(captured_piece.piece_type, 0) if captured_piece else 0
        is_sacrifice = (moving_val - captured_val) >= 200
        "Sacrifice check"
        # 3. Post-move evaluation
        temp_board = board.copy()
        temp_board.push(move)
        info_after = self.engine.analyse(temp_board, chess.engine.Limit(time=0.05))
        score_after = info_after["score"].pov(board.turn).score(mate_score=-10000)

        # 4. Format eval score text
        rel_score = info_after["score"].pov(chess.WHITE)
        if rel_score.is_mate():
            eval_str = f"Mate in {abs(rel_score.mate())}"
        else:
            eval_str = f"Eval: {rel_score.score() / 100:+.2f}"

        # 5. Determine quality classification
        loss = score_before - score_after
        if move == best_move:
            label = "Brilliant" if is_sacrifice and score_after >= 0 else "Best"
        elif loss <= 25:
            label = "Good"
        elif loss <= 80:
            label = "Inaccuracy"
        elif loss <= 220:
            label = "Mistake"
        else:
            label = "Blunder"

        return label, eval_str

    def close(self):
        if self.engine:
            self.engine.quit()


class Player:
    "Base player."
    def __init__(self, pieces: Pieces, board: chess.Board):
        self.pieces = pieces
        self.board = board
        self.team = self.pieces.random_team()


class You(Player):
    "Base you."
    def __init__(self, pieces: Pieces, board_logic: chess.Board):
        self.board = board_logic 
        self.pieces = pieces
        super().__init__(self.pieces, self.board)
        self.has_checkmated = False
        self.has_check = False
        self.has_stalemate = False

    def checkmate(self): self.has_checkmated = True
    def check(self): self.has_check = True
    def stalemate(self): self.has_stalemate = True
class Opponent(Player):
    "Base opponent."
    def __init__(self, pieces: Pieces, board_logic: chess.Board, player_team: bool):
        super().__init__(pieces, board_logic)
        self.team = chess.BLACK if player_team == chess.WHITE else chess.WHITE
        self.has_checkmated = False
        self.has_check = False
        self.has_stalemate = False

    def get_random_move(self) -> chess.Move | None:
        legal_moves = list(self.board.legal_moves)
        return random.choice(legal_moves) if legal_moves else None

    def checkmate(self): self.has_checkmated = True
    def check(self): self.has_check = True
    def stalemate(self): self.has_stalemate = True


def draw_board(screen: pygame.Surface, board_logic: chess.Board, pieces: Pieces, player_team: bool, selected_square: int):
    colors = [pygame.Color(235, 236, 208), pygame.Color(115, 149, 82)]
    highlight_color = pygame.Color(246, 246, 105, 150) 

    for row in range(8):
        for col in range(8):
            color = colors[(row + col) % 2]
            rect = pygame.Rect(col * SQ_SIZE, row * SQ_SIZE, SQ_SIZE, SQ_SIZE)
            pygame.draw.rect(screen, color, rect)

            file = col if player_team == chess.WHITE else 7 - col
            rank = 7 - row if player_team == chess.WHITE else row
            sq = chess.square(file, rank)

            if sq == selected_square:
                s = pygame.Surface((SQ_SIZE, SQ_SIZE), pygame.SRCALPHA)
                s.fill(highlight_color)
                screen.blit(s, rect)

            piece = board_logic.piece_at(sq)
            if piece:
                img = pieces.images.get((piece.piece_type, piece.color))
                if img:
                    screen.blit(img, rect)


def draw_hud(screen: pygame.Surface, eval_label: str, eval_score: str):
    """Renders the bottom evaluation bar."""
    hud_rect = pygame.Rect(0, BOARD_SIZE, WIDTH, HUD_HEIGHT)
    pygame.draw.rect(screen, (30, 30, 30), hud_rect)

    color_map = {
        "Brilliant": (0, 225, 255), "Best": (76, 175, 80),
        "Good": (139, 195, 74), "Inaccuracy": (255, 235, 59),
        "Mistake": (255, 152, 0), "Blunder": (244, 67, 54),
        "N/A": (180, 180, 180)
    }

    font = pygame.font.SysFont("Arial", 20, bold=True)
    score_surf = font.render(eval_score, True, (255, 255, 255))
    label_surf = font.render(f"Move: {eval_label}", True, color_map.get(eval_label, (255, 255, 255)))

    screen.blit(score_surf, (15, BOARD_SIZE + 12))
    screen.blit(label_surf, (WIDTH - label_surf.get_width() - 15, BOARD_SIZE + 12))


def play_move_sound(board_logic: chess.Board, move: chess.Move):
    """Determines sound effects based on board state, plays audio, and pushes the move."""
    is_promo = bool(move.promotion)
    is_castle = board_logic.is_castling(move)
    is_capture = board_logic.is_capture(move)

    # Push move to inspect resulting board state
    board_logic.push(move)

    if board_logic.is_checkmate():
        SOUND["check"].play()
        pygame.time.delay(60)
        SOUND["end"].play()
    elif board_logic.is_check():
        SOUND["check"].play()
    elif is_promo:
        SOUND["promote"].play()
    elif is_castle:
        SOUND["castle"].play()
    elif is_capture:
        SOUND["capture"].play()
    else:
        SOUND["move"].play()


def main() -> None:
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Chess")
    clock = pygame.time.Clock()

    board_logic = Board.init()
    pieces = Pieces()
    evaluator = Evaluator(STOCKFISH_PATH)

    player = You(pieces, board_logic)
    opponent = Opponent(pieces, board_logic, player.team)
    
    selected_square = None
    running = True
    game_over = False

    last_label = "N/A"
    last_score = "Eval: +0.00"

    opponent_move_time = None
    if opponent.team == chess.WHITE:
        opponent_move_time = pygame.time.get_ticks() + 3000

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_x:
                    running = False

            elif event.type == pygame.MOUSEBUTTONDOWN and board_logic.turn == player.team and not game_over:
                x, y = pygame.mouse.get_pos()
                if y < BOARD_SIZE:  # Click inside board area
                    col = x // SQ_SIZE
                    row = y // SQ_SIZE
                    
                    sq = chess.square(col, 7 - row) if player.team == chess.WHITE else chess.square(7 - col, row)

                    if selected_square is None:
                        piece = board_logic.piece_at(sq)
                        if piece and piece.color == player.team:
                            selected_square = sq
                    else:
                        move = chess.Move(selected_square, sq)
                        moving_piece = board_logic.piece_at(selected_square)
                        
                        # Handle Pawn Promotion
                        if moving_piece and moving_piece.piece_type == chess.PAWN:
                            if (player.team == chess.WHITE and chess.square_rank(sq) == 7) or \
                               (player.team == chess.BLACK and chess.square_rank(sq) == 0):
                                move = chess.Move(selected_square, sq, promotion=chess.QUEEN)
                                
                        if move in board_logic.legal_moves:
                            last_label, last_score = evaluator.analyze_move(board_logic, move)
                            play_move_sound(board_logic, move)  # Plays sound AND pushes move
                            selected_square = None
                            opponent_move_time = pygame.time.get_ticks() + 800 
                            
                        else:
                            piece = board_logic.piece_at(sq)
                            if piece and piece.color == player.team:
                                selected_square = sq
                            else:
                                selected_square = None

        # Opponent move execution
        if not game_over and board_logic.turn == opponent.team:
            if opponent_move_time is not None and pygame.time.get_ticks() >= opponent_move_time:
                op_move = opponent.get_random_move()
                if op_move:
                    last_label, last_score = evaluator.analyze_move(board_logic, op_move)
                    play_move_sound(board_logic, op_move)  # Plays sound AND pushes move
                opponent_move_time = None

        # Check Game Over conditions
        if not game_over:
            if board_logic.is_checkmate():
                game_over = True
                if board_logic.turn == opponent.team:
                    player.checkmate()
                    print("Checkmate! You win!")
                else:
                    opponent.checkmate()
                    print("Checkmate! Opponent wins!")
                    
            elif board_logic.is_stalemate():
                game_over = True
                SOUND["end"].play()
                player.stalemate()
                opponent.stalemate()
                print("Stalemate! The game is a draw.")

        # Render loop
        draw_board(screen, board_logic, pieces, player.team, selected_square)
        draw_hud(screen, last_label, last_score)
        
        pygame.display.flip()
        clock.tick(60)

    evaluator.close()
    pygame.quit()
    sys.exit()


if __name__ == "__main__": 
    main()
