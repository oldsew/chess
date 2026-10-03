"""DPI/layout and history motion evidence from the actual source or frozen application."""
from __future__ import annotations

import json
import time
import chess
import chess.engine
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from app.services.clocks import time_control
from app.services.coaching import build_coaching
from app.services.game import GameState
from app.services.live import LiveEvaluation
from app.ui.dialogs import AnalysisDialog, SettingsDialog, StatisticsDialog
from app.ui.smoke_polish import SCENARIOS
from app.ui.style import ADVANTAGE_COLORS


def attach_visual_smoke(app,window,report_path):
    scale = float(__import__('os').environ.get('QT_SCALE_FACTOR','1'))
    state={'start':time.monotonic(),'index':0,'frames':0,'animations':[],'active':False,'phase':'history'}
    timer=QTimer(window);timer.setInterval(16)
    window.board.animations_enabled=True
    window.sounds.set_enabled(False)
    width,height=int(1366/scale),int(768/scale)
    window.resize(width,height)

    def finish(success,message):
        timer.stop()
        report={'success':success,'message':message,'window_visible':window.isVisible(),
                'scale_factor':scale,'device_pixel_ratio':window.devicePixelRatioF(),
                'requested_logical_size':[width,height],'actual_logical_size':[window.width(),window.height()],
                'historical_transitions':state['animations'],'layout':state.get('layout'),
                'explanations':state.get('explanation'),'semantic_colors':state.get('colors')}
        window.close();report['engine_closed']=window.engine._engine is None
        report['database_created']=(window.directory/'chess.sqlite3').exists()
        report['settings_created']=(window.directory/'settings.json').exists()
        report_path.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
        app.exit(0 if success else 1)

    def tick():
        try:
            assert time.monotonic()-state['start']<30,'Visual smoke timed out'
            if state['phase']=='history':
                index=state['index']
                if index<len(SCENARIOS)*2:
                    name,fen,uci,count,capture,promotion=SCENARIOS[index//2]
                    reverse=bool(index%2)
                    if not state['active']:
                        before=chess.Board(fen);after=before.copy();after.push_uci(uci)
                        window.board.set_position(after if reverse else before)
                        window.board.set_position(before if reverse else after,animate=True,celebrate=False)
                        transition=window.board.transition
                        assert transition and transition.reverse==reverse and len(transition.motions)==count
                        assert bool(transition.captured)==capture
                        assert bool(transition.motions[0].promoted_piece)==promotion
                        assert all(r.isValid() for r in window.board.renderers.values())
                        state.update(active=True,frames=0,target=(before if reverse else after).fen())
                        return
                    if window.board.animating:
                        if 0<window.board.progress<1:
                            state['frames']+=1
                            if state['frames']==4 and reverse and capture:
                                window.grab().save(str(report_path.with_name(report_path.stem+'-capture-restore.png')))
                        return
                    assert state['frames']>=3 and window.board.board.fen()==state['target']
                    assert not window.board.presenting_end
                    state['animations'].append({'name':name,'reverse':reverse,'frames':state['frames']})
                    state.update(index=index+1,active=False)
                    return
                state['phase']='layout'
                window.session.start(chess.WHITE,time_control('3+2'))
                for uci in ['e2e4','d7d5','e4d5','d8d5','b1c3','d5e5']:
                    window.session.play(chess.Move.from_uci(uci))
                window.refresh()
                original=window.game.pgn(),window.game.board.fen()
                for _ in range(4):
                    for _ in range(6):window.previous_position()
                    for _ in range(6):window.next_position()
                window.current_position()
                assert (window.game.pgn(),window.game.board.fen())==original
                assert window.board.board.fen()==original[1]
                state['phase']='settle'
                return
            if state['phase']=='settle':
                timer.stop()  # processEvents below paints dialogs; never reenter this scenario.
                assert window.width()<=width and window.height()<=height, 'Window exceeds 1366x768 at selected DPI'
                assert min(window.board.width(),window.board.height())>=300
                for widget in [window.player_clock,window.bot_clock,window.previous_button,window.current_button,window.save_button]:
                    corner=widget.mapTo(window,widget.rect().bottomRight())
                    assert 0<=corner.y()<window.height() and 0<=corner.x()<window.width()
                state['layout']={'board':[window.board.width(),window.board.height()],'clock_and_navigation_visible':True}
                state['colors']=[]
                for cp in [-300,-150,-60,0,60,150,300]:
                    score=chess.engine.PovScore(chess.engine.Cp(cp),chess.WHITE)
                    value=LiveEvaluation.from_info(window.game.board,{'score':score,'depth':10})
                    window.on_live(window.token,value)
                    level=window.indicator.level
                    assert ADVANTAGE_COLORS[level] in window.position_label.styleSheet()
                    assert window.position_label.text()==window.indicator.text
                    state['colors'].append({'cp':cp,'level':level,'color':ADVANTAGE_COLORS[level]})
                window.grab().save(str(report_path.with_suffix('.png')))
                for color in (True,False):
                    fen='r5k1/5ppp/8/4p3/8/8/PP3PPP/3Q2K1 w - - 0 1'
                    board=chess.Board(fen);move=chess.Move.from_uci('d1d4')
                    def info(cp,pv):
                        moves=[chess.Move.from_uci(uci) for uci in pv.split()]
                        if not color:
                            moves=[chess.Move(chess.square_mirror(m.from_square),chess.square_mirror(m.to_square)) for m in moves]
                        return {'score':chess.engine.PovScore(chess.engine.Cp(cp),color),'pv':moves,'depth':16}
                    if not color:
                        board=board.mirror();move=chess.Move(chess.square_mirror(move.from_square),chess.square_mirror(move.to_square))
                    notes=build_coaching(board,move,info(400,'d1d2'),info(-600,'e5d4 g1f1 a8c8'),
                                         [info(400,'d1d2 a8c8 d2d3'),info(380,'d1e2 a8c8 e2d3'),info(350,'d1f3 a8c8 f3d3')],color)
                    played_san=board.san(move)
                    game=GameState(board=board.copy(),player_color=color);game.play(move)
                    row={'result':'0-1','accuracy':30.,'player_color':color,'pgn':game.pgn(),
                         'analysis':json.dumps([{'ply':1,'san':played_san,'best_san':notes['alternatives'][0]['san'],
                                                'category':'Грубая ошибка','cpl':1000,'before_cp':400,'after_cp':-600,'coaching':notes}])}
                    dialog=AnalysisDialog(row,window)
                    dialog.board.animations_enabled=True  # Exercise full motion independently of runner preferences.
                    dialog.resize(width-40,height-40);dialog.show();QApplication.processEvents()
                    assert dialog.width()<=width and dialog.height()<=height,'Analysis window does not fit'
                    assert dialog.showing_before and len(dialog.board.annotations)==2
                    assert 'сохраняет материал' in dialog.recommendation.text()
                    assert dialog.explanation_debug.isHidden()
                    assert dialog.board.orientation==color and not dialog.board.interactive
                    for widget in [dialog.actual_button,dialog.next,dialog.previous]:
                        corner=widget.mapTo(dialog,widget.rect().bottomRight())
                        assert corner.x()<dialog.width() and corner.y()<dialog.height()
                    dialog.grab().save(str(report_path.with_name(report_path.stem+'-analysis-'+('white' if color else 'black')+'.png')))
                    actual=dialog.game.pgn()
                    dialog.variations.setCurrentRow(0)
                    assert dialog.board.animating and not dialog.board.presenting_end
                    dialog.step_variation(1);dialog.step_variation(-1)
                    assert dialog.board.transition and dialog.board.transition.reverse
                    dialog.return_to_actual();assert dialog.board.board.fen()==game.board.fen()
                    assert dialog.game.pgn()==actual
                    dialog.close()
                window.show_history()
                window.show_statistics()
                window._present(SettingsDialog(window.settings.values,window))
                QApplication.processEvents()
                for dialog in window.dialogs:
                    dialog.grab().save(str(report_path.with_name(report_path.stem+'-'+str(dialog.windowTitle()).replace(' ','-')+'.png')))
                state['explanation']={'both_colors':True,'confidence':notes['explanation']['confidence'],
                                      'before_move_arrows':True,'why_recommendation_present':True,'variation_animation':True}
                window.settings.save()
                finish(True,'14 forward/backward transitions, rapid navigation, semantic colors, offline ideas and laptop DPI layout passed')
        except Exception as error:
            finish(False,f'{type(error).__name__}: {error}')
    timer.timeout.connect(tick);timer.start()
    return timer
