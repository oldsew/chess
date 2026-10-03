"""Local per-game calibration records. No telemetry, PGN edits or rating evidence changes."""
from __future__ import annotations

from collections import Counter
import json
import logging
from pathlib import Path
import statistics

log = logging.getLogger(__name__)
BINS = ('0–25','25–50','50–100','100–150','150–250','>250')


class GameCalibration:
    def __init__(self,directory:Path,game):
        self.path = directory/'calibration'/f'game-{game.database_id}.json'
        self.records = []
        self.metadata = {'schema':1,'game_id':game.database_id,'player_rating':game.rating_before,
                         'target_bot_rating':game.bot_rating,'player_color':'white' if game.player_color else 'black',
                         'time_control':game.time_control.key,'result':game.result}
        try:
            data = json.loads(self.path.read_text(encoding='utf-8'))
            if isinstance(data,dict) and data.get('schema') == 1 and data.get('game_id') == game.database_id and isinstance(data.get('moves'),list):
                records = data['moves']
                if all(isinstance(r,dict) and all(type(r.get(k)) is int and r[k] >= 0 for k in ['ply','cpl','rank'])
                       and type(r.get('unique_best')) is bool for r in records):
                    self.records = records
        except FileNotFoundError:
            pass
        except (ValueError,OSError):
            log.exception('Cannot read optional calibration record')

    def _save(self):
        try:
            self.path.parent.mkdir(parents=True,exist_ok=True)
            temp = self.path.with_suffix('.tmp')
            temp.write_text(json.dumps({**self.metadata,'moves':self.records,'summary':self.summary()},ensure_ascii=False,indent=2),encoding='utf-8')
            temp.replace(self.path)
        except OSError:
            # Optional diagnostics must never prevent a legal move or its SQLite autosave.
            log.exception('Cannot save optional calibration diagnostics')

    def record(self,game,selection):
        if game.database_id != self.metadata['game_id']:
            return
        ply = len(game.board.move_stack)
        if any(r['ply'] == ply for r in self.records):
            return
        chosen = next(c for c in selection.candidates if c['uci'] == selection.move.uci())
        self.records.append({'ply':ply,'uci':chosen['uci'],'san':chosen['move'],'target_bot_rating':game.bot_rating,
                             'evaluation':chosen['evaluation'],'mate':chosen['mate'],'cpl':chosen['cpl'],
                             'rank':selection.selected_rank,'unique_best':selection.unique_best,
                             'profile':selection.profile})
        self.metadata.update(result=game.result,duration_seconds=game.elapsed_seconds)
        self._save()

    def complete(self,game,metrics=None):
        if game.database_id != self.metadata['game_id']:
            return
        self.metadata.update(result=game.result,termination=game.termination,duration_seconds=game.elapsed_seconds)
        if metrics:
            self.metadata['player_accuracy'] = metrics.accuracy
        self._save()

    def summary(self):
        values = [r['cpl'] for r in self.records]
        bins = Counter(BINS[sum(value > t for t in [25,50,100,150,250])] for value in values)
        ranks = Counter(str(r['rank']) if r['rank'] <= 3 else 'lower' for r in self.records)
        unique = [r for r in self.records if r['unique_best']]
        return {'moves':len(values),'distribution':{name:bins[name] for name in BINS},
                'average_cpl':sum(values)/len(values) if values else 0,
                'median_cpl':statistics.median(values) if values else 0,
                'inaccuracies':sum(40 < c <= 90 for c in values),'mistakes':sum(90 < c <= 200 for c in values),
                'blunders':sum(c > 200 for c in values),'ranks':{name:ranks[name] for name in ['1','2','3','lower']},
                'unique_best_positions':len(unique),'unique_best_found':sum(r['rank'] == 1 for r in unique)}
