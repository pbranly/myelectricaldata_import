from datetime import datetime, timedelta
import logging
import pytz

UTC = pytz.UTC

class Stat:
    def __init__(self, db, measurement_direction=None):
        self.db = db
        self.measurement_direction = measurement_direction

    def first_or_none(self, lst):
        return lst[0] if lst else None

    def _get_period(self, i):
        """Placeholder pour calcul de période"""
        begin = datetime.now()
        end = datetime.now()
        return begin, end

    def tempo(self, i):
        """Retourne les données Tempo du jour précédent"""
        begin, end = self._get_period(i)
        tempo_list = self.db.get_tempo_range(begin - timedelta(days=1), end - timedelta(days=1))
        first_item = self.first_or_none(tempo_list)
        if first_item is None:
            logging.warning(f"Aucune donnée TEMPO trouvée pour {i}")
            return {"value": None, "color": None}
        return {"value": first_item.value, "color": first_item.color}

    def daily_summary(self, i):
        """Résumé quotidien pour un point d’usage"""
        lst = self.db.get_daily_data(i)
        first_item = self.first_or_none(lst)
        if first_item is None:
            logging.warning(f"Aucune donnée quotidienne trouvée pour {i}")
            return None
        return first_item

    # ---------------------------------------------------------------------
    # Fonctions statistiques utilisées par export_home_assistant.py
    # ---------------------------------------------------------------------

    def current_week(self):
        today = datetime.now(tz=UTC)
        start_of_week = today - timedelta(days=today.weekday())   # lundi
        end_of_week = start_of_week + timedelta(days=6)           # dimanche
        data = self.db.get_range(start_of_week, end_of_week, self.measurement_direction)
        total = sum(d.value for d in data) if data else 0
        return {
            "begin": start_of_week.strftime("%Y-%m-%d"),
            "end": end_of_week.strftime("%Y-%m-%d"),
            "value": total,
        }

    def last_week(self):
        today = datetime.now(tz=UTC)
        start_of_week = today - timedelta(days=today.weekday() + 7)
        end_of_week = start_of_week + timedelta(days=6)
        data = self.db.get_range(start_of_week, end_of_week, self.measurement_direction)
        total = sum(d.value for d in data) if data else 0
        return {
            "begin": start_of_week.strftime("%Y-%m-%d"),
            "end": end_of_week.strftime("%Y-%m-%d"),
            "value": total,
        }

    def current_week_last_year(self):
        today = datetime.now(tz=UTC)
        start_of_week = (today - timedelta(days=today.weekday())).replace(year=today.year - 1)
        end_of_week = start_of_week + timedelta(days=6)
        data = self.db.get_range(start_of_week, end_of_week, self.measurement_direction)
        total = sum(d.value for d in data) if data else 0
        return {
            "begin": start_of_week.strftime("%Y-%m-%d"),
            "end": end_of_week.strftime("%Y-%m-%d"),
            "value": total,
        }

    def current_month(self):
        today = datetime.now(tz=UTC)
        start_of_month = today.replace(day=1)
        # mois suivant
        if today.month == 12:
            next_month = today.replace(year=today.year + 1, month=1, day=1)
        else:
            next_month = today.replace(month=today.month + 1, day=1)
        end_of_month = next_month - timedelta(days=1)
        data = self.db.get_range(start_of_month, end_of_month, self.measurement_direction)
        total = sum(d.value for d in data) if data else 0
        return {
            "begin": start_of_month.strftime("%Y-%m-%d"),
            "end": end_of_month.strftime("%Y-%m-%d"),
            "value": total,
        }

    def last_month(self):
        today = datetime.now(tz=UTC)
        first_of_this_month = today.replace(day=1)
        last_day_last_month = first_of_this_month - timedelta(days=1)
        start_of_last_month = last_day_last_month.replace(day=1)
        data = self.db.get_range(start_of_last_month, last_day_last_month, self.measurement_direction)
        total = sum(d.value for d in data) if data else 0
        return {
            "begin": start_of_last_month.strftime("%Y-%m-%d"),
            "end": last_day_last_month.strftime("%Y-%m-%d"),
            "value": total,
        }

    def current_year(self):
        today = datetime.now(tz=UTC)
        start_of_year = today.replace(month=1, day=1)
        end_of_year = today.replace(month=12, day=31)
        data = self.db.get_range(start_of_year, end_of_year, self.measurement_direction)
        total = sum(d.value for d in data) if data else 0
        return {
            "begin": start_of_year.strftime("%Y-%m-%d"),
            "end": end_of_year.strftime("%Y-%m-%d"),
            "value": total,
        }

    def last_year(self):
        today = datetime.now(tz=UTC)
        start_of_last_year = today.replace(year=today.year - 1, month=1, day=1)
        end_of_last_year = today.replace(year=today.year - 1, month=12, day=31)
        data = self.db.get_range(start_of_last_year, end_of_last_year, self.measurement_direction)
        total = sum(d.value for d in data) if data else 0
        return {
            "begin": start_of_last_year.strftime("%Y-%m-%d"),
            "end": end_of_last_year.strftime("%Y-%m-%d"),
            "value": total,
        }
