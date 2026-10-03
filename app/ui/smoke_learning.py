"""Real executable smoke: capture/history/restart, offline teaching, both colors and calibration."""
from __future__ import annotations

from dataclasses import asdict
import json
import random
import time

import chess
from PySide6.QtCore import QTimer

from app.adaptive.rating import PlayerProfile
from app.adaptive.selector import Candidate, select_move
from app.services.calibration import GameCalibration
from app.services.game import GameState
from app.services.material import MaterialSnapshot
from app.ui.dialogs import AnalysisDialog

LOSS_FEN = 'r5k1/5ppp/8/4p3/8/8/PP3PPP/3Q2K1 w - - 0 1'


def attach_learning_smoke(app,window,report_path,resume=False):
    state = {'phase':'resume' if resume else 'capture','started':time.monotonic(),
             'scenarios':[],'material_resume_verified':False,'clock_resume_verified':False}
    timer = QTimer(window)
    timer.setInterval(30)

    def finish(success,message):
        timer.stop()
        report = {'success':success,'message':message,'window_visible':window.isVisible(),
                  'database_created':(window.directory/'chess.sqlite3').is_file(),
                  'settings_created':(window.directory/'settings.json').is_file(),
                  'material_resume_verified':state['material_resume_verified'],'clock_resume_verified':state['clock_resume_verified'],
                  'coaching_scenarios':state['scenarios'],'calibration_sample':state.get('calibration_sample')}
        if window.game:
            report['material'] = asdict(MaterialSnapshot.from_board(window.game.board))
            report['fen'] = window.game.board.fen()
            report['bot_diagnostics'] = window.calibration.summary() if window.calibration else {}
        window.close()
        report['clock_state'] = window.game.clock_state if window.game else None
        report['engine_closed'] = window.engine._engine is None
        report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        app.exit(0 if success else 1)

    def fixture(color):
        window.invalidate_worker()
        window.busy = False
        board = chess.Board(LOSS_FEN)
        move = chess.Move.from_uci('d1d4')
        if color == chess.BLACK:
            board = board.mirror()
            move = chess.Move(chess.square_mirror(move.from_square),chess.square_mirror(move.to_square))
        profile = window.store.profile()
        game = GameState(player_color=color,board=board,bot_rating=profile.target,rating_before=profile.rating)
        window.session.resume(game)
        window.calibration = GameCalibration(window.directory,game)
        window.navigator.current()
        window.last_selection = None
        window._pending_result = None
        window._end_notified = None
        window.refresh()
        window.human_move(move.from_square,move.to_square)
        state['color'] = color
        state['phase'] = 'reply'

    def sample(rating):
        board = chess.Board()
        candidates = [Candidate(chess.Move.from_uci(m),s) for m,s in zip(
            ['e2e4','d2d4','g1f3','c2c4','b1c3','a2a3','h2h3','b2b3'],[100,95,80,50,20,-20,-70,-120])]
        rng = random.Random(832)
        choices = [select_move(board,candidates,rating,rng) for _ in range(1000)]
        return {'rating':rating,'samples':1000,'average_cpl':sum(c.selected_cpl for c in choices)/1000,
                'top_two_fraction':sum(c.selected_rank <= 2 for c in choices)/1000}

    def tick():
        try:
            if time.monotonic()-state['started'] > 70:
                raise AssertionError('Learning smoke timed out')
            if state['phase'] == 'capture':
                profile = PlayerProfile(rating=832,games=10)
                with window.store.connection:
                    window.store.connection.execute('INSERT OR REPLACE INTO profile VALUES(1,?)',(json.dumps(asdict(profile)),))
                window.settings.values['sound'] = False
                window.time_combo.setCurrentIndex(window.time_combo.findData('3+2'))
                window._start_game(chess.WHITE)
                assert window.game.bot_rating == profile.target and profile.difficulty_offset < 60
                window.session.play(chess.Move.from_uci('e2e4'))
                window.session.play(chess.Move.from_uci('d7d5'))
                window.invalidate_worker()
                window.refresh()
                window.human_move(chess.E4,chess.D5)
                assert window.top_material.snapshot.black_lost == (chess.PAWN,)
                assert window.bottom_material.snapshot.balance(chess.WHITE) == 1
                window.grab().save(str(report_path.with_name('learning-capture.png')))
                pgn,token = window.game.pgn(),window.token
                window.previous_position()
                assert window.top_material.snapshot.black_lost == ()
                assert window.bottom_material.snapshot.balance(chess.WHITE) == 0
                assert window.game.pgn() == pgn and window.token == token
                window.grab().save(str(report_path.with_name('learning-history.png')))
                window.current_position()
                assert window.top_material.snapshot.black_lost == (chess.PAWN,)
                state['phase'] = 'capture_reply'
                return
            if state['phase'] == 'capture_reply':
                if window.busy or window.board.animating:
                    return
                assert len(window.game.board.move_stack) == 4 and window.game.result == '*'
                assert window.calibration.summary()['moves'] == 1
                assert len(window.last_selection.candidates) > 8
                assert window.game.board.turn == window.session.clock.active == chess.WHITE
                finish(True,'Real low-rating opponent, capture SVG strips, historical material, live return, diagnostics and save passed')
                return
            if state['phase'] == 'resume':
                previous = json.loads((report_path.parent/'learning.json').read_text(encoding='utf-8'))
                saved = window.store.unfinished()
                assert saved and saved.clock_state == previous['clock_state']
                window.resume_game()
                current = json.loads(json.dumps(asdict(MaterialSnapshot.from_board(window.game.board))))
                assert current == previous['material'] and window.game.board.fen() == previous['fen']
                assert window.calibration.summary() == previous['bot_diagnostics']
                for color,key in [(chess.WHITE,'white_seconds'),(chess.BLACK,'black_seconds')]:
                    assert abs(window.session.clock.remaining(color)-previous['clock_state'][key]) < .2
                state['material_resume_verified'] = state['clock_resume_verified'] = True
                fixture(chess.WHITE)
                return
            if state['phase'] == 'reply':
                if window.busy or window.board.animating or window.board.presenting_end:
                    return
                assert len(window.game.board.move_stack) == 2, 'Real opponent did not answer the teaching fixture'
                assert window.calibration.summary()['moves'] == 1
                if window.game.result == '*':
                    window.session.resign()
                window.advance()
                state['phase'] = 'analysis'
                return
            if state['phase'] == 'analysis':
                if window.busy or window.board.presenting_end:
                    return
                row = next(row for row in window.store.history() if row['id'] == window.game.database_id)
                assert row['rated'] and row['analysis']
                move = json.loads(row['analysis'])[0]
                notes = move['coaching']
                assert notes and len(notes['alternatives']) == 3 and notes['confidence'] != 'fallback'
                assert notes['after_cp'] is None or notes['after_cp'] < 0, 'Score was not from the player perspective'
                window.show_analysis(window.game.database_id)
                dialog = next(d for d in reversed(window.dialogs) if isinstance(d,AnalysisDialog))
                assert dialog.variations.count() == 3 and dialog.advice.text() == notes['advice']
                actual_game,actual_dialog = window.game.pgn(),dialog.game.pgn()
                actual_position = dialog.root_position.copy()
                actual_position.push(dialog.game.board.move_stack[dialog.moves[dialog.selected_row]['ply']-1])
                actual_position = actual_position.fen()
                dialog.variations.setCurrentRow(0)
                assert dialog.line_moves and not dialog.board.interactive
                dialog.next.click()
                dialog.previous.click()
                dialog.actual_button.click()
                assert dialog.board.board.fen() == actual_position
                assert window.game.pgn() == actual_game and dialog.game.pgn() == actual_dialog
                dialog.grab().save(str(report_path.with_name('learning-analysis-'+('white' if state['color'] else 'black')+'.png')))
                state['scenarios'].append({'player':'white' if state['color'] else 'black','alternatives':3,
                                          'reason':notes['reason'],'confidence':notes['confidence'],
                                          'pv_lengths':[len(v['pv_uci']) for v in notes['alternatives']]})
                if state['color'] == chess.WHITE:
                    fixture(chess.BLACK)
                    return
                weak,strong = sample(900),sample(2200)
                assert weak['average_cpl'] > strong['average_cpl']+50 and strong['top_two_fraction'] > weak['top_two_fraction']+.4
                state['calibration_sample'] = {'kind':'fixed synthetic candidate set, not an Elo certification','weak':weak,'strong':strong}
                finish(True,'Restarted material/clocks/diagnostics, real offline MultiPV teaching for both colors, read-only PV review and deterministic calibration passed')
        except Exception as error:
            finish(False,f'{type(error).__name__}: {error}')

    timer.timeout.connect(tick)
    timer.start()
    return timer
