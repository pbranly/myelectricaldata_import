from datetime import datetime, timedelta
import logging
import pytz
from init import DB  # Import ajouté pour accéder à la base de données

UTC = pytz.UTC


class Stat:
    def __init__(self, usage_point_id, measurement_direction=None):
        """
        Constructeur corrigé pour recevoir usage_point_id au lieu de db
        """
        self.usage_point_id = usage_point_id
        self.db = DB
        self.measurement_direction = measurement_direction

    def first_or_none(self, lst):
        return lst[0] if lst else None

    def _get_period(self, i):
        """Calcul de période pour le jour i (0=aujourd'hui, 1=hier, etc.)"""
        target_date = datetime.now(tz=UTC) - timedelta(days=i)
        begin = datetime.combine(target_date, datetime.min.time())
        end = datetime.combine(target_date, datetime.max.time())
        return begin, end

    def tempo(self, i):
        """Retourne les données Tempo du jour i"""
        begin, end = self._get_period(i)
        tempo_list = self.db.get_tempo_range(begin, end)
        first_item = self.first_or_none(tempo_list)
        if first_item is None:
            logging.warning(f"Aucune donnée TEMPO trouvée pour le jour {i}")
            return {"value": None, "color": None}

        if hasattr(first_item, 'detail') and first_item.detail:
            try:
                import json
                detail = json.loads(first_item.detail.replace("'", '"'))
                return {"value": detail, "color": first_item.color}
            except Exception:
                pass

        return {"value": first_item.value, "color": first_item.color}

    def daily_summary(self, i):
        """Résumé quotidien pour un point d'usage"""
        begin, end = self._get_period(i)
        lst = self.db.get_daily_range(self.usage_point_id, begin, end)
        first_item = self.first_or_none(lst)
        if first_item is None:
            logging.warning(f"Aucune donnée quotidienne trouvée pour le jour {i}")
            return None
        return first_item

    def daily(self, i):
        """Récupère les données quotidiennes pour le jour i"""
        begin, end = self._get_period(i)
        data = self.db.get_daily_range(self.usage_point_id, begin, end, self.measurement_direction)
        first_item = self.first_or_none(data)
        if first_item is None:
            logging.warning(f"Aucune donnée quotidienne trouvée pour le jour {i}")
            return {"begin": begin.strftime("%Y-%m-%d"), "end": end.strftime("%Y-%m-%d"), "value": 0}
        return {
            "begin": begin.strftime("%Y-%m-%d"),
            "end": end.strftime("%Y-%m-%d"),
            "value": first_item.value
        }

    def detail(self, i, period_type):
        """Récupère les détails HP/HC pour le jour i"""
        begin, end = self._get_period(i)
        data = self.db.get_detail_range(self.usage_point_id, begin, end, self.measurement_direction, period_type)
        total = sum(d.value for d in data) if data else 0
        return {
            "begin": begin.strftime("%Y-%m-%d"),
            "end": end.strftime("%Y-%m-%d"),
            "value": total
        }

    def max_power(self, i):
        """Puissance maximale pour le jour i"""
        begin, end = self._get_period(i)
        data = self.db.get_max_power(self.usage_point_id, begin, end)
        if data:
            return {"value": data.value, "date": data.date}
        return {"value": 0, "date": None}

    def max_power_time(self, i):
        """Heure de la puissance maximale pour le jour i"""
        begin, end = self._get_period(i)
        data = self.db.get_max_power(self.usage_point_id, begin, end)
        if data and hasattr(data, 'date'):
            return {"value": data.date.strftime("%H:%M:%S")}
        return {"value": "00:00:00"}

    def max_power_over(self, i):
        """Dépassement de puissance pour le jour i"""
        begin, end = self._get_period(i)
        return {"value": 0}  # Placeholder

    def tempo_color(self, i):
        """Couleur Tempo pour le jour i"""
        tempo_data = self.tempo(i)
        return {"value": tempo_data["color"] if tempo_data["color"] else "Inconnu"}

    # ---------------------------------------------------------------------
    # Fonctions statistiques utilisées par export_home_assistant.py
    # ---------------------------------------------------------------------

    def current_week(self):
        today = datetime.now(tz=UTC)
        start_of_week = today - timedelta(days=today.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        data = self.db.get_range(self.usage_point_id, start_of_week, end_of_week, self.measurement_direction)
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
        data = self.db.get_range(self.usage_point_id, start_of_week, end_of_week, self.measurement_direction)
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
        data = self.db.get_range(self.usage_point_id, start_of_week, end_of_week, self.measurement_direction)
        total = sum(d.value for d in data) if data else 0
        return {
            "begin": start_of_week.strftime("%Y-%m-%d"),
            "end": end_of_week.strftime("%Y-%m-%d"),
            "value": total,
        }

    def current_month(self):
        today = datetime.now(tz=UTC)
        start_of_month = today.replace(day=1)
        if today.month == 12:
            next_month = today.replace(year=today.year + 1, month=1, day=1)
        else:
            next_month = today.replace(month=today.month + 1, day=1)
        end_of_month = next_month - timedelta(days=1)
        data = self.db.get_range(self.usage_point_id, start_of_month, end_of_month, self.measurement_direction)
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
        data = self.db.get_range(self.usage_point_id, start_of_last_month, last_day_last_month, self.measurement_direction)
        total = sum(d.value for d in data) if data else 0
        return {
            "begin": start_of_last_month.strftime("%Y-%m-%d"),
            "end": last_day_last_month.strftime("%Y-%m-%d"),
            "value": total,
        }

    def current_month_last_year(self):
        today = datetime.now(tz=UTC)
        start_of_month = today.replace(year=today.year - 1, day=1)
        if today.month == 12:
            next_month = today.replace(year=today.year, month=1, day=1)
        else:
            next_month = today.replace(year=today.year - 1, month=today.month + 1, day=1)
        end_of_month = next_month - timedelta(days=1)
        data = self.db.get_range(self.usage_point_id, start_of_month, end_of_month, self.measurement_direction)
        total = sum(d.value for d in data) if data else 0
        return {
            "begin": start_of_month.strftime("%Y-%m-%d"),
            "end": end_of_month.strftime("%Y-%m-%d"),
            "value": total,
        }

    def last_month_last_year(self):
        today = datetime.now(tz=UTC)
        target_date = today.replace(year=today.year - 1)
        first_of_this_month = target_date.replace(day=1)
        last_day_last_month = first_of_this_month - timedelta(days=1)
        start_of_last_month = last_day_last_month.replace(day=1)
        data = self.db.get_range(self.usage_point_id, start_of_last_month, last_day_last_month, self.measurement_direction)
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
        data = self.db.get_range(self.usage_point_id, start_of_year, end_of_year, self.measurement_direction)
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
        data = self.db.get_range(self.usage_point_id, start_of_last_year, end_of_last_year, self.measurement_direction)
        total = sum(d.value for d in data) if data else 0
        return {
            "begin": start_of_last_year.strftime("%Y-%m-%d"),
            "end": end_of_last_year.strftime("%Y-%m-%d"),
            "value": total,
        }

    def current_year_last_year(self):
        today = datetime.now(tz=UTC)
        start_of_year = today.replace(year=today.year - 1, month=1, day=1)
        end_of_year = today.replace(year=today.year - 1, month=12, day=31)
        data = self.db.get_range(self.usage_point_id, start_of_year, end_of_year, self.measurement_direction)
        total = sum(d.value for d in data) if data else 0
        return {
            "begin": start_of_year.strftime("%Y-%m-%d"),
            "end": end_of_year.strftime("%Y-%m-%d"),
            "value": total,
        }

    # ---------------------------------------------------------------------
    # Nouvelles méthodes pour les calculs d'évolution et statistiques
    # ---------------------------------------------------------------------

    def yesterday_hc_hp(self):
        """Récupère les données HC/HP d'hier"""
        begin, end = self._get_period(1)
        hc_data = self.db.get_detail_range(self.usage_point_id, begin, end, self.measurement_direction, "HC")
        hp_data = self.db.get_detail_range(self.usage_point_id, begin, end, self.measurement_direction, "HP")

        hc_total = sum(d.value for d in hc_data) if hc_data else 0
        hp_total = sum(d.value for d in hp_data) if hp_data else 0

        return {
            "begin": begin.strftime("%Y-%m-%d"),
            "end": end.strftime("%Y-%m-%d"),
            "value": {"hc": hc_total, "hp": hp_total}
        }

    def peak_offpeak_percent(self):
        """Calcule le pourcentage heures pleines/creuses sur les 30 derniers jours"""
        end_date = datetime.now(tz=UTC)
        start_date = end_date - timedelta(days=30)

        hp_data = self.db.get_detail_range(self.usage_point_id, start_date, end_date, self.measurement_direction, "HP")
        hc_data = self.db.get_detail_range(self.usage_point_id, start_date, end_date, self.measurement_direction, "HC")

        hp_total = sum(d.value for d in hp_data) if hp_data else 0
        hc_total = sum(d.value for d in hc_data) if hc_data else 0
        total = hp_total + hc_total

        if total == 0:
            return 0

        return (hp_total / total) * 100

    def current_week_evolution(self):
        """Évolution de la semaine courante par rapport à la semaine dernière"""
        current = self.current_week()["value"]
        last = self.last_week()["value"]

        if last == 0:
            return 0
        return ((current - last) / last) * 100

    def current_month_evolution(self):
        """Évolution du mois courant par rapport au mois dernier"""
        current = self.current_month()["value"]
        last = self.last_month()["value"]

        if last == 0:
            return 0
        return ((current - last) / last) * 100

    def yesterday_evolution(self):
        """Évolution d'hier par rapport au même jour la semaine dernière"""
        yesterday = self.daily(1)["value"]
        last_week_same_day = self.daily(8)["value"]

        if last_week_same_day == 0:
            return 0
        return ((yesterday - last_week_same_day) / last_week_same_day) * 100

    def monthly_evolution(self):
        """Évolution mensuelle moyenne sur les 12 derniers mois"""
        current_month = self.current_month()["value"]
        last_month = self.last_month()["value"]

        if last_month == 0:
            return 0
        return ((current_month - last_month) / last_month) * 100

    def yearly_evolution(self):
        """Évolution annuelle"""
        current_year = self.current_year()["value"]
        last_year = self.last_year()["value"]

        if last_year == 0:
            return 0
        return ((current_year - last_year) / last_year) * 100
