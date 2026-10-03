"""Causal analysis, engine budget, responsive UI and synchronized variants in the actual exe."""
from __future__ import annotations

import json
import time

import chess
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from app.services.explanation_corpus import run_corpus
from app.ui.dialogs import AnalysisDialog
from app.ui.workers import Worker


def attach_explanations_smoke(app,window,report_path):
    state={'started':time.monotonic(),'heartbeats':0,'corpus':None}
    timer=QTimer(window);timer.setInterval(50)
    window.sounds.set_enabled(False)

    def finish(success,message):
        timer.stop()
        report={'success':success,'message':message,'window_visible':window.isVisible(),
                'ui_heartbeats_during_analysis':state['heartbeats'],'corpus':state['corpus'],
                'variant_selection':state.get('variant_selection')}
        window.close()
        report['engine_closed']=window.engine._engine is None
        report['database_created']=(window.directory/'chess.sqlite3').is_file()
        report['settings_created']=(window.directory/'settings.json').is_file()
        report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        app.exit(0 if success else 1)

    def result(token,kind,corpus):
        try:
            state['corpus']=corpus
            assert state['heartbeats']>=3,'Final analysis blocked the GUI event loop'
            checked=[]
            for color in (True,False):
                record=next(g for g in corpus['games'] if g['name']=='queen_loss' and g['player_color']==color)
                row={'result':'*','accuracy':record['metrics']['accuracy'],'player_color':color,
                     'pgn':record['pgn'],'analysis':json.dumps(record['explanations'])}
                dialog=AnalysisDialog(row,window);dialog.show();QApplication.processEvents()
                original=dialog.game.pgn();value=dialog.current_explanation
                assert value['reason_type']=='material_loss' and value['confidence']=='high'
                assert value['opponent_pv'] and dialog.response_label.text()
                assert dialog.board.tactical_highlights
                assert dialog.explanation_debug.isHidden()
                assert len(value['alternatives'])>=2
                assert len({a['idea'] for a in value['alternatives']})==len(value['alternatives'])
                for index,alternative in enumerate(dialog.alternatives):
                    dialog.variations.setCurrentRow(index)
                    detail=next(a for a in value['alternatives'] if a['uci']==alternative['uci'])
                    assert dialog.recommendation.text()==detail['idea']
                    move=chess.Move.from_uci(detail['uci'])
                    assert (move.from_square,move.to_square,'recommended') in dialog.board.annotations
                    assert dialog.board.tactical_highlights==set(detail['key_squares'])
                    assert dialog.game.pgn()==original and not dialog.board.interactive
                    if index==1:
                        QApplication.processEvents()
                        dialog.grab().save(str(report_path.with_name('explanations-'+('white' if color else 'black')+'.png')))
                dialog.return_to_actual()
                assert dialog.game.pgn()==original and not dialog.board.tactical_highlights
                assert dialog.board.board.fen()==dialog.game.board.fen()
                dialog.close();checked.append(color)
            state['variant_selection']={'both_colors':checked,'text_arrows_key_squares_synced':True,
                                        'pgn_unchanged':True,'developer_values_hidden':True}
            finish(True,f"12 PGN games: {sum(corpus['reason_categories'].values())} matched-depth explanations; causal evidence and both-color variant UI passed")
        except Exception as error:finish(False,f'{type(error).__name__}: {error}')

    def tick():
        state['heartbeats']+=1
        if time.monotonic()-state['started']>85:
            finish(False,'Explanatory corpus timed out')

    worker=Worker(window.token,'explanation-corpus',lambda progress:run_corpus(window.engine,progress))
    worker.signals.result.connect(result)
    worker.signals.error.connect(lambda token,kind,message:finish(False,message))
    window.explanation_smoke_worker=worker
    timer.timeout.connect(tick);timer.start()
    window.pool.start(worker)
    return timer
