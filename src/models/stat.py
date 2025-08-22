from datetime import timedelta
import logging

class Stat:
    def __init__(self, db):
        self.db = db

    def first_or_none(self, lst):
        """Retourne le premier élément d'une liste ou None si vide"""
        return lst[0] if lst else None

    def _get_period(self, i):
        """Retourne (begin, end) pour un usage point i (exemple placeholder)"""
        # Remplacer par la logique réelle de calcul de période
        from datetime import datetime
        begin = datetime.now()
        end = datetime.now()
        return begin, end

    def tempo(self, i):
        """Retourne les données TEMPO pour le point d'utilisation i"""
        begin, end = self._get_period(i)

        tempo_list = self.db.get_tempo_range(begin - timedelta(days=1), end - timedelta(days=1))
        first_item = self.first_or_none(tempo_list)

        if first_item is None:
            logging.warning(f"Aucune donnée TEMPO trouvée pour {begin - timedelta(days=1)} à {end - timedelta(days=1)} (usage_point {i})")
            return {"value": None, "color": None}

        return {"value": first_item.value, "color": first_item.color}

    def daily_summary(self, i):
        """Exemple de fonction récupérant une liste pour un résumé quotidien"""
        lst = self.db.get_daily_data(i)
        first_item = self.first_or_none(lst)
        if first_item is None:
            logging.warning(f"Aucune donnée quotidienne trouvée pour {i}")
            return None
        return first_item
