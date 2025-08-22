class Stat:
    def __init__(self, db, measurement_direction=None):
        self.db = db
        self.measurement_direction = measurement_direction

    def first_or_none(self, lst):
        return lst[0] if lst else None

    def _get_period(self, i):
        from datetime import datetime
        begin = datetime.now()
        end = datetime.now()
        return begin, end

    def tempo(self, i):
        begin, end = self._get_period(i)
        tempo_list = self.db.get_tempo_range(begin - timedelta(days=1), end - timedelta(days=1))
        first_item = self.first_or_none(tempo_list)
        if first_item is None:
            logging.warning(f"Aucune donnée TEMPO trouvée pour {i}")
            return {"value": None, "color": None}
        return {"value": first_item.value, "color": first_item.color}

    def daily_summary(self, i):
        lst = self.db.get_daily_data(i)
        first_item = self.first_or_none(lst)
        if first_item is None:
            logging.warning(f"Aucune donnée quotidienne trouvée pour {i}")
            return None
        return first_item
