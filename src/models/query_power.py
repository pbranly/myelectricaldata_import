import json
import logging
from datetime import datetime, timedelta

from config import DAILY_MAX_DAYS, URL
from init import CONFIG, DB
from models.query import Query


def daterange(start_date, end_date):
    for n in range(int((end_date - start_date).days)):
        yield start_date + timedelta(n)


class Power:
    def __init__(self, headers, usage_point_id):
        self.config = CONFIG
        self.db = DB
        self.url = URL
        self.max_daily = 1095
        self.date_format = "%Y-%m-%d"
        self.date_format_detail = "%Y-%m-%d %H:%M:%S"
        self.headers = headers
        self.usage_point_id = usage_point_id
        self.usage_point_config = self.db.get_usage_point(self.usage_point_id)
        self.contract = self.db.get_contract(self.usage_point_id)
        self.daily_max_days = DAILY_MAX_DAYS
        self.max_days_date = datetime.utcnow() - timedelta(days=self.daily_max_days)
        if (
            hasattr(self.usage_point_config, "consumption_max_date")
            and self.usage_point_config.consumption_max_date
        ):
            self.activation_date = self.usage_point_config.consumption_max_date
        elif (
            hasattr(self.contract, "last_activation_date")
            and self.contract.last_activation_date
        ):
            self.activation_date = self.contract.last_activation_date
        else:
            self.activation_date = self.max_days_date

    def safe_json_loads(self, text):
        """Charge du JSON de manière sécurisée, même si vide ou invalide."""
        if not text or not text.strip():
            return {}
        try:
            return json.loads(text)
        except Exception:
            logging.warning(f"Réponse non JSON ou invalide : {text[:200]}")
            return {}

    def run(self, begin, end):
        begin_str = begin.strftime(self.date_format)
        end_str = end.strftime(self.date_format)
        logging.info(f"Récupération des données : {begin_str} => {end_str}")

        endpoint = f"daily_consumption_max_power/{self.usage_point_id}/start/{begin_str}/end/{end_str}"
        if hasattr(self.usage_point_config, "cache") and self.usage_point_config.cache:
            endpoint += "/cache"

        try:
            current_data = self.db.get_daily_power(self.usage_point_id, begin, end)
            if not current_data["missing_data"]:
                logging.info(" => Toutes les données sont déjà en cache.")
                output = []
                for date, data in current_data["date"].items():
                    output.append({"date": date, "value": data["value"]})
                return output

            logging.info(f" Chargement des données depuis MyElectricalData {begin_str} => {end_str}")
            data = Query(endpoint=f"{self.url}/{endpoint}/", headers=self.headers).get()
            max_histo = datetime.combine(datetime.now(), datetime.max.time()) - timedelta(days=1)
            blacklist = 0

            if hasattr(data, "status_code"):
                if data.status_code == 200:
                    parsed = self.safe_json_loads(getattr(data, "text", ""))
                    meter_reading = parsed.get("meter_reading")
                    if not meter_reading:
                        return {
                            "error": True,
                            "description": "Réponse invalide de MyElectricalData",
                            "status_code": 200,
                        }

                    interval_reading = meter_reading.get("interval_reading", [])
                    interval_reading_tmp = {}
                    for interval_reading_data in interval_reading:
                        date = datetime.strptime(interval_reading_data["date"], self.date_format_detail)
                        date = datetime.combine(date, datetime.min.time())
                        interval_reading_tmp[date.strftime(self.date_format)] = {
                            "date": datetime.strptime(
                                interval_reading_data["date"],
                                self.date_format_detail,
                            ),
                            "value": interval_reading_data["value"],
                        }

                    for single_date in daterange(begin, end):
                        if single_date < max_histo:
                            date_key = single_date.strftime(self.date_format)
                            if date_key in interval_reading_tmp:
                                single_date_value = interval_reading_tmp[date_key]
                                self.db.insert_daily_max_power(
                                    usage_point_id=self.usage_point_id,
                                    date=datetime.combine(single_date, datetime.min.time()),
                                    event_date=single_date_value["date"],
                                    value=single_date_value["value"],
                                    blacklist=blacklist,
                                )
                            else:
                                self.db.daily_max_power_fail_increment(
                                    usage_point_id=self.usage_point_id,
                                    date=datetime.combine(single_date, datetime.min.time()),
                                )
                    return interval_reading

                # Status code != 200
                parsed = self.safe_json_loads(getattr(data, "text", ""))
                description = parsed.get("detail", getattr(data, "text", "Erreur inconnue"))
                return {
                    "error": True,
                    "description": description,
                    "status_code": data.status_code,
                }

            # Cas où data n’a pas de status_code
            parsed = self.safe_json_loads(getattr(data, "text", ""))
            return {
                "error": True,
                "description": parsed.get("detail", str(data)),
                "status_code": getattr(data, "status_code", 500),
            }

        except Exception as e:
            logging.exception(e)
            logging.error(e)
            return {
                "error": True,
                "description": str(e),
                "status_code": 500,
            }

    def get(self):
        end = datetime.combine((datetime.now() + timedelta(days=2)), datetime.max.time())
        begin = datetime.combine(end - timedelta(days=self.max_daily), datetime.min.time())
        finish = True
        result = []

        while finish:
            if self.max_days_date > begin:
                begin = self.max_days_date
                finish = False
                response = self.run(begin, end)
            elif self.activation_date and self.activation_date > begin:
                begin = self.activation_date
                finish = False
                response = self.run(begin, end)
            else:
                response = self.run(begin, end)
                begin = begin - timedelta(days=self.max_daily)
                end = end - timedelta(days=self.max_daily)

            if not response:
                response = {
                    "error": True,
                    "description": "MyElectricalData est indisponible.",
                }

            if isinstance(response, list):
                result.extend(response)
            elif isinstance(response, dict) and response.get("error"):
                logging.error("Echec de la récupération des données.")
                logging.error(f' => {response["description"]}')
                logging.error(f" => {begin.strftime(self.date_format)} -> {end.strftime(self.date_format)}")

        return result

    def reset(self, date=None):
        if date is not None:
            date = datetime.strptime(date, self.date_format)
        self.db.reset_daily_max_power(self.usage_point_id, date)
        return True

    def delete(self, date=None):
        if date is not None:
            date = datetime.strptime(date, self.date_format)
        self.db.delete_daily_max_power(self.usage_point_id, date)
        return True

    def blacklist(self, date, action):
        if date is not None:
            date = datetime.strptime(date, self.date_format)
        self.db.blacklist_daily_max_power(self.usage_point_id, date, action)
        return True

    def fetch(self, date):
        if date is not None:
            date = datetime.strptime(date, self.date_format)
        result = self.run(
            date - timedelta(days=1),
            date + timedelta(days=1),
        )
        if isinstance(result, dict) and result.get("error"):
            return {
                "error": True,
                "notif": result["description"],
                "fail_count": self.db.get_daily_max_power_fail_count(self.usage_point_id, date),
            }

        for item in result:
            target_date = datetime.strptime(item["date"], self.date_format_detail).strftime(self.date_format)
            event_date = datetime.strptime(item["date"], self.date_format_detail).strftime("%H:%M:%S")
            if date.strftime(self.date_format) == target_date:
                item["date"] = target_date
                item["event_date"] = event_date
                return item

        return {
            "error": True,
            "notif": f"Aucune donnée n'est disponible chez Enedis sur cette date ({date})",
            "fail_count": self.db.get_daily_max_power_fail_count(self.usage_point_id, date),
        }
